#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

# Making books accessible: the language of the book and its HTML files, the
# alternative text of images and the accessibility metadata of EPUB 3 books,
# see https://www.w3.org/TR/epub-a11y-11/ and https://www.w3.org/TR/epub-a11y-tech-11/
# Used by the Edit book accessibility tool.

from typing import NamedTuple

from calibre.ebooks.metadata.utils import normalize_languages
from calibre.ebooks.oeb.base import DC, EPUB, OEB_DOCS, OPF, XHTML, XML
from calibre.ebooks.oeb.polish.container import Container
from calibre.ebooks.oeb.polish.opf import get_book_language_tag
from calibre.utils.localization import canonicalize_lang

# Language {{{


def has_language(root) -> bool:
    return bool(root.get('lang') or root.get(XML('lang')))


def book_languages(container: Container) -> list[str]:
    # The languages of the book as ISO 639-3 codes
    ans = []
    for lang in container.opf_xpath('//opf:metadata/dc:language'):
        code = canonicalize_lang((lang.text or '').strip())
        if code and code != 'und' and code not in ans:
            ans.append(code)
    return ans


def set_book_languages(container: Container, languages: list[str]) -> bool:
    """
    Set the languages of the book, given as ISO 639-3 codes. Country codes
    already present in the OPF are kept. Returns True if the OPF was changed.
    """
    if languages == book_languages(container):
        return False
    tags = container.opf_xpath('//opf:metadata/dc:language')
    existing = [t.text.strip() for t in tags if t.text and t.text.strip()]
    parent = container.opf_xpath('//opf:metadata')[0]
    index = parent.index(tags[0]) if tags else None
    for t in tags:
        container.remove_from_xml(t)
    # The EPUB specification requires a dc:language
    values = list(dict.fromkeys(normalize_languages(existing, languages))) or ['und']
    for val in values:
        t = parent.makeelement(DC('language'))
        t.text = val
        container.insert_into_xml(parent, t, index)
        if index is not None:
            index += 1
    container.dirty(container.opf_name)
    return True


def html_files_without_language(container: Container) -> list[str]:
    return [name for name in html_names(container) if not has_language(container.parsed(name))]


def set_html_language(container: Container, names: list[str], lang: str, replace: bool = False) -> set[str]:
    """
    Set the language of the HTML files in ``names`` to the BCP 47 tag
    ``lang``. Only files without a language are changed, unless ``replace`` is
    True. Returns the names of the changed files.
    """
    # The lang attribute is not valid in the XHTML 1.1 used by EPUB 2
    attrs = ('lang', XML('lang')) if container.opf_version_parsed.major > 2 else (XML('lang'),)
    changed = set()
    for name in names:
        root = container.parsed(name)
        if replace or not has_language(root):
            if all(root.get(attr) == lang for attr in attrs):
                continue
            for attr in attrs:
                root.set(attr, lang)
            container.dirty(name)
            changed.add(name)
    return changed


# }}}

# Alternative text for images {{{

IMG = XHTML('img')
CONTEXT_TAGS = frozenset(map(XHTML, ('p', 'figure', 'li', 'td', 'th', 'dd', 'blockquote', 'section', 'div', 'body')))
MAX_CONTEXT_LENGTH = 300


class ImageUse(NamedTuple):
    html_name: str  # The HTML file containing the <img> tag
    index: int  # The position of the <img> tag among all <img> tags in the HTML file
    image_name: str | None  # The image file, None if it is missing or remote
    sourceline: int | None
    alt: str | None  # None when the alt attribute is missing, an empty string means the image is decorative
    context: str  # Text surrounding the image, to help describe it


def html_names(container: Container) -> list[str]:
    # Spine order first, then any HTML files not in the spine
    ans = [name for name, linear in container.spine_names]
    seen = set(ans)
    ans.extend(sorted(name for name, mt in container.mime_map.items() if mt in OEB_DOCS and name not in seen))
    return ans


def context_text(img) -> str:
    parent = img.getparent()
    while parent is not None and parent.tag not in CONTEXT_TAGS:
        parent = parent.getparent()
    if parent is None:
        return ''
    if parent.tag == XHTML('figure'):
        for caption in parent.iter(XHTML('figcaption')):
            text = ' '.join(''.join(caption.itertext()).split())
            if text:
                return text
    text = ' '.join(''.join(parent.itertext()).split())
    if len(text) > MAX_CONTEXT_LENGTH:
        text = text[: MAX_CONTEXT_LENGTH - 1].rstrip() + '…'
    return text


def image_uses(container: Container) -> list[ImageUse]:
    ans = []
    for name in html_names(container):
        root = container.parsed(name)
        for i, img in enumerate(root.iter(IMG)):
            src = (img.get('src') or '').strip()
            image_name = container.href_to_name(src, name) if src else None
            if image_name is not None and not container.has_name(image_name):
                image_name = None
            ans.append(ImageUse(name, i, image_name, img.sourceline, img.get('alt'), context_text(img)))
    return ans


