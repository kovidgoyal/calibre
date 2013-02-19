''' CHM File decoding support '''
__license__ = 'GPL v3'
__copyright__  = '2008, Kovid Goyal <kovid at kovidgoyal.net>,' \
                 ' and Alex Bramley <a.bramley at gmail.com>.'

import os

from calibre.customize.conversion import InputFormatPlugin
from calibre.ptempfile import TemporaryDirectory
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
            encoding = self._chm_reader.get_encoding() or options.input_encoding or 'cp1252'
            self._chm_reader.CloseCHM()
            # print tdir, mainpath
            # from calibre import ipython
            # ipython()

            options.debug_pipeline = None
            options.input_encoding = 'utf-8'
            htmlpath, toc = self._create_html_root(mainpath, log, encoding)
            oeb = self._create_oebbook_html(htmlpath, tdir, options, log, metadata)
            options.debug_pipeline = odi
            if toc.count() > 1:
                oeb.toc = self.parse_html_toc(oeb.spine[0])
                oeb.manifest.remove(oeb.spine[0])
                oeb.auto_generated_toc = False
        return oeb

    def parse_html_toc(self, item):
        from calibre.ebooks.oeb.base import TOC, XPath
        dx = XPath('./h:div')
        ax = XPath('./h:a[1]')

        def do_node(parent, div):
            for child in dx(div):
                a = ax(child)[0]
                c = parent.add(a.text, a.attrib['href'])
                do_node(c, child)

        toc = TOC()
        root = XPath('//h:div[1]')(item.data)[0]
        do_node(toc, root)
        return toc

    def _create_oebbook_html(self, htmlpath, basedir, opts, log, mi):
        # use HTMLInput plugin to generate book
        from calibre.customize.builtins import HTMLInput
        opts.breadth_first = True
        htmlinput = HTMLInput(None)
        oeb = htmlinput.create_oebbook(htmlpath, basedir, opts, log, mi)
        return oeb

    def _create_html_root(self, hhcpath, log, encoding):
        from lxml import html
        from urllib import unquote as _unquote
        from calibre.ebooks.oeb.base import urlquote
        from calibre.ebooks.chardet import xml_to_unicode
        hhcdata = self._read_file(hhcpath)
        hhcdata = hhcdata.decode(encoding)
        hhcdata = xml_to_unicode(hhcdata, verbose=True,
                            strip_encoding_pats=True, resolve_entities=True)[0]
        hhcroot = html.fromstring(hhcdata)
        toc = self._process_nodes(hhcroot)
        #print "============================="
        #print "Printing hhcroot"
        #print etree.tostring(hhcroot, pretty_print=True)
        #print "============================="
        log.debug('Found %d section nodes' % toc.count())
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

        def donode(item, parent, base, subpath):
            for child in item:
                title = child.title
                if not title: continue
                raw = unquote_path(child.href or '')
                rsrcname = os.path.basename(raw)
                rsrcpath = os.path.join(subpath, rsrcname)
                if (not os.path.exists(os.path.join(base, rsrcpath)) and
                        os.path.exists(os.path.join(base, raw))):
                    rsrcpath = raw

                if '%' not in rsrcpath:
                    rsrcpath = urlquote(rsrcpath)
                if not raw:
                    rsrcpath = ''
                c = DIV(A(title, href=rsrcpath))
                donode(child, c, base, subpath)
                parent.append(c)

        with open(htmlpath, 'wb') as f:
            if toc.count() > 1:
                from lxml.html.builder import HTML, BODY, DIV, A
                path0 = toc[0].href
                path0 = unquote_path(path0)
                subpath = os.path.dirname(path0)
                base = os.path.dirname(f.name)
                root = DIV()
                donode(toc, root, base, subpath)
                raw = html.tostring(HTML(BODY(root)), encoding='utf-8',
                                   pretty_print=True)
                f.write(raw)
            else:
                f.write(hhcdata)
        return htmlpath, toc

    def _read_file(self, name):
        f = open(name, 'rb')
        data = f.read()
        f.close()
        return data

    def add_node(self, node, toc, ancestor_map):
        from calibre.ebooks.chm.reader import match_string
        if match_string(node.attrib['type'], 'text/sitemap'):
            p = node.xpath('ancestor::ul[1]/ancestor::li[1]/object[1]')
            parent = p[0] if p else None
            toc = ancestor_map.get(parent, toc)
            title = href = u''
            for param in node.xpath('./param'):
                if match_string(param.attrib['name'], 'name'):
                    title = param.attrib['value']
                elif match_string(param.attrib['name'], 'local'):
                    href = param.attrib['value']
            child = toc.add(title or _('Unknown'), href)
            ancestor_map[node] = child

    def _process_nodes(self, root):
        from calibre.ebooks.oeb.base import TOC
        toc = TOC()
        ancestor_map = {}
        for node in root.xpath('//object'):
            self.add_node(node, toc, ancestor_map)
        return toc


