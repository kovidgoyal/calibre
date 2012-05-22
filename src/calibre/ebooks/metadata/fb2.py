#!/usr/bin/env python
from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2011, Roman Mukhin <ramses_ru at hotmail.com>, '\
                '2008, Anatoly Shipitsin <norguhtar at gmail.com>'
'''Read meta information from fb2 files'''

import os
import datetime
from functools import partial
from lxml import etree
from calibre.utils.date import parse_date
from calibre import guess_type, guess_all_extensions, prints, force_unicode
from calibre.ebooks.metadata import MetaInformation, check_isbn
from calibre.ebooks.chardet import xml_to_unicode
from string import ascii_letters, digits


NAMESPACES = {
    'fb2'   :   'http://www.gribuser.ru/xml/fictionbook/2.0',
    'xlink' :   'http://www.w3.org/1999/xlink'  }

XPath = partial(etree.XPath, namespaces=NAMESPACES)
tostring = partial(etree.tostring, method='text', encoding=unicode)

def FB2(tag):
    return '{%s}%s'%(NAMESPACES['fb2'], tag)

def XLINK(tag):
    return '{%s}%s'%(NAMESPACES['xlink'], tag)

def get_metadata(stream):
    ''' Return fb2 metadata as a L{MetaInformation} object '''

    root = _get_fbroot(stream)
    book_title = _parse_book_title(root)
    authors = _parse_authors(root)

    # fallback for book_title
    if book_title:
        book_title = unicode(book_title)
    else:
        book_title = force_unicode(os.path.splitext(
            os.path.basename(getattr(stream, 'name',
                _('Unknown'))))[0])
    mi = MetaInformation(book_title, authors)

    try:
        _parse_cover(root, mi)
    except:
        pass
    try:
        _parse_comments(root, mi)
    except:
        pass
    try:
        _parse_tags(root, mi)
    except:
        pass
    try:
        _parse_series(root, mi)
    except:
        pass
    try:
        _parse_isbn(root, mi)
    except:
        pass
    try:
        _parse_publisher(root, mi)
    except:
        pass
    try:
        _parse_pubdate(root, mi)
    except:
        pass
    #try:
    #    _parse_timestamp(root, mi)
    #except:
    #    pass

    try:
        _parse_language(root, mi)
    except:
        pass
    #_parse_uuid(root, mi)

    #if DEBUG:
    #   prints(mi)
    return mi

def _parse_authors(root):
    authors = []
    # pick up authors but only from 1 secrion <title-info>; otherwise it is not consistent!
    # Those are fallbacks: <src-title-info>, <document-info>
    author = None
    for author_sec in ['title-info', 'src-title-info', 'document-info']:
        for au in XPath('//fb2:%s/fb2:author'%author_sec)(root):
            author = _parse_author(au)
            if author:
                authors.append(author)
        if author:
            break

    # if no author so far
    if not authors:
        authors.append(_('Unknown'))

    return authors

def _parse_author(elm_author):
    """ Returns a list of display author and sortable author"""

    xp_templ = 'normalize-space(fb2:%s/text())'

    author = XPath(xp_templ % 'first-name')(elm_author)
    lname = XPath(xp_templ % 'last-name')(elm_author)
    mname = XPath(xp_templ % 'middle-name')(elm_author)

    if mname:
        author = (author + ' ' + mname).strip()
    if lname:
        author = (author + ' ' + lname).strip()

    # fallback to nickname
    if not author:
        nname = XPath(xp_templ % 'nickname')(elm_author)
        if nname:
            author = nname

    return author


def _parse_book_title(root):
    # <title-info> has a priority.   (actually <title-info>  is mandatory)
    # other are backup solution (sequence is important. other then in fb2-doc)
    xp_ti = '//fb2:title-info/fb2:book-title/text()'
    xp_pi = '//fb2:publish-info/fb2:book-title/text()'
    xp_si = '//fb2:src-title-info/fb2:book-title/text()'
    book_title = XPath('normalize-space(%s|%s|%s)' % (xp_ti, xp_pi, xp_si))(root)

    return book_title

def _parse_cover(root, mi):
    # pickup from <title-info>, if not exists it fallbacks to <src-title-info>
    imgid = XPath('substring-after(string(//fb2:coverpage/fb2:image/@xlink:href), "#")')(root)
    if imgid:
        try:
            _parse_cover_data(root, imgid, mi)
        except:
            pass

