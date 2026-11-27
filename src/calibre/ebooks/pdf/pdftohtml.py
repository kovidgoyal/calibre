#!/usr/bin/env python
# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>

import errno
import os
import re
import shutil
import subprocess
from typing import TYPE_CHECKING, NamedTuple, Protocol, Unpack, cast

from calibre import CurrentDir, prints, xml_replace_entities
from calibre.constants import bundled_binaries_dir, isbsd, iswindows
from calibre.ebooks import ConversionError, DRMError
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.pdf.bidi import fix_pdftohtml_html
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.cleantext import clean_ascii_chars, clean_xml_chars
from calibre.utils.ipc import eintr_retry_call
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from lxml.etree import _Element

    from calibre.type_hints import PopenKwargs


PDFTOHTML = 'pdftohtml' + ('.exe' if iswindows else '')
creationflags = subprocess.DETACHED_PROCESS if iswindows else 0


def popen(cmd: Sequence[str], **kw: Unpack[PopenKwargs]) -> subprocess.Popen[bytes]:
    if iswindows:
        kw['creationflags'] = creationflags
    return subprocess.Popen(cmd, **kw)


if bbd := bundled_binaries_dir():
    PDFTOHTML = os.path.join(bbd, PDFTOHTML)
PDFTOTEXT = os.path.join(os.path.dirname(PDFTOHTML), 'pdftotext' + ('.exe' if iswindows else ''))


# Searchable PDFs made by OCR programs, such as ABBYY FineReader or OCRmyPDF,
# have scanned pages with invisible text over them, which pdftohtml leaves out
# unless it is given -hidden. Giving it -hidden for all pages would duplicate
# the text of pages that have both visible text and an invisible copy of it,
# and leaving it out loses the text of the scanned pages of a PDF that also has
# some visible text, such as a cover page or a watermark on every page. So the
# content streams of the pages are first read with podofo, which is fast, as
# nothing is drawn and no images are decoded, to find the pages whose text is
# invisible. pdftotext, which extracts the text of a page, invisible or not,
# much faster than pdftohtml, gives the text of those pages. Scanned pages
# are covered by images of themselves, whose extraction is by far the
# slowest part of the conversion, so pdftohtml is only run for the other
# pages.
#
# The text of a page is its invisible text if it has at most this many
# characters of visible text, as a watermark or running head can be visible
OCR_PAGE_MAX_VISIBLE_CHARS = 500
# and more than this many times as many characters of invisible text. A page
# with visible text and an invisible copy of it has only as many.
OCR_PAGE_MIN_HIDDEN_TEXT_FACTOR = 3
# Such a page is scanned, and its images are not extracted, if images cover at
# least this fraction of it. Their areas are added up, as a scanned page can
# be split into layers, strips or tiles.
OCR_PAGE_MIN_IMAGE_COVERAGE = 0.5
# Pages whose invisible text is used, and are at most this many pages apart,
# are extracted by one run of pdftotext, to avoid opening the PDF once for
# each of them
OCR_PAGE_MAX_GAP = 10
# The positions and sizes in the XML output of pdftohtml are in points
# multiplied by this
PDFTOHTML_ZOOM = 1.5


class OCRPages(NamedTuple):
    # The page numbers, from 1, of the pages whose text is their invisible text
    hidden_text: frozenset[int]
    # Those of them that are scanned, see OCR_PAGE_MIN_IMAGE_COVERAGE
    scanned: frozenset[int]
    page_count: int


def find_ocr_pages(pdf_path: str) -> OCRPages | None:
    # See OCR_PAGE_MAX_VISIBLE_CHARS. None if the PDF cannot be read.
    from calibre.utils.podofo import get_page_content_stats

    try:
        stats = get_page_content_stats(pdf_path)
    except Exception as err:
        prints(f'Failed to read the PDF to find pages with invisible text, as made by OCR programs: {err}')
        return None
    hidden_text: set[int] = set()
    scanned: set[int] = set()
    for num, page_stats in enumerate(stats, start=1):
        if page_stats is None:
            continue
        visible, invisible, coverage = page_stats
        if visible <= OCR_PAGE_MAX_VISIBLE_CHARS and invisible > OCR_PAGE_MIN_HIDDEN_TEXT_FACTOR * visible:
            hidden_text.add(num)
            if coverage >= OCR_PAGE_MIN_IMAGE_COVERAGE:
                scanned.add(num)
    return OCRPages(frozenset(hidden_text), frozenset(scanned), len(stats))


