# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2010, Li Fanxi <lifanxi@freemindworld.com>'
__docformat__ = 'restructuredtext en'

import os, uuid

from calibre.customize.conversion import InputFormatPlugin
from calibre.ebooks.oeb.base import DirContainer
from calibre.ebooks.snb.snbfile import SNBFile
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.filenames import ascii_filename
from lxml import etree

HTML_TEMPLATE = u'<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/><title>%s</title></head><body>\n%s\n</body></html>'

def html_encode(s):
    return s.replace(u'&', u'&amp;').replace(u'<', u'&lt;').replace(u'>', u'&gt;').replace(u'"', u'&quot;').replace(u"'", u'&apos;').replace(u'\n', u'<br/>').replace(u' ', u'&nbsp;')

class SNBInput(InputFormatPlugin):

    name        = 'SNB Input'
    author      = 'Li Fanxi'
    description = 'Convert SNB files to OEB'
    file_types  = set(['snb'])

    options = set([
    ])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        log.debug("Parsing SNB file...")
        snbFile = SNBFile()
        try:
            snbFile.Parse(stream)
        except:
            raise ValueError("Invalid SNB file")
        if not snbFile.IsValid():
            log.debug("Invaild SNB file")
            raise ValueError("Invalid SNB file")
        log.debug("Handle meta data ...")
        from calibre.ebooks.conversion.plumber import create_oebbook
        oeb = create_oebbook(log, None, options, self,
                encoding=options.input_encoding, populate=False)
        meta = snbFile.GetFileStream('snbf/book.snbf')
        if meta != None:
            meta = etree.fromstring(meta)
            oeb.metadata.add('title', meta.find('.//head/name').text)
            oeb.metadata.add('creator', meta.find('.//head/author').text, attrib={'role':'aut'})
            oeb.metadata.add('language', meta.find('.//head/language').text.lower().replace('_', '-'))
            oeb.metadata.add('creator', meta.find('.//head/generator').text)
            oeb.metadata.add('publisher', meta.find('.//head/publisher').text)
            cover = meta.find('.//head/cover')
            if cover != None and cover.text != None:
                oeb.guide.add('cover', 'Cover', cover.text)

        bookid = str(uuid.uuid4())
        oeb.metadata.add('identifier', bookid, id='uuid_id', scheme='uuid')
        for ident in oeb.metadata.identifier:
            if 'id' in ident.attrib:
                oeb.uid = oeb.metadata.identifier[0]
                break

        with TemporaryDirectory('_chm2oeb', keep=True) as tdir:
            log.debug('Process TOC ...')
            toc = snbFile.GetFileStream('snbf/toc.snbf')
            oeb.container = DirContainer(tdir, log)
            if toc != None:
                toc = etree.fromstring(toc)
                i = 1
                for ch in toc.find('.//body'):
                    chapterName = ch.text
                    chapterSrc = ch.get('src')
                    fname = 'ch_%d.htm' % i
                    data = snbFile.GetFileStream('snbc/' + chapterSrc)
                    if data != None:
                        snbc = etree.fromstring(data)
                        outputFile = open(os.path.join(tdir, fname), 'wb')
                        lines = []
                        for line in snbc.find('.//body'):
                            if line.tag == 'text':
                                lines.append(u'<p>%s</p>' % html_encode(line.text))
                            elif line.tag == 'img':
                                lines.append(u'<p><img src="%s" /></p>' % html_encode(line.text))
                        outputFile.write((HTML_TEMPLATE % (chapterName, u'\n'.join(lines))).encode('utf-8', 'replace'))
                        outputFile.close()
                    oeb.toc.add(ch.text, fname)
                    id, href = oeb.manifest.generate(id='html',
                        href=ascii_filename(fname))
                    item = oeb.manifest.add(id, href, 'text/html')
                    item.html_input_href = fname
                    oeb.spine.add(item, True)
                    i = i + 1
                imageFiles = snbFile.OutputImageFiles(tdir)
                for f, m in imageFiles:
                    id, href = oeb.manifest.generate(id='image',
                        href=ascii_filename(f))
                    item = oeb.manifest.add(id, href, m)
                    item.html_input_href = f

        return oeb

