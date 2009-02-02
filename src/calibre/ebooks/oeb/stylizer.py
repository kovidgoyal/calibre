# -*- encoding: utf-8 -*-

'''
CSS property propagation class.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import sys
import os
import locale
import codecs
import itertools
import types
import re
import copy
from itertools import izip
import cssutils
from cssutils.css import CSSStyleRule, CSSPageRule, CSSStyleDeclaration, \
    CSSValueList, cssproperties
from lxml import etree
from lxml.cssselect import css_to_xpath, ExpressionError
from calibre.ebooks.oeb.base import XHTML, XHTML_NS, CSS_MIME, OEB_STYLES
from calibre.ebooks.oeb.base import XPNSMAP, xpath, barename, urlnormalize
from calibre.ebooks.oeb.profile import PROFILES
from calibre.resources import html_css

XHTML_CSS_NAMESPACE = '@namespace "%s";\n' % XHTML_NS
HTML_CSS_STYLESHEET = cssutils.parseString(html_css)
HTML_CSS_STYLESHEET.namespaces['h'] = XHTML_NS

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
        path = css_to_xpath(css)
        path = self.LOCAL_NAME_RE.sub(r"local-name() = '", path)
        etree.XPath.__init__(self, path, namespaces=namespaces)
        self.css = css

    def __repr__(self):
        return '<%s %s for %r>' % (
            self.__class__.__name__,
            hex(abs(id(self)))[2:],
            self.css)


class Stylizer(object):    
    STYLESHEETS = {}
    
    def __init__(self, tree, path, oeb, profile=PROFILES['PRS505']):
        self.oeb = oeb
        self.profile = profile
        self.logger = oeb.logger
        item = oeb.manifest.hrefs[path]
        basename = os.path.basename(path)
        cssname = os.path.splitext(basename)[0] + '.css'
        stylesheets = [HTML_CSS_STYLESHEET]
        head = xpath(tree, '/h:html/h:head')[0]
        parser = cssutils.CSSParser()
        parser.setFetcher(self._fetch_css_file)
        for elem in head:
            if elem.tag == XHTML('style') and elem.text \
               and elem.get('type', CSS_MIME) in OEB_STYLES:
                text = XHTML_CSS_NAMESPACE + elem.text
                stylesheet = parser.parseString(text, href=cssname)
                stylesheet.namespaces['h'] = XHTML_NS
                stylesheets.append(stylesheet)
            elif elem.tag == XHTML('link') and elem.get('href') \
                 and elem.get('rel', 'stylesheet') == 'stylesheet' \
                 and elem.get('type', CSS_MIME) in OEB_STYLES:
                href = urlnormalize(elem.attrib['href'])
                path = item.abshref(href)
                if path not in oeb.manifest.hrefs:
                    self.logger.warn(
                        'Stylesheet %r referenced by file %r not in manifest' %
                        (path, item.href))
                    continue
                if path in self.STYLESHEETS:
                    stylesheet = self.STYLESHEETS[path]
                else:
                    data = self._fetch_css_file(path)[1]
                    stylesheet = parser.parseString(data, href=path)
                    stylesheet.namespaces['h'] = XHTML_NS
                    self.STYLESHEETS[path] = stylesheet
                stylesheets.append(stylesheet)
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
        for _, _, cssdict, text, _ in rules:
            try:
                selector = CSSSelector(text)
            except ExpressionError, e:
                continue
            for elem in selector(tree):
                self.style(elem)._update_cssdict(cssdict)
        for elem in xpath(tree, '//h:*[@style]'):
            self.style(elem)._apply_style_attr()
    
    def _fetch_css_file(self, path):
        hrefs = self.oeb.manifest.hrefs
        if path not in hrefs:
            return (None, None)
        data = hrefs[path].data
        data = self.oeb.decode(data)
        data = XHTML_CSS_NAMESPACE + data
        return (None, data)
    
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
        return results
    
    def flatten_style(self, cssstyle):
        style = {}
        for prop in cssstyle:
            name = prop.name
            if name in ('margin', 'padding'):
                style.update(self._normalize_edge(prop.cssValue, name))
            elif name == 'font':
                style.update(self._normalize_font(prop.cssValue))
            else:
                style[name] = prop.value
        if 'font-size' in style:
            size = style['font-size']
            if size == 'normal': size = 'medium'
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
                if cssproperties.cssvalues[key](value):
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
    UNIT_RE = re.compile(r'^(-*[0-9]*[.]?[0-9]*)\s*(%|em|px|mm|cm|in|pt|pc)$')
    
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

    def _update_cssdict(self, cssdict):
        self._style.update(cssdict)
        
    def _apply_style_attr(self):
        attrib = self._element.attrib
        if 'style' in attrib:
            css = attrib['style'].split(';')
            css = filter(None, map(lambda x: x.strip(), css))
            style = CSSStyleDeclaration('; '.join(css))
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
                base = base or self.width
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
            elif unit == 'pc':
                result = value * 12.0
            elif unit == 'mm':
                result = value * 0.04
            elif unit == 'cm':
                result = value * 0.40
        return result

    @property
    def fontSize(self):
        def normalize_fontsize(value, base):
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
            if 'width' is self._element.attrib:
                width = self._element.attrib['width']
            elif 'width' in self._style:
                width = self._style['width']
            if not width or width == 'auto':
                result = base
            else:
                result = self._unit_convert(width, base=base)
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
            if 'height' is self._element.attrib:
                height = self._element.attrib['height']
            elif 'height' in self._style:
                height = self._style['height']
            if not height or height == 'auto':
                result = base
            else:
                result = self._unit_convert(height, base=base)
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
