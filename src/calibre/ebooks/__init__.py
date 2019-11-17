

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Code for the conversion of ebook formats and the reading of metadata
from various formats.
'''

import os, re, numbers, sys
from calibre import prints
from calibre.ebooks.chardet import xml_to_unicode
from polyglot.builtins import unicode_type


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
                   'epub', 'fb2', 'fbz', 'djv', 'djvu', 'lrx', 'cbr', 'cbz', 'cbc', 'oebzip',
                   'rb', 'imp', 'odt', 'chm', 'tpz', 'azw1', 'pml', 'pmlz', 'mbp', 'tan', 'snb',
                   'xps', 'oxps', 'azw4', 'book', 'zbf', 'pobi', 'docx', 'docm', 'md',
                   'textile', 'markdown', 'ibook', 'ibooks', 'iba', 'azw3', 'ps', 'kepub', 'kfx', 'kpf']


def return_raster_image(path):
    from calibre.utils.imghdr import what
    if os.access(path, os.R_OK):
        with open(path, 'rb') as f:
            raw = f.read()
        if what(None, raw) not in (None, 'svg'):
            return raw


def extract_cover_from_embedded_svg(html, base, log):
    from calibre.ebooks.oeb.base import XPath, SVG, XLINK
    from calibre.utils.xml_parse import safe_xml_fromstring
    root = safe_xml_fromstring(html)

    svg = XPath('//svg:svg')(root)
    if len(svg) == 1 and len(svg[0]) == 1 and svg[0][0].tag == SVG('image'):
        image = svg[0][0]
        href = image.get(XLINK('href'), None)
        if href:
            path = os.path.join(base, *href.split('/'))
            return return_raster_image(path)


def extract_calibre_cover(raw, base, log):
    from calibre.ebooks.BeautifulSoup import BeautifulSoup
    soup = BeautifulSoup(raw)
    matches = soup.find(name=['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span',
        'font', 'br'])
    images = soup.findAll('img', src=True)
    if matches is None and len(images) == 1 and \
            images[0].get('alt', '').lower()=='cover':
        img = images[0]
        img = os.path.join(base, *img['src'].split('/'))
        q = return_raster_image(img)
        if q is not None:
            return q

    # Look for a simple cover, i.e. a body with no text and only one <img> tag
    if matches is None:
        body = soup.find('body')
        if body is not None:
            text = u''.join(map(unicode_type, body.findAll(text=True)))
            if text.strip():
                # Body has text, abort
                return
            images = body.findAll('img', src=True)
            if len(images) == 1:
                img = os.path.join(base, *images[0]['src'].split('/'))
                return return_raster_image(img)


def render_html_svg_workaround(path_to_html, log, width=590, height=750):
    from calibre.ebooks.oeb.base import SVG_NS
    with open(path_to_html, 'rb') as f:
        raw = f.read()
    raw = xml_to_unicode(raw, strip_encoding_pats=True)[0]
    data = None
    if SVG_NS in raw:
        try:
            data = extract_cover_from_embedded_svg(raw,
                   os.path.dirname(path_to_html), log)
        except Exception:
            pass
    if data is None:
        try:
            data = extract_calibre_cover(raw, os.path.dirname(path_to_html), log)
        except Exception:
            pass

    if data is None:
        data = render_html_data(path_to_html, width, height)
    return data


def render_html_data(path_to_html, width, height):
    from calibre.ptempfile import TemporaryDirectory
    from calibre.utils.ipc.simple_worker import fork_job, WorkerError
    result = {}

    def report_error(text=''):
        prints('Failed to render', path_to_html, 'with errors:', file=sys.stderr)
        if text:
            prints(text, file=sys.stderr)
        if result and result['stdout_stderr']:
            with open(result['stdout_stderr'], 'rb') as f:
                prints(f.read(), file=sys.stderr)

    with TemporaryDirectory('-render-html') as tdir:
        try:
            result = fork_job('calibre.ebooks.render_html', 'main', args=(path_to_html, tdir, 'jpeg'))
        except WorkerError as e:
            report_error(e.orig_tb)
        else:
            if result['result']:
                with open(os.path.join(tdir, 'rendered.jpeg'), 'rb') as f:
                    return f.read()
            else:
                report_error()


def check_ebook_format(stream, current_guess):
    ans = current_guess
    if current_guess.lower() in ('prc', 'mobi', 'azw', 'azw1', 'azw3'):
        stream.seek(0)
        if stream.read(3) == b'TPZ':
            ans = 'tpz'
        stream.seek(0)
    return ans


def normalize(x):
    if isinstance(x, unicode_type):
        import unicodedata
        x = unicodedata.normalize('NFC', x)
    return x


def calibre_cover(title, author_string, series_string=None,
        output_format='jpg', title_size=46, author_size=36, logo_path=None):
    title = normalize(title)
    author_string = normalize(author_string)
    series_string = normalize(series_string)
    from calibre.ebooks.covers import calibre_cover2
    from calibre.utils.img import image_to_data
    ans = calibre_cover2(title, author_string or '', series_string or '', logo_path=logo_path, as_qimage=True)
    return image_to_data(ans, fmt=output_format)


UNIT_RE = re.compile(r'^(-*[0-9]*[.]?[0-9]*)\s*(%|em|ex|en|px|mm|cm|in|pt|pc|rem|q)$')


def unit_convert(value, base, font, dpi, body_font_size=12):
    ' Return value in pts'
    if isinstance(value, numbers.Number):
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
        elif unit == 'rem':
            result = value * body_font_size
        elif unit == 'q':
            result = value * 0.708661417325
    return result


def parse_css_length(value):
    try:
        m = UNIT_RE.match(value)
    except TypeError:
        return None, None
    if m is not None and m.group(1):
        value = float(m.group(1))
        unit = m.group(2)
        return value, unit.lower()
    return None, None


def generate_masthead(title, output_path=None, width=600, height=60):
    from calibre.ebooks.conversion.config import load_defaults
    recs = load_defaults('mobi_output')
    masthead_font_family = recs.get('masthead_font', None)
    from calibre.ebooks.covers import generate_masthead
    return generate_masthead(title, output_path=output_path, width=width, height=height, font_family=masthead_font_family)


def escape_xpath_attr(value):
    if '"' in value:
        if "'" in value:
            parts = re.split('("+)', value)
            ans = []
            for x in parts:
                if x:
                    q = "'" if '"' in x else '"'
                    ans.append(q + x + q)
            return 'concat(%s)' % ', '.join(ans)
        else:
            return "'%s'" % value
    return '"%s"' % value
