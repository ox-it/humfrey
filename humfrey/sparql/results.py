import types
import weakref

import rdflib

class SparqlResultBinding(dict):
    def __init__(self, bindings):
        if isinstance(bindings, (list, tuple, types.GeneratorType)):
            bindings = dict(zip(self._fields, bindings))
        for field in self._fields:
            if field not in bindings:
                bindings[field] = None
        super(SparqlResultBinding, self).__init__(bindings)
    def __iter__(self):
        return (self[field] for field in self._fields)
    def __getattr__(self, name):
        return self[name]
    @property
    def fields(self):
        return self._fields
    def __reduce__(self):
        return (Result, (self._fields, self._asdict()))
    def _asdict(self):
        return dict(self)

def Result(fields, bindings=None):
    fields = tuple(fields)
    if fields in Result._memo:
        cls = Result._memo[fields]
    else:
        class cls(SparqlResultBinding):
            _fields = fields
        Result._memo[fields] = cls
    if bindings is not None:
        return cls(bindings)
    else:
        return cls
Result._memo = weakref.WeakValueDictionary()

class SparqlResultList(list):
    """
    A SPARQL resultset that has been turned into a list.
    """
    def __init__(self, fields, arg=None):
        self.fields = fields
        if arg is not None:
            list.__init__(self, arg)

    def get_bindings(self):
        return self

    def get_fields(self):
        return self.fields
