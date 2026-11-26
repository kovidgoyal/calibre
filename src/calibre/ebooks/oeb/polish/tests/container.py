#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import os
import pickle
import subprocess
from typing import TYPE_CHECKING
from zipfile import ZipFile

from lxml import etree

from calibre import CurrentDir
from calibre.ebooks.oeb.polish.container import OCF_NS, clone_container
from calibre.ebooks.oeb.polish.container import get_container as _gc
from calibre.ebooks.oeb.polish.replace import rationalize_folders, rename_files
from calibre.ebooks.oeb.polish.split import do_split, merge, split, split_at_body_children
from calibre.ebooks.oeb.polish.tests.base import BaseTest, get_simple_book, get_split_book
from calibre.ptempfile import TemporaryDirectory, TemporaryFile
from calibre.utils.filenames import nlinks_file
from calibre.utils.logging import DevNull
from calibre.utils.resources import get_path as P

if TYPE_CHECKING:
    from lxml.etree import _ElementTree

    from calibre.ebooks.oeb.polish.check.base import BaseError
    from calibre.ebooks.oeb.polish.container import Container
    from calibre.ebooks.oeb.polish.utils import FolderCaseMap


def get_container(path: str, tdir: str | None = None) -> Container:
    return _gc(path, tdir=tdir, tweak_mode=True)


