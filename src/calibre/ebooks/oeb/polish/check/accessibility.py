#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

# Checks for common accessibility problems, based on the EPUB Accessibility
# specification and WCAG, see https://www.w3.org/TR/epub-a11y-11/

from calibre import prepare_string_for_xml as xml
from calibre.ebooks.oeb.base import OEB_DOCS, OPF, XHTML, XML
from calibre.ebooks.oeb.polish.check.base import INFO, WARN, BaseError
from calibre.ebooks.oeb.polish.toc import find_existing_nav_toc
from calibre.utils.localization import _, canonicalize_lang, ngettext

HEADINGS = {XHTML(f'h{i}'): i for i in range(1, 7)}
IMG = XHTML('img')
LANG_ATTRS = ('lang', XML('lang'))
ACCESSIBILITY_PROPERTIES = ('schema:accessMode', 'schema:accessModeSufficient', 'schema:accessibilityFeature', 'schema:accessibilityHazard')
SUMMARY_PROPERTY = 'schema:accessibilitySummary'


def html_names(container):
    for name, mt in container.mime_map.items():
        if mt in OEB_DOCS:
            yield name


def is_decorative(img):
    return img.get('role') in ('presentation', 'none') or img.get('aria-hidden') == 'true'


def images_without_alt(root):
    return [img for img in root.iter(IMG) if img.get('alt') is None and not is_decorative(img)]


def book_language(container):
    # The language as specified in the OPF, used as is since it is usually a
    # BCP 47 language tag, which is what the lang attribute needs
    for elem in container.opf_xpath('//dc:language'):
        raw = (elem.text or '').strip()
        if raw and canonicalize_lang(raw):
            return raw


class MissingAltText(BaseError):
    level = WARN
    has_multiple_locations = True
    RULE_NAME = _('Image without alternative text')
    HELP = _(
        'Images should have alternative text, specified with the alt attribute, that describes them for'
        ' readers who cannot see them, such as people using screen readers. For images that are purely'
        ' decorative, use an empty alt attribute, like this: alt=""'
    )

    def __init__(self, name, lines):
        BaseError.__init__(
            self, ngettext('An image has no alternative text', '{} images have no alternative text', len(lines)).format(len(lines)), name, lines[0]
        )
        self.all_locations = [(name, lnum, None) for lnum in lines]


class MissingLanguage(BaseError):
    level = WARN
    has_multiple_locations = True
    RULE_NAME = _('HTML file without a language')

    def __init__(self, names, lang):
        msg = ngettext('An HTML file does not specify its language', '{} HTML files do not specify their language', len(names))
        BaseError.__init__(self, msg.format(len(names)), names[0][0])
        self.all_locations = [(name, lnum, None) for name, lnum in names]
        self.names = [name for name, lnum in names]
        self.HELP = _(
            'HTML files should specify the language of their text with the lang attribute on the <html> tag.'
            ' Screen readers and text-to-speech engines use it to pronounce the text correctly.'
        )
        self.lang = lang
        if lang:
            self.INDIVIDUAL_FIX = _('Set the language of these files to the language of the book: {}').format(lang)
        else:
            self.HELP += ' ' + _('Set the language of the book in the metadata so that this can be fixed automatically.')
        self.HELP = xml(self.HELP)

    def __call__(self, container):
        changed = False
        for name in self.names:
            root = container.parsed(name)
            if not any(root.get(attr) for attr in LANG_ATTRS):
                for attr in LANG_ATTRS:
                    root.set(attr, self.lang)
                container.dirty(name)
                changed = True
        return changed


class SkippedHeadingLevel(BaseError):
    level = INFO
    has_multiple_locations = True
    RULE_NAME = _('Heading levels skipped')
    HELP = _(
        'Headings should not skip levels, for example, an <h2> heading should be followed by a heading at most one'
        ' level lower, that is an <h3>, not an <h4>. Screen readers allow navigating by headings and skipped'
        ' levels make the structure of the text harder to follow.'
    )

    def __init__(self, name, lines):
        BaseError.__init__(self, ngettext('A heading skips a level', '{} headings skip a level', len(lines)).format(len(lines)), name, lines[0])
        self.HELP = xml(self.HELP)
        self.all_locations = [(name, lnum, None) for lnum in lines]


