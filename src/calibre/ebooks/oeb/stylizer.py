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
from calibre.ebooks.oeb.base import barename, urlnormalize
from calibre.resources import html_css

XHTML_CSS_NAMESPACE = "@namespace url(%s);\n" % XHTML_NS
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
            'text-align': 'left', 'text-decoration': 'none', 'text-indent':
            0, 'text-transform': 'none', 'top': 'auto', 'unicode-bidi':
            'normal', 'vertical-align': 'baseline', 'visibility': 'visible',
            'voice-family': 'default', 'volume': 'medium', 'white-space':
            'normal', 'widows': '2', 'width': 'auto', 'word-spacing': 'normal',
            'z-index': 'auto'}

FONT_SIZE_NAMES = set(['xx-small', 'x-small', 'small', 'medium', 'large',
                       'x-large', 'xx-large'])

FONT_SIZES = [('xx-small', 1),
              ('x-small',  None),
              ('small',    2),
              ('medium',   3),
              ('large',    4),
              ('x-large',  5),
              ('xx-large', 6),
              (None,       7)]


XPNSMAP = {'h': XHTML_NS,}
def xpath(elem, expr):
    return elem.xpath(expr, namespaces=XPNSMAP)

class CSSSelector(etree.XPath):
    def __init__(self, css, namespaces=XPNSMAP):
        path = css_to_xpath(css)
        etree.XPath.__init__(self, path, namespaces=namespaces)
        self.css = css

    def __repr__(self):
        return '<%s %s for %r>' % (
            self.__class__.__name__,
            hex(abs(id(self)))[2:],
            self.css)


class Page(object):
    def __init__(self, width, height, dpi, fbase, fsizes):
        self.width = (float(width) / dpi) * 72.
        self.height = (float(height) / dpi) * 72.
        self.dpi = float(dpi)
        self.fbase = float(fbase)
        self.fsizes = []
        for (name, num), size in izip(FONT_SIZES, fsizes):
            self.fsizes.append((name, num, float(size)))
        self.fnames = dict((name, sz) for name, _, sz in self.fsizes if name)
        self.fnums = dict((num, sz) for _, num, sz in self.fsizes if num)

class Profiles(object):
    PRS505 = Page(584, 754, 168.451, 12, [7.5, 9, 10, 12, 15.5, 20, 22, 24])
    MSLIT = Page(652, 480, 168.451, 13, [10, 11, 13, 16, 18, 20, 22, 26])

    
class Stylizer(object):    
    STYLESHEETS = {}
    
    def __init__(self, tree, path, oeb, page=Profiles.PRS505):
        self.page = page
        base = os.path.dirname(path)
        basename = os.path.basename(path)
        cssname = os.path.splitext(basename)[0] + '.css'
        stylesheets = [HTML_CSS_STYLESHEET]
        head = xpath(tree, '/h:html/h:head')[0]
        parser = cssutils.CSSParser()
        parser.setFetcher(lambda path: ('utf-8', oeb.container.read(path)))
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
                path = os.path.join(base, href)
                path = os.path.normpath(path).replace('\\', '/')
                if path in self.STYLESHEETS:
                    stylesheet = self.STYLESHEETS[path]
                else:
                    data = XHTML_CSS_NAMESPACE
                    data += oeb.manifest.hrefs[path].data
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
            except ExpressionError:
                continue
            for elem in selector(tree):
                self.style(elem)._update_cssdict(cssdict)
        for elem in tree.xpath('//*[@style]'):
            self.style(elem)._apply_style_tag()
        

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
                style['font-size'] = "%dpt" % self.page.fnames[size]
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
            primitives = [v.cssText for v in cssvalue]
            primitites.reverse()
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
    def __init__(self, element, stylizer):
        self._element = element
        self._page = stylizer.page
        self._stylizer = stylizer
        self._style = {}
        stylizer._styles[element] = self

    def _update_cssdict(self, cssdict):
        self._style.update(cssdict)
        
    def _apply_style_tag(self):
        attrib = self._element.attrib
        if 'style' in attrib:
            style = CSSStyleDeclaration(attrib['style'])
            self._style.update(self._stylizer.flatten_style(style))

    def _has_parent(self):
        parent = self._element.getparent()
        return (parent is not None) \
            and (parent in self._stylizer._styles)
    
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
            styles = self._stylizer._styles
            result = styles[self._element.getparent()]._get(name)
        if result is None:
            result = DEFAULTS[name]
        return result

    def _unit_convert(self, value, base=None, font=None):
        if isinstance(value, (int, long, float)):
            return value
        try:
            if float(value) == 0:
                return 0.0
        except:
            pass
        result = value
        m = re.search(
            r"^(-*[0-9]*\.?[0-9]*)\s*(%|em|px|mm|cm|in|pt|pc)$", value)
        if m is not None and m.group(1):
            value = float(m.group(1))
            unit = m.group(2)
            if unit == '%':
                base = base or self.width
                result = (value/100.0) * base
            elif unit == 'px':
                result = value * 72.0 / self._page.dpi
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
        def normalize_fontsize(value, base=None):
            result = None
            factor = None
            if value == 'inherit':
                # We should only see this if the root element
                value = self._stylizer.page.fbase
            if value in FONT_SIZE_NAMES:
                result = self._stylizer.page.fnames[value]
            elif value == 'smaller':
                factor = 1.0/1.2
                for _, _, size in self._stylizer.page.fsizes:
                    if base <= size: break
                    factor = None
                    result = size
            elif value == 'larger':
                factor = 1.2
                for _, _, size in reversed(self._stylizer.page.fsizes):
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
        result = None
        if self._has_parent():
            styles = self._stylizer._styles
            base = styles[self._element.getparent()].fontSize
        else:
            base = self._stylizer.page.fbase
        if 'font-size' in self._style:
            size = self._style['font-size']
            result = normalize_fontsize(size, base)
        else:
            result = base
        self.__dict__['fontSize'] = result
        return result

    @property
    def width(self):
        result = None
        base = None
        if self._has_parent():
            styles = self._stylizer._styles
            base = styles[self._element.getparent()].width
        else:
            base = self._page.width
        if 'width' in self._style:
            width = self._style['width']
            if width == 'auto':
                result = base
            else:
                result = self._unit_convert(width, base=base)
        else:
            result = base
        self.__dict__['width'] = result
        return result
    
    def __str__(self):
        items = self._style.items()
        items.sort()
        return '; '.join("%s: %s" % (key, val) for key, val in items)

    def cssdict(self):
        return dict(self._style)
