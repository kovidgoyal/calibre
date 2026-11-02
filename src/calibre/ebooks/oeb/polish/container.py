#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import errno
import hashlib
import logging
import os
import re
import shutil
import sys
import unicodedata
import uuid
from collections import defaultdict
from io import BytesIO
from itertools import count
from math import floor
from typing import IO, TYPE_CHECKING, NotRequired, Protocol, TypedDict, TypeGuard, cast, overload
from urllib.parse import urlparse

from css_parser import getUrls, replaceUrls
from lxml import etree

from calibre import CurrentDir, walk
from calibre.constants import iswindows
from calibre.customize.ui import plugin_for_input_format, plugin_for_output_format
from calibre.ebooks import escape_xpath_attr
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.conversion.plugins.epub_input import ADOBE_OBFUSCATION, IDPF_OBFUSCATION, decrypt_font_data
from calibre.ebooks.conversion.preprocess import CSSPreProcessor as cssp
from calibre.ebooks.conversion.preprocess import HTMLPreProcessor
from calibre.ebooks.metadata.opf3 import CALIBRE_PREFIX, ensure_prefix, items_with_property, read_prefixes
from calibre.ebooks.metadata.utils import parse_opf_version
from calibre.ebooks.mobi import MobiError
from calibre.ebooks.mobi.reader.headers import MetadataHeader
from calibre.ebooks.oeb.base import (
    DC11_NS,
    OEB_DOCS,
    OEB_STYLES,
    OPF,
    OPF2_NS,
    Manifest,
    itercsslinks,
    iterlinks,
    rewrite_idrefs,
    rewrite_links,
    serialize,
    urlquote,
    urlunquote,
)
from calibre.ebooks.oeb.parse_utils import NotHTML, parse_html
from calibre.ebooks.oeb.polish.errors import DRMError, InvalidBook
from calibre.ebooks.oeb.polish.parsing import decode_xml
from calibre.ebooks.oeb.polish.parsing import parse as parse_html_tweak
from calibre.ebooks.oeb.polish.utils import OEB_FONTS, CommentFinder, PositionFinder, adjust_mime_for_epub, guess_type, insert_self_closing, parse_css
from calibre.ptempfile import PersistentTemporaryDirectory, PersistentTemporaryFile, TemporaryDirectory
from calibre.utils.filenames import hardlink_file, make_long_path_useable, nlinks_file, retry_on_fail
from calibre.utils.ipc.simple_worker import WorkerError, fork_job
from calibre.utils.localization import _
from calibre.utils.logging import default_log
from calibre.utils.xml_parse import safe_xml_fromstring
from calibre.utils.zipfile import ZipFile

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
    from collections.abc import Container as AbstractContainer
    from typing import Literal

    from css_parser.css import CSSStyleDeclaration, CSSStyleSheet
    from lxml.etree import _Element

    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.ebooks.metadata.utils import OPFVersion
    from calibre.ebooks.oeb.base import OEBBook
    from calibre.utils.logging import Log

#: The type of objects returned by :meth:`Container.parsed`: an lxml element
#: for HTML/XML, a css_parser stylesheet for CSS and raw bytes for everything else
type ParsedObject = _Element | CSSStyleSheet | bytes


class LinkReplacerType(Protocol):
    "The type of the ``replace_func`` passed to :meth:`Container.replace_links`"

    #: Set to True by the replacer if any link was actually changed
    replaced: bool
    #: Set by the container to the type of file being processed
    file_type: str

    def __call__(self, url: str, /) -> str: ...


class CloneData(TypedDict):
    root: str
    opf_name: str
    mime_map: dict[str, str]
    pretty_print: set[str]
    encoding_map: dict[str, str | None]
    tweak_mode: bool
    cloned: bool
    name_path_map: dict[str, str]
    pathtoepub: NotRequired[str]
    obfuscated_fonts: NotRequired[dict[str, tuple[str, bytes]] | set[str]]
    is_dir: NotRequired[bool]
    pathtoazw3: NotRequired[str]


exists, join, relpath = os.path.exists, os.path.join, os.path.relpath
OPF_NAMESPACES = {'opf': OPF2_NS, 'dc': DC11_NS}
null = object()
OEB_FONTS  # ruff: ignore[useless-expression] # for plugin compat


class CSSPreProcessor(cssp):
    def __call__(self, data: str, add_namespace: bool = False) -> str:
        return self.MS_PAT.sub(self.ms_sub, data)


def clone_dir(src: str, dest: str) -> None:
    "Clone a folder using hard links for the files, dest must already exist"
    for x in os.listdir(src):
        dpath = os.path.join(dest, x)
        spath = os.path.join(src, x)
        if os.path.isdir(spath):
            os.mkdir(dpath)
            clone_dir(spath, dpath)
        else:
            try:
                hardlink_file(spath, dpath)
            except Exception:
                shutil.copy2(spath, dpath)


def clone_container[C: Container](container: C, dest_dir: str, container_class: type[C] | None = None) -> C:
    "Efficiently clone a container using hard links"
    dest_dir = os.path.abspath(os.path.realpath(dest_dir))
    clone_data = container.clone_data(dest_dir)
    container_class = container_class or type(container)
    return container_class(log=container.log, clone_data=clone_data)


def name_to_abspath(name: str, root: str) -> str:
    return os.path.abspath(join(root, *name.split('/')))


def abspath_to_name(path: str, root: str) -> str:
    return relpath(os.path.abspath(path), root).replace(os.sep, '/')


def name_to_href(name: str, root: str, base: str | None = None, quote: Callable[[str], str] = urlquote) -> str:
    fullpath = name_to_abspath(name, root)
    basepath = root if base is None else os.path.dirname(name_to_abspath(base, root))
    path = relpath(fullpath, basepath).replace(os.sep, '/')
    return quote(path)


def href_to_name(href: str | None, root: str, base: str | None = None) -> str | None:
    base = root if base is None else os.path.dirname(name_to_abspath(base, root))
    try:
        purl = urlparse(href)
    except ValueError:
        return None
    if purl.scheme or not purl.path:
        return None
    href = urlunquote(purl.path)
    if iswindows and ':' in href:
        # path manipulations on windows fail for paths with : in them, so we
        # assume all such paths are invalid/absolute paths.
        return None
    fullpath = os.path.join(base, *href.split('/'))
    try:
        return unicodedata.normalize('NFC', abspath_to_name(fullpath, root))
    except ValueError:
        return None


def seconds_to_timestamp(duration: float) -> str:
    seconds = floor(duration)
    float_part = duration - seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    ans = f'{hours:02d}:{minutes:02d}:{seconds:02d}'
    if float_part:
        ans += f'{float_part:.20f}'.rstrip('0')[1:]
    return ans


class ContainerBase:  # {{{
    """
    A base class that implements just the parsing methods. Useful to create
    virtual containers for testing.
    """

    #: The mode used to parse HTML and CSS (polishing uses tweak_mode=False and the editor uses tweak_mode=True)
    tweak_mode = False
    #: The encoding used to decode the most recently parsed/decoded file
    used_encoding: str | None

    def __init__(self, log: Log | None = default_log) -> None:
        self.log: Log = log or default_log
        self.parsed_cache: dict[str, ParsedObject] = {}
        self.mime_map: dict[str, str] = {}
        self.encoding_map: dict[str, str | None] = {}
        self.html_preprocessor = HTMLPreProcessor()
        self.css_preprocessor = CSSPreProcessor()

    def guess_type(self, name: str) -> str:
        "Return the expected mimetype for the specified file name based on its extension."
        # ContainerBase has no opf_version_parsed, use the default OPF version for it
        return adjust_mime_for_epub(filename=name, opf_version=getattr(self, 'opf_version_parsed', (2, 0)))

    def decode(self, data: bytes, normalize_to_nfc: bool = True) -> str:
        """
        Automatically decode ``data`` into a ``unicode`` object.

        :param normalize_to_nfc: Normalize returned unicode to the NFC normal form as is required by both the EPUB and AZW3 formats.
        """
        html, used_encoding = decode_xml(data, normalize_to_nfc)
        if used_encoding:
            self.used_encoding = used_encoding
        return html

    def parse_xml(self, data: str | bytes) -> _Element:
        data, self.used_encoding = xml_to_unicode(data, strip_encoding_pats=True, assume_utf8=True, resolve_entities=True)
        data = unicodedata.normalize('NFC', data)
        return safe_xml_fromstring(data)

    def parse_xhtml(self, data: str | bytes, fname: str = '<string>', force_html5_parse: bool = False) -> _Element:
        if self.tweak_mode:
            return parse_html_tweak(data, log=self.log, decoder=self.decode, force_html5_parse=force_html5_parse)
        else:
            try:
                return parse_html(
                    data,
                    log=self.log,
                    decoder=self.decode,
                    preprocessor=self.html_preprocessor,
                    filename=fname,
                    non_html_file_tags={'ncx'},
                )
            except NotHTML:
                return self.parse_xml(data)

    @overload
    def parse_css(self, data: str | bytes | None, fname: str = '<string>', is_declaration: Literal[False] = False) -> CSSStyleSheet: ...
    @overload
    def parse_css(self, data: str | bytes | None, fname: str = '<string>', *, is_declaration: Literal[True]) -> CSSStyleDeclaration: ...
    @overload
    def parse_css(self, data: str | bytes | None, fname: str = '<string>', is_declaration: bool = False) -> CSSStyleSheet | CSSStyleDeclaration: ...
    def parse_css(self, data: str | bytes | None, fname: str = '<string>', is_declaration: bool = False) -> CSSStyleSheet | CSSStyleDeclaration:
        return parse_css(
            data,
            fname=fname,
            is_declaration=is_declaration,
            decode=self.decode,
            log_level=logging.WARNING,
            css_preprocessor=(None if self.tweak_mode else self.css_preprocessor),
        )


