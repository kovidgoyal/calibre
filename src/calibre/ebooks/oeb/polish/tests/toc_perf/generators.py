#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>
'''Generators for deep-TOC performance corpus (check A-* and convert B-*).'''

from __future__ import annotations

import os
from io import BytesIO
from typing import TYPE_CHECKING, Literal
from zipfile import ZIP_STORED, ZipFile

from calibre.ebooks.oeb.base import XHTML_NS
from calibre.ebooks.oeb.polish.tests.base import get_cache
from calibre.ebooks.oeb.polish.tests.toc_perf.scales import SEED, Fanout, fanout_for, scale_n
from calibre.ebooks.oeb.polish.utils import guess_type

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

AVariant = Literal['dangling', 'case', 'dual', 'mixed', 'clean']
CHAPTER = 'chapter.xhtml'
CHAPTER_CASE_WRONG = 'Chapter.xhtml'  # wrong case href → CHAPTER on case-sensitive FS
MISSING = 'missing.xhtml'
NAV = 'nav.xhtml'
NCX = 'toc.ncx'
OPF = 'content.opf'

XHTML = f'http://www.w3.org/1999/xhtml'
EPUB_NS = 'http://www.idpf.org/2007/ops'
NCX_NS = 'http://www.daisy.org/z3986/2005/ncx/'


def _cache_dir() -> str:
    d = os.path.join(get_cache(), 'toc_perf')
    os.makedirs(d, exist_ok=True)
    return d


def iter_toc_entries(fanout: Fanout) -> Iterable[tuple[int, int, int, str, str]]:
    '''Yield (l1, l2, l3_or_0, title, frag_id) in document order.

    L1/L2 entries have l3=0. Every entry gets a unique frag id on CHAPTER.
    '''
    idx = 0
    for i in range(1, fanout.l1 + 1):
        idx += 1
        frag = f'h1-{i}'
        yield (i, 0, 0, f'Chapter {i}', frag)
        for j in range(1, fanout.l2 + 1):
            idx += 1
            frag = f'h2-{i}-{j}'
            yield (i, j, 0, f'Section {i}.{j}', frag)
            for k in range(1, fanout.l3 + 1):
                idx += 1
                frag = f'h3-{i}-{j}-{k}'
                yield (i, j, k, f'Subsection {i}.{j}.{k}', frag)


def _chapter_html(fanout: Fanout, *, include_ids: bool = True, bad_frags: Sequence[str] = ()) -> str:
    '''Spine HTML with heading ids matching TOC fragments (unless bad_frags).'''
    parts = [
        f'<html xmlns="{XHTML_NS}" xmlns:epub="{EPUB_NS}">',
        '<head><title>Chapter</title></head><body>',
        '<p>Body start.</p>',
    ]
    bad = set(bad_frags)
    for _i, _j, _k, title, frag in iter_toc_entries(fanout):
        if not include_ids or frag in bad:
            parts.append(f'<h3>{title}</h3>')
        else:
            level = 1 if _j == 0 else (2 if _k == 0 else 3)
            parts.append(f'<h{level} id="{frag}">{title}</h{level}>')
            parts.append(f'<p>Text for {title}.</p>')
    parts.append('<p><a href="#h1-1">Legitimate body link</a></p>')
    parts.append('</body></html>')
    return '\n'.join(parts)


def _nav_ol(entries: list[tuple[int, int, int, str, str]], href_for) -> str:
    '''Build nested <ol> for nav from flat entry list.'''
    # Group into tree
    lines: list[str] = ['<ol>']
    prev_l1 = prev_l2 = 0
    open_l1 = open_l2 = False
    for i, j, k, title, frag in entries:
        href = href_for(title, frag)
        if j == 0:  # L1
            if open_l2:
                lines.append('</ol></li>')
                open_l2 = False
            if open_l1:
                lines.append('</ol></li>')
            lines.append(f'<li><a href="{href}">{title}</a><ol>')
            open_l1 = True
            prev_l1, prev_l2 = i, 0
        elif k == 0:  # L2
            if open_l2:
                lines.append('</ol></li>')
            lines.append(f'<li><a href="{href}">{title}</a><ol>')
            open_l2 = True
            prev_l2 = j
        else:  # L3
            lines.append(f'<li><a href="{href}">{title}</a></li>')
    if open_l2:
        lines.append('</ol></li>')
    if open_l1:
        lines.append('</ol></li>')
    lines.append('</ol>')
    return '\n'.join(lines)


