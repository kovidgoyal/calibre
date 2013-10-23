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

    markup = '<html xml:lang="en"><body><p lang="de"><p xml:lang="es"><p lang="en" xml:lang="de">'
    root = parse_function(markup)
    err = 'xml:lang not converted to lang, parsed markup:\n' + etree.tostring(root)
    ae(len(root.xpath('//*[@lang="en"]')), 2, err)
    ae(len(root.xpath('//*[@lang="de"]')), 1, err)
    ae(len(root.xpath('//*[@lang="es"]')), 1, err)
    ae(len(XPath('//*[@xml:lang]')(root)), 0, err)

def space_characters(test, parse_function):
    markup = '<html><p>\u000c</p>'
    root = parse_function(markup)
    err = 'form feed character not converted, parsed markup:\n' + etree.tostring(root)
    test.assertNotIn('\u000c', root.xpath('//*[local-name()="p"]')[0].text, err)

def case_insensitive_element_names(test, parse_function):
    markup = '<HTML><P> </p>'
    root = parse_function(markup)
    err = 'case sensitive parsing, parsed markup:\n' + etree.tostring(root)
    test.assertEqual(len(XPath('//h:p')(root)), 1, err)

basic_checks = (nonvoid_cdata_elements, namespaces, space_characters, case_insensitive_element_names)

class ParsingTests(BaseTest):

    def test_conversion_parser(self):
        ' Test parsing with the HTML5 parser used for conversion '
        for test in basic_checks:
            test(self, html5_parse)