# }}}


class Container(ContainerBase):  # {{{
    """
    A container represents an open e-book as a folder full of files and an
    OPF file. There are two important concepts:

        * The root folder. This is the base of the e-book. All the e-books
          files are inside this folder or in its sub-folders.

        * Names: These are paths to the books' files relative to the root
          folder. They always contain POSIX separators and are unquoted. They
          can be thought of as canonical identifiers for files in the book.
          Most methods on the container object work with names. Names are always
          in the NFC Unicode normal form.

        * Clones: the container object supports efficient on-disk cloning, which is used to
          implement checkpoints in the e-book editor. In order to make this work, you should
          never access files on the filesystem directly. Instead, use :meth:`raw_data` or
          :meth:`open` to read/write to component files in the book.

    When converting between hrefs and names use the methods provided by this
    class, they assume all hrefs are quoted.
    """

    #: The type of book (epub for EPUB files and azw3 for AZW3 files)
    book_type = 'oeb'
    #: If this container represents an unzipped book (a directory)
    is_dir = False

    SUPPORTS_TITLEPAGES = True
    SUPPORTS_FILENAMES = True
    MAX_HTML_FILE_SIZE = 0

    #: The canonical name of the OPF file
    opf_name: str
    #: The absolute path to the folder containing the OPF file
    opf_dir: str

    @property
    def book_type_for_display(self) -> str:
        return self.book_type.upper()

    def __init__(self, rootpath: str | None = None, opfpath: str | None = None, log: Log | None = default_log, clone_data: CloneData | None = None) -> None:
        super().__init__(log=log)
        if clone_data is not None:
            self.root = clone_data['root']
        else:
            assert rootpath is not None
            self.root = os.path.abspath(rootpath)

        self.name_path_map: dict[str, str] = {}
        self.dirtied: set[str] = set()
        self.pretty_print: set[str] = set()
        self.cloned = False
        self.cache_names = ('parsed_cache', 'mime_map', 'name_path_map', 'encoding_map', 'dirtied', 'pretty_print')
        self.href_to_name_cache: dict[tuple[str | None, str | None], str | None] = {}

        if clone_data is not None:
            for x in ('cloned', 'name_path_map', 'opf_name', 'mime_map', 'pretty_print', 'encoding_map', 'tweak_mode'):
                setattr(self, x, clone_data[x])
            self.opf_dir = os.path.dirname(self.name_path_map[self.opf_name])
            return

        # Map of relative paths with '/' separators from root of unzipped ePub
        # to absolute paths on filesystem with os-specific separators
        assert opfpath is not None
        opfpath = os.path.abspath(os.path.realpath(opfpath))
        all_opf_files: list[tuple[str, str]] = []
        for dirpath, _dirnames, filenames in os.walk(self.root):
            for f in filenames:
                path = join(dirpath, f)
                name = self.abspath_to_name(path)
                self.name_path_map[name] = path
                self.mime_map[name] = guess_type(path)
                # Special case if we have stumbled onto the opf
                if path == opfpath:
                    self.opf_name = name
                    self.opf_dir = os.path.dirname(path)
                    self.mime_map[name] = guess_type('a.opf')
                if path.lower().endswith('.opf'):
                    all_opf_files.append((name, os.path.dirname(path)))

        if not hasattr(self, 'opf_name') and all_opf_files:
            self.opf_name, self.opf_dir = all_opf_files[0]
            self.mime_map[self.opf_name] = guess_type('a.opf')

        if not hasattr(self, 'opf_name'):
            raise InvalidBook(f'Could not locate opf file: {opfpath!r}')

        # Update mime map with data from the OPF
        self.refresh_mime_map()

    def refresh_mime_map(self) -> None:
        for item in self.opf_xpath('//opf:manifest/opf:item[@href and @media-type]'):
            href = item.get('href')
            try:
                name = self.href_to_name(href, self.opf_name)
            except ValueError:
                continue  # special filenames such as CON on windows cause relpath to fail
            mt = item.get('media-type')
            if name in self.mime_map and name != self.opf_name and mt:
                # some epubs include the opf in the manifest with an incorrect mime type
                self.mime_map[name] = mt

    def data_for_clone(self, dest_dir: str | None = None) -> CloneData:
        dest_dir = dest_dir or self.root
        return {
            'root': dest_dir,
            'opf_name': self.opf_name,
            'mime_map': self.mime_map.copy(),
            'pretty_print': set(self.pretty_print),
            'encoding_map': self.encoding_map.copy(),
            'tweak_mode': self.tweak_mode,
            'cloned': self.cloned,
            'name_path_map': {name: os.path.join(dest_dir, os.path.relpath(path, self.root)) for name, path in self.name_path_map.items()},
        }

    def clone_data(self, dest_dir: str) -> CloneData:
        Container.commit(self, keep_parsed=False)
        clone_dir(self.root, dest_dir)
        self.cloned = True
        return self.data_for_clone(dest_dir)

    def __getstate__(self) -> CloneData:
        Container.commit(self, keep_parsed=True)
        return self.data_for_clone()

    def __setstate__(self, state: CloneData) -> None:
        self.__init__(log=default_log, clone_data=state)

    def add_name_to_manifest(self, name: str, process_manifest_item: Callable[[_Element], object] | None = None, suggested_id: str = '') -> str:
        "Add an entry to the manifest for a file with the specified name. Returns the manifest id."
        all_ids = {x.get('id') for x in self.opf_xpath('//*[@id]')}
        c = 0
        item_id = suggested_id = suggested_id or 'id'
        while item_id in all_ids:
            c += 1
            item_id = f'{suggested_id}-{c}'
        manifest = self.opf_xpath('//opf:manifest')[0]
        href = self.name_to_href(name, self.opf_name)
        item = manifest.makeelement(OPF('item'), id=item_id, href=href)
        item.set('media-type', self.mime_map[name])
        self.insert_into_xml(manifest, item)
        if process_manifest_item is not None:
            process_manifest_item(item)
        self.dirty(self.opf_name)
        return item_id

    def manifest_has_name(self, name: str) -> bool:
        """Return True if the manifest has an entry corresponding to name"""
        all_names = {self.href_to_name(x.get('href'), self.opf_name) for x in self.opf_xpath('//opf:manifest/opf:item[@href]')}
        return name in all_names

    def make_name_unique(self, name: str) -> str:
        """Ensure that `name` does not already exist in this book. If it does, return a modified version that does not exist."""
        counter = count()
        while self.has_name_case_insensitive(name) or self.manifest_has_name(name):
            c = next(counter) + 1
            base, ext = name.rpartition('.')[::2]
            if c > 1:
                base = base.rpartition('-')[0]
            name = f'{base}-{c}.{ext}'
        return name

    def add_file(
        self,
        name: str,
        data: bytes | IO[bytes] = b'',
        media_type: str | None = None,
        spine_index: int | None = None,
        modify_name_if_needed: bool = False,
        process_manifest_item: Callable[[_Element], object] | None = None,
        suggested_id: str = '',
    ) -> str:
        """Add a file to this container. Entries for the file are
        automatically created in the OPF manifest and spine
        (if the file is a text document)"""
        if '..' in name:
            raise ValueError('Names are not allowed to have .. in them')
        href = self.name_to_href(name, self.opf_name)
        if self.has_name_case_insensitive(name) or self.manifest_has_name(name):
            if not modify_name_if_needed:
                raise ValueError(
                    (f'A file with the name {name} already exists')
                    if self.has_name_case_insensitive(name)
                    else (f'An item with the href {href} already exists in the manifest')
                )
            name = self.make_name_unique(name)
            href = self.name_to_href(name, self.opf_name)
        path = self.name_to_abspath(name)
        base = os.path.dirname(path)
        if not os.path.exists(base):
            os.makedirs(base)
        with open(path, 'wb') as f:
            if hasattr(data, 'read'):
                shutil.copyfileobj(cast('IO[bytes]', data), f)
            else:
                f.write(data)
        mt = media_type or self.guess_type(name)
        self.name_path_map[name] = path
        self.mime_map[name] = mt
        if self.ok_to_be_unmanifested(name):
            return name
        item_id = self.add_name_to_manifest(name, process_manifest_item=process_manifest_item, suggested_id=suggested_id)
        if mt in OEB_DOCS:
            manifest = self.opf_xpath('//opf:manifest')[0]
            spine = self.opf_xpath('//opf:spine')[0]
            si = manifest.makeelement(OPF('itemref'), idref=item_id)
            self.insert_into_xml(spine, si, index=spine_index)
        return name

    def rename(self, current_name: str, new_name: str) -> None:
        """Renames a file from current_name to new_name. It automatically
        rebases all links inside the file if the folder the file is in
        changes. Note however, that links are not updated in the other files
        that could reference this file. This is for performance, such updates
        should be done once, in bulk."""
        if current_name in self.names_that_must_not_be_changed:
            raise ValueError(f'Renaming of {current_name} is not allowed')
        if self.exists(new_name) and (new_name == current_name or new_name.lower() != current_name.lower()):
            # The destination exists and does not differ from the current name only by case
            raise ValueError(f'Cannot rename {current_name} to {new_name} as {new_name} already exists')
        new_path = self.name_to_abspath(new_name)
        base = os.path.dirname(new_path)
        if os.path.isfile(base):
            raise ValueError(f'Cannot rename {current_name} to {new_name} as {base} is a file')
        if not os.path.exists(base):
            os.makedirs(base)
        old_path = parent_dir = self.name_to_abspath(current_name)
        self.commit_item(current_name)
        os.rename(old_path, new_path)
        # Remove empty directories
        while parent_dir:
            parent_dir = os.path.dirname(parent_dir)
            try:
                os.rmdir(parent_dir)
            except OSError:
                break

        for x in ('mime_map', 'encoding_map'):
            x = getattr(self, x)
            if current_name in x:
                x[new_name] = x[current_name]
        self.name_path_map[new_name] = new_path
        for x in self.cache_names:
            x = getattr(self, x)
            try:
                x.pop(current_name, None)
            except TypeError:
                x.discard(current_name)
        if current_name == self.opf_name:
            self.opf_name = new_name
        if os.path.dirname(old_path) != os.path.dirname(new_path):
            from calibre.ebooks.oeb.polish.replace import LinkRebaser

            repl = LinkRebaser(self, current_name, new_name)
            self.replace_links(new_name, repl)
            self.dirty(new_name)

    def replace_links(self, name: str, replace_func: LinkReplacerType) -> bool:
        """Replace all links in name using replace_func, which must be a
        callable that accepts a URL and returns the replaced URL. It must also
        have a 'replaced' attribute that is set to True if any actual
        replacement is done. Convenient ways of creating such callables are
        using the :class:`LinkReplacer` and :class:`LinkRebaser` classes.

        In HTML files, attributes that refer to elements in the same file by
        id, such as aria-labelledby, are also replaced. Each id is passed to
        replace_func as a URL of the form #id with file_type set to 'idref'
        and is replaced only if replace_func returns a URL of the same form."""
        media_type = self.mime_map.get(name, guess_type(name))
        if name == self.opf_name:
            replace_func.file_type = 'opf'
            for elem in self.opf_xpath('//*[@href]'):
                href = elem.get('href')
                assert href is not None  # guaranteed by the XPath expression
                elem.set('href', replace_func(href))
        elif media_type.lower() in OEB_DOCS:
            replace_func.file_type = 'text'
            root = self.parsed(name)
            assert isinstance(root, etree._Element)
            rewrite_links(root, replace_func)
            replace_func.file_type = 'idref'

            def replace_idref(eid: str) -> str:
                q = replace_func('#' + eid)
                return q[1:] if q and q.startswith('#') and len(q) > 1 else eid

            rewrite_idrefs(root, replace_idref)
        elif media_type.lower() in OEB_STYLES:
            replace_func.file_type = 'style'
            replaceUrls(self.parsed(name), replace_func)
        elif media_type.lower() == guess_type('toc.ncx'):
            replace_func.file_type = 'ncx'
            root = self.parsed(name)
            assert isinstance(root, etree._Element)
            for elem in root.xpath('//*[@src]'):
                elem.set('src', replace_func(elem.get('src')))

        if replace_func.replaced:
            self.dirty(name)
        return replace_func.replaced

    @overload
    def iterlinks(self, name: str, get_line_numbers: Literal[True] = True) -> Iterator[tuple[str | None, int | None, int]]: ...
    @overload
    def iterlinks(self, name: str, get_line_numbers: Literal[False]) -> Iterator[str | None]: ...
    @overload
    def iterlinks(self, name: str, get_line_numbers: bool = True) -> Iterator[tuple[str | None, int | None, int]] | Iterator[str | None]: ...
    def iterlinks(self, name: str, get_line_numbers: bool = True) -> Iterator[tuple[str | None, int | None, int] | str | None]:
        """Iterate over all links in name. If get_line_numbers is True the
        yields results of the form (link, line_number, offset). Where
        line_number is the line_number at which the link occurs and offset is
        the number of characters from the start of the line. Note that offset
        could actually encompass several lines if not zero."""
        media_type = self.mime_map.get(name, guess_type(name))
        if name == self.opf_name:
            for elem in self.opf_xpath('//*[@href]'):
                yield (elem.get('href'), elem.sourceline, 0) if get_line_numbers else elem.get('href')
        elif media_type.lower() in OEB_DOCS:
            root = self.parsed(name)
            assert isinstance(root, etree._Element)
            for el, attr, link, pos in iterlinks(root):
                yield (link, el.sourceline, pos) if get_line_numbers else link
        elif media_type.lower() in OEB_STYLES:
            if get_line_numbers:
                with self.open(name, 'rb') as f:
                    raw = self.decode(f.read()).replace('\r\n', '\n').replace('\r', '\n')
                    position = PositionFinder(raw)
                    is_in_comment = CommentFinder(raw)
                    for link, offset in itercsslinks(raw):
                        if not is_in_comment(offset):
                            lnum, col = position(offset)
                            yield link, lnum, col
            else:
                for link in getUrls(self.parsed(name)):
                    yield link
        elif media_type.lower() == guess_type('toc.ncx'):
            root = self.parsed(name)
            assert isinstance(root, etree._Element)
            for elem in root.xpath('//*[@src]'):
                yield (elem.get('src'), elem.sourceline, 0) if get_line_numbers else elem.get('src')

    def abspath_to_name(self, fullpath: str, root: str | None = None) -> str:
        """
        Convert an absolute path to a canonical name relative to :attr:`root`

        :param root: The base folder. By default the root for this container object is used.
        """
        # OS X silently changes all file names to NFD form. The EPUB
        # spec requires all text including filenames to be in NFC form.
        # The proper fix is to implement a VFS that maps between
        # canonical names and their file system representation, however,
        # I don't have the time for that now. Note that the container
        # ensures that all text files are normalized to NFC when
        # decoding them anyway, so there should be no mismatch between
        # names in the text and NFC canonical file names.
        return unicodedata.normalize('NFC', abspath_to_name(fullpath, root or self.root))

    def name_to_abspath(self, name: str) -> str:
        "Convert a canonical name to an absolute OS dependent path"
        return name_to_abspath(name, self.root)

    def exists(self, name: str) -> bool:
        """True iff a file/folder corresponding to the canonical name exists. Note
        that this function suffers from the limitations of the underlying OS
        filesystem, in particular case (in)sensitivity. So on a case
        insensitive filesystem this will return True even if the case of name
        is different from the case of the underlying filesystem file. See also :meth:`has_name`"""
        return os.path.exists(self.name_to_abspath(name))

    def href_to_name(self, href: str | None, base: str | None = None) -> str | None:
        """
        Convert an href (relative to base) to a name. base must be a name or
        None, in which case self.root is used.
        """
        key = href, base
        try:
            return self.href_to_name_cache[key]
        except KeyError:
            ans = self.href_to_name_cache[key] = href_to_name(href, self.root, base=base)
            return ans

    def name_to_href(self, name: str, base: str | None = None) -> str:
        """Convert a name to a href relative to base, which must be a name or
        None in which case self.root is used as the base"""
        return name_to_href(name, self.root, base=base)

    def opf_xpath(self, expr: str) -> list[_Element]:
        "Convenience method to evaluate an XPath expression on the OPF file, has the opf: and dc: namespace prefixes pre-defined."
        return self.opf.xpath(expr, namespaces=OPF_NAMESPACES)

    def has_name(self, name: str | None) -> TypeGuard[str]:
        """Return True iff a file with the same canonical name as that specified exists. Unlike :meth:`exists` this method is always case-sensitive."""
        return bool(name) and name in self.name_path_map

    def has_name_and_is_not_empty(self, name: str) -> bool:
        path = self.name_path_map.get(name)
        if not path:
            return False
        try:
            if (sz := os.path.getsize(path)) == 0:
                # this can happen when the directory entry is not flushed (which happens during fast EPUB extraction), so
                # open the file and check to be sure.
                with open(path) as f:
                    sz = f.seek(0, os.SEEK_END)
            return sz > 0
        except OSError:
            return False

    def has_name_case_insensitive(self, name: str) -> bool:
        if not name:
            return False
        name = name.lower()
        return any(q.lower() == name for q in self.name_path_map)

    def relpath(self, path: str, base: str | None = None) -> str:
        """Convert an absolute path (with OS separators) to a path relative to
        base (defaults to self.root). The relative path is *not* a name. Use
        :meth:`abspath_to_name` for that."""
        return relpath(path, base or self.root)

    def ok_to_be_unmanifested(self, name: str) -> bool:
        return name in self.names_that_need_not_be_manifested

    @property
    def names_that_need_not_be_manifested(self) -> set[str]:
        "Set of names that are allowed to be missing from the manifest. Depends on the e-book file format."
        return {self.opf_name}

    @property
    def names_that_must_not_be_removed(self) -> set[str]:
        "Set of names that must never be deleted from the container. Depends on the e-book file format."
        return {self.opf_name}

    @property
    def names_that_must_not_be_changed(self) -> set[str]:
        "Set of names that must never be renamed. Depends on the e-book file format."
        return set()

    def parse(self, path: str, mime: str) -> ParsedObject:
        with open(path, 'rb') as src:
            data = src.read()
        if mime in OEB_DOCS:
            return self.parse_xhtml(data, self.relpath(path))
        elif mime[-4:] in {'+xml', '/xml'}:
            return self.parse_xml(data)
        elif mime in OEB_STYLES:
            return self.parse_css(data, self.relpath(path))
        return data

    @overload
    def raw_data(self, name: str, decode: Literal[False], normalize_to_nfc: bool = True) -> bytes: ...
    @overload
    def raw_data(self, name: str, decode: bool = True, normalize_to_nfc: bool = True) -> str | bytes: ...
    def raw_data(self, name: str, decode: bool = True, normalize_to_nfc: bool = True) -> str | bytes:
        """
        Return the raw data corresponding to the file specified by name

        :param decode: If True and the file has a text based MIME type, decode it and return a unicode object instead of raw bytes.
        :param normalize_to_nfc: If True the returned unicode object is normalized to the NFC normal form as is required for the EPUB and AZW3 file formats.
        """
        with self.open(name) as nf:
            ans = nf.read()
        mime = self.mime_map.get(name, guess_type(name))
        if decode and (mime in OEB_STYLES or mime in OEB_DOCS or mime == 'text/plain' or mime[-4:] in {'+xml', '/xml'}):
            return self.decode(ans, normalize_to_nfc=normalize_to_nfc)
        return ans

    def parsed(self, name: str) -> ParsedObject:
        """Return a parsed representation of the file specified by name. For
        HTML and XML files an lxml tree is returned. For CSS files a css_parser
        stylesheet is returned. Note that parsed objects are cached for
        performance. If you make any changes to the parsed object, you must
        call :meth:`dirty` so that the container knows to update the cache. See also :meth:`replace`."""
        ans = self.parsed_cache.get(name, None)
        if ans is None:
            self.used_encoding = None
            mime = self.mime_map.get(name, guess_type(name))
            ans = self.parse(self.name_path_map[name], mime)
            self.parsed_cache[name] = ans
            self.encoding_map[name] = self.used_encoding
        return ans

    def replace(self, name: str, obj: ParsedObject) -> None:
        """
        Replace the parsed object corresponding to name with obj, which must be
        a similar object, i.e. an lxml tree for HTML/XML or a css_parser
        stylesheet for a CSS file.
        """
        self.parsed_cache[name] = obj
        self.dirty(name)

    @property
    def opf(self) -> _Element:
        "The parsed OPF file"
        ans = self.parsed(self.opf_name)
        assert isinstance(ans, etree._Element)
        return ans

    @property
    def mi(self) -> Metadata:
        """The metadata of this book as a Metadata object. Note that this
        object is constructed on the fly every time this property is requested,
        so use it sparingly."""
        from calibre.ebooks.metadata.opf2 import OPF as O

        mi = self.serialize_item(self.opf_name)
        return O(BytesIO(mi), basedir=self.opf_dir, unquote_urls=False, populate_spine=False).to_book_metadata()

    @property
    def opf_version(self) -> str:
        "The version set on the OPF's <package> element"
        try:
            # use xpath() directly as this is an attribute query, which returns strings not elements
            return self.opf.xpath('//opf:package/@version', namespaces=OPF_NAMESPACES)[0]
        except IndexError:
            return ''

    @property
    def opf_version_parsed(self) -> OPFVersion:
        "The version set on the OPF's <package> element as a tuple of integers"
        return parse_opf_version(self.opf_version)

    @property
    def manifest_items(self) -> list[_Element]:
        return self.opf_xpath('//opf:manifest/opf:item[@href and @id]')

    @property
    def manifest_id_map(self) -> dict[str, str | None]:
        "Mapping of manifest id to canonical names"
        # manifest_items only contains items that have an id
        return {cast('str', item.get('id')): self.href_to_name(item.get('href'), self.opf_name) for item in self.manifest_items}

    @property
    def manifest_type_map(self) -> dict[str, tuple[str | None, ...]]:
        "Mapping of manifest media-type to list of canonical names of that media-type"
        ans: defaultdict[str, list[str | None]] = defaultdict(list)
        for item in self.opf_xpath('//opf:manifest/opf:item[@href and @media-type]'):
            ans[cast('str', item.get('media-type')).lower()].append(  # guaranteed by the XPath expression
                self.href_to_name(item.get('href'), self.opf_name)
            )
        return {mt: tuple(v) for mt, v in ans.items()}

    def manifest_items_with_property(self, property_name: str) -> Iterator[str | None]:
        "All manifest items that have the specified property"
        prefixes = read_prefixes(self.opf)
        for item in items_with_property(self.opf, property_name, prefixes):
            href = item.get('href')
            if href:
                yield self.href_to_name(item.get('href'), self.opf_name)

    def manifest_items_of_type(self, predicate: str | AbstractContainer[str] | Callable[[str], bool]) -> Iterator[str | None]:
        """The names of all manifest items whose media-type matches predicate.
        `predicate` can be a set, a list, a string or a function taking a single
        argument, which will be called with the media-type."""
        pred: Callable[[str], bool]
        if isinstance(predicate, str):
            pred = predicate.__eq__
        elif hasattr(predicate, '__contains__'):
            pred = cast('AbstractContainer[str]', predicate).__contains__
        else:
            pred = cast('Callable[[str], bool]', predicate)
        for mt, names in self.manifest_type_map.items():
            if pred(mt):
                yield from names

    def apply_unique_properties(self, name: str | None, *properties: str) -> tuple[list[str | None], list[str | None]]:
        """Ensure that the specified properties are set on only the manifest item
        identified by name. You can pass None as the name to remove the
        property from all items."""
        uproperties = frozenset(properties)
        removed_names: list[str | None] = []
        added_names: list[str | None] = []
        for p in uproperties:
            if p.startswith('calibre:'):
                ensure_prefix(self.opf, None, 'calibre', CALIBRE_PREFIX)
                break

        for item in self.opf_xpath('//opf:manifest/opf:item'):
            iname = self.href_to_name(item.get('href'), self.opf_name)
            # the cast is needed as ty infers list[LiteralString] for ''.split()
            props = cast('list[str]', (item.get('properties') or '').split())
            lprops = {p.lower() for p in props}
            for prop in uproperties:
                if prop.lower() in lprops:
                    if name != iname:
                        removed_names.append(iname)
                        props = [p for p in props if p.lower() != prop]
                        if props:
                            item.set('properties', ' '.join(props))
                        else:
                            del item.attrib['properties']
                elif name == iname:
                    added_names.append(iname)
                    props.append(prop)
                    item.set('properties', ' '.join(props))
        self.dirty(self.opf_name)
        return removed_names, added_names

    def add_properties(self, name: str, *properties: str) -> bool:
        """Add the specified properties to the manifest item identified by name."""
        uproperties = frozenset(properties)
        if not uproperties:
            return True
        for p in uproperties:
            if p.startswith('calibre:'):
                ensure_prefix(self.opf, None, 'calibre', CALIBRE_PREFIX)
                break
        for item in self.opf_xpath('//opf:manifest/opf:item'):
            iname = self.href_to_name(item.get('href'), self.opf_name)
            if name == iname:
                props = frozenset((item.get('properties') or '').split()) | uproperties
                item.set('properties', ' '.join(props))
                return True
        return False

    @property
    def guide_type_map(self) -> dict[str, str | None]:
        "Mapping of guide type to canonical name"
        return {
            item.get('type', ''): self.href_to_name(item.get('href'), self.opf_name) for item in self.opf_xpath('//opf:guide/opf:reference[@href and @type]')
        }

    @property
    def spine_iter(self) -> Iterator[tuple[_Element, str, bool]]:
        """An iterator that yields item, name is_linear for every item in the
        books' spine. item is the lxml element, name is the canonical file name
        and is_linear is True if the item is linear. See also: :attr:`spine_names` and :attr:`spine_items`."""
        manifest_id_map = self.manifest_id_map
        non_linear = []
        for item in self.opf_xpath('//opf:spine/opf:itemref[@idref]'):
            idref = item.get('idref')
            name = manifest_id_map.get(idref, None) if idref is not None else None
            path = self.name_path_map.get(name, None) if name is not None else None
            if path and name is not None:
                if item.get('linear', 'yes') == 'yes':
                    yield item, name, True
                else:
                    non_linear.append((item, name))
        for item, name in non_linear:
            yield item, name, False

    def index_in_spine(self, name: str) -> int | None:
        manifest_id_map = self.manifest_id_map
        for i, item in enumerate(self.opf_xpath('//opf:spine/opf:itemref[@idref]')):
            idref = item.get('idref')
            q = manifest_id_map.get(idref, None)
            if q == name:
                return i

    @property
    def spine_names(self) -> Iterator[tuple[str, bool]]:
        """An iterator yielding name and is_linear for every item in the
        books' spine. See also: :attr:`spine_iter` and :attr:`spine_items`."""
        for item, name, linear in self.spine_iter:
            yield name, linear

    @property
    def spine_items(self) -> Iterator[str]:
        """An iterator yielding the path for every item in the
        books' spine. See also: :attr:`spine_iter` and :attr:`spine_items`."""
        for name, linear in self.spine_names:
            yield self.name_path_map[name]

    def remove_from_spine(self, spine_items: Iterable[tuple[str, bool]], remove_if_no_longer_in_spine: bool = True) -> None:
        """
        Remove the specified items (by canonical name) from the spine. If ``remove_if_no_longer_in_spine``
        is True, the items are also deleted from the book, not just from the spine.
        """
        nixed: set[str] = set()
        for (name, remove), (item, xname, linear) in zip(spine_items, self.spine_iter):
            if remove and name == xname:
                self.remove_from_xml(item)
                nixed.add(name)
        if remove_if_no_longer_in_spine:
            # Remove from the book if no longer in spine
            nixed -= {name for name, linear in self.spine_names}
            for name in nixed:
                self.remove_item(name)

    def set_spine(self, spine_items: Iterable[tuple[str, bool]]) -> None:
        """Set the spine to be spine_items where spine_items is an iterable of
        the form (name, linear). Will raise an error if one of the names is not
        present in the manifest."""
        imap = self.manifest_id_map
        imap = {name: item_id for item_id, name in imap.items()}
        items = [item for item, name, linear in self.spine_iter]
        tail, last_tail = (items[0].tail, items[-1].tail) if items else ('\n    ', '\n  ')
        for i in items:
            self.remove_from_xml(i)
        spine = self.opf_xpath('//opf:spine')[0]
        spine.text = tail
        for name, linear in spine_items:
            i = spine.makeelement('{{{}}}itemref'.format(OPF_NAMESPACES['opf']), nsmap={'opf': OPF_NAMESPACES['opf']})
            i.tail = tail
            i.set('idref', imap[name])
            spine.append(i)
            if not linear:
                i.set('linear', 'no')
        if len(spine) > 0:
            spine[-1].tail = last_tail
        self.dirty(self.opf_name)

    def remove_item(self, name: str, remove_from_guide: bool = True) -> None:
        """
        Remove the item identified by name from this container. This removes all
        references to the item in the OPF manifest, guide and spine as well as from
        any internal caches.
        """
        removed: set[str] = set()
        for elem in self.opf_xpath('//opf:manifest/opf:item[@href]'):
            if self.href_to_name(elem.get('href'), self.opf_name) == name:
                id_ = elem.get('id', None)
                if id_ is not None:
                    removed.add(id_)
                self.remove_from_xml(elem)
                self.dirty(self.opf_name)
        if removed:
            for spine in self.opf_xpath('//opf:spine'):
                tocref = spine.attrib.get('toc', None)
                if tocref and tocref in removed:
                    spine.attrib.pop('toc', None)
                    self.dirty(self.opf_name)

            for item in self.opf_xpath('//opf:spine/opf:itemref[@idref]'):
                idref = item.get('idref')
                if idref in removed:
                    self.remove_from_xml(item)
                    self.dirty(self.opf_name)

            for meta in self.opf_xpath('//opf:meta[@name="cover" and @content]'):
                if meta.get('content') in removed:
                    self.remove_from_xml(meta)
                    self.dirty(self.opf_name)

            for meta in self.opf_xpath('//opf:meta[@refines]'):
                q = meta.get('refines')
                assert q is not None  # guaranteed by the XPath expression
                if q.startswith('#') and q[1:] in removed:
                    self.remove_from_xml(meta)
                    self.dirty(self.opf_name)

        if remove_from_guide:
            for item in self.opf_xpath('//opf:guide/opf:reference[@href]'):
                if self.href_to_name(item.get('href'), self.opf_name) == name:
                    self.remove_from_xml(item)
                    self.dirty(self.opf_name)

        path = self.name_path_map.pop(name, None)
        if path and os.path.exists(path):
            os.remove(path)
        self.mime_map.pop(name, None)
        self.parsed_cache.pop(name, None)
        self.dirtied.discard(name)

    def set_media_overlay_durations(self, duration_map: dict[str, float] | None = None) -> None:
        self.dirty(self.opf_name)
        for meta in self.opf_xpath('//opf:meta[@property="media:duration"]'):
            self.remove_from_xml(meta)
        metadata = self.opf_xpath('//opf:metadata')[0]
        total_duration = 0.0
        for item_id, duration in (duration_map or {}).items():
            meta = metadata.makeelement(OPF('meta'), property='media:duration', refines='#' + item_id)
            meta.text = seconds_to_timestamp(duration)
            self.insert_into_xml(metadata, meta)
            total_duration += duration
        if duration_map:
            meta = metadata.makeelement(OPF('meta'), property='media:duration')
            meta.text = seconds_to_timestamp(total_duration)
            self.insert_into_xml(metadata, meta)

    def dirty(self, name: str) -> None:
        """Mark the parsed object corresponding to name as dirty. See also: :meth:`parsed`."""
        self.dirtied.add(name)

    def remove_from_xml(self, item: _Element) -> _Element:
        "Removes item from parent, fixing indentation (works only with self closing items)"
        parent = cast('_Element', item.getparent())  # item must be in a tree
        idx = parent.index(item)
        if idx == 0:
            # We are removing the first item - only care about adjusting
            # the tail if this was the only child
            if len(parent) == 1:
                parent.text = item.tail
        else:
            # Make sure the preceding item has this tail
            parent[idx - 1].tail = item.tail
        parent.remove(item)
        return item

    def insert_into_xml(self, parent: _Element, item: _Element, index: int | None = None) -> None:
        """Insert item into parent (or append if index is None), fixing
        indentation. Only works with self closing items."""
        insert_self_closing(parent, item, index)

    def opf_get_or_create(self, name: str) -> _Element:
        """Convenience method to either return the first XML element with the
        specified name or create it under the opf:package element and then
        return it, if it does not already exist."""
        ans = self.opf_xpath('//opf:' + name)
        if ans:
            return ans[0]
        self.dirty(self.opf_name)
        package = self.opf_xpath('//opf:package')[0]
        item = package.makeelement(OPF(name))
        item.tail = '\n'
        package.append(item)
        return item

    def generate_item(self, name: str, id_prefix: str | None = None, media_type: str | None = None, unique_href: bool = True) -> _Element:
        """Add an item to the manifest with href derived from the given
        name. Ensures uniqueness of href and id automatically. Returns
        generated item."""
        id_prefix = id_prefix or 'id'
        media_type = media_type or self.guess_type(name)
        if unique_href:
            name = self.make_name_unique(name)
        href = self.name_to_href(name, self.opf_name)
        base, ext = href.rpartition('.')[0::2]
        all_ids = {x.get('id') for x in self.opf_xpath('//*[@id]')}
        if id_prefix.endswith('-'):
            all_ids.add(id_prefix)
        c = 0
        item_id = id_prefix
        while item_id in all_ids:
            c += 1
            item_id = f'{id_prefix}{c}'

        manifest = self.opf_xpath('//opf:manifest')[0]
        item = manifest.makeelement(OPF('item'), id=item_id, href=href)
        item.set('media-type', media_type)
        self.insert_into_xml(manifest, item)
        self.dirty(self.opf_name)
        # href was created from a valid name so it always maps back to a name
        name = cast('str', self.href_to_name(href, self.opf_name))
        self.name_path_map[name] = path = self.name_to_abspath(name)
        self.mime_map[name] = media_type
        # Ensure that the file corresponding to the newly created item exists
        # otherwise cloned containers will fail when they try to get the number
        # of links to the file
        base = os.path.dirname(path)
        if not os.path.exists(base):
            os.makedirs(base)
        open(path, 'wb').close()
        return item

    def format_opf(self) -> None:
        try:
            mdata = self.opf_xpath('//opf:metadata')[0]
        except IndexError:
            pass
        else:
            mdata.text = '\n    '
            remove = set()
            for child in mdata:
                child.tail = '\n    '
                try:
                    if child.get('name', '').startswith('calibre:') and child.get('content', '').strip() in {'{}', ''}:
                        remove.add(child)
                except AttributeError:
                    continue  # Happens for XML comments
            for child in remove:
                mdata.remove(child)
            if len(mdata) > 0:
                mdata[-1].tail = '\n  '
        # Ensure name comes before content, needed for Nooks
        for meta in self.opf_xpath('//opf:meta[@name="cover"]'):
            if 'content' in meta.attrib:
                meta.set('content', meta.attrib.pop('content'))

    def serialize_item(self, name: str) -> bytes:
        """Convert a parsed object (identified by canonical name) into a bytestring. See :meth:`parsed`."""
        data = root = self.parsed(name)
        if name == self.opf_name:
            self.format_opf()
        data = serialize(data, self.mime_map[name], pretty_print=name in self.pretty_print)
        if name == self.opf_name and isinstance(root, etree._Element) and root.nsmap.get(None) == OPF2_NS:
            # Needed as I can't get lxml to output opf:role and
            # not output <opf:metadata> as well
            data = re.sub(rb'(<[/]{0,1})opf:', rb'\1', data)
        return data

    def commit_item(self, name: str, keep_parsed: bool = False) -> None:
        """Commit a parsed object to disk (it is serialized and written to the
        underlying file). If ``keep_parsed`` is True the parsed representation
        is retained in the cache. See also: :meth:`parsed`"""
        if name not in self.parsed_cache:
            return
        data = self.serialize_item(name)
        self.dirtied.discard(name)
        if not keep_parsed:
            self.parsed_cache.pop(name)
        dest = self.name_path_map[name]
        if self.cloned and nlinks_file(dest) > 1:
            # Decouple this file from its links
            os.unlink(dest)
        with open(dest, 'wb') as f:
            f.write(data)

    def filesize(self, name: str) -> int:
        """Return the size in bytes of the file represented by the specified
        canonical name. Automatically handles dirtied parsed objects. See also:
        :meth:`parsed`"""
        if name in self.dirtied:
            self.commit_item(name, keep_parsed=True)
        path = self.name_to_abspath(name)
        return os.path.getsize(path)

    def get_file_path_for_processing(self, name: str, allow_modification: bool = True) -> str:
        """Similar to open() except that it returns a file path, instead of an open file object."""
        if name in self.dirtied:
            self.commit_item(name)
        self.parsed_cache.pop(name, False)
        path = self.name_to_abspath(name)
        base = os.path.dirname(path)
        if not os.path.exists(base):
            os.makedirs(base)
        elif self.cloned and allow_modification and os.path.exists(path) and nlinks_file(path) > 1:
            # Decouple this file from its links
            temp = path + 'xxx'
            shutil.copyfile(path, temp)
            if iswindows:
                retry_on_fail(os.unlink, path)
            else:
                os.unlink(path)
            os.rename(temp, path)
        return path

    def open(self, name: str, mode: str = 'rb') -> IO[bytes]:
        """Open the file pointed to by name for direct read/write. Note that
        this will commit the file if it is dirtied and remove it from the parse
        cache. You must finish with this file before accessing the parsed
        version of it again, or bad things will happen."""
        return open(make_long_path_useable(self.get_file_path_for_processing(name, mode not in {'r', 'rb'})), mode)

    def commit(self, outpath: str | None = None, keep_parsed: bool = False) -> None:
        """
        Commit all dirtied parsed objects to the filesystem and write out the e-book file at outpath.

        :param output: The path to write the saved e-book file to. If None, the path of the original book file is used.
        :param keep_parsed: If True the parsed representations of committed items are kept in the cache.
        """
        for name in tuple(self.dirtied):
            self.commit_item(name, keep_parsed=keep_parsed)

    def compare_to(self, other: Container) -> str:
        if set(self.name_path_map) != set(other.name_path_map):
            return 'Set of files is not the same'
        mismatches = []
        for name, path in self.name_path_map.items():
            opath = other.name_path_map[name]
            with open(path, 'rb') as f1, open(opath, 'rb') as f2:
                if f1.read() != f2.read():
                    mismatches.append(f'The file {name} is not the same')
        return '\n'.join(mismatches)


