#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

# Checks for common accessibility problems, based on the EPUB Accessibility
# specification and WCAG, see https://www.w3.org/TR/epub-a11y-11/

from calibre import prepare_string_for_xml as xml
from calibre.ebooks.oeb.base import OEB_DOCS, SVG, XHTML, XPath
from calibre.ebooks.oeb.polish.accessibility import has_language, is_decorative, role_for, set_html_language
from calibre.ebooks.oeb.polish.check.base import INFO, WARN, BaseError
from calibre.ebooks.oeb.polish.opf import get_book_language_tag
from calibre.utils.localization import _, ngettext

HEADINGS = {XHTML(f'h{i}'): i for i in range(1, 7)}
IMG = XHTML('img')
SVG_ROOT, SVG_TITLE = SVG('svg'), SVG('title')
ACCESSIBILITY_PROPERTIES = ('schema:accessMode', 'schema:accessModeSufficient', 'schema:accessibilityFeature', 'schema:accessibilityHazard')
SUMMARY_PROPERTY = 'schema:accessibilitySummary'
WITH_EPUB_TYPE = XPath('//*[@epub:type]')


def html_names(container):
    # Sorted so that problems are reported in the same order on every system
    return sorted(name for name, mt in container.mime_map.items() if mt in OEB_DOCS)


def svg_has_text_alternative(svg):
    if (svg.get('aria-label') or '').strip() or (svg.get('aria-labelledby') or '').strip():
        return True
    return any((title.text or '').strip() for title in svg.iterchildren(SVG_TITLE))


def images_without_alt(root):
    ans = [img for img in root.iter(IMG) if img.get('alt') is None and not is_decorative(img)]
    # Only outermost <svg> elements, as nested ones are part of the same image
    ans.extend(
        svg for svg in root.iter(SVG_ROOT) if next(svg.iterancestors(SVG_ROOT), None) is None and not is_decorative(svg) and not svg_has_text_alternative(svg)
    )
    return sorted(ans, key=lambda x: x.sourceline)


def elements_without_role(root):
    # Elements that have no role, but whose epub:type has a corresponding
    # role. Elements that already have a role are left alone, even if it is
    # different, as it was chosen by the author.
    for elem in WITH_EPUB_TYPE(root):
        if not (elem.get('role') or '').strip() and (role := role_for(elem)):
            yield elem, role


