# -*- coding: utf-8 -*-
from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, Roman Mukhin <ramses_ru at hotmail.com>'
__docformat__ = 'restructuredtext en'

import re
from urllib import quote_plus
from Queue import Queue, Empty

from calibre import as_unicode
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import Source
from calibre.ebooks.metadata.book.base import Metadata
from calibre.utils.date import parse_only_date

class Ozon(Source):
    name = 'OZON.ru'
    description = _('Downloads metadata and covers from OZON.ru')

    capabilities = frozenset(['identify', 'cover'])

    touched_fields = frozenset(['title', 'authors', 'identifier:isbn', 'identifier:ozon',
                               'publisher', 'pubdate', 'comments', 'series', 'rating', 'language'])
    # Test purpose only, test function does not like when sometimes some filed are empty
    # touched_fields = frozenset(['title', 'authors', 'identifier:isbn', 'identifier:ozon',
    #                          'publisher', 'pubdate', 'comments'])

    supports_gzip_transfer_encoding = True
    has_html_comments = True

    ozon_url = 'http://www.ozon.ru'

    # match any ISBN10/13. From "Regular Expressions Cookbook"
    isbnPattern = r'(?:ISBN(?:-1[03])?:? )?(?=[-0-9 ]{17}|'\
             '[-0-9X ]{13}|[0-9X]{10})(?:97[89][- ]?)?[0-9]{1,5}[- ]?'\
             '(?:[0-9]+[- ]?){2}[0-9X]'
    isbnRegex = re.compile(isbnPattern)

    def get_book_url(self, identifiers): # {{{
        import urllib2
        ozon_id = identifiers.get('ozon', None)
        res = None
        if ozon_id:
            url = '{}/context/detail/id/{}?partner={}'.format(self.ozon_url, urllib2.quote(ozon_id), _get_affiliateId())
            res = ('ozon', ozon_id, url)
        return res
    # }}}

    def create_query(self, log, title=None, authors=None, identifiers={}): # {{{
        # div_book -> search only books, ebooks and audio books
        search_url = self.ozon_url + '/webservice/webservice.asmx/SearchWebService?searchContext=div_book&searchText='

        # for ozon.ru search we have to format ISBN with '-'
        isbn = _format_isbn(log, identifiers.get('isbn', None))
        # TODO: format isbn!
        qItems = set([isbn, title])
        if authors:
            qItems |= frozenset(authors)
        qItems.discard(None)
        qItems.discard('')
        qItems = map(_quoteString, qItems)

        q = u' '.join(qItems).strip()
        log.info(u'search string: ' + q)

        if isinstance(q, unicode):
            q = q.encode('utf-8')
        if not q:
            return None

        search_url += quote_plus(q)
        log.debug(u'search url: %r'%search_url)

        return search_url
    # }}}

    def identify(self, log, result_queue, abort, title=None, authors=None,
            identifiers={}, timeout=30): # {{{
        from lxml import etree
        from calibre.ebooks.chardet import xml_to_unicode

        if not self.is_configured():
            return
        query = self.create_query(log, title=title, authors=authors, identifiers=identifiers)
        if not query:
            err = u'Insufficient metadata to construct query'
            log.error(err)
            return err

        try:
            raw = self.browser.open_novisit(query).read()

        except Exception as e:
            log.exception(u'Failed to make identify query: %r'%query)
            return as_unicode(e)

        try:
            parser = etree.XMLParser(recover=True, no_network=True)
            feed = etree.fromstring(xml_to_unicode(raw, strip_encoding_pats=True, assume_utf8=True)[0], parser=parser)
            entries = feed.xpath('//*[local-name() = "SearchItems"]')
            if entries:
                metadata = self.get_metadata(log, entries, title, authors, identifiers)
                self.get_all_details(log, metadata, abort, result_queue, identifiers, timeout)
        except Exception as e:
            log.exception('Failed to parse identify results')
            return as_unicode(e)

    # }}}

    def get_metadata(self, log, entries, title, authors, identifiers): # {{{
        # some book titles have extra characters like this
        # TODO: make a twick
        reRemoveFromTitle = None
        #reRemoveFromTitle = re.compile(r'[?!:.,;+-/&%"\'=]')

        title = unicode(title).upper() if title else ''
        if reRemoveFromTitle:
            title = reRemoveFromTitle.sub('', title)
        authors = map(_normalizeAuthorNameWithInitials,
                      map(unicode.upper, map(unicode, authors))) if authors else None
        ozon_id = identifiers.get('ozon', None)

        unk = unicode(_('Unknown')).upper()

        if title == unk:
            title = None

        if authors == [unk]:
            authors = None

        def in_authors(authors, miauthors):
            for author in authors:
                for miauthor in miauthors:
                    #log.debug(u'=> %s <> %s'%(author, miauthor))
                    if author in miauthor: return True
            return None

        def ensure_metadata_match(mi): # {{{
            match = True
            if title:
                mititle = unicode(mi.title).upper() if mi.title else ''
                if reRemoveFromTitle:
                    mititle = reRemoveFromTitle.sub('', mititle)
                match = title in mititle
                #log.debug(u't=> %s <> %s'%(title, mititle))
            if match and authors:
                miauthors = map(unicode.upper, map(unicode, mi.authors)) if mi.authors else []
                match = in_authors(authors, miauthors)

            if match and ozon_id:
                mozon_id = mi.identifiers['ozon']
                match = ozon_id == mozon_id

            return match

        metadata = []
        for i, entry in enumerate(entries):
            mi = self.to_metadata(log, entry)
            mi.source_relevance = i
            if ensure_metadata_match(mi):
                metadata.append(mi)
                #log.debug(u'added metadata %s %s.'%(mi.title,  mi.authors))
            else:
                log.debug(u'skipped metadata %s %s. (does not match the query)'%(mi.title, mi.authors))
        return metadata
    # }}}

    def get_all_details(self, log, metadata, abort, result_queue, identifiers, timeout): # {{{
        req_isbn = identifiers.get('isbn', None)

        for mi in metadata:
            if abort.is_set():
                break
            try:
                ozon_id = mi.identifiers['ozon']

                try:
                    self.get_book_details(log, mi, timeout)
                except:
                    log.exception(u'Failed to get details for metadata: %s'%mi.title)

                all_isbns = getattr(mi, 'all_isbns', [])
                if req_isbn and all_isbns and check_isbn(req_isbn) not in all_isbns:
                    log.debug(u'skipped, no requested ISBN %s found'%req_isbn)
                    continue

                for isbn in all_isbns:
                    self.cache_isbn_to_identifier(isbn, ozon_id)

                if mi.ozon_cover_url:
                    self.cache_identifier_to_cover_url(ozon_id, mi.ozon_cover_url)

                self.clean_downloaded_metadata(mi)
                result_queue.put(mi)
            except:
                log.exception(u'Failed to get details for metadata: %s'%mi.title)
    # }}}

    def to_metadata(self, log, entry): # {{{
        xp_template = 'normalize-space(./*[local-name() = "{0}"]/text())'

        title = entry.xpath(xp_template.format('Name'))
        author = entry.xpath(xp_template.format('Author'))
        norm_authors = map(_normalizeAuthorNameWithInitials, map(unicode.strip, unicode(author).split(u',')))
        mi = Metadata(title, norm_authors)

        ozon_id = entry.xpath(xp_template.format('ID'))
        mi.identifiers = {'ozon':ozon_id}

        mi.comments = entry.xpath(xp_template.format('Annotation'))

        mi.ozon_cover_url = None
        cover = entry.xpath(xp_template.format('Picture'))
        if cover:
            mi.ozon_cover_url = _translateToBigCoverUrl(cover)

        pub_year = entry.xpath(xp_template.format('Year'))
        if pub_year:
            mi.pubdate = toPubdate(log, pub_year)
            #log.debug('pubdate %s'%mi.pubdate)

        rating = entry.xpath(xp_template.format('ClientRatingValue'))
        if rating:
            try:
                #'rating',     A floating point number between 0 and 10
                # OZON raion N of 5, calibre of 10, but there is a bug? in identify
                mi.rating = float(rating)
            except:
                pass
            rating
        return mi
    # }}}

    def get_cached_cover_url(self, identifiers): # {{{
        url = None
        ozon_id = identifiers.get('ozon', None)
        if ozon_id is None:
            isbn = identifiers.get('isbn', None)
            if isbn is not None:
                ozon_id = self.cached_isbn_to_identifier(isbn)
        if ozon_id is not None:
            url = self.cached_identifier_to_cover_url(ozon_id)
        return url
    # }}}

    def download_cover(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30): # {{{
        cached_url = self.get_cached_cover_url(identifiers)
        if cached_url is None:
            log.debug('No cached cover found, running identify')
            rq = Queue()
            self.identify(log, rq, abort, title=title, authors=authors, identifiers=identifiers)
            if abort.is_set():
                return
            results = []
            while True:
                try:
                    results.append(rq.get_nowait())
                except Empty:
                    break
            results.sort(key=self.identify_results_keygen(title=title, authors=authors, identifiers=identifiers))
            for mi in results:
                cached_url = self.get_cached_cover_url(mi.identifiers)
                if cached_url is not None:
                    break

        if cached_url is None:
            log.info('No cover found')
            return

        if abort.is_set():
            return

        log.debug('Downloading cover from:', cached_url)
        try:
            cdata = self.browser.open_novisit(cached_url, timeout=timeout).read()
            if cdata:
                result_queue.put((self, cdata))
        except Exception as e:
            log.exception(u'Failed to download cover from: %s'%cached_url)
            return as_unicode(e)
    # }}}

    def get_book_details(self, log, metadata, timeout): # {{{
        from lxml import html, etree
        from calibre.ebooks.chardet import xml_to_unicode

        url = self.get_book_url(metadata.get_identifiers())[2]

        raw = self.browser.open_novisit(url, timeout=timeout).read()
        doc = html.fromstring(xml_to_unicode(raw, verbose=True)[0])

        xpt_prod_det_at = u'string(//div[contains(@class, "product-detail")]//*[contains(normalize-space(text()), "%s")]/a[1]/@title)'
        xpt_prod_det_tx = u'substring-after(//div[contains(@class, "product-detail")]//text()[contains(., "%s")], ":")'

        # series Серия/Серии
        xpt = xpt_prod_det_at % u'Сери'
        # % u'Серия:'
        series = doc.xpath(xpt)
        if series:
            metadata.series = series

        xpt = u'normalize-space(substring-after(//meta[@name="description"]/@content, "ISBN"))'
        isbn_str = doc.xpath(xpt)
        if isbn_str:
            all_isbns = [check_isbn(isbn) for isbn in self.isbnRegex.findall(isbn_str) if _verifyISBNIntegrity(log, isbn)]
            if all_isbns:
                metadata.all_isbns = all_isbns
                metadata.isbn = all_isbns[0]

        xpt = xpt_prod_det_at % u'Издатель'
        publishers = doc.xpath(xpt)
        if publishers:
            metadata.publisher = publishers

        displ_lang = None
        xpt = xpt_prod_det_tx % u'Язык'
        langs = doc.xpath(xpt)
        if langs:
            lng_splt = langs.split(u',')
            if lng_splt:
                displ_lang = lng_splt[0].strip()
        metadata.language = _translageLanguageToCode(displ_lang)
        #log.debug(u'language: %s'%displ_lang)

        # can be set before from xml search responce
        if not metadata.pubdate:
            xpt = u'normalize-space(//div[@class="product-misc"]//text()[contains(., "г.")])'
            yearIn = doc.xpath(xpt)
            if yearIn:
                matcher = re.search(r'\d{4}', yearIn)
                if matcher:
                    metadata.pubdate = toPubdate(log, matcher.group(0))

        # overwrite comments from HTML if any
        xpt = u'//table[@id="detail_description"]//tr/td'
        comment_elem = doc.xpath(xpt)
        if comment_elem:
            comments = unicode(etree.tostring(comment_elem[0], encoding=unicode))
            if comments:
                # cleanup root tag, TODO: remove tags like object/embeded
                comments = re.sub(ur'\A.*?<td.*?>|</td>.*\Z', u'', comments.strip(), re.MULTILINE).strip()
                if comments and (not metadata.comments or len(comments) > len(metadata.comments)):
                    metadata.comments = comments
                else:
                    log.debug('HTML book description skipped in favour of search service xml responce')
        else:
            log.debug('No book description found in HTML')
    # }}}