# }}}

# EPUB {{{


class InvalidEpub(InvalidBook):
    pass


class ObfuscationKeyMissing(InvalidEpub):
    pass


OCF_NS = 'urn:oasis:names:tc:opendocument:xmlns:container'
VCS_IGNORE_FILES = frozenset('.gitignore .hgignore .agignore .bzrignore'.split())
VCS_DIRS = frozenset(('.git', '.hg', '.svn', '.bzr'))


def walk_dir(basedir: str) -> Iterator[tuple[bool, str, str | None]]:
    for dirpath, dirnames, filenames in os.walk(basedir):
        for vcsdir in VCS_DIRS:
            try:
                dirnames.remove(vcsdir)
            except Exception:
                pass
        is_root = os.path.abspath(os.path.normcase(dirpath)) == os.path.abspath(os.path.normcase(basedir))
        yield is_root, dirpath, None
        for fname in filenames:
            if fname not in VCS_IGNORE_FILES:
                yield is_root, dirpath, fname


class EpubContainer(Container):
    book_type = 'epub'
    MAX_HTML_FILE_SIZE = 260 * 1024

    @property
    def book_type_for_display(self) -> str:
        ans = self.book_type.upper()
        try:
            v = self.opf_version_parsed
        except Exception:
            pass
        else:
            try:
                if v.major == 2:
                    ans += ' 2'
                elif not v.minor:
                    ans += f' {v.major}'
                else:
                    ans += f' {v.major}.{v.minor}'
            except Exception:
                pass
        return ans

    META_INF = {
        'container.xml': True,
        'manifest.xml': False,
        'encryption.xml': False,
        'metadata.xml': False,
        'signatures.xml': False,
        'rights.xml': False,
    }

    pathtoepub: str
    obfuscated_fonts: dict[str, tuple[str, bytes]]

    def __init__(self, pathtoepub: str | None = None, log: Log | None = default_log, clone_data: CloneData | None = None, tdir: str | None = None) -> None:
        if clone_data is not None:
            super().__init__(log=log, clone_data=clone_data)
            for x in ('pathtoepub', 'obfuscated_fonts', 'is_dir'):
                setattr(self, x, clone_data[x])
            return

        assert pathtoepub is not None
        self.pathtoepub = pathtoepub
        if tdir is None:
            tdir = PersistentTemporaryDirectory('_epub_container')
        tdir = os.path.abspath(os.path.realpath(tdir))
        self.root = tdir
        self.is_dir = os.path.isdir(pathtoepub)
        if self.is_dir:
            for is_root, dirpath, fname in walk_dir(self.pathtoepub):
                if is_root:
                    base = tdir
                else:
                    base = os.path.join(tdir, os.path.relpath(dirpath, self.pathtoepub))
                    if fname is None:
                        os.mkdir(base)
                if fname is not None:
                    shutil.copy(os.path.join(dirpath, fname), os.path.join(base, fname))
        else:
            with open(self.pathtoepub, 'rb') as stream:
                try:
                    zf = ZipFile(stream)
                    zf.extractall(tdir)
                except Exception:
                    if log is not None:
                        log.exception('EPUB appears to be invalid ZIP file, trying a more forgiving ZIP parser')
                    from calibre.utils.localunzip import extractall

                    stream.seek(0)
                    extractall(stream, path=tdir)
        try:
            os.remove(join(tdir, 'mimetype'))
        except OSError:
            pass
        # Ensure all filenames are in NFC normalized form
        # has no effect on HFS+ filesystems as they always store filenames
        # in NFD form
        for filename in walk(self.root):
            n = unicodedata.normalize('NFC', filename)
            if n != filename:
                s = filename + 'suff1x'
                os.rename(filename, s)
                os.rename(s, n)

        container_path = join(self.root, 'META-INF', 'container.xml')
        if not exists(container_path):
            raise InvalidEpub('No META-INF/container.xml in epub')
        with open(container_path, 'rb') as cf:
            container = safe_xml_fromstring(cf.read())
        opf_files = container.xpath(
            (
                r'child::ocf:rootfiles/ocf:rootfile'
                '[@media-type="{}" and @full-path]'.format(guess_type('a.opf'))
            ),
            namespaces={'ocf': OCF_NS},
        )
        if not opf_files:
            raise InvalidEpub('META-INF/container.xml contains no link to OPF file')
        opf_path = os.path.join(self.root, *(urlunquote(opf_files[0].get('full-path')).split('/')))
        if not exists(opf_path):
            raise InvalidEpub('OPF file does not exist at location pointed to by META-INF/container.xml')

        super().__init__(rootpath=tdir, opfpath=opf_path, log=log)

        self.obfuscated_fonts = {}
        if 'META-INF/encryption.xml' in self.name_path_map:
            self.process_encryption()
        self.parsed_cache['META-INF/container.xml'] = container

    def data_for_clone(self, dest_dir: str | None = None) -> CloneData:
        ans = super().data_for_clone(dest_dir)
        ans['pathtoepub'] = self.pathtoepub
        ans['obfuscated_fonts'] = self.obfuscated_fonts.copy()
        ans['is_dir'] = self.is_dir
        return ans

    def rename(self, current_name: str, new_name: str) -> None:
        is_opf = current_name == self.opf_name
        super().rename(current_name, new_name)
        if is_opf:
            croot = self.parsed('META-INF/container.xml')
            assert isinstance(croot, etree._Element)
            for elem in croot.xpath(
                (
                    r'child::ocf:rootfiles/ocf:rootfile'
                    '[@media-type="{}" and @full-path]'.format(guess_type('a.opf'))
                ),
                namespaces={'ocf': OCF_NS},
            ):
                # The asinine epubcheck cannot handle quoted filenames in
                # container.xml
                elem.set('full-path', self.opf_name)
            self.dirty('META-INF/container.xml')
        if current_name in self.obfuscated_fonts:
            self.obfuscated_fonts[new_name] = self.obfuscated_fonts.pop(current_name)
            enc = self.parsed('META-INF/encryption.xml')
            assert isinstance(enc, etree._Element)
            for cr in enc.xpath('//*[local-name()="CipherReference" and @URI]'):
                if self.href_to_name(cr.get('URI')) == current_name:
                    cr.set('URI', self.name_to_href(new_name))
                    self.dirty('META-INF/encryption.xml')

    @property
    def names_that_need_not_be_manifested(self) -> set[str]:
        return super().names_that_need_not_be_manifested | {'META-INF/' + x for x in self.META_INF}

    def ok_to_be_unmanifested(self, name: str) -> bool:
        return name in self.names_that_need_not_be_manifested or name.startswith('META-INF/')

    @property
    def names_that_must_not_be_removed(self) -> set[str]:
        return super().names_that_must_not_be_removed | {'META-INF/container.xml'}

    @property
    def names_that_must_not_be_changed(self) -> set[str]:
        return super().names_that_must_not_be_changed | {'META-INF/' + x for x in self.META_INF}

    def remove_item(self, name: str, remove_from_guide: bool = True) -> None:
        # Handle removal of obfuscated fonts
        if name == 'META-INF/encryption.xml':
            self.obfuscated_fonts.clear()
        if name in self.obfuscated_fonts:
            self.obfuscated_fonts.pop(name, None)
            enc = self.parsed('META-INF/encryption.xml')
            assert isinstance(enc, etree._Element)
            for em in enc.xpath('//*[local-name()="EncryptionMethod" and @Algorithm]'):
                alg = em.get('Algorithm')
                if alg not in {ADOBE_OBFUSCATION, IDPF_OBFUSCATION}:
                    continue
                try:
                    cr = em.getparent().xpath('descendant::*[local-name()="CipherReference" and @URI]')[0]
                except IndexError, ValueError, KeyError:
                    continue
                if name == self.href_to_name(cr.get('URI')):
                    self.remove_from_xml(em.getparent())
                    self.dirty('META-INF/encryption.xml')
        super().remove_item(name, remove_from_guide=remove_from_guide)

    def read_raw_unique_identifier(self) -> tuple[str | None, str | None, bytes | None]:
        package_id: str | None = None
        raw_unique_identifier: str | None = None
        idpf_key: bytes | None = None
        for attrib, val in self.opf.attrib.items():
            if attrib.endswith('unique-identifier'):
                package_id = val
                break
        if package_id is not None:
            for elem in self.opf_xpath(f'//*[@id={escape_xpath_attr(package_id)}]'):
                if elem.text:
                    raw_unique_identifier = elem.text
                    break
        if raw_unique_identifier is not None:
            idpf_key_text = re.sub(r'[ \t\r\n]', '', raw_unique_identifier)
            idpf_key = hashlib.sha1(idpf_key_text.encode('utf-8')).digest()
        return package_id, raw_unique_identifier, idpf_key

    def iter_encryption_entries(self) -> Iterator[tuple[_Element, _Element | None]]:
        if 'META-INF/encryption.xml' in self.name_path_map:
            enc = self.parsed('META-INF/encryption.xml')
            assert isinstance(enc, etree._Element)
            for em in enc.xpath('//*[local-name()="EncryptionMethod" and @Algorithm]'):
                try:
                    cr = em.getparent().xpath('descendant::*[local-name()="CipherReference" and @URI]')[0]
                except Exception:
                    cr = None
                yield em, cr

    def process_encryption(self) -> None:
        fonts: dict[str, str] = {}
        for em, cr in self.iter_encryption_entries():
            alg = em.get('Algorithm')
            if alg not in {ADOBE_OBFUSCATION, IDPF_OBFUSCATION}:
                raise DRMError()
            if cr is None:
                continue
            name = self.href_to_name(cr.get('URI'))
            path = self.name_path_map.get(name, None) if name is not None else None
            if path is not None and name is not None:
                fonts[name] = alg

        package_id, raw_unique_identifier, idpf_key = self.read_raw_unique_identifier()
        key = None
        for item in self.opf_xpath('//*[local-name()="metadata"]/*[local-name()="identifier"]'):
            scheme = None
            for xkey in item.attrib.keys():
                if xkey.endswith('scheme'):
                    scheme = item.get(xkey)
            if (scheme and scheme.lower() == 'uuid') or (item.text and item.text.startswith('urn:uuid:')):
                try:
                    key = item.text.rpartition(':')[-1]  # ty: ignore[unresolved-attribute] a None text is handled by the except clause
                    key = uuid.UUID(key).bytes
                except Exception:
                    if self.log is not None:
                        self.log.exception('Failed to parse obfuscation key')
                    key = None

        for font, alg in fonts.items():
            tkey = key if alg == ADOBE_OBFUSCATION else idpf_key
            if not tkey:
                raise ObfuscationKeyMissing('Failed to find obfuscation key')
            raw = self.raw_data(font, decode=False)
            raw = decrypt_font_data(tkey, raw, alg)
            with self.open(font, 'wb') as f:
                f.write(raw)
            self.obfuscated_fonts[font] = (alg, tkey)

    def update_modified_timestamp(self) -> None:
        from calibre.ebooks.metadata.opf3 import set_last_modified_in_opf

        set_last_modified_in_opf(self.opf)
        self.dirty(self.opf_name)

    def commit(self, outpath: str | None = None, keep_parsed: bool = False) -> None:
        if self.opf_version_parsed.major == 3:
            self.update_modified_timestamp()
        super().commit(keep_parsed=keep_parsed)
        container_path = join(self.root, 'META-INF', 'container.xml')
        if not exists(container_path):
            raise InvalidEpub(
                'No META-INF/container.xml in EPUB, this typically happens if the temporary files calibre'
                ' is using are deleted by some other program while calibre is running'
            )
        restore_fonts: dict[str, bytes] = {}
        for name in self.obfuscated_fonts:
            if name not in self.name_path_map:
                continue
            alg, key = self.obfuscated_fonts[name]
            # Decrypting and encrypting are the same operation (XOR with key)
            restore_fonts[name] = data = self.raw_data(name, decode=False)
            with self.open(name, 'wb') as f:
                f.write(decrypt_font_data(key, data, alg))
        if outpath is None:
            outpath = self.pathtoepub
        assert outpath is not None
        self.commit_epub(outpath)
        for name, data in restore_fonts.items():
            with self.open(name, 'wb') as f:
                f.write(data)

    def commit_epub(self, outpath: str) -> None:
        if self.is_dir:
            assert self.pathtoepub is not None
            # First remove items from the source dir that do not exist any more
            for is_root, dirpath, fname in walk_dir(self.pathtoepub):
                if fname is not None:
                    if is_root and fname == 'mimetype':
                        continue
                    base = self.root if is_root else os.path.join(self.root, os.path.relpath(dirpath, self.pathtoepub))
                    fpath = os.path.join(base, fname)
                    if not os.path.exists(fpath):
                        os.remove(os.path.join(dirpath, fname))
                        try:
                            os.rmdir(dirpath)
                        except OSError as err:
                            if err.errno != errno.ENOTEMPTY:
                                raise
            # Now copy over everything from root to source dir
            for dirpath, dirnames, filenames in os.walk(self.root):
                is_root = os.path.abspath(os.path.normcase(dirpath)) == os.path.abspath(os.path.normcase(self.root))
                base = self.pathtoepub if is_root else os.path.join(self.pathtoepub, os.path.relpath(dirpath, self.root))
                try:
                    os.mkdir(base)
                except OSError as err:
                    if err.errno != errno.EEXIST:
                        raise
                for fname in filenames:
                    with open(os.path.join(dirpath, fname), 'rb') as src, open(os.path.join(base, fname), 'wb') as dest:
                        shutil.copyfileobj(src, dest)

        else:
            from calibre.ebooks.tweak import zip_rebuilder

            with open(join(self.root, 'mimetype'), 'wb') as f:
                et = guess_type('a.epub')
                if not isinstance(et, bytes):
                    et = et.encode('ascii')
                f.write(et)
            zip_rebuilder(self.root, outpath)

    @property
    def path_to_ebook(self) -> str:
        return self.pathtoepub

    @path_to_ebook.setter
    def path_to_ebook(self, val: str) -> None:
        self.pathtoepub = val


