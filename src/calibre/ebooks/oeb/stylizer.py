# -*- encoding: utf-8 -*-

'''
CSS property propagation class.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import os, re, logging, copy, unicodedata
from weakref import WeakKeyDictionary
from xml.dom import SyntaxErr as CSSSyntaxError
from cssutils.css import (CSSStyleRule, CSSPageRule, CSSFontFaceRule,
        cssproperties, CSSRule)
from cssutils import (profile as cssprofiles, parseString, parseStyle, log as
        cssutils_log, CSSParser, profiles, replaceUrls)
from calibre import force_unicode, as_unicode
from calibre.ebooks import unit_convert
from calibre.ebooks.oeb.base import XHTML, XHTML_NS, CSS_MIME, OEB_STYLES, xpath, urlnormalize
from calibre.ebooks.oeb.normalize_css import DEFAULTS, normalizers
from css_selectors import Select, SelectorError, INAPPROPRIATE_PSEUDO_CLASSES
from tinycss.media3 import CSSMedia3Parser

cssutils_log.setLevel(logging.WARN)

_html_css_stylesheet = None


def html_css_stylesheet():
    global _html_css_stylesheet
    if _html_css_stylesheet is None:
        html_css = open(P('templates/html.css'), 'rb').read()
        _html_css_stylesheet = parseString(html_css, validate=False)
    return _html_css_stylesheet


INHERITED = {
    'azimuth', 'border-collapse', 'border-spacing', 'caption-side', 'color',
    'cursor', 'direction', 'elevation', 'empty-cells', 'font-family',
    'font-size', 'font-style', 'font-variant', 'font-weight', 'letter-spacing',
    'line-height', 'list-style-image', 'list-style-position',
    'list-style-type', 'orphans', 'page-break-inside', 'pitch-range', 'pitch',
    'quotes', 'richness', 'speak-header', 'speak-numeral', 'speak-punctuation',
    'speak', 'speech-rate', 'stress', 'text-align', 'text-indent',
    'text-transform', 'visibility', 'voice-family', 'volume', 'white-space',
    'widows', 'word-spacing', 'text-shadow',
}

FONT_SIZE_NAMES = {
    'xx-small', 'x-small', 'small', 'medium', 'large', 'x-large', 'xx-large'
}

ALLOWED_MEDIA_TYPES = frozenset({'screen', 'all', 'aural', 'amzn-kf8'})
IGNORED_MEDIA_FEATURES = frozenset('width min-width max-width height min-height max-height device-width min-device-width max-device-width device-height min-device-height max-device-height aspect-ratio min-aspect-ratio max-aspect-ratio device-aspect-ratio min-device-aspect-ratio max-device-aspect-ratio color min-color max-color color-index min-color-index max-color-index monochrome min-monochrome max-monochrome -webkit-min-device-pixel-ratio resolution min-resolution max-resolution scan grid'.split())  # noqa


def media_ok(raw):
    if not raw:
        return True
    if raw == 'amzn-mobi':  # Optimization for the common case
        return False

    def query_ok(mq):
        matched = True
        if mq.media_type not in ALLOWED_MEDIA_TYPES:
            matched = False
        # Media queries that test for device specific features always fail
        for media_feature, expr in mq.expressions:
            if media_feature in IGNORED_MEDIA_FEATURES:
                matched = False
        return mq.negated ^ matched

    try:
        for mq in CSSMedia3Parser().parse_stylesheet(u'@media %s {}' % raw).rules[0].media:
            if query_ok(mq):
                return True
        return False
    except Exception:
        pass
    return True


def test_media_ok():
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


class Stylizer(object):
    STYLESHEETS = WeakKeyDictionary()

    def __init__(self, tree, path, oeb, opts, profile=None,
            extra_css='', user_css='', base_css=''):
        self.oeb, self.opts = oeb, opts
        self.profile = profile
        if self.profile is None:
            # Use the default profile. This should really be using
            # opts.output_profile, but I don't want to risk changing it, as
            # doing so might well have hard to debug font size effects.
            from calibre.customize.ui import output_profiles
            for x in output_profiles():
                if x.short_name == 'default':
                    self.profile = x
                    break
        if self.profile is None:
            # Just in case the default profile is removed in the future :)
            self.profile = opts.output_profile
        self.body_font_size = self.profile.fbase
        self.logger = oeb.logger
        item = oeb.manifest.hrefs[path]
        basename = os.path.basename(path)
        cssname = os.path.splitext(basename)[0] + '.css'
        stylesheets = [html_css_stylesheet()]
        if base_css:
            stylesheets.append(parseString(base_css, validate=False))
        style_tags = xpath(tree, '//*[local-name()="style" or local-name()="link"]')

        # Add cssutils parsing profiles from output_profile
        for profile in self.opts.output_profile.extra_css_modules:
            cssprofiles.addProfile(profile['name'],
                                        profile['props'],
                                        profile['macros'])

        parser = CSSParser(fetcher=self._fetch_css_file,
                log=logging.getLogger('calibre.css'))
        self.font_face_rules = []
        for elem in style_tags:
            if (elem.tag == XHTML('style') and elem.get('type', CSS_MIME) in OEB_STYLES and media_ok(elem.get('media'))):
                text = elem.text if elem.text else u''
                for x in elem:
                    t = getattr(x, 'text', None)
                    if t:
                        text += u'\n\n' + force_unicode(t, u'utf-8')
                    t = getattr(x, 'tail', None)
                    if t:
                        text += u'\n\n' + force_unicode(t, u'utf-8')
                if text:
                    text = oeb.css_preprocessor(text)
                    # We handle @import rules separately
                    parser.setFetcher(lambda x: ('utf-8', b''))
                    stylesheet = parser.parseString(text, href=cssname,
                            validate=False)
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
                                self.logger.warn('CSS @import of non-CSS file %r' % rule.href)
                                continue
                            stylesheets.append(sitem.data)
                    for rule in tuple(stylesheet.cssRules.rulesOfType(CSSRule.PAGE_RULE)):
                        stylesheet.cssRules.remove(rule)
                    # Make links to resources absolute, since these rules will
                    # be folded into a stylesheet at the root
                    replaceUrls(stylesheet, item.abshref,
                            ignoreImportRules=True)
                    stylesheets.append(stylesheet)
            elif (elem.tag == XHTML('link') and elem.get('href') and elem.get(
                    'rel', 'stylesheet').lower() == 'stylesheet' and elem.get(
                    'type', CSS_MIME).lower() in OEB_STYLES and media_ok(elem.get('media'))
                ):
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
                    text = x
                    stylesheet = parser.parseString(text, href=cssname,
                            validate=False)
                    stylesheets.append(stylesheet)
                except:
                    self.logger.exception('Failed to parse %s, ignoring.'%w)
                    self.logger.debug('Bad css: ')
                    self.logger.debug(x)
        rules = []
        index = 0
        self.stylesheets = set()
        self.page_rule = {}
        for sheet_index, stylesheet in enumerate(stylesheets):
            href = stylesheet.href
            self.stylesheets.add(href)
            for rule in stylesheet.cssRules:
                if rule.type == rule.MEDIA_RULE:
                    if media_ok(rule.media.mediaText):
                        for subrule in rule.cssRules:
                            rules.extend(self.flatten_rule(subrule, href, index, is_user_agent_sheet=sheet_index==0))
                            index += 1
                else:
                    rules.extend(self.flatten_rule(rule, href, index, is_user_agent_sheet=sheet_index==0))
                    index = index + 1
        rules.sort()
        self.rules = rules
        self._styles = {}
        pseudo_pat = re.compile(ur':{1,2}(%s)' % ('|'.join(INAPPROPRIATE_PSEUDO_CLASSES)), re.I)
        select = Select(tree, ignore_inappropriate_pseudo_classes=True)

        for _, _, cssdict, text, _ in rules:
            fl = pseudo_pat.search(text)
            try:
                matches = tuple(select(text))
            except SelectorError as err:
                self.logger.error('Ignoring CSS rule with invalid selector: %r (%s)' % (text, as_unicode(err)))
                continue

            if fl is not None:
                fl = fl.group(1)
                if fl == 'first-letter' and getattr(self.oeb,
                        'plumber_output_format', '').lower() in {u'mobi', u'docx'}:
                    # Fake first-letter
                    for elem in matches:
                        for x in elem.iter('*'):
                            if x.text:
                                punctuation_chars = []
                                text = unicode(x.text)
                                while text:
                                    category = unicodedata.category(text[0])
                                    if category[0] not in {'P', 'Z'}:
                                        break
                                    punctuation_chars.append(text[0])
                                    text = text[1:]

                                special_text = u''.join(punctuation_chars) + \
                                        (text[0] if text else u'')
                                span = x.makeelement('{%s}span' % XHTML_NS)
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
        for elem in xpath(tree, '//h:*[@style]'):
            self.style(elem)._apply_style_attr(url_replacer=item.abshref)
        num_pat = re.compile(r'[0-9.]+$')
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

    def flatten_rule(self, rule, href, index, is_user_agent_sheet=False):
        results = []
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

    def flatten_style(self, cssstyle):
        style = {}
        for prop in cssstyle:
            name = prop.name
            normalizer = normalizers.get(name, None)
            if normalizer is not None:
                style.update(normalizer(name, prop.cssValue))
            elif name == 'text-align':
                style['text-align'] = self._apply_text_align(prop.value)
            else:
                style[name] = prop.value
        if 'font-size' in style:
            size = style['font-size']
            if size == 'normal':
                size = 'medium'
            if size == 'smallest':
                size = 'xx-small'
            if size in FONT_SIZE_NAMES:
                style['font-size'] = "%dpt" % self.profile.fnames[size]
        if '-epub-writing-mode' in style:
            for x in ('-webkit-writing-mode', 'writing-mode'):
                style[x] = style.get(x, style['-epub-writing-mode'])
        return style

    def _apply_text_align(self, text):
        if text in ('left', 'justify') and self.opts.change_justification in ('left', 'justify'):
            text = self.opts.change_justification
        return text

    def style(self, element):
        try:
            return self._styles[element]
        except KeyError:
            return Style(element, self)

    def stylesheet(self, name, font_scale=None):
        rules = []
        for _, _, style, selector, href in self.rules:
            if href != name:
                continue
            if font_scale and 'font-size' in style and \
                    style['font-size'].endswith('pt'):
                style = copy.copy(style)
                size = float(style['font-size'][:-2])
                style['font-size'] = "%.2fpt" % (size * font_scale)
            style = ';\n    '.join(': '.join(item) for item in style.items())
            rules.append('%s {\n    %s;\n}' % (selector, style))
        return '\n'.join(rules)


class Style(object):
    MS_PAT = re.compile(r'^\s*(mso-|panose-|text-underline|tab-interval)')

    def __init__(self, element, stylizer):
        self._element = element
        self._profile = stylizer.profile
        self._stylizer = stylizer
        self._style = {}
        self._fontSize = None
        self._width = None
        self._height = None
        self._lineHeight = None
        self._bgcolor = None
        self._pseudo_classes = {}
        stylizer._styles[element] = self

    def set(self, prop, val):
        self._style[prop] = val

    def drop(self, prop, default=None):
        return self._style.pop(prop, default)

    def _update_cssdict(self, cssdict):
        self._style.update(cssdict)

    def _update_pseudo_class(self, name, cssdict):
        orig = self._pseudo_classes.get(name, {})
        orig.update(cssdict)
        self._pseudo_classes[name] = orig

    def _apply_style_attr(self, url_replacer=None):
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
        self._style.update(self._stylizer.flatten_style(style))

    def _has_parent(self):
        try:
            return self._element.getparent() is not None
        except AttributeError:
            return False  # self._element is None

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
        if (result == 'inherit' or (result is None and name in INHERITED and self._has_parent())):
            stylizer = self._stylizer
            result = stylizer.style(self._element.getparent())._get(name)
        if result is None:
            result = DEFAULTS[name]
        return result

    def get(self, name, default=None):
        return self._style.get(name, default)

    def _unit_convert(self, value, base=None, font=None):
        'Return value in pts'
        if base is None:
            base = self.width
        if not font and font != 0:
            font = self.fontSize
        return unit_convert(value, base, font, self._profile.dpi, body_font_size=self._stylizer.body_font_size)

    def pt_to_px(self, value):
        return (self._profile.dpi / 72.0) * value

    @property
    def backgroundColor(self):
        '''
        Return the background color by parsing both the background-color and
        background shortcut properties. Note that inheritance/default values
        are not used. None is returned if no background color is set.
        '''

        def validate_color(col):
            return cssprofiles.validateWithProfile('color',
                        col,
                        profiles=[profiles.Profiles.CSS_LEVEL_2])[1]

        if self._bgcolor is None:
            col = None
            val = self._style.get('background-color', None)
            if val and validate_color(val):
                col = val
            else:
                val = self._style.get('background', None)
                if val is not None:
                    try:
                        style = parseStyle('background: '+val, validate=False)
                        val = style.getProperty('background').cssValue
                        try:
                            val = list(val)
                        except:
                            # val is CSSPrimitiveValue
                            val = [val]
                        for c in val:
                            c = c.cssText
                            if validate_color(c):
                                col = c
                                break
                    except:
                        pass
            if col is None:
                self._bgcolor = False
            else:
                self._bgcolor = col
        return self._bgcolor if self._bgcolor else None

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

    def img_dimension(self, attr, img_size):
        ans = None
        parent = self._get_parent()
        if parent is not None:
            base = getattr(parent, attr)
        else:
            base = getattr(self._profile, attr + '_pts')
        x = self._style.get(attr)
        if x is not None:
            if x == 'auto':
                ans = self._unit_convert(str(img_size) + 'px', base=base)
            else:
                x = self._unit_convert(x, base=base)
                if isinstance(x, (float, int, long)):
                    ans = x
        if ans is None:
            x = self._element.get(attr)
            if x is not None:
                x = self._unit_convert(x + 'px', base=base)
                if isinstance(x, (float, int, long)):
                    ans = x
        if ans is None:
            ans = self._unit_convert(str(img_size) + 'px', base=base)
        maa = self._style.get('max-' + attr)
        if maa is not None:
            x = self._unit_convert(maa, base=base)
            if isinstance(x, (int, float, long)) and (ans is None or x < ans):
                ans = x
        return ans

    def img_size(self, width, height):
        ' Return the final size of an <img> given that it points to an image of size widthxheight '
        w, h = self._get('width'), self._get('height')
        answ, ansh = self.img_dimension('width', width), self.img_dimension('height', height)
        if w == 'auto' and h != 'auto':
            answ = (float(width)/height) * ansh
        elif h == 'auto' and w != 'auto':
            ansh = (float(height)/width) * answ
        return answ, ansh

    @property
    def width(self):
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
    def parent_width(self):
        parent = self._get_parent()
        if parent is None:
            return self.width
        return parent.width

    @property
    def height(self):
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
    def effective_text_decoration(self):
        '''
        Browsers do this creepy thing with text-decoration where even though the
        property is not inherited, it looks like it is because containing
        blocks apply it. The actual algorithm is utterly ridiculous, see
        http://reference.sitepoint.com/css/text-decoration
        This matters for MOBI output, where text-decoration is mapped to <u>
        and <st> tags. Trying to implement the actual algorithm is too much
        work, so we just use a simple fake that should cover most cases.
        '''
        css = self._style.get('text-decoration', None)
        pcss = None
        parent = self._get_parent()
        if parent is not None:
            pcss = parent._style.get('text-decoration', None)
        if css in ('none', None, 'inherit') and pcss not in (None, 'none'):
            return pcss
        return css

    @property
    def first_vertical_align(self):
        ''' For docx output where tags are not nested, we cannot directly
        simulate the HTML vertical-align rendering model. Instead use the
        approximation of considering the first non-default vertical-align '''
        val = self['vertical-align']
        if val != 'baseline':
            raw_val = self._get('vertical-align')
            if '%' in raw_val:
                val = self._unit_convert(raw_val, base=self['line-height'])
            return val
        parent = self._get_parent()
        if parent is not None and 'inline' in parent['display']:
            return parent.first_vertical_align

    @property
    def marginTop(self):
        return self._unit_convert(
            self._get('margin-top'), base=self.parent_width)

    @property
    def marginBottom(self):
        return self._unit_convert(
            self._get('margin-bottom'), base=self.parent_width)

    @property
    def marginLeft(self):
        return self._unit_convert(
            self._get('margin-left'), base=self.parent_width)

    @property
    def marginRight(self):
        return self._unit_convert(
            self._get('margin-right'), base=self.parent_width)

    @property
    def paddingTop(self):
        return self._unit_convert(
            self._get('padding-top'), base=self.parent_width)

    @property
    def paddingBottom(self):
        return self._unit_convert(
            self._get('padding-bottom'), base=self.parent_width)

    @property
    def paddingLeft(self):
        return self._unit_convert(
            self._get('padding-left'), base=self.parent_width)

    @property
    def paddingRight(self):
        return self._unit_convert(
            self._get('padding-right'), base=self.parent_width)

    def __str__(self):
        items = sorted(self._style.iteritems())
        return '; '.join("%s: %s" % (key, val) for key, val in items)

    def cssdict(self):
        return dict(self._style)

    def pseudo_classes(self, filter_css):
        if filter_css:
            css = copy.deepcopy(self._pseudo_classes)
            for psel, cssdict in css.iteritems():
                for k in filter_css:
                    cssdict.pop(k, None)
        else:
            css = self._pseudo_classes
        return {k:v for k, v in css.iteritems() if v}

    @property
    def is_hidden(self):
        return self._style.get('display') == 'none' or self._style.get('visibility') == 'hidden'