def _quoteString(strToQuote): # {{{
    return '"' + strToQuote + '"' if strToQuote and strToQuote.find(' ') != -1 else strToQuote
# }}}

def _verifyISBNIntegrity(log, isbn): # {{{
    # Online ISBN-Check http://www.isbn-check.de/
    res = check_isbn(isbn)
    if not res:
        log.error(u'ISBN integrity check failed for "%s"'%isbn)
    return res is not None
# }}}

# TODO: make customizable
def _translateToBigCoverUrl(coverUrl): # {{{
    # http://www.ozon.ru/multimedia/books_covers/small/1002986468.gif
    # http://www.ozon.ru/multimedia/books_covers/1002986468.jpg

    m = re.match(r'^(.+\/)small\/(.+\.).+$', coverUrl)
    if m:
        coverUrl = m.group(1) + m.group(2) + 'jpg'
    return coverUrl
# }}}

def _get_affiliateId(): # {{{
    import random

    aff_id = 'romuk'
    # Use Kovid's affiliate id 30% of the time.
    if random.randint(1, 10) in (1, 2, 3):
        aff_id = 'kovidgoyal'
    return aff_id
# }}}

# for now only RUS ISBN are supported
#http://ru.wikipedia.org/wiki/ISBN_российских_издательств
isbn_pat = re.compile(r"""
    ^
    (\d{3})?            # match GS1 Prefix for ISBN13
    (5)                 # group identifier for rRussian-speaking countries
    (                   # begin variable length for Publisher
        [01]\d{1}|      # 2x
        [2-6]\d{2}|     # 3x
        7\d{3}|         # 4x (starting with 7)
        8[0-4]\d{2}|    # 4x (starting with 8)
        9[2567]\d{2}|   # 4x (starting with 9)
        99[26]\d{1}|    # 4x (starting with 99)
        8[5-9]\d{3}|    # 5x (starting with 8)
        9[348]\d{3}|    # 5x (starting with 9)
        900\d{2}|       # 5x (starting with 900)
        91[0-8]\d{2}|   # 5x (starting with 91)
        90[1-9]\d{3}|   # 6x (starting with 90)
        919\d{3}|       # 6x (starting with 919)
        99[^26]\d{4}    # 7x (starting with 99)
    )                   # end variable length for Publisher
    (\d+)               # Title
    ([\dX])             # Check digit
    $
""", re.VERBOSE)

