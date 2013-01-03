import lxml.etree

from django.utils.safestring import mark_safe

_xslt = """\
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:template match="/">
    <html>
      <xsl:apply-templates select="*"/>
    </html>
  </xsl:template>

  <xsl:template match="html|body|noscript|font">
    <xsl:apply-templates select="*|text()"/>
  </xsl:template>

  <xsl:template match="ul|li|em|strong|u|b|div|span|ol|i|dl|dt|dd|table|tbody|
                       thead|tfoot|tr|td|th|p|a|h1|h2|h3|h4|h5|h6|pre|address|
                       blockquote|del|ins|abbr|dfn|code|samp|kbd|var|small|s|
                       big|tt|span|bdo|cite|q|sub|sup|wbr|colgroup|col|
                       caption">
    <xsl:copy>
      <xsl:if test="@href">
        <xsl:attribute name="rel">
          <xsl:if test="string-length(@rel)">
            <xsl:value-of select="@rel"/>
            <xsl:text> </xsl:text>
          </xsl:if>
          <xsl:text>nofollow</xsl:text>
        </xsl:attribute>
      </xsl:if>

      <xsl:apply-templates select="@*|node()"/>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="br|hr|img">
    <xsl:copy>
      <xsl:apply-templates select="@*"/>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="iframe|applet|script|style|title|object|param"/>

  <xsl:template match="*">
    <span>
      <xsl:apply-templates match="@*|node()"/>
    </span>
  </xsl:template>

  <xsl:template match="@src|@href|@alt|@title|@longdesc">
    <xsl:copy/>
  </xsl:template>

  <xsl:template match="@*"/>

  <xsl:template match="text()">
    <xsl:copy/>
  </xsl:template>
</xsl:stylesheet>
"""

class HTMLSanitizer(object):
    """
    Removes tags and attributes not on a whitelist, and adds rel="nofollow" to links.

    Usage: ``HTMLSanitizer.sanitize_html(data)``
    """

    _xslt = lxml.etree.XSLT(lxml.etree.XML(_xslt))

    # These are overridden by XHTMLSanitizer to provide XHTML support
    NS_PREFIX = ''
    parser_class = lxml.etree.HTMLParser

    def __init__(self):
        raise NotImplementedError("This class cannot be instantiated.")

    @classmethod
    def sanitize(cls, data):
        parser = cls.parser_class()

        if isinstance(data, basestring):
            data = lxml.etree.fromstring(data, parser=parser)
        elif hasattr(data, 'read'):
            data = lxml.etree.parse(data, parser=parser)

        for elem in data.xpath('/descendant-or-self::*'):
            if elem.tag.startswith(cls.NS_PREFIX):
                elem.tag = elem.tag[len(cls.NS_PREFIX):]

        data = cls._xslt(data).find('*')
        return mark_safe(lxml.etree.tostring(data, method='html'))

class XHTMLSanitizer(HTMLSanitizer):
    NS_PREFIX = '{http://www.w3.org/1999/xhtml}'
    parser_class = lxml.etree.XMLParser

def sanitize_html(data, is_xhtml=False):
    return (XHTMLSanitizer if is_xhtml else HTMLSanitizer).sanitize(data)