def _nav_html(entries: list[tuple[int, int, int, str, str]], href_for) -> str:
    ol = _nav_ol(entries, href_for)
    return (
        f'<html xmlns="{XHTML_NS}" xmlns:epub="{EPUB_NS}">'
        f'<head><title>Nav</title></head><body>'
        f'<nav epub:type="toc" id="toc"><h1>Contents</h1>{ol}</nav>'
        f'</body></html>'
    )


def _ncx_xml(entries: list[tuple[int, int, int, str, str]], href_for) -> str:
    parts = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<ncx xmlns="{NCX_NS}" version="2005-1">',
        '<head><meta name="dtb:uid" content="toc-perf-test"/></head>',
        '<docTitle><text>TOC Perf</text></docTitle>',
        '<navMap>',
    ]
    play = 0
    open_l1 = open_l2 = False
    for i, j, k, title, frag in entries:
        play += 1
        href = href_for(title, frag)
        if j == 0:
            if open_l2:
                parts.append('</navPoint>')
                open_l2 = False
            if open_l1:
                parts.append('</navPoint>')
            parts.append(
                f'<navPoint id="np-{play}" playOrder="{play}">'
                f'<navLabel><text>{title}</text></navLabel>'
                f'<content src="{href}"/>'
            )
            open_l1 = True
        elif k == 0:
            if open_l2:
                parts.append('</navPoint>')
            parts.append(
                f'<navPoint id="np-{play}" playOrder="{play}">'
                f'<navLabel><text>{title}</text></navLabel>'
                f'<content src="{href}"/>'
            )
            open_l2 = True
        else:
            parts.append(
                f'<navPoint id="np-{play}" playOrder="{play}">'
                f'<navLabel><text>{title}</text></navLabel>'
                f'<content src="{href}"/>'
                f'</navPoint>'
            )
    if open_l2:
        parts.append('</navPoint>')
    if open_l1:
        parts.append('</navPoint>')
    parts.append('</navMap></ncx>')
    return '\n'.join(parts)


def _opf(manifest_items: list[tuple[str, str, str | None]], spine_toc: str | None = 'ncx') -> str:
    '''Build OPF. manifest_items: (id, href, properties|None).'''
    man = []
    for mid, href, props in manifest_items:
        mt = guess_type(href)
        p = f' properties="{props}"' if props else ''
        man.append(f'<item id="{mid}" href="{href}" media-type="{mt}"{p}/>')
    # Chapter only in spine; nav is referenced via the manifest nav property.
    spine_attrs = f' toc="{spine_toc}"' if spine_toc else ''
    spine = '<itemref idref="chapter"/>'
    return f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">toc-perf-{SEED}</dc:identifier>
    <dc:title>TOC Perf</dc:title>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    {''.join(man)}
  </manifest>
  <spine{spine_attrs}>
    {spine}
  </spine>