def page_ranges(pages: Iterable[int], max_gap: int = 1) -> list[tuple[int, int]]:
    # Ranges of the page numbers in pages, joining those at most max_gap apart
    ans: list[tuple[int, int]] = []
    for num in sorted(pages):
        if ans and num - ans[-1][1] <= max_gap:
            ans[-1] = ans[-1][0], num
        else:
            ans.append((num, num))
    return ans


def local_name(elem: _Element) -> str:
    tag = elem.tag
    return tag.rpartition('}')[2] if isinstance(tag, str) else ''


def pdftotext_pages(pdf_path: str, pages: Iterable[int]) -> dict[int, _Element] | None:
    """
    The <page> elements of the output of pdftotext -bbox-layout for pages, by
    page number, which have the position of every line and word of the text of
    the page, invisible or not. None if pdftotext fails.
    """
    from calibre.utils.xml_parse import safe_xml_fromstring

    ans: dict[int, _Element] = {}
    for first, last in page_ranges(pages, OCR_PAGE_MAX_GAP):
        cmd = [PDFTOTEXT, '-enc', 'UTF-8', '-bbox-layout', '-q', '-f', str(first), '-l', str(last), pdf_path, '-']
        try:
            p = popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        except OSError as err:
            prints(f'Failed to run pdftotext to extract the invisible text of pages {first} to {last}: {err}')
            return None
        raw, err_output = p.communicate()
        if p.returncode != 0:
            prints(f'pdftotext failed to extract the invisible text of pages {first} to {last} with return code: {p.returncode}')
            prints(err_output.decode('utf-8', 'replace').strip())
            return None
        try:
            root = safe_xml_fromstring(clean_ascii_chars(raw))
        except Exception as err:
            prints(f'Failed to parse the invisible text of pages {first} to {last} from pdftotext: {err}')
            return None
        page_elems = [e for e in root.iter() if local_name(e) == 'page']
        if len(page_elems) != last - first + 1:
            prints(f'pdftotext output {len(page_elems)} pages for pages {first} to {last}')
            return None
        for num, page in enumerate(page_elems, start=first):
            ans[num] = page
    return ans


class RunPdftohtml(Protocol):
    # Runs pdftohtml for the pages, all if None, writing its output to output
    def __call__(self, output: str, hidden: bool = False, pages: tuple[int, int] | None = None) -> None: ...


class FontNumbers:
    # The fonts of the XML output of pdftohtml are numbered from 0 in each
    # run, so those of the outputs that are put together, and of the text from
    # pdftotext, are given the number of the same font, or a new one

    def __init__(self) -> None:
        self.numbers: dict[tuple[tuple[str, str], ...], str] = {}

    def number(self, key: tuple[tuple[str, str], ...], page: _Element) -> str:
        # The number of the font with the attributes in key, adding a
        # <fontspec> for it to page if it is new
        from lxml import etree

        ans = self.numbers.get(key)
        if ans is None:
            ans = self.numbers[key] = str(len(self.numbers))
            spec = etree.Element('fontspec')
            spec.set('id', ans)
            for name, value in key:
                spec.set(name, value)
            page.insert(0, spec)
        return ans


def font_key(spec: _Element) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(k), str(v)) for k, v in spec.attrib.items() if k != 'id'))


def coordinate(elem: _Element, name: str) -> float:
    try:
        return float(cast('str', elem.get(name)))
    except TypeError, ValueError:
        return 0


