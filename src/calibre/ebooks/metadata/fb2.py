#!/usr/bin/env python2
# vim:fileencoding=utf-8
__license__   = 'GPL v3'
__copyright__ = '2011, Roman Mukhin <ramses_ru at hotmail.com>, '\
                '2008, Anatoly Shipitsin <norguhtar at gmail.com>'
'''Read meta information from fb2 files'''

import os, random
from functools import partial
from string import ascii_letters, digits
from base64 import b64encode

from lxml import etree

from calibre.utils.date import parse_only_date
from calibre.utils.img import save_cover_data_to
from calibre.utils.imghdr import identify
from calibre import guess_type, guess_all_extensions, prints, force_unicode
from calibre.ebooks.metadata import MetaInformation, check_isbn
from calibre.ebooks.chardet import xml_to_unicode


NAMESPACES = {
    'fb2'   :   'http://www.gribuser.ru/xml/fictionbook/2.0',
    'fb21'  :   'http://www.gribuser.ru/xml/fictionbook/2.1',
    'xlink' :   'http://www.w3.org/1999/xlink'
}

tostring = partial(etree.tostring, method='text', encoding=unicode)


def XLINK(tag):
    return '{%s}%s'%(NAMESPACES['xlink'], tag)


class Context(object):

    def __init__(self, root):
        try:
            self.fb_ns = root.nsmap[root.prefix] or NAMESPACES['fb2']
        except Exception:
            self.fb_ns = NAMESPACES['fb2']
        self.namespaces = {
            'fb': self.fb_ns,
            'fb2': self.fb_ns,
            'xlink': NAMESPACES['xlink']
        }

    def XPath(self, *args):
        return etree.XPath(*args, namespaces=self.namespaces)

    def get_or_create(self, parent, tag, attribs={}, at_start=True):
        xpathstr='./fb:'+tag
        for n, v in attribs.items():
            xpathstr += '[@%s="%s"]' % (n, v)
        ans = self.XPath(xpathstr)(parent)
        if ans:
            ans = ans[0]
        else:
            ans = self.create_tag(parent, tag, attribs, at_start)
        return ans

    def create_tag(self, parent, tag, attribs={}, at_start=True):
        ans = parent.makeelement('{%s}%s' % (self.fb_ns, tag))
        ans.attrib.update(attribs)
        if at_start:
            parent.insert(0, ans)
        else:
            parent.append(ans)
        return ans

    def clear_meta_tags(self, doc, tag):
        for parent in ('title-info', 'src-title-info', 'publish-info'):
            for x in self.XPath('//fb:%s/fb:%s'%(parent, tag))(doc):
                x.getparent().remove(x)

    def text2fb2(self, parent, text):
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line:
                p = self.create_tag(parent, 'p', at_start=False)
                p.text = line
            else:
                self.create_tag(parent, 'empty-line', at_start=False)


def get_fb2_data(stream):
    from calibre.utils.zipfile import ZipFile, BadZipfile
    pos = stream.tell()
    try:
        zf = ZipFile(stream)
    except BadZipfile:
        stream.seek(pos)
        ans = stream.read()
        zip_file_name = None
    else:
        names = zf.namelist()
        names = [x for x in names if x.lower().endswith('.fb2')] or names
        zip_file_name = names[0]
        ans = zf.open(zip_file_name).read()
    return ans, zip_file_name


