#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os
import posixpath
from collections import namedtuple
from functools import partial
from future_builtins import map

from lxml import etree

from calibre import fit_image
from calibre.ebooks.oeb.base import urlunquote
from calibre.ebooks.docx.images import pt_to_emu
from calibre.utils.filenames import ascii_filename
from calibre.utils.imghdr import identify

Image = namedtuple('Image', 'rid fname width height fmt item')


def as_num(x):
    try:
        return float(x)
    except Exception:
        pass
    return 0


def get_image_margins(style):
    ans = {}
    for edge in 'Left Right Top Bottom'.split():
        val = as_num(getattr(style, 'padding' + edge)) + as_num(getattr(style, 'margin' + edge))
        ans['dist' + edge[0]] = str(pt_to_emu(val))
    return ans


class ImagesManager(object):

    def __init__(self, oeb, document_relationships, opts):
        self.oeb, self.log = oeb, oeb.log
        self.page_width, self.page_height = opts.output_profile.width_pts, opts.output_profile.height_pts
        self.images = {}
        self.seen_filenames = set()
        self.document_relationships = document_relationships
        self.count = 0

    def read_image(self, href):
        if href not in self.images:
            item = self.oeb.manifest.hrefs.get(href)
            if item is None or not isinstance(item.data, bytes):
                return
            try:
                fmt, width, height = identify(item.data)
            except Exception:
                self.log.warning('Replacing corrupted image with blank: %s' % href)
                item.data = I('blank.png', data=True, allow_user_override=False)
                fmt, width, height = identify(item.data)
            image_fname = 'media/' + self.create_filename(href, fmt)
            image_rid = self.document_relationships.add_image(image_fname)
            self.images[href] = Image(image_rid, image_fname, width, height, fmt, item)
            item.unload_data_from_memory()
        return self.images[href]

    def add_image(self, img, block, stylizer, bookmark=None, as_block=False):
        src = img.get('src')
        if not src:
            return
        href = self.abshref(src)
        try:
            rid = self.read_image(href).rid
        except AttributeError:
            return
        drawing = self.create_image_markup(img, stylizer, href, as_block=as_block)
        block.add_image(drawing, bookmark=bookmark)
        return rid

    def create_image_markup(self, html_img, stylizer, href, as_block=False):
        # TODO: img inside a link (clickable image)
        style = stylizer.style(html_img)
        floating = style['float']
        if floating not in {'left', 'right'}:
            floating = None
        if as_block:
            ml, mr = style._get('margin-left'), style._get('margin-right')
            if ml == 'auto':
                floating = 'center' if mr == 'auto' else 'right'
            if mr == 'auto':
                floating = 'center' if ml == 'auto' else 'right'
        else:
            parent = html_img.getparent()
            if len(parent) == 1 and not (parent.text or '').strip() and not (html_img.tail or '').strip():
                # We have an inline image alone inside a block
                pstyle = stylizer.style(parent)
                if pstyle['text-align'] in ('center', 'right') and 'block' in pstyle['display']:
                    floating = pstyle['text-align']
        fake_margins = floating is None
        self.count += 1
        img = self.images[href]
        name = urlunquote(posixpath.basename(href))
        width, height = style.img_size(img.width, img.height)
        scaled, width, height = fit_image(width, height, self.page_width, self.page_height)
        width, height = map(pt_to_emu, (width, height))

        makeelement, namespaces = self.document_relationships.namespace.makeelement, self.document_relationships.namespace.namespaces

        root = etree.Element('root', nsmap=namespaces)
        ans = makeelement(root, 'w:drawing', append=False)
        if floating is None:
            parent = makeelement(ans, 'wp:inline')
        else:
            parent = makeelement(ans, 'wp:anchor', **get_image_margins(style))
            # The next three lines are boilerplate that Word requires, even
            # though the DOCX specs define defaults for all of them
            parent.set('simplePos', '0'), parent.set('relativeHeight', '1'), parent.set('behindDoc',"0"), parent.set('locked', "0")
            parent.set('layoutInCell', "1"), parent.set('allowOverlap', '1')
            makeelement(parent, 'wp:simplePos', x='0', y='0')
            makeelement(makeelement(parent, 'wp:positionH', relativeFrom='margin'), 'wp:align').text = floating
            makeelement(makeelement(parent, 'wp:positionV', relativeFrom='line'), 'wp:align').text = 'top'
        makeelement(parent, 'wp:extent', cx=str(width), cy=str(height))
        if fake_margins:
            # DOCX does not support setting margins for inline images, so we
            # fake it by using effect extents to simulate margins
            makeelement(parent, 'wp:effectExtent', **{k[-1].lower():v for k, v in get_image_margins(style).iteritems()})
        else:
            makeelement(parent, 'wp:effectExtent', l='0', r='0', t='0', b='0')
        if floating is not None:
            # The idiotic Word requires this to be after the extent settings
            if as_block:
                makeelement(parent, 'wp:wrapTopAndBottom')
            else:
                makeelement(parent, 'wp:wrapSquare', wrapText='bothSides')
        self.create_docx_image_markup(parent, name, html_img.get('alt') or name, img.rid, width, height)
        return ans

    def create_docx_image_markup(self, parent, name, alt, img_rid, width, height):
        makeelement, namespaces = self.document_relationships.namespace.makeelement, self.document_relationships.namespace.namespaces
        makeelement(parent, 'wp:docPr', id=str(self.count), name=name, descr=alt)
        makeelement(makeelement(parent, 'wp:cNvGraphicFramePr'), 'a:graphicFrameLocks', noChangeAspect="1")
        g = makeelement(parent, 'a:graphic')
        gd = makeelement(g, 'a:graphicData', uri=namespaces['pic'])
        pic = makeelement(gd, 'pic:pic')
        nvPicPr = makeelement(pic, 'pic:nvPicPr')
        makeelement(nvPicPr, 'pic:cNvPr', id='0', name=name, descr=alt)
        makeelement(nvPicPr, 'pic:cNvPicPr')
        bf = makeelement(pic, 'pic:blipFill')
        makeelement(bf, 'a:blip', r_embed=img_rid)
        makeelement(makeelement(bf, 'a:stretch'), 'a:fillRect')
        spPr = makeelement(pic, 'pic:spPr')
        xfrm = makeelement(spPr, 'a:xfrm')
        makeelement(xfrm, 'a:off', x='0', y='0'), makeelement(xfrm, 'a:ext', cx=str(width), cy=str(height))
        makeelement(makeelement(spPr, 'a:prstGeom', prst='rect'), 'a:avLst')

    def create_filename(self, href, fmt):
        fname = ascii_filename(urlunquote(posixpath.basename(href)))
        fname = posixpath.splitext(fname)[0]
        fname = fname[:75].rstrip('.') or 'image'
        num = 0
        base = fname
        while fname.lower() in self.seen_filenames:
            num += 1
            fname = base + str(num)
        self.seen_filenames.add(fname.lower())
        fname += os.extsep + fmt.lower()
        return fname

    def serialize(self, images_map):
        for img in self.images.itervalues():
            images_map['word/' + img.fname] = partial(self.get_data, img.item)

    def get_data(self, item):
        try:
            return item.data
        finally:
            item.unload_data_from_memory(False)

    def create_cover_markup(self, img, width, height):
        self.count += 1
        makeelement, namespaces = self.document_relationships.namespace.makeelement, self.document_relationships.namespace.namespaces

        root = etree.Element('root', nsmap=namespaces)
        ans = makeelement(root, 'w:drawing', append=False)
        parent = makeelement(ans, 'wp:anchor', **{'dist'+edge:'0' for edge in 'LRTB'})
        parent.set('simplePos', '0'), parent.set('relativeHeight', '1'), parent.set('behindDoc',"0"), parent.set('locked', "0")
        parent.set('layoutInCell', "1"), parent.set('allowOverlap', '1')
        makeelement(parent, 'wp:simplePos', x='0', y='0')
        makeelement(makeelement(parent, 'wp:positionH', relativeFrom='page'), 'wp:align').text = 'center'
        makeelement(makeelement(parent, 'wp:positionV', relativeFrom='page'), 'wp:align').text = 'center'
        width, height = map(pt_to_emu, (width, height))
        makeelement(parent, 'wp:extent', cx=str(width), cy=str(height))
        makeelement(parent, 'wp:effectExtent', l='0', r='0', t='0', b='0')
        makeelement(parent, 'wp:wrapTopAndBottom')
        self.create_docx_image_markup(parent, 'cover.jpg', _('Cover'), img.rid, width, height)
        return ans

    def write_cover_block(self, body, cover_image):
        makeelement, namespaces = self.document_relationships.namespace.makeelement, self.document_relationships.namespace.namespaces
        pbb = body[0].xpath('//*[local-name()="pageBreakBefore"]')[0]
        pbb.set('{%s}val' % namespaces['w'], 'on')
        p = makeelement(body, 'w:p', append=False)
        body.insert(0, p)
        r = makeelement(p, 'w:r')
        r.append(cover_image)
