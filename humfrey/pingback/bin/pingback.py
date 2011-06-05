import pickle, base64, urllib, urllib2, sys, threading, logging, time, rdflib, urlparse, socket
from collections import defaultdict
from functools import wraps

from django.conf import settings

import redis
from lxml import etree

WORKER_COUNT = 8

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger('pingback')

RDF_MEDIA_TYPES = {
    'application/rdf+xml': 'xml',
    'text/n3': 'n3',
    'text/turtle': 'n3',
}

TARGET_DOMAINS = frozenset(['data.ox.ac.uk', 'oxpoints.oucs.ox.ac.uk'])

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


def set_data(client, ping_hash, data):
    client.set('pingback.data:%s' % ping_hash, base64.b64encode(pickle.dumps(data)))
def get_data(client, ping_hash):
    return pickle.loads(base64.b64decode(client.get('pingback.data:%s' % ping_hash)))
def set_expiry(client, ping_hash):
    client.expire('pingback.data:%s' % ping_hash, 3600 * 24 * 7)

def redis_queue(client, key, bail):
    while not bail.is_set():
        item = client.blpop(key, 30)
        if item is None:
            continue
        key_name, ping_hash = item
        data = get_data(client, ping_hash)
        
        yield key_name, ping_hash, data

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



def process(client, data):
    source, target = (rdflib.URIRef(data[x]) for x in ('source', 'target'))

    request = urllib2.Request(source)
    request.headers['Accept'] = 'application/rdf+xml, text/n3, text/turtle, application/xhtml+xml;q=0.9; text/html;q=0.8'

    try:
        response = urllib2.urlopen(request)
    except (ValueError, urllib2.URLError), e:
        logger.exception('Problem with URL for %r' % data['source'])
        data['state'] = 'invalid'
        return
    except urllib2.HTTPError, e:
        logger.exception('Could not retrieve source: %r' % data['source'])
        data['state'] = 'invalid'
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
        data['state'] = 'invalid'
        return

    if not graph:
        data['state'] = 'invalid'
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
    
    if client.sismember('pingback.whitelist.ip', data['remote_addr']) or \
       client.sismember('pingback.whitelist.hostname', data['hostname']) or \
       client.sismember('pingback.whitelist.source_domain', data['source_domain']):
        data['state'] = 'accepted'
    elif client.sismember('pingback.blacklist.ip', data['remote_addr']) or \
         client.sismember('pingback.blacklist.hostname', data['hostname']) or \
         client.sismember('pingback.blacklist.source_domain', data['source_domain']):
        data['state'] = 'rejected'
    else:
        data['state'] = 'pending'

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
def worker(client_locks, host_locks, bail):
    client = get_redis_client()
    
    for _, ping_hash, data in redis_queue(client, 'pingback.new', bail):
        
        source_url = urlparse.urlparse(data['source'])
        source_domain = source_url.netloc.split(':')[0].lower()
        
        target_url = urlparse.urlparse(data['target'])
        target_domain = source_url.netloc.split(':')[0].lower()
        
        data['source_domain'] = source_domain
        data['target_domain'] = target_domain
        
        if target_domain not in TARGET_DOMAINS:
            logging.warning('Pingback for non-targetable host: %r' % data['target'])
            continue
        if source_url.scheme not in ('http', 'https', 'ftp'):
            logging.warning('Unsupported scheme for pingback')
            continue
            
        
        client_lock = client_locks[data['remote_addr']]
        host_lock = host_locks[source_domain]
        
        with client_lock, host_lock:
            print id(data)
            process(client, data)
            set_data(client, ping_hash, data)
            print id(data)
            logging.info('Data with state %r' % data['state'])
            if data['state'] in ('invalid', 'rejected'):
                set_expiry(client, ping_hash)
            elif data['state'] == 'accepted':
                client.rpush('pingback.accepted', ping_hash)
            elif data['state'] == 'pending':
                client.sadd('pingback.pending', ping_hash)
            else:
                logging.error('Unexpected state')
                
            time.sleep(1)

@bailable
def accepted_manager(bail):
    client = get_redis_client()
    
    for _, ping_hash, data in redis_queue(client, 'pingback.accepted', bail):
        
        graph = data['graph']
        graph += data['graph_metadata']
        
        url = 'http://localhost:3030/dataset/data?%s' % urllib.urlencode({'graph': data['graph_name']})
        request = PutRequest(url, data=graph.serialize())
        request.headers['Content-type'] = 'application/rdf+xml'
        try:
            urllib2.urlopen(request)
        except urllib2.HTTPError, e:
            if e.code not in (201, 204,):
                raise
        
        data['state'] = 'published'
        set_data(client, ping_hash, data)
        set_expiry(client, ping_hash)

def interrupt_handler(bail):
    def f(signum, frame):
        logging.info("Bailing")
        bail.set()
    return f

def run():
    #signal.signal(signal.SIGINT, interrupt_handler)

    client_locks, host_locks = defaultdict(threading.Lock), defaultdict(threading.Lock)
    bail = threading.Event()
    
    worker_pool = []
    for i in range(WORKER_COUNT):
        worker_thread = threading.Thread(target=worker,
                                         args=(client_locks, host_locks),
                                         kwargs={'bail': bail})
        #worker_thread.daemon = True 
        worker_thread.start()
        worker_pool.append(worker_thread)
        
    accepted_manager_thread = threading.Thread(target=accepted_manager,
                                               kwargs={'bail': bail})
    #accepted_manager_thread.daemon = True 
    accepted_manager_thread.start()

    try:
        while True: time.sleep(100)
    except KeyboardInterrupt:
        bail.set()
    
    logging.info("Shutting down")


if __name__ == '__main__':
    run()
