# License: GPLv3 Copyright: 2008, Marshall T. Vandegrift <llasram@gmail.com>

"""
CSS property propagation class.
"""

import copy
import logging
import os
import re
import unicodedata
from operator import itemgetter
from typing import TYPE_CHECKING, Literal, cast
from weakref import WeakKeyDictionary
from xml.dom import SyntaxErr as CSSSyntaxError

from css_parser import CSSParser, parseString, parseStyle, profiles, replaceUrls
from css_parser import log as css_parser_log
from css_parser import profile as cssprofiles
from css_parser.css import CSSFontFaceRule, CSSPageRule, CSSStyleRule, CSSStyleSheet, cssproperties
from css_selectors import INAPPROPRIATE_PSEUDO_CLASSES, Select, SelectorError
from tinycss.media3 import CSSMedia3Parser

from calibre import as_unicode, force_unicode
from calibre.ebooks import unit_convert
from calibre.ebooks.oeb.base import CSS_MIME, OEB_STYLES, SVG, XHTML, XHTML_NS, is_element_list, urlnormalize, xpath
from calibre.ebooks.oeb.normalize_css import DEFAULTS, normalizers
from calibre.utils.resources import get_path as P

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping
    from optparse import Values

    from css_parser.css import CSSRule, CSSStyleDeclaration
    from lxml.etree import _Element
    from tinycss.media3 import MediaQuery

    from calibre.customize.profiles import Plugin as Profile
    from calibre.ebooks.conversion.plumber import OptionValues
    from calibre.ebooks.oeb.base import OEBBook

    # (specificity, selector sequence, style, selector text, href of the stylesheet)
    type FlatRule = tuple[tuple[int, ...], list[object], style_map, str, str | None]

css_parser_log.setLevel(logging.WARNING)

_html_css_stylesheet: CSSStyleSheet | None = None


def validate_color(col: object) -> bool:
    return cssprofiles.validateWithProfile('color', col, profiles=[profiles.Profiles.CSS_LEVEL_2])[1]


def html_css_stylesheet() -> CSSStyleSheet:
    global _html_css_stylesheet
    if _html_css_stylesheet is None:
        with open(P('templates/html.css'), 'rb') as f:
            html_css = f.read().decode('utf-8')
        _html_css_stylesheet = parseString(html_css, validate=False)
    return _html_css_stylesheet


INHERITED = {
    'azimuth',
    'border-collapse',
    'border-spacing',
    'caption-side',
    'color',
    'cursor',
    'direction',
    'elevation',
    'empty-cells',
    'font-family',
    'font-size',
    'font-style',
    'font-variant',
    'font-weight',
    'letter-spacing',
    'line-height',
    'list-style-image',
    'list-style-position',
    'list-style-type',
    'orphans',
    'page-break-inside',
    'pitch-range',
    'pitch',
    'quotes',
    'richness',
    'speak-header',
    'speak-numeral',
    'speak-punctuation',
    'speak',
    'speech-rate',
    'stress',
    'text-align',
    'text-indent',
    'text-transform',
    'visibility',
    'voice-family',
    'volume',
    'white-space',
    'widows',
    'word-spacing',
    'text-shadow',
}

FONT_SIZE_NAMES = {'xx-small', 'x-small', 'small', 'medium', 'large', 'x-large', 'xx-large'}

ALLOWED_MEDIA_TYPES = frozenset({'screen', 'all', 'aural', 'amzn-kf8'})
IGNORED_MEDIA_FEATURES = frozenset(
    'width min-width max-width height min-height max-height device-width min-device-width max-device-width device-height min-device-height max-device-height aspect-ratio min-aspect-ratio max-aspect-ratio device-aspect-ratio min-device-aspect-ratio max-device-aspect-ratio color min-color max-color color-index min-color-index max-color-index monochrome min-monochrome max-monochrome -webkit-min-device-pixel-ratio resolution min-resolution max-resolution scan grid'.split()  # ruff: ignore[line-too-long]
)