def _format_isbn(log, isbn):  # {{{
    res = check_isbn(isbn)
    if res:
        m = isbn_pat.match(res)
        if m:
            res = '-'.join([g for g in m.groups() if g])
        else:
            log.error('cannot format isbn %s'%isbn)
    return res
# }}}

def _translageLanguageToCode(displayLang): # {{{
    displayLang = unicode(displayLang).strip() if displayLang else None
    langTbl = {  None: 'ru',
                u'Немецкий': 'de',
                u'Английский': 'en',
                u'Французский': 'fr',
                u'Итальянский': 'it',
                u'Испанский': 'es',
                u'Китайский': 'zh',
                u'Японский': 'ja',
                u'Финский' : 'fi',
                u'Польский' : 'pl',}
    return langTbl.get(displayLang, None)
# }}}

# [В.П. Колесников | Колесников В.П.]-> В. П. BКолесников
def _normalizeAuthorNameWithInitials(name): # {{{
    res = name
    if name:
        re1 = u'^(?P<lname>\S+)\s+(?P<fname>[^\d\W]\.)(?:\s*(?P<mname>[^\d\W]\.))?$'
        re2 = u'^(?P<fname>[^\d\W]\.)(?:\s*(?P<mname>[^\d\W]\.))?\s+(?P<lname>\S+)$'
        matcher = re.match(re1, unicode(name), re.UNICODE)
        if not matcher:
            matcher = re.match(re2, unicode(name), re.UNICODE)

        if matcher:
            d = matcher.groupdict()
            res = ' '.join(x for x in (d['fname'], d['mname'], d['lname']) if x)
    return res
