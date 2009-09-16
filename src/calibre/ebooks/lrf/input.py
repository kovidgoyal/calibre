#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from copy import deepcopy

from lxml import etree

from calibre.customize.conversion import InputFormatPlugin
from calibre import guess_type

class MediaType(etree.XSLTExtension):
    def execute(self, context, self_node, input_node, output_parent):
        name = input_node.get('file', None)
        typ = guess_type(name)[0]
        if not typ:
            typ = 'application/octet-stream'
        output_parent.text = typ

class Metadata(etree.XSLTExtension):

    def __init__(self):
        from calibre.ebooks.oeb.base import DC, OPF, DC11_NS, OPF2_NS
        self.namespaces = {'dc':DC11_NS, 'opf':OPF2_NS}
        self.DC, self.OPF = DC, OPF
        print self.namespaces

    def execute(self, context, self_node, input_node, output_parent):
        input_node = deepcopy(input_node)
        titles = input_node.xpath('//Info//Title')
        if titles:
            tn = etree.Element(self.DC('title'), nsmap=self.namespaces)
            tn.text = titles[-1].text
            tn.set(self.OPF('file-as'), 'boo')
            output_parent.append(tn)


class LRFInput(InputFormatPlugin):

    name        = 'LRF Input'
    author      = 'Kovid Goyal'
    description = 'Convert LRF files to HTML'
    file_types  = set(['lrf'])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        self.log = log
        self.log('Generating XML')
        from calibre.ebooks.lrf.lrfparser import LRFDocument
        d = LRFDocument(stream)
        d.parse()
        xml = d.to_xml(write_files=True)
        parser = etree.XMLParser(recover=True, no_network=True)
        doc = etree.fromstring(xml, parser=parser)
        self.log('Converting XML to HTML...')
        styledoc = etree.fromstring(P('templates/lrf.xsl', data=True))
        media_type, metadata = MediaType(), Metadata()
        extensions = { ('calibre', 'media-type') : media_type,
                ('calibre', 'metadata'): metadata}
        transform = etree.XSLT(styledoc, extensions=extensions)
        result = transform(doc)
        with open('content.opf', 'wb') as f:
            f.write(result)

        return os.path.abspath('content.opf')