class ContainerTests(BaseTest):
    def test_clone(self) -> None:
        "Test cloning of containers"
        for fmt in ('epub', 'azw3'):
            base = os.path.join(self.tdir, fmt + '-')
            book = get_simple_book(fmt)
            tdir = base + 'first'
            os.mkdir(tdir)
            c1 = get_container(book, tdir=tdir)
            tdir = base + 'second'
            os.mkdir(tdir)
            c2 = clone_container(c1, tdir)

            for c in (c1, c2):
                for name, path in c.name_path_map.items():
                    self.assertEqual(2, nlinks_file(path), f'The file {name} is not linked')

            for name in c1.name_path_map:
                self.assertIn(name, c2.name_path_map)
                with c1.open(name) as one, c2.open(name) as two:
                    self.assertEqual(one.read(), two.read(), f'The file {name} differs')

            spine_names = tuple(x[0] for x in c1.spine_names)
            text = spine_names[0]
            root = c2.parsed(text)
            root.xpath('//*[local-name()="body"]')[0].set('id', 'changed id for test')
            c2.dirty(text)
            c2.commit_item(text)
            for c in (c1, c2):
                self.assertEqual(1, nlinks_file(c.name_path_map[text]))
            with c1.open(text) as c1f, c2.open(text) as c2f:
                self.assertNotEqual(c1f.read(), c2f.read())

            name = spine_names[1]
            with c1.open(name, mode='r+b') as f:
                f.seek(0, 2)
                f.write(b'    ')
            for c in (c1, c2):
                self.assertEqual(1, nlinks_file(c.name_path_map[name]))
            with c1.open(text) as c1f, c2.open(text) as c2f:
                self.assertNotEqual(c1f.read(), c2f.read())

            x = base + 'out.' + fmt
            for c in (c1, c2):
                c.commit(outpath=x)
            c = pickle.loads(pickle.dumps(c1))
            for attr in c1.data_for_clone():
                self.assertEqual(getattr(c1, attr), getattr(c, attr))

    def test_file_removal(self) -> None:
        "Test removal of files from the container"
        book = get_simple_book()
        c = get_container(book, tdir=self.tdir)
        files = ('toc.ncx', 'cover.png', 'titlepage.xhtml')
        self.assertIn('titlepage.xhtml', {x[0] for x in c.spine_names})
        self.assertTrue(c.opf_xpath('//opf:meta[@name="cover"]'))
        for x in files:
            c.remove_item(x)
        self.assertIn(c.opf_name, c.dirtied)
        self.assertNotIn('titlepage.xhtml', {x[0] for x in c.spine_names})
        self.assertFalse(c.opf_xpath('//opf:meta[@name="cover"]'))
        raw = c.serialize_item(c.opf_name).decode('utf-8')
        for x in files:
            self.assertNotIn(x, raw)

    def run_external_tools(self, container: Container, vim: bool = False, epubcheck: bool = True) -> None:
        with TemporaryFile(suffix='.epub', dir=self.tdir) as f:
            container.commit(outpath=f)
            if vim:
                subprocess.Popen(['vim', '-f', f]).wait()
            if epubcheck:
                subprocess.Popen(['epubcheck', f]).wait()

    def test_file_rename(self) -> None:
        "Test renaming of files"
        book = get_simple_book()
        count = [0]

        def new_container() -> Container:
            count[0] += 1
            tdir = os.path.join(self.tdir, str(count[0]))
            os.mkdir(tdir)
            return get_container(book, tdir=tdir)

        # Test simple opf rename
        c = new_container()
        orig_name = c.opf_name
        name = 'renamed opf.opf'
        rename_files(c, {c.opf_name: name})
        self.assertEqual(c.opf_name, name)
        for x in ('name_path_map', 'mime_map'):
            self.assertNotIn(orig_name, getattr(c, x))
            self.assertIn(name, getattr(c, x))
        self.assertNotIn(name, c.dirtied)
        root = c.parsed('META-INF/container.xml')
        vals = set(root.xpath(r'child::ocf:rootfiles/ocf:rootfile/@full-path', namespaces={'ocf': OCF_NS}))
        self.assertSetEqual(vals, {name})
        self.check_links(c)

        # Test a rename that moves the OPF into different directory
        c = new_container()
        orig_name = c.opf_name
        name = 'renamed/again/metadata.opf'
        rename_files(c, {c.opf_name: name})
        self.check_links(c)

        # Test that renaming commits dirtied items
        c = new_container()
        name = next(c.spine_names)[0]
        root = c.parsed(name)
        root.xpath('//*[local-name()="body"]')[0].set('id', 'rename-dirty-test')
        rename_files(c, {name: 'other/' + name})
        with c.open('other/' + name) as f:
            raw = f.read()
        self.assertIn(b'id="rename-dirty-test"', raw)
        self.check_links(c)

        # Test renaming of stylesheets
        c = new_container()
        rename_files(c, {'stylesheet.css': 'styles/s 1.css', 'page_styles.css': 'styles/p 1.css'})
        self.check_links(c)

        # Test renaming of images
        c = new_container()
        rename_files(
            c,
            {
                'cover.png': 'images/cover img.png',
                'light_wood.png': 'images/light wood.png',
                'marked.png': 'images/marked img.png',
            },
        )
        self.check_links(c)

        # Test renaming of ToC
        c = new_container()
        rename_files(c, {'toc.ncx': 'toc/toc file.ncx'})
        self.check_links(c)

        # Test renaming of font files
        c = new_container()
        fname = 'LiberationMono-Regular.ttf'
        if fname not in c.name_path_map:
            fname = fname.lower()  # On OS X the font file name is lowercased for some reason (maybe on windows too)
        rename_files(c, {fname: 'fonts/LiberationMono Regular.ttf'})
        self.check_links(c)

        # Test renaming of text files
        c = new_container()
        rename_files(
            c,
            {'index_split_000.html': 'text/page one fällen.html', 'index_split_001.html': 'text/page two fällen.html'},
        )
        self.check_links(c)

        # Test rename with only case change
        c = new_container()
        rename_files(c, {'index_split_000.html': 'Index_split_000.html'})
        self.check_links(c)

        # self.run_external_tools(c, vim=True)

    def test_file_add(self) -> None:
        "Test adding of files"
        book = get_simple_book()
        c = get_container(book)
        name = 'folder/added file.html'
        c.add_file(name, b'xxx')
        self.assertEqual('xxx', c.raw_data(name))
        self.assertIn(name, set(c.manifest_id_map.values()))
        self.assertIn(name, {x[0] for x in c.spine_names})

        name = 'added.css'
        c.add_file(name, b'xxx')
        self.assertEqual('xxx', c.raw_data(name))
        self.assertIn(name, set(c.manifest_id_map.values()))
        self.assertNotIn(name, {x[0] for x in c.spine_names})
        self.assertEqual(c.make_name_unique(name), 'added-1.css')
        c.add_file('added-1.css', b'xxx')
        self.assertEqual(c.make_name_unique(name.upper()), 'added-2.css'.upper())

        self.check_links(c)

    def test_actual_case(self) -> None:
        "Test getting the actual case for files from names on case insensitive filesystems"
        from calibre.ebooks.oeb.polish.utils import actual_case_for_name, corrected_case_for_name

        book = get_simple_book()
        c = get_container(book)
        name = 'f1/f2/added file.html'
        c.add_file(name, b'xxx')
        self.assertTrue(c.exists(name))
        variations = (name, name.upper(), name.replace('f1', 'F1'), name.replace('f2', 'F2'))
        self.assertEqual(name, actual_case_for_name(c, name, {}))
        if c.exists(name.upper()):
            folder_case_map: FolderCaseMap = {}
            for n in variations:
                self.assertEqual(name, actual_case_for_name(c, n))
                self.assertEqual(name, actual_case_for_name(c, n, folder_case_map))
        else:
            folder_case_map = {}
            for n in variations:
                self.assertEqual(name, corrected_case_for_name(c, n))
                self.assertEqual(name, corrected_case_for_name(c, n, folder_case_map))
            self.assertIsNone(corrected_case_for_name(c, name + '/xx'))
            self.assertIsNone(corrected_case_for_name(c, name + '/xx', folder_case_map))
            self.assertIsNone(corrected_case_for_name(c, name.upper() + '/xx', folder_case_map))
            self.assertIsNone(corrected_case_for_name(c, 'f1/F2/missing.html', folder_case_map))

    def test_check_manifest_case_mismatch(self) -> None:
        "Test that fixing a case mismatch in the manifest does not remove the file"
        from calibre.ebooks.oeb.polish.check.links import CaseMismatch
        from calibre.ebooks.oeb.polish.check.main import fix_errors
        from calibre.ebooks.oeb.polish.check.main import run_checks as run_all_checks

        def run_checks(c: Container) -> list[BaseError]:
            # The stylesheet of the simple book has a font-family without a generic family
            return run_all_checks(c, frozenset({'css:font-family-no-missing-generic-family-keyword'}))

        c = get_container(get_simple_book())
        # Audio referenced only from the media overlay of a spine item
        c.add_file('audio.mp3', b'xxx')
        c.add_file('overlay.smil', b'<smil xmlns="http://www.w3.org/ns/SMIL"><body><par><audio src="audio.mp3"/></par></body></smil>')
        overlay_id = {v: k for k, v in c.manifest_id_map.items()}['overlay.smil']
        # Cover image referenced only from <meta name="cover">
        for img in c.parsed('titlepage.xhtml').xpath('//*[@*[local-name()="href" or local-name()="src"]="cover.png"]'):
            img.getparent().remove(img)
        c.dirty('titlepage.xhtml')
        renames = {'index_split_001.html': 'INDEX_split_001.html', 'cover.png': 'Cover.png'}
        for item in c.opf_xpath('//opf:manifest/opf:item[@href]'):
            if (href := item.get('href')) in renames:
                item.set('href', renames[href])
                if href == 'index_split_001.html':
                    item.set('media-overlay', overlay_id)
        c.dirty(c.opf_name)
        self.assertNotIn('cover.png', {x for n in c.mime_map if n.endswith(('html', 'xhtml')) for x, *_ in c.iterlinks(n)})
        # A link with the wrong case still counts as a reference to the file
        for img in c.parsed('index_split_000.html').xpath('//*[local-name()="img"][@src="marked.png"]'):
            img.set('src', 'Marked.png')
        c.dirty('index_split_000.html')
        errors = run_checks(c)
        self.assertEqual({type(e) for e in errors}, {CaseMismatch}, '\n'.join(f'{type(e).__name__}: {e.msg}' for e in errors))
        self.assertEqual(len(errors), len(renames) + 1)
        self.assertTrue(fix_errors(c, errors))
        for name in (*renames, 'audio.mp3'):
            self.assertTrue(c.has_name(name), f'{name} was removed from the book')
        self.assertEqual(set(renames) - set(c.manifest_id_map.values()), set())
        self.assertEqual(run_checks(c), [])

    def test_split_file(self) -> None:
        "Test splitting of files"
        book = get_split_book()
        c = get_container(book)
        name = 'index.html'
        nname = split(c, name, '//*[@id="page2"]')
        root = c.parsed(nname)
        troot = c.parsed(name)
        self.assertEqual(1, len(root.xpath('//*[@id="container"]')), 'Split point was not adjusted')
        self.assertEqual(0, len(troot.xpath('//*[@id="container"]')), 'Split point was not adjusted')
        self.check_links(c)

    def test_split_at_body_children(self) -> None:
        "Test that splitting at many points at once matches sequential splitting"
        log = DevNull()

        def tree_from(body: str) -> _ElementTree:
            return etree.fromstring(
                f'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>t</title></head><body class="b">{body}</body></html>'
            ).getroottree()

        def serialize(trees: list[_ElementTree]) -> list[bytes]:
            return [etree.tostring(t) for t in trees]

        def sequential(body: str, points: tuple[tuple[str, bool], ...]) -> list[bytes]:
            trees = [tree_from(body)]
            for pid, before in points:
                for i in range(len(trees) - 1, -1, -1):
                    elems = trees[i].getroot().xpath(f'//*[@id="{pid}"]')
                    if elems:
                        trees[i : i + 1] = do_split(elems[0], log, before=before)
                        break
            return serialize(trees)

        def at_once(body: str, points: tuple[tuple[str, bool], ...]) -> list[bytes] | None:
            tree = tree_from(body)
            before_split = etree.tostring(tree)
            root = tree.getroot()
            split_points = [(root.xpath(f'//*[@id="{pid}"]')[0], before) for pid, before in points]
            trees = split_at_body_children(tree, split_points, log)
            self.assertEqual(before_split, etree.tostring(tree), 'Original tree was modified')
            return None if trees is None else serialize(trees)

        # Elements used as after split points have no tail text
        flat = 'btext<h1 id="t">Title</h1>\n<p id="a">a<b>b</b></p> <!-- c -->tc<p id="q">q</p>tq<h2 id="h">H</h2>\n<p id="z">z</p>\n'
        for body, points in (
            (flat, (('h', True),)),
            (flat, (('a', True), ('h', True))),
            (flat, (('q', True), ('h', True))),
            (flat, (('t', True), ('z', True))),
            (flat, (('t', True), ('a', False), ('h', True))),
            (flat, (('a', False), ('h', False))),
            (flat, (('h', False), ('z', False))),
            (flat, (('t', False), ('a', True), ('h', False), ('z', True))),
            (flat, ()),
            # Split point adjusted to a child of body
            ('<p>x</p><div id="d"><h2 id="h">H</h2><p>y</p></div>\n<p id="p">p</p>', (('h', True), ('p', True))),
            ('<div id="d"><h2 id="h">H</h2><p>y</p></div><p id="p">p</p>', (('d', True), ('h', True))),
            # Redundant namespace declarations must be preserved
            (
                '<p id="a">a</p><p xmlns="http://www.w3.org/1999/xhtml" id="b">b<i xmlns:epub="http://www.idpf.org/2007/ops">i</i></p><p id="c">c</p>',
                (('b', True), ('c', True)),
            ),
            # Comment at a split boundary, no body text
            ('<p id="a">a</p><!-- c --><p id="b">b</p>', (('a', False), ('b', True))),
        ):
            expected = sequential(body, points)
            self.assertEqual(expected, at_once(body, points), f'Mismatch for: {body} split at: {points}')

        for body, points in (
            # Not a child of body, even after adjustment
            ('<div><p id="x">x</p><h2 id="h">H</h2><p>y</p></div>', (('h', True),)),
            ('<div><h2 id="h">H</h2><p>y</p></div>', (('h', False),)),
            # All content wrapped in a single <div>
            ('<div><h2 id="a">A</h2><p>a</p><h2 id="b">B</h2><p>b</p></div>', (('a', True), ('b', True))),
            # Split after with significant tail text
            ('<p id="a">a</p>tail<p id="b">b</p>', (('a', False),)),
            # Not in document order after adjustment
            ('<p id="a">a</p><div id="d"><h2 id="h">H</h2></div>', (('d', False), ('h', True))),
        ):
            self.assertIsNone(at_once(body, points), f'Fast path wrongly used for: {body} split at: {points}')
            self.assertGreater(len(sequential(body, points)), 1)

    def test_split_on_page_breaks_duplicate_ids(self) -> None:
        "Page breaks on elements with duplicate ids must split as they always did"
        from calibre.ebooks.oeb.transforms.split import FlowSplitter, XPath

        root = etree.fromstring(
            '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>t</title></head><body>'
            '<p id="b">intro</p><h2 id="a">A</h2><p>a</p><h2 id="b">B</h2><p>b</p></body></html>'
        )
        fs = FlowSplitter.__new__(FlowSplitter)
        fs.log = DevNull()
        fs.page_break_ids = ['a', 'b']
        fs.page_breaks = [(XPath('//*[@id="a"]'), True), (XPath('//*[@id="b"]'), True)]
        fs.split_on_page_breaks(root.getroottree())
        self.assertEqual(['t\nintro', 't\nAaBb'], [''.join(t.getroot().itertext()) for t in fs.trees])

    def test_merge_file(self) -> None:
        "Test merging of files"
        book = get_simple_book()
        c = get_container(book)
        merge(c, 'text', ('index_split_000.html', 'index_split_001.html'), 'index_split_000.html')
        self.check_links(c)

        book = get_simple_book()
        c = get_container(book)
        one, two = 'one/one.html', 'two/two.html'
        c.add_file(
            one,
            b'<head><link href="../stylesheet.css"><p><a name="one" href="../two/two.html">1</a><a name="two" href="../two/two.html#one">2</a>',
        )
        c.add_file(
            two,
            b'<head><link href="../page_styles.css"><p><a name="one" href="two.html#two">1</a>'
            b'<a name="two" href="../one/one.html#one">2</a><a href="#one">3</a>',
        )
        merge(c, 'text', (one, two), one)
        self.check_links(c)
        root = c.parsed(one)
        self.assertEqual(1, len(root.xpath('//*[@href="../page_styles.css"]')))

        book = get_simple_book()
        c = get_container(book)
        c.add_file(one, b'<p id="x" aria-labelledby="x">1</p>')
        c.add_file(two, b'<p id="x">2</p><p aria-labelledby="x y" aria-describedby="x">3</p><label for="x">4</label>')
        merge(c, 'text', (one, two), one)
        root = c.parsed(one)
        self.assertEqual(root.xpath('//*[@id]/@id'), ['x', 'x_1'])
        self.assertEqual(root.xpath('//*/@aria-labelledby'), ['x', 'x_1 y'])
        self.assertEqual(root.xpath('//*/@aria-describedby'), ['x_1'])
        self.assertEqual(root.xpath('//*/@for'), ['x_1'])

        book = get_simple_book()
        c = get_container(book)
        merge(c, 'styles', ('stylesheet.css', 'page_styles.css'), 'stylesheet.css')
        self.check_links(c)

    def test_dir_container(self) -> None:
        def create_book(source: str) -> None:
            with ZipFile(P('quick_start/eng.epub', allow_user_override=False)) as zf:
                zf.extractall(source)
            with CurrentDir(source):
                self.assertTrue(os.path.exists('images/cover.jpg'))
                with open('.gitignore', 'wb') as f:
                    f.write(b'nothing')
                os.mkdir('.git')
                with open('.git/xxx', 'wb') as f:
                    f.write(b'xxx')

        with TemporaryDirectory('-polish-dir-container') as source:
            create_book(source)
            c = get_container(source)
            c.remove_item('images/cover.jpg')
            with c.open('images/test-container.xyz', 'wb') as f:
                f.write(b'xyz')
            c.commit()

            with CurrentDir(source):
                self.assertTrue(os.path.exists('.gitignore'))
                self.assertTrue(os.path.exists('.git/xxx'))
                self.assertTrue(os.path.exists('images/test-container.xyz'))
                self.assertFalse(os.path.exists('images/cover.jpg'))

    def test_folder_type_map_case(self) -> None:
        book = get_simple_book()
        c = get_container(book)
        c.add_file('Image/testcase.png', b'xxx')
        rationalize_folders(c, {'image': 'image'})
        self.assertTrue(c.has_name('Image/testcase.png'))
        self.assertTrue(c.exists('Image/testcase.png'))
        self.assertFalse(c.has_name('image/testcase.png'))