def media_ok(raw: str | None) -> bool:
    if not raw:
        return True
    if raw == 'amzn-mobi':  # Optimization for the common case
        return False

    def query_ok(mq: MediaQuery) -> bool:
        matched = True
        if mq.media_type not in ALLOWED_MEDIA_TYPES:
            matched = False
        # Media queries that test for device specific features always fail
        for media_feature, expr in mq.expressions:
            if media_feature in IGNORED_MEDIA_FEATURES:
                matched = False
        return mq.negated ^ matched

    try:
        # ruff: ignore[reimplemented-builtin]
        for mq in CSSMedia3Parser().parse_stylesheet(f'@media {raw} {{}}').rules[0].media:
            if query_ok(mq):
                return True
        return False
    except Exception:
        pass
    return True


def test_media_ok() -> None:
    assert media_ok(None)
    assert media_ok('')
    assert not media_ok('amzn-mobi')
    assert media_ok('amzn-kf8')
    assert media_ok('screen')
    assert media_ok('only screen')
    assert not media_ok('not screen')
    assert not media_ok('(device-width:10px)')
    assert media_ok('screen, (device-width:10px)')
    assert not media_ok('screen and (device-width:10px)')


class style_map(dict[str, str]):
    def __init__(self) -> None:
        super().__init__()
        self.important_properties: set[str] = set()


def epub_prefix_properties() -> dict[str, tuple[str, str]]:
    ans = getattr(epub_prefix_properties, 'ans', None)
    if ans is None:
        ans = {}
        for unprefixed in (
            'writing-mode',
            'text-emphasis',
            'text-emphasis-color',
            'text-emphasis-position',
            'text-emphasis-style',
        ):
            ans[f'-epub-{unprefixed}'] = f'-webkit-{unprefixed}', unprefixed
        setattr(epub_prefix_properties, 'ans', ans)
    return ans


def cleanup_epub_prefixed_properties(style: dict[str, str]) -> None:
    epub_prefixed = epub_prefix_properties()
    for x in tuple(filter(epub_prefixed.__contains__, style)):
        val = style.pop(x)
        for key in epub_prefixed[x]:
            if key not in style:
                style[key] = val


class StylizerRules:
    def __init__(self, opts: Values | OptionValues, profile: Profile, stylesheets: list[CSSStyleSheet]) -> None:
        self.opts, self.profile, self.stylesheets = opts, profile, stylesheets

        index = 0
        self.rules: list[FlatRule] = []
        self.page_rule: dict[str, str] = {}
        self.font_face_rules: list[CSSFontFaceRule] = []
        for sheet_index, stylesheet in enumerate(stylesheets):
            href = stylesheet.href
            for rule in stylesheet.cssRules:
                if rule.type == rule.MEDIA_RULE:
                    if media_ok(rule.media.mediaText):
                        for subrule in rule.cssRules:
                            self.rules.extend(self.flatten_rule(subrule, href, index, is_user_agent_sheet=sheet_index == 0))
                            index += 1
                else:
                    self.rules.extend(self.flatten_rule(rule, href, index, is_user_agent_sheet=sheet_index == 0))
                    index = index + 1
        self.rules.sort(key=itemgetter(0))  # sort by specificity

    def flatten_rule(self, rule: CSSRule, href: str | None, index: int, is_user_agent_sheet: bool = False) -> list[FlatRule]:
        results: list[FlatRule] = []
        sheet_index = 0 if is_user_agent_sheet else 1
        if isinstance(rule, CSSStyleRule):
            style = self.flatten_style(rule.style)
            for selector in rule.selectorList:
                specificity = (sheet_index,) + selector.specificity + (index,)
                text = selector.selectorText
                selector = list(selector.seq)
                results.append((specificity, selector, style, text, href))
        elif isinstance(rule, CSSPageRule):
            style = self.flatten_style(rule.style)
            self.page_rule.update(style)
        elif isinstance(rule, CSSFontFaceRule):
            if rule.style.length > 1:
                # Ignore the meaningless font face rules generated by the
                # benighted MS Word that contain only a font-family declaration
                # and nothing else
                self.font_face_rules.append(rule)
        return results

    def flatten_style(self, cssstyle: CSSStyleDeclaration) -> style_map:
        style = style_map()
        for prop in cssstyle:
            name = prop.name
            normalizer = normalizers.get(name, None)
            is_important = prop.priority == 'important'
            if normalizer is not None:
                for key, val in normalizer(name, prop.propertyValue).items():
                    style[key] = val
                    if is_important:
                        style.important_properties.add(key)
            elif name == 'text-align':
                style['text-align'] = self._apply_text_align(prop.value)
                if is_important:
                    style.important_properties.add(name)
            else:
                style[name] = prop.value
                if is_important:
                    style.important_properties.add(name)
        if 'font-size' in style:
            size = style['font-size']
            if size == 'normal':
                size = 'medium'
            if size == 'smallest':
                size = 'xx-small'
            if size in FONT_SIZE_NAMES:
                style['font-size'] = f'{self.profile.fnames[size] / float(self.profile.fbase):.1f}rem'
        cleanup_epub_prefixed_properties(style)
        return style

    def _apply_text_align(self, text: str) -> str:
        if text in ('left', 'justify') and self.opts.change_justification in ('left', 'justify'):
            text = self.opts.change_justification
        return text

    def same_rules(self, opts: Values | OptionValues, profile: Profile, stylesheets: list[CSSStyleSheet]) -> bool:
        if self.opts != opts:
            # it's unlikely to happen, but better safe than sorry
            return False
        if self.profile != profile:
            return False
        if len(self.stylesheets) != len(stylesheets):
            return False
        return all(stylesheet == stylesheets[index] for index, stylesheet in enumerate(self.stylesheets))


