# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into a single (more or less) HTML file.
'''

import os

from functools import partial
from lxml import html
from urlparse import urldefrag

from calibre import prepare_string_for_xml
from calibre.ebooks.oeb.base import XHTML, XHTML_NS, barename, namespace,\
    OEB_IMAGES, XLINK, rewrite_links, urlnormalize
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.utils.logging import default_log

class OEB2HTML(object):
    '''
    Base class. All subclasses should implement dump_text to actually transform
    content. Also, callers should use oeb2html to get the transformed html.
    links and images can be retrieved after calling oeb2html to get the mapping
    of OEB links and images to the new names used in the html returned by oeb2html.
    Images will always be referenced as if they are in an images directory.

    Use get_css to get the CSS classes for the OEB document as a string.
    '''

    def __init__(self, log=None):
        self.log = default_log if log is None else log
        self.links = {}
        self.images = {}

    def oeb2html(self, oeb_book, opts):
        self.log.info('Converting OEB book to HTML...')
        self.opts = opts
        self.links = {}
        self.images = {}
        self.base_hrefs = [item.href for item in oeb_book.spine]
        self.map_resources(oeb_book)

        return self.mlize_spine(oeb_book)

    def mlize_spine(self, oeb_book):
        output = [u'<html><body><head><meta http-equiv="Content-Type" content="text/html;charset=utf-8" /></head>']
        for item in oeb_book.spine:
            self.log.debug('Converting %s to HTML...' % item.href)
            self.rewrite_ids(item.data, item)
            rewrite_links(item.data, partial(self.rewrite_link, page=item))
            stylizer = Stylizer(item.data, item.href, oeb_book, self.opts)
            output += self.dump_text(item.data.find(XHTML('body')), stylizer, item)
            output.append('\n\n')
        output.append('</body></html>')
        return ''.join(output)

    def dump_text(self, elem, stylizer, page):
        raise NotImplementedError

    def get_link_id(self, href, id=''):
        if id:
            href += '#%s' % id
        if href not in self.links:
            self.links[href] = '#calibre_link-%s' % len(self.links.keys())
        return self.links[href]

    def map_resources(self, oeb_book):
        for item in oeb_book.manifest:
            if item.media_type in OEB_IMAGES:
                if item.href not in self.images:
                    ext = os.path.splitext(item.href)[1]
                    fname = '%s%s' % (len(self.images), ext)
                    fname = fname.zfill(10)
                    self.images[item.href] = fname
            if item in oeb_book.spine:
                self.get_link_id(item.href)
                root = item.data.find(XHTML('body'))
                link_attrs = set(html.defs.link_attrs)
                link_attrs.add(XLINK('href'))
                for el in root.iter():
                    attribs = el.attrib
                    try:
                        if not isinstance(el.tag, basestring):
                            continue
                    except:
                        continue
                    for attr in attribs:
                        if attr in link_attrs:
                            href = item.abshref(attribs[attr])
                            href, id = urldefrag(href)
                            if href in self.base_hrefs:
                                self.get_link_id(href, id)

    def rewrite_link(self, url, page=None):
        if not page:
            return url
        abs_url = page.abshref(urlnormalize(url))
        if abs_url in self.images:
            return 'images/%s' % self.images[abs_url]
        if abs_url in self.links:
            return self.links[abs_url]
        return url

    def rewrite_ids(self, root, page):
        for el in root.iter():
            try:
                tag = el.tag
            except UnicodeDecodeError:
                continue
            if tag == XHTML('body'):
                el.attrib['id'] = self.get_link_id(page.href)[1:]
                continue
            if 'id' in el.attrib:
                el.attrib['id'] = self.get_link_id(page.href, el.attrib['id'])[1:]

    def get_css(self, oeb_book):
        css = b''
        for item in oeb_book.manifest:
            if item.media_type == 'text/css':
                css += item.data.cssText + b'\n\n'
        return css

    def prepare_string_for_html(self, raw):
        raw = prepare_string_for_xml(raw)
        raw = raw.replace(u'\u00ad', '&shy;')
        raw = raw.replace(u'\u2014', '&mdash;')
        raw = raw.replace(u'\u2013', '&ndash;')
        raw = raw.replace(u'\u00a0', '&nbsp;')
        return raw


class OEB2HTMLNoCSSizer(OEB2HTML):
    '''
    This will remap a small number of CSS styles to equivalent HTML tags.
    '''

    def dump_text(self, elem, stylizer, page):
        '''
        @elem: The element in the etree that we are working on.
        @stylizer: The style information attached to the element.
        '''

        # We can only processes tags. If there isn't a tag return any text.
        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) != XHTML_NS:
            p = elem.getparent()
            if p is not None and isinstance(p.tag, basestring) and namespace(p.tag) == XHTML_NS \
                    and elem.tail:
                return [elem.tail]
            return ['']

        # Setup our variables.
        text = ['']
        style = stylizer.style(elem)
        tags = []
        tag = barename(elem.tag)
        attribs = elem.attrib

        if tag == 'body':
            tag = 'div'
        tags.append(tag)

        # Ignore anything that is set to not be displayed.
        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            return ['']

        # Remove attributes we won't want.
        if 'class' in attribs:
            del attribs['class']
        if 'style' in attribs:
            del attribs['style']

        # Turn the rest of the attributes into a string we can write with the tag.
        at = ''
        for k, v in attribs.items():
            at += ' %s="%s"' % (k, prepare_string_for_xml(v, attribute=True))

        # Write the tag.
        text.append('<%s%s>' % (tag, at))

        # Turn styles into tags.
        if style['font-weight'] in ('bold', 'bolder'):
            text.append('<b>')
            tags.append('b')
        if style['font-style'] == 'italic':
            text.append('<i>')
            tags.append('i')
        if style['text-decoration'] == 'underline':
            text.append('<u>')
            tags.append('u')
        if style['text-decoration'] == 'line-through':
            text.append('<s>')
            tags.append('s')

        # Process tags that contain text.
        if hasattr(elem, 'text') and elem.text:
            text.append(self.prepare_string_for_html(elem.text))

        # Recurse down into tags within the tag we are in.
        for item in elem:
            text += self.dump_text(item, stylizer, page)

        # Close all open tags.
        tags.reverse()
        for t in tags:
            text.append('</%s>' % t)

        # Add the text that is outside of the tag.
        if hasattr(elem, 'tail') and elem.tail:
            text.append(self.prepare_string_for_html(elem.tail))

        return text


class OEB2HTMLInlineCSSizer(OEB2HTML):
    '''
    Turns external CSS classes into inline style attributes.
    '''

    def dump_text(self, elem, stylizer, page):
        '''
        @elem: The element in the etree that we are working on.
        @stylizer: The style information attached to the element.
        '''

        # We can only processes tags. If there isn't a tag return any text.
        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) != XHTML_NS:
            p = elem.getparent()
            if p is not None and isinstance(p.tag, basestring) and namespace(p.tag) == XHTML_NS \
                    and elem.tail:
                return [elem.tail]
            return ['']

        # Setup our variables.
        text = ['']
        style = stylizer.style(elem)
        tags = []
        tag = barename(elem.tag)
        attribs = elem.attrib

        style_a = '%s' % style
        if tag == 'body':
            tag = 'div'
            if not style['page-break-before'] == 'always':
                style_a = 'page-break-before: always;' + ' ' if style_a else '' + style_a
        tags.append(tag)

        # Remove attributes we won't want.
        if 'class' in attribs:
            del attribs['class']
        if 'style' in attribs:
            del attribs['style']

        # Turn the rest of the attributes into a string we can write with the tag.
        at = ''
        for k, v in attribs.items():
            at += ' %s="%s"' % (k, prepare_string_for_xml(v, attribute=True))

        # Turn style into strings for putting in the tag.
        style_t = ''
        if style_a:
            style_t = ' style="%s"' % style_a

        # Write the tag.
        text.append('<%s%s%s>' % (tag, at, style_t))

        # Process tags that contain text.
        if hasattr(elem, 'text') and elem.text:
            text.append(self.prepare_string_for_html(elem.text))

        # Recurse down into tags within the tag we are in.
        for item in elem:
            text += self.dump_text(item, stylizer, page)

        # Close all open tags.
        tags.reverse()
        for t in tags:
            text.append('</%s>' % t)

        # Add the text that is outside of the tag.
        if hasattr(elem, 'tail') and elem.tail:
            text.append(self.prepare_string_for_html(elem.tail))

        return text


class OEB2HTMLClassCSSizer(OEB2HTML):
    '''
    Use CSS classes. css_style option can specify whether to use
    inline classes (style tag in the head) or reference an external
    CSS file called style.css.
    '''

    def mlize_spine(self, oeb_book):
        output = []
        for item in oeb_book.spine:
            self.log.debug('Converting %s to HTML...' % item.href)
            self.rewrite_ids(item.data, item)
            rewrite_links(item.data, partial(self.rewrite_link, page=item))
            stylizer = Stylizer(item.data, item.href, oeb_book, self.opts)
            output += self.dump_text(item.data.find(XHTML('body')), stylizer, item)
            output.append('\n\n')
        if self.opts.htmlz_class_style == 'external':
            css = u'<link href="style.css" rel="stylesheet" type="text/css" />'
        else:
            css =  u'<style type="text/css">' + self.get_css(oeb_book) + u'</style>'
        output = [u'<html><head><meta http-equiv="Content-Type" content="text/html;charset=utf-8" />'] + [css] + [u'</head><body>'] + output + [u'</body></html>']
        return ''.join(output)

    def dump_text(self, elem, stylizer, page):
        '''
        @elem: The element in the etree that we are working on.
        @stylizer: The style information attached to the element.
        '''

        # We can only processes tags. If there isn't a tag return any text.
        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) != XHTML_NS:
            p = elem.getparent()
            if p is not None and isinstance(p.tag, basestring) and namespace(p.tag) == XHTML_NS \
                    and elem.tail:
                return [elem.tail]
            return ['']

        # Setup our variables.
        text = ['']
        tags = []
        tag = barename(elem.tag)
        attribs = elem.attrib

        if tag == 'body':
            tag = 'div'
        tags.append(tag)

        # Remove attributes we won't want.
        if 'style' in attribs:
            del attribs['style']

        # Turn the rest of the attributes into a string we can write with the tag.
        at = ''
        for k, v in attribs.items():
            at += ' %s="%s"' % (k, prepare_string_for_xml(v, attribute=True))

        # Write the tag.
        text.append('<%s%s>' % (tag, at))

        # Process tags that contain text.
        if hasattr(elem, 'text') and elem.text:
            text.append(self.prepare_string_for_html(elem.text))

        # Recurse down into tags within the tag we are in.
        for item in elem:
            text += self.dump_text(item, stylizer, page)

        # Close all open tags.
        tags.reverse()
        for t in tags:
            text.append('</%s>' % t)

        # Add the text that is outside of the tag.
        if hasattr(elem, 'tail') and elem.tail:
            text.append(self.prepare_string_for_html(elem.tail))

        return text


def oeb2html_no_css(oeb_book, log, opts):
    izer = OEB2HTMLNoCSSizer(log)
    html = izer.oeb2html(oeb_book, opts)
    images = izer.images
    return (html, images)

def oeb2html_inline_css(oeb_book, log, opts):
    izer = OEB2HTMLInlineCSSizer(log)
    html = izer.oeb2html(oeb_book, opts)
    images = izer.images
    return (html, images)

def oeb2html_class_css(oeb_book, log, opts):
    izer = OEB2HTMLClassCSSizer(log)
    setattr(opts, 'class_style', 'inline')
    html = izer.oeb2html(oeb_book, opts)
    images = izer.images
    return (html, images)
