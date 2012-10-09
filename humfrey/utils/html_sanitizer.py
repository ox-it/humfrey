import lxml.etree

from django.utils.safestring import mark_safe

class HTMLSanitizer(object):
    """
    Removes tags and attributes not on a whitelist, and adds rel="nofollow" to links.
    
    Usage: ``HTMLSanitizer.sanitize_html(data)``
    """
    
    
    # These are the only attributes we'll keep
    good_attribs = 'src href alt title rel'.split()
    
    # Here is our whitelist of good tags. Everything else is replaced with a div or span
    good_tags = 'ul li em strong u b div span ol i dl dt dd table tbody thead tfoot tr td th hr img p br a h1 h2 h3 h4 h5 h6'.split()
    
    # These and their content are removed completely
    remove_tags = 'iframe applet script'.split()
    
    # These are stripped, but their content preserved
    ignore_tags = 'html body'.split()
    
    # Here's the list of non-good tags that should be replaced with div elements
    block_tags = 'h1 h2 h3 h4 h5 h6'.split()
    
    # These are overridden by XHTMLSanitizer to provide XHTML support
    NS_PREFIX = ''
    parser_class = lxml.etree.HTMLParser
    
    def __init__(self):
        raise NotImplementedError("This class cannot be instantiated.")
    
    @classmethod
    def _process_children(cls, elem, children=None):
        for child in (children or elem):
            new_child = cls._sanitize(child)
            if new_child is None:
                if child.tail:
                    if child.getnext() is not None:
                        child.getnext().text = child.tail + (child.getnext().text or '')
                    elif child.getprevious() is not None:
                        child.getprevious().tail = (child.getprevious().tail or '') + child.tail
                    else:
                        elem.text = (elem.text or '') + child.tail
                elem.remove(child)
            elif isinstance(new_child, list):
                if child.text:
                    if child.getprevious() is not None:
                        child.getprevious().tail = (child.getprevious().tail or '') + child.text
                    else:
                        elem.text = (elem.text or '') + child.text
                if child.tail:
                    if child.getnext() is not None:
                        child.getnext().text = child.tail + (child.getnext().text or '')
                    elif child.getprevious() is not None:
                        child.getprevious().tail = (child.getprevious().tail or '') + child.tail
                    else:
                        elem.text = (elem.text or '') + child.tail
                for c in new_child:
                    child.addnext(c)
                elem.remove(c)
                cls._process_children(elem, new_child)
            elif new_child is not child:
                elem.replace(child, new_child)
                cls._process_children(elem, [new_child])

    @classmethod
    def _sanitize(cls, elem):
        for key in list(elem.attrib):
            if key not in cls.good_attribs:
                del elem.attrib[key]
            if key == 'href':
                elem.attrib['rel'] = ' '.join(elem.attrib.get('rel', '').split() + ['nofollow'])
        if elem.tag.startswith(cls.NS_PREFIX):
            elem.tag = elem.tag[len(cls.NS_PREFIX):]
        if elem.tag in cls.remove_tags:
            return
        if elem.tag in cls.ignore_tags:
            return elem.getchildren()
        
        if elem.tag not in cls.good_tags:
            elem.tag = 'div' if elem.tag in cls.block_tags else 'span'

        cls._process_children(elem)
        return elem
    
    @classmethod
    def sanitize(cls, data):
        parser = cls.parser_class()

        if isinstance(data, basestring):
            data = lxml.etree.fromstring(data, parser=parser)
        elif hasattr(data, 'read'):
            data = lxml.etree.parse(data, parser=parser)

        data = cls._sanitize(data)
        while isinstance(data, list):
            data = cls._sanitize(data[0])

        return mark_safe(lxml.etree.tostring(data, method='html'))

class XHTMLSanitizer(object):
    NS_PREFIX = '{http://www.w3.org/1999/xhtml}'
    parser_class = lxml.etree.XMLParser

def sanitize_html(data, is_xhtml=False):
    return (XHTMLSanitizer if is_xhtml else HTMLSanitizer).sanitize(data)