# }}}


class KEPUBContainer(EpubContainer):
    book_type = 'kepub'
    MAX_HTML_FILE_SIZE = 512 * 1024

    def __init__(self, pathtokepub: str | None = None, log: Log | None = default_log, clone_data: CloneData | None = None, tdir: str | None = None) -> None:
        super().__init__(pathtokepub, log=log, clone_data=clone_data, tdir=tdir)
        from calibre.ebooks.oeb.polish.kepubify import unkepubify_container

        Container.commit(self, keep_parsed=True)
        unkepubify_container(self)

    def commit_epub(self, outpath: str) -> None:
        if self.is_dir:
            return super().commit_epub(outpath)
        from calibre.ebooks.oeb.polish.kepubify import Options, kepubify_container

        with TemporaryDirectory() as tdir:
            container = clone_container(self, tdir, container_class=EpubContainer)
            kepubify_container(container, Options())
            container.commit(outpath)


# AZW3 {{{


class InvalidMobi(InvalidBook):
    pass


def do_explode(path: str, dest: str) -> tuple[str, list[str]]:
    from calibre.ebooks.mobi.reader.mobi6 import MobiReader
    from calibre.ebooks.mobi.reader.mobi8 import Mobi8Reader

    with open(path, 'rb') as stream:
        mr = MobiReader(stream, default_log, None, None)

        with CurrentDir(dest):
            mr = Mobi8Reader(mr, default_log, for_tweak=True)
            opf = os.path.abspath(mr())
            obfuscated_fonts = mr.encrypted_fonts

    return opf, obfuscated_fonts


