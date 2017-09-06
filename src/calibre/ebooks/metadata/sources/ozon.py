#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL 3'
__copyright__ = '2011-2013 Roman Mukhin <ramses_ru at hotmail.com>'
__docformat__ = 'restructuredtext en'

# To ensure bugfix and development of this metadata source please donate
# bitcoins to 1E6CRSLY1uNstcZjLYZBHRVs1CPKbdi4ep

import re
from Queue import Queue, Empty

from calibre import as_unicode, replace_entities
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import Source, Option
from calibre.ebooks.metadata.book.base import Metadata


class Ozon(Source):
    name = 'OZON.ru'
    minimum_calibre_version = (2, 80, 0)
    version = (1, 1, 0)
    description = _('Downloads metadata and covers from OZON.ru (updated)')

    capabilities = frozenset(['identify', 'cover'])

    touched_fields = frozenset(['title', 'authors', 'identifier:isbn', 'identifier:ozon',
                                'publisher', 'pubdate', 'comments', 'series', 'rating', 'languages'])
    # Test purpose only, test function does not like when sometimes some filed are empty
    # touched_fields = frozenset(['title', 'authors', 'identifier:isbn', 'identifier:ozon',
    #                          'publisher', 'pubdate', 'comments'])

    supports_gzip_transfer_encoding = True
    has_html_comments = True

    ozon_url = 'https://www.ozon.ru'

    # match any ISBN10/13. From "Regular Expressions Cookbook"
    isbnPattern = r'(?:ISBN(?:-1[03])?:? )?(?=[-0-9 ]{17}|' \
                  '[-0-9X ]{13}|[0-9X]{10})(?:97[89][- ]?)?[0-9]{1,5}[- ]?' \
                  '(?:[0-9]+[- ]?){2}[0-9X]'
    isbnRegex = re.compile(isbnPattern)

    optkey_strictmatch = 'strict_result_match'
    options = (
        Option(optkey_strictmatch, 'bool', False,
               _('Filter out less relevant hits from the search results'),
               _(
                   'Improve search result by removing less relevant hits. It can be useful to refine the search when there are many matches')),
    )

    def get_book_url(self, identifiers):  # {{{
        import urllib2
        ozon_id = identifiers.get('ozon', None)
        res = None
        if ozon_id:
            # no affiliateId is used in search/detail
            url = '{}/context/detail/id/{}'.format(self.ozon_url, urllib2.quote(ozon_id), _get_affiliateId())
            res = ('ozon', ozon_id, url)
        return res

    # }}}

    def create_query(self, log, title=None, authors=None, identifiers={}):  # {{{
        from urllib import quote_plus

        # div_book -> search only books, ebooks and audio books
        search_url = self.ozon_url + '/?context=search&group=div_book&text='

        # for ozon.ru search we have to format ISBN with '-'
        isbn = _format_isbn(log, identifiers.get('isbn', None))
        if isbn and '-' not in isbn:
            log.error(
                "%s requires formatted ISBN for search. %s cannot be formated - removed. (only Russian ISBN format is supported now)"
                % (self.name, isbn))
            isbn = None

        ozonid = identifiers.get('ozon', None)

        qItems = set([ozonid, isbn])

        # Added Russian variant of 'Unknown'
        unk = [_('Unknown').upper(), 'Неизв.'.upper(), icu_upper('Неизв.')]

        # use only ozonid if specified otherwise ozon.ru does not like a combination
        if not ozonid:
            if title and title not in unk:
                qItems.add(title)

            if authors:
                for auth in authors:
                    if icu_upper(auth) not in unk:
                        qItems.add(auth)

        qItems.discard(None)
        qItems.discard('')
        searchText = u' '.join(qItems).strip()

        if isinstance(searchText, unicode):
            searchText = searchText.encode('utf-8')
        if not searchText:
            return None

        search_url += quote_plus(searchText)
        log.debug(u'search url: %s' % search_url)
        return search_url

    # }}}

    def identify(self, log, result_queue, abort, title=None, authors=None,
                 identifiers={}, timeout=90):  # {{{
        from calibre.ebooks.chardet import xml_to_unicode
        from HTMLParser import HTMLParser
        from lxml import etree, html
        import json

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
            log.exception(u'Failed to make identify query: %r' % query)
            return as_unicode(e)

        try:
            doc = html.fromstring(xml_to_unicode(raw, verbose=True)[0])
            entries_block = doc.xpath(u'//div[@class="bSearchResult"]')

            # log.debug(u'HTML: %s' % xml_to_unicode(raw, verbose=True)[0])

            if entries_block:
                entries = doc.xpath(u'//div[contains(@itemprop, "itemListElement")]')
                # log.debug(u'entries_block')
                # for entry in entries:
                #   log.debug('entries %s' % entree.tostring(entry))
                metadata = self.get_metadata(log, entries, title, authors, identifiers)
                self.get_all_details(log, metadata, abort, result_queue, identifiers, timeout)
            else:
                # Redirect page: trying to extract ozon_id from javascript data
                h = HTMLParser()
                entry_string = (h.unescape(etree.tostring(doc, pretty_print=True, encoding=unicode)))
                json_pat = re.compile(u'dataLayer\s*=\s*(.+)?;')
                json_info = re.search(json_pat, entry_string)
                jsondata = json_info.group(1) if json_info else None
                if jsondata:
                    idx = jsondata.rfind('}]')
                    if idx > 0:
                        jsondata = jsondata[:idx + 2]

                # log.debug(u'jsondata: %s' % jsondata)
                dataLayer = json.loads(jsondata) if jsondata else None

                ozon_id = None
                if dataLayer and dataLayer[0] and 'ecommerce' in dataLayer[0]:
                    jsproduct = dataLayer[0]['ecommerce']['detail']['products'][0]
                    ozon_id = as_unicode(jsproduct['id'])
                    entry_title = as_unicode(jsproduct['name'])

                    log.debug(u'ozon_id %s' % ozon_id)
                    log.debug(u'entry_title %s' % entry_title)

                    if ozon_id:
                        metadata = self.to_metadata_for_single_entry(log, ozon_id, entry_title, authors)
                        identifiers['ozon'] = ozon_id
                        self.get_all_details(log, [metadata], abort, result_queue, identifiers, timeout, cachedPagesDict={})

                if not ozon_id:
                    log.error('No SearchResults in Ozon.ru response found!')

        except Exception as e:
            log.exception('Failed to parse identify results')
            return as_unicode(e)

    # }}}

    def to_metadata_for_single_entry(self, log, ozon_id, title, authors):  # {{{

        # parsing javascript data from the redirect page
        mi = Metadata(title, authors)
        mi.identifiers = {'ozon': ozon_id}

        return mi

    # }}}

    def get_metadata(self, log, entries, title, authors, identifiers):  # {{{
        # some book titles have extra characters like this

        reRemoveFromTitle = re.compile(r'[?!:.,;+-/&%"\'=]')

        title = unicode(title).upper() if title else ''
        if reRemoveFromTitle:
            title = reRemoveFromTitle.sub('', title)
        authors = map(_normalizeAuthorNameWithInitials,
                      map(unicode.upper, map(unicode, authors))) if authors else None

        ozon_id = identifiers.get('ozon', None)
        # log.debug(u'ozonid: ', ozon_id)

        unk = unicode(_('Unknown')).upper()

        if title == unk:
            title = None

        if authors == [unk] or authors == []:
            authors = None

        def in_authors(authors, miauthors):
            for author in authors:
                for miauthor in miauthors:
                    # log.debug(u'=> %s <> %s'%(author, miauthor))
                    if author in miauthor:
                        return True
            return None

        def calc_source_relevance(mi):  # {{{
            relevance = 0
            if title:
                mititle = unicode(mi.title).upper() if mi.title else ''

                if reRemoveFromTitle:
                    mititle = reRemoveFromTitle.sub('', mititle)

                if title in mititle:
                    relevance += 3
                elif mititle:
                    # log.debug(u'!!%s!'%mititle)
                    relevance -= 3
            else:
                relevance += 1

            if authors:
                miauthors = map(unicode.upper, map(unicode, mi.authors)) if mi.authors else []
                # log.debug('Authors %s vs miauthors %s'%(','.join(authors), ','.join(miauthors)))

                if (in_authors(authors, miauthors)):
                    relevance += 3
                elif u''.join(miauthors):
                    # log.debug(u'!%s!'%u'|'.join(miauthors))
                    relevance -= 3
            else:
                relevance += 1

            if ozon_id:
                mozon_id = mi.identifiers['ozon']
                if ozon_id == mozon_id:
                    relevance += 100

            if relevance < 0:
                relevance = 0
            return relevance

        # }}}

        strict_match = self.prefs[self.optkey_strictmatch]
        metadata = []
        for entry in entries:

            mi = self.to_metadata(log, entry)
            relevance = calc_source_relevance(mi)
            # TODO findout which is really used
            mi.source_relevance = relevance
            mi.relevance_in_source = relevance

            if not strict_match or relevance > 0:
                # getting rid of a random book that shows up in results
                if not (mi.title == 'Unknown'):
                    metadata.append(mi)
                    # log.debug(u'added metadata %s %s.'%(mi.title,  mi.authors))
            else:
                log.debug(u'skipped metadata title: %s, authors: %s. (does not match the query - relevance score: %s)'
                          % (mi.title, u' '.join(mi.authors), relevance))
        return metadata

    # }}}

    def get_all_details(self, log, metadata, abort, result_queue, identifiers, timeout, cachedPagesDict={}):  # {{{

        req_isbn = identifiers.get('isbn', None)

        for mi in metadata:
            if abort.is_set():
                break
            try:
                ozon_id = mi.identifiers['ozon']

                try:
                    self.get_book_details(log, mi, timeout, cachedPagesDict[
                        ozon_id] if cachedPagesDict and ozon_id in cachedPagesDict else None)
                except:
                    log.exception(u'Failed to get details for metadata: %s' % mi.title)

                all_isbns = getattr(mi, 'all_isbns', [])
                if req_isbn and all_isbns and check_isbn(req_isbn) not in all_isbns:
                    log.debug(u'skipped, no requested ISBN %s found' % req_isbn)
                    continue

                for isbn in all_isbns:
                    self.cache_isbn_to_identifier(isbn, ozon_id)

                if mi.ozon_cover_url:
                    self.cache_identifier_to_cover_url(ozon_id, mi.ozon_cover_url)

                self.clean_downloaded_metadata(mi)
                result_queue.put(mi)

            except:
                log.exception(u'Failed to get details for metadata: %s' % mi.title)

    # }}}

    def to_metadata(self, log, entry):  # {{{
        title = unicode(entry.xpath(u'normalize-space(.//div[@itemprop="name"][1]/text())'))
        # log.debug(u'Title: -----> %s' % title)

        author = unicode(entry.xpath(u'normalize-space(.//div[contains(@class, "mPerson")])'))
        # log.debug(u'Author: -----> %s' % author)

        norm_authors = map(_normalizeAuthorNameWithInitials, map(unicode.strip, unicode(author).split(u',')))
        mi = Metadata(title, norm_authors)

        ozon_id = entry.get('data-href').split('/')[-2]

        if ozon_id:
            mi.identifiers = {'ozon': ozon_id}
            # log.debug(u'ozon_id: -----> %s' % ozon_id)

        mi.ozon_cover_url = None
        cover = entry.xpath(u'normalize-space(.//img[1]/@src)')
        log.debug(u'cover: -----> %s' % cover)
        if cover:
            mi.ozon_cover_url = _translateToBigCoverUrl(cover)
            # log.debug(u'mi.ozon_cover_url: -----> %s' % mi.ozon_cover_url)

        pub_year = None
        pub_year_block = entry.xpath(u'.//div[@class="bOneTileProperty"]/text()')
        year_pattern = re.compile('\d{4}')
        if pub_year_block:
            pub_year = re.search(year_pattern, pub_year_block[0])
            if pub_year:
                mi.pubdate = toPubdate(log, pub_year.group())
        # log.debug('pubdate %s' % mi.pubdate)

        mi.rating = self.get_rating(log, entry)
        # if not mi.rating:
        #    log.debug('No rating found. ozon_id:%s'%ozon_id)

        return mi

    # }}}

    def get_rating(self, log, entry):  # {{{
        # log.debug(entry)
        ozon_rating = None
        try:
            xp_rating_template = u'boolean(.//div[contains(@class, "bStars") and contains(@class, "%s")])'
            rating = None
            if entry.xpath(xp_rating_template % 'm5'):
                rating = 5.
            elif entry.xpath(xp_rating_template % 'm4'):
                rating = 4.
            elif entry.xpath(xp_rating_template % 'm3'):
                rating = 3.
            elif entry.xpath(xp_rating_template % 'm2'):
                rating = 2.
            elif entry.xpath(xp_rating_template % 'm1'):
                rating = 1.
            if rating:
                # 'rating',     A floating point number between 0 and 10
                # OZON raion N of 5, calibre of 10, but there is a bug? in identify
                ozon_rating = float(rating)
        except:
            pass
        return ozon_rating

    # }}}

    def get_cached_cover_url(self, identifiers):  # {{{
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

    def download_cover(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30,
                       get_best_cover=False):  # {{{

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
            log.exception(u'Failed to download cover from: %s' % cached_url)
            return as_unicode(e)

    # }}}

    def get_book_details(self, log, metadata, timeout, cachedPage):  # {{{
        from lxml import etree, html
        from calibre.ebooks.chardet import xml_to_unicode

        if not cachedPage:
            url = self.get_book_url(metadata.get_identifiers())[2]
            # log.debug(u'book_details_url', url)

            raw = self.browser.open_novisit(url, timeout=timeout).read()
            fulldoc = html.fromstring(xml_to_unicode(raw, verbose=True)[0])
        else:
            fulldoc = cachedPage
            log.debug(u'book_details -> using cached page')

        fullString = etree.tostring(fulldoc)
        doc = fulldoc.xpath(u'//div[@class="bDetailPage"][1]')[0]

        # series Серия/Серии
        series_elem = doc.xpath(u'//div[contains(text(), "Сери")]')
        if series_elem:
            series_text_elem = series_elem[0].getnext()
            metadata.series = series_text_elem.xpath(u'.//a/text()')[0]
            log.debug(u'**Seria: ', metadata.series)

        isbn = None
        isbn_elem = doc.xpath(u'//div[contains(text(), "ISBN")]')
        if isbn_elem:
            isbn = isbn_elem[0].getnext().xpath(u'normalize-space(./text())')
            metadata.identifiers['isbn'] = isbn

        # get authors/editors if no authors are available
        authors_joined = ','.join(metadata.authors)

        if authors_joined == '' or authors_joined == "Unknown":
            authors_from_detail = []
            editor_elem = doc.xpath(u'//div[contains(text(), "Редактор")]')
            if editor_elem:
                editor = editor_elem[0].getnext().xpath(u'.//a/text()')[0]
                authors_from_detail.append(editor + u' (ред.)')
            authors_elem = doc.xpath(u'//div[contains(text(), "Автор")]')
            if authors_elem:
                authors = authors_elem[0].getnext().xpath(u'.//a/text()')  # list
                authors_from_detail.extend(authors)
            if len(authors_from_detail) > 0:
                metadata.authors = authors_from_detail

        cover = doc.xpath('.//img[contains(@class, "fullImage")]/@src')[0]
        metadata.ozon_cover_url = _translateToBigCoverUrl(cover)

        publishers = None
        publishers_elem = doc.xpath(u'//div[contains(text(), "Издатель")]')
        if publishers_elem:
            publishers_elem = publishers_elem[0].getnext()
            publishers = publishers_elem.xpath(u'.//a/text()')[0]

        if publishers:
            metadata.publisher = publishers

        displ_lang = None
        langs = None
        langs_elem = doc.xpath(u'//div[contains(text(), "зык")]')
        if langs_elem:
            langs_elem = langs_elem[0].getnext()
            langs = langs_elem.xpath(u'text()')[0].strip() if langs_elem else None
        if langs:
            lng_splt = langs.split(u',')
            if lng_splt:
                displ_lang = lng_splt[0].strip()
                # log.debug(u'displ_lang1: ', displ_lang)
        metadata.language = _translageLanguageToCode(displ_lang)
        # log.debug(u'Language: ', metadata.language)

        # can be set before from xml search response
        if not metadata.pubdate:
            pubdate_elem = doc.xpath(u'//div[contains(text(), "Год выпуска")]')
            if pubdate_elem:
                pubYear = pubdate_elem[0].getnext().xpath(u'text()')[0].strip()
                if pubYear:
                    matcher = re.search(r'\d{4}', pubYear)
                    if matcher:
                        metadata.pubdate = toPubdate(log, matcher.group(0))
        # log.debug(u'Pubdate: ', metadata.pubdate)

        # comments, from Javascript data
        beginning = fullString.find(u'FirstBlock')
        end = fullString.find(u'}', beginning)
        comments = unicode(fullString[beginning + 75:end - 1]).decode("unicode-escape")
        metadata.comments = replace_entities(comments, 'utf-8')
        # }}}


