import functools
import unittest

from humfrey.utils.html_sanitizer import HTMLSanitizer, XHTMLSanitizer

class HTMLSanitizerTestCaseMeta(type):
    def __new__(cls, name, bases, attrs):
        def wrapper(f):
            def g(*args, **kwargs):
                return f(*args, **kwargs)
            return g
        test_case_method = attrs.pop('test_case_method')
        test_cases = attrs.pop('test_cases')
        for key in test_cases:
            original, expected = test_cases[key]
            f = wrapper(functools.partial(test_case_method, original=original, expected=expected))
            f.__name__ = 'test_' + key
            attrs[f.__name__] = f
        return super(HTMLSanitizerTestCaseMeta, cls).__new__(cls, name, bases, attrs)

class HTMLSanitizerTestCase(unittest.TestCase):
    __metaclass__ = HTMLSanitizerTestCaseMeta
    test_cases = {'bad_attribute': ("""<div badattr="foo">bar</div>""",
                                    """<div>bar</div>"""),
                  'strip_html_body': ("""<html><body><h1>Hello</h1></body></html>""",
                                      """<h1>Hello</h1>"""),
                  'remove_applet': ("""<div>Foo<applet>Bar</applet>Baz</div>""",
                                    """<div>FooBaz</div>"""),
                  'remove_applet_previous': ("""<div>Foo<em>Bar</em>Baz<applet>Qux</applet>Quux</div>""",
                                             """<div>Foo<em>Bar</em>BazQuux</div>"""),
                  'remove_empty': ("""<div>Foo<font></font>Bar</div>""",
                                   """<div>FooBar</div>"""),
                  'add_rel': ("""<a href="foo">bar</a>""",
                              """<a rel="nofollow" href="foo">bar</a>"""),
                  'add_rel_append': ("""<a rel="baz" href="foo">bar</a>""",
                                     """<a rel="baz nofollow" href="foo">bar</a>"""),
                  'sharepoint': ("""<div xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns="http://www.w3.org/1999/xhtml">
               <xhtml:p>
                  <xhtml:span id="ms-rterangepaste-start">
                     <xhtml:div>
                        <xhtml:font size="1">
                           <xhtml:font size="1"/>
                        </xhtml:font>
                        <xhtml:font size="1">
                           <xhtml:font size="1">
                              <xhtml:font size="1">
                                 <xhtml:span id="ms-rterangepaste-start"/>
                                 <xhtml:div>Foo</xhtml:div>
                                 <xhtml:div>Bar<xhtml:br/>
                                 </xhtml:div>
                              </xhtml:font>
                           </xhtml:font>
                        </xhtml:font>
                     </xhtml:div>
                     <xhtml:ul>
                        <xhtml:span id="ms-rterangepaste-end"/>
                        <xhtml:font size="1"/>
                     </xhtml:ul>
                     <xhtml:span id="ms-rterangepaste-end">
                        <xhtml:p/>
                     </xhtml:span>
                  </xhtml:span>
               </xhtml:p>
               <xhtml:p>Intended Audience: Humanities DPhils</xhtml:p>
            </div>""", """<div>
               <p>
                  <span>
                     <div>
                        
                           
                        
                        
                           
                              
                                 <span></span>
                                 <div>Foo</div>
                                 <div>Bar<br>
                                 </div>
                              
                           
                        
                     </div>
                     <ul>
                        <span></span>
                        
                     </ul>
                     <span>
                        <p></p>
                     </span>
                  </span>
               </p>
               <p>Intended Audience: Humanities DPhils</p>
            </div>"""),
                  }

    def test_case_method(self, original, expected):
        self.assertEqual(HTMLSanitizer.sanitize(original),
                         expected)