def opf_to_azw3(opf: str, outpath: str, container: Container) -> None:
    from calibre.ebooks.conversion.plumber import Plumber, create_oebbook
    from calibre.ebooks.mobi.tweak import set_cover

    class Item(Manifest.Item):
        def _parse_css(self, data: str | bytes) -> CSSStyleSheet:
            # The default CSS parser used by oeb.base inserts the h namespace
            # and resolves all @import rules. We don't want that.
            return container.parse_css(data)

    def specialize(oeb: OEBBook) -> None:
        oeb.manifest.Item = Item  # ty: ignore[invalid-assignment] Manifest.Item is designed to be overridden per instance

    plumber = Plumber(opf, outpath, container.log)
    plumber.setup_options()
    inp = plugin_for_input_format('azw3')
    assert inp is not None
    outp = plugin_for_output_format('azw3')
    assert outp is not None
    plumber.opts.mobi_passthrough = True
    plumber.opts.keep_ligatures = True
    oeb = create_oebbook(container.log, opf, plumber.opts, specialize=specialize)
    set_cover(oeb)
    outp.convert(oeb, outpath, inp, plumber.opts, container.log)


def epub_to_azw3(epub: str, outpath: str | None = None) -> None:
    container = get_container(epub, tweak_mode=True)
    changed = False
    for item in container.opf_xpath('//opf:manifest/opf:item[@properties and @href]'):
        properties, href = item.get('properties'), item.get('href')
        assert properties is not None and href is not None  # guaranteed by the XPath expression
        p = properties.split()
        if 'cover-image' in p:
            guides = container.opf_xpath('//opf:guide')
            if not guides:
                guides = (container.opf.makeelement(OPF('guide')),)
                container.opf.append(guides[0])
            for guide in guides:
                for child in guide:
                    if child.get('type') == 'cover':
                        break
                else:
                    guide.append(guide.makeelement(OPF('reference'), type='cover', href=href))
                    changed = True
            break
        elif 'calibre:title-page' in p:
            cast('_Element', item.getparent()).remove(item)  # manifest items always have a parent
    if changed:
        container.dirty(container.opf_name)
        container.commit_item(container.opf_name)
    outpath = outpath or (epub.rpartition('.')[0] + '.azw3')
    opf_to_azw3(container.name_to_abspath(container.opf_name), outpath, container)