def _parse_cover_data(root, imgid, mi):
    from calibre.ebooks.fb2 import base64_decode
    elm_binary = XPath('//fb2:binary[@id="%s"]'%imgid)(root)
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
                mi.cover_data = (mime_extensions[0][1:],
                        base64_decode(pic_data.strip()))
        else:
            prints("WARNING: Unsupported coverpage mime-type '%s' (id=#%s)" % (mimetype, imgid) )

def _parse_tags(root, mi):
    # pick up genre but only from 1 secrion <title-info>; otherwise it is not consistent!
    # Those are fallbacks: <src-title-info>
    for genre_sec in ['title-info', 'src-title-info']:
        # -- i18n Translations-- ?
        tags = XPath('//fb2:%s/fb2:genre/text()' % genre_sec)(root)
        if tags:
            mi.tags = list(map(unicode, tags))
            break

def _parse_series(root, mi):
    # calibri supports only 1 series: use the 1-st one
    # pick up sequence but only from 1 secrion in prefered order
    # except <src-title-info>
    xp_ti = '//fb2:title-info/fb2:sequence[1]'
    xp_pi = '//fb2:publish-info/fb2:sequence[1]'

    elms_sequence = XPath('%s|%s' % (xp_ti, xp_pi))(root)
    if elms_sequence:
        mi.series = elms_sequence[0].get('name', None)
        if mi.series:
            mi.series_index = elms_sequence[0].get('number', None)

def _parse_isbn(root, mi):
    # some people try to put several isbn in this field, but it is not allowed.  try to stick to the 1-st one in this case
    isbn = XPath('normalize-space(//fb2:publish-info/fb2:isbn/text())')(root)
    if isbn:
        # some people try to put several isbn in this field, but it is not allowed.  try to stick to the 1-st one in this case
        if ',' in isbn:
            isbn = isbn[:isbn.index(',')]
        if check_isbn(isbn):
            mi.isbn = isbn

def _parse_comments(root, mi):
    # pick up annotation but only from 1 secrion <title-info>;  fallback: <src-title-info>
    for annotation_sec in ['title-info', 'src-title-info']:
        elms_annotation = XPath('//fb2:%s/fb2:annotation' % annotation_sec)(root)
        if elms_annotation:
            mi.comments = tostring(elms_annotation[0])
            # TODO: tags i18n, xslt?
            break

def _parse_publisher(root, mi):
    publisher = XPath('string(//fb2:publish-info/fb2:publisher/text())')(root)
    if publisher:
        mi.publisher = publisher

def _parse_pubdate(root, mi):
    year = XPath('number(//fb2:publish-info/fb2:year/text())')(root)
    if float.is_integer(year):
        # only year is available, so use 2nd of June
        mi.pubdate = datetime.date(int(year), 6, 2)

def _parse_timestamp(root, mi):
    #<date value="1996-12-03">03.12.1996</date>
    xp ='//fb2:document-info/fb2:date/@value|'\
        '//fb2:document-info/fb2:date/text()'
    docdate = XPath('string(%s)' % xp)(root)
    if docdate:
        mi.timestamp = parse_date(docdate)

def _parse_language(root, mi):
    language = XPath('string(//fb2:title-info/fb2:lang/text())')(root)
    if language:
        mi.language = language
        mi.languages = [ language ]

def _parse_uuid(root, mi):
    uuid = XPath('normalize-space(//document-info/fb2:id/text())')(root)
    if uuid:
        mi.uuid = uuid

def _get_fbroot(stream):
    parser = etree.XMLParser(recover=True, no_network=True)
    raw = stream.read()
    raw = xml_to_unicode(raw, strip_encoding_pats=True)[0]
    root = etree.fromstring(raw, parser=parser)
    return root

def _clear_meta_tags(doc, tag):
    for parent in ('title-info', 'src-title-info', 'publish-info'):
        for x in XPath('//fb2:%s/fb2:%s'%(parent, tag))(doc):
            x.getparent().remove(x)

def _set_title(title_info, mi):
    if not mi.is_null('title'):
        _clear_meta_tags(title_info, 'book-title')
        title = _get_or_create(title_info, 'book-title')
        title.text = mi.title

