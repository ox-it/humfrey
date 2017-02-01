from collections import defaultdict, namedtuple
from urllib.parse import urlparse
import datetime, time
import rdflib
import sparql

class OxPointsQuery(object):
    def __init__(self, endpoint, graph_meta, types=(), date=None, scheme=None, identifier=None, relation=None, uri=None, about=None):
        self.endpoint = endpoint
        self.quote = endpoint.quote
        self._graph_meta = graph_meta

        if not date:
            date=datetime.date.today().strftime('%Y-%m-%d')
        cur = '?cur' if relation else '?uri'

        self.date, self.scheme, identifier, self.relation, self.cur = date, scheme, identifier, relation, cur

        self.types = list(map(self.quote, types))
        self.about = about

        self.params = {
            'date': self.date + 'T00:00:00',
            'cur': cur,
            'about': self.about,
        }
        
    def describe(self, with_fragments=False):
        query = 'DESCRIBE ?uri %s WHERE { %s }' % (' '.join('FROM '+g.n3() for g in self.get_graphs()), ' . '.join(self.get_clauses()))
        graph = self.endpoint.query(query)
        if with_fragments:
            query = 'DESCRIBE ?uri %s WHERE { %s }' % (' '.join('FROM '+g.n3() for g in self.get_graphs()), ' . '.join(self.get_clauses(True)))
            graph += self.endpoint.query(query)
        return graph

    def get_ask(self):
        return 'ASK %s WHERE { %s }' % (' '.join('FROM '+g.n3() for g in self.get_graphs()), ' . '.join(self.get_clauses()))

    def get_graphs(self):
        if not self.date:
            return self._graph_meta.current_graphs()
        else:
            return self._graph_meta.graphs_for_date(self.date)

    def get_clauses(self, fragments=False):
        clauses = [
            '?uri a ?t' % self.params,
            'FILTER isIRI(?uri)'
        ]
        clauses += self.get_type_clauses()
        clauses += self.get_about_clauses(fragments)
        return clauses

        

    def get_type_clauses(self):
        if not self.types:
            return []
        f = ' || '.join('?type a %s' % t for t in self.types)
        return [
            "%(cur)s a ?type" % self.params,
            "FILTER ( %s )" % f,
        ]

    def get_about_clauses(self, fragments=False):
        if not self.about:
            return []
        if fragments:
            return ["FILTER fn:starts-with(?uri, %s)" % self.endpoint.quote(str(self.about)+'#')]
        else:
            return ["FILTER ( %s = %s )" % (self.cur, self.about.n3())]
        

    @classmethod
    def from_request(cls, endpoint, graph_meta, request, uri=None):
        when = request.GET.get('date')
        if request.path.startswith('/doc/'):
            if not uri:
                uri = urlparse(request.build_absolute_uri())
                uri = '%s://%s/id/%s' % (uri.scheme, uri.netloc, uri.path[5:])
            return cls(endpoint, graph_meta, about=rdflib.URIRef(uri), date=when)
        elif request.path == '/all':
            return cls(endpoint, graph_meta, date=when)

class GraphMeta(object):
    _graph_meta_query = """\
        SELECT DISTINCT ?name ?beginning ?end ?license WHERE {
          GRAPH ?name {
            ?s ?p ?o .
            OPTIONAL { ?name time:hasBeginning [ time:inXSDDateTime ?beginning ] } .
            OPTIONAL { ?name time:hasEnd [ time:inXSDDateTime ?end ] } .
            OPTIONAL { ?name dcterms:license ?license }
          }
        }"""

    def __init__(self, endpoint):
        self._endpoint = endpoint
        self._graphs = None
        self._updated = 0

    def _update_graph_meta(self):
        self._graphs = self._endpoint.query(self._graph_meta_query)
        self._updated = time.time()

    def graphs_for_date(self, when):
        if self._updated + 60 < time.time():
            self._update_graph_meta()
        return [g.name for g in self._graphs if (not g.beginning or g.beginning <= when) and (not g.end or g.end > when)]
    def current_graphs(self):
        return graphs_for_date(datetime.now().strptime('%Y-%m-%d'))