def accessibility_metadata(container):
    # Accessibility metadata that can be determined from the contents of the book
    has_images = has_headings = False
    all_images_have_alt = True
    for name in html_names(container):
        root = container.parsed(name)
        for img in root.iter(IMG):
            if not is_decorative(img):
                has_images = True
                if img.get('alt') is None:
                    all_images_have_alt = False
        if not has_headings and next(root.iter(*HEADINGS), None) is not None:
            has_headings = True
    ans = {
        'schema:accessMode': ['textual', 'visual'] if has_images else ['textual'],
        'schema:accessModeSufficient': ['textual'],
        'schema:accessibilityHazard': ['unknown'],
    }
    if has_images:
        ans['schema:accessModeSufficient'] = ['textual', 'textual,visual'] if all_images_have_alt else ['textual,visual']
    features = []
    if find_existing_nav_toc(container):
        features.append('tableOfContents')
    if has_headings:
        features.append('structuralNavigation')
    if has_images and all_images_have_alt:
        features.append('alternativeText')
    ans['schema:accessibilityFeature'] = features or ['none']
    return ans


def existing_properties(container):
    return {m.get('property') for m in container.opf_xpath('//opf:metadata/opf:meta[@property]') if (m.text or '').strip() and not m.get('refines')}


class MissingAccessibilityMetadata(BaseError):
    level = WARN
    RULE_NAME = _('Missing accessibility metadata')
    INDIVIDUAL_FIX = _('Add the accessibility metadata that can be determined from the contents of the book')

    def __init__(self, name, missing):
        BaseError.__init__(self, _('The book does not have accessibility metadata'), name)
        self.missing = missing
        self.HELP = xml(
            _(
                'Accessibility metadata tells readers, reading systems and online stores about the accessibility'
                ' of the book. The EPUB Accessibility specification calls for these properties, which are missing: {}.'
                ' The automatic fix fills them in based on the contents of the book, for example, whether it has images'
                ' and whether they have alternative text. It sets the accessibility hazards to "unknown", review them'
                ' and change them if you know the book does not contain hazards such as flashing content.'
            ).format(', '.join(missing))
        )

    def __call__(self, container):
        missing = set(ACCESSIBILITY_PROPERTIES) - existing_properties(container)
        if not missing:
            return False
        values = accessibility_metadata(container)
        metadata = container.opf_xpath('//opf:metadata')[0]
        for prop in ACCESSIBILITY_PROPERTIES:
            if prop in missing:
                for val in values[prop]:
                    meta = metadata.makeelement(OPF('meta'), property=prop)
                    meta.text = val
                    container.insert_into_xml(metadata, meta)
        container.dirty(container.opf_name)
        return True


class MissingAccessibilitySummary(BaseError):
    level = INFO
    RULE_NAME = _('Missing accessibility summary')

    def __init__(self, name):
        BaseError.__init__(self, _('The book does not have an accessibility summary'), name)
        self.HELP = xml(
            _(
                'The accessibility summary is a short description of the accessibility of the book for readers,'
                ' for example: "This publication has a table of contents and all images have alternative text."'
                ' Add it to the OPF like this: {}'
            ).format(f'<meta property="{SUMMARY_PROPERTY}">…</meta>')
        )


def check_accessibility(container):
    errors = []
    missing_lang = []
    for name in html_names(container):
        root = container.parsed(name)
        if not any(root.get(attr) for attr in LANG_ATTRS):
            missing_lang.append((name, root.sourceline))
        lines = [img.sourceline for img in images_without_alt(root)]
        if lines:
            errors.append(MissingAltText(name, lines))
        skipped, prev = [], None
        for heading in root.iter(*HEADINGS):
            level = HEADINGS[heading.tag]
            if prev is not None and level > prev + 1:
                skipped.append(heading.sourceline)
            prev = level
        if skipped:
            errors.append(SkippedHeadingLevel(name, skipped))
    if missing_lang:
        errors.append(MissingLanguage(missing_lang, book_language(container)))

    if container.opf_version_parsed.major > 2:
        existing = existing_properties(container)
        missing = [p for p in ACCESSIBILITY_PROPERTIES if p not in existing]
        if missing:
            errors.append(MissingAccessibilityMetadata(container.opf_name, missing))
        if SUMMARY_PROPERTY not in existing:
            errors.append(MissingAccessibilitySummary(container.opf_name))
    return errors
