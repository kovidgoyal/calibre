# -*- encoding: utf-8 -*-

'''
CSS property propagation class.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import os
import itertools
import re
import logging
import copy
from weakref import WeakKeyDictionary
from xml.dom import SyntaxErr as CSSSyntaxError
import cssutils
from cssutils.css import CSSStyleRule, CSSPageRule, CSSStyleDeclaration, \
    CSSValueList, CSSFontFaceRule, cssproperties
from cssutils import profile as cssprofiles
from lxml import etree
from lxml.cssselect import css_to_xpath, ExpressionError, SelectorSyntaxError
from calibre.ebooks.oeb.base import XHTML, XHTML_NS, CSS_MIME, OEB_STYLES
from calibre.ebooks.oeb.base import XPNSMAP, xpath, urlnormalize
from calibre.ebooks.oeb.profile import PROFILES

_html_css_stylesheet = None

def html_css_stylesheet():
    global _html_css_stylesheet
    if _html_css_stylesheet is None:
        html_css = open(P('templates/html.css'), 'rb').read()
        _html_css_stylesheet = cssutils.parseString(html_css)
        _html_css_stylesheet.namespaces['h'] = XHTML_NS
    return _html_css_stylesheet

XHTML_CSS_NAMESPACE = '@namespace "%s";\n' % XHTML_NS

INHERITED = set(['azimuth', 'border-collapse', 'border-spacing',
                 'caption-side', 'color', 'cursor', 'direction', 'elevation',
                 'empty-cells', 'font-family', 'font-size', 'font-style',
                 'font-variant', 'font-weight', 'letter-spacing',
                 'line-height', 'list-style-image', 'list-style-position',
                 'list-style-type', 'orphans', 'page-break-inside',
                 'pitch-range', 'pitch', 'quotes', 'richness', 'speak-header',
                 'speak-numeral', 'speak-punctuation', 'speak', 'speech-rate',
                 'stress', 'text-align', 'text-indent', 'text-transform',
                 'visibility', 'voice-family', 'volume', 'white-space',
                 'widows', 'word-spacing'])

DEFAULTS = {'azimuth': 'center', 'background-attachment': 'scroll',
            'background-color': 'transparent', 'background-image': 'none',
            'background-position': '0% 0%', 'background-repeat': 'repeat',
            'border-bottom-color': ':color', 'border-bottom-style': 'none',
            'border-bottom-width': 'medium', 'border-collapse': 'separate',
            'border-left-color': ':color', 'border-left-style': 'none',
            'border-left-width': 'medium', 'border-right-color': ':color',
            'border-right-style': 'none', 'border-right-width': 'medium',
            'border-spacing': 0, 'border-top-color': ':color',
            'border-top-style': 'none', 'border-top-width': 'medium', 'bottom':
            'auto', 'caption-side': 'top', 'clear': 'none', 'clip': 'auto',
            'color': 'black', 'content': 'normal', 'counter-increment': 'none',
            'counter-reset': 'none', 'cue-after': 'none', 'cue-before': 'none',
            'cursor': 'auto', 'direction': 'ltr', 'display': 'inline',
            'elevation': 'level', 'empty-cells': 'show', 'float': 'none',
            'font-family': 'serif', 'font-size': 'medium', 'font-style':
            'normal', 'font-variant': 'normal', 'font-weight': 'normal',
            'height': 'auto', 'left': 'auto', 'letter-spacing': 'normal',
            'line-height': 'normal', 'list-style-image': 'none',
            'list-style-position': 'outside', 'list-style-type': 'disc',
            'margin-bottom': 0, 'margin-left': 0, 'margin-right': 0,
            'margin-top': 0, 'max-height': 'none', 'max-width': 'none',
            'min-height': 0, 'min-width': 0, 'orphans': '2',
            'outline-color': 'invert', 'outline-style': 'none',
            'outline-width': 'medium', 'overflow': 'visible', 'padding-bottom':
            0, 'padding-left': 0, 'padding-right': 0, 'padding-top': 0,
            'page-break-after': 'auto', 'page-break-before': 'auto',
            'page-break-inside': 'auto', 'pause-after': 0, 'pause-before':
            0, 'pitch': 'medium', 'pitch-range': '50', 'play-during': 'auto',
            'position': 'static', 'quotes': u"'“' '”' '‘' '’'", 'richness':
            '50', 'right': 'auto', 'speak': 'normal', 'speak-header': 'once',
            'speak-numeral': 'continuous', 'speak-punctuation': 'none',
            'speech-rate': 'medium', 'stress': '50', 'table-layout': 'auto',
            'text-align': 'auto', 'text-decoration': 'none', 'text-indent':
            0, 'text-transform': 'none', 'top': 'auto', 'unicode-bidi':
            'normal', 'vertical-align': 'baseline', 'visibility': 'visible',
            'voice-family': 'default', 'volume': 'medium', 'white-space':
            'normal', 'widows': '2', 'width': 'auto', 'word-spacing': 'normal',
            'z-index': 'auto'}

FONT_SIZE_NAMES = set(['xx-small', 'x-small', 'small', 'medium', 'large',
                       'x-large', 'xx-large'])


class CSSSelector(etree.XPath):
    MIN_SPACE_RE = re.compile(r' *([>~+]) *')
    LOCAL_NAME_RE = re.compile(r"(?<!local-)name[(][)] *= *'[^:]+:")

    def __init__(self, css, namespaces=XPNSMAP):
        css = self.MIN_SPACE_RE.sub(r'\1', css)
        try:
            path = css_to_xpath(css)
        except UnicodeEncodeError: # Bug in css_to_xpath
            path = '/'
        except NotImplementedError: # Probably a subselect like :hover
            path = '/'
        path = self.LOCAL_NAME_RE.sub(r"local-name() = '", path)
        etree.XPath.__init__(self, path, namespaces=namespaces)
        self.css = css

    def __repr__(self):
        return '<%s %s for %r>' % (
            self.__class__.__name__,
            hex(abs(id(self)))[2:],
            self.css)


class Stylizer(object):
    STYLESHEETS = WeakKeyDictionary()

    def __init__(self, tree, path, oeb, opts, profile=PROFILES['PRS505'],
            extra_css='', user_css=''):
        self.oeb, self.opts = oeb, opts
        self.profile = profile
        self.logger = oeb.logger
        item = oeb.manifest.hrefs[path]
        basename = os.path.basename(path)
        cssname = os.path.splitext(basename)[0] + '.css'
        stylesheets = [html_css_stylesheet()]
        head = xpath(tree, '/h:html/h:head')
        if head:
            head = head[0]
        else:
            head = []

        # Add cssutils parsing profiles from output_profile
        for profile in self.opts.output_profile.extra_css_modules:
            cssutils.profile.addProfile(profile['name'],
                                        profile['props'],
                                        profile['macros'])

        parser = cssutils.CSSParser(fetcher=self._fetch_css_file,
                log=logging.getLogger('calibre.css'))
        self.font_face_rules = []
        for elem in head:
            if elem.tag == XHTML('style') and elem.text \
               and elem.get('type', CSS_MIME) in OEB_STYLES:
                text = XHTML_CSS_NAMESPACE + elem.text
                text = oeb.css_preprocessor(text)
                stylesheet = parser.parseString(text, href=cssname)
                stylesheet.namespaces['h'] = XHTML_NS
                stylesheets.append(stylesheet)
            elif elem.tag == XHTML('link') and elem.get('href') \
                 and elem.get('rel', 'stylesheet').lower() == 'stylesheet' \
                 and elem.get('type', CSS_MIME).lower() in OEB_STYLES:
                href = urlnormalize(elem.attrib['href'])
                path = item.abshref(href)
                sitem = oeb.manifest.hrefs.get(path, None)
                if sitem is None:
                    self.logger.warn(
                        'Stylesheet %r referenced by file %r not in manifest' %
                        (path, item.href))
                    continue
                if not hasattr(sitem.data, 'cssRules'):
                    self.logger.warn(
                    'Stylesheet %r referenced by file %r is not CSS'%(path,
                        item.href))
                    continue
                stylesheets.append(sitem.data)
        csses = {'extra_css':extra_css, 'user_css':user_css}
        for w, x in csses.items():
            if x:
                try:
                    text = XHTML_CSS_NAMESPACE + x
                    stylesheet = parser.parseString(text, href=cssname)
                    stylesheet.namespaces['h'] = XHTML_NS
                    stylesheets.append(stylesheet)
                except:
                    self.logger.exception('Failed to parse %s, ignoring.'%w)
                    self.logger.debug('Bad css: ')
                    self.logger.debug(x)
        rules = []
        index = 0
        self.stylesheets = set()
        self.page_rule = {}
        for stylesheet in stylesheets:
            href = stylesheet.href
            self.stylesheets.add(href)
            for rule in stylesheet.cssRules:
                rules.extend(self.flatten_rule(rule, href, index))
                index = index + 1
        rules.sort()
        self.rules = rules
        self._styles = {}
        class_sel_pat = re.compile(r'\.[a-z]+', re.IGNORECASE)
        capital_sel_pat = re.compile(r'h|[A-Z]+')
        for _, _, cssdict, text, _ in rules:
            fl = ':first-letter' in text
            if fl:
                text = text.replace(':first-letter', '')
            try:
                selector = CSSSelector(text)
            except (AssertionError, ExpressionError, etree.XPathSyntaxError,
                    NameError, # thrown on OS X instead of SelectorSyntaxError
                    SelectorSyntaxError):
                continue
            matches = selector(tree)

            if not matches:
                ntext = capital_sel_pat.sub(lambda m: m.group().lower(), text)
                if ntext != text:
                    self.logger.warn('Transformed CSS selector', text, 'to',
                            ntext)
                    selector = CSSSelector(ntext)
                    matches = selector(tree)

            if not matches and class_sel_pat.match(text) and text.lower() != text:
                found = False
                ltext = text.lower()
                for x in tree.xpath('//*[@class]'):
                    if ltext.endswith('.'+x.get('class').lower()):
                        matches.append(x)
                        found = True
                if found:
                    self.logger.warn('Ignoring case mismatches for CSS selector: %s in %s'
                        %(text, item.href))
            if fl:
                from lxml.builder import ElementMaker
                E = ElementMaker(namespace=XHTML_NS)
                for elem in matches:
                    for x in elem.iter():
                        if x.text:
                            span = E.span(x.text[0])
                            span.tail = x.text[1:]
                            x.text = None
                            x.insert(0, span)
                            self.style(span)._update_cssdict(cssdict)
                            break
            else:
                for elem in matches:
                    self.style(elem)._update_cssdict(cssdict)
        for elem in xpath(tree, '//h:*[@style]'):
            self.style(elem)._apply_style_attr()
        num_pat = re.compile(r'\d+$')
        for elem in xpath(tree, '//h:img[@width or @height]'):
            style = self.style(elem)
            # Check if either height or width is not default
            is_styled = style._style.get('width', 'auto') != 'auto' or \
                    style._style.get('height', 'auto') != 'auto'
            if not is_styled:
                # Update img style dimension using width and height
                upd = {}
                for prop in ('width', 'height'):
                    val = elem.get(prop, '').strip()
                    try:
                        del elem.attrib[prop]
                    except:
                        pass
                    if val:
                        if num_pat.match(val) is not None:
                            val += 'px'
                        upd[prop] = val
                if upd:
                    style._update_cssdict(upd)

    def _fetch_css_file(self, path):
        hrefs = self.oeb.manifest.hrefs
        if path not in hrefs:
            self.logger.warn('CSS import of missing file %r' % path)
            return (None, None)
        item = hrefs[path]
        if item.media_type not in OEB_STYLES:
            self.logger.warn('CSS import of non-CSS file %r' % path)
            return (None, None)
        data = item.data.cssText
        return ('utf-8', data)

    def flatten_rule(self, rule, href, index):
        results = []
        if isinstance(rule, CSSStyleRule):
            style = self.flatten_style(rule.style)
            for selector in rule.selectorList:
                specificity = selector.specificity + (index,)
                text = selector.selectorText
                selector = list(selector.seq)
                results.append((specificity, selector, style, text, href))
        elif isinstance(rule, CSSPageRule):
            style = self.flatten_style(rule.style)
            self.page_rule.update(style)
        elif isinstance(rule, CSSFontFaceRule):
            self.font_face_rules.append(rule)
        return results

    def flatten_style(self, cssstyle):
        style = {}
        for prop in cssstyle:
            name = prop.name
            if name in ('margin', 'padding'):
                style.update(self._normalize_edge(prop.cssValue, name))
            elif name == 'font':
                style.update(self._normalize_font(prop.cssValue))
            elif name == 'list-style':
                style.update(self._normalize_list_style(prop.cssValue))
            elif name == 'text-align':
                style.update(self._normalize_text_align(prop.cssValue))
            else:
                style[name] = prop.value
        if 'font-size' in style:
            size = style['font-size']
            if size == 'normal': size = 'medium'
            if size == 'smallest': size = 'xx-small'
            if size in FONT_SIZE_NAMES:
                style['font-size'] = "%dpt" % self.profile.fnames[size]
        return style

    def _normalize_edge(self, cssvalue, name):
        style = {}
        if isinstance(cssvalue, CSSValueList):
            primitives = [v.cssText for v in cssvalue]
        else:
            primitives = [cssvalue.cssText]
        if len(primitives) == 1:
            value, = primitives
            values = [value, value, value, value]
        elif len(primitives) == 2:
            vert, horiz = primitives
            values = [vert, horiz, vert, horiz]
        elif len(primitives) == 3:
            top, horiz, bottom = primitives
            values = [top, horiz, bottom, horiz]
        else:
            values = primitives[:4]
        edges = ('top', 'right', 'bottom', 'left')
        for edge, value in itertools.izip(edges, values):
            style["%s-%s" % (name, edge)] = value
        return style

    def _normalize_list_style(self, cssvalue):
        composition = ('list-style-type', 'list-style-position',
                       'list-style-image')
        style = {}
        if cssvalue.cssText == 'inherit':
            for key in composition:
                style[key] = 'inherit'
        else:
            try:
                primitives = [v.cssText for v in cssvalue]
            except TypeError:
                primitives = [cssvalue.cssText]
            primitives.reverse()
            value = primitives.pop()
            for key in composition:
                if cssprofiles.validate(key, value):
                    style[key] = value
                    if not primitives: break
                    value = primitives.pop()
            for key in composition:
                if key not in style:
                    style[key] = DEFAULTS[key]

        return style

    def _normalize_text_align(self, cssvalue):
        style = {}
        text = cssvalue.cssText
        if text == 'inherit':
            style['text-align'] = 'inherit'
        else:
            if text in ('left', 'justify') and self.opts.change_justification in ('left', 'justify'):
                val = self.opts.change_justification
                style['text-align'] = val
            else:
                style['text-align'] = text
        return style

    def _normalize_font(self, cssvalue):
        composition = ('font-style', 'font-variant', 'font-weight',
                       'font-size', 'line-height', 'font-family')
        style = {}
        if cssvalue.cssText == 'inherit':
            for key in composition:
                style[key] = 'inherit'
        else:
            try:
                primitives = [v.cssText for v in cssvalue]
            except TypeError:
                primitives = [cssvalue.cssText]
            primitives.reverse()
            value = primitives.pop()
            for key in composition:
                if cssprofiles.validate(key, value):
                    style[key] = value
                    if not primitives: break
                    value = primitives.pop()
            for key in composition:
                if key not in style:
                    style[key] = DEFAULTS[key]
        return style

    def style(self, element):
        try:
            return self._styles[element]
        except KeyError:
            return Style(element, self)

    def stylesheet(self, name, font_scale=None):
        rules = []
        for _, _, style, selector, href in self.rules:
            if href != name: continue
            if font_scale and 'font-size' in style and \
                    style['font-size'].endswith('pt'):
                style = copy.copy(style)
                size = float(style['font-size'][:-2])
                style['font-size'] = "%.2fpt" % (size * font_scale)
            style = ';\n    '.join(': '.join(item) for item in style.items())
            rules.append('%s {\n    %s;\n}' % (selector, style))
        return '\n'.join(rules)


class Style(object):
    UNIT_RE = re.compile(r'^(-*[0-9]*[.]?[0-9]*)\s*(%|em|ex|en|px|mm|cm|in|pt|pc)$')

    def __init__(self, element, stylizer):
        self._element = element
        self._profile = stylizer.profile
        self._stylizer = stylizer
        self._style = {}
        self._fontSize = None
        self._width = None
        self._height = None
        self._lineHeight = None
        stylizer._styles[element] = self

    def set(self, prop, val):
        self._style[prop] = val

    def _update_cssdict(self, cssdict):
        self._style.update(cssdict)

    def _apply_style_attr(self):
        attrib = self._element.attrib
        if 'style' not in attrib:
            return
        css = attrib['style'].split(';')
        css = filter(None, (x.strip() for x in css))
        try:
            style = CSSStyleDeclaration('; '.join(css))
        except CSSSyntaxError:
            return
        self._style.update(self._stylizer.flatten_style(style))

    def _has_parent(self):
        return (self._element.getparent() is not None)

    def _get_parent(self):
        elem = self._element.getparent()
        if elem is None:
            return None
        return self._stylizer.style(elem)

    def __getitem__(self, name):
        domname = cssproperties._toDOMname(name)
        if hasattr(self, domname):
            return getattr(self, domname)
        return self._unit_convert(self._get(name))

    def _get(self, name):
        result = None
        if name in self._style:
            result = self._style[name]
        if (result == 'inherit'
            or (result is None and name in INHERITED
                and self._has_parent())):
            stylizer = self._stylizer
            result = stylizer.style(self._element.getparent())._get(name)
        if result is None:
            result = DEFAULTS[name]
        return result

    def _unit_convert(self, value, base=None, font=None):
        ' Return value in pts'
        if isinstance(value, (int, long, float)):
            return value
        try:
            return float(value) * 72.0 / self._profile.dpi
        except:
            pass
        result = value
        m = self.UNIT_RE.match(value)
        if m is not None and m.group(1):
            value = float(m.group(1))
            unit = m.group(2)
            if unit == '%':
                if base is None:
                    base = self.width
                result = (value / 100.0) * base
            elif unit == 'px':
                result = value * 72.0 / self._profile.dpi
            elif unit == 'in':
                result = value * 72.0
            elif unit == 'pt':
                result = value
            elif unit == 'em':
                font = font or self.fontSize
                result = value * font
            elif unit in ('ex', 'en'):
                # This is a hack for ex since we have no way to know
                # the x-height of the font
                font = font or self.fontSize
                result = value * font * 0.5
            elif unit == 'pc':
                result = value * 12.0
            elif unit == 'mm':
                result = value * 0.04
            elif unit == 'cm':
                result = value * 0.40
        return result

    def pt_to_px(self, value):
        return (self._profile.dpi / 72.0) * value

    @property
    def fontSize(self):
        def normalize_fontsize(value, base):
            value = value.replace('"', '').replace("'", '')
            result = None
            factor = None
            if value == 'inherit':
                value = base
            if value in FONT_SIZE_NAMES:
                result = self._profile.fnames[value]
            elif value == 'smaller':
                factor = 1.0/1.2
                for _, _, size in self._profile.fsizes:
                    if base <= size: break
                    factor = None
                    result = size
            elif value == 'larger':
                factor = 1.2
                for _, _, size in reversed(self._profile.fsizes):
                    if base >= size: break
                    factor = None
                    result = size
            else:
                result = self._unit_convert(value, base=base, font=base)
                if not isinstance(result, (int, float, long)):
                    return base
                if result < 0:
                    result = normalize_fontsize("smaller", base)
            if factor:
                result = factor * base
            return result
        if self._fontSize is None:
            result = None
            parent = self._get_parent()
            if parent is not None:
                base = parent.fontSize
            else:
                base = self._profile.fbase
            if 'font-size' in self._style:
                size = self._style['font-size']
                result = normalize_fontsize(size, base)
            else:
                result = base
            self._fontSize = result
        return self._fontSize

    @property
    def width(self):
        if self._width is None:
            width = None
            base = None
            parent = self._get_parent()
            if parent is not None:
                base = parent.width
            else:
                base = self._profile.width
            if 'width' in self._element.attrib:
                width = self._element.attrib['width']
            elif 'width' in self._style:
                width = self._style['width']
            if not width or width == 'auto':
                result = base
            else:
                result = self._unit_convert(width, base=base)
            if isinstance(result, (unicode, str, bytes)):
                result = self._profile.width
            self._width = result
            if 'max-width' in self._style:
                result = self._unit_convert(self._style['max-width'], base=base)
                if isinstance(result, (unicode, str, bytes)):
                    result = self._width
                if result < self._width:
                    self._width = result

        return self._width

    @property
    def height(self):
        if self._height is None:
            height = None
            base = None
            parent = self._get_parent()
            if parent is not None:
                base = parent.height
            else:
                base = self._profile.height
            if 'height' in self._element.attrib:
                height = self._element.attrib['height']
            elif 'height' in self._style:
                height = self._style['height']
            if not height or height == 'auto':
                result = base
            else:
                result = self._unit_convert(height, base=base)
            if isinstance(result, (unicode, str, bytes)):
                result = self._profile.height
            self._height = result
            if 'max-height' in self._style:
                result = self._unit_convert(self._style['max-height'], base=base)
                if isinstance(result, (unicode, str, bytes)):
                    result = self._height
                if result < self._height:
                    self._height = result

        return self._height

    @property
    def lineHeight(self):
        if self._lineHeight is None:
            result = None
            parent = self._getparent()
            if 'line-height' in self._style:
                lineh = self._style['line-height']
                try:
                    float(lineh)
                except ValueError:
                    result = self._unit_convert(lineh, base=self.fontSize)
                else:
                    result = float(lineh) * self.fontSize
            elif parent is not None:
                # TODO: proper inheritance
                result = parent.lineHeight
            else:
                result = 1.2 * self.fontSize
            self._lineHeight = result
        return self._lineHeight

    @property
    def marginTop(self):
        return self._unit_convert(
            self._get('margin-top'), base=self.height)

    @property
    def marginBottom(self):
        return self._unit_convert(
            self._get('margin-bottom'), base=self.height)

    @property
    def paddingTop(self):
        return self._unit_convert(
            self._get('padding-top'), base=self.height)

    @property
    def paddingBottom(self):
        return self._unit_convert(
            self._get('padding-bottom'), base=self.height)

    def __str__(self):
        items = self._style.items()
        items.sort()
        return '; '.join("%s: %s" % (key, val) for key, val in items)

    def cssdict(self):
        return dict(self._style)
