'''
CSS flattening transform.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import re, operator, math
from collections import defaultdict

from lxml import etree
import cssutils

from calibre.ebooks.oeb.base import (XHTML, XHTML_NS, CSS_MIME, OEB_STYLES,
        namespace, barename, XPath)
from calibre.ebooks.oeb.stylizer import Stylizer

COLLAPSE = re.compile(r'[ \t\r\n\v]+')
STRIPNUM = re.compile(r'[-0-9]+$')

def asfloat(value, default):
    if not isinstance(value, (int, long, float)):
        value = default
    return float(value)

def dynamic_rescale_factor(node):
    classes = node.get('class', '').split(' ')
    classes = [x.replace('calibre_rescale_', '') for x in classes if
            x.startswith('calibre_rescale_')]
    if not classes: return None
    factor = 1.0
    for x in classes:
        try:
            factor *= float(x)/100.
        except ValueError:
            continue
    return factor


class KeyMapper(object):
    def __init__(self, sbase, dbase, dkey):
        self.sbase = float(sbase)
        self.dprop = [(self.relate(x, dbase), float(x)) for x in dkey]
        self.cache = {}

    @staticmethod
    def relate(size, base):
        if size == 0:
            return base
        size = float(size)
        base = float(base)
        if abs(size - base) < 0.1: return 0
        sign = -1 if size < base else 1
        endp = 0 if size < base else 36
        diff = (abs(base - size) * 3) + ((36 - size) / 100)
        logb = abs(base - endp)
        if logb == 0:
            logb = 1e-6
        result = sign * math.log(diff, logb)
        return result

    def __getitem__(self, ssize):
        ssize = asfloat(ssize, 0)
        if ssize in self.cache:
            return self.cache[ssize]
        dsize = self.map(ssize)
        self.cache[ssize] = dsize
        return dsize

    def map(self, ssize):
        sbase = self.sbase
        prop = self.relate(ssize, sbase)
        diff = [(abs(prop - p), s) for p, s in self.dprop]
        dsize = min(diff)[1]
        return dsize

class ScaleMapper(object):
    def __init__(self, sbase, dbase):
        self.dscale = float(dbase) / float(sbase)

    def __getitem__(self, ssize):
        ssize = asfloat(ssize, 0)
        dsize = ssize * self.dscale
        return dsize

class NullMapper(object):
    def __init__(self):
        pass

    def __getitem__(self, ssize):
        return ssize

def FontMapper(sbase=None, dbase=None, dkey=None):
    if sbase and dbase and dkey:
        return KeyMapper(sbase, dbase, dkey)
    elif sbase and dbase:
        return ScaleMapper(sbase, dbase)
    else:
        return NullMapper()


class CSSFlattener(object):
    def __init__(self, fbase=None, fkey=None, lineh=None, unfloat=False,
                 untable=False, page_break_on_body=False, specializer=None):
        self.fbase = fbase
        self.fkey = fkey
        self.lineh = lineh
        self.unfloat = unfloat
        self.untable = untable
        self.specializer = specializer
        self.page_break_on_body = page_break_on_body

    @classmethod
    def config(cls, cfg):
        return cfg

    @classmethod
    def generate(cls, opts):
        return cls()

    def __call__(self, oeb, context):
        oeb.logger.info('Flattening CSS and remapping font sizes...')
        self.context = self.opts =context
        self.oeb = oeb

        self.filter_css = frozenset()
        if self.opts.filter_css:
            try:
                self.filter_css = frozenset([x.strip().lower() for x in
                    self.opts.filter_css.split(',')])
            except:
                self.oeb.log.warning('Failed to parse filter_css, ignoring')
            else:
                self.oeb.log.debug('Filtering CSS properties: %s'%
                    ', '.join(self.filter_css))

        for item in oeb.manifest.values():
            # Make all links to resources absolute, as these sheets will be
            # consolidated into a single stylesheet at the root of the document
            if item.media_type in OEB_STYLES:
                cssutils.replaceUrls(item.data, item.abshref,
                        ignoreImportRules=True)

        self.stylize_spine()
        self.sbase = self.baseline_spine() if self.fbase else None
        self.fmap = FontMapper(self.sbase, self.fbase, self.fkey)
        self.flatten_spine()

    def stylize_spine(self):
        self.stylizers = {}
        profile = self.context.source
        css = ''
        for item in self.oeb.spine:
            html = item.data
            body = html.find(XHTML('body'))
            bs = body.get('style', '').split(';')
            bs.append('margin-top: 0pt')
            bs.append('margin-bottom: 0pt')
            bs.append('margin-left : %fpt'%\
                    float(self.context.margin_left))
            bs.append('margin-right : %fpt'%\
                    float(self.context.margin_right))
            bs.extend(['padding-left: 0pt', 'padding-right: 0pt'])
            if self.page_break_on_body:
                bs.extend(['page-break-before: always'])
            if self.context.change_justification != 'original':
                bs.append('text-align: '+ self.context.change_justification)
            body.set('style', '; '.join(bs))
            stylizer = Stylizer(html, item.href, self.oeb, self.context, profile,
                    user_css=self.context.extra_css,
                    extra_css=css)
            self.stylizers[item] = stylizer

    def baseline_node(self, node, stylizer, sizes, csize):
        csize = stylizer.style(node)['font-size']
        if node.text:
            sizes[csize] += len(COLLAPSE.sub(' ', node.text))
        for child in node:
            self.baseline_node(child, stylizer, sizes, csize)
            if child.tail:
                sizes[csize] += len(COLLAPSE.sub(' ', child.tail))

    def baseline_spine(self):
        sizes = defaultdict(float)
        for item in self.oeb.spine:
            html = item.data
            stylizer = self.stylizers[item]
            body = html.find(XHTML('body'))
            fsize = self.context.source.fbase
            self.baseline_node(body, stylizer, sizes, fsize)
        try:
            sbase = max(sizes.items(), key=operator.itemgetter(1))[0]
        except:
            sbase = 12.0
        self.oeb.logger.info(
            "Source base font size is %0.05fpt" % sbase)
        return sbase

    def clean_edges(self, cssdict, style, fsize):
        slineh = self.sbase * 1.26
        dlineh = self.lineh
        for kind in ('margin', 'padding'):
            for edge in ('bottom', 'top'):
                property = "%s-%s" % (kind, edge)
                if property not in cssdict: continue
                if '%' in cssdict[property]: continue
                value = style[property]
                if value == 0:
                    continue
                elif value <= slineh:
                    cssdict[property] = "%0.5fem" % (dlineh / fsize)
                else:
                    try:
                        value = round(value / slineh) * dlineh
                    except:
                        self.oeb.logger.warning(
                                'Invalid length:', value)
                        value = 0.0
                    cssdict[property] = "%0.5fem" % (value / fsize)

    def flatten_node(self, node, stylizer, names, styles, psize, item_id, left=0):
        if not isinstance(node.tag, basestring) \
           or namespace(node.tag) != XHTML_NS:
               return
        tag = barename(node.tag)
        style = stylizer.style(node)
        cssdict = style.cssdict()
        try:
            font_size = style['font-size']
        except:
            font_size = self.sbase if self.sbase is not None else \
                self.context.source.fbase
        if 'align' in node.attrib:
            if tag != 'img':
                cssdict['text-align'] = node.attrib['align']
            else:
                val = node.attrib['align']
                if val in ('middle', 'bottom', 'top'):
                    cssdict['vertical-align'] = val
                elif val in ('left', 'right'):
                    cssdict['text-align'] = val
            del node.attrib['align']
        if node.tag == XHTML('font'):
            tags = ['descendant::h:%s'%x for x in ('p', 'div', 'table', 'h1',
                'h2', 'h3', 'h4', 'h5', 'h6', 'ol', 'ul', 'dl', 'blockquote')]
            tag = 'div' if XPath('|'.join(tags))(node) else 'span'
            node.tag = XHTML(tag)
            if 'size' in node.attrib:
                def force_int(raw):
                    return int(re.search(r'([0-9+-]+)', raw).group(1))
                size = node.attrib['size'].strip()
                if size:
                    fnums = self.context.source.fnums
                    if size[0] in ('+', '-'):
                        # Oh, the warcrimes
                        try:
                            esize = 3 + force_int(size)
                        except:
                            esize = 3
                        if esize < 1:
                            esize = 1
                        if esize > 7:
                            esize = 7
                        font_size = fnums[esize]
                    else:
                        try:
                            font_size = fnums[force_int(size)]
                        except:
                            font_size = fnums[3]
                    cssdict['font-size'] = '%.1fpt'%font_size
                del node.attrib['size']
            if 'face' in node.attrib:
                cssdict['font-family'] = node.attrib['face']
                del node.attrib['face']
        if 'color' in node.attrib:
            cssdict['color'] = node.attrib['color']
            del node.attrib['color']
        if 'bgcolor' in node.attrib:
            cssdict['background-color'] = node.attrib['bgcolor']
            del node.attrib['bgcolor']
        if cssdict.get('font-weight', '').lower() == 'medium':
            cssdict['font-weight'] = 'normal' # ADE chokes on font-weight medium

        fsize = font_size
        if not self.context.disable_font_rescaling:
            _sbase = self.sbase if self.sbase is not None else \
                self.context.source.fbase
            dyn_rescale = dynamic_rescale_factor(node)
            if dyn_rescale is not None:
                fsize = self.fmap[_sbase]
                fsize *= dyn_rescale
                cssdict['font-size'] = '%0.5fem'%(fsize/psize)
                psize = fsize
            elif 'font-size' in cssdict or tag == 'body':
                fsize = self.fmap[font_size]
                try:
                    cssdict['font-size'] = "%0.5fem" % (fsize / psize)
                except ZeroDivisionError:
                    cssdict['font-size'] = '%.1fpt'%fsize
                psize = fsize

        try:
            minlh = self.context.minimum_line_height / 100.
            if style['line-height'] < minlh * fsize:
                cssdict['line-height'] = str(minlh)
        except:
            self.oeb.logger.exception('Failed to set minimum line-height')

        if cssdict:
            for x in self.filter_css:
                cssdict.pop(x, None)

        if cssdict:
            if self.lineh and self.fbase and tag != 'body':
                self.clean_edges(cssdict, style, psize)
            margin = asfloat(style['margin-left'], 0)
            indent = asfloat(style['text-indent'], 0)
            left += margin
            if (left + indent) < 0:
                try:
                    percent = (margin - indent) / style['width']
                    cssdict['margin-left'] = "%d%%" % (percent * 100)
                except ZeroDivisionError:
                    pass
                left -= indent
            if 'display' in cssdict and cssdict['display'] == 'in-line':
                cssdict['display'] = 'inline'
            if self.unfloat and 'float' in cssdict \
               and cssdict.get('display', 'none') != 'none':
                del cssdict['display']
            if self.untable and 'display' in cssdict \
               and cssdict['display'].startswith('table'):
                display = cssdict['display']
                if display == 'table-cell':
                    cssdict['display'] = 'inline'
                else:
                    cssdict['display'] = 'block'
            if 'vertical-align' in cssdict \
               and cssdict['vertical-align'] == 'sup':
                cssdict['vertical-align'] = 'super'
        if self.lineh and 'line-height' not in cssdict:
            lineh = self.lineh / psize
            cssdict['line-height'] = "%0.5fem" % lineh

        if (self.context.remove_paragraph_spacing or
                self.context.insert_blank_line) and tag in ('p', 'div'):
            if item_id != 'calibre_jacket' or self.context.output_profile.name == 'Kindle':
                for prop in ('margin', 'padding', 'border'):
                    for edge in ('top', 'bottom'):
                        cssdict['%s-%s'%(prop, edge)] = '0pt'
            if self.context.insert_blank_line:
                cssdict['margin-top'] = cssdict['margin-bottom'] = \
                    '%fem'%self.context.insert_blank_line_size
            indent_size = self.context.remove_paragraph_spacing_indent_size
            keep_indents = indent_size < 0.0
            if (self.context.remove_paragraph_spacing and not keep_indents and
                cssdict.get('text-align', None) not in ('center', 'right')):
                cssdict['text-indent'] =  "%1.1fem" % indent_size

        if cssdict:
            items = cssdict.items()
            items.sort()
            css = u';\n'.join(u'%s: %s' % (key, val) for key, val in items)
            classes = node.get('class', '').strip() or 'calibre'
            klass = STRIPNUM.sub('', classes.split()[0].replace('_', ''))
            if css in styles:
                match = styles[css]
            else:
                match = klass + str(names[klass] or '')
                styles[css] = match
                names[klass] += 1
            node.attrib['class'] = match
        elif 'class' in node.attrib:
            del node.attrib['class']
        if 'style' in node.attrib:
            del node.attrib['style']
        for child in node:
            self.flatten_node(child, stylizer, names, styles, psize, item_id, left)

    def flatten_head(self, item, stylizer, href):
        html = item.data
        head = html.find(XHTML('head'))
        for node in head:
            if node.tag == XHTML('link') \
               and node.get('rel', 'stylesheet') == 'stylesheet' \
               and node.get('type', CSS_MIME) in OEB_STYLES:
                head.remove(node)
            elif node.tag == XHTML('style') \
                 and node.get('type', CSS_MIME) in OEB_STYLES:
                head.remove(node)
        href = item.relhref(href)
        etree.SubElement(head, XHTML('link'),
            rel='stylesheet', type=CSS_MIME, href=href)
        stylizer.page_rule['margin-top'] = '%fpt'%\
                float(self.context.margin_top)
        stylizer.page_rule['margin-bottom'] = '%fpt'%\
                float(self.context.margin_bottom)

        items = stylizer.page_rule.items()
        items.sort()
        css = '; '.join("%s: %s" % (key, val) for key, val in items)
        style = etree.SubElement(head, XHTML('style'), type=CSS_MIME)
        style.text = "\n\t\t@page { %s; }" % css
        rules = [r.cssText for r in stylizer.font_face_rules]
        raw = '\n\n'.join(rules)
        # Make URLs referring to fonts relative to this item
        sheet = cssutils.parseString(raw, validate=False)
        cssutils.replaceUrls(sheet, item.relhref, ignoreImportRules=True)
        style.text += '\n' + sheet.cssText

    def replace_css(self, css):
        manifest = self.oeb.manifest
        id, href = manifest.generate('css', 'stylesheet.css')
        for item in manifest.values():
            if item.media_type in OEB_STYLES:
                manifest.remove(item)
        item = manifest.add(id, href, CSS_MIME, data=css)
        return href

    def flatten_spine(self):
        names = defaultdict(int)
        styles = {}
        for item in self.oeb.spine:
            html = item.data
            stylizer = self.stylizers[item]
            if self.specializer is not None:
                self.specializer(item, stylizer)
            body = html.find(XHTML('body'))
            fsize = self.context.dest.fbase
            self.flatten_node(body, stylizer, names, styles, fsize, item.id)
        items = [(key, val) for (val, key) in styles.items()]
        items.sort()
        css = ''.join(".%s {\n%s;\n}\n\n" % (key, val) for key, val in items)
        href = self.replace_css(css)
        for item in self.oeb.spine:
            stylizer = self.stylizers[item]
            self.flatten_head(item, stylizer, href)

