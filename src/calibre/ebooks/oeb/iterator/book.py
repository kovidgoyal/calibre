#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


'''
Iterate over the HTML files in an ebook. Useful for writing viewers.
'''

import re, os, math
from functools import partial

from calibre.ebooks.metadata.opf2 import OPF
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.config import DynamicConfig
from calibre.utils.logging import default_log
from calibre import (guess_type, prepare_string_for_xml,
        xml_replace_entities)
from calibre.ebooks.oeb.transforms.cover import CoverManager
from calibre.ebooks.oeb.iterator.spine import (SpineItem, create_indexing_data)
from calibre.ebooks.oeb.iterator.bookmarks import BookmarksMixin

TITLEPAGE = CoverManager.SVG_TEMPLATE.decode('utf-8').replace(
        '__ar__', 'none').replace('__viewbox__', '0 0 600 800'
        ).replace('__width__', '600').replace('__height__', '800')

class FakeOpts(object):
    verbose = 0
    breadth_first = False
    max_levels = 5
    input_encoding = None


def write_oebbook(oeb, path):
    from calibre.ebooks.oeb.writer import OEBWriter
    from calibre import walk
    w = OEBWriter()
    w(oeb, path)
    for f in walk(path):
        if f.endswith('.opf'):
            return f

class EbookIterator(BookmarksMixin):

    CHARACTERS_PER_PAGE = 1000

    def __init__(self, pathtoebook, log=None):
        self.log = log or default_log
        pathtoebook = pathtoebook.strip()
        self.pathtoebook = os.path.abspath(pathtoebook)
        self.config = DynamicConfig(name='iterator')
        ext = os.path.splitext(pathtoebook)[1].replace('.', '').lower()
        ext = re.sub(r'(x{0,1})htm(l{0,1})', 'html', ext)
        self.ebook_ext = ext.replace('original_', '')

    def search(self, text, index, backwards=False):
        text = prepare_string_for_xml(text.lower())
        pmap = [(i, path) for i, path in enumerate(self.spine)]
        if backwards:
            pmap.reverse()
        for i, path in pmap:
            if (backwards and i < index) or (not backwards and i > index):
                with open(path, 'rb') as f:
                    raw = f.read().decode(path.encoding)
                try:
                    raw = xml_replace_entities(raw)
                except:
                    pass
                if text in raw.lower():
                    return i

    def __enter__(self, processed=False, only_input_plugin=False,
            run_char_count=True, read_anchor_map=True,
            extract_embedded_fonts_for_qt=False):
        ''' Convert an ebook file into an exploded OEB book suitable for
        display in viewers/preprocessing etc. '''

        from calibre.ebooks.conversion.plumber import Plumber, create_oebbook

        self.delete_on_exit = []
        self._tdir = TemporaryDirectory('_ebook_iter')
        self.base  = self._tdir.__enter__()
        plumber = Plumber(self.pathtoebook, self.base, self.log)
        plumber.setup_options()
        if self.pathtoebook.lower().endswith('.opf'):
            plumber.opts.dont_package = True
        if hasattr(plumber.opts, 'no_process'):
            plumber.opts.no_process = True

        plumber.input_plugin.for_viewer = True
        with plumber.input_plugin, open(plumber.input, 'rb') as inf:
            self.pathtoopf = plumber.input_plugin(inf,
                plumber.opts, plumber.input_fmt, self.log,
                {}, self.base)

            if not only_input_plugin:
                # Run the HTML preprocess/parsing from the conversion pipeline as
                # well
                if (processed or plumber.input_fmt.lower() in {'pdb', 'pdf', 'rb'}
                        and not hasattr(self.pathtoopf, 'manifest')):
                    if hasattr(self.pathtoopf, 'manifest'):
                        self.pathtoopf = write_oebbook(self.pathtoopf, self.base)
                    self.pathtoopf = create_oebbook(self.log, self.pathtoopf,
                            plumber.opts)

            if hasattr(self.pathtoopf, 'manifest'):
                self.pathtoopf = write_oebbook(self.pathtoopf, self.base)

        self.book_format = os.path.splitext(self.pathtoebook)[1][1:].upper()
        if getattr(plumber.input_plugin, 'is_kf8', False):
            self.book_format = 'KF8'

        self.opf = getattr(plumber.input_plugin, 'optimize_opf_parsing', None)
        if self.opf is None:
            self.opf = OPF(self.pathtoopf, os.path.dirname(self.pathtoopf))
        self.language = self.opf.language
        if self.language:
            self.language = self.language.lower()
        ordered = [i for i in self.opf.spine if i.is_linear] + \
                  [i for i in self.opf.spine if not i.is_linear]
        self.spine = []
        Spiny = partial(SpineItem, read_anchor_map=read_anchor_map,
                run_char_count=run_char_count, from_epub=self.book_format == 'EPUB')
        is_comic = plumber.input_fmt.lower() in {'cbc', 'cbz', 'cbr', 'cb7'}
        for i in ordered:
            spath = i.path
            mt = None
            if i.idref is not None:
                mt = self.opf.manifest.type_for_id(i.idref)
            if mt is None:
                mt = guess_type(spath)[0]
            try:
                self.spine.append(Spiny(spath, mime_type=mt))
                if is_comic:
                    self.spine[-1].is_single_page = True
            except:
                self.log.warn('Missing spine item:', repr(spath))

        cover = self.opf.cover
        if cover and self.ebook_ext in {'lit', 'mobi', 'prc', 'opf', 'fb2',
                                        'azw', 'azw3'}:
            cfile = os.path.join(self.base, 'calibre_iterator_cover.html')
            rcpath = os.path.relpath(cover, self.base).replace(os.sep, '/')
            chtml = (TITLEPAGE%prepare_string_for_xml(rcpath, True)).encode('utf-8')
            with open(cfile, 'wb') as f:
                f.write(chtml)
            self.spine[0:0] = [Spiny(cfile,
                mime_type='application/xhtml+xml')]
            self.delete_on_exit.append(cfile)

        if self.opf.path_to_html_toc is not None and \
           self.opf.path_to_html_toc not in self.spine:
            try:
                self.spine.append(Spiny(self.opf.path_to_html_toc))
            except:
                import traceback
                traceback.print_exc()

        sizes = [i.character_count for i in self.spine]
        self.pages = [math.ceil(i/float(self.CHARACTERS_PER_PAGE)) for i in sizes]
        for p, s in zip(self.pages, self.spine):
            s.pages = p
        start = 1

        for s in self.spine:
            s.start_page = start
            start += s.pages
            s.max_page = s.start_page + s.pages - 1
        self.toc = self.opf.toc
        if read_anchor_map:
            create_indexing_data(self.spine, self.toc)

        self.read_bookmarks()

        if extract_embedded_fonts_for_qt:
            from calibre.ebooks.oeb.iterator.extract_fonts import extract_fonts
            try:
                extract_fonts(self.opf, self.log)
            except:
                ol = self.log.filter_level
                self.log.filter_level = self.log.DEBUG
                self.log.exception('Failed to extract fonts')
                self.log.filter_level = ol

        return self

    def __exit__(self, *args):
        self._tdir.__exit__(*args)
        for x in self.delete_on_exit:
            try:
                os.remove(x)
            except:
                pass


