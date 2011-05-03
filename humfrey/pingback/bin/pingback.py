import pickle, base64, urllib, urllib2, sys, threading, Queue, logging, time, rdflib, urlparse, hashlib, socket
from collections import defaultdict
from functools import wraps

from django.conf import settings

import redis
from lxml import etree

WORKER_COUNT = 8

logging.basicConfig(stream=sys.stderr)
logger = logging.getLogger('pingback')

RDF_MEDIA_TYPES = {
    'application/rdf+xml': 'xml',
    'text/n3': 'n3',
    'text/turtle': 'n3',
}

TARGET_HOSTS = frozenset(['data.ox.ac.uk', 'oxpoints.oucs.ox.ac.uk'])

SIOC = rdflib.Namespace('http://rdfs.org/sioc/ns#')
DCTERMS = rdflib.Namespace('http://purl.org/dc/terms/')
VOID = rdflib.Namespace('http://rdfs.org/ns/void#')
DC = rdflib.Namespace('http://purl.org/dc/elements/1.1/')
FOAF = rdflib.Namespace('http://xmlns.com/foaf/0.1/')
RDFS = rdflib.Namespace('http://www.w3.org/2000/01/rdf-schema#')

NS = {'sioc': SIOC, 'dcterms': DCTERMS, 'void': VOID, 'dc':DC, 'foaf': FOAF, 'rdfs': RDFS}

LABEL_PREDICATES = (RDFS.label, FOAF.name, DCTERMS['title'], DC['title'])

def get_redis_client():
    return redis.Redis(host=getattr(settings, 'REDIS_HOST', 'localhost'),
                       port=getattr(settings, 'REDIS_PORT', 6379))
class PutRequest(urllib2.Request):
    def get_method(self):
        return 'PUT'

# Bailing infrastructure

def bailable(f):
    @wraps(f)
    def g(*args, **kwargs):
        bail = kwargs['bail']
        try:
            return f(*args, **kwargs)
        except:
            bail.set()
            raise
    return g

def bailer(bail, *queues):
    bail.wait()
    for queue in queues:
        queue.put(None)


def process(data):
    source, target = (rdflib.URIRef(data[x]) for x in ('source', 'target'))

    request = urllib2.Request(source)
    request.headers['Accept'] = 'application/rdf+xml, text/n3, text/turtle, application/xhtml+xml;q=0.9; text/html;q=0.8'

    try:
        response = urllib2.urlopen(request)
    except (ValueError, urllib2.URLError), e:
        logger.warning('Problem with URL for %r' % data['source'])
        return
    except urllib2.HTTPError, e:
        logger.warning('Could not retrieve source: %r' % data['source'])
        return
        
    content_type = response.headers.get('Content-Type', '').split(';')[0].lower()
    
    graph, graph_metadata = rdflib.ConjunctiveGraph(), rdflib.ConjunctiveGraph()
    for prefix in NS:
        graph.namespace_manager.bind(prefix, NS[prefix])
        graph_metadata.namespace_manager.bind(prefix, NS[prefix])
    
    if content_type in ('application/xhtml+xml', 'text/html'):
        process_html(source, target, response, graph)
    elif content_type in RDF_MEDIA_TYPES:
        process_rdf(source, target, response, graph, RDF_MEDIA_TYPES[content_type])
    else:
        logger.warning('Unexpected media type for %r: %r' % (data['source'], content_type))
        response.close()
        return
    
    if not graph:
        return
    
    graph_name = rdflib.URIRef('http://data.ox.ac.uk/graph/pingback/' + data['hash'])
    
    graph_metadata += (
        (graph_name, DCTERMS.created, rdflib.Literal(data['date'])),
        (graph_name, DCTERMS.source, rdflib.URIRef(response.geturl())),
        (graph_name, VOID.inDataset, rdflib.URIRef('http://data.ox.ac.uk/id/dataset/pingbacks')),
        (graph_name, DCTERMS['title'], rdflib.Literal(u'Pingback from %s to %s' % (unicode(source), unicode(target)))),
    )
    
    data['graph'] = graph
    data['graph_metadata'] = graph_metadata
    data['graph_name'] = graph_name
    data['hostname'] = socket.gethostbyaddr(data['remote_addr'])[0]
    
    return data

def process_html(source, target, response, graph):
    html = etree.parse(response, parser=etree.HTMLParser())
    
    for anchor in html.xpath(".//a"):
        if anchor.get('href') == str(target):
            break
    else:
        return
        
    title = html.xpath('.//head/title')
    if title and title[0].text:
        graph.add((source, DCTERMS['title'], rdflib.Literal(title[0].text)))
        
    
    graph.add((source, SIOC.links_to, target))