</package>'''


def _href_clean(_title: str, frag: str) -> str:
    return f'{CHAPTER}#{frag}'


def _href_dangling(_title: str, frag: str) -> str:
    return f'{MISSING}#{frag}'


def _href_case(_title: str, frag: str) -> str:
    # Wrong case of filename; preserve fragment
    return f'{CHAPTER_CASE_WRONG}#{frag}'


def build_a_epub(
    variant: AVariant,
    n: int,
    *,
    dual_toc: bool | None = None,
) -> bytes:
    '''Build an EPUB3 bytes object for material A variants.

    dual_toc: default True except A-clean may be overridden; A-dual forces True.
    '''
    fanout = fanout_for(n)
    entries = list(iter_toc_entries(fanout))
    assert fanout.leaf_n == n
    assert len(entries) == fanout.total_entries

    if dual_toc is None:
        dual_toc = True
    if variant == 'dual':
        dual_toc = True
        href_for = _href_dangling
        bad_frags: Sequence[str] = ()
        chapter = _chapter_html(fanout, include_ids=True)
    elif variant == 'dangling':
        href_for = _href_dangling
        bad_frags = ()
        chapter = _chapter_html(fanout, include_ids=True)
    elif variant == 'case':
        href_for = _href_case
        bad_frags = ()
        chapter = _chapter_html(fanout, include_ids=True)
    elif variant == 'mixed':
        # Case on L1/L2, dangling on L3; a few BadDestinationFragment via missing frags
        bad_frags = [e[4] for e in entries if e[4].startswith('h1-')][:3]
        chapter = _chapter_html(fanout, include_ids=True, bad_frags=bad_frags)

        def href_for(title: str, frag: str) -> str:
            if frag in bad_frags:
                return f'{CHAPTER}#{frag}-missing'
            if frag.startswith('h3-'):
                return _href_dangling(title, frag)
            return _href_case(title, frag)
    elif variant == 'clean':
        href_for = _href_clean
        bad_frags = ()
        chapter = _chapter_html(fanout, include_ids=True)
    else:
        raise ValueError(variant)

    nav = _nav_html(entries, href_for)
    manifest: list[tuple[str, str, str | None]] = [
        ('chapter', CHAPTER, None),
        ('nav', NAV, 'nav'),
    ]
    files: dict[str, bytes] = {
        CHAPTER: chapter.encode('utf-8'),
        NAV: nav.encode('utf-8'),
    }
    spine_toc = None
    if dual_toc:
        ncx = _ncx_xml(entries, href_for)
        files[NCX] = ncx.encode('utf-8')
        manifest.append(('ncx', NCX, None))
        spine_toc = 'ncx'

    opf = _opf(manifest, spine_toc=spine_toc)
    files[OPF] = opf.encode('utf-8')

    buf = BytesIO()
    with ZipFile(buf, 'w', ZIP_STORED) as zf:
        zf.writestr(
            'META-INF/container.xml',
            b'''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>''',
        )
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def a_epub_path(variant: AVariant, scale: str, *, dual_toc: bool | None = None) -> str:
    '''Write (or reuse cached) A-variant EPUB under polish-test cache; return path.'''
    n = scale_n(scale)
    dual_tag = '' if dual_toc is None else f'-dual{int(dual_toc)}'
    path = os.path.join(_cache_dir(), f'A-{variant}-{scale}{dual_tag}.epub')
    raw = build_a_epub(variant, n, dual_toc=dual_toc)
    # Always rewrite — generators are cheap vs convert; keeps corpus in sync with code
    with open(path, 'wb') as f:
        f.write(raw)
    return path


def b_levels_markdown(n: int) -> str:
    '''Markdown with h1/h2/h3 tree matching fanout (depth 3 only). Also used as B-playorder source.'''
    fanout = fanout_for(n)
    lines = [f'<!-- seed={SEED} n={n} -->', '']
    for i, j, k, title, frag in iter_toc_entries(fanout):
        if j == 0:
            lines.append(f'# {title} {{#{frag}}}')
            lines.append('')
        elif k == 0:
            lines.append(f'## {title} {{#{frag}}}')
            lines.append('')
        else:
            lines.append(f'### {title} {{#{frag}}}')
            lines.append('')
            lines.append(f'Paragraph for {title}.')
            lines.append('')
    return '\n'.join(lines)


def b_levels_html(n: int) -> str:
    '''Equivalent HTML heading tree for DetectStructure (shared convert TOC path).'''
    fanout = fanout_for(n)
    parts = [
        f'<html xmlns="{XHTML_NS}"><head><title>B-levels</title></head><body>',
    ]
    for i, j, k, title, frag in iter_toc_entries(fanout):
        if j == 0:
            parts.append(f'<h1 id="{frag}">{title}</h1>')
        elif k == 0:
            parts.append(f'<h2 id="{frag}">{title}</h2>')
        else:
            parts.append(f'<h3 id="{frag}">{title}</h3>')
            parts.append(f'<p>Paragraph for {title}.</p>')
    parts.append('</body></html>')
    return '\n'.join(parts)


def b_levels_path(scale: str, fmt: Literal['md', 'html'] = 'html') -> str:
    n = scale_n(scale)
    path = os.path.join(_cache_dir(), f'B-levels-{scale}.{fmt}')
    raw = b_levels_markdown(n) if fmt == 'md' else b_levels_html(n)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(raw)
    return path


def b_sony_stub_note() -> str:
    '''Stub: B-sony EPUB2 with many #frag TOC entries — filled in PR-B2 tests.'''
    return 'B-sony: use b_levels_html + DetectStructure TOC then EPUB2 output with fragments'


def b_inline_stub_note() -> str:
    '''Stub: B-inline with epub_inline_toc — filled in PR-B2 tests.'''
    return 'B-inline: TOCAdder path with epub_inline_toc / count() gate'


LEVEL_TOC_OPTS = [
    '--level1-toc=//h:h1',
    '--level2-toc=//h:h2',
    '--level3-toc=//h:h3',
]
