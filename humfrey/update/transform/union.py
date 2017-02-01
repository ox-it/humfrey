import itertools
import os

import rdflib

from humfrey.update.transform.base import Transform
from humfrey.streaming import parse, serialize

class Union(Transform):
    def __init__(self, *others):
        self.others = others

    def execute(self, transform_manager, input=None):
        inputs = [input] if input else []
        inputs += [other(transform_manager) for other in self.others]

        transform_manager.start(self, inputs)

        inputs = [parse(open(fn)) for fn in inputs]
        triples = itertools.chain(*inputs)

        with transform_manager('nt') as output:
            serialize(triples, output)
            return output.name
