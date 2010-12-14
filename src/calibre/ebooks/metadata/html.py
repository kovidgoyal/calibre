#!/usr/bin/env  python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Try to read metadata from an HTML file.
'''

import re

from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.chardet import xml_to_unicode
from calibre import entity_to_unicode
from calibre.utils.date import parse_date

def get_metadata(stream):
    src = stream.read()
    return get_metadata_(src)

def get_meta_regexp_(name):
    return re.compile('<meta name=[\'"]' + name + '[\'"] content=[\'"](.+?)[\'"]\s*/?>', re.IGNORECASE)

def get_metadata_(src, encoding=None):
    if not isinstance(src, unicode):
        if not encoding:
            src = xml_to_unicode(src)[0]
        else:
            src = src.decode(encoding, 'replace')

    # Meta data definitions as in
    # http://www.mobileread.com/forums/showpost.php?p=712544&postcount=9

    # Title
    title = None
    pat = re.compile(r'<!--.*?TITLE=(?P<q>[\'"])(.+?)(?P=q).*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        title = match.group(2)
    else:
        pat = re.compile('<title>([^<>]+?)</title>', re.IGNORECASE)
        match = pat.search(src)
        if match:
            title = match.group(1)
    if not title:
        for x in ('Title','DC.title','DCTERMS.title'):
            pat = get_meta_regexp_(x)
            match = pat.search(src)
            if match:
                title = match.group(1)
                break

    # Author
    author = None
    pat = re.compile(r'<!--.*?AUTHOR=(?P<q>[\'"])(.+?)(?P=q).*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        author = match.group(2).replace(',', ';')
    else:
        for x in ('Author','DC.creator.aut','DCTERMS.creator.aut'):
            pat = get_meta_regexp_(x)
            match = pat.search(src)
            if match:
                author = match.group(1)
                break

    # Create MetaInformation with Title and Author
    ent_pat = re.compile(r'&(\S+)?;')
    if title:
        title = ent_pat.sub(entity_to_unicode, title)
    if author:
        author = ent_pat.sub(entity_to_unicode, author)
    mi = MetaInformation(title, [author] if author else None)

    # Publisher
    publisher = None
    pat = re.compile(r'<!--.*?PUBLISHER=(?P<q>[\'"])(.+?)(?P=q).*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        publisher = match.group(2)
    else:
        for x in ('Publisher','DC.publisher','DCTERMS.publisher'):
            pat = get_meta_regexp_(x)
            match = pat.search(src)
            if match:
                publisher = match.group(1)
                break
    if publisher:
        mi.publisher = ent_pat.sub(entity_to_unicode, publisher)

    # ISBN
    isbn = None
    pat = re.compile(r'<!--.*?ISBN=[\'"]([^"\']+)[\'"].*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        isbn = match.group(1)
    else:
        for x in ('ISBN','DC.identifier.ISBN','DCTERMS.identifier.ISBN'):
            pat = get_meta_regexp_(x)
            match = pat.search(src)
            if match:
                isbn = match.group(1)
                break
    if isbn:
        mi.isbn = re.sub(r'[^0-9xX]', '', isbn)

    # LANGUAGE
    language = None
    pat = re.compile(r'<!--.*?LANGUAGE=[\'"]([^"\']+)[\'"].*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        language = match.group(1)
    else:
        for x in ('DC.language','DCTERMS.language'):
            pat = get_meta_regexp_(x)
            match = pat.search(src)
            if match:
                language = match.group(1)
                break
    if language:
        mi.language = language

    # PUBDATE
    pubdate = None
    pat = re.compile(r'<!--.*?PUBDATE=[\'"]([^"\']+)[\'"].*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        pubdate = match.group(1)
    else:
        for x in ('Pubdate','Date of publication','DC.date.published','DC.date.publication','DC.date.issued','DCTERMS.issued'):
            pat = get_meta_regexp_(x)
            match = pat.search(src)
            if match:
                pubdate = match.group(1)
                break
    if pubdate:
        try:
            mi.pubdate = parse_date(pubdate)
        except:
            pass

    # TIMESTAMP
    timestamp = None
    pat = re.compile(r'<!--.*?TIMESTAMP=[\'"]([^"\']+)[\'"].*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        timestamp = match.group(1)
    else:
        for x in ('Timestamp','Date of creation','DC.date.created','DC.date.creation','DCTERMS.created'):
            pat = get_meta_regexp_(x)
            match = pat.search(src)
            if match:
                timestamp = match.group(1)
                break
    if timestamp:
        try:
            mi.timestamp = parse_date(timestamp)
        except:
            pass

    # SERIES
    series = None
    pat = re.compile(r'<!--.*?SERIES=[\'"]([^"\']+)[\'"].*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        series = match.group(1)
    else:
        pat = get_meta_regexp_("Series")
        match = pat.search(src)
        if match:
            series = match.group(1)
    if series:
        pat = re.compile(r'\[([.0-9]+)\]')
        match = pat.search(series)
        series_index = None
        if match is not None:
            try:
                series_index = float(match.group(1))
            except:
                pass
            series = series.replace(match.group(), '').strip()

        mi.series = ent_pat.sub(entity_to_unicode, series)
        if series_index is None:
            pat = get_meta_regexp_("Seriesnumber")
            match = pat.search(src)
            if match:
                try:
                    series_index = float(match.group(1))
                except:
                    pass
        if series_index is not None:
            mi.series_index = series_index

    # RATING
    rating = None
    pat = re.compile(r'<!--.*?RATING=[\'"]([^"\']+)[\'"].*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        rating = match.group(1)
    else:
        pat = get_meta_regexp_("Rating")
        match = pat.search(src)
        if match:
            rating = match.group(1)
    if rating:
        try:
            mi.rating = float(rating)
            if mi.rating < 0:
                mi.rating = 0
            if mi.rating > 5:
                mi.rating /= 2.
            if mi.rating > 5:
                mi.rating = 0
        except:
            pass

    # COMMENTS
    comments = None
    pat = re.compile(r'<!--.*?COMMENTS=[\'"]([^"\']+)[\'"].*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        comments = match.group(1)
    else:
        pat = get_meta_regexp_("Comments")
        match = pat.search(src)
        if match:
            comments = match.group(1)
    if comments:
        mi.comments = ent_pat.sub(entity_to_unicode, comments)

    # TAGS
    tags = None
    pat = re.compile(r'<!--.*?TAGS=[\'"]([^"\']+)[\'"].*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        tags = match.group(1)
    else:
        pat = get_meta_regexp_("Tags")
        match = pat.search(src)
        if match:
            tags = match.group(1)
    if tags:
        mi.tags = [x.strip() for x in ent_pat.sub(entity_to_unicode,
            tags).split(",")]

    # Ready to return MetaInformation
    return mi