def _text2fb2(parent, text):
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if line:
            p = _create_tag(parent, 'p', at_start=False)
            p.text = line
        else:
            _create_tag(parent, 'empty-line', at_start=False)

def _set_comments(title_info, mi):
    if not mi.is_null('comments'):
        from calibre.utils.html2text import html2text
        _clear_meta_tags(title_info, 'annotation')
        title = _get_or_create(title_info, 'annotation')
        _text2fb2(title, html2text(mi.comments))


def _set_authors(title_info, mi):
    if not mi.is_null('authors'):
        _clear_meta_tags(title_info, 'author')
        for author in mi.authors:
            author_parts = author.split()
            if not author_parts: continue
            atag = _create_tag(title_info, 'author')
            if len(author_parts) == 1:
                _create_tag(atag, 'nickname').text = author
            else:
                _create_tag(atag, 'first-name').text = author_parts[0]
                author_parts = author_parts[1:]
                if len(author_parts) > 1:
                    _create_tag(atag, 'middle-name', at_start=False).text = author_parts[0]
                    author_parts = author_parts[1:]
                if author_parts:
                    _create_tag(atag, 'last-name', at_start=False).text = ' '.join(author_parts)

def _set_tags(title_info, mi):
    if not mi.is_null('tags'):
        _clear_meta_tags(title_info, 'genre')
        for t in mi.tags:
            tag = _create_tag(title_info, 'genre')
            tag.text = t

def _set_series(title_info, mi):
    if not mi.is_null('series'):
        _clear_meta_tags(title_info, 'sequence')
        seq = _get_or_create(title_info, 'sequence')
        seq.set('name', mi.series)
        try:
            seq.set('number', '%g'%mi.series_index)
        except:
            seq.set('number', '1')

def _rnd_name(size=8, chars=ascii_letters + digits):
    import random
    return ''.join(random.choice(chars) for x in range(size))

def _rnd_pic_file_name(prefix='', size=8, ext='jpg'):
    return prefix + _rnd_name(size) + '.' + ext

def _encode_into_jpeg(data):
    from base64 import b64encode
    if data[0] == 'jpg':
        pic = b64encode(data[1])
    else:
        im = Image()
        im.load(data[1])
        im.set_compression_quality(70)
        imdata = im.export('jpg')
        pic = b64encode(imdata)
    return pic

def _set_cover(title_info, mi):
    if not mi.is_null('cover_data'):
        coverpage = _get_or_create(title_info, 'coverpage')
        cim_tag = _get_or_create(coverpage, 'image')
        cim_filename = _rnd_pic_file_name('cover')
        if cim_tag.attrib.has_key(XLINK('href')):
            cim_filename = cim_tag.attrib[XLINK('href')][1:]
        else:
            cim_tag.attrib[XLINK('href')] = '#' + cim_filename
        fb2_root = cim_tag.getroottree().getroot()
        cim_binary = _get_or_create(fb2_root, 'binary', attribs={'id': cim_filename}, at_start=False)
        cim_binary.attrib['content-type'] = 'image/jpeg'
        cim_binary.text = _encode_into_jpeg(mi.cover_data)

def _create_tag(parent, tag, attribs={}, at_start=True):
    ans = parent.makeelement(FB2(tag))
    ans.attrib.update(attribs)
    if at_start:
        parent.insert(0, ans)
    else:
        parent.append(ans)
    return ans

def _get_or_create(parent, tag, attribs={}, at_start=True):
    xpathstr='./fb2:'+tag
    for n, v in attribs.items():
        xpathstr += '[@%s="%s"]' % (n, v)
    ans = XPath(xpathstr)(parent)
    if ans:
        ans = ans[0]
    else:
        ans = _create_tag(parent, tag, attribs, at_start)
    return ans

def set_metadata(stream, mi, apply_null=False, update_timestamp=False):
    stream.seek(0)
    root = _get_fbroot(stream)
    desc = _get_or_create(root, 'description')
    ti = _get_or_create(desc, 'title-info')

    indent = ti.text

    _set_comments(ti, mi)
    _set_series(ti, mi)
    _set_tags(ti, mi)
    _set_authors(ti, mi)
    _set_title(ti, mi)
    _set_cover(ti, mi)

    for child in ti:
        child.tail = indent

    stream.seek(0)
    stream.truncate()
    stream.write(etree.tostring(root, method='xml', encoding='utf-8',
        xml_declaration=True))