def get_metadata(stream):
    ''' Return fb2 metadata as a L{MetaInformation} object '''

    root = _get_fbroot(get_fb2_data(stream)[0])
    ctx = Context(root)
    book_title = _parse_book_title(root, ctx)
    authors = _parse_authors(root, ctx) or [_('Unknown')]

    # fallback for book_title
    if book_title:
        book_title = unicode(book_title)
    else:
        book_title = force_unicode(os.path.splitext(
            os.path.basename(getattr(stream, 'name',
                _('Unknown'))))[0])
    mi = MetaInformation(book_title, authors)

    try:
        _parse_cover(root, mi, ctx)
    except:
        pass
    try:
        _parse_comments(root, mi, ctx)
    except:
        pass
    try:
        _parse_tags(root, mi, ctx)
    except:
        pass
    try:
        _parse_series(root, mi, ctx)
    except:
        pass
    try:
        _parse_isbn(root, mi, ctx)
    except:
        pass
    try:
        _parse_publisher(root, mi, ctx)
    except:
        pass
    try:
        _parse_pubdate(root, mi, ctx)
    except:
        pass

    try:
        _parse_language(root, mi, ctx)
    except:
        pass

    return mi


def _parse_authors(root, ctx):
    authors = []
    # pick up authors but only from 1 secrion <title-info>; otherwise it is not consistent!
    # Those are fallbacks: <src-title-info>, <document-info>
    author = None
    for author_sec in ['title-info', 'src-title-info', 'document-info']:
        for au in ctx.XPath('//fb:%s/fb:author'%author_sec)(root):
            author = _parse_author(au, ctx)
            if author:
                authors.append(author)
        if author:
            break

    # if no author so far
    if not authors:
        authors.append(_('Unknown'))

    return authors


def _parse_author(elm_author, ctx):
    """ Returns a list of display author and sortable author"""

    xp_templ = 'normalize-space(fb:%s/text())'

    author = ctx.XPath(xp_templ % 'first-name')(elm_author)
    lname = ctx.XPath(xp_templ % 'last-name')(elm_author)
    mname = ctx.XPath(xp_templ % 'middle-name')(elm_author)

    if mname:
        author = (author + ' ' + mname).strip()
    if lname:
        author = (author + ' ' + lname).strip()

    # fallback to nickname
    if not author:
        nname = ctx.XPath(xp_templ % 'nickname')(elm_author)
        if nname:
            author = nname

    return author


def _parse_book_title(root, ctx):
    # <title-info> has a priority.   (actually <title-info>  is mandatory)
    # other are backup solution (sequence is important. Other than in fb2-doc)
    xp_ti = '//fb:title-info/fb:book-title/text()'
    xp_pi = '//fb:publish-info/fb:book-title/text()'
    xp_si = '//fb:src-title-info/fb:book-title/text()'
    book_title = ctx.XPath('normalize-space(%s|%s|%s)' % (xp_ti, xp_pi, xp_si))(root)

    return book_title


def _parse_cover(root, mi, ctx):
    # pickup from <title-info>, if not exists it fallbacks to <src-title-info>
    imgid = ctx.XPath('substring-after(string(//fb:coverpage/fb:image/@xlink:href), "#")')(root)
    if imgid:
        try:
            _parse_cover_data(root, imgid, mi, ctx)
        except:
            pass


def _parse_cover_data(root, imgid, mi, ctx):
    from calibre.ebooks.fb2 import base64_decode
    elm_binary = ctx.XPath('//fb:binary[@id="%s"]'%imgid)(root)
    if elm_binary:
        mimetype = elm_binary[0].get('content-type', 'image/jpeg')
        mime_extensions = guess_all_extensions(mimetype)

        if not mime_extensions and mimetype.startswith('image/'):
            mimetype_fromid = guess_type(imgid)[0]
            if mimetype_fromid and mimetype_fromid.startswith('image/'):
                mime_extensions = guess_all_extensions(mimetype_fromid)

        if mime_extensions:
            pic_data = elm_binary[0].text
            if pic_data:
                cdata = base64_decode(pic_data.strip())
                fmt = identify(bytes(cdata))[0]
                mi.cover_data = (fmt, cdata)
        else:
            prints("WARNING: Unsupported coverpage mime-type '%s' (id=#%s)" % (mimetype, imgid))


