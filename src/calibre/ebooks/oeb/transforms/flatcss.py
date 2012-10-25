'''
CSS flattening transform.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import re, operator, math
from collections import defaultdict
from xml.dom import SyntaxErr

from lxml import etree
import cssutils
from cssutils.css import Property

from calibre import guess_type
from calibre.ebooks.oeb.base import (XHTML, XHTML_NS, CSS_MIME, OEB_STYLES,
        namespace, barename, XPath)
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.utils.filenames import ascii_filename

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

class EmbedFontsCSSRules(object):

    def __init__(self, body_font_family, rules):
        self.body_font_family, self.rules = body_font_family, rules
        self.href = None

    def __call__(self, oeb):
        if not self.body_font_family: return None
        if not self.href:
            iid, href = oeb.manifest.generate(u'page_styles', u'page_styles.css')
            rules = [x.cssText for x in self.rules]
            rules = u'\n\n'.join(rules)
            sheet = cssutils.parseString(rules, validate=False)
            self.href = oeb.manifest.add(iid, href, guess_type(href)[0],
                    data=sheet).href
        return self.href

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

        self.body_font_family, self.embed_font_rules = self.get_embed_font_info(
                self.opts.embed_font_family)
        # Store for use in output plugins/transforms that generate content,
        # like the AZW3 output inline ToC.
        self.oeb.store_embed_font_rules = EmbedFontsCSSRules(self.body_font_family,
                self.embed_font_rules)
        self.stylize_spine()
        self.sbase = self.baseline_spine() if self.fbase else None
        self.fmap = FontMapper(self.sbase, self.fbase, self.fkey)
        self.flatten_spine()

    def get_embed_font_info(self, family, failure_critical=True):
        efi = []
        body_font_family = None
        if not family:
            return body_font_family, efi
        from calibre.utils.fonts import fontconfig
        from calibre.utils.fonts.utils import (get_font_characteristics,
                panose_to_css_generic_family, get_font_names)
        faces = fontconfig.fonts_for_family(family)
        if not faces or not u'normal' in faces:
            msg = (u'No embeddable fonts found for family: %r'%self.opts.embed_font_family)
            if failure_critical:
                raise ValueError(msg)
            self.oeb.log.warn(msg)
            return body_font_family, efi

        for k, v in faces.iteritems():
            ext, data = v[0::2]
            weight, is_italic, is_bold, is_regular, fs_type, panose = \
                get_font_characteristics(data)
            generic_family = panose_to_css_generic_family(panose)
            family_name, subfamily_name, full_name = get_font_names(data)
            if k == u'normal':
                body_font_family = u"'%s',%s"%(family_name, generic_family)
                if family_name.lower() != family.lower():
                    self.oeb.log.warn(u'Failed to find an exact match for font:'
                            u' %r, using %r instead'%(family, family_name))
                else:
                    self.oeb.log(u'Embedding font: %s'%family_name)
            font = {u'font-family':u'"%s"'%family_name}
            if is_italic:
                font[u'font-style'] = u'italic'
            if is_bold:
                font[u'font-weight'] = u'bold'
            fid, href = self.oeb.manifest.generate(id=u'font',
                href=u'%s.%s'%(ascii_filename(full_name).replace(u' ', u'-'), ext))
            item = self.oeb.manifest.add(fid, href,
                    guess_type(full_name+'.'+ext)[0],
                    data=data)
            item.unload_data_from_memory()
            font[u'src'] = u'url(%s)'%item.href
            rule = '@font-face { %s }'%('; '.join(u'%s:%s'%(k, v) for k, v in
                font.iteritems()))
            rule = cssutils.parseString(rule)
            efi.append(rule)

        return body_font_family, efi

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
            if float(self.context.margin_left) >= 0:
                bs.append('margin-left : %gpt'%\
                        float(self.context.margin_left))
            if float(self.context.margin_right) >= 0:
                bs.append('margin-right : %gpt'%\
                        float(self.context.margin_right))
            bs.extend(['padding-left: 0pt', 'padding-right: 0pt'])
            if self.page_break_on_body:
                bs.extend(['page-break-before: always'])
            if self.context.change_justification != 'original':
                bs.append('text-align: '+ self.context.change_justification)
            if self.body_font_family:
                bs.append(u'font-family: '+self.body_font_family)
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

    def flatten_node(self, node, stylizer, names, styles, pseudo_styles, psize, item_id):
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
            try:
                cssdict['color'] = Property('color', node.attrib['color']).value
            except (ValueError, SyntaxErr):
                pass
            del node.attrib['color']
        if 'bgcolor' in node.attrib:
            try:
                cssdict['background-color'] = Property('background-color', node.attrib['bgcolor']).value
            except ValueError:
                pass
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

        pseudo_classes = style.pseudo_classes(self.filter_css)
        if cssdict or pseudo_classes:
            keep_classes = set()

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
                keep_classes.add(match)

            for psel, cssdict in pseudo_classes.iteritems():
                items = sorted(cssdict.iteritems())
                css = u';\n'.join(u'%s: %s' % (key, val) for key, val in items)
                pstyles = pseudo_styles[psel]
                if css in pstyles:
                    match = pstyles[css]
                else:
                    # We have to use a different class for each psel as
                    # otherwise you can have incorrect styles for a situation
                    # like: a:hover { color: red } a:link { color: blue } a.x:hover { color: green }
                    # If the pcalibre class for a:hover and a:link is the same,
                    # then the class attribute for a.x tags will contain both
                    # that class and the class for a.x:hover, which is wrong.
                    klass = 'pcalibre'
                    match = klass + str(names[klass] or '')
                    pstyles[css] = match
                    names[klass] += 1
                keep_classes.add(match)
                node.attrib['class'] = ' '.join(keep_classes)

        elif 'class' in node.attrib:
            del node.attrib['class']
        if 'style' in node.attrib:
            del node.attrib['style']
        for child in node:
            self.flatten_node(child, stylizer, names, styles, pseudo_styles, psize, item_id)

    def flatten_head(self, item, href, global_href):
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
        l = etree.SubElement(head, XHTML('link'),
            rel='stylesheet', type=CSS_MIME, href=href)
        l.tail='\n'
        if global_href:
            href = item.relhref(global_href)
            l = etree.SubElement(head, XHTML('link'),
                rel='stylesheet', type=CSS_MIME, href=href)
            l.tail = '\n'

    def replace_css(self, css):
        manifest = self.oeb.manifest
        for item in manifest.values():
            if item.media_type in OEB_STYLES:
                manifest.remove(item)
        id, href = manifest.generate('css', 'stylesheet.css')
        item = manifest.add(id, href, CSS_MIME, data=cssutils.parseString(css,
            validate=False))
        self.oeb.manifest.main_stylesheet = item
        return href

    def collect_global_css(self):
        global_css = defaultdict(list)
        for item in self.oeb.spine:
            stylizer = self.stylizers[item]
            if float(self.context.margin_top) >= 0:
                stylizer.page_rule['margin-top'] = '%gpt'%\
                        float(self.context.margin_top)
            if float(self.context.margin_bottom) >= 0:
                stylizer.page_rule['margin-bottom'] = '%gpt'%\
                        float(self.context.margin_bottom)
            items = stylizer.page_rule.items()
            items.sort()
            css = ';\n'.join("%s: %s" % (key, val) for key, val in items)
            css = ('@page {\n%s\n}\n'%css) if items else ''
            rules = [r.cssText for r in stylizer.font_face_rules +
                    self.embed_font_rules]
            raw = '\n\n'.join(rules)
            css += '\n\n' + raw
            global_css[css].append(item)

        gc_map = {}
        manifest = self.oeb.manifest
        for css in global_css:
            href = None
            if css.strip():
                id_, href = manifest.generate('page_css', 'page_styles.css')
                manifest.add(id_, href, CSS_MIME, data=cssutils.parseString(css,
                    validate=False))
            gc_map[css] = href

        ans = {}
        for css, items in global_css.iteritems():
            for item in items:
                ans[item] = gc_map[css]
        return ans

    def flatten_spine(self):
        names = defaultdict(int)
        styles, pseudo_styles = {}, defaultdict(dict)
        for item in self.oeb.spine:
            html = item.data
            stylizer = self.stylizers[item]
            if self.specializer is not None:
                self.specializer(item, stylizer)
            body = html.find(XHTML('body'))
            fsize = self.context.dest.fbase
            self.flatten_node(body, stylizer, names, styles, pseudo_styles, fsize, item.id)
        items = [(key, val) for (val, key) in styles.items()]
        items.sort()
        # :hover must come after link and :active must come after :hover
        psels = sorted(pseudo_styles.iterkeys(), key=lambda x :
                {'hover':1, 'active':2}.get(x, 0))
        for psel in psels:
            styles = pseudo_styles[psel]
            if not styles: continue
            x = sorted(((k+':'+psel, v) for v, k in styles.iteritems()))
            items.extend(x)

        css = ''.join(".%s {\n%s;\n}\n\n" % (key, val) for key, val in items)

        href = self.replace_css(css)
        global_css = self.collect_global_css()
        for item in self.oeb.spine:
            stylizer = self.stylizers[item]
            self.flatten_head(item, href, global_css[item])