def set_alt_text(container: Container, changes: dict[tuple[str, int], str | None]) -> set[str]:
    """
    Set the alternative text of images. ``changes`` maps (html_name, index), as
    in :class:`ImageUse`, to the new alternative text. Use an empty string for
    decorative images and None to remove the alt attribute. Returns the names
    of the changed HTML files.
    """
    by_name: dict[str, dict[int, str | None]] = {}
    for (name, index), alt in changes.items():
        by_name.setdefault(name, {})[index] = alt
    changed = set()
    for name, alts in by_name.items():
        root = container.parsed(name)
        for i, img in enumerate(root.iter(IMG)):
            if i not in alts:
                continue
            alt = alts[i]
            if alt == img.get('alt'):
                continue
            if alt is None:
                del img.attrib['alt']
            else:
                img.set('alt', alt)
            changed.add(name)
        if name in changed:
            container.dirty(name)
    return changed


# }}}

# Accessibility metadata {{{

SUMMARY = 'schema:accessibilitySummary'
ACCESS_MODE = 'schema:accessMode'
ACCESS_MODE_SUFFICIENT = 'schema:accessModeSufficient'
FEATURE = 'schema:accessibilityFeature'
HAZARD = 'schema:accessibilityHazard'
CONFORMS_TO = 'dcterms:conformsTo'
CERTIFIED_BY = 'a11y:certifiedBy'
PROPERTIES = (SUMMARY, ACCESS_MODE, ACCESS_MODE_SUFFICIENT, FEATURE, HAZARD, CONFORMS_TO, CERTIFIED_BY)

# The values from the schema.org vocabularies that are useful for e-books
ACCESS_MODES = ('textual', 'visual', 'auditory', 'tactile', 'chartOnVisual', 'diagramOnVisual', 'mathOnVisual', 'textOnVisual', 'colorDependent')
SUFFICIENT_ACCESS_MODES = ('textual', 'visual', 'auditory', 'tactile', 'textual,visual', 'textual,auditory', 'auditory,visual')
FEATURES = (
    'alternativeText',
    'longDescription',
    'tableOfContents',
    'structuralNavigation',
    'readingOrder',
    'index',
    'pageNavigation',
    'pageBreakMarkers',
    'printPageNumbers',
    'displayTransformability',
    'ARIA',
    'MathML',
    'describedMath',
    'synchronizedAudioText',
    'ttsMarkup',
    'captions',
    'transcript',
    'annotations',
    'none',
)
CONFORMANCE = (
    'EPUB Accessibility 1.1 - WCAG 2.2 Level AA',
    'EPUB Accessibility 1.1 - WCAG 2.2 Level A',
    'EPUB Accessibility 1.1 - WCAG 2.1 Level AA',
    'EPUB Accessibility 1.1 - WCAG 2.1 Level A',
)

# Hazards are flashing, motion simulation and sound, each of which can be
# present, absent or unknown
HAZARDS = {
    'flashing': ('flashing', 'noFlashingHazard'),
    'motionSimulation': ('motionSimulation', 'noMotionSimulationHazard'),
    'sound': ('sound', 'noSoundHazard'),
}
PRESENT, ABSENT, UNKNOWN = 'present', 'absent', 'unknown'


def hazard_states(values: list[str]) -> dict[str, str]:
    ans = dict.fromkeys(HAZARDS, UNKNOWN)
    for val in values:
        if val == 'none':
            ans = dict.fromkeys(HAZARDS, ABSENT)
            break
        for hazard, (present, absent) in HAZARDS.items():
            if val == present:
                ans[hazard] = PRESENT
            elif val == absent:
                ans[hazard] = ABSENT
    return ans


def hazard_values(states: dict[str, str]) -> list[str]:
    if all(s == ABSENT for s in states.values()):
        return ['none']
    if all(s == UNKNOWN for s in states.values()):
        return ['unknown']
    ans = []
    for hazard, (present, absent) in HAZARDS.items():
        state = states.get(hazard, UNKNOWN)
        if state == PRESENT:
            ans.append(present)
        elif state == ABSENT:
            ans.append(absent)
    return ans


def property_tags(container: Container, prop: str):
    # Only tags that describe the book itself, not other metadata
    return [m for m in container.opf_xpath('//opf:metadata/opf:meta[@property]') if m.get('property') == prop and not m.get('refines')]


def read_accessibility_metadata(container: Container) -> dict[str, list[str]]:
    ans = {}
    for prop in PROPERTIES:
        ans[prop] = [val for val in (' '.join((m.text or '').split()) for m in property_tags(container, prop)) if val]
    return ans