class MissingAltText(BaseError):
    level = WARN
    has_multiple_locations = True
    RULE_NAME = _('Image without alternative text')
    HELP = xml(
        _(
            'Images should have alternative text, specified with the alt attribute, that describes them for'
            ' readers who cannot see them, such as people using screen readers. For images that are purely'
            ' decorative, use an empty alt attribute, like this: alt="". For SVG images, add a <title> element'
            ' as the first child of the <svg> element, or for decorative SVG images, the attribute aria-hidden="true".'
            ' The alternative text of images, including inline SVG images, can be edited in one place with Tools->Accessibility.'
        )
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
        BaseError.__init__(self, msg.format(len(names)), names[0][0], names[0][1])
        self.all_locations = [(name, lnum, None) for name, lnum in names]
        self.names = [name for name, lnum in names]
        self.lang = lang
        help = _(
            'HTML files should specify the language of their text with the lang attribute on the <html> tag.'
            ' Screen readers and text-to-speech engines use it to pronounce the text correctly.'
        )
        if lang:
            self.INDIVIDUAL_FIX = xml(_('Set the language of these files to the language of the book: {}').format(lang))
        else:
            help += ' ' + _('Set the language of the book with Tools->Accessibility so that this can be fixed automatically.')
        self.HELP = xml(help)

    def __call__(self, container):
        return bool(set_html_language(container, self.names, self.lang))


class SkippedHeadingLevel(BaseError):
    level = INFO
    has_multiple_locations = True
    RULE_NAME = _('Heading levels skipped')
    HELP = xml(
        _(
            'Headings should not skip levels, for example, an <h2> heading should be followed by a heading at most one'
            ' level lower, that is an <h3>, not an <h4>. Screen readers allow navigating by headings and skipped'
            ' levels make the structure of the text harder to follow.'
        )
    )

    def __init__(self, name, lines):
        BaseError.__init__(self, ngettext('A heading skips a level', '{} headings skip a level', len(lines)).format(len(lines)), name, lines[0])
        self.all_locations = [(name, lnum, None) for lnum in lines]


class MissingRole(BaseError):
    level = INFO
    has_multiple_locations = True
    RULE_NAME = _('Structural semantics without ARIA roles')
    INDIVIDUAL_FIX = _('Add the matching ARIA roles')
    HELP = xml(
        _(
            'The epub:type attribute is used by reading systems, but screen readers should not be relied on to'
            ' understand it, they use the role attribute instead. For example, a link with epub:type="noteref" should also have role="doc-noteref" so'
            ' that screen readers announce it as a link to a note. The automatic fix adds the role that corresponds to'
            ' the epub:type, if it is allowed on that element.'
        )
    )

    def __init__(self, name, lines):
        BaseError.__init__(
            self,
            ngettext('An element has an epub:type but no ARIA role', '{} elements have an epub:type but no ARIA role', len(lines)).format(len(lines)),
            name,
            lines[0],
        )
        self.all_locations = [(name, lnum, None) for lnum in lines]

    def __call__(self, container):
        root = container.parsed(self.name)
        changed = False
        for elem, role in elements_without_role(root):
            elem.set('role', role)
            changed = True
        if changed:
            container.dirty(self.name)
        return changed


def existing_properties(container):
    return {m.get('property') for m in container.opf_xpath('//opf:metadata/opf:meta[@property]') if (m.text or '').strip() and not m.get('refines')}


class MissingAccessibilityMetadata(BaseError):
    # There is no automatic fix as this metadata makes claims about the book
    # that cannot be reliably determined from its contents, for example,
    # whether the images are adequately described by text
    level = WARN
    RULE_NAME = _('Missing accessibility metadata')

    def __init__(self, name, missing):
        BaseError.__init__(self, _('The book does not have accessibility metadata'), name)
        self.missing = missing
        self.HELP = xml(
            _(
                'Accessibility metadata tells readers, reading systems and online stores about the accessibility'
                ' of the book. The EPUB Accessibility specification calls for these properties, which are missing: {0}.'
                ' Add them with Tools->Accessibility, or to the OPF directly, one value per tag, like this: {1}'
            ).format(', '.join(missing), '<meta property="schema:accessMode">textual</meta>')
        )


class MissingAccessibilitySummary(BaseError):
    level = INFO
    RULE_NAME = _('Missing accessibility summary')

    def __init__(self, name):
        BaseError.__init__(self, _('The book does not have an accessibility summary'), name)
        self.HELP = xml(
            _(
                'The accessibility summary is a short description of the accessibility of the book for readers,'
                ' for example: "This publication has a table of contents and all images have alternative text."'
                ' Add it with Tools->Accessibility, or to the OPF directly, like this: {}'
            ).format(f'<meta property="{SUMMARY_PROPERTY}">…</meta>')
        )


def check_accessibility(container):
    errors = []
    missing_lang = []
    is_epub3 = container.opf_version_parsed.major > 2
    for name in html_names(container):
        root = container.parsed(name)
        if not has_language(root):
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
        # The role attribute is not valid in the XHTML 1.1 used by EPUB 2
        if is_epub3:
            lines = [elem.sourceline for elem, role in elements_without_role(root)]
            if lines:
                errors.append(MissingRole(name, lines))
    if missing_lang:
        errors.append(MissingLanguage(missing_lang, get_book_language_tag(container)))

    if is_epub3:
        existing = existing_properties(container)
        missing = [p for p in ACCESSIBILITY_PROPERTIES if p not in existing]
        if missing:
            errors.append(MissingAccessibilityMetadata(container.opf_name, missing))
        if SUMMARY_PROPERTY not in existing:
            errors.append(MissingAccessibilitySummary(container.opf_name))
    return errors