class AZW3Container(Container):
    book_type = 'azw3'
    SUPPORTS_TITLEPAGES = False
    SUPPORTS_FILENAMES = False

    pathtoazw3: str
    obfuscated_fonts: set[str]

    def __init__(self, pathtoazw3: str | None = None, log: Log | None = default_log, clone_data: CloneData | None = None, tdir: str | None = None) -> None:
        if clone_data is not None:
            super().__init__(log=log, clone_data=clone_data)
            for x in ('pathtoazw3', 'obfuscated_fonts'):
                setattr(self, x, clone_data[x])
            return

        assert pathtoazw3 is not None
        self.pathtoazw3 = pathtoazw3
        if tdir is None:
            tdir = PersistentTemporaryDirectory('_azw3_container')
        tdir = os.path.abspath(os.path.realpath(tdir))
        self.root = tdir
        with open(pathtoazw3, 'rb') as stream:
            raw = stream.read(3)
            if raw == b'TPZ':
                raise InvalidMobi(_('This is not a MOBI file. It is a Topaz file.'))

            try:
                header = MetadataHeader(stream, default_log)
            except MobiError:
                raise InvalidMobi(_('This is not a MOBI file.'))

            if header.encryption_type != 0:
                raise DRMError()

            kf8_type = header.kf8_type

            if kf8_type is None:
                raise InvalidMobi(
                    _(
                        'This MOBI file does not contain a KF8 format '
                        'book. KF8 is the new format from Amazon. calibre can '
                        'only edit MOBI files that contain KF8 books. Older '
                        'MOBI files without KF8 are not editable.'
                    )
                )

            if kf8_type == 'joint':
                raise InvalidMobi(_('This MOBI file contains both KF8 and older Mobi6 data. calibre can only edit MOBI files that contain only KF8 data.'))

        try:
            opf_path, obfuscated_fonts = fork_job('calibre.ebooks.oeb.polish.container', 'do_explode', args=(pathtoazw3, tdir), no_output=True)['result']
        except WorkerError as e:
            if log is not None:
                log(e.orig_tb)
            raise InvalidMobi('Failed to explode MOBI')
        super().__init__(rootpath=tdir, opfpath=opf_path, log=log)
        self.obfuscated_fonts = {x.replace(os.sep, '/') for x in obfuscated_fonts}

    def data_for_clone(self, dest_dir: str | None = None) -> CloneData:
        ans = super().data_for_clone(dest_dir)
        ans['pathtoazw3'] = self.pathtoazw3
        ans['obfuscated_fonts'] = self.obfuscated_fonts.copy()
        return ans

    def commit(self, outpath: str | None = None, keep_parsed: bool = False) -> None:
        super().commit(keep_parsed=keep_parsed)
        if outpath is None:
            outpath = self.pathtoazw3
        opf_to_azw3(self.name_path_map[self.opf_name], outpath, self)

    @property
    def path_to_ebook(self) -> str:
        return self.pathtoazw3

    @path_to_ebook.setter
    def path_to_ebook(self, val: str) -> None:
        self.pathtoazw3 = val

    @property
    def names_that_must_not_be_changed(self) -> set[str]:
        return set(self.name_path_map)


