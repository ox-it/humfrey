from __future__ import with_statement

import os

import rdflib

from humfrey.update.transform.base import Transform

class Union(Transform):
    def __init__(self, *others):
        self.others = others

    def execute(self, transform_manager, input=None):
        inputs = [input] if input else []
        inputs += [other(transform_manager) for other in self.others]
        
        transform_manager.start(self, inputs)
        
        graph = rdflib.ConjunctiveGraph()
        for filename in inputs:
            graph.parse(filename,
                        format=self.rdf_formats[os.path.splitext(filename)[1:]])
        
        with transform_manager('nt') as output:
            graph.serialize(output, format='nt')
            
            return output.name
