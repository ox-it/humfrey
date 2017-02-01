# Some characters aren't allowed in N-Triples files, or SPARQL queries.
# See http://answers.semanticweb.com/questions/8244/ for specifics.
#
# We'll percent encode all characters that aren't allowed in IRIs:
#
# [^<>"{}|^`\]-[#x00-#x20]

import re

from rdflib import URIRef

def encode(char):
    return '%%%02X' % ord(char.group(0))

characters_needing_encoding = re.compile(r'[\^<>"{}|`\\\x00-\x20]', re.M)
subn_characters = characters_needing_encoding.subn

def coerce_triple_iris(triples):
    """
    Replaces forbidden characters with their percent-encoded equivalents
    """
    # This is a bit verbose in order to be speedy. We use subn so we only
    # construct a new URIRef iff characters were actually replaced.
    for s, p, o in triples:
        if isinstance(s, URIRef):
            new, n = subn_characters(encode, s)
            if n > 0:
                s = URIRef(new)
        if isinstance(p, URIRef):
            new, n = subn_characters(encode, p)
            if n > 0:
                p = URIRef(new)
        if isinstance(o, URIRef):
            new, n = subn_characters(encode, o)
            if n > 0:
                o = URIRef(new)
        yield s, p, o