def _parse_tags(root, mi, ctx):
    # pick up genre but only from 1 secrion <title-info>; otherwise it is not consistent!
    # Those are fallbacks: <src-title-info>
    for genre_sec in ['title-info', 'src-title-info']:
        # -- i18n Translations-- ?
        tags = ctx.XPath('//fb:%s/fb:genre/text()' % genre_sec)(root)
        if tags:
            mi.tags = list(map(unicode, tags))
            break


def _parse_series(root, mi, ctx):
    # calibri supports only 1 series: use the 1-st one
    # pick up sequence but only from 1 secrion in preferred order
    # except <src-title-info>
    xp_ti = '//fb:title-info/fb:sequence[1]'
    xp_pi = '//fb:publish-info/fb:sequence[1]'

    elms_sequence = ctx.XPath('%s|%s' % (xp_ti, xp_pi))(root)
    if elms_sequence:
        mi.series = elms_sequence[0].get('name', None)
        if mi.series:
            try:
                mi.series_index = float('.'.join(elms_sequence[0].get('number', None).split()[:2]))
            except Exception:
                pass


def _parse_isbn(root, mi, ctx):
    # some people try to put several isbn in this field, but it is not allowed.  try to stick to the 1-st one in this case
    isbn = ctx.XPath('normalize-space(//fb:publish-info/fb:isbn/text())')(root)
    if isbn:
        # some people try to put several isbn in this field, but it is not allowed.  try to stick to the 1-st one in this case
        if ',' in isbn:
            isbn = isbn[:isbn.index(',')]
        if check_isbn(isbn):
            mi.isbn = isbn


def _parse_comments(root, mi, ctx):
    # pick up annotation but only from 1 secrion <title-info>;  fallback: <src-title-info>
    for annotation_sec in ['title-info', 'src-title-info']:
        elms_annotation = ctx.XPath('//fb:%s/fb:annotation' % annotation_sec)(root)
        if elms_annotation:
            mi.comments = tostring(elms_annotation[0])
            # TODO: tags i18n, xslt?
            break


def _parse_publisher(root, mi, ctx):
    publisher = ctx.XPath('string(//fb:publish-info/fb:publisher/text())')(root)
    if publisher:
        mi.publisher = publisher


def _parse_pubdate(root, mi, ctx):
    year = ctx.XPath('number(//fb:publish-info/fb:year/text())')(root)
    if float.is_integer(year):
        # only year is available, so use 2nd of June
        mi.pubdate = parse_only_date(type(u'')(int(year)))


def _parse_language(root, mi, ctx):
    language = ctx.XPath('string(//fb:title-info/fb:lang/text())')(root)
    if language:
        mi.language = language
        mi.languages = [language]


def _get_fbroot(raw):
    parser = etree.XMLParser(recover=True, no_network=True)
    raw = xml_to_unicode(raw, strip_encoding_pats=True)[0]
    root = etree.fromstring(raw, parser=parser)
    return ensure_namespace(root)


def _set_title(title_info, mi, ctx):
    if not mi.is_null('title'):
        ctx.clear_meta_tags(title_info, 'book-title')
        title = ctx.get_or_create(title_info, 'book-title')
        title.text = mi.title


def _set_comments(title_info, mi, ctx):
    if not mi.is_null('comments'):
        from calibre.utils.html2text import html2text
        ctx.clear_meta_tags(title_info, 'annotation')
        title = ctx.get_or_create(title_info, 'annotation')
        ctx.text2fb2(title, html2text(mi.comments))


def _set_authors(title_info, mi, ctx):
    if not mi.is_null('authors'):
        ctx.clear_meta_tags(title_info, 'author')
        for author in reversed(mi.authors):
            author_parts = author.split()
            if not author_parts:
                continue
            atag = ctx.create_tag(title_info, 'author')
            if len(author_parts) == 1:
                ctx.create_tag(atag, 'nickname').text = author
            else:
                ctx.create_tag(atag, 'first-name').text = author_parts[0]
                author_parts = author_parts[1:]
                if len(author_parts) > 1:
                    ctx.create_tag(atag, 'middle-name', at_start=False).text = author_parts[0]
                    author_parts = author_parts[1:]
                if author_parts:
                    ctx.create_tag(atag, 'last-name', at_start=False).text = ' '.join(author_parts)


