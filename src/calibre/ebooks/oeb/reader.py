# License: GPLv3 Copyright: 2008, Marshall T. Vandegrift <llasram@gmail.com>

"""
Container-/OPF-based input OEBBook reader.
"""

import copy
import io
import os
import re
import sys
import uuid
from collections import defaultdict
from typing import IO, TYPE_CHECKING, Self
from urllib.parse import urldefrag, urlparse

from lxml import etree

from calibre import guess_type, xml_replace_entities
from calibre.constants import __appname__, __version__
from calibre.ebooks.oeb.base import (
    BINARY_MIME,
    COLLAPSE_RE,
    DC11_NS,
    DC_NSES,
    JPEG_MIME,
    MS_COVER_TYPE,
    NCX_MIME,
    OEB_DOCS,
    OEB_IMAGES,
    OEB_STYLES,
    OPF,
    OPF1_NS,
    OPF2_NS,
    OPF2_NSMAP,
    PAGE_MAP_MIME,
    SVG_MIME,
    XHTML_MIME,
    XMLDECL_RE,
    DirContainer,
    OEBBook,
    OEBError,
    XPath,
    barename,
    is_element_list,
    is_str_list,
    iterlinks,
    namespace,
    urlnormalize,
    xml2text,
    xpath,
)
from calibre.ebooks.oeb.writer import OEBWriter
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.cleantext import clean_xml_chars
from calibre.utils.localization import __, get_lang
from calibre.utils.xml_parse import safe_xml_fromstring
from polyglot.urllib import unquote

if TYPE_CHECKING:
    from collections.abc import Collection
    from optparse import Values

    from calibre.ebooks.oeb.base import TOC, Manifest

__all__ = ['OEBReader']