def process_rdf(source, target, response, graph, format):
    def add_labels(uri):
        for p in LABEL_PREDICATES:
            triples = list(source_graph.triples((uri, p, None)))
            if triples:
                graph.__iadd__(triples)
                break
    
    source_graph = rdflib.ConjunctiveGraph()
    try:
        source_graph.parse(response, format=format)
    except Exception:
        logger.exception("Could not parse remote graph")
        return
        
    for s, p in source_graph.subject_predicates(target):
        if isinstance(s, rdflib.URIRef):
            graph.add((s, p, target))
            add_labels(s)
    for p, o in source_graph.predicate_objects(target):
        if isinstance(o, rdflib.URIRef):
            graph.add((target, p, o))
            add_labels(o) 
    
@bailable
def worker(client_locks, host_locks, queue_new, queue_pending, bail):
    while not bail.is_set():
        data = queue_new.get()
        if data is None:
            queue_new.put(None)
            break
        
        source_url = urlparse.urlparse(data['source'])
        source_host = source_url.netloc.split(':')[0].lower()
        
        target_url = urlparse.urlparse(data['target'])
        target_host = source_url.netloc.split(':')[0].lower()
        
        if target_host not in TARGET_HOSTS:
            logging.warning('Pingback for non-targetable host: %r' % data['target'])
            continue
        if source_url.scheme not in ('http', 'https', 'ftp'):
            logging.warning('Unsupported scheme for pingback')
            continue
            
        
        client_lock = client_locks[data['remote_addr']]
        host_lock = host_locks[source_host]
        
        with client_lock, host_lock:
            data = process(data)
            if data is not None:
                queue_pending.put(data)
            time.sleep(1)
        

@bailable
def pending_manager(queue_pending, bail):
    client = get_redis_client()
    
    while not bail.is_set():
        data = queue_pending.get()
        if data is None:
            break
        data['state'] = 'pending'
 
        client.set('pingback.data:%s' % data['hash'], base64.b64encode(pickle.dumps(data)))
        client.sadd('pingback.pending', data['hash'])

def accepted_manager(queue_accepted, bail):
    client = get_redis_client()
    
    while not bail.is_set():
        data = queue_accepted.get()
        if data is None:
            break
        
        graph = data['graph']
        graph += data['graph_metadata']
        
        url = 'http://localhost:3030/dataset/data?%s' % urllib.urlencode({'graph': data['graph_name']})
        request = PutRequest(url, data=graph.serialize())
        request.headers['Content-type'] = 'application/rdf+xml'
        try:
            response = urllib2.urlopen(request)
        except urllib2.HTTPError, e:
            if e.code not in (201, 204,):
                raise
def run():
    client_locks, host_locks = defaultdict(threading.Lock), defaultdict(threading.Lock)
    bail = threading.Event()
    queue_new, queue_pending, queue_accepted = (Queue.Queue() for i in range(3))
    
    worker_pool = []
    for i in range(WORKER_COUNT):
        worker_thread = threading.Thread(target=worker,
                                         args=(client_locks, host_locks,
                                               queue_new, queue_pending),
                                         kwargs={'bail': bail}) 
        worker_thread.start()
        worker_pool.append(worker_thread)
        
    bail_thread = threading.Thread(target=bailer, args=(bail, queue_new, queue_pending))
    bail_thread.start()
    
    pending_manager_thread = threading.Thread(target=pending_manager,
                                              args=(queue_pending,),
                                              kwargs={'bail': bail})
    pending_manager_thread.start()

    accepted_manager_thread = threading.Thread(target=accepted_manager,
                                               args=(queue_accepted,),
                                               kwargs={'bail': bail})
    accepted_manager_thread.start()

    client = get_redis_client()

    try:
        while True:
            item = client.blpop(('pingback.new', 'pingback.accepted'), 30)
            if item is None:
                continue
            key_name, ping_hash = item
            data = client.get('pingback.data:%s' % ping_hash)
            try:
                data = pickle.loads(base64.b64decode(data))
            except Exception, e:
                logger.exception('Failed to decode pingback data.\n')
                continue

            if key_name == 'pingback.new':
                queue_new.put(data)
            elif key_name == 'pingback.accepted':
                queue_accepted.put(data)
    except:
        bail.set()
        raise
    #finally:
    #    client.close()


if __name__ == '__main__':
    run()