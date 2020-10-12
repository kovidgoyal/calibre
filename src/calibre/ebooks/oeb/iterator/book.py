#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


'''
Iterate over the HTML files in an ebook. Useful for writing viewers.
'''

import re, os, math
from functools import partial

from calibre.ebooks.metadata.opf2 import OPF
from calibre.ptempfile import PersistentTemporaryDirectory, remove_dir
from calibre.utils.config import DynamicConfig
from calibre.utils.logging import default_log
from calibre.utils.tdir_in_cache import tdir_in_cache
from calibre import guess_type, prepare_string_for_xml
from calibre.ebooks.oeb.transforms.cover import CoverManager
from calibre.ebooks.oeb.iterator.spine import (SpineItem, create_indexing_data)
from calibre.ebooks.oeb.iterator.bookmarks import BookmarksMixin
from calibre.ebooks.oeb.base import urlparse, urlunquote

TITLEPAGE = CoverManager.SVG_TEMPLATE.replace(
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


def extract_book(pathtoebook, tdir, log=None, view_kepub=False, processed=False, only_input_plugin=False):
    from calibre.ebooks.conversion.plumber import Plumber, create_oebbook
    from calibre.utils.logging import default_log
    log = log or default_log
    plumber = Plumber(pathtoebook, tdir, log, view_kepub=view_kepub)
    plumber.setup_options()
    if pathtoebook.lower().endswith('.opf'):
        plumber.opts.dont_package = True
    if hasattr(plumber.opts, 'no_process'):
        plumber.opts.no_process = True

    plumber.input_plugin.for_viewer = True
    with plumber.input_plugin, open(plumber.input, 'rb') as inf:
        pathtoopf = plumber.input_plugin(inf,
            plumber.opts, plumber.input_fmt, log, {}, tdir)

        if not only_input_plugin:
            # Run the HTML preprocess/parsing from the conversion pipeline as
            # well
            if (processed or plumber.input_fmt.lower() in {'pdb', 'pdf', 'rb'} and
                    not hasattr(pathtoopf, 'manifest')):
                if hasattr(pathtoopf, 'manifest'):
                    pathtoopf = write_oebbook(pathtoopf, tdir)
                pathtoopf = create_oebbook(log, pathtoopf, plumber.opts)

        if hasattr(pathtoopf, 'manifest'):
            pathtoopf = write_oebbook(pathtoopf, tdir)

    book_format = os.path.splitext(pathtoebook)[1][1:].upper()
    if getattr(plumber.input_plugin, 'is_kf8', False):
        fs = ':joint' if getattr(plumber.input_plugin, 'mobi_is_joint', False) else ''
        book_format = 'KF8' + fs
    return book_format, pathtoopf, plumber.input_fmt


def run_extract_book(*args, **kwargs):
    from calibre.utils.ipc.simple_worker import fork_job
    ans = fork_job('calibre.ebooks.oeb.iterator.book', 'extract_book', args=args, kwargs=kwargs, timeout=3000, no_output=True)
    return ans['result']


class EbookIterator(BookmarksMixin):

    CHARACTERS_PER_PAGE = 1000

    def __init__(self, pathtoebook, log=None, copy_bookmarks_to_file=True, use_tdir_in_cache=False):
        BookmarksMixin.__init__(self, copy_bookmarks_to_file=copy_bookmarks_to_file)
        self.use_tdir_in_cache = use_tdir_in_cache
        self.log = log or default_log
        pathtoebook = pathtoebook.strip()
        self.pathtoebook = os.path.abspath(pathtoebook)
        self.config = DynamicConfig(name='iterator')
        ext = os.path.splitext(pathtoebook)[1].replace('.', '').lower()
        ext = re.sub(r'(x{0,1})htm(l{0,1})', 'html', ext)
        self.ebook_ext = ext.replace('original_', '')

    def search(self, text, index, backwards=False):
        from calibre.ebooks.oeb.polish.parsing import parse
        pmap = [(i, path) for i, path in enumerate(self.spine)]
        if backwards:
            pmap.reverse()
        q = text.lower()
        for i, path in pmap:
            if (backwards and i < index) or (not backwards and i > index):
                with open(path, 'rb') as f:
                    raw = f.read().decode(path.encoding)
                root = parse(raw)
                fragments = []

                def serialize(elem):
                    if elem.text:
                        fragments.append(elem.text.lower())
                    if elem.tail:
                        fragments.append(elem.tail.lower())
                    for child in elem.iterchildren():
                        if hasattr(getattr(child, 'tag', None), 'rpartition') and child.tag.rpartition('}')[-1] not in {'script', 'style', 'del'}:
                            serialize(child)
                        elif getattr(child, 'tail', None):
                            fragments.append(child.tail.lower())
                for body in root.xpath('//*[local-name() = "body"]'):
                    body.tail = None
                    serialize(body)

                if q in ''.join(fragments):
                    return i

    def __enter__(self, processed=False, only_input_plugin=False,
                  run_char_count=True, read_anchor_map=True, view_kepub=False, read_links=True):
        ''' Convert an ebook file into an exploded OEB book suitable for
        display in viewers/preprocessing etc. '''

        self.delete_on_exit = []
        if self.use_tdir_in_cache:
            self._tdir = tdir_in_cache('ev')
        else:
            self._tdir = PersistentTemporaryDirectory('_ebook_iter')
        self.base  = os.path.realpath(self._tdir)
        self.book_format, self.pathtoopf, input_fmt = run_extract_book(
            self.pathtoebook, self.base, only_input_plugin=only_input_plugin, view_kepub=view_kepub, processed=processed)
        self.opf = OPF(self.pathtoopf, os.path.dirname(self.pathtoopf))
        self.mi = self.opf.to_book_metadata()
        self.language = None
        if self.mi.languages:
            self.language = self.mi.languages[0].lower()

        self.spine = []
        Spiny = partial(SpineItem, read_anchor_map=read_anchor_map, read_links=read_links,
                run_char_count=run_char_count, from_epub=self.book_format == 'EPUB')
        if input_fmt.lower() == 'htmlz':
            self.spine.append(Spiny(os.path.join(os.path.dirname(self.pathtoopf), 'index.html'), mime_type='text/html'))
        else:
            ordered = [i for i in self.opf.spine if i.is_linear] + \
                    [i for i in self.opf.spine if not i.is_linear]
            is_comic = input_fmt.lower() in {'cbc', 'cbz', 'cbr', 'cb7'}
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
                                        'azw', 'azw3', 'docx', 'htmlz'}:
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

        self.verify_links()

        self.read_bookmarks()

        return self

    def verify_links(self):
        spine_paths = {s:s for s in self.spine}
        for item in self.spine:
            base = os.path.dirname(item)
            for link in item.all_links:
                try:
                    p = urlparse(urlunquote(link))
                except Exception:
                    continue
                if not p.scheme and not p.netloc:
                    path = os.path.abspath(os.path.join(base, p.path)) if p.path else item
                    try:
                        path = spine_paths[path]
                    except Exception:
                        continue
                    if not p.fragment or p.fragment in path.anchor_map:
                        item.verified_links.add((path, p.fragment))

    def __exit__(self, *args):
        remove_dir(self._tdir)
        for x in self.delete_on_exit:
            try:
                os.remove(x)
            except:
                pass