class OEBReader:
    """Read an OEBPS 1.x or OPF/OPS 2.0 file collection."""

    COVER_SVG_XP = XPath('h:body//svg:svg[position() = 1]')
    COVER_OBJECT_XP = XPath('h:body//h:object[@data][position() = 1]')

    Container = DirContainer
    '''Container type used to access book files.  Override in sub-classes.'''

    DEFAULT_PROFILE = 'PRS505'
    '''Default renderer profile for content read with this Reader.'''

    TRANSFORMS = []
    '''List of transforms to apply to content read with this Reader.'''

    @classmethod
    def config(cls, cfg: object) -> None:
        """Add any book-reading options to the :class:`Config` object
        :param:`cfg`.
        """
        return

    @classmethod
    def generate(cls, opts: Values) -> Self:
        """Generate a Reader instance from command-line options."""
        return cls()

    def __call__(self, oeb: OEBBook, path: str | IO[bytes]) -> OEBBook:
        """Read the book at :param:`path` into the :class:`OEBBook` object
        :param:`oeb`.
        """
        self.oeb = oeb
        self.logger = self.log = oeb.logger
        # sub-classes such as LitReader use containers that also accept streams
        oeb.container = container = self.Container(path, self.logger)  # ty: ignore[invalid-argument-type]
        container.log = oeb.log
        opf = self._read_opf()
        self._all_from_opf(opf)
        return oeb

    def _clean_opf(self, opf: etree._Element) -> etree._Element:
        nsmap: dict[str | None, str] = {}
        for elem in opf.iter(tag=etree.Element):
            nsmap.update(elem.nsmap)
        for elem in opf.iter(tag=etree.Element):
            etag = elem.tag
            assert isinstance(etag, str)  # the etree.Element filter excludes comments/PIs/entities
            if namespace(etag) in ('', OPF1_NS) and ':' not in barename(etag):
                elem.tag = OPF(barename(etag))

        nsmap.update(OPF2_NSMAP)
        attrib = dict(opf.attrib)
        if xmlns := attrib.pop('xmlns:', None):
            attrib['xmlns'] = xmlns
        nroot = etree.Element(OPF('package'), nsmap={None: OPF2_NS}, attrib=attrib)
        metadata = etree.SubElement(nroot, OPF('metadata'), nsmap=nsmap)
        ignored = (OPF('dc-metadata'), OPF('x-metadata'))
        mdelems = xpath(opf, 'o2:metadata//*')
        assert is_element_list(mdelems)
        for elem in mdelems:
            etag = elem.tag
            assert isinstance(etag, str)  # selected by an element-only XPath
            if etag in ignored:
                continue
            if namespace(etag) in DC_NSES:
                tag = barename(etag).lower()
                elem.tag = etag = f'{{{DC11_NS}}}{tag}'
            if etag.startswith('dc:'):
                tag = etag.partition(':')[-1].lower()
                elem.tag = f'{{{DC11_NS}}}{tag}'
            metadata.append(elem)
        metas = xpath(opf, 'o2:metadata//o2:meta')
        assert is_element_list(metas)
        for element in metas:
            metadata.append(element)
        for tag in ('o2:manifest', 'o2:spine', 'o2:tours', 'o2:guide'):
            elems = xpath(opf, tag)
            assert is_element_list(elems)
            for element in elems:
                nroot.append(element)
        return nroot

    def _read_opf(self) -> etree._Element:
        data = self.oeb.container.read(None)
        data = self.oeb.decode(data)
        data = XMLDECL_RE.sub('', data)
        data = re.sub(r'http://openebook.org/namespaces/oeb-package/1.0(/*)', OPF1_NS, data)
        try:
            opf = safe_xml_fromstring(data)
        except etree.XMLSyntaxError:
            data = xml_replace_entities(clean_xml_chars(data), encoding=None)
            try:
                opf = safe_xml_fromstring(data)
                self.logger.warn('OPF contains invalid HTML named entities')
            except etree.XMLSyntaxError:
                data = re.sub(r'(?is)<tours>.+</tours>', '', data)
                data = data.replace('<dc-metadata>', '<dc-metadata xmlns:dc="http://purl.org/metadata/dublin_core">')
                opf = safe_xml_fromstring(data)
                self.logger.warn('OPF contains invalid tours section')

        otag = opf.tag
        assert isinstance(otag, str)  # root of a parsed XML document
        ns = namespace(otag)
        if ns not in ('', OPF1_NS, OPF2_NS):
            raise OEBError(f'Invalid namespace {ns!r} for OPF document')
        opf = self._clean_opf(opf)
        return opf

    def _metadata_from_opf(self, opf: etree._Element) -> None:
        from calibre.ebooks.metadata.opf2 import OPF
        from calibre.ebooks.oeb.transforms.metadata import meta_info_to_oeb_metadata

        stream = io.BytesIO(etree.tostring(opf, xml_declaration=True, encoding='utf-8'))
        o = OPF(stream)
        pwm = o.primary_writing_mode
        if pwm:
            self.oeb.metadata.primary_writing_mode = pwm
        mi = o.to_book_metadata()
        lang_is_fallback = o.languages_are_fallback
        if not mi.language:
            mi.language = get_lang().replace('_', '-')
        self.oeb.metadata.add('language', mi.language)
        if not mi.book_producer:
            mi.book_producer = '{a} ({v}) [http://{a}-ebook.com]'.format(**dict(a=__appname__, v=__version__))
        meta_info_to_oeb_metadata(mi, self.oeb.metadata, self.logger)
        m = self.oeb.metadata
        if lang_is_fallback:
            for lang in m.language:
                lang.is_fallback = True
        m.add('identifier', str(uuid.uuid4()), id='uuid_id', scheme='uuid')
        self.oeb.uid = self.oeb.metadata.identifier[-1]
        if not m.title:
            m.add('title', self.oeb.translate(__('Unknown')))
        has_aut = False
        for x in m.creator:
            if getattr(x, 'role', '').lower() in ('', 'aut'):
                has_aut = True
                break
        if not has_aut:
            m.add('creator', self.oeb.translate(__('Unknown')), role='aut')

    def _manifest_prune_invalid(self) -> list[Manifest.Item]:
        """
        Remove items from manifest that contain invalid data. This prevents
        catastrophic conversion failure, when a few files contain corrupted
        data.
        """
        bad: list[Manifest.Item] = []
        check = OEB_DOCS.union(OEB_STYLES)
        for item in list(self.oeb.manifest.values()):
            if item.media_type in check:
                try:
                    item.data  # ruff: ignore[useless-expression]
                except KeyboardInterrupt:
                    raise
                except Exception:
                    self.logger.exception(f'Failed to parse content in {item.href}')
                    bad.append(item)
                    self.oeb.manifest.remove(item)
        return bad

    def _manifest_add_missing(self, invalid: Collection[Manifest.Item]) -> None:
        import css_parser

        manifest = self.oeb.manifest
        known = set(manifest.hrefs)
        unchecked = set(manifest.values())
        cdoc = OEB_DOCS | OEB_STYLES
        invalid = set()
        while unchecked:
            new = set()
            for item in unchecked:
                data = None
                if item.media_type in cdoc or item.media_type[-4:] in ('/xml', '+xml'):
                    try:
                        data = item.data
                    except Exception:
                        self.oeb.log.exception(f'Failed to read from manifest entry with id: {item.id}, ignoring')
                        invalid.add(item)
                        continue
                if data is None:
                    continue

                if item.media_type in OEB_DOCS or item.media_type[-4:] in ('/xml', '+xml'):
                    assert isinstance(data, etree._Element)  # XHTML/XML items are parsed into elements
                    hrefs = [r[2] for r in iterlinks(data)]
                    for href in hrefs:
                        if isinstance(href, bytes):
                            href = href.decode('utf-8')
                        href, _ = urldefrag(href)
                        if not href:
                            continue
                        try:
                            href = item.abshref(urlnormalize(href))
                            scheme = urlparse(href).scheme
                        except Exception:
                            self.oeb.log.exception(f'Skipping invalid href: {href!r}')
                            continue
                        if not scheme and href not in known:
                            new.add(href)
                elif item.media_type in OEB_STYLES:
                    try:
                        urls = list(css_parser.getUrls(data))
                    except Exception:
                        urls = []
                    for url in urls:
                        href, _ = urldefrag(url)
                        href = item.abshref(urlnormalize(href))
                        scheme = urlparse(href).scheme
                        if not scheme and href not in known:
                            new.add(href)
            unchecked.clear()
            warned = set()
            for href in new:
                known.add(href)
                is_invalid = False
                for item in invalid:
                    if href == item.abshref(urlnormalize(href)):
                        is_invalid = True
                        break
                if is_invalid:
                    continue
                if not self.oeb.container.exists(href):
                    if href not in warned:
                        self.logger.warn(f'Referenced file {href!r} not found')
                        warned.add(href)
                    continue
                if href not in warned:
                    self.logger.warn(f'Referenced file {href!r} not in manifest')
                    warned.add(href)
                id, _ = manifest.generate(id='added')
                guessed = guess_type(href)[0]
                media_type = guessed or BINARY_MIME
                added = manifest.add(id, href, media_type)
                unchecked.add(added)

            for item in invalid:
                self.oeb.manifest.remove(item)

    def _manifest_from_opf(self, opf: etree._Element) -> None:
        manifest = self.oeb.manifest
        items = xpath(opf, '/o2:package/o2:manifest/o2:item')
        assert is_element_list(items)
        for elem in items:
            id = elem.get('id')
            href = elem.get('href')
            media_type = elem.get('media-type', None)
            if media_type is None:
                media_type = elem.get('mediatype', None)
            if not media_type or media_type == 'text/xml':
                guessed = guess_type(href)[0]
                media_type = guessed or media_type or BINARY_MIME
            if hasattr(media_type, 'lower'):
                media_type = media_type.lower()
            fallback = elem.get('fallback')
            if href in manifest.hrefs:
                self.logger.warn(f'Duplicate manifest entry for {href!r}')
                continue
            if href is None or not self.oeb.container.exists(href):
                self.logger.warn(f'Manifest item {href!r} not found')
                continue
            if not id:
                id = manifest.generate('id')[0]
            elif id in manifest.ids:
                self.logger.warn(f'Duplicate manifest id {id!r}')
                id, href = manifest.generate(id, href)
            manifest.add(id, href, media_type, fallback)
        invalid = self._manifest_prune_invalid()
        self._manifest_add_missing(invalid)

    def _spine_add_extra(self) -> None:
        manifest = self.oeb.manifest
        spine = self.oeb.spine
        unchecked = set(spine)
        selector = XPath('h:body//h:a/@href')
        extras = set()
        while unchecked:
            new = set()
            for item in unchecked:
                if item.media_type not in OEB_DOCS:
                    # TODO: handle fallback chains
                    continue
                root = item.data
                assert isinstance(root, etree._Element)  # item.media_type is in OEB_DOCS
                for href in selector(root):
                    href, _ = urldefrag(href)
                    if not href:
                        continue
                    try:
                        href = item.abshref(urlnormalize(href))
                    except ValueError:  # Malformed URL
                        continue
                    if href not in manifest.hrefs:
                        continue
                    found = manifest.hrefs[href]
                    if found.media_type not in OEB_DOCS or found in spine or found in extras:
                        continue
                    new.add(found)
            extras.update(new)
            unchecked = new
        version = int(self.oeb.version[0])
        removed_items_to_ignore = getattr(self.oeb, 'removed_items_to_ignore', ())
        for item in extras:
            if item.href in removed_items_to_ignore:
                continue
            if version >= 2:
                self.logger.warn(f'Spine-referenced file {item.href!r} not in spine')
            spine.add(item, linear=False)

    def _spine_from_opf(self, opf: etree._Element) -> None:
        spine = self.oeb.spine
        manifest = self.oeb.manifest
        itemrefs = xpath(opf, '/o2:package/o2:spine/o2:itemref')
        assert is_element_list(itemrefs)
        for elem in itemrefs:
            idref = elem.get('idref')
            if idref not in manifest.ids:
                self.logger.warn(f'Spine item {idref!r} not found')
                continue
            item = manifest.ids[idref]
            mt = item.media_type.lower()
            data = item.data
            root_tag = None
            if isinstance(data, etree._Element):
                root_tag = data.tag
                assert isinstance(root_tag, str)  # root of a parsed document
            if mt in OEB_DOCS and root_tag is not None and not root_tag.endswith('}ncx'):
                spine.add(item, elem.get('linear'))
            elif root_tag and root_tag.endswith('}html'):
                item.media_type = XHTML_MIME
                spine.add(item, elem.get('linear'))
            else:
                self.oeb.log.warn(f'The item {item.href} is not a XML document. Removing it from spine.')
        if len(spine) == 0:
            raise OEBError('Spine is empty')
        self._spine_add_extra()
        ppds = xpath(opf, '/o2:package/o2:spine/@page-progression-direction')
        assert is_str_list(ppds)
        for val in ppds:
            if val in {'ltr', 'rtl'}:
                spine.page_progression_direction = val

    def _guide_from_opf(self, opf: etree._Element) -> None:
        guide = self.oeb.guide
        manifest = self.oeb.manifest
        refs = xpath(opf, '/o2:package/o2:guide/o2:reference')
        assert is_element_list(refs)
        for elem in refs:
            ref_href, typ = elem.get('href'), elem.get('type')
            if not ref_href or not typ:
                self.logger.warn(f'Ignoring guide reference with no href or type: {ref_href!r}, {typ!r}')
                continue
            path = urlnormalize(urldefrag(ref_href)[0])
            if path not in manifest.hrefs:
                corrected_href = None
                for href in manifest.hrefs:
                    if href.lower() == path.lower():
                        corrected_href = href
                        break
                if corrected_href is None:
                    self.logger.warn(f'Guide reference {ref_href!r} not found')
                    continue
                ref_href = corrected_href
            if typ not in guide:
                guide.add(typ, elem.get('title'), ref_href)

    def _find_ncx(self, opf: etree._Element) -> Manifest.Item | None:
        result = xpath(opf, '/o2:package/o2:spine/@toc')
        assert is_str_list(result)
        if result:
            id = result[0]
            if id not in self.oeb.manifest.ids:
                return None
            item = self.oeb.manifest.ids[id]
            self.oeb.manifest.remove(item)
            return item
        for item in self.oeb.manifest.values():
            if item.media_type == NCX_MIME:
                self.oeb.manifest.remove(item)
                return item
        return None

    def _toc_from_navpoint(self, item: Manifest.Item, toc: TOC, navpoint: etree._Element) -> None:
        children = xpath(navpoint, 'ncx:navPoint')
        assert is_element_list(children)
        for child in children:
            texts = xpath(child, 'ncx:navLabel/ncx:text/text()')
            assert is_str_list(texts)
            title = ''.join(texts)
            title = COLLAPSE_RE.sub(' ', title.strip())
            srcs = xpath(child, 'ncx:content/@src')
            assert is_str_list(srcs)
            if not title:
                self._toc_from_navpoint(item, toc, child)
                continue
            if (not srcs or not srcs[0]) and not xpath(child, 'ncx:navPoint'):
                # This node is useless
                continue
            href = item.abshref(urlnormalize(srcs[0])) if srcs and srcs[0] else ''
            path, _ = urldefrag(href)
            if path and path not in self.oeb.manifest.hrefs:
                path = urlnormalize(path)
            if href and path not in self.oeb.manifest.hrefs:
                self.logger.warn(f'TOC reference {href!r} not found')
                gc = xpath(child, 'ncx:navPoint')
                if not gc:
                    # This node is useless
                    continue
            id = child.get('id')
            klass = child.get('class', 'chapter')

            try:
                po = int(child.get('playOrder', self.oeb.toc.next_play_order()))
            except Exception:
                po = self.oeb.toc.next_play_order()

            authorElement = xpath(child, 'descendant::calibre:meta[@name = "author"]')
            assert is_element_list(authorElement)
            if authorElement:
                author = authorElement[0].text
            else:
                author = None

            descriptionElement = xpath(child, 'descendant::calibre:meta[@name = "description"]')
            assert is_element_list(descriptionElement)
            if descriptionElement:
                description = etree.tostring(descriptionElement[0], method='text', encoding='unicode').strip()
                if not description:
                    description = None
            else:
                description = None

            index_image = xpath(child, 'descendant::calibre:meta[@name = "toc_thumbnail"]')
            assert is_element_list(index_image)
            toc_thumbnail = index_image[0].text if index_image else None
            if not toc_thumbnail or not toc_thumbnail.strip():
                toc_thumbnail = None

            node = toc.add(
                title,
                href,
                id=id,
                klass=klass,
                play_order=po,
                description=description,
                author=author,
                toc_thumbnail=toc_thumbnail,
            )

            self._toc_from_navpoint(item, node, child)

    def _toc_from_ncx(self, item: Manifest.Item | None) -> bool:
        if (item is None) or (item.data is None):
            return False
        self.log.debug('Reading TOC from NCX...')
        ncx = item.data
        assert isinstance(ncx, etree._Element)  # the NCX is an XML document
        texts = xpath(ncx, 'ncx:docTitle/ncx:text/text()')
        assert is_str_list(texts)
        title = ''.join(texts)
        title = COLLAPSE_RE.sub(' ', title.strip())
        title = title or str(self.oeb.metadata.title[0])
        toc = self.oeb.toc
        toc.title = title
        navmaps = xpath(ncx, 'ncx:navMap')
        assert is_element_list(navmaps)
        for navmap in navmaps:
            self._toc_from_navpoint(item, toc, navmap)
        return True

    def _toc_from_tour(self, opf: etree._Element) -> bool:
        result = xpath(opf, 'o2:tours/o2:tour')
        assert is_element_list(result)
        if not result:
            return False
        self.log.debug('Reading TOC from tour...')
        tour = result[0]
        toc = self.oeb.toc
        toc.title = tour.get('title')
        sites = xpath(tour, 'o2:site')
        assert is_element_list(sites)
        for site in sites:
            title = site.get('title')
            href = site.get('href')
            if not title or not href:
                continue
            path, _ = urldefrag(urlnormalize(href))
            if path not in self.oeb.manifest.hrefs:
                self.logger.warn(f'TOC reference {href!r} not found')
                continue
            id = site.get('id')
            toc.add(title, href, id=id)
        return True

    def _toc_from_html(self, opf: etree._Element) -> bool:
        if 'toc' not in self.oeb.guide:
            return False
        self.log.debug('Reading TOC from HTML...')
        itempath, frag = urldefrag(self.oeb.guide['toc'].href)
        item = self.oeb.manifest.hrefs[itempath]
        html = item.data
        assert isinstance(html, etree._Element)  # the guide TOC is an (X)HTML document
        if frag:
            elems = xpath(html, f'.//*[@id="{frag}"]')
            if not elems:
                elems = xpath(html, f'.//*[@name="{frag}"]')
            assert is_element_list(elems)
            elem = elems[0] if elems else html
            while elem != html and not xpath(elem, './/h:a[@href]'):
                parent = elem.getparent()
                assert parent is not None  # elem is a descendant of html, so we reach html first
                elem = parent
            html = elem
        titles = defaultdict(list)
        order = []
        anchors = xpath(html, './/h:a[@href]')
        assert is_element_list(anchors)
        for anchor in anchors:
            href = anchor.attrib['href']
            href = item.abshref(urlnormalize(href))
            path, frag = urldefrag(href)
            if path not in self.oeb.manifest.hrefs:
                continue
            title = xml2text(anchor)
            title = COLLAPSE_RE.sub(' ', title.strip())
            if href not in titles:
                order.append(href)
            titles[href].append(title)
        toc = self.oeb.toc
        for href in order:
            toc.add(' '.join(titles[href]), href)
        return True

    def _toc_from_spine(self, opf: etree._Element) -> bool:
        self.log.warn('Generating default TOC from spine...')
        toc = self.oeb.toc
        titles = []
        headers = []
        for item in self.oeb.spine:
            if not item.linear:
                continue
            html = item.data
            assert isinstance(html, etree._Element)  # spine items are (X)HTML documents
            texts = xpath(html, '/h:html/h:head/h:title/text()')
            assert is_str_list(texts)
            title = ''.join(texts)
            title = COLLAPSE_RE.sub(' ', title.strip())
            if title:
                titles.append(title)
            headers.append('(unlabeled)')
            for tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'strong'):
                expr = '/h:html/h:body//h:%s[position()=1]/text()'
                texts = xpath(html, expr % tag)
                assert is_str_list(texts)
                header = ''.join(texts)
                header = COLLAPSE_RE.sub(' ', header.strip())
                if header:
                    headers[-1] = header
                    break
        use = titles
        if len(titles) > len(set(titles)):
            use = headers
        for title, item in zip(use, self.oeb.spine):
            if not item.linear:
                continue
            toc.add(title, item.href)
        return True

    def _toc_from_opf(self, opf: etree._Element, item: Manifest.Item | None) -> None:
        self.oeb.auto_generated_toc = False
        if self._toc_from_ncx(item):
            return
        # Prefer HTML to tour based TOC, since several LIT files
        # have good HTML TOCs but bad tour based TOCs
        if self._toc_from_html(opf):
            return
        if self._toc_from_tour(opf):
            return
        self._toc_from_spine(opf)
        self.oeb.auto_generated_toc = True

    def _pages_from_ncx(self, opf: etree._Element, item: Manifest.Item | None) -> bool:
        if item is None:
            return False
        ncx = item.data
        if ncx is None:
            return False
        assert isinstance(ncx, etree._Element)  # the NCX is an XML document
        ptargets = xpath(ncx, 'ncx:pageList/ncx:pageTarget')
        assert is_element_list(ptargets)
        if not ptargets:
            return False
        pages = self.oeb.pages
        for ptarget in ptargets:
            texts = xpath(ptarget, 'ncx:navLabel/ncx:text/text()')
            assert is_str_list(texts)
            name = ''.join(texts)
            name = COLLAPSE_RE.sub(' ', name.strip())
            srcs = xpath(ptarget, 'ncx:content/@src')
            assert is_str_list(srcs)
            if not srcs:
                continue
            href = item.abshref(urlnormalize(srcs[0]))
            id = ptarget.get('id')
            type = ptarget.get('type', 'normal')
            klass = ptarget.get('class')
            pages.add(name, href, type=type, id=id, klass=klass)
        return True

    def _find_page_map(self, opf: etree._Element) -> Manifest.Item | None:
        result = xpath(opf, '/o2:package/o2:spine/@page-map')
        assert is_str_list(result)
        if result:
            id = result[0]
            if id not in self.oeb.manifest.ids:
                return None
            item = self.oeb.manifest.ids[id]
            self.oeb.manifest.remove(item)
            return item
        for item in self.oeb.manifest.values():
            if item.media_type == PAGE_MAP_MIME:
                self.oeb.manifest.remove(item)
                return item
        return None

    def _pages_from_page_map(self, opf: etree._Element) -> bool:
        item = self._find_page_map(opf)
        if item is None:
            return False
        pmap = item.data
        assert isinstance(pmap, etree._Element)  # the page map is an XML document
        pages = self.oeb.pages
        page_elems = xpath(pmap, 'o2:page')
        assert is_element_list(page_elems)
        for page in page_elems:
            name = page.get('name', '')
            href = page.get('href')
            if not href:
                continue
            name = COLLAPSE_RE.sub(' ', name.strip())
            href = item.abshref(urlnormalize(href))
            type = 'normal'
            if not name:
                type = 'special'
            elif name.lower().strip('ivxlcdm') == '':
                type = 'front'
            pages.add(name, href, type=type)
        return True

    def _pages_from_opf(self, opf: etree._Element, item: Manifest.Item | None) -> None:
        if self._pages_from_ncx(opf, item):
            return
        if self._pages_from_page_map(opf):
            return
        return

    def _cover_from_html(self, hcover: Manifest.Item) -> Manifest.Item:
        from calibre.ebooks import render_html_svg_workaround

        with TemporaryDirectory('_html_cover') as tdir:
            writer = OEBWriter()
            writer(self.oeb, tdir)
            path = os.path.join(tdir, unquote(hcover.href))
            data = render_html_svg_workaround(path, self.logger, root=tdir)
            if not data:
                data = b''
        id, href = self.oeb.manifest.generate('cover', 'cover.jpg')
        item = self.oeb.manifest.add(id, href, JPEG_MIME, data=data)
        return item

    def _locate_cover_image(self) -> Manifest.Item:
        if self.oeb.metadata.cover:
            id = str(self.oeb.metadata.cover[0])
            item = self.oeb.manifest.ids.get(id, None)
            if item is not None and item.media_type in OEB_IMAGES:
                return item
            else:
                self.logger.warn(f'Invalid cover image @id {id!r}')
        hcover = self.oeb.spine[0]
        if 'cover' in self.oeb.guide:
            href = self.oeb.guide['cover'].href
            item = self.oeb.manifest.hrefs[href]
            media_type = item.media_type
            if media_type in OEB_IMAGES:
                return item
            elif media_type in OEB_DOCS:
                hcover = item
        html = hcover.data
        assert isinstance(html, etree._Element)  # hcover is a spine item or a guide item in OEB_DOCS
        if MS_COVER_TYPE in self.oeb.guide:
            href = self.oeb.guide[MS_COVER_TYPE].href
            item = self.oeb.manifest.hrefs.get(href, None)
            if item is not None and item.media_type in OEB_IMAGES:
                return item
        if self.COVER_SVG_XP(html):
            svg = copy.deepcopy(self.COVER_SVG_XP(html)[0])
            href = os.path.splitext(hcover.href)[0] + '.svg'
            id, href = self.oeb.manifest.generate(hcover.id, href)
            item = self.oeb.manifest.add(id, href, SVG_MIME, data=svg)
            return item
        if self.COVER_OBJECT_XP(html):
            object = self.COVER_OBJECT_XP(html)[0]
            href = hcover.abshref(object.get('data'))
            item = self.oeb.manifest.hrefs.get(href, None)
            if item is not None and item.media_type in OEB_IMAGES:
                return item
        return self._cover_from_html(hcover)

    def _ensure_cover_image(self) -> None:
        cover = self._locate_cover_image()
        if self.oeb.metadata.cover:
            self.oeb.metadata.cover[0].value = cover.id
            return
        self.oeb.metadata.add('cover', cover.id)

    def _manifest_remove_duplicates(self) -> None:
        seen = set()
        dups = set()
        for item in self.oeb.manifest:
            if item.href in seen:
                dups.add(item.href)
            seen.add(item.href)

        for href in dups:
            items = [x for x in self.oeb.manifest if x.href == href]
            for x in items:
                if x not in self.oeb.spine:
                    self.oeb.log.warn('Removing duplicate manifest item with id:', x.id)
                    self.oeb.manifest.remove_duplicate_item(x)

    def _all_from_opf(self, opf: etree._Element) -> None:
        self.oeb.version = opf.get('version', '1.2')
        self._metadata_from_opf(opf)
        self._manifest_from_opf(opf)
        self._spine_from_opf(opf)
        self._manifest_remove_duplicates()
        self._guide_from_opf(opf)
        item = self._find_ncx(opf)
        self._toc_from_opf(opf, item)
        self._pages_from_opf(opf, item)
        # self._ensure_cover_image()


def main(argv: list[str] = sys.argv) -> int:

    from calibre.utils.logging import default_log

    reader = OEBReader()
    for arg in argv[1:]:
        oeb = reader(OEBBook(default_log), arg)
        for name, doc in oeb.to_opf1().values():
            print(etree.tostring(doc, pretty_print=True))
        for name, doc in oeb.to_opf2(page_map=True).values():
            print(etree.tostring(doc, pretty_print=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
