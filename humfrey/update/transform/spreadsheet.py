from __future__ import with_statement

import datetime
import decimal
import gzip
import itertools
from xml.sax.saxutils import XMLGenerator
import zipfile

from lxml import etree

from humfrey.update.transform.base import Transform

class Currency(decimal.Decimal):
    def __new__(cls, value, currency, rendered):
        return decimal.Decimal.__new__(cls, value)
    def __init__(self, value, currency, rendered):
        super(Currency, self).__init__(value)
        self.currency, self.rendered = currency, rendered
    def __repr__(self):
        return "Currency(%r, %r, %r)" % (decimal.Decimal.__repr__(self), self.currency, self.rendered)

class Percentage(decimal.Decimal):
    def __new__(cls, value, rendered, dp=None):
        return decimal.Decimal.__new__(cls, value, dp)
    def __init__(self, value, rendered, dp=None):
        super(Percentage, self).__init__(value, dp)
        self.rendered = rendered
    def __repr__(self):
        return "Percentage(%r, %r)" % (decimal.Decimal.__str__(self), self.rendered)

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
                        generator.characters(unicode(cell))
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
            self.style_regions = self.elem.xpath('gnm:Styles/gnm:StyleRegion', namespaces=GnumericToTEI.NS)

        @property
        def name(self):
            return self.elem.xpath('gnm:Name', namespaces=GnumericToTEI.NS)[0].text
        @property
        def rows(self):
            i = 0
            for group, row in itertools.groupby(self.elem.xpath('gnm:Cells/gnm:Cell', namespaces=GnumericToTEI.NS), lambda cell:cell.attrib['Row']):
                while int(group) > i:
                    yield GnumericToTEI.Row([], self)
                    i += 1
                yield GnumericToTEI.Row(row, self)
                i += 1

        def find_style(self, row, col):
            row, col = int(row), int(col)
            for sr in self.style_regions:
                a = dict((k, int(v)) for k, v in sr.attrib.items())
                if a['startCol'] <= col <= a['endCol'] and a['startRow'] <= row <= a['endRow']:
                    return sr
            else:
                return None

        def parse(self, cell):
            sr = self.find_style(cell.attrib['Row'], cell.attrib['Col'])
            if cell.attrib['ValueType'] != '40': # '60' is string, '40' seems to be numeric
                return cell.text
            if sr is None:
                return cell.text
            format = sr.xpath('gnm:Style/@Format', namespaces=GnumericToTEI.NS)[0]
            if format.endswith('%'):
                dp = len(format) - 3 # "0.000%"; len 6, dp 3
                rendered = ('%%0.%df%%%%' % dp) % (float(cell.text) * 100)
                return Percentage(cell.text, rendered, dp)
            elif format in ('dd/mm/yyyy', 'm/d/yy', 'm/d/yyyy', 'yyyy-mm-dd', 'dd/mm/yy'):
                value = datetime.date(1899, 12, 31) + datetime.timedelta(int(cell.text))
                # Lotus incorrectly believes that 1900 was a leap year
                if value > datetime.date(1900, 2, 28):
                    value -= datetime.timedelta(1)
                return value
            elif 'yy' in format:
                day, fraction = int(float(cell.text)), (float(cell.text) % 1) * 24 * 3600
                value = datetime.datetime(1899, 12, 31) + datetime.timedelta(int(day), fraction)
                # Lotus incorrectly believes that 1900 was a leap year
                if value > datetime.datetime(1900, 2, 28):
                    value -= datetime.timedelta(1)
                return value
            else:
                return float(cell.text)


    class Row(SpreadsheetToTEI.Row):
        def __init__(self, row, sheet):
            self.row, self.sheet = row, sheet
        @property
        def cells(self):
            i = 0
            for cell in self.row:
                while int(cell.attrib['Col']) > i:
                    yield ''
                    i += 1
                yield self.sheet.parse(cell)
                i += 1

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
            for row in self.elem.xpath('table:table-row', namespaces=ODSToTEI.NS):
                try:
                    repeated = int(row.xpath('@table:number-rows-repeated', namespaces=ODSToTEI.NS)[0])
                except (ValueError, IndexError):
                    repeated = 1
                if row.xpath('((self::table:table-row | following-sibling::table:table-row)/table:table-cell/text:p)[1]', namespaces=ODSToTEI.NS):
                    for n in xrange(repeated):
                        yield ODSToTEI.Row(row)

    class Row(SpreadsheetToTEI.Row):
        def __init__(self, elem):
            self.elem = elem
        @property
        def cells(self):
            cells = self.elem.xpath('table:table-cell', namespaces=ODSToTEI.NS)
            for cell in cells:
                attrib = cell.attrib
                value_type = attrib.get('{%(office)s}value-type' % ODSToTEI.NS)
                if value_type == 'date':
                    value = attrib['{%(office)s}date-value' % ODSToTEI.NS]
                    if len(value) == 10:
                        value = datetime.date(*map(int, value.split('-')))
                    else:
                        value = datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')
                elif value_type == 'currency':
                    value = Currency(attrib['{%(office)s}value' % ODSToTEI.NS],
                                     attrib['{%(office)s}currency' % ODSToTEI.NS],
                                     cell.xpath('text:p/text()', namespaces=ODSToTEI.NS)[0])
                elif value_type == 'percentage':
                    value = Percentage(attrib['{%(office)s}value' % ODSToTEI.NS],
                                     cell.xpath('text:p/text()', namespaces=ODSToTEI.NS)[0])
                elif value_type == 'float':
                    value = float(attrib['{%(office)s}value' % ODSToTEI.NS])
                    if value == int(value):
                        value = int(value)
                elif value_type == 'string':
                    value = cell.xpath('text:p/text()', namespaces=ODSToTEI.NS)[0]
                else:
                    value = ''
                try:
                    repeated = int(cell.xpath('@table:number-columns-repeated', namespaces=ODSToTEI.NS)[0])
                except (ValueError, IndexError):
                    repeated = 1
                if value or cell.xpath('following-sibling::table:table-cell/text:p', namespaces=ODSToTEI.NS):
                    for n in xrange(repeated):
                        yield value

    def sheets(self, input):
        zip = zipfile.ZipFile(input)
        try:
            input = etree.fromstring(zip.read('content.xml'))
            return itertools.imap(self.Sheet, input.xpath('office:body/office:spreadsheet/table:table', namespaces=self.NS))
        finally:
            zip.close()