def set_text_from_pdftotext(page: _Element, text_page: _Element, fonts: FontNumbers) -> None:
    """
    Replace the <text> elements of page, in the XML output of pdftohtml, with
    one for each line of text_page, the output of pdftotext for it
    """
    from lxml import etree

    for text in page.xpath('descendant::text'):
        parent = text.getparent()
        if parent is not None:
            parent.remove(text)
    for line in text_page.iter():
        if local_name(line) != 'line':
            continue
        words = [w for w in line if local_name(w) == 'word' and (w.text or '').strip()]
        if not words:
            continue
        # The size of the font is the height of the words, which, unlike that
        # of the line, does not include the space between the lines
        heights = sorted(coordinate(w, 'yMax') - coordinate(w, 'yMin') for w in words)
        size = max(1, round(heights[len(heights) // 2] * PDFTOHTML_ZOOM))
        left = coordinate(line, 'xMin') * PDFTOHTML_ZOOM
        text = etree.SubElement(page, 'text')
        text.set('top', str(round(coordinate(line, 'yMax') * PDFTOHTML_ZOOM - size)))
        text.set('left', str(round(left)))
        text.set('width', str(round(coordinate(line, 'xMax') * PDFTOHTML_ZOOM - left)))
        text.set('height', str(size))
        text.set('font', fonts.number((('color', '#000000'), ('family', 'OCRText'), ('size', str(size))), page))
        text.text = ' '.join(cast('str', w.text).strip() for w in words)


def convert_ocr_pages(pdf_path: str, index: str, ocr_pages: OCRPages, run: RunPdftohtml) -> bool:
    """
    Write the XML output of pdftohtml for the PDF to index, with the
    invisible text of the pages in ocr_pages, extracted by pdftotext, and
    running pdftohtml, with run(), only for the pages that are not scanned.
    False, having written nothing, if pdftotext fails.
    """
    from lxml import etree

    from calibre.utils.xml_parse import safe_xml_fromstring

    text_pages = pdftotext_pages(pdf_path, ocr_pages.hidden_text)
    if text_pages is None:
        return False
    other_pages = [num for num in range(1, ocr_pages.page_count + 1) if num not in ocr_pages.scanned]
    root = etree.Element('pdf2xml')
    pages: dict[int, _Element] = {}
    fonts = FontNumbers()
    outline: _Element | None = None
    ranges: list[tuple[int, int] | None] = [None] if len(other_pages) == ocr_pages.page_count else list(page_ranges(other_pages))
    for pages_range in ranges:
        # Each part has its own name, which its images are named after
        output = index if pages_range is None else f'part{pages_range[0]}.xml'
        run(output, pages=pages_range)
        with open(output, 'rb') as f:
            part = safe_xml_fromstring(clean_ascii_chars(f.read()))
        if output != index:
            os.remove(output)
        part_fonts = {cast('str', spec.get('id')): font_key(spec) for spec in part.iter('fontspec')}
        for page in part.iterchildren('page'):
            for spec in page.xpath('descendant::fontspec'):
                cast('_Element', spec.getparent()).remove(spec)
            for text in page.xpath('descendant::text'):
                if (key := part_fonts.get(cast('str', text.get('font')))) is not None:
                    text.set('font', fonts.number(key, page))
            pages[int(cast('str', page.get('number')))] = page
        if outline is None:
            # Every part has the outline of the whole PDF
            outline = next(part.iterchildren('outline'), None)
    for num in sorted(ocr_pages.scanned):
        # Scanned pages are only their text, see OCR_PAGE_MIN_IMAGE_COVERAGE
        text_page = text_pages[num]
        page = pages[num] = etree.Element('page')
        page.set('number', str(num))
        page.set('position', 'absolute')
        page.set('top', '0')
        page.set('left', '0')
        page.set('height', str(round(coordinate(text_page, 'height') * PDFTOHTML_ZOOM)))
        page.set('width', str(round(coordinate(text_page, 'width') * PDFTOHTML_ZOOM)))
    for num in sorted(ocr_pages.hidden_text):
        if (page := pages.get(num)) is not None:
            set_text_from_pdftotext(page, text_pages[num], fonts)
    for num in sorted(pages):
        root.append(pages[num])
    if outline is not None:
        root.append(outline)
    prints(
        f'Using the invisible text, as made by OCR programs, of {len(ocr_pages.hidden_text)} pages,'
        f' and not extracting the images of the {len(ocr_pages.scanned)} of them that are scanned'
    )
    with open(index, 'wb') as f:
        f.write(etree.tostring(root.getroottree(), encoding='utf-8', xml_declaration=True))
    return True


def pdftohtml(output_dir: str, pdf_path: str, no_images: bool, as_xml: bool = False) -> None:
    """
    Convert the pdf into html using the pdftohtml app.
    This will write the html as index.html into output_dir.
    It will also write all extracted images to the output_dir
    """

    pdfsrc = os.path.join(output_dir, 'src.pdf')
    index = os.path.join(output_dir, 'index.' + ('xml' if as_xml else 'html'))

    with open(pdf_path, 'rb') as src, open(pdfsrc, 'wb') as dest:
        shutil.copyfileobj(src, dest)

    with CurrentDir(output_dir):

        def a(x: str) -> str:
            return os.path.basename(x)

        def run(output: str, hidden: bool = False, pages: tuple[int, int] | None = None) -> None:
            cmd = [PDFTOHTML, '-enc', 'UTF-8', '-noframes', '-p', '-nomerge', '-nodrm', a(pdfsrc), output]
            if isbsd:
                cmd.remove('-nodrm')
            if no_images:
                cmd.append('-i')
            if as_xml:
                cmd.append('-xml')
            if hidden:
                cmd.append('-hidden')
            if pages is not None:
                cmd += ['-f', str(pages[0]), '-l', str(pages[1])]

            logf = PersistentTemporaryFile('pdftohtml_log')
            try:
                p = popen(cmd, stderr=logf._fd, stdout=logf._fd, stdin=subprocess.PIPE)
            except OSError as err:
                if err.errno == errno.ENOENT:
                    raise ConversionError(_('Could not find pdftohtml, check it is in your PATH'))
                else:
                    raise
            ret = eintr_retry_call(p.wait)
            logf.flush()
            logf.close()
            with open(logf.name, 'rb') as f:
                out = f.read().decode('utf-8', 'replace').strip()
            if ret != 0:
                raise ConversionError(f'pdftohtml failed with return code: {ret}\n{out}')
            if out:
                prints('pdftohtml log:')
                prints(out)
            if not os.path.exists(output) or os.stat(output).st_size < 100:
                raise DRMError()

        # See OCR_PAGE_MAX_VISIBLE_CHARS
        ocr_pages = find_ocr_pages(a(pdfsrc))
        if ocr_pages is None or not ocr_pages.hidden_text:
            run(a(index))
        elif not as_xml or not convert_ocr_pages(a(pdfsrc), a(index), ocr_pages, run):
            # The HTML output cannot be put together from parts, so its text
            # is the invisible text if that of most pages is
            hidden = len(ocr_pages.hidden_text) * 2 > ocr_pages.page_count
            if hidden:
                prints('Using the invisible text, as made by OCR programs, as that of most pages is invisible')
            run(a(index), hidden)

        if not as_xml:
            with open(index, 'r+b') as i:
                raw = i.read().decode('utf-8', 'replace')
                raw = flip_images(raw)
                raw = raw.replace('<head', "<!-- created by calibre's pdftohtml -->\n  <head", 1)
                i.seek(0)
                i.truncate()
                # versions of pdftohtml >= 0.20 output self closing <br> tags, this
                # breaks the pdf heuristics regexps, so replace them
                raw = raw.replace('<br/>', '<br>')
                raw = re.sub(r'<a\s+name=(\d+)', r'<a id="\1"', raw, flags=re.I)
                raw = re.sub(r'<a id="(\d+)"', r'<a id="p\1"', raw, flags=re.I)
                raw = re.sub(r'<a href="index.html#(\d+)"', r'<a href="#p\1"', raw, flags=re.I)
                raw = xml_replace_entities(raw)
                raw = re.sub(r'[\u00a0\u2029]', ' ', raw)
                # pdftohtml outputs the text of a line in visual order, which
                # means right-to-left text comes out with its letters backwards
                raw = fix_pdftohtml_html(raw)

                i.write(raw.encode('utf-8'))

            cmd = [
                PDFTOHTML,
                '-f',
                '1',
                '-l',
                '1',
                '-xml',
                '-i',
                '-enc',
                'UTF-8',
                '-noframes',
                '-p',
                '-nomerge',
                '-nodrm',
                '-q',
                '-stdout',
                a(pdfsrc),
            ]
            if isbsd:
                cmd.remove('-nodrm')
            p = popen(cmd, stdout=subprocess.PIPE)
            assert p.stdout is not None  # stdout=PIPE
            rawb = p.stdout.read().strip()
            if p.wait() == 0 and rawb:
                parse_outline(rawb, output_dir, pdfsrc)

        try:
            os.remove(pdfsrc)
        except Exception:
            pass


def resolve_outline_pages(outline: _Element, pdf_path: str, report: Callable[[str], object]) -> None:
    """
    Set the page attribute on <item> elements in the pdftohtml generated
    outline that poppler could not resolve, for example, because the PDF
    outline uses JavaScript actions of the form "this.pageNum = N;"
    rather than destinations.
    """
    items = list(outline.iter('item'))
    if all(item.get('page') for item in items):
        return
    from calibre.utils.podofo import get_outline_and_page_count

    try:
        nodes, num_pages = get_outline_and_page_count(pdf_path)
    except Exception as err:
        report(f'Failed to read the PDF outline to resolve Table of Contents destinations: {err}')
        return
    flat: list[dict[str, object]] = []

    def flatten(children: list[dict[str, object]]) -> None:
        for node in children:
            flat.append(node)
            flatten(cast('list[dict[str, object]]', node['children']))

    flatten(nodes)
    if len(flat) != len(items):
        report(f'PDF outline has {len(flat)} entries but pdftohtml found {len(items)}, cannot resolve Table of Contents destinations')
        return

    def normalized(x: object) -> str:
        return ' '.join(str(x or '').split())

    for item, node in zip(items, flat):
        if normalized(item.text) != normalized(node.get('title')):
            report(f'PDF outline entry {node.get("title")!r} does not match pdftohtml entry {item.text!r}, cannot resolve Table of Contents destinations')
            return
    for item, node in zip(items, flat):
        if item.get('page'):
            continue
        page = 0
        if isinstance(dest := node.get('dest'), dict):
            page = int(cast('dict[str, int]', dest)['page'])
        elif isinstance(js := node.get('js'), str) and (m := re.fullmatch(r'\s*this\.pageNum\s*=\s*(\d+)\s*;?\s*', js)):
            page = int(m.group(1)) + 1  # pageNum is zero based
        if 0 < page <= num_pages:
            item.set('page', str(page))
        elif page > num_pages:
            report(f'PDF outline entry {item.text!r} links to page {page} but the PDF has only {num_pages} pages, ignoring it')


def parse_outline(raw: bytes, output_dir: str, pdf_path: str) -> None:
    from lxml import etree

    from calibre.utils.xml_parse import safe_xml_fromstring

    text = clean_xml_chars(xml_to_unicode(raw, strip_encoding_pats=True, assume_utf8=True)[0])
    outline = safe_xml_fromstring(text).xpath('(//outline)[1]')
    if outline:
        from calibre.ebooks.oeb.polish.toc import TOC, create_ncx

        outline = outline[0]
        resolve_outline_pages(outline, pdf_path, prints)
        toc = TOC()
        count = [0]

        def process_node(node: _Element, toc: TOC) -> None:
            for child in node.iterchildren('*'):
                if child.tag == 'outline':
                    parent = toc.children[-1] if toc.children else toc
                    process_node(child, parent)
                elif child.text:
                    page = child.get('page', '1')
                    toc.add(child.text, 'index.html', 'p' + page)
                    count[0] += 1

        process_node(outline, toc)
        if count[0] > 2:
            root = create_ncx(toc, (lambda x: x), 'pdftohtml', 'en', 'pdftohtml')
            with open(os.path.join(output_dir, 'toc.ncx'), 'wb') as f:
                f.write(etree.tostring(root, pretty_print=True, with_tail=False, encoding='utf-8', xml_declaration=True))


def flip_image(img_path: str, flip: str) -> None:
    from calibre.utils.img import flip_image, image_and_format_from_data, image_to_data

    with open(img_path, 'r+b') as f:
        img, fmt = image_and_format_from_data(f.read())
        img = flip_image(img, horizontal='x' in flip, vertical='y' in flip)
        f.seek(0), f.truncate()
        f.write(image_to_data(img, fmt=fmt))


def flip_images(raw: str) -> str:
    for match in re.finditer(r'<IMG[^>]+/?>', raw, flags=re.I):
        img = match.group()
        m = re.search(r'class="(x|y|xy)flip"', img)
        if m is None:
            continue
        flip = m.group(1)
        src = re.search(r'src="([^"]+)"', img)
        if src is None:
            continue
        img = src.group(1)
        if not os.path.exists(img):
            continue
        flip_image(img, flip)
    raw = re.sub(r'<STYLE.+?</STYLE>\s*', '', raw, flags=re.I | re.DOTALL)

    counter = 0

    def add_alt(m: re.Match[str]) -> str:
        nonlocal counter
        counter += 1
        return m.group(1).rstrip('/') + f' alt="Image {counter}"/>'

    raw = re.sub(r'(<IMG[^>]+)/?>', add_alt, raw, flags=re.I)
    return raw