def _verifyISBNIntegrity(log, isbn):  # {{{
    # Online ISBN-Check http://www.isbn-check.de/
    res = check_isbn(isbn)
    if not res:
        log.error(u'ISBN integrity check failed for "%s"' % isbn)
    return res is not None


# }}}

# TODO: make customizable
def _translateToBigCoverUrl(coverUrl):  # {{{
    # //static.ozone.ru/multimedia/c200/1005748980.jpg
    # http://www.ozon.ru/multimedia/books_covers/1009493080.jpg
    m = re.match(r'.+\/([^\.\\]+).+$', coverUrl)
    if m:
        coverUrl = 'https://www.ozon.ru/multimedia/books_covers/' + m.group(1) + '.jpg'
    return coverUrl


# }}}

def _get_affiliateId():  # {{{
    import random

    aff_id = 'romuk'
    # Use Kovid's affiliate id 30% of the time.
    if random.randint(1, 10) in (1, 2, 3):
        aff_id = 'kovidgoyal'
    return aff_id


# }}}

def _format_isbn(log, isbn):  # {{{
    # for now only RUS ISBN are supported
    # http://ru.wikipedia.org/wiki/ISBN_российских_издательств
    isbn_pat = re.compile(r"""
        ^
        (\d{3})?            # match GS1 Prefix for ISBN13
        (5)                 # group identifier for Russian-speaking countries
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

    res = check_isbn(isbn)
    if res:
        m = isbn_pat.match(res)
        if m:
            res = '-'.join([g for g in m.groups() if g])
        else:
            log.error('cannot format ISBN %s. Fow now only russian ISBNs are supported' % isbn)
    return res

# }}}


def _translageLanguageToCode(displayLang):  # {{{
    displayLang = unicode(displayLang).strip() if displayLang else None
    langTbl = {None: 'ru',
               u'Русский': 'ru',
               u'Немецкий': 'de',
               u'Английский': 'en',
               u'Французский': 'fr',
               u'Итальянский': 'it',
               u'Испанский': 'es',
               u'Китайский': 'zh',
               u'Японский': 'ja',
               u'Финский': 'fi',
               u'Польский': 'pl',
               u'Украинский': 'uk',}
    return langTbl.get(displayLang, None)


# }}}

# [В.П. Колесников | Колесников В.П.]-> В. П. BКолесников
def _normalizeAuthorNameWithInitials(name):  # {{{
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

def toPubdate(log, yearAsString):  # {{{
    from calibre.utils.date import parse_only_date
    res = None
    if yearAsString:
        try:
            res = parse_only_date(u"01.01." + yearAsString)
        except:
            log.error('cannot parse to date %s' % yearAsString)
    return res


# }}}

def _listToUnicodePrintStr(lst):  # {{{
    return u'[' + u', '.join(unicode(x) for x in lst) + u']'


# }}}

if __name__ == '__main__':  # tests {{{
    # To run these test use: calibre-debug src/calibre/ebooks/metadata/sources/ozon.py
    # comment some touched_fields before run thoses tests
    from calibre.ebooks.metadata.sources.test import (test_identify_plugin,
                                                      title_test, authors_test, isbn_test)

    test_identify_plugin(Ozon.name, [
    # (
    #     {'identifiers':{}, 'title':u'Норвежский язык: Практический курс',
    #         'authors':[u'Колесников В.П.', u'Г.В. Шатков']},
    #     [title_test(u'Норвежский язык: Практический курс', exact=True),
    #     authors_test([u'В. П. Колесников', u'Г. В. Шатков'])]
    # ),
    (
        {'identifiers': {'isbn': '9785916572629'}},
        [title_test(u'На все четыре стороны', exact=True),
        authors_test([u'А. А. Гилл'])]
    ),
    (
        {'identifiers': {}, 'title': u'Der Himmel Kennt Keine Gunstlinge',
        'authors': [u'Erich Maria Remarque']},
        [title_test(u'Der Himmel Kennt Keine Gunstlinge', exact=True),
        authors_test([u'Erich Maria Remarque'])]
    ),
    (
        {'identifiers': {}, 'title': u'Метро 2033',
        'authors': [u'Дмитрий Глуховский']},
        [title_test(u'Метро 2033', exact=False)]
    ),
    (
        {'identifiers': {'isbn': '9785170727209'}, 'title': u'Метро 2033',
        'authors': [u'Дмитрий Глуховский']},
        [title_test(u'Метро 2033', exact=True),
        authors_test([u'Дмитрий Глуховский']),
        isbn_test('9785170727209')]
    ),
    (
        {'identifiers': {'isbn': '5-699-13613-4'}, 'title': u'Метро 2033',
        'authors': [u'Дмитрий Глуховский']},
        [title_test(u'Метро 2033', exact=True),
        authors_test([u'Дмитрий Глуховский'])]
    ),
    (
        {'identifiers': {}, 'title': u'Метро',
        'authors': [u'Глуховский']},
        [title_test(u'Метро', exact=False)]
    ),
])
# }}}