class Stylizer:
    STYLESHEETS = WeakKeyDictionary()

    def __init__(
        self,
        tree: _Element,
        path: str,
        oeb: OEBBook,
        opts: Values | OptionValues,
        profile: Profile | None = None,
        extra_css: str = '',
        user_css: str = '',
        base_css: str = '',
    ) -> None:
        self.oeb, self.opts = oeb, opts
        if profile is None:
            # Use the default profile. This should really be using
            # opts.output_profile, but I don't want to risk changing it, as
            # doing so might well have hard to debug font size effects.
            from calibre.customize.ui import output_profiles

            for x in output_profiles():
                if x.short_name == 'default':
                    profile = x
                    break
        if profile is None:
            # Just in case the default profile is removed in the future :)
            profile = opts.output_profile
        self.profile: Profile = profile
        self.body_font_size: float = self.profile.fbase
        self.logger = oeb.logger
        item = oeb.manifest.hrefs[path]
        basename = os.path.basename(path)
        cssname = os.path.splitext(basename)[0] + '.css'
        stylesheets = [html_css_stylesheet()]
        if base_css:
            stylesheets.append(parseString(base_css, validate=False))
        style_tags = xpath(tree, '//*[local-name()="style" or local-name()="link"]')
        assert is_element_list(style_tags)

        # Add css_parser parsing profiles from output_profile
        for profile in self.opts.output_profile.extra_css_modules:
            cssprofiles.addProfile(profile['name'], profile['props'], profile['macros'])

        parser = CSSParser(fetcher=self._fetch_css_file, log=logging.getLogger('calibre.css'))
        for elem in style_tags:
            if elem.tag in (XHTML('style'), SVG('style')) and elem.get('type', CSS_MIME) in OEB_STYLES and media_ok(elem.get('media')):
                text = elem.text or ''
                for x in elem:
                    t = getattr(x, 'text', None)
                    if t:
                        text += '\n\n' + force_unicode(t, 'utf-8')
                    t = getattr(x, 'tail', None)
                    if t:
                        text += '\n\n' + force_unicode(t, 'utf-8')
                if text:
                    text = oeb.css_preprocessor(text)
                    # We handle @import rules separately
                    parser.setFetcher(lambda x: ('utf-8', b''))
                    stylesheet = parser.parseString(text, href=cssname, validate=False)
                    parser.setFetcher(self._fetch_css_file)
                    for rule in stylesheet.cssRules:
                        if rule.type == rule.IMPORT_RULE:
                            ihref = item.abshref(rule.href)
                            if not media_ok(rule.media.mediaText):
                                continue
                            hrefs = self.oeb.manifest.hrefs
                            if ihref not in hrefs:
                                self.logger.warn('Ignoring missing stylesheet in @import rule:', rule.href)
                                continue
                            sitem = hrefs[ihref]
                            if sitem.media_type not in OEB_STYLES:
                                self.logger.warn(f'CSS @import of non-CSS file {rule.href!r}')
                                continue
                            sdata = sitem.data
                            assert isinstance(sdata, CSSStyleSheet)  # sitem.media_type is in OEB_STYLES
                            stylesheets.append(sdata)
                    # Make links to resources absolute, since these rules will
                    # be folded into a stylesheet at the root
                    replaceUrls(stylesheet, item.abshref, ignoreImportRules=True)
                    stylesheets.append(stylesheet)
            elif (
                elem.tag == XHTML('link')
                and elem.get('href')
                and elem.get('rel', 'stylesheet').lower() == 'stylesheet'
                and elem.get('type', CSS_MIME).lower() in OEB_STYLES
                and media_ok(elem.get('media'))
            ):
                href = urlnormalize(elem.attrib['href'])
                path = item.abshref(href)
                sitem = oeb.manifest.hrefs.get(path, None)
                if sitem is None:
                    self.logger.warn(f'Stylesheet {path!r} referenced by file {item.href!r} not in manifest')
                    continue
                sdata = sitem.data
                if not isinstance(sdata, CSSStyleSheet):
                    self.logger.warn(f'Stylesheet {path!r} referenced by file {item.href!r} is not CSS')
                    continue
                stylesheets.append(sdata)
        csses = {'extra_css': extra_css, 'user_css': user_css}
        for w, x in csses.items():
            if x:
                try:
                    text = x
                    stylesheet = parser.parseString(text, href=cssname, validate=False)
                    stylesheets.append(stylesheet)
                except Exception:
                    self.logger.exception(f'Failed to parse {w}, ignoring.')
                    self.logger.debug('Bad css: ')
                    self.logger.debug(x)

        # using oeb to store the rules, page rule and font face rules
        # and generating them again if opts, profile or stylesheets are different
        # stylizer_rules is an ad-hoc attribute on OEBBook
        if (not hasattr(self.oeb, 'stylizer_rules')) or not self.oeb.stylizer_rules.same_rules(self.opts, self.profile, stylesheets):
            self.oeb.stylizer_rules = StylizerRules(self.opts, self.profile, stylesheets)
        stylizer_rules: StylizerRules = self.oeb.stylizer_rules
        self.rules = stylizer_rules.rules
        self.page_rule = stylizer_rules.page_rule
        self.font_face_rules = stylizer_rules.font_face_rules
        self.flatten_style = stylizer_rules.flatten_style

        self._styles: dict[_Element, Style] = {}
        pseudo_pat = re.compile(':{{1,2}}({})'.format('|'.join(INAPPROPRIATE_PSEUDO_CLASSES)), re.I)
        select = Select(tree, ignore_inappropriate_pseudo_classes=True)

        for _, _, cssdict, text, _ in self.rules:
            fl = pseudo_pat.search(text)
            try:
                matches = tuple(select(text))
            except SelectorError as err:
                self.logger.error(f'Ignoring CSS rule with invalid selector: {text!r} ({as_unicode(err)})')
                continue

            if fl is not None:
                fl = fl.group(1)
                if fl == 'first-letter' and getattr(self.oeb, 'plumber_output_format', '').lower() in {'mobi', 'docx'}:
                    # Fake first-letter
                    for elem in matches:
                        for x in elem.iter('*'):
                            if x.text:
                                punctuation_chars = []
                                text = str(x.text)
                                while text:
                                    category = unicodedata.category(text[0])
                                    if category[0] not in {'P', 'Z'}:
                                        break
                                    punctuation_chars.append(text[0])
                                    text = text[1:]

                                special_text = ''.join(punctuation_chars) + (text[0] if text else '')
                                span = x.makeelement(f'{{{XHTML_NS}}}span')
                                span.text = special_text
                                span.set('data-fake-first-letter', '1')
                                span.tail = text[1:]
                                x.text = None
                                x.insert(0, span)
                                self.style(span)._update_cssdict(cssdict)
                                break
                else:  # Element pseudo-class
                    for elem in matches:
                        self.style(elem)._update_pseudo_class(fl, cssdict)
            else:
                for elem in matches:
                    self.style(elem)._update_cssdict(cssdict)
        styled = xpath(tree, '//h:*[@style]')
        assert is_element_list(styled)
        for elem in styled:
            self.style(elem)._apply_style_attr(url_replacer=item.abshref)
        num_pat = re.compile(r'[0-9.]+$')
        imgs = xpath(tree, '//h:img[@width or @height]')
        assert is_element_list(imgs)
        for elem in imgs:
            style = self.style(elem)
            # Check if either height or width is not default
            is_styled = style._style.get('width', 'auto') != 'auto' or style._style.get('height', 'auto') != 'auto'
            if not is_styled:
                # Update img style dimension using width and height
                upd: dict[str, str] = {}
                for prop in ('width', 'height'):
                    val = elem.get(prop, '').strip()
                    try:
                        del elem.attrib[prop]
                    except Exception:
                        pass
                    if val:
                        if num_pat.match(val) is not None:
                            val += 'px'
                        upd[prop] = val
                if upd:
                    style._update_cssdict(upd)

    def _fetch_css_file(self, path: str) -> tuple[str | None, bytes | None]:
        hrefs = self.oeb.manifest.hrefs
        if path not in hrefs:
            self.logger.warn(f'CSS import of missing file {path!r}')
            return None, None
        item = hrefs[path]
        if item.media_type not in OEB_STYLES:
            self.logger.warn(f'CSS import of non-CSS file {path!r}')
            return None, None
        sheet = item.data
        assert isinstance(sheet, CSSStyleSheet)  # item.media_type is in OEB_STYLES
        data = sheet.cssText
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        return 'utf-8', data

    def style(self, element: _Element) -> Style:
        try:
            return self._styles[element]
        except KeyError:
            return Style(element, self)

    def stylesheet(self, name: str, font_scale: float | None = None) -> str:
        rules: list[str] = []
        for _, _, style, selector, href in self.rules:
            if href != name:
                continue
            if font_scale and 'font-size' in style and style['font-size'].endswith('pt'):
                style = copy.copy(style)
                size = float(style['font-size'][:-2])
                style['font-size'] = f'{size * font_scale:.2f}pt'
            style = ';\n    '.join(': '.join(item) for item in style.items())
            rules.append(f'{selector} {{\n    {style};\n}}')
        return '\n'.join(rules)


