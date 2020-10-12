# -*- coding: utf-8 -*-


__license__ = 'GPL 3'
__copyright__ = '2010, Li Fanxi <lifanxi@freemindworld.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.filenames import ascii_filename
from polyglot.builtins import unicode_type

HTML_TEMPLATE = '<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/><title>%s</title></head><body>\n%s\n</body></html>'


def html_encode(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;').replace('\n', '<br/>').replace(' ', '&nbsp;')  # noqa


class SNBInput(InputFormatPlugin):

    name        = 'SNB Input'
    author      = 'Li Fanxi'
    description = 'Convert SNB files to OEB'
    file_types  = {'snb'}
    commit_name = 'snb_input'

    options = set()

    def convert(self, stream, options, file_ext, log,
                accelerators):
        import uuid

        from calibre.ebooks.oeb.base import DirContainer
        from calibre.ebooks.snb.snbfile import SNBFile
        from calibre.utils.xml_parse import safe_xml_fromstring

        log.debug("Parsing SNB file...")
        snbFile = SNBFile()
        try:
            snbFile.Parse(stream)
        except:
            raise ValueError("Invalid SNB file")
        if not snbFile.IsValid():
            log.debug("Invalid SNB file")
            raise ValueError("Invalid SNB file")
        log.debug("Handle meta data ...")
        from calibre.ebooks.conversion.plumber import create_oebbook
        oeb = create_oebbook(log, None, options,
                encoding=options.input_encoding, populate=False)
        meta = snbFile.GetFileStream('snbf/book.snbf')
        if meta is not None:
            meta = safe_xml_fromstring(meta)
            l = {'title'    : './/head/name',
                  'creator'  : './/head/author',
                  'language' : './/head/language',
                  'generator': './/head/generator',
                  'publisher': './/head/publisher',
                  'cover'    : './/head/cover', }
            d = {}
            for item in l:
                node = meta.find(l[item])
                if node is not None:
                    d[item] = node.text if node.text is not None else ''
                else:
                    d[item] = ''

            oeb.metadata.add('title', d['title'])
            oeb.metadata.add('creator', d['creator'], attrib={'role':'aut'})
            oeb.metadata.add('language', d['language'].lower().replace('_', '-'))
            oeb.metadata.add('generator', d['generator'])
            oeb.metadata.add('publisher', d['publisher'])
            if d['cover'] != '':
                oeb.guide.add('cover', 'Cover', d['cover'])

        bookid = unicode_type(uuid.uuid4())
        oeb.metadata.add('identifier', bookid, id='uuid_id', scheme='uuid')
        for ident in oeb.metadata.identifier:
            if 'id' in ident.attrib:
                oeb.uid = oeb.metadata.identifier[0]
                break

        with TemporaryDirectory('_snb2oeb', keep=True) as tdir:
            log.debug('Process TOC ...')
            toc = snbFile.GetFileStream('snbf/toc.snbf')
            oeb.container = DirContainer(tdir, log)
            if toc is not None:
                toc = safe_xml_fromstring(toc)
                i = 1
                for ch in toc.find('.//body'):
                    chapterName = ch.text
                    chapterSrc = ch.get('src')
                    fname = 'ch_%d.htm' % i
                    data = snbFile.GetFileStream('snbc/' + chapterSrc)
                    if data is None:
                        continue
                    snbc = safe_xml_fromstring(data)
                    lines = []
                    for line in snbc.find('.//body'):
                        if line.tag == 'text':
                            lines.append('<p>%s</p>' % html_encode(line.text))
                        elif line.tag == 'img':
                            lines.append('<p><img src="%s" /></p>' % html_encode(line.text))
                    with open(os.path.join(tdir, fname), 'wb') as f:
                        f.write((HTML_TEMPLATE % (chapterName, '\n'.join(lines))).encode('utf-8', 'replace'))
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
