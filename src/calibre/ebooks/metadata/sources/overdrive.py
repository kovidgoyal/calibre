#!/usr/bin/env  python
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Fetch metadata using Overdrive Content Reserve
'''
import re, random, copy, json
from threading import RLock
from Queue import Queue, Empty


from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import Source, Option
from calibre.ebooks.metadata.book.base import Metadata

ovrdrv_data_cache = {}
cache_lock = RLock()
base_url = 'http://search.overdrive.com/'


class OverDrive(Source):

    name = 'Overdrive'
    description = _('Downloads metadata and covers from Overdrive\'s Content Reserve')

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset(['title', 'authors', 'tags', 'pubdate',
        'comments', 'publisher', 'identifier:isbn', 'series', 'series_index',
        'languages', 'identifier:overdrive'])
    has_html_comments = True
    supports_gzip_transfer_encoding = False
    cached_cover_url_is_reliable = True

    options = (
            Option('get_full_metadata', 'bool', True,
                _('Download all metadata (slow)'),
                _('Enable this option to gather all metadata available from Overdrive.')),
            )

    config_help_message = '<p>'+_('Additional metadata can be taken from Overdrive\'s book detail'
            ' page. This includes a limited set of tags used by libraries, comments, language,'
            ' and the ebook ISBN. Collecting this data is disabled by default due to the extra'
            ' time required. Check the download all metadata option below to'
            ' enable downloading this data.')

    def identify(self, log, result_queue, abort, title=None, authors=None, # {{{
            identifiers={}, timeout=30):
        ovrdrv_id = identifiers.get('overdrive', None)
        isbn = identifiers.get('isbn', None)

        br = self.browser
        ovrdrv_data = self.to_ovrdrv_data(br, log, title, authors, ovrdrv_id)
        if ovrdrv_data:
            title = ovrdrv_data[8]
            authors = ovrdrv_data[6]
            mi = Metadata(title, authors)
            self.parse_search_results(ovrdrv_data, mi)
            if ovrdrv_id is None:
                ovrdrv_id = ovrdrv_data[7]

            if self.prefs['get_full_metadata']:
                self.get_book_detail(br, ovrdrv_data[1], mi, ovrdrv_id, log)

            if isbn is not None:
                self.cache_isbn_to_identifier(isbn, ovrdrv_id)

            result_queue.put(mi)

        return None
    # }}}

    def download_cover(self, log, result_queue, abort, # {{{
            title=None, authors=None, identifiers={}, timeout=30):
        import mechanize
        cached_url = self.get_cached_cover_url(identifiers)
        if cached_url is None:
            log.info('No cached cover found, running identify')
            rq = Queue()
            self.identify(log, rq, abort, title=title, authors=authors,
                    identifiers=identifiers)
            if abort.is_set():
                return
            results = []
            while True:
                try:
                    results.append(rq.get_nowait())
                except Empty:
                    break
            results.sort(key=self.identify_results_keygen(
                title=title, authors=authors, identifiers=identifiers))
            for mi in results:
                cached_url = self.get_cached_cover_url(mi.identifiers)
                if cached_url is not None:
                    break
        if cached_url is None:
            log.info('No cover found')
            return

        if abort.is_set():
            return

        ovrdrv_id = identifiers.get('overdrive', None)
        br = self.browser
        req = mechanize.Request(cached_url)
        if ovrdrv_id is not None:
            referer = self.get_base_referer()+'ContentDetails-Cover.htm?ID='+ovrdrv_id
            req.add_header('referer', referer)

        log('Downloading cover from:', cached_url)
        try:
            cdata = br.open_novisit(req, timeout=timeout).read()
            result_queue.put((self, cdata))
        except:
            log.exception('Failed to download cover from:', cached_url)
    # }}}

    def get_cached_cover_url(self, identifiers): # {{{
        url = None
        ovrdrv_id = identifiers.get('overdrive', None)
        if ovrdrv_id is None:
            isbn = identifiers.get('isbn', None)
            if isbn is not None:
                ovrdrv_id = self.cached_isbn_to_identifier(isbn)
        if ovrdrv_id is not None:
            url = self.cached_identifier_to_cover_url(ovrdrv_id)

        return url
    # }}}

    def get_base_referer(self): # to be used for passing referrer headers to cover download
        choices = [
            'http://overdrive.chipublib.org/82DC601D-7DDE-4212-B43A-09D821935B01/10/375/en/',
            'http://emedia.clevnet.org/9D321DAD-EC0D-490D-BFD8-64AE2C96ECA8/10/241/en/',
            'http://singapore.lib.overdrive.com/F11D55BE-A917-4D63-8111-318E88B29740/10/382/en/',
            'http://ebooks.nypl.org/20E48048-A377-4520-BC43-F8729A42A424/10/257/en/',
            'http://spl.lib.overdrive.com/5875E082-4CB2-4689-9426-8509F354AFEF/10/335/en/'
        ]
        return choices[random.randint(0, len(choices)-1)]

    def format_results(self, reserveid, od_title, subtitle, series, publisher, creators, thumbimage, worldcatlink, formatid):
        fix_slashes = re.compile(r'\\/')
        thumbimage = fix_slashes.sub('/', thumbimage)
        worldcatlink = fix_slashes.sub('/', worldcatlink)
        cover_url = re.sub('(?P<img>(Ima?g(eType-)?))200', '\g<img>100', thumbimage)
        social_metadata_url = base_url+'TitleInfo.aspx?ReserveID='+reserveid+'&FormatID='+formatid
        series_num = ''
        if not series:
            if subtitle:
                title = od_title+': '+subtitle
            else:
                title = od_title
        else:
            title = od_title
            m = re.search("([0-9]+$)", subtitle)
            if m:
                series_num = float(m.group(1))
        return [cover_url, social_metadata_url, worldcatlink, series, series_num, publisher, creators, reserveid, title]

    def safe_query(self, br, query_url, post=''):
        '''
        The query must be initialized by loading an empty search results page
        this page attempts to set a cookie that Mechanize doesn't like
        copy the cookiejar to a separate instance and make a one-off request with the temp cookiejar
        '''
        import mechanize
        goodcookies = br._ua_handlers['_cookies'].cookiejar
        clean_cj = mechanize.CookieJar()
        cookies_to_copy = []
        for cookie in goodcookies:
            copied_cookie = copy.deepcopy(cookie)
            cookies_to_copy.append(copied_cookie)
        for copied_cookie in cookies_to_copy:
            clean_cj.set_cookie(copied_cookie)

        if post:
            br.open_novisit(query_url, post)
        else:
            br.open_novisit(query_url)

        br.set_cookiejar(clean_cj)

    def overdrive_search(self, br, log, q, title, author):
        import mechanize
        # re-initialize the cookiejar to so that it's clean
        clean_cj = mechanize.CookieJar()
        br.set_cookiejar(clean_cj)
        q_query = q+'default.aspx/SearchByKeyword'
        q_init_search = q+'SearchResults.aspx'
        # get first author as string - convert this to a proper cleanup function later
        author_tokens = list(self.get_author_tokens(author,
                only_first_author=True))
        title_tokens = list(self.get_title_tokens(title,
                strip_joiners=False, strip_subtitle=True))

        xref_q = ''
        if len(author_tokens) <= 1:
            initial_q = ' '.join(title_tokens)
            xref_q = '+'.join(author_tokens)
        else:
            initial_q = ' '.join(author_tokens)
            for token in title_tokens:
                if len(xref_q) < len(token):
                    xref_q = token

        log.error('Initial query is %s'%initial_q)
        log.error('Cross reference query is %s'%xref_q)

        q_xref = q+'SearchResults.svc/GetResults?iDisplayLength=50&sSearch='+xref_q
        query = '{"szKeyword":"'+initial_q+'"}'

        # main query, requires specific Content Type header
        req = mechanize.Request(q_query)
        req.add_header('Content-Type', 'application/json; charset=utf-8')
        br.open_novisit(req, query)

        # initiate the search without messing up the cookiejar
        self.safe_query(br, q_init_search)

        # get the search results object
        results = False
        iterations = 0
        while results == False:
            iterations += 1
            xreq = mechanize.Request(q_xref)
            xreq.add_header('X-Requested-With', 'XMLHttpRequest')
            xreq.add_header('Referer', q_init_search)
            xreq.add_header('Accept', 'application/json, text/javascript, */*')
            raw = br.open_novisit(xreq).read()
            for m in re.finditer(ur'"iTotalDisplayRecords":(?P<displayrecords>\d+).*?"iTotalRecords":(?P<totalrecords>\d+)', raw):
                if int(m.group('totalrecords')) == 0:
                    return ''
                elif int(m.group('displayrecords')) >= 1:
                    results = True
                elif int(m.group('totalrecords')) >= 1 and iterations < 3:
                    if xref_q.find('+') != -1:
                        xref_tokens = xref_q.split('+')
                        xref_q = xref_tokens[0]
                        for token in xref_tokens:
                            if len(xref_q) < len(token):
                                xref_q = token
                        #log.error('rewrote xref_q, new query is '+xref_q)
                else:
                        xref_q = ''
                q_xref = q+'SearchResults.svc/GetResults?iDisplayLength=50&sSearch='+xref_q

        return self.sort_ovrdrv_results(raw, log, title, title_tokens, author, author_tokens)


    def sort_ovrdrv_results(self, raw, log, title=None, title_tokens=None, author=None, author_tokens=None, ovrdrv_id=None):
        close_matches = []
        raw = re.sub('.*?\[\[(?P<content>.*?)\]\].*', '[[\g<content>]]', raw)
        results = json.loads(raw)
        #log.error('raw results are:'+str(results))
        # The search results are either from a keyword search or a multi-format list from a single ID,
        # sort through the results for closest match/format
        if results:
            for reserveid, od_title, subtitle, edition, series, publisher, format, formatid, creators, \
                    thumbimage, shortdescription, worldcatlink, excerptlink, creatorfile, sorttitle, \
                    availabletolibrary, availabletoretailer, relevancyrank, unknown1, unknown2, unknown3 in results:
                #log.error("this record's title is "+od_title+", subtitle is "+subtitle+", author[s] are "+creators+", series is "+series)
                if ovrdrv_id is not None and int(formatid) in [1, 50, 410, 900]:
                    #log.error('overdrive id is not None, searching based on format type priority')
                    return self.format_results(reserveid, od_title, subtitle, series, publisher,
                            creators, thumbimage, worldcatlink, formatid)
                else:
                    if creators:
                        creators = creators.split(', ')

                    # if an exact match in a preferred format occurs
                    if ((author and creators and creators[0] == author[0]) or (not author and not creators)) and od_title.lower() == title.lower() and int(formatid) in [1, 50, 410, 900] and thumbimage:
                        return self.format_results(reserveid, od_title, subtitle, series, publisher,
                                creators, thumbimage, worldcatlink, formatid)
                    else:
                        close_title_match = False
                        close_author_match = False
                        for token in title_tokens:
                            if od_title.lower().find(token.lower()) != -1:
                                close_title_match = True
                            else:
                                close_title_match = False
                                break
                        for author in creators:
                            for token in author_tokens:
                                if author.lower().find(token.lower()) != -1:
                                    close_author_match = True
                                else:
                                    close_author_match = False
                                    break
                            if close_author_match:
                                break
                        if close_title_match and close_author_match and int(formatid) in [1, 50, 410, 900] and thumbimage:
                            if subtitle and series:
                                close_matches.insert(0, self.format_results(reserveid, od_title, subtitle, series, publisher, creators, thumbimage, worldcatlink, formatid))
                            else:
                                close_matches.append(self.format_results(reserveid, od_title, subtitle, series, publisher, creators, thumbimage, worldcatlink, formatid))

                        elif close_title_match and close_author_match and int(formatid) in [1, 50, 410, 900]:
                            close_matches.append(self.format_results(reserveid, od_title, subtitle, series, publisher, creators, thumbimage, worldcatlink, formatid))

            if close_matches:
                return close_matches[0]
            else:
                return ''
        else:
            return ''

    def overdrive_get_record(self, br, log, q, ovrdrv_id):
        import mechanize
        search_url = q+'SearchResults.aspx?ReserveID={'+ovrdrv_id+'}'
        results_url = q+'SearchResults.svc/GetResults?sEcho=1&iColumns=18&sColumns=ReserveID%2CTitle%2CSubtitle%2CEdition%2CSeries%2CPublisher%2CFormat%2CFormatID%2CCreators%2CThumbImage%2CShortDescription%2CWorldCatLink%2CExcerptLink%2CCreatorFile%2CSortTitle%2CAvailableToLibrary%2CAvailableToRetailer%2CRelevancyRank&iDisplayStart=0&iDisplayLength=10&sSearch=&bEscapeRegex=true&iSortingCols=1&iSortCol_0=17&sSortDir_0=asc'

        # re-initialize the cookiejar to so that it's clean
        clean_cj = mechanize.CookieJar()
        br.set_cookiejar(clean_cj)
        # get the base url to set the proper session cookie
        br.open_novisit(q)

        # initialize the search
        self.safe_query(br, search_url)

        # get the results
        req = mechanize.Request(results_url)
        req.add_header('X-Requested-With', 'XMLHttpRequest')
        req.add_header('Referer', search_url)
        req.add_header('Accept', 'application/json, text/javascript, */*')
        raw = br.open_novisit(req)
        raw = str(list(raw))
        clean_cj = mechanize.CookieJar()
        br.set_cookiejar(clean_cj)
        return self.sort_ovrdrv_results(raw, log, None, None, None, ovrdrv_id)


    def find_ovrdrv_data(self, br, log, title, author, isbn, ovrdrv_id=None):
        q = base_url
        if ovrdrv_id is None:
            return self.overdrive_search(br, log, q, title, author)
        else:
            return self.overdrive_get_record(br, log, q, ovrdrv_id)



    def to_ovrdrv_data(self, br, log, title=None, author=None, ovrdrv_id=None):
        '''
        Takes either a title/author combo or an Overdrive ID.  One of these
        two must be passed to this function.
        '''
        if ovrdrv_id is not None:
            with cache_lock:
                ans = ovrdrv_data_cache.get(ovrdrv_id, None)
            if ans:
                return ans
            elif ans is False:
                return None
            else:
                ovrdrv_data = self.find_ovrdrv_data(br, log, title, author, ovrdrv_id)
        else:
            try:
                ovrdrv_data = self.find_ovrdrv_data(br, log, title, author, ovrdrv_id)
            except:
                import traceback
                traceback.print_exc()
                ovrdrv_data = None
        with cache_lock:
            ovrdrv_data_cache[ovrdrv_id] = ovrdrv_data if ovrdrv_data else False

        return ovrdrv_data if ovrdrv_data else False


    def parse_search_results(self, ovrdrv_data, mi):
        '''
        Parse the formatted search results from the initial Overdrive query and
        add the values to the metadta.

        The list object has these values:
        [cover_url[0], social_metadata_url[1], worldcatlink[2], series[3], series_num[4],
        publisher[5], creators[6], reserveid[7], title[8]]

        '''
        ovrdrv_id = ovrdrv_data[7]
        mi.set_identifier('overdrive', ovrdrv_id)

        if len(ovrdrv_data[3]) > 1:
            mi.series = ovrdrv_data[3]
            if ovrdrv_data[4]:
                try:
                    mi.series_index = float(ovrdrv_data[4])
                except:
                    pass
        mi.publisher = ovrdrv_data[5]
        mi.authors = ovrdrv_data[6]
        mi.title = ovrdrv_data[8]
        cover_url = ovrdrv_data[0]
        if cover_url:
            self.cache_identifier_to_cover_url(ovrdrv_id,
                    cover_url)


    def get_book_detail(self, br, metadata_url, mi, ovrdrv_id, log):
        from lxml import html
        from calibre.ebooks.chardet import xml_to_unicode
        from calibre.utils.soupparser import fromstring
        from calibre.library.comments import sanitize_comments_html

        try:
            raw = br.open_novisit(metadata_url).read()
        except Exception, e:
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                return False
            raise
        raw = xml_to_unicode(raw, strip_encoding_pats=True,
                resolve_entities=True)[0]
        try:
            root = fromstring(raw)
        except:
            return False

        pub_date = root.xpath("//div/label[@id='ctl00_ContentPlaceHolder1_lblPubDate']/text()")
        lang = root.xpath("//div/label[@id='ctl00_ContentPlaceHolder1_lblLanguage']/text()")
        subjects = root.xpath("//div/label[@id='ctl00_ContentPlaceHolder1_lblSubjects']/text()")
        ebook_isbn = root.xpath("//td/label[@id='ctl00_ContentPlaceHolder1_lblIdentifier']/text()")
        desc = root.xpath("//div/label[@id='ctl00_ContentPlaceHolder1_lblDescription']/ancestor::div[1]")

        if pub_date:
            from calibre.utils.date import parse_date
            try:
                mi.pubdate = parse_date(pub_date[0].strip())
            except:
                pass
        if lang:
            lang = lang[0].strip().lower()
            lang = {'english':'eng', 'french':'fra', 'german':'deu',
                    'spanish':'spa'}.get(lang, None)
            if lang:
                mi.language = lang

        if ebook_isbn:
            #print "ebook isbn is "+str(ebook_isbn[0])
            isbn = check_isbn(ebook_isbn[0].strip())
            if isbn:
                self.cache_isbn_to_identifier(isbn, ovrdrv_id)
                mi.isbn = isbn
        if subjects:
            mi.tags = [tag.strip() for tag in subjects[0].split(',')]

        if desc:
            desc = desc[0]
            desc = html.tostring(desc, method='html', encoding=unicode).strip()
            # remove all attributes from tags
            desc = re.sub(r'<([a-zA-Z0-9]+)\s[^>]+>', r'<\1>', desc)
            # Remove comments
            desc = re.sub(r'(?s)<!--.*?-->', '', desc)
            mi.comments = sanitize_comments_html(desc)

        return None


if __name__ == '__main__':
    # To run these test use:
    # calibre-debug -e src/calibre/ebooks/metadata/sources/overdrive.py
    from calibre.ebooks.metadata.sources.test import (test_identify_plugin,
            title_test, authors_test)
    test_identify_plugin(OverDrive.name,
        [

            (
                {'title':'The Sea Kings Daughter',
                    'authors':['Elizabeth Peters']},
                [title_test('The Sea Kings Daughter', exact=False),
                    authors_test(['Elizabeth Peters'])]
            ),

            (
                {'title': 'Elephants', 'authors':['Agatha']},
                [title_test('Elephants Can Remember', exact=False),
                    authors_test(['Agatha Christie'])]
            ),
    ])