no_important_properties = frozenset()
svg_text_tags = tuple(map(SVG, ('text', 'textPath', 'tref', 'tspan')))


def is_only_number(x: str) -> bool:
    try:
        float(x)
        return True
    except Exception:
        return False


def is_svg_text_tag(x: object) -> bool:
    return getattr(x, 'tag', '') in svg_text_tags


class Style:
    MS_PAT = re.compile(r'^\s*(mso-|panose-|text-underline|tab-interval)')
    viewport_relative_font_size: str = ''

    def __init__(self, element: _Element, stylizer: Stylizer) -> None:
        self._element = element
        self._profile = stylizer.profile
        self._stylizer = stylizer
        self._style: dict[str, str] = style_map()
        self._fontSize: float | None = None
        self._width: float | None = None
        self._height: float | None = None
        self._lineHeight: float | str | None = None
        self._bgcolor: str | Literal[False] | None = None
        self._fgcolor: str | int | None = None
        self._pseudo_classes: dict[str, dict[str, str]] = {}
        stylizer._styles[element] = self

    def set(self, prop: str, val: str) -> None:
        self._style[prop] = val

    def drop(self, prop: str, default: str | None = None) -> str | None:
        return self._style.pop(prop, default)

    def _update_cssdict(self, cssdict: Mapping[str, str]) -> None:
        self._update_style(cssdict)

    def _update_style(self, cssdict: Mapping[str, str]) -> None:
        current_ip = getattr(self._style, 'important_properties', no_important_properties)
        if current_ip is no_important_properties:
            s = style_map()
            s.update(self._style)
            self._style = s
            current_ip = self._style.important_properties
        update_ip = getattr(cssdict, 'important_properties', no_important_properties)
        for name, val in cssdict.items():
            override = False
            if name in update_ip:
                cast('set', current_ip).add(name)
                override = True
            elif name not in current_ip:
                override = True
            if override:
                self._style[name] = val

    def _update_pseudo_class(self, name: str, cssdict: Mapping[str, str]) -> None:
        orig = self._pseudo_classes.get(name, {})
        orig.update(cssdict)
        self._pseudo_classes[name] = orig

    def _apply_style_attr(self, url_replacer: Callable[[str], str] | None = None) -> None:
        attrib = self._element.attrib
        if 'style' not in attrib:
            return
        css = attrib['style'].split(';')
        css = filter(None, (x.strip() for x in css))
        css = [y.strip() for y in css]
        css = [y for y in css if self.MS_PAT.match(y) is None]
        css = '; '.join(css)
        try:
            style = parseStyle(css, validate=False)
        except CSSSyntaxError:
            return
        if url_replacer is not None:
            replaceUrls(style, url_replacer, ignoreImportRules=True)
        self._update_style(self._stylizer.flatten_style(style))

    def _has_parent(self) -> bool:
        try:
            return self._element.getparent() is not None
        except AttributeError:
            return False  # self._element is None

    def _get_parent(self) -> Style | None:
        elem = self._element.getparent()
        if elem is None:
            return None
        return self._stylizer.style(elem)

    def __getitem__(self, name: str) -> str | float | None:  # a property value or a length converted to pts
        domname = cssproperties._toDOMname(name)
        if hasattr(self, domname):
            return getattr(self, domname)
        return self._unit_convert(self._get(name))

    def _get(self, name: str) -> str | int:
        result = self._style.get(name, None)
        if result == 'inherit' or (result is None and name in INHERITED and self._has_parent()):
            stylizer = self._stylizer
            # FIXME: for 'inherit' on the root element getparent() is None, Style() tolerates a None element
            result = stylizer.style(self._element.getparent())._get(name)  # ty: ignore[invalid-argument-type]
        if result is None:
            result = DEFAULTS[name]
        return result

    def get(self, name: str, default: str | None = None) -> str | None:
        return self._style.get(name, default)

    def _unit_convert(self, value: str | float, base: float | None = None, font: float | None = None) -> float | str:
        "Return value in pts"
        if base is None:
            base = self.width
        if not font and font != 0:
            font = self.fontSize
        return unit_convert(value, base, font, self._profile.dpi, body_font_size=self._stylizer.body_font_size)

    def pt_to_px(self, value: float) -> float:
        return (self._profile.dpi / 72) * value

    @property
    def color(self) -> str | int:
        if self._fgcolor is None:
            val = self._get('color')
            if val and validate_color(val):
                self._fgcolor = val
            else:
                self._fgcolor = DEFAULTS['color']
        return self._fgcolor

    @property
    def backgroundColor(self) -> str | None:
        """
        Return the background color by parsing both the background-color and
        background shortcut properties. Note that inheritance/default values
        are not used. None is returned if no background color is set.
        """

        if self._bgcolor is None:
            col = None
            val = self._style.get('background-color', None)
            if val and validate_color(val):
                col = val
            else:
                val = self._style.get('background', None)
                if val is not None:
                    try:
                        style = parseStyle('background: ' + val, validate=False)
                        css_val = style.getProperty('background').propertyValue
                        try:
                            val_list = list(css_val)
                        except Exception:
                            # css_val is CSSPrimitiveValue
                            val_list = [css_val]
                        for c in val_list:
                            c = c.cssText
                            if isinstance(c, bytes):
                                c = c.decode('utf-8', 'replace')
                            if validate_color(c):
                                col = c
                                break
                    except Exception:
                        pass
            if col is None:
                self._bgcolor = False
            else:
                self._bgcolor = col
        return self._bgcolor or None

    @property
    def fontSize(self) -> float:
        def normalize_fontsize(value: str, base: float) -> float:
            value = value.replace('"', '').replace("'", '')
            result: float | None = None
            factor = None
            if value == 'inherit':
                value = base  # ty: ignore[invalid-assignment] a float, handled by _unit_convert() below
            if value in FONT_SIZE_NAMES:
                result = self._profile.fnames[value]
            elif value == 'smaller':
                factor = 1.0 / 1.2
                for _, _, size in self._profile.fsizes:
                    if base <= size:
                        break
                    factor = None
                    result = size
            elif value == 'larger':
                factor = 1.2
                for _, _, size in reversed(self._profile.fsizes):
                    if base >= size:
                        break
                    factor = None
                    result = size
            else:
                converted = self._unit_convert(value, base=base, font=base)
                if not isinstance(converted, (int, float)):  # _unit_convert() returns int, float or str
                    return base
                result = converted
                if result < 0:
                    result = normalize_fontsize('smaller', base)
            if factor:
                result = factor * base
            return cast('float', result)  # result is always set when factor is None

        if self._fontSize is None:
            result = None
            parent = self._get_parent()
            if parent is not None:
                base = parent.fontSize
            else:
                base = self._profile.fbase
            if 'font-size' in self._style:
                size = self._style['font-size']
                if is_svg_text_tag(self._element) and (size.endswith('px') or is_only_number(size)):
                    self.viewport_relative_font_size = size
                result = normalize_fontsize(size, base)
            else:
                result = base
            self._fontSize = result
        return self._fontSize

    def img_dimension(self, attr: str, img_size: float) -> float:
        ans: float | None = None
        parent = self._get_parent()
        if parent is not None:
            base = getattr(parent, attr)
        else:
            base = getattr(self._profile, attr + '_pts')
        x = self._style.get(attr)
        if x is not None:
            if x == 'auto':
                ans = cast('float', self._unit_convert(str(img_size) + 'px', base=base))  # px lengths always convert
            else:
                cx = self._unit_convert(x, base=base)
                if isinstance(cx, (int, float)):  # _unit_convert() returns int, float or str
                    ans = cx
        if ans is None:
            x = self._element.get(attr)
            if x is not None:
                cx = self._unit_convert(x + 'px', base=base)
                if isinstance(cx, (int, float)):
                    ans = cx
        if ans is None:
            ans = cast('float', self._unit_convert(str(img_size) + 'px', base=base))  # px lengths always convert
        maa = self._style.get('max-' + attr)
        if maa is not None:
            cx = self._unit_convert(maa, base=base)
            if isinstance(cx, (int, float)) and (ans is None or cx < ans):
                ans = cx
        return ans

    def img_size(self, width: float, height: float) -> tuple[float, float]:
        "Return the final size of an <img> given that it points to an image of size widthxheight"
        w, h = self._get('width'), self._get('height')
        answ, ansh = self.img_dimension('width', width), self.img_dimension('height', height)
        if w == 'auto' and h != 'auto':
            answ = (float(width) / height) * ansh
        elif h == 'auto' and w != 'auto':
            ansh = (float(height) / width) * answ
        return answ, ansh

    @property
    def width(self) -> float:
        if self._width is None:
            width = None
            base = None
            parent = self._get_parent()
            if parent is not None:
                base = parent.width
            else:
                base = self._profile.width_pts
            if 'width' in self._element.attrib:
                width = self._element.attrib['width']
            elif 'width' in self._style:
                width = self._style['width']
            if not width or width == 'auto':
                result = base
            else:
                result = self._unit_convert(width, base=base)
            if isinstance(result, (str, bytes)):
                result = self._profile.width
            self._width = result
            if 'max-width' in self._style:
                result = self._unit_convert(self._style['max-width'], base=base)
                if isinstance(result, (str, bytes)):
                    result = self._width
                self._width = min(self._width, result)

        return self._width

    @property
    def parent_width(self) -> float:
        parent = self._get_parent()
        if parent is None:
            return self.width
        return parent.width

    @property
    def height(self) -> float:
        if self._height is None:
            height = None
            base = None
            parent = self._get_parent()
            if parent is not None:
                base = parent.height
            else:
                base = self._profile.height_pts
            if 'height' in self._element.attrib:
                height = self._element.attrib['height']
            elif 'height' in self._style:
                height = self._style['height']
            if not height or height == 'auto':
                result = base
            else:
                result = self._unit_convert(height, base=base)
            if isinstance(result, (str, bytes)):
                result = self._profile.height
            self._height = result
            if 'max-height' in self._style:
                result = self._unit_convert(self._style['max-height'], base=base)
                if isinstance(result, (str, bytes)):
                    result = self._height
                self._height = min(self._height, result)

        return self._height

    @property
    def lineHeight(self) -> float | str:
        if self._lineHeight is None:
            result = None
            parent = self._get_parent()
            if 'line-height' in self._style:
                lineh = self._style['line-height']
                if lineh == 'normal':
                    lineh = '1.2'
                try:
                    result = float(lineh) * self.fontSize
                except ValueError:
                    result = self._unit_convert(lineh, base=self.fontSize)
            elif parent is not None:
                # TODO: proper inheritance
                result = parent.lineHeight
            else:
                result = 1.2 * self.fontSize
            self._lineHeight = result
        return self._lineHeight

    @property
    def effective_text_decoration(self) -> str | None:
        """
        Browsers do this creepy thing with text-decoration where even though the
        property is not inherited, it looks like it is because containing
        blocks apply it. The actual algorithm is utterly ridiculous, see
        http://reference.sitepoint.com/css/text-decoration
        This matters for MOBI output, where text-decoration is mapped to <u>
        and <st> tags. Trying to implement the actual algorithm is too much
        work, so we just use a simple fake that should cover most cases.
        """
        css = self._style.get('text-decoration', None)
        pcss = None
        parent = self._get_parent()
        if parent is not None:
            pcss = parent._style.get('text-decoration', None)
        if css in ('none', None, 'inherit') and pcss not in (None, 'none'):
            return pcss
        return css

    @property
    def first_vertical_align(self) -> float | str | None:
        """For docx output where tags are not nested, we cannot directly
        simulate the HTML vertical-align rendering model. Instead use the
        approximation of considering the first non-default vertical-align"""
        val = self['vertical-align']
        if val != 'baseline':
            raw_val = cast('str', self._get('vertical-align'))  # DEFAULTS['vertical-align'] is a str
            if '%' in raw_val:
                line_height = self.lineHeight
                if isinstance(line_height, str):  # unparseable line-height, use the value for line-height: normal
                    line_height = 1.2 * self.fontSize
                val = self._unit_convert(raw_val, base=line_height)
            return val
        parent = self._get_parent()
        if parent is not None and isinstance(display := parent['display'], str) and 'inline' in display:
            return parent.first_vertical_align

    @property
    def marginTop(self) -> float | str:
        return self._unit_convert(self._get('margin-top'), base=self.parent_width)

    @property
    def marginBottom(self) -> float | str:
        return self._unit_convert(self._get('margin-bottom'), base=self.parent_width)

    @property
    def marginLeft(self) -> float | str:
        return self._unit_convert(self._get('margin-left'), base=self.parent_width)

    @property
    def marginRight(self) -> float | str:
        return self._unit_convert(self._get('margin-right'), base=self.parent_width)

    @property
    def paddingTop(self) -> float | str:
        return self._unit_convert(self._get('padding-top'), base=self.parent_width)

    @property
    def paddingBottom(self) -> float | str:
        return self._unit_convert(self._get('padding-bottom'), base=self.parent_width)

    @property
    def paddingLeft(self) -> float | str:
        return self._unit_convert(self._get('padding-left'), base=self.parent_width)

    @property
    def paddingRight(self) -> float | str:
        return self._unit_convert(self._get('padding-right'), base=self.parent_width)

    def __str__(self) -> str:
        items = sorted(self._style.items())
        return '; '.join(f'{key}: {val}' for key, val in items)

    def cssdict(self) -> dict[str, str]:
        return dict(self._style)

    def pseudo_classes(self, filter_css: Collection[str]) -> dict[str, dict[str, str]]:
        if filter_css:
            css = copy.deepcopy(self._pseudo_classes)
            for psel, cssdict in css.items():
                for k in filter_css:
                    cssdict.pop(k, None)
        else:
            css = self._pseudo_classes
        return {k: v for k, v in css.items() if v}

    @property
    def is_hidden(self) -> bool:

        return self._style.get('display') == 'none' or self._style.get('visibility') == 'hidden'
