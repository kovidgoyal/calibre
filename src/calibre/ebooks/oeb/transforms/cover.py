#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap, cStringIO
from urllib import unquote

from lxml import etree
try:
    from PIL import Image as PILImage
    PILImage
except ImportError:
    import Image as PILImage

from calibre import __appname__, __version__, guess_type

class CoverManager(object):

    SVG_TEMPLATE = textwrap.dedent('''\
        <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
            <head>
                <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
                <meta name="calibre:cover" content="true" />
                <title>Cover</title>
                <style type="text/css" title="override_css">
                    @page {padding: 0pt; margin:0pt}
                    body { text-align: center; padding:0pt; margin: 0pt; }
                </style>
            </head>
            <body>
                <svg version="1.1" xmlns="http://www.w3.org/2000/svg"
                    xmlns:xlink="http://www.w3.org/1999/xlink"
                    width="100%%" height="100%%" viewBox="__viewbox__"
                    preserveAspectRatio="__ar__">
                    <image width="__width__" height="__height__" xlink:href="%s"/>
                </svg>
            </body>
        </html>
        ''')

    NONSVG_TEMPLATE = textwrap.dedent('''\
        <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
            <head>
                <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
                <meta name="calibre:cover" content="true" />
                <title>Cover</title>
                <style type="text/css" title="override_css">
                    @page {padding: 0pt; margin:0pt}
                    body { text-align: center; padding:0pt; margin: 0pt }
                    div { padding:0pt; margin: 0pt }
                    img { padding:0pt; margin: 0pt }
                </style>
            </head>
            <body>
                <div>
                    <img src="%s" alt="cover" __style__ />
                </div>
            </body>
        </html>
    ''')


    def __init__(self, no_default_cover=False, no_svg_cover=False,
            preserve_aspect_ratio=False, fixed_size=None):
        self.no_default_cover = no_default_cover
        self.no_svg_cover = no_svg_cover
        self.preserve_aspect_ratio = preserve_aspect_ratio

        ar = 'xMidYMid meet' if preserve_aspect_ratio else 'none'
        self.svg_template = self.SVG_TEMPLATE.replace('__ar__', ar)

        if fixed_size is None:
            style = 'style="height: 100%%"'
        else:
            width, height = fixed_size
            style = 'style="height: %s; width: %s"'%(width, height)
        self.non_svg_template = self.NONSVG_TEMPLATE.replace('__style__',
                style)

    def __call__(self, oeb, opts, log):
        self.oeb = oeb
        self.log = log
        self.insert_cover()

    def default_cover(self):
        '''
        Create a generic cover for books that dont have a cover
        '''
        from calibre.utils.pil_draw import draw_centered_text
        from calibre.ebooks.metadata import authors_to_string
        if self.no_default_cover:
            return None
        self.log('Generating default cover')
        m = self.oeb.metadata
        title = unicode(m.title[0])
        authors = [unicode(x) for x in m.creator if x.role == 'aut']

        cover_file = cStringIO.StringIO()
        try:
            try:
                from PIL import Image, ImageDraw, ImageFont
                Image, ImageDraw, ImageFont
            except ImportError:
                import Image, ImageDraw, ImageFont
            font_path = P('fonts/liberation/LiberationSerif-Bold.ttf')
            app = '['+__appname__ +' '+__version__+']'

            COVER_WIDTH, COVER_HEIGHT = 590, 750
            img = Image.new('RGB', (COVER_WIDTH, COVER_HEIGHT), 'white')
            draw = ImageDraw.Draw(img)
            # Title
            font = ImageFont.truetype(font_path, 44)
            bottom = draw_centered_text(img, draw, font, title, 15, ysep=9)
            # Authors
            bottom += 14
            font = ImageFont.truetype(font_path, 32)
            authors = authors_to_string(authors)
            bottom = draw_centered_text(img, draw, font, authors, bottom, ysep=7)
            # Vanity
            font = ImageFont.truetype(font_path, 28)
            width, height = draw.textsize(app, font=font)
            left = max(int((COVER_WIDTH - width)/2.), 0)
            top = COVER_HEIGHT - height - 15
            draw.text((left, top), app, fill=(0,0,0), font=font)
            # Logo
            logo = Image.open(I('library.png'), 'r')
            width, height = logo.size
            left = max(int((COVER_WIDTH - width)/2.), 0)
            top = max(int((COVER_HEIGHT - height)/2.), 0)
            img.paste(logo, (left, max(bottom, top)))
            img = img.convert('RGB').convert('P', palette=Image.ADAPTIVE)

            img.convert('RGB').save(cover_file, 'JPEG')
            cover_file.flush()
            id, href = self.oeb.manifest.generate('cover_image', 'cover_image.jpg')
            item = self.oeb.manifest.add(id, href, guess_type('t.jpg')[0],
                        data=cover_file.getvalue())
            m.clear('cover')
            m.add('cover', item.id)

            return item.href
        except:
            self.log.exception('Failed to generate default cover')
        return None

    def inspect_cover(self, href):
        from calibre.ebooks.oeb.base import urlnormalize
        for x in self.oeb.manifest:
            if x.href == urlnormalize(href):
                try:
                    raw = x.data
                    f = cStringIO.StringIO(raw)
                    im = PILImage.open(f)
                    return im.size
                except:
                    self.log.exception('Failed to read image dimensions')
        return None, None

    def insert_cover(self):
        from calibre.ebooks.oeb.base import urldefrag
        g, m = self.oeb.guide, self.oeb.manifest
        item = None
        if 'titlepage' not in g:
            if 'cover' in g:
                href = g['cover'].href
            else:
                href = self.default_cover()
            width, height = self.inspect_cover(href)
            if width is None or height is None:
                self.log.warning('Failed to read cover dimensions')
                width, height = 600, 800
            if self.preserve_aspect_ratio:
                width, height = 600, 800
            self.svg_template = self.svg_template.replace('__viewbox__',
                    '0 0 %d %d'%(width, height))
            self.svg_template = self.svg_template.replace('__width__',
                    str(width))
            self.svg_template = self.svg_template.replace('__height__',
                    str(height))

            if href is not None:
                templ = self.non_svg_template if self.no_svg_cover \
                        else self.svg_template
                tp = templ%unquote(href)
                id, href = m.generate('titlepage', 'titlepage.xhtml')
                item = m.add(id, href, guess_type('t.xhtml')[0],
                        data=etree.fromstring(tp))
        else:
            item = self.oeb.manifest.hrefs[
                    urldefrag(self.oeb.guide['titlepage'].href)[0]]
        if item is not None:
            self.oeb.spine.insert(0, item, True)
            if 'cover' not in self.oeb.guide.refs:
                self.oeb.guide.add('cover', 'Title Page', 'a')
            self.oeb.guide.refs['cover'].href = item.href
            if 'titlepage' in self.oeb.guide.refs:
                self.oeb.guide.refs['titlepage'].href = item.href


