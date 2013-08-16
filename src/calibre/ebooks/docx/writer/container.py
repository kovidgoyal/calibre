#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import textwrap

from lxml.builder import ElementMaker

from calibre import guess_type
from calibre.constants import numeric_version, __appname__
from calibre.ebooks.docx.names import namespaces
from calibre.ebooks.oeb.base import xml2str
from calibre.utils.zipfile import ZipFile

class DOCX(object):

    def __init__(self):
        pass

    # Boilerplate {{{
    @property
    def contenttypes(self):
        E = ElementMaker(namespace=namespaces['ct'], nsmap={None:namespaces['ct']})
        types = E.Types()
        for partname, mt in {
            "/word/footnotes.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml",
            "/word/document.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
            "/word/numbering.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml",
            "/word/styles.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml",
            "/word/endnotes.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml",
            "/word/settings.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml",
            "/word/theme/theme1.xml": "application/vnd.openxmlformats-officedocument.theme+xml",
            "/word/fontTable.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml",
            "/word/webSettings.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.webSettings+xml",
            "/docProps/core.xml": "application/vnd.openxmlformats-package.core-properties+xml",
            "/docProps/app.xml": "application/vnd.openxmlformats-officedocument.extended-properties+xml",
        }.iteritems():
            types.append(E.Override(PartName=partname, ContentType=mt))
        added = {'png', 'gif', 'jpeg', 'jpg', 'svg', 'xml'}
        for ext in added:
            types.append(E.Default(Extension=ext, ContentType=guess_type('a.'+ext)[0]))
        for ext, mt in {
            "rels": "application/vnd.openxmlformats-package.relationships+xml",
            "odttf": "application/vnd.openxmlformats-officedocument.obfuscatedFont",
        }.iteritems():
            added.add(ext)
            types.append(E.Default(Extension=ext, ContentType=mt))
        # TODO: Iterate over all resources and add mimetypes for any that are
        # not already added
        return xml2str(types, pretty_print=True)

    @property
    def appproperties(self):
        E = ElementMaker(namespace=namespaces['ep'], nsmap={None:namespaces['ep']})
        props = E.Properties(
            E.Application(__appname__),
            E.AppVersion('%02d.%04d' % numeric_version[:2]),
            E.DocSecurity('0'),
            E.HyperlinksChanged('false'),
            E.LinksUpToDate('true'),
            E.ScaleCrop('false'),
            E.SharedDoc('false'),
        )
        return xml2str(props, pretty_print=True)

    @property
    def containerrels(self):
        return textwrap.dedent(b'''\
        <?xml version='1.0' encoding='utf-8'?>
        <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
            <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
            <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
            <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
        </Relationships>''')

    @property
    def websettings(self):
        E = ElementMaker(namespace=namespaces['w'], nsmap={'w':namespaces['w']})
        ws = E.webSettings(
            E.optimizeForBrowser, E.allowPNG, E.doNotSaveAsSingleFile)
        return xml2str(ws, pretty_print=True)

    # }}}

    def write(self, path_or_stream):
        with ZipFile(path_or_stream, 'w') as zf:
            zf.writestr('[Content_Types].xml', self.contenttypes)
            zf.writestr('_rels/.rels', self.containerrels)
            zf.writestr('docProps/app.xml', self.appproperties)
            zf.writestr('word/webSettings.xml', self.websettings)
            # TODO: Write document and document relationships

if __name__ == '__main__':
    d = DOCX()
    print (d.websettings)
