from __future__ import with_statement

import gzip
import itertools
from xml.sax.saxutils import XMLGenerator
import zipfile

from lxml import etree

from humfrey.update.transform.base import Transform

class SpreadsheetToTEI(Transform):
    class Sheet(object): pass
    class Row(object): pass

    def execute(self, transform_manager, input):
        with open(transform_manager('xml'), 'w') as output:
            transform_manager.start(self, [input])
            generator = XMLGenerator(output, encoding='utf-8')
            generator.startDocument()
            generator.startElement('TEI', {'xmlns':'http://www.tei-c.org/ns/1.0'})
            generator.startElement('text', {})
            generator.startElement('body', {})

            for sheet in self.sheets(input):
                generator.startElement('table', {})
                generator.startElement('head', {})
                generator.characters(sheet.name)
                generator.endElement('head')

                for i, row in enumerate(sheet.rows):
                    generator.startElement('row', {'n': unicode(int(i) + 1)})
                    for j, cell in enumerate(row.cells):
                        generator.startElement('cell', {'n': unicode(j + 1)})
                        generator.characters(cell)
                        generator.endElement('cell')
                    generator.endElement('row')
                generator.endElement('table')

            generator.endElement('body')
            generator.endElement('text')
            generator.endElement('TEI')

            transform_manager.end([output.name])
            return output.name

class GnumericToTEI(SpreadsheetToTEI):
    NS = {'gnm': 'http://www.gnumeric.org/v10.dtd'}

    class Sheet(SpreadsheetToTEI.Sheet):
        def __init__(self, elem):
            self.elem = elem
        @property
        def name(self):
            return self.elem.xpath('gnm:Name', namespaces=GnumericToTEI.NS)[0].text
        @property
        def rows(self):
            return itertools.imap(GnumericToTEI.Row, itertools.groupby(self.elem.xpath('gnm:Cells/gnm:Cell', namespaces=GnumericToTEI.NS), lambda cell:cell.attrib['Row']))

    class Row(SpreadsheetToTEI.Row):
        def __init__(self, group):
            self.group = group
        @property
        def cells(self):
            return ((cell.text or '') for cell in self.group[1])

    def sheets(self, input):
        input = etree.parse(gzip.GzipFile(input, mode='r'))
        return itertools.imap(self.Sheet, input.xpath('gnm:Sheets/gnm:Sheet', namespaces=self.NS))

class ODSToTEI(SpreadsheetToTEI):
    NS = {
        'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
        'style': 'urn:oasis:names:tc:opendocument:xmlns:style:1.0',
        'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
        'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
    }
        #'draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" xmlns:number="urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0" xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" xmlns:chart="urn:oasis:names:tc:opendocument:xmlns:chart:1.0" xmlns:dr3d="urn:oasis:names:tc:opendocument:xmlns:dr3d:1.0" xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0" xmlns:math="http://www.w3.org/1998/Math/MathML" xmlns:form="urn:oasis:names:tc:opendocument:xmlns:form:1.0" xmlns:script="urn:oasis:names:tc:opendocument:xmlns:script:1.0" xmlns:ooo="http://openoffice.org/2004/office" xmlns:ooow="http://openoffice.org/2004/writer" xmlns:oooc="http://openoffice.org/2004/calc" xmlns:of="urn:oasis:names:tc:opendocument:xmlns:of:1.2" xmlns:dom="http://www.w3.org/2001/xml-events" xmlns:xforms="http://www.w3.org/2002/xforms" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:gnm="http://www.gnumeric.org/odf-extension/1.0" office:version="1.1">

    class Sheet(SpreadsheetToTEI.Sheet):
        def __init__(self, elem):
            self.elem = elem
        @property
        def name(self):
            return self.elem.xpath('@table:name', namespaces=ODSToTEI.NS)[0]
        @property
        def rows(self):
            return itertools.imap(ODSToTEI.Row, self.elem.xpath('table:table-row[table:table-cell/@office:value-type]', namespaces=ODSToTEI.NS))

    class Row(SpreadsheetToTEI.Row):
        def __init__(self, elem):
            self.elem = elem
        @property
        def cells(self):
            cells = self.elem.xpath('table:table-cell[@office:value-type]', namespaces=ODSToTEI.NS)
            for cell in cells:
                value_type = cell.xpath('@office:value-type', namespaces=ODSToTEI.NS)[0]
                print etree.tostring(cell)
                value = cell.xpath('@office:%s-value' % value_type, namespaces=ODSToTEI.NS) \
                     or cell.xpath('@office:value', namespaces=ODSToTEI.NS) \
                     or cell.xpath('text:p/text()', namespaces=ODSToTEI.NS)
                print value
                try:
                    repeated = int(cell.xpath('@table:number-columns-repeated', namespaces=ODSToTEI.NS)[0])
                except (ValueError, IndexError):
                    repeated = 1
                for n in xrange(repeated):
                    yield value[0]

    def sheets(self, input):
        zip = zipfile.ZipFile(input)
        try:
            input = etree.fromstring(zip.read('content.xml'))
            return itertools.imap(self.Sheet, input.xpath('office:body/office:spreadsheet/table:table', namespaces=self.NS))
        finally:
            zip.close()