def set_accessibility_metadata(container: Container, metadata: dict[str, list[str]]) -> bool:
    """
    Replace the values of the accessibility properties in ``metadata``.
    Properties not in ``metadata`` are left unchanged. Returns True if the
    OPF was changed.
    """
    current = read_accessibility_metadata(container)
    changed = False
    parent = container.opf_xpath('//opf:metadata')[0]
    for prop, values in metadata.items():
        values = [val for val in (' '.join(v.split()) for v in values) if val]
        if values == current.get(prop):
            continue
        for m in property_tags(container, prop):
            container.remove_from_xml(m)
        for val in values:
            m = parent.makeelement(OPF('meta'), property=prop)
            m.text = val
            container.insert_into_xml(parent, m)
        changed = True
    if changed:
        container.dirty(container.opf_name)
    return changed


# }}}


# ARIA roles {{{

EPUB_TYPE = EPUB('type')


def _roles():
    # The epub:type values that have a corresponding role, from the EPUB Type
    # to ARIA Role Authoring Guide, see
    # https://www.w3.org/TR/epub-aria-authoring-11/ and the elements the roles
    # are allowed on, from ARIA in HTML, see https://www.w3.org/TR/html-aria/
    # Only the DPUB-ARIA roles are used, the WAI-ARIA roles such as list and
    # table change the nature of the element and so need more care than can be
    # taken automatically. The deprecated doc-biblioentry and doc-endnote roles
    # are not used, and neither is doc-cover, which is for images, not the
    # cover type.
    allowed_on = {
        'section': (
            'abstract acknowledgments afterword appendix bibliography chapter colophon conclusion credit credits dedication'
            ' endnotes epigraph epilogue errata foreword glossary index introduction notice page-list part preface prologue'
            ' pullquote qna toc'
        ),
        'aside': 'dedication footnote glossary pullquote tip',
        'footer': 'footnote',
        'nav': 'index page-list toc',
        'hr': 'pagebreak',
        'a': 'backlink biblioref glossref noteref',
    } | {f'h{i}': 'subtitle' for i in range(1, 7)}
    ans = {}
    for tag, epub_types in allowed_on.items():
        for epub_type in epub_types.split():
            ans.setdefault(epub_type, set()).add(XHTML(tag))
    return {epub_type: ('doc-' + epub_type.replace('-', ''), frozenset(tags)) for epub_type, tags in ans.items()}


ROLE_FOR_EPUB_TYPE = _roles()
# Elements that accept any role, from ARIA in HTML. Not included are <a> with
# a href, <figure> with a <figcaption> and table cells and rows, which accept
# any role only in some circumstances
ACCEPTS_ANY_ROLE = frozenset(
    map(
        XHTML,
        (
            'abbr address b bdi bdo blockquote canvas cite code data del dfn div em hgroup i ins kbd mark output p pre q'
            ' rp rt ruby s samp small span strong sub sup table tbody tfoot thead time u var'
        ).split(),
    )
)
A, FIGURE, FIGCAPTION = XHTML('a'), XHTML('figure'), XHTML('figcaption')


def accepts_any_role(elem) -> bool:
    if elem.tag in ACCEPTS_ANY_ROLE:
        return True
    if elem.tag == A:
        return elem.get('href') is None
    if elem.tag == FIGURE:
        return next(elem.iterchildren(FIGCAPTION), None) is None
    return False


def role_for(elem) -> str | None:
    # The role for the first epub:type of the element that has one valid on it
    for epub_type in (elem.get(EPUB_TYPE) or '').split():
        x = ROLE_FOR_EPUB_TYPE.get(epub_type)
        if x is not None and (elem.tag in x[1] or accepts_any_role(elem)):
            return x[0]
    return None


# }}}


class AccessibilityChanges(NamedTuple):
    languages: list[str] | None = None  # The new languages of the book as ISO 639-3 codes, None to leave unchanged
    html_language: str | None = None  # One of the HTML_LANGUAGE_* values below, None to leave the HTML files unchanged
    alt_text: dict[tuple[str, int], str | None] = {}  # As for set_alt_text()
    metadata: dict[str, list[str]] = {}  # As for set_accessibility_metadata()

    @property
    def is_empty(self) -> bool:
        return self.languages is None and self.html_language is None and not self.alt_text and not self.metadata


HTML_LANGUAGE_MISSING, HTML_LANGUAGE_ALL = 'missing', 'all'


def apply_accessibility_changes(container: Container, changes: AccessibilityChanges) -> bool:
    changed = False
    if changes.languages is not None:
        changed |= set_book_languages(container, changes.languages)
    if changes.html_language is not None and (lang := get_book_language_tag(container)):
        changed |= bool(set_html_language(container, html_names(container), lang, replace=changes.html_language == HTML_LANGUAGE_ALL))
    if changes.alt_text:
        changed |= bool(set_alt_text(container, changes.alt_text))
    if changes.metadata:
        changed |= set_accessibility_metadata(container, changes.metadata)
    return changed