# }}}

def toPubdate(log, yearAsString): # {{{
    res = None
    if yearAsString:
        try:
            res = parse_only_date(yearAsString)
        except:
            log.error('cannot parse to date %s'%yearAsString)
    return res
# }}}

def _listToUnicodePrintStr(lst): # {{{
    return u'[' + u', '.join(unicode(x) for x in lst) + u']'
# }}}

if __name__ == '__main__': # tests {{{
    # To run these test use: calibre-debug -e src/calibre/ebooks/metadata/sources/ozon.py
    # comment some touched_fields before run thoses tests
    from calibre.ebooks.metadata.sources.test import (test_identify_plugin,
            title_test, authors_test, isbn_test)


    test_identify_plugin(Ozon.name,
        [
#            (
#                {'identifiers':{}, 'title':u'Норвежский язык: Практический курс',
#                    'authors':[u'Колесников В.П.', u'Г.В. Шатков']},
#                [title_test(u'Норвежский язык: Практический курс', exact=True),
#                 authors_test([u'В. П. Колесников', u'Г. В. Шатков'])]
#            ),
             (
                {'identifiers':{'isbn': '9785916572629'} },
                [title_test(u'На все четыре стороны', exact=True),
                 authors_test([u'А. А. Гилл'])]
             ),
             (
                {'identifiers':{}, 'title':u'Der Himmel Kennt Keine Gunstlinge',
                    'authors':[u'Erich Maria Remarque']},
                [title_test(u'Der Himmel Kennt Keine Gunstlinge', exact=True),
                 authors_test([u'Erich Maria Remarque'])]
             ),
             (
                {'identifiers':{ }, 'title':u'Метро 2033',
                    'authors':[u'Дмитрий Глуховский']},
                [title_test(u'Метро 2033', exact=False)]
             ),
             (
                {'identifiers':{'isbn': '9785170727209'}, 'title':u'Метро 2033',
                    'authors':[u'Дмитрий Глуховский']},
                [title_test(u'Метро 2033', exact=True),
                    authors_test([u'Дмитрий Глуховский']),
                    isbn_test('9785170727209')]
             ),
             (
                {'identifiers':{'isbn': '5-699-13613-4'}, 'title':u'Метро 2033',
                    'authors':[u'Дмитрий Глуховский']},
                [title_test(u'Метро 2033', exact=True),
                 authors_test([u'Дмитрий Глуховский'])]
             ),
             (
                {'identifiers':{}, 'title':u'Метро',
                    'authors':[u'Глуховский']},
                [title_test(u'Метро', exact=False)]
             ),
    ])
# }}}
