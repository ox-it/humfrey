import datetime

class OxPointsQuery(object):
    def __init__(self, endpoint, types=(), date=None, scheme=None, identifier=None, relation=None, uri=None, about=None):
        self.endpoint = endpoint
        self.quote = endpoint.quote

        if not date:
            date=datetime.date.today().strftime('%Y-%m-%d')
        cur = '?cur' if relation else '?uri'

        self.date, self.scheme, identifier, self.relation, self.cur = date, scheme, identifier, relation, cur

        self.types = list(map(self.quote, types))
        self.about = self.quote(about)

        self.params = {
            'date': self.date + 'T00:00:00',
            'cur': cur,
            'about': about
        }

    def get_describe(self):
        return 'DESCRIBE ?uri WHERE { GRAPH ?g { %s } }' + ' . '.join(self.get_clauses())
    def get_ask(self):
        return 'ASK WHERE { GRAPH ?g { %s } }' + ' . '.join(self.get_clauses())

    def get_clauses(self):
        clauses = []
        clauses += self.get_date_clauses()
        clauses += self.get_type_clauses()
        clauses += self.get_about_clauses()
        return clauses

    def get_date_clauses(self):
        return [
            "OPTIONAL { ?g time:hasBeginning [ time:inXSDDateTime ?beginning ] }",
            "OPTIONAL { ?g time:hasEnd [ time:inXSDDateTime ?end ] }",
            "FILTER ( !bound(?beginning) || ?beginning < '%(date)s'^^xsd:dateTime )" % self.params,
            "FILTER ( !bound(?end) || ?end >= '%(date)s'^^xsd:dateTime )" % self.params,
        ]

    def get_type_clauses(self):
        if not self.types:
            return []
        f = ' || '.join('?type a %s' % t for t in self.types)
        return [
            "%(cur)s a ?type" % self.params,
            "FILTER ( %s )" % f,
        ]

    def get_about_clauses(self):
        if not self.about:
            return []
        return [
            "FILTER ( %(cur)s = %(about)s )" % self.params,
        ]


    def perform(self):
        graph = rdflib.ConjunctiveGraph()
        query = "SELECT ?uri ?p ?o WHERE { GRAPH ?g { %s } }" % self.get_clauses()

        for s, p, o in self.endpoint.query(query):
            if isinstance(o, rdflib.BNode):
                graph += self.sub_perform(s, [p])
            else:
                graph.add((s, p, o))

        return graph

    def sub_perform(self, subject, path):
        return []

if __name__ == '__main__':
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from utils import sparql
    endpoint = sparql.Endpoint('http://localhost:3030/dataset/query')
    query = OxPointsQuery(endpoint)
    graph = query.perform()
    print(graph.serialize())

