''' CHM File decoding support '''
__license__ = 'GPL v3'
__copyright__  = '2008, Kovid Goyal <kovid at kovidgoyal.net>,' \
                 ' and Alex Bramley <a.bramley at gmail.com>.'

import os

from calibre.customize.conversion import InputFormatPlugin
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.localization import get_lang
from calibre.utils.filenames import ascii_filename
from calibre.constants import filesystem_encoding

class CHMInput(InputFormatPlugin):

    name        = 'CHM Input'
    author      = 'Kovid Goyal and Alex Bramley'
    description = 'Convert CHM files to OEB'
    file_types  = set(['chm'])

    def _chmtohtml(self, output_dir, chm_path, no_images, log, debug_dump=False):
        from calibre.ebooks.chm.reader import CHMReader
        log.debug('Opening CHM file')
        rdr = CHMReader(chm_path, log, input_encoding=self.opts.input_encoding)
        log.debug('Extracting CHM to %s' % output_dir)
        rdr.extract_content(output_dir, debug_dump=debug_dump)
        self._chm_reader = rdr
        return rdr.hhc_path


    def convert(self, stream, options, file_ext, log, accelerators):
        from calibre.ebooks.chm.metadata import get_metadata_from_reader
        from calibre.customize.ui import plugin_for_input_format
        self.opts = options

        log.debug('Processing CHM...')
        with TemporaryDirectory('_chm2oeb') as tdir:
            if not isinstance(tdir, unicode):
                tdir = tdir.decode(filesystem_encoding)
            html_input = plugin_for_input_format('html')
            for opt in html_input.options:
                setattr(options, opt.option.name, opt.recommended_value)
            no_images = False #options.no_images
            chm_name = stream.name
            #chm_data = stream.read()

            #closing stream so CHM can be opened by external library
            stream.close()
            log.debug('tdir=%s' % tdir)
            log.debug('stream.name=%s' % stream.name)
            debug_dump = False
            odi = options.debug_pipeline
            if odi:
                debug_dump = os.path.join(odi, 'input')
            mainname = self._chmtohtml(tdir, chm_name, no_images, log,
                    debug_dump=debug_dump)
            mainpath = os.path.join(tdir, mainname)

            metadata = get_metadata_from_reader(self._chm_reader)
            self._chm_reader.CloseCHM()
            # print tdir, mainpath
            # from calibre import ipython
            # ipython()

            options.debug_pipeline = None
            options.input_encoding = 'utf-8'
            # try a custom conversion:
            #oeb = self._create_oebbook(mainpath, tdir, options, log, metadata)
            # try using html converter:
            htmlpath = self._create_html_root(mainpath, log)
            oeb = self._create_oebbook_html(htmlpath, tdir, options, log, metadata)
            options.debug_pipeline = odi
            #log.debug('DEBUG: Not removing tempdir %s' % tdir)
        return oeb

    def _create_oebbook_html(self, htmlpath, basedir, opts, log, mi):
        # use HTMLInput plugin to generate book
        from calibre.customize.builtins import HTMLInput
        opts.breadth_first = True
        htmlinput = HTMLInput(None)
        oeb = htmlinput.create_oebbook(htmlpath, basedir, opts, log, mi)
        return oeb


    def _create_oebbook(self, hhcpath, basedir, opts, log, mi):
        import uuid
        from lxml import html
        from calibre.ebooks.conversion.plumber import create_oebbook
        from calibre.ebooks.oeb.base import DirContainer
        oeb = create_oebbook(log, None, opts,
                encoding=opts.input_encoding, populate=False)
        self.oeb = oeb

        metadata = oeb.metadata
        if mi.title:
            metadata.add('title', mi.title)
        if mi.authors:
            for a in mi.authors:
                metadata.add('creator', a, attrib={'role':'aut'})
        if mi.publisher:
            metadata.add('publisher', mi.publisher)
        if mi.isbn:
            metadata.add('identifier', mi.isbn, attrib={'scheme':'ISBN'})
        if not metadata.language:
            oeb.logger.warn(u'Language not specified')
            metadata.add('language', get_lang().replace('_', '-'))
        if not metadata.creator:
            oeb.logger.warn('Creator not specified')
            metadata.add('creator', _('Unknown'))
        if not metadata.title:
            oeb.logger.warn('Title not specified')
            metadata.add('title', _('Unknown'))

        bookid = str(uuid.uuid4())
        metadata.add('identifier', bookid, id='uuid_id', scheme='uuid')
        for ident in metadata.identifier:
            if 'id' in ident.attrib:
                self.oeb.uid = metadata.identifier[0]
                break

        hhcdata = self._read_file(hhcpath)
        hhcroot = html.fromstring(hhcdata)
        chapters = self._process_nodes(hhcroot)
        #print "============================="
        #print "Printing hhcroot"
        #print etree.tostring(hhcroot, pretty_print=True)
        #print "============================="
        log.debug('Found %d section nodes' % len(chapters))

        if len(chapters) > 0:
            path0 = chapters[0][1]
            subpath = os.path.dirname(path0)
            htmlpath = os.path.join(basedir, subpath)

            oeb.container = DirContainer(htmlpath, log)
            for chapter in chapters:
                title = chapter[0]
                basename = os.path.basename(chapter[1])
                self._add_item(oeb, title, basename)

            oeb.container = DirContainer(htmlpath, oeb.log)
        return oeb

    def _create_html_root(self, hhcpath, log):
        from lxml import html
        from urllib import unquote as _unquote
        from calibre.ebooks.oeb.base import urlquote
        hhcdata = self._read_file(hhcpath)
        hhcroot = html.fromstring(hhcdata)
        chapters = self._process_nodes(hhcroot)
        #print "============================="
        #print "Printing hhcroot"
        #print etree.tostring(hhcroot, pretty_print=True)
        #print "============================="
        log.debug('Found %d section nodes' % len(chapters))
        htmlpath = os.path.splitext(hhcpath)[0] + ".html"
        base = os.path.dirname(os.path.abspath(htmlpath))

        def unquote(x):
            if isinstance(x, unicode):
                x = x.encode('utf-8')
            return _unquote(x).decode('utf-8')

        def unquote_path(x):
            y = unquote(x)
            if (not os.path.exists(os.path.join(base, x)) and
                os.path.exists(os.path.join(base, y))):
                x = y
            return x

        with open(htmlpath, 'wb') as f:
            if chapters:
                f.write('<html><head><meta http-equiv="Content-type"'
                    ' content="text/html;charset=UTF-8" /></head><body>\n')
                path0 = chapters[0][1]
                path0 = unquote_path(path0)
                subpath = os.path.dirname(path0)
                base = os.path.dirname(f.name)

                for chapter in chapters:
                    title = chapter[0]
                    raw = unquote_path(chapter[1])
                    rsrcname = os.path.basename(raw)
                    rsrcpath = os.path.join(subpath, rsrcname)
                    if (not os.path.exists(os.path.join(base, rsrcpath)) and
                            os.path.exists(os.path.join(base, raw))):
                        rsrcpath = raw

                    # title should already be url encoded
                    if '%' not in rsrcpath:
                        rsrcpath = urlquote(rsrcpath)
                    url = "<br /><a href=" + rsrcpath + ">" + title + " </a>\n"
                    if isinstance(url, unicode):
                        url = url.encode('utf-8')
                    f.write(url)

                f.write("</body></html>")
            else:
                f.write(hhcdata)
        return htmlpath


    def _read_file(self, name):
        f = open(name, 'rb')
        data = f.read()
        f.close()
        return data

    def _visit_node(self, node, chapters, depth):
        # check that node is a normal node (not a comment, DOCTYPE, etc.)
        # (normal nodes have string tags)
        if isinstance(node.tag, basestring):
            from calibre.ebooks.chm.reader import match_string

            chapter_path = None
            if match_string(node.tag, 'object') and match_string(node.attrib['type'], 'text/sitemap'):
                chapter_title = None
                for child in node:
                    if match_string(child.tag,'param') and match_string(child.attrib['name'], 'name'):
                        chapter_title = child.attrib['value']
                    if match_string(child.tag,'param') and match_string(child.attrib['name'],'local'):
                        chapter_path = child.attrib['value']
                if chapter_title is not None and chapter_path is not None:
                    chapter = [chapter_title, chapter_path, depth]
                    chapters.append(chapter)
            if node.tag=="UL":
                depth = depth + 1
            if node.tag=="/UL":
                depth = depth - 1

    def _process_nodes(self, root):
        chapters = []
        depth = 0
        for node in root.iter():
            self._visit_node(node, chapters, depth)
        return chapters

    def _add_item(self, oeb, title, path):
        bname = os.path.basename(path)
        id, href = oeb.manifest.generate(id='html',
                href=ascii_filename(bname))
        item = oeb.manifest.add(id, href, 'text/html')
        item.html_input_href = bname
        oeb.spine.add(item, True)
        oeb.toc.add(title, item.href)

