#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from lxml import etree
from html5lib.constants import cdataElements, rcdataElements

from calibre.ebooks.oeb.polish.tests.base import BaseTest
from calibre.ebooks.oeb.base import XPath, XHTML_NS, SVG_NS, XLINK_NS
from calibre.ebooks.oeb.parse_utils import html5_parse

def nonvoid_cdata_elements(test, parse_function):
    ''' If self closed version of non-void cdata elements like <title/> are
    present, the HTML5 parsing algorithm treats all following data as CDATA '''
    markup = '''
    <html> <head><{0}/></head> <body id="test"> </html>
    '''
    for tag in cdataElements | rcdataElements:
        for x in (tag, tag.upper(), '\n' + tag, tag + ' id="xxx" '):
            root = parse_function(markup.format(x))
            test.assertEqual(
                len(XPath('//h:body[@id="test"]')(root)), 1,
                'Incorrect parsing for <%s/>, parsed markup:\n' % x + etree.tostring(root))

def namespaces(test, parse_function):
    ae = test.assertEqual
    markup = ''' <html xmlns="{xhtml}"><head><body id="test"></html> '''.format(xhtml=XHTML_NS)
    root = parse_function(markup)
    ae(
        len(XPath('//h:body[@id="test"]')(root)), 1,
        'Incorrect parsing, parsed markup:\n' + etree.tostring(root))

    markup = '''
    <html xmlns="{xhtml}"><head><body id="test">
    <svg:svg xmlns:svg="{svg}"><svg:image xmlns:xlink="{xlink}" xlink:href="xxx"/></svg:svg>
    '''.format(xhtml=XHTML_NS, svg=SVG_NS, xlink=XLINK_NS)
    root = parse_function(markup)
    err = 'Incorrect parsing, parsed markup:\n' + etree.tostring(root)
    ae(len(XPath('//h:body[@id="test"]')(root)), 1, err)
    ae(len(XPath('//svg:svg')(root)), 1, err)
    ae(len(XPath('//svg:image[@xl:href]')(root)), 1, err)

    markup = '''
    <html xmlns="{xhtml}"><head><body id="test">
    <svg xmlns="{svg}" xmlns:xlink="{xlink}" ><image xlink:href="xxx"/></svg>
    '''.format(xhtml=XHTML_NS, svg=SVG_NS, xlink=XLINK_NS)
    root = parse_function(markup)
    err = 'Incorrect parsing, parsed markup:\n' + etree.tostring(root)
    ae(len(XPath('//h:body[@id="test"]')(root)), 1, err)
    ae(len(XPath('//svg:svg')(root)), 1, err)
    ae(len(XPath('//svg:image[@xl:href]')(root)), 1, err)

    markup = '<html><body><svg><image xlink:href="xxx"></svg>'
    root = parse_function(markup)
    err = 'Namespaces not created, parsed markup:\n' + etree.tostring(root)
    ae(len(XPath('//svg:svg')(root)), 1, err)
    ae(len(XPath('//svg:image[@xl:href]')(root)), 1, err)

    markup = '<html><body><ns1:tag1 xmlns:ns1="NS"><ns2:tag2 xmlns:ns2="NS" ns1:id="test"/><ns1:tag3 xmlns:ns1="NS2" ns1:id="test"/></ns1:tag1>'
    root = parse_function(markup)
    err = 'Arbitrary namespaces not preserved, parsed markup:\n' + etree.tostring(root)
    def xpath(expr):
        return etree.XPath(expr, namespaces={'ns1':'NS', 'ns2':'NS2'})(root)
    ae(len(xpath('//ns1:tag1')), 1, err)
    ae(len(xpath('//ns1:tag2')), 1, err)
    ae(len(xpath('//ns2:tag3')), 1, err)
    ae(len(xpath('//ns1:tag2[@ns1:id="test"]')), 1, err)
    ae(len(xpath('//ns2:tag3[@ns2:id="test"]')), 1, err)

all_checks = (nonvoid_cdata_elements, namespaces)

class ParsingTests(BaseTest):

    def test_conversion_parser(self):
        ' Test parsing with the parser used for conversion '
        for test in all_checks:
            test(self, html5_parse)
