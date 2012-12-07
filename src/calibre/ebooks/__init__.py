from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Code for the conversion of ebook formats and the reading of metadata
from various formats.
'''

import traceback, os, re
from cStringIO import StringIO
from calibre import CurrentDir, force_unicode

class ConversionError(Exception):

    def __init__(self, msg, only_msg=False):
        Exception.__init__(self, msg)
        self.only_msg = only_msg

class UnknownFormatError(Exception):
    pass

class DRMError(ValueError):
    pass

class ParserError(ValueError):
    pass

BOOK_EXTENSIONS = ['lrf', 'rar', 'zip', 'rtf', 'lit', 'txt', 'txtz', 'text', 'htm', 'xhtm',
                   'html', 'htmlz', 'xhtml', 'pdf', 'pdb', 'updb', 'pdr', 'prc', 'mobi', 'azw', 'doc',
                   'epub', 'fb2', 'djv', 'djvu', 'lrx', 'cbr', 'cbz', 'cbc', 'oebzip',
                   'rb', 'imp', 'odt', 'chm', 'tpz', 'azw1', 'pml', 'pmlz', 'mbp', 'tan', 'snb',
                   'xps', 'oxps', 'azw4', 'book', 'zbf', 'pobi', 'docx', 'md',
                   'textile', 'markdown', 'ibook', 'iba', 'azw3', 'ps']

class HTMLRenderer(object):

    def __init__(self, page, loop):
        self.page, self.loop = page, loop
        self.data = ''
        self.exception = self.tb = None

    def __call__(self, ok):
        from PyQt4.Qt import QImage, QPainter, QByteArray, QBuffer
        try:
            if not ok:
                raise RuntimeError('Rendering of HTML failed.')
            de = self.page.mainFrame().documentElement()
            pe = de.findFirst('parsererror')
            if not pe.isNull():
                raise ParserError(pe.toPlainText())
            image = QImage(self.page.viewportSize(), QImage.Format_ARGB32)
            image.setDotsPerMeterX(96*(100/2.54))
            image.setDotsPerMeterY(96*(100/2.54))
            painter = QPainter(image)
            self.page.mainFrame().render(painter)
            painter.end()
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QBuffer.WriteOnly)
            image.save(buf, 'JPEG')
            self.data = str(ba.data())
        except Exception as e:
            self.exception = e
            self.traceback = traceback.format_exc()
        finally:
            self.loop.exit(0)


def extract_cover_from_embedded_svg(html, base, log):
    from lxml import etree
    from calibre.ebooks.oeb.base import XPath, SVG, XLINK
    root = etree.fromstring(html)

    svg = XPath('//svg:svg')(root)
    if len(svg) == 1 and len(svg[0]) == 1 and svg[0][0].tag == SVG('image'):
        image = svg[0][0]
        href = image.get(XLINK('href'), None)
        path = os.path.join(base, *href.split('/'))
        if href and os.access(path, os.R_OK):
            return open(path, 'rb').read()

def extract_calibre_cover(raw, base, log):
    from calibre.ebooks.BeautifulSoup import BeautifulSoup
    soup = BeautifulSoup(raw)
    matches = soup.find(name=['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span',
        'font', 'br'])
    images = soup.findAll('img')
    if matches is None and len(images) == 1 and \
            images[0].get('alt', '')=='cover':
        img = images[0]
        img = os.path.join(base, *img['src'].split('/'))
        if os.path.exists(img):
            return open(img, 'rb').read()

    # Look for a simple cover, i.e. a body with no text and only one <img> tag
    if matches is None:
        body = soup.find('body')
        if body is not None:
            text = u''.join(map(unicode, body.findAll(text=True)))
            if text.strip():
                # Body has text, abort
                return
            images = body.findAll('img', src=True)
            if 0 < len(images) < 2:
                img = os.path.join(base, *images[0]['src'].split('/'))
                if os.path.exists(img):
                    return open(img, 'rb').read()

def render_html_svg_workaround(path_to_html, log, width=590, height=750):
    from calibre.ebooks.oeb.base import SVG_NS
    raw = open(path_to_html, 'rb').read()
    data = None
    if SVG_NS in raw:
        try:
            data = extract_cover_from_embedded_svg(raw,
                   os.path.dirname(path_to_html), log)
        except:
            pass
    if data is None:
        try:
            data = extract_calibre_cover(raw, os.path.dirname(path_to_html), log)
        except:
            pass

    if data is None:
        renderer = render_html(path_to_html, width, height)
        data = getattr(renderer, 'data', None)
    return data


def render_html(path_to_html, width=590, height=750, as_xhtml=True):
    from PyQt4.QtWebKit import QWebPage
    from PyQt4.Qt import QEventLoop, QPalette, Qt, QUrl, QSize
    from calibre.gui2 import is_ok_to_use_qt
    if not is_ok_to_use_qt(): return None
    path_to_html = os.path.abspath(path_to_html)
    with CurrentDir(os.path.dirname(path_to_html)):
        page = QWebPage()
        pal = page.palette()
        pal.setBrush(QPalette.Background, Qt.white)
        page.setPalette(pal)
        page.setViewportSize(QSize(width, height))
        page.mainFrame().setScrollBarPolicy(Qt.Vertical, Qt.ScrollBarAlwaysOff)
        page.mainFrame().setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)
        loop = QEventLoop()
        renderer = HTMLRenderer(page, loop)
        page.loadFinished.connect(renderer, type=Qt.QueuedConnection)
        if as_xhtml:
            page.mainFrame().setContent(open(path_to_html, 'rb').read(),
                    'application/xhtml+xml', QUrl.fromLocalFile(path_to_html))
        else:
            page.mainFrame().load(QUrl.fromLocalFile(path_to_html))
        loop.exec_()
    renderer.loop = renderer.page = None
    page.loadFinished.disconnect()
    del page
    del loop
    if isinstance(renderer.exception, ParserError) and as_xhtml:
        return render_html(path_to_html, width=width, height=height,
                as_xhtml=False)
    return renderer

def check_ebook_format(stream, current_guess):
    ans = current_guess
    if current_guess.lower() in ('prc', 'mobi', 'azw', 'azw1', 'azw3'):
        stream.seek(0)
        if stream.read(3) == 'TPZ':
            ans = 'tpz'
        stream.seek(0)
    return ans

def normalize(x):
    if isinstance(x, unicode):
        import unicodedata
        x = unicodedata.normalize('NFC', x)
    return x

def calibre_cover(title, author_string, series_string=None,
        output_format='jpg', title_size=46, author_size=36, logo_path=None):
    from calibre.utils.config_base import tweaks
    title = normalize(title)
    author_string = normalize(author_string)
    series_string = normalize(series_string)
    from calibre.utils.magick.draw import create_cover_page, TextLine
    text = title + author_string + (series_string or u'')
    font_path = tweaks['generate_cover_title_font']
    if font_path is None:
        font_path = P('fonts/liberation/LiberationSerif-Bold.ttf')

    from calibre.utils.fonts.utils import get_font_for_text
    font = open(font_path, 'rb').read()
    c = get_font_for_text(text, font)
    cleanup = False
    if c is not None and c != font:
        from calibre.ptempfile import PersistentTemporaryFile
        pt = PersistentTemporaryFile('.ttf')
        pt.write(c)
        pt.close()
        font_path = pt.name
        cleanup = True

    lines = [TextLine(title, title_size, font_path=font_path),
            TextLine(author_string, author_size, font_path=font_path)]
    if series_string:
        lines.append(TextLine(series_string, author_size, font_path=font_path))
    if logo_path is None:
        logo_path = I('library.png')
    try:
        return create_cover_page(lines, logo_path, output_format='jpg',
            texture_opacity=0.3, texture_data=I('cover_texture.png',
                data=True))
    finally:
        if cleanup:
            os.remove(font_path)

UNIT_RE = re.compile(r'^(-*[0-9]*[.]?[0-9]*)\s*(%|em|ex|en|px|mm|cm|in|pt|pc)$')

def unit_convert(value, base, font, dpi):
    ' Return value in pts'
    if isinstance(value, (int, long, float)):
        return value
    try:
        return float(value) * 72.0 / dpi
    except:
        pass
    result = value
    m = UNIT_RE.match(value)
    if m is not None and m.group(1):
        value = float(m.group(1))
        unit = m.group(2)
        if unit == '%':
            result = (value / 100.0) * base
        elif unit == 'px':
            result = value * 72.0 / dpi
        elif unit == 'in':
            result = value * 72.0
        elif unit == 'pt':
            result = value
        elif unit == 'em':
            result = value * font
        elif unit in ('ex', 'en'):
            # This is a hack for ex since we have no way to know
            # the x-height of the font
            font = font
            result = value * font * 0.5
        elif unit == 'pc':
            result = value * 12.0
        elif unit == 'mm':
            result = value * 2.8346456693
        elif unit == 'cm':
            result = value * 28.346456693
    return result

def generate_masthead(title, output_path=None, width=600, height=60):
    from calibre.ebooks.conversion.config import load_defaults
    from calibre.utils.config import tweaks
    fp = tweaks['generate_cover_title_font']
    if not fp:
        fp = P('fonts/liberation/LiberationSerif-Bold.ttf')
    font_path = default_font = fp
    recs = load_defaults('mobi_output')
    masthead_font_family = recs.get('masthead_font', 'Default')

    if masthead_font_family != 'Default':
        from calibre.utils.fonts.scanner import font_scanner, NoFonts
        try:
            faces = font_scanner.fonts_for_family(masthead_font_family)
        except NoFonts:
            faces = []
        if faces:
            font_path = faces[0]['path']

    if not font_path or not os.access(font_path, os.R_OK):
        font_path = default_font

    try:
        from PIL import Image, ImageDraw, ImageFont
        Image, ImageDraw, ImageFont
    except ImportError:
        import Image, ImageDraw, ImageFont

    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(font_path, 48, encoding='unic')
    except:
        font = ImageFont.truetype(default_font, 48, encoding='unic')
    text = force_unicode(title)
    width, height = draw.textsize(text, font=font)
    left = max(int((width - width)/2.), 0)
    top = max(int((height - height)/2.), 0)
    draw.text((left, top), text, fill=(0,0,0), font=font)
    if output_path is None:
        f = StringIO()
        img.save(f, 'JPEG')
        return f.getvalue()
    else:
        with open(output_path, 'wb') as f:
            img.save(f, 'JPEG')