def _set_tags(title_info, mi, ctx):
    if not mi.is_null('tags'):
        ctx.clear_meta_tags(title_info, 'genre')
        for t in mi.tags:
            tag = ctx.create_tag(title_info, 'genre')
            tag.text = t


def _set_series(title_info, mi, ctx):
    if not mi.is_null('series'):
        ctx.clear_meta_tags(title_info, 'sequence')
        seq = ctx.get_or_create(title_info, 'sequence')
        seq.set('name', mi.series)
        try:
            seq.set('number', '%g'%mi.series_index)
        except:
            seq.set('number', '1')


def _rnd_name(size=8, chars=ascii_letters + digits):
    return ''.join(random.choice(chars) for x in range(size))


def _rnd_pic_file_name(prefix='calibre_cover_', size=32, ext='jpg'):
    return prefix + _rnd_name(size=size) + '.' + ext


def _encode_into_jpeg(data):
    data = save_cover_data_to(data)
    return b64encode(data)


def _set_cover(title_info, mi, ctx):
    if not mi.is_null('cover_data') and mi.cover_data[1]:
        coverpage = ctx.get_or_create(title_info, 'coverpage')
        cim_tag = ctx.get_or_create(coverpage, 'image')
        if XLINK('href') in cim_tag.attrib:
            cim_filename = cim_tag.attrib[XLINK('href')][1:]
        else:
            cim_filename = _rnd_pic_file_name('cover')
            cim_tag.attrib[XLINK('href')] = '#' + cim_filename
        fb2_root = cim_tag.getroottree().getroot()
        cim_binary = ctx.get_or_create(fb2_root, 'binary', attribs={'id': cim_filename}, at_start=False)
        cim_binary.attrib['content-type'] = 'image/jpeg'
        cim_binary.text = _encode_into_jpeg(mi.cover_data[1])


def set_metadata(stream, mi, apply_null=False, update_timestamp=False):
    stream.seek(0)
    raw, zip_file_name = get_fb2_data(stream)
    root = _get_fbroot(raw)
    ctx = Context(root)
    desc = ctx.get_or_create(root, 'description')
    ti = ctx.get_or_create(desc, 'title-info')

    indent = ti.text

    _set_comments(ti, mi, ctx)
    _set_series(ti, mi, ctx)
    _set_tags(ti, mi, ctx)
    _set_authors(ti, mi, ctx)
    _set_title(ti, mi, ctx)
    _set_cover(ti, mi, ctx)

    for child in ti:
        child.tail = indent

    # Apparently there exists FB2 reading software that chokes on the use of
    # single quotes in xml declaration. Sigh. See
    # https://www.mobileread.com/forums/showthread.php?p=2273184#post2273184
    raw = b'<?xml version="1.0" encoding="UTF-8"?>\n'
    raw += etree.tostring(root, method='xml', encoding='utf-8', xml_declaration=False)

    stream.seek(0)
    stream.truncate()
    if zip_file_name:
        from calibre.utils.zipfile import ZipFile
        with ZipFile(stream, 'w') as zf:
            zf.writestr(zip_file_name, raw)
    else:
        stream.write(raw)


def ensure_namespace(doc):
    # Workaround for broken FB2 files produced by convertonlinefree.com. See
    # https://bugs.launchpad.net/bugs/1404701
    bare_tags = False
    for x in ('description', 'body'):
        for x in doc.findall(x):
            if '{' not in x.tag:
                bare_tags = True
                break
    if bare_tags:
        import re
        raw = etree.tostring(doc, encoding=unicode)
        raw = re.sub(r'''<(description|body)\s+xmlns=['"]['"]>''', r'<\1>', raw)
        doc = etree.fromstring(raw)
    return doc