# }}}


def get_container(
    path: str, log: Log | None = None, tdir: str | None = None, tweak_mode: bool = False, ebook_cls: type[EpubContainer | AZW3Container] | None = None
) -> Container:
    try:
        isdir = os.path.isdir(path)
    except Exception:
        isdir = False
    own_tdir = not tdir
    if ebook_cls is None:
        ext = path.rpartition('.')[-1].lower()
        ebook_cls = EpubContainer
        if not isdir:
            if ext in {'azw3', 'mobi', 'original_azw3', 'original_mobi'}:
                ebook_cls = AZW3Container
            elif ext in {'kepub', 'original_kepub'}:
                ebook_cls = KEPUBContainer
    if own_tdir:
        tdir = PersistentTemporaryDirectory(f'_{ebook_cls.book_type}_container')
    try:
        ebook = ebook_cls(path, log=log or default_log, tdir=tdir)
        ebook.tweak_mode = tweak_mode
    except BaseException:
        if own_tdir:
            assert tdir is not None
            shutil.rmtree(tdir, ignore_errors=True)
        raise
    return ebook


def test_roundtrip() -> None:
    ebook = get_container(sys.argv[-1])
    p = PersistentTemporaryFile(suffix='.' + sys.argv[-1].rpartition('.')[-1])
    p.close()
    ebook.commit(outpath=p.name)
    ebook2 = get_container(p.name)
    ebook3 = get_container(p.name)
    diff = ebook3.compare_to(ebook2)
    if diff is not None:
        print(diff)


if __name__ == '__main__':
    test_roundtrip()
