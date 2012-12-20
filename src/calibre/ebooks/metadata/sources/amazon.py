#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import socket, time, re
from urllib import urlencode
from threading import Thread
from Queue import Queue, Empty


from calibre import as_unicode, random_user_agent
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import (Source, Option, fixcase,
        fixauthors)
from calibre.ebooks.metadata.book.base import Metadata
from calibre.utils.date import parse_only_date
from calibre.utils.localization import canonicalize_lang

class Worker(Thread): # Get details {{{

    '''
    Get book details from amazons book page in a separate thread
    '''

    def __init__(self, url, result_queue, browser, log, relevance, domain,
            plugin, timeout=20, testing=False):
        Thread.__init__(self)
        self.daemon = True
        self.testing = testing
        self.url, self.result_queue = url, result_queue
        self.log, self.timeout = log, timeout
        self.relevance, self.plugin = relevance, plugin
        self.browser = browser.clone_browser()
        self.cover_url = self.amazon_id = self.isbn = None
        self.domain = domain
        from lxml.html import tostring
        self.tostring = tostring

        months = {
                'de': {
            1 : ['jän'],
            2 : ['februar'],
            3 : ['märz'],
            5 : ['mai'],
            6 : ['juni'],
            7 : ['juli'],
            10: ['okt'],
            12: ['dez']
            },
                'it': {
            1: ['enn'],
            2: ['febbr'],
            5: ['magg'],
            6: ['giugno'],
            7: ['luglio'],
            8: ['ag'],
            9: ['sett'],
            10: ['ott'],
            12: ['dic'],
            },
                'fr': {
            1: ['janv'],
            2: ['févr'],
            3: ['mars'],
            4: ['avril'],
            5: ['mai'],
            6: ['juin'],
            7: ['juil'],
            8: ['août'],
            9: ['sept'],
            12: ['déc'],
            },
            'es': {
                1: ['enero'],
                2: ['febrero'],
                3: ['marzo'],
                4: ['abril'],
                5: ['mayo'],
                6: ['junio'],
                7: ['julio'],
                8: ['agosto'],
                9: ['septiembre', 'setiembre'],
                10: ['octubre'],
                11: ['noviembre'],
                12: ['diciembre'],
            },
                'jp': {
            1: [u'1月'],
            2: [u'2月'],
            3: [u'3月'],
            4: [u'4月'],
            5: [u'5月'],
            6: [u'6月'],
            7: [u'7月'],
            8: [u'8月'],
            9: [u'9月'],
            10: [u'10月'],
            11: [u'11月'],
            12: [u'12月'],
            },

        }

        self.english_months = [None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        self.months = months.get(self.domain, {})

        self.pd_xpath = '''
            //h2[text()="Product Details" or \
                 text()="Produktinformation" or \
                 text()="Dettagli prodotto" or \
                 text()="Product details" or \
                 text()="Détails sur le produit" or \
                 text()="Detalles del producto" or \
                 text()="登録情報"]/../div[@class="content"]
            '''
        # Editor: is for Spanish
        self.publisher_xpath = '''
            descendant::*[starts-with(text(), "Publisher:") or \
                    starts-with(text(), "Verlag:") or \
                    starts-with(text(), "Editore:") or \
                    starts-with(text(), "Editeur") or \
                    starts-with(text(), "Editor:") or \
                    starts-with(text(), "出版社:")]
            '''
        self.language_xpath =    '''
            descendant::*[
                starts-with(text(), "Language:") \
                or text() = "Language" \
                or text() = "Sprache:" \
                or text() = "Lingua:" \
                or text() = "Idioma:" \
                or starts-with(text(), "Langue") \
                or starts-with(text(), "言語") \
                ]
            '''

        self.ratings_pat = re.compile(
            r'([0-9.]+) ?(out of|von|su|étoiles sur|つ星のうち|de un máximo de) ([\d\.]+)( (stars|Sternen|stelle|estrellas)){0,1}')

        lm = {
                'eng': ('English', 'Englisch'),
                'fra': ('French', 'Français'),
                'ita': ('Italian', 'Italiano'),
                'deu': ('German', 'Deutsch'),
                'spa': ('Spanish', 'Espa\xf1ol', 'Espaniol'),
                'jpn': ('Japanese', u'日本語'),
                }
        self.lang_map = {}
        for code, names in lm.iteritems():
            for name in names:
                self.lang_map[name] = code

        self.series_pat = re.compile(
                r'''
                \|\s*              # Prefix
                (Series)\s*:\s*    # Series declaration
                (?P<series>.+?)\s+  # The series name
                \((Book)\s*    # Book declaration
                (?P<index>[0-9.]+) # Series index
                \s*\)
                ''', re.X)

    def delocalize_datestr(self, raw):
        if not self.months:
            return raw
        ans = raw.lower()
        for i, vals in self.months.iteritems():
            for x in vals:
                ans = ans.replace(x, self.english_months[i])
        ans = ans.replace(' de ', ' ')
        return ans

    def run(self):
        try:
            self.get_details()
        except:
            self.log.exception('get_details failed for url: %r'%self.url)

    def get_details(self):
        from calibre.utils.cleantext import clean_ascii_chars
        from calibre.ebooks.chardet import xml_to_unicode
        import html5lib

        try:
            raw = self.browser.open_novisit(self.url, timeout=self.timeout).read().strip()
        except Exception as e:
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                self.log.error('URL malformed: %r'%self.url)
                return
            attr = getattr(e, 'args', [None])
            attr = attr if attr else [None]
            if isinstance(attr[0], socket.timeout):
                msg = 'Amazon timed out. Try again later.'
                self.log.error(msg)
            else:
                msg = 'Failed to make details query: %r'%self.url
                self.log.exception(msg)
            return

        oraw = raw
        raw = xml_to_unicode(raw, strip_encoding_pats=True,
                resolve_entities=True)[0]
        if '<title>404 - ' in raw:
            self.log.error('URL malformed: %r'%self.url)
            return

        try:
            root = html5lib.parse(clean_ascii_chars(raw), treebuilder='lxml',
                    namespaceHTMLElements=False)
        except:
            msg = 'Failed to parse amazon details page: %r'%self.url
            self.log.exception(msg)
            return

        errmsg = root.xpath('//*[@id="errorMessage"]')
        if errmsg:
            msg = 'Failed to parse amazon details page: %r'%self.url
            msg += self.tostring(errmsg, method='text', encoding=unicode).strip()
            self.log.error(msg)
            return

        self.parse_details(oraw, root)

    def parse_details(self, raw, root):
        try:
            asin = self.parse_asin(root)
        except:
            self.log.exception('Error parsing asin for url: %r'%self.url)
            asin = None
        if self.testing:
            import tempfile
            with tempfile.NamedTemporaryFile(prefix=asin + '_',
                    suffix='.html', delete=False) as f:
                f.write(raw)
            print ('Downloaded html for', asin, 'saved in', f.name)

        try:
            title = self.parse_title(root)
        except:
            self.log.exception('Error parsing title for url: %r'%self.url)
            title = None

        try:
            authors = self.parse_authors(root)
        except:
            self.log.exception('Error parsing authors for url: %r'%self.url)
            authors = []


        if not title or not authors or not asin:
            self.log.error('Could not find title/authors/asin for %r'%self.url)
            self.log.error('ASIN: %r Title: %r Authors: %r'%(asin, title,
                authors))
            return

        mi = Metadata(title, authors)
        idtype = 'amazon' if self.domain == 'com' else 'amazon_'+self.domain
        mi.set_identifier(idtype, asin)
        self.amazon_id = asin

        try:
            mi.rating = self.parse_rating(root)
        except:
            self.log.exception('Error parsing ratings for url: %r'%self.url)

        try:
            mi.comments = self.parse_comments(root)
        except:
            self.log.exception('Error parsing comments for url: %r'%self.url)

        try:
            series, series_index = self.parse_series(root)
            if series:
                mi.series, mi.series_index = series, series_index
            elif self.testing:
                mi.series, mi.series_index = 'Dummy series for testing', 1
        except:
            self.log.exception('Error parsing series for url: %r'%self.url)

        try:
            self.cover_url = self.parse_cover(root)
        except:
            self.log.exception('Error parsing cover for url: %r'%self.url)
        mi.has_cover = bool(self.cover_url)

        pd = root.xpath(self.pd_xpath)
        if pd:
            pd = pd[0]

            try:
                isbn = self.parse_isbn(pd)
                if isbn:
                    self.isbn = mi.isbn = isbn
            except:
                self.log.exception('Error parsing ISBN for url: %r'%self.url)

            try:
                mi.publisher = self.parse_publisher(pd)
            except:
                self.log.exception('Error parsing publisher for url: %r'%self.url)

            try:
                mi.pubdate = self.parse_pubdate(pd)
            except:
                self.log.exception('Error parsing publish date for url: %r'%self.url)

            try:
                lang = self.parse_language(pd)
                if lang:
                    mi.language = lang
            except:
                self.log.exception('Error parsing language for url: %r'%self.url)

        else:
            self.log.warning('Failed to find product description for url: %r'%self.url)

        mi.source_relevance = self.relevance

        if self.amazon_id:
            if self.isbn:
                self.plugin.cache_isbn_to_identifier(self.isbn, self.amazon_id)
            if self.cover_url:
                self.plugin.cache_identifier_to_cover_url(self.amazon_id,
                        self.cover_url)

        self.plugin.clean_downloaded_metadata(mi)

        self.result_queue.put(mi)

    def parse_asin(self, root):
        link = root.xpath('//link[@rel="canonical" and @href]')
        for l in link:
            return l.get('href').rpartition('/')[-1]

    def parse_title(self, root):
        tdiv = root.xpath('//h1[contains(@class, "parseasinTitle")]')[0]
        actual_title = tdiv.xpath('descendant::*[@id="btAsinTitle"]')
        if actual_title:
            title = self.tostring(actual_title[0], encoding=unicode,
                    method='text').strip()
        else:
            title = self.tostring(tdiv, encoding=unicode, method='text').strip()
        ans = re.sub(r'[(\[].*[)\]]', '', title).strip()
        if not ans:
            ans = title.rpartition('[')[0].strip()
        return ans

    def parse_authors(self, root):
        x = '//h1[contains(@class, "parseasinTitle")]/following-sibling::span/*[(name()="a" and @href) or (name()="span" and @class="contributorNameTrigger")]'
        aname = root.xpath(x)
        if not aname:
            aname = root.xpath('''
            //h1[contains(@class, "parseasinTitle")]/following-sibling::*[(name()="a" and @href) or (name()="span" and @class="contributorNameTrigger")]
                    ''')
        for x in aname:
            x.tail = ''
        authors = [self.tostring(x, encoding=unicode, method='text').strip() for x
                in aname]
        authors = [a for a in authors if a]
        return authors

    def parse_rating(self, root):
        ratings = root.xpath('//div[@class="jumpBar"]/descendant::span[contains(@class,"asinReviewsSummary")]')
        if not ratings:
            ratings = root.xpath('//div[@class="buying"]/descendant::span[contains(@class,"asinReviewsSummary")]')
        if not ratings:
            ratings = root.xpath('//span[@class="crAvgStars"]/descendant::span[contains(@class,"asinReviewsSummary")]')
        if ratings:
            for elem in ratings[0].xpath('descendant::*[@title]'):
                t = elem.get('title').strip()
                m = self.ratings_pat.match(t)
                if m is not None:
                    return float(m.group(1))/float(m.group(3)) * 5

    def _render_comments(self, desc):
        from calibre.library.comments import sanitize_comments_html

        for c in desc.xpath('descendant::noscript'):
            c.getparent().remove(c)
        for c in desc.xpath('descendant::*[@class="seeAll" or'
                ' @class="emptyClear" or @id="collapsePS" or'
                ' @id="expandPS"]'):
            c.getparent().remove(c)

        for a in desc.xpath('descendant::a[@href]'):
            del a.attrib['href']
            a.tag = 'span'
        desc = self.tostring(desc, method='html', encoding=unicode).strip()

        # Encoding bug in Amazon data U+fffd (replacement char)
        # in some examples it is present in place of '
        desc = desc.replace('\ufffd', "'")
        # remove all attributes from tags
        desc = re.sub(r'<([a-zA-Z0-9]+)\s[^>]+>', r'<\1>', desc)
        # Collapse whitespace
        #desc = re.sub('\n+', '\n', desc)
        #desc = re.sub(' +', ' ', desc)
        # Remove the notice about text referring to out of print editions
        desc = re.sub(r'(?s)<em>--This text ref.*?</em>', '', desc)
        # Remove comments
        desc = re.sub(r'(?s)<!--.*?-->', '', desc)
        return sanitize_comments_html(desc)


    def parse_comments(self, root):
        ans = ''
        desc = root.xpath('//div[@id="ps-content"]/div[@class="content"]')
        if desc:
            ans = self._render_comments(desc[0])

        desc = root.xpath('//div[@id="productDescription"]/*[@class="content"]')
        if desc:
            ans += self._render_comments(desc[0])
        return ans

    def parse_series(self, root):
        ans = (None, None)
        desc = root.xpath('//div[@id="ps-content"]/div[@class="buying"]')
        if desc:
            raw = self.tostring(desc[0], method='text', encoding=unicode)
            raw = re.sub(r'\s+', ' ', raw)
            match = self.series_pat.search(raw)
            if match is not None:
                s, i = match.group('series'), float(match.group('index'))
                if s:
                    ans = (s, i)
        return ans


    def parse_cover(self, root):
        imgs = root.xpath('//img[(@id="prodImage" or @id="original-main-image") and @src]')
        if imgs:
            src = imgs[0].get('src')
            if '/no-image-avail' not in src:
                parts = src.split('/')
                if len(parts) > 3:
                    bn = parts[-1]
                    sparts = bn.split('_')
                    if len(sparts) > 2:
                        bn = sparts[0] + sparts[-1]
                        return ('/'.join(parts[:-1]))+'/'+bn

    def parse_isbn(self, pd):
        items = pd.xpath(
            'descendant::*[starts-with(text(), "ISBN")]')
        if not items:
            items = pd.xpath(
                'descendant::b[contains(text(), "ISBN:")]')
        for x in reversed(items):
            if x.tail:
                ans = check_isbn(x.tail.strip())
                if ans:
                    return ans

    def parse_publisher(self, pd):
        for x in reversed(pd.xpath(self.publisher_xpath)):
            if x.tail:
                ans = x.tail.partition(';')[0]
                return ans.partition('(')[0].strip()

    def parse_pubdate(self, pd):
        for x in reversed(pd.xpath(self.publisher_xpath)):
            if x.tail:
                ans = x.tail
                date = ans.rpartition('(')[-1].replace(')', '').strip()
                date = self.delocalize_datestr(date)
                return parse_only_date(date, assume_utc=True)

    def parse_language(self, pd):
        for x in reversed(pd.xpath(self.language_xpath)):
            if x.tail:
                raw = x.tail.strip()
                ans = self.lang_map.get(raw, None)
                if ans:
                    return ans
                ans = canonicalize_lang(ans)
                if ans:
                    return ans
# }}}

class Amazon(Source):

    name = 'Amazon.com'
    description = _('Downloads metadata and covers from Amazon')

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset(['title', 'authors', 'identifier:amazon',
        'identifier:isbn', 'rating', 'comments', 'publisher', 'pubdate',
        'languages', 'series'])
    has_html_comments = True
    supports_gzip_transfer_encoding = True

    AMAZON_DOMAINS = {
            'com': _('US'),
            'fr' : _('France'),
            'de' : _('Germany'),
            'uk' : _('UK'),
            'it' : _('Italy'),
            'jp' : _('Japan'),
            'es' : _('Spain'),
    }

    options = (
            Option('domain', 'choices', 'com', _('Amazon website to use:'),
                _('Metadata from Amazon will be fetched using this '
                    'country\'s Amazon website.'), choices=AMAZON_DOMAINS),
            )

    def __init__(self, *args, **kwargs):
        Source.__init__(self, *args, **kwargs)
        self.set_amazon_id_touched_fields()

    def test_fields(self, mi):
        '''
        Return the first field from self.touched_fields that is null on the
        mi object
        '''
        for key in self.touched_fields:
            if key.startswith('identifier:'):
                key = key.partition(':')[-1]
                if key == 'amazon':
                    if self.domain != 'com':
                        key += '_' + self.domain
                if not mi.has_identifier(key):
                    return 'identifier: ' + key
            elif mi.is_null(key):
                return key

    @property
    def user_agent(self):
        # Pass in an index to random_user_agent() to test with a particular
        # user agent
        return random_user_agent()

    def save_settings(self, *args, **kwargs):
        Source.save_settings(self, *args, **kwargs)
        self.set_amazon_id_touched_fields()

    def set_amazon_id_touched_fields(self):
        ident_name = "identifier:amazon"
        if self.domain != 'com':
            ident_name += '_' + self.domain
        tf = [x for x in self.touched_fields if not
                x.startswith('identifier:amazon')] + [ident_name]
        self.touched_fields = frozenset(tf)

    def get_domain_and_asin(self, identifiers):
        for key, val in identifiers.iteritems():
            key = key.lower()
            if key in ('amazon', 'asin'):
                return 'com', val
            if key.startswith('amazon_'):
                domain = key.split('_')[-1]
                if domain and domain in self.AMAZON_DOMAINS:
                    return domain, val
        return None, None

    def get_book_url(self, identifiers): # {{{
        domain, asin = self.get_domain_and_asin(identifiers)
        if domain and asin:
            url = None
            if domain == 'com':
                url = 'http://amzn.com/'+asin
            elif domain == 'uk':
                url = 'http://www.amazon.co.uk/dp/'+asin
            else:
                url = 'http://www.amazon.%s/dp/%s'%(domain, asin)
            if url:
                idtype = 'amazon' if domain == 'com' else 'amazon_'+domain
                return (idtype, asin, url)

    def get_book_url_name(self, idtype, idval, url):
        if idtype == 'amazon':
            return self.name
        return 'A' + idtype.replace('_', '.')[1:]
    # }}}

    @property
    def domain(self):
        x = getattr(self, 'testing_domain', None)
        if x is not None:
            return x
        domain = self.prefs['domain']
        if domain not in self.AMAZON_DOMAINS:
            domain = 'com'

        return domain

    def clean_downloaded_metadata(self, mi):
        if mi.title and self.domain in ('com', 'uk'):
            mi.title = fixcase(mi.title)
        mi.authors = fixauthors(mi.authors)
        if self.domain in ('com', 'uk'):
            mi.tags = list(map(fixcase, mi.tags))
        mi.isbn = check_isbn(mi.isbn)


    def create_query(self, log, title=None, authors=None, identifiers={}, # {{{
            domain=None):
        if domain is None:
            domain = self.domain

        idomain, asin = self.get_domain_and_asin(identifiers)
        if idomain is not None:
            domain = idomain

        # See the amazon detailed search page to get all options
        q = {   'search-alias' : 'aps',
                'unfiltered' : '1',
            }

        if domain == 'com':
            q['sort'] = 'relevanceexprank'
        else:
            q['sort'] = 'relevancerank'

        isbn = check_isbn(identifiers.get('isbn', None))

        if asin is not None:
            q['field-keywords'] = asin
        elif isbn is not None:
            q['field-isbn'] = isbn
        else:
            # Only return book results
            q['search-alias'] = 'stripbooks'
            if title:
                title_tokens = list(self.get_title_tokens(title))
                if title_tokens:
                    q['field-title'] = ' '.join(title_tokens)
            if authors:
                author_tokens = self.get_author_tokens(authors,
                        only_first_author=True)
                if author_tokens:
                    q['field-author'] = ' '.join(author_tokens)

        if not ('field-keywords' in q or 'field-isbn' in q or
                ('field-title' in q)):
            # Insufficient metadata to make an identify query
            return None, None

        # magic parameter to enable Japanese Shift_JIS encoding.
        if domain == 'jp':
            q['__mk_ja_JP'] = u'カタカナ'

        if domain == 'jp':
            encode_to = 'Shift_JIS'
        else:
            encode_to = 'latin1'
        encoded_q = dict([(x.encode(encode_to, 'ignore'), y.encode(encode_to,
            'ignore')) for x, y in
            q.iteritems()])
        udomain = domain
        if domain == 'uk':
            udomain = 'co.uk'
        elif domain == 'jp':
            udomain = 'co.jp'
        url = 'http://www.amazon.%s/s/?'%udomain + urlencode(encoded_q)
        return url, domain

    # }}}

    def get_cached_cover_url(self, identifiers): # {{{
        url = None
        domain, asin = self.get_domain_and_asin(identifiers)
        if asin is None:
            isbn = identifiers.get('isbn', None)
            if isbn is not None:
                asin = self.cached_isbn_to_identifier(isbn)
        if asin is not None:
            url = self.cached_identifier_to_cover_url(asin)

        return url
    # }}}

    def parse_results_page(self, root): # {{{
        from lxml.html import tostring

        matches = []

        def title_ok(title):
            title = title.lower()
            for x in ('bulk pack', '[audiobook]', '[audio cd]'):
                if x in title:
                    return False
            return True

        for div in root.xpath(r'//div[starts-with(@id, "result_")]'):
            links = div.xpath(r'descendant::a[@class="title" and @href]')
            if not links:
                # New amazon markup
                links = div.xpath('descendant::h3/a[@href]')
            for a in links:
                title = tostring(a, method='text', encoding=unicode)
                if title_ok(title):
                    matches.append(a.get('href'))
                break

        if not matches:
            # This can happen for some user agents that Amazon thinks are
            # mobile/less capable
            for td in root.xpath(
                r'//div[@id="Results"]/descendant::td[starts-with(@id, "search:Td:")]'):
                for a in td.xpath(r'descendant::td[@class="dataColumn"]/descendant::a[@href]/span[@class="srTitle"]/..'):
                    title = tostring(a, method='text', encoding=unicode)
                    if title_ok(title):
                        matches.append(a.get('href'))
                    break


        # Keep only the top 5 matches as the matches are sorted by relevance by
        # Amazon so lower matches are not likely to be very relevant
        return matches[:5]
    # }}}

    def identify(self, log, result_queue, abort, title=None, authors=None, # {{{
            identifiers={}, timeout=30):
        '''
        Note this method will retry without identifiers automatically if no
        match is found with identifiers.
        '''
        from calibre.utils.cleantext import clean_ascii_chars
        from calibre.ebooks.chardet import xml_to_unicode
        from lxml.html import tostring
        import html5lib

        testing = getattr(self, 'running_a_test', False)

        query, domain = self.create_query(log, title=title, authors=authors,
                identifiers=identifiers)
        if query is None:
            log.error('Insufficient metadata to construct query')
            return
        br = self.browser
        if testing:
            print ('Using user agent for amazon: %s'%self.user_agent)
        try:
            raw = br.open_novisit(query, timeout=timeout).read().strip()
        except Exception as e:
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                log.error('Query malformed: %r'%query)
                return
            attr = getattr(e, 'args', [None])
            attr = attr if attr else [None]
            if isinstance(attr[0], socket.timeout):
                msg = _('Amazon timed out. Try again later.')
                log.error(msg)
            else:
                msg = 'Failed to make identify query: %r'%query
                log.exception(msg)
            return as_unicode(msg)


        raw = clean_ascii_chars(xml_to_unicode(raw,
            strip_encoding_pats=True, resolve_entities=True)[0])

        if testing:
            import tempfile
            with tempfile.NamedTemporaryFile(prefix='amazon_results_',
                    suffix='.html', delete=False) as f:
                f.write(raw.encode('utf-8'))
            print ('Downloaded html for results page saved in', f.name)

        matches = []
        found = '<title>404 - ' not in raw

        if found:
            try:
                root = html5lib.parse(raw, treebuilder='lxml',
                        namespaceHTMLElements=False)
            except:
                msg = 'Failed to parse amazon page for query: %r'%query
                log.exception(msg)
                return msg

                errmsg = root.xpath('//*[@id="errorMessage"]')
                if errmsg:
                    msg = tostring(errmsg, method='text', encoding=unicode).strip()
                    log.error(msg)
                    # The error is almost always a not found error
                    found = False


        if found:
            matches = self.parse_results_page(root)

        if abort.is_set():
            return

        if not matches:
            if identifiers and title and authors:
                log('No matches found with identifiers, retrying using only'
                        ' title and authors. Query: %r'%query)
                return self.identify(log, result_queue, abort, title=title,
                        authors=authors, timeout=timeout)
            log.error('No matches found with query: %r'%query)
            return

        workers = [Worker(url, result_queue, br, log, i, domain, self,
                            testing=testing) for i, url in enumerate(matches)]

        for w in workers:
            w.start()
            # Don't send all requests at the same time
            time.sleep(0.1)

        while not abort.is_set():
            a_worker_is_alive = False
            for w in workers:
                w.join(0.2)
                if abort.is_set():
                    break
                if w.is_alive():
                    a_worker_is_alive = True
            if not a_worker_is_alive:
                break

        return None
    # }}}

    def download_cover(self, log, result_queue, abort, # {{{
            title=None, authors=None, identifiers={}, timeout=30):
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
        br = self.browser
        log('Downloading cover from:', cached_url)
        try:
            cdata = br.open_novisit(cached_url, timeout=timeout).read()
            result_queue.put((self, cdata))
        except:
            log.exception('Failed to download cover from:', cached_url)
    # }}}

if __name__ == '__main__': # tests {{{
    # To run these test use: calibre-debug -e
    # src/calibre/ebooks/metadata/sources/amazon.py
    from calibre.ebooks.metadata.sources.test import (test_identify_plugin,
            isbn_test, title_test, authors_test, comments_test, series_test)
    com_tests = [ # {{{

            ( # Series
                {'identifiers':{'amazon':'0756407117'}},
                [title_test(
                "Throne of the Crescent Moon"
                , exact=True), series_test('Crescent Moon Kingdoms', 1),
                comments_test('Makhslood'),
                ]
            ),

            ( # Different comments markup, using Book Description section
                {'identifiers':{'amazon':'0982514506'}},
                [title_test(
                "Griffin's Destiny: Book Three: The Griffin's Daughter Trilogy"
                , exact=True),
                comments_test('Jelena'), comments_test('Leslie'),
                ]
            ),

            ( # # in title
                {'title':'Expert C# 2008 Business Objects',
                    'authors':['Lhotka']},
                [title_test('Expert C# 2008 Business Objects', exact=True),
                    authors_test(['Rockford Lhotka'])
                    ]
            ),

            (  # Description has links
                {'identifiers':{'isbn': '9780671578275'}},
                [title_test('A Civil Campaign: A Comedy of Biology and Manners',
                    exact=True), authors_test(['Lois McMaster Bujold'])
                 ]

            ),

            ( # Sophisticated comment formatting
                {'identifiers':{'isbn': '9781416580829'}},
                [title_test('Angels & Demons - Movie Tie-In: A Novel',
                    exact=True), authors_test(['Dan Brown'])]
            ),

            ( # No specific problems
                {'identifiers':{'isbn': '0743273567'}},
                [title_test('The great gatsby', exact=True),
                    authors_test(['F. Scott Fitzgerald'])]
            ),

            (  # A newer book
                {'identifiers':{'isbn': '9780316044981'}},
                [title_test('The Heroes', exact=True),
                    authors_test(['Joe Abercrombie'])]

            ),

    ] # }}}

    de_tests = [ # {{{
            (
                {'identifiers':{'isbn': '3548283519'}},
                [title_test('Wer Wind Sät: Der Fünfte Fall Für Bodenstein Und Kirchhoff',
                    exact=True), authors_test(['Nele Neuhaus'])
                 ]

            ),
    ] # }}}

    it_tests = [ # {{{
            (
                {'identifiers':{'isbn': '8838922195'}},
                [title_test('La briscola in cinque',
                    exact=True), authors_test(['Marco Malvaldi'])
                 ]

            ),
    ] # }}}

    fr_tests = [ # {{{
            (
                {'identifiers':{'isbn': '2221116798'}},
                [title_test('L\'étrange voyage de Monsieur Daldry',
                    exact=True), authors_test(['Marc Levy'])
                 ]

            ),
    ] # }}}

    es_tests = [ # {{{
            (
                {'identifiers':{'isbn': '8483460831'}},
                [title_test('Tiempos Interesantes',
                    exact=True), authors_test(['Terry Pratchett'])
                 ]

            ),
    ] # }}}

    jp_tests = [ # {{{
            ( # isbn -> title, authors
                {'identifiers':{'isbn': '9784101302720' }},
                [title_test(u'精霊の守り人',
                    exact=True), authors_test([u'上橋 菜穂子'])
                 ]
            ),
            ( # title, authors -> isbn (will use Shift_JIS encoding in query.)
                {'title': u'考えない練習',
                 'authors': [u'小池 龍之介']},
                [isbn_test('9784093881067'), ]
            ),
    ] # }}}

    def do_test(domain, start=0, stop=None):
        tests = globals().get(domain+'_tests')
        if stop is None:
            stop = len(tests)
        tests = tests[start:stop]
        test_identify_plugin(Amazon.name, tests, modify_plugin=lambda
                p:setattr(p, 'testing_domain', domain))

    do_test('com')

    #do_test('de')

# }}}

