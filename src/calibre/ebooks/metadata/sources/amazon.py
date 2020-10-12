#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2011, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

import re
import socket
import time
from functools import partial
try:
    from queue import Empty, Queue
except ImportError:
    from Queue import Empty, Queue
from threading import Thread
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

from calibre import as_unicode, browser, random_user_agent, xml_replace_entities
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.sources.base import Option, Source, fixauthors, fixcase
from calibre.utils.localization import canonicalize_lang
from calibre.utils.random_ua import accept_header_for_ua
from calibre.ebooks.oeb.base import urlquote


def iri_quote_plus(url):
    ans = urlquote(url)
    if isinstance(ans, bytes):
        ans = ans.decode('utf-8')
    return ans.replace('%20', '+')


def user_agent_is_ok(ua):
    return 'Mobile/' not in ua and 'Mobile ' not in ua


class CaptchaError(Exception):
    pass


class SearchFailed(ValueError):
    pass


def parse_html(raw):
    try:
        from html5_parser import parse
    except ImportError:
        # Old versions of calibre
        import html5lib
        return html5lib.parse(raw, treebuilder='lxml', namespaceHTMLElements=False)
    else:
        return parse(raw)


def parse_details_page(url, log, timeout, browser, domain):
    from calibre.utils.cleantext import clean_ascii_chars
    from calibre.ebooks.chardet import xml_to_unicode
    from lxml.html import tostring
    log('Getting details from:', url)
    try:
        raw = browser.open_novisit(url, timeout=timeout).read().strip()
    except Exception as e:
        if callable(getattr(e, 'getcode', None)) and \
                e.getcode() == 404:
            log.error('URL malformed: %r' % url)
            return
        attr = getattr(e, 'args', [None])
        attr = attr if attr else [None]
        if isinstance(attr[0], socket.timeout):
            msg = 'Details page timed out. Try again later.'
            log.error(msg)
        else:
            msg = 'Failed to make details query: %r' % url
            log.exception(msg)
        return

    oraw = raw
    if 'amazon.com.br' in url:
        # amazon.com.br serves utf-8 but has an incorrect latin1 <meta> tag
        raw = raw.decode('utf-8')
    raw = xml_to_unicode(raw, strip_encoding_pats=True,
                         resolve_entities=True)[0]
    if '<title>404 - ' in raw:
        raise ValueError('URL malformed: %r' % url)
    if '>Could not find the requested document in the cache.<' in raw:
        raise ValueError('No cached entry for %s found' % url)

    try:
        root = parse_html(clean_ascii_chars(raw))
    except Exception:
        msg = 'Failed to parse amazon details page: %r' % url
        log.exception(msg)
        return
    if domain == 'jp':
        for a in root.xpath('//a[@href]'):
            if 'black-curtain-redirect.html' in a.get('href'):
                url = a.get('href')
                if url:
                    if url.startswith('/'):
                        url = 'https://amazon.co.jp' + a.get('href')
                    log('Black curtain redirect found, following')
                    return parse_details_page(url, log, timeout, browser, domain)

    errmsg = root.xpath('//*[@id="errorMessage"]')
    if errmsg:
        msg = 'Failed to parse amazon details page: %r' % url
        msg += tostring(errmsg, method='text', encoding='unicode').strip()
        log.error(msg)
        return

    from css_selectors import Select
    selector = Select(root)
    return oraw, root, selector


def parse_asin(root, log, url):
    try:
        link = root.xpath('//link[@rel="canonical" and @href]')
        for l in link:
            return l.get('href').rpartition('/')[-1]
    except Exception:
        log.exception('Error parsing ASIN for url: %r' % url)


class Worker(Thread):  # Get details {{{

    '''
    Get book details from amazons book page in a separate thread
    '''

    def __init__(self, url, result_queue, browser, log, relevance, domain,
                 plugin, timeout=20, testing=False, preparsed_root=None,
                 cover_url_processor=None, filter_result=None):
        Thread.__init__(self)
        self.cover_url_processor = cover_url_processor
        self.preparsed_root = preparsed_root
        self.daemon = True
        self.testing = testing
        self.url, self.result_queue = url, result_queue
        self.log, self.timeout = log, timeout
        self.filter_result = filter_result or (lambda x, log: True)
        self.relevance, self.plugin = relevance, plugin
        self.browser = browser
        self.cover_url = self.amazon_id = self.isbn = None
        self.domain = domain
        from lxml.html import tostring
        self.tostring = tostring

        months = {  # {{{
            'de': {
                1: ['jän', 'januar'],
                2: ['februar'],
                3: ['märz'],
                5: ['mai'],
                6: ['juni'],
                7: ['juli'],
                10: ['okt', 'oktober'],
                12: ['dez', 'dezember']
            },
            'it': {
                1: ['gennaio', 'enn'],
                2: ['febbraio', 'febbr'],
                3: ['marzo'],
                4: ['aprile'],
                5: ['maggio', 'magg'],
                6: ['giugno'],
                7: ['luglio'],
                8: ['agosto', 'ag'],
                9: ['settembre', 'sett'],
                10: ['ottobre', 'ott'],
                11: ['novembre'],
                12: ['dicembre', 'dic'],
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
            'br': {
                1: ['janeiro'],
                2: ['fevereiro'],
                3: ['março'],
                4: ['abril'],
                5: ['maio'],
                6: ['junho'],
                7: ['julho'],
                8: ['agosto'],
                9: ['setembro'],
                10: ['outubro'],
                11: ['novembro'],
                12: ['dezembro'],
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
                1: ['1月'],
                2: ['2月'],
                3: ['3月'],
                4: ['4月'],
                5: ['5月'],
                6: ['6月'],
                7: ['7月'],
                8: ['8月'],
                9: ['9月'],
                10: ['10月'],
                11: ['11月'],
                12: ['12月'],
            },
            'nl': {
                1: ['januari'], 2: ['februari'], 3: ['maart'], 5: ['mei'], 6: ['juni'], 7: ['juli'], 8: ['augustus'], 10: ['oktober'],
            }

        }  # }}}

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
                 text()="Detalhes do produto" or \
                 text()="Productgegevens" or \
                 text()="基本信息" or \
                 starts-with(text(), "登録情報")]/../div[@class="content"]
            '''
        # Editor: is for Spanish
        self.publisher_xpath = '''
            descendant::*[starts-with(text(), "Publisher:") or \
                    starts-with(text(), "Verlag:") or \
                    starts-with(text(), "Editore:") or \
                    starts-with(text(), "Editeur") or \
                    starts-with(text(), "Editor:") or \
                    starts-with(text(), "Editora:") or \
                    starts-with(text(), "Uitgever:") or \
                    starts-with(text(), "出版社:")]
            '''
        self.pubdate_xpath = '''
            descendant::*[starts-with(text(), "Publication Date:") or \
                    starts-with(text(), "Audible.com Release Date:")]
        '''
        self.publisher_names = {'Publisher', 'Uitgever', 'Verlag',
                                'Editore', 'Editeur', 'Editor', 'Editora', '出版社'}

        self.language_xpath =    '''
            descendant::*[
                starts-with(text(), "Language:") \
                or text() = "Language" \
                or text() = "Sprache:" \
                or text() = "Lingua:" \
                or text() = "Idioma:" \
                or starts-with(text(), "Langue") \
                or starts-with(text(), "言語") \
                or starts-with(text(), "语种")
                ]
            '''
        self.language_names = {'Language', 'Sprache',
                               'Lingua', 'Idioma', 'Langue', '言語', 'Taal', '语种'}

        self.tags_xpath = '''
            descendant::h2[
                text() = "Look for Similar Items by Category" or
                text() = "Ähnliche Artikel finden" or
                text() = "Buscar productos similares por categoría" or
                text() = "Ricerca articoli simili per categoria" or
                text() = "Rechercher des articles similaires par rubrique" or
                text() = "Procure por itens similares por categoria" or
                text() = "関連商品を探す"
            ]/../descendant::ul/li
        '''

        self.ratings_pat = re.compile(
            r'([0-9.,]+) ?(out of|von|van|su|étoiles sur|つ星のうち|de un máximo de|de) ([\d\.]+)( (stars|Sternen|stelle|estrellas|estrelas|sterren)){0,1}')
        self.ratings_pat_cn = re.compile('平均([0-9.]+)')
        self.ratings_pat_jp = re.compile(r'\d+つ星のうち([\d\.]+)')

        lm = {
            'eng': ('English', 'Englisch', 'Engels'),
            'fra': ('French', 'Français'),
            'ita': ('Italian', 'Italiano'),
            'deu': ('German', 'Deutsch'),
            'spa': ('Spanish', 'Espa\xf1ol', 'Espaniol'),
            'jpn': ('Japanese', '日本語'),
            'por': ('Portuguese', 'Português'),
            'nld': ('Dutch', 'Nederlands',),
            'chs': ('Chinese', '中文', '简体中文'),
        }
        self.lang_map = {}
        for code, names in lm.items():
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
        if self.domain == 'cn':
            return raw.replace('年', '-').replace('月', '-').replace('日', '')
        if not self.months:
            return raw
        ans = raw.lower()
        for i, vals in self.months.items():
            for x in vals:
                ans = ans.replace(x, self.english_months[i])
        ans = ans.replace(' de ', ' ')
        return ans

    def run(self):
        try:
            self.get_details()
        except:
            self.log.exception('get_details failed for url: %r' % self.url)

    def get_details(self):
        if self.preparsed_root is None:
            raw, root, selector = parse_details_page(
                self.url, self.log, self.timeout, self.browser, self.domain)
        else:
            raw, root, selector = self.preparsed_root

        from css_selectors import Select
        self.selector = Select(root)
        self.parse_details(raw, root)

    def parse_details(self, raw, root):
        asin = parse_asin(root, self.log, self.url)
        if not asin and root.xpath('//form[@action="/errors/validateCaptcha"]'):
            raise CaptchaError(
                'Amazon returned a CAPTCHA page, probably because you downloaded too many books. Wait for some time and try again.')
        if self.testing:
            import tempfile
            import uuid
            with tempfile.NamedTemporaryFile(prefix=(asin or type('')(uuid.uuid4())) + '_',
                                             suffix='.html', delete=False) as f:
                f.write(raw)
            print('Downloaded html for', asin, 'saved in', f.name)

        try:
            title = self.parse_title(root)
        except:
            self.log.exception('Error parsing title for url: %r' % self.url)
            title = None

        try:
            authors = self.parse_authors(root)
        except:
            self.log.exception('Error parsing authors for url: %r' % self.url)
            authors = []

        if not title or not authors or not asin:
            self.log.error(
                'Could not find title/authors/asin for %r' % self.url)
            self.log.error('ASIN: %r Title: %r Authors: %r' % (asin, title,
                                                               authors))
            return

        mi = Metadata(title, authors)
        idtype = 'amazon' if self.domain == 'com' else 'amazon_' + self.domain
        mi.set_identifier(idtype, asin)
        self.amazon_id = asin

        try:
            mi.rating = self.parse_rating(root)
        except:
            self.log.exception('Error parsing ratings for url: %r' % self.url)

        try:
            mi.comments = self.parse_comments(root, raw)
        except:
            self.log.exception('Error parsing comments for url: %r' % self.url)

        try:
            series, series_index = self.parse_series(root)
            if series:
                mi.series, mi.series_index = series, series_index
            elif self.testing:
                mi.series, mi.series_index = 'Dummy series for testing', 1
        except:
            self.log.exception('Error parsing series for url: %r' % self.url)

        try:
            mi.tags = self.parse_tags(root)
        except:
            self.log.exception('Error parsing tags for url: %r' % self.url)

        try:
            self.cover_url = self.parse_cover(root, raw)
        except:
            self.log.exception('Error parsing cover for url: %r' % self.url)
        if self.cover_url_processor is not None and self.cover_url and self.cover_url.startswith('/'):
            self.cover_url = self.cover_url_processor(self.cover_url)
        mi.has_cover = bool(self.cover_url)

        non_hero = tuple(self.selector(
            'div#bookDetails_container_div div#nonHeroSection'))
        if non_hero:
            # New style markup
            try:
                self.parse_new_details(root, mi, non_hero[0])
            except:
                self.log.exception(
                    'Failed to parse new-style book details section')
        else:
            pd = root.xpath(self.pd_xpath)
            if pd:
                pd = pd[0]

                try:
                    isbn = self.parse_isbn(pd)
                    if isbn:
                        self.isbn = mi.isbn = isbn
                except:
                    self.log.exception(
                        'Error parsing ISBN for url: %r' % self.url)

                try:
                    mi.publisher = self.parse_publisher(pd)
                except:
                    self.log.exception(
                        'Error parsing publisher for url: %r' % self.url)

                try:
                    mi.pubdate = self.parse_pubdate(pd)
                except:
                    self.log.exception(
                        'Error parsing publish date for url: %r' % self.url)

                try:
                    lang = self.parse_language(pd)
                    if lang:
                        mi.language = lang
                except:
                    self.log.exception(
                        'Error parsing language for url: %r' % self.url)

            else:
                self.log.warning(
                    'Failed to find product description for url: %r' % self.url)

        mi.source_relevance = self.relevance

        if self.amazon_id:
            if self.isbn:
                self.plugin.cache_isbn_to_identifier(self.isbn, self.amazon_id)
            if self.cover_url:
                self.plugin.cache_identifier_to_cover_url(self.amazon_id,
                                                          self.cover_url)

        self.plugin.clean_downloaded_metadata(mi)

        if self.filter_result(mi, self.log):
            self.result_queue.put(mi)

    def totext(self, elem):
        return self.tostring(elem, encoding='unicode', method='text').strip()

    def parse_title(self, root):

        def sanitize_title(title):
            ans = re.sub(r'[(\[].*[)\]]', '', title).strip()
            if not ans:
                ans = title.rpartition('[')[0].strip()
            return ans

        h1 = root.xpath('//h1[@id="title"]')
        if h1:
            h1 = h1[0]
            for child in h1.xpath('./*[contains(@class, "a-color-secondary")]'):
                h1.remove(child)
            return sanitize_title(self.totext(h1))
        tdiv = root.xpath('//h1[contains(@class, "parseasinTitle")]')
        if not tdiv:
            span = root.xpath('//*[@id="ebooksTitle"]')
            if span:
                return sanitize_title(self.totext(span[0]))
            raise ValueError('No title block found')
        tdiv = tdiv[0]
        actual_title = tdiv.xpath('descendant::*[@id="btAsinTitle"]')
        if actual_title:
            title = self.tostring(actual_title[0], encoding='unicode',
                                  method='text').strip()
        else:
            title = self.tostring(tdiv, encoding='unicode',
                                  method='text').strip()
        return sanitize_title(title)

    def parse_authors(self, root):
        for sel in (
                '#byline .author .contributorNameID',
                '#byline .author a.a-link-normal',
                '#bylineInfo .author .contributorNameID',
                '#bylineInfo .author a.a-link-normal',
        ):
            matches = tuple(self.selector(sel))
            if matches:
                authors = [self.totext(x) for x in matches]
                return [a for a in authors if a]

        x = '//h1[contains(@class, "parseasinTitle")]/following-sibling::span/*[(name()="a" and @href) or (name()="span" and @class="contributorNameTrigger")]'
        aname = root.xpath(x)
        if not aname:
            aname = root.xpath('''
            //h1[contains(@class, "parseasinTitle")]/following-sibling::*[(name()="a" and @href) or (name()="span" and @class="contributorNameTrigger")]
                    ''')
        for x in aname:
            x.tail = ''
        authors = [self.tostring(x, encoding='unicode', method='text').strip() for x
                   in aname]
        authors = [a for a in authors if a]
        return authors

    def parse_rating(self, root):
        for x in root.xpath('//div[@id="cpsims-feature" or @id="purchase-sims-feature" or @id="rhf"]'):
            # Remove the similar books section as it can cause spurious
            # ratings matches
            x.getparent().remove(x)

        rating_paths = (
            '//div[@data-feature-name="averageCustomerReviews" or @id="averageCustomerReviews"]',
            '//div[@class="jumpBar"]/descendant::span[contains(@class,"asinReviewsSummary")]',
            '//div[@class="buying"]/descendant::span[contains(@class,"asinReviewsSummary")]',
            '//span[@class="crAvgStars"]/descendant::span[contains(@class,"asinReviewsSummary")]'
        )
        ratings = None
        for p in rating_paths:
            ratings = root.xpath(p)
            if ratings:
                break

        def parse_ratings_text(text):
            try:
                m = self.ratings_pat.match(text)
                return float(m.group(1).replace(',', '.')) / float(m.group(3)) * 5
            except Exception:
                pass

        if ratings:
            ratings = ratings[0]
            for elem in ratings.xpath('descendant::*[@title]'):
                t = elem.get('title').strip()
                if self.domain == 'cn':
                    m = self.ratings_pat_cn.match(t)
                    if m is not None:
                        return float(m.group(1))
                elif self.domain == 'jp':
                    m = self.ratings_pat_jp.match(t)
                    if m is not None:
                        return float(m.group(1))
                else:
                    ans = parse_ratings_text(t)
                    if ans is not None:
                        return ans
            for elem in ratings.xpath('descendant::span[@class="a-icon-alt"]'):
                t = self.tostring(
                    elem, encoding='unicode', method='text', with_tail=False).strip()
                ans = parse_ratings_text(t)
                if ans is not None:
                    return ans

    def _render_comments(self, desc):
        from calibre.library.comments import sanitize_comments_html

        for c in desc.xpath('descendant::noscript'):
            c.getparent().remove(c)
        for c in desc.xpath('descendant::*[@class="seeAll" or'
                            ' @class="emptyClear" or @id="collapsePS" or'
                            ' @id="expandPS"]'):
            c.getparent().remove(c)
        for b in desc.xpath('descendant::b[@style]'):
            # Bing highlights search results
            s = b.get('style', '')
            if 'color' in s:
                b.tag = 'span'
                del b.attrib['style']

        for a in desc.xpath('descendant::a[@href]'):
            del a.attrib['href']
            a.tag = 'span'
        desc = self.tostring(desc, method='html', encoding='unicode').strip()
        desc = xml_replace_entities(desc, 'utf-8')

        # Encoding bug in Amazon data U+fffd (replacement char)
        # in some examples it is present in place of '
        desc = desc.replace('\ufffd', "'")
        # remove all attributes from tags
        desc = re.sub(r'<([a-zA-Z0-9]+)\s[^>]+>', r'<\1>', desc)
        # Collapse whitespace
        # desc = re.sub('\n+', '\n', desc)
        # desc = re.sub(' +', ' ', desc)
        # Remove the notice about text referring to out of print editions
        desc = re.sub(r'(?s)<em>--This text ref.*?</em>', '', desc)
        # Remove comments
        desc = re.sub(r'(?s)<!--.*?-->', '', desc)
        return sanitize_comments_html(desc)

    def parse_comments(self, root, raw):
        try:
            from urllib.parse import unquote
        except ImportError:
            from urllib import unquote
        ans = ''
        ns = tuple(self.selector('#bookDescription_feature_div noscript'))
        if ns:
            ns = ns[0]
            if len(ns) == 0 and ns.text:
                import html5lib
                # html5lib parsed noscript as CDATA
                ns = html5lib.parseFragment(
                    '<div>%s</div>' % (ns.text), treebuilder='lxml', namespaceHTMLElements=False)[0]
            else:
                ns.tag = 'div'
            ans = self._render_comments(ns)
        else:
            desc = root.xpath('//div[@id="ps-content"]/div[@class="content"]')
            if desc:
                ans = self._render_comments(desc[0])

        desc = root.xpath(
            '//div[@id="productDescription"]/*[@class="content"]')
        if desc:
            ans += self._render_comments(desc[0])
        else:
            # Idiot chickens from amazon strike again. This data is now stored
            # in a JS variable inside a script tag URL encoded.
            m = re.search(br'var\s+iframeContent\s*=\s*"([^"]+)"', raw)
            if m is not None:
                try:
                    text = unquote(m.group(1)).decode('utf-8')
                    nr = parse_html(text)
                    desc = nr.xpath(
                        '//div[@id="productDescription"]/*[@class="content"]')
                    if desc:
                        ans += self._render_comments(desc[0])
                except Exception as e:
                    self.log.warn(
                        'Parsing of obfuscated product description failed with error: %s' % as_unicode(e))

        return ans

    def parse_series(self, root):
        ans = (None, None)

        # This is found on the paperback/hardback pages for books on amazon.com
        series = root.xpath('//div[@data-feature-name="seriesTitle"]')
        if series:
            series = series[0]
            spans = series.xpath('./span')
            if spans:
                raw = self.tostring(
                    spans[0], encoding='unicode', method='text', with_tail=False).strip()
                m = re.search(r'\s+([0-9.]+)$', raw.strip())
                if m is not None:
                    series_index = float(m.group(1))
                    s = series.xpath('./a[@id="series-page-link"]')
                    if s:
                        series = self.tostring(
                            s[0], encoding='unicode', method='text', with_tail=False).strip()
                        if series:
                            ans = (series, series_index)
        # This is found on Kindle edition pages on amazon.com
        if ans == (None, None):
            for span in root.xpath('//div[@id="aboutEbooksSection"]//li/span'):
                text = (span.text or '').strip()
                m = re.match(r'Book\s+([0-9.]+)', text)
                if m is not None:
                    series_index = float(m.group(1))
                    a = span.xpath('./a[@href]')
                    if a:
                        series = self.tostring(
                            a[0], encoding='unicode', method='text', with_tail=False).strip()
                        if series:
                            ans = (series, series_index)
        # This is found on newer Kindle edition pages on amazon.com
        if ans == (None, None):
            for b in root.xpath('//div[@id="reviewFeatureGroup"]/span/b'):
                text = (b.text or '').strip()
                m = re.match(r'Book\s+([0-9.]+)', text)
                if m is not None:
                    series_index = float(m.group(1))
                    a = b.getparent().xpath('./a[@href]')
                    if a:
                        series = self.tostring(
                            a[0], encoding='unicode', method='text', with_tail=False).partition('(')[0].strip()
                        if series:
                            ans = series, series_index

        if ans == (None, None):
            desc = root.xpath('//div[@id="ps-content"]/div[@class="buying"]')
            if desc:
                raw = self.tostring(desc[0], method='text', encoding='unicode')
                raw = re.sub(r'\s+', ' ', raw)
                match = self.series_pat.search(raw)
                if match is not None:
                    s, i = match.group('series'), float(match.group('index'))
                    if s:
                        ans = (s, i)
        if ans[0]:
            ans = (re.sub(r'\s+Series$', '', ans[0]).strip(), ans[1])
            ans = (re.sub(r'\(.+?\s+Series\)$', '', ans[0]).strip(), ans[1])
        return ans

    def parse_tags(self, root):
        ans = []
        exclude_tokens = {'kindle', 'a-z'}
        exclude = {'special features', 'by authors',
                   'authors & illustrators', 'books', 'new; used & rental textbooks'}
        seen = set()
        for li in root.xpath(self.tags_xpath):
            for i, a in enumerate(li.iterdescendants('a')):
                if i > 0:
                    # we ignore the first category since it is almost always
                    # too broad
                    raw = (a.text or '').strip().replace(',', ';')
                    lraw = icu_lower(raw)
                    tokens = frozenset(lraw.split())
                    if raw and lraw not in exclude and not tokens.intersection(exclude_tokens) and lraw not in seen:
                        ans.append(raw)
                        seen.add(lraw)
        return ans

    def parse_cover(self, root, raw=b""):
        # Look for the image URL in javascript, using the first image in the
        # image gallery as the cover
        import json
        imgpat = re.compile(r"""'imageGalleryData'\s*:\s*(\[\s*{.+])""")
        for script in root.xpath('//script'):
            m = imgpat.search(script.text or '')
            if m is not None:
                try:
                    return json.loads(m.group(1))[0]['mainUrl']
                except Exception:
                    continue

        def clean_img_src(src):
            parts = src.split('/')
            if len(parts) > 3:
                bn = parts[-1]
                sparts = bn.split('_')
                if len(sparts) > 2:
                    bn = re.sub(r'\.\.jpg$', '.jpg', (sparts[0] + sparts[-1]))
                    return ('/'.join(parts[:-1])) + '/' + bn

        imgpat2 = re.compile(r'var imageSrc = "([^"]+)"')
        for script in root.xpath('//script'):
            m = imgpat2.search(script.text or '')
            if m is not None:
                src = m.group(1)
                url = clean_img_src(src)
                if url:
                    return url

        imgs = root.xpath(
            '//img[(@id="prodImage" or @id="original-main-image" or @id="main-image" or @id="main-image-nonjs") and @src]')
        if not imgs:
            imgs = (
                root.xpath('//div[@class="main-image-inner-wrapper"]/img[@src]') or
                root.xpath('//div[@id="main-image-container" or @id="ebooks-main-image-container"]//img[@src]') or
                root.xpath(
                    '//div[@id="mainImageContainer"]//img[@data-a-dynamic-image]')
            )
            for img in imgs:
                try:
                    idata = json.loads(img.get('data-a-dynamic-image'))
                except Exception:
                    imgs = ()
                else:
                    mwidth = 0
                    try:
                        url = None
                        for iurl, (width, height) in idata.items():
                            if width > mwidth:
                                mwidth = width
                                url = iurl
                        return url
                    except Exception:
                        pass

        for img in imgs:
            src = img.get('src')
            if 'data:' in src:
                continue
            if 'loading-' in src:
                js_img = re.search(br'"largeImage":"(https?://[^"]+)",', raw)
                if js_img:
                    src = js_img.group(1).decode('utf-8')
            if ('/no-image-avail' not in src and 'loading-' not in src and '/no-img-sm' not in src):
                self.log('Found image: %s' % src)
                url = clean_img_src(src)
                if url:
                    return url

    def parse_new_details(self, root, mi, non_hero):
        table = non_hero.xpath('descendant::table')[0]
        for tr in table.xpath('descendant::tr'):
            cells = tr.xpath('descendant::td')
            if len(cells) == 2:
                name = self.totext(cells[0])
                val = self.totext(cells[1])
                if not val:
                    continue
                if name in self.language_names:
                    ans = self.lang_map.get(val, None)
                    if not ans:
                        ans = canonicalize_lang(val)
                    if ans:
                        mi.language = ans
                elif name in self.publisher_names:
                    pub = val.partition(';')[0].partition('(')[0].strip()
                    if pub:
                        mi.publisher = pub
                    date = val.rpartition('(')[-1].replace(')', '').strip()
                    try:
                        from calibre.utils.date import parse_only_date
                        date = self.delocalize_datestr(date)
                        mi.pubdate = parse_only_date(date, assume_utc=True)
                    except:
                        self.log.exception('Failed to parse pubdate: %s' % val)
                elif name in {'ISBN', 'ISBN-10', 'ISBN-13'}:
                    ans = check_isbn(val)
                    if ans:
                        self.isbn = mi.isbn = ans

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
        from calibre.utils.date import parse_only_date
        for x in reversed(pd.xpath(self.pubdate_xpath)):
            if x.tail:
                date = x.tail.strip()
                date = self.delocalize_datestr(date)
                try:
                    return parse_only_date(date, assume_utc=True)
                except Exception:
                    pass
        for x in reversed(pd.xpath(self.publisher_xpath)):
            if x.tail:
                ans = x.tail
                date = ans.rpartition('(')[-1].replace(')', '').strip()
                date = self.delocalize_datestr(date)
                try:
                    return parse_only_date(date, assume_utc=True)
                except Exception:
                    pass

    def parse_language(self, pd):
        for x in reversed(pd.xpath(self.language_xpath)):
            if x.tail:
                raw = x.tail.strip().partition(',')[0].strip()
                ans = self.lang_map.get(raw, None)
                if ans:
                    return ans
                ans = canonicalize_lang(ans)
                if ans:
                    return ans
# }}}


class Amazon(Source):

    name = 'Amazon.com'
    version = (1, 2, 14)
    minimum_calibre_version = (2, 82, 0)
    description = _('Downloads metadata and covers from Amazon')

    capabilities = frozenset(('identify', 'cover'))
    touched_fields = frozenset(('title', 'authors', 'identifier:amazon',
        'rating', 'comments', 'publisher', 'pubdate',
        'languages', 'series', 'tags'))
    has_html_comments = True
    supports_gzip_transfer_encoding = True
    prefer_results_with_isbn = False

    AMAZON_DOMAINS = {
        'com': _('US'),
        'fr': _('France'),
        'de': _('Germany'),
        'uk': _('UK'),
        'au': _('Australia'),
        'it': _('Italy'),
        'jp': _('Japan'),
        'es': _('Spain'),
        'br': _('Brazil'),
        'nl': _('Netherlands'),
        'cn': _('China'),
        'ca': _('Canada'),
    }

    SERVERS = {
        'auto': _('Choose server automatically'),
        'amazon': _('Amazon servers'),
        'bing': _('Bing search cache'),
        'google': _('Google search cache'),
        'wayback': _('Wayback machine cache (slow)'),
    }

    options = (
        Option('domain', 'choices', 'com', _('Amazon country website to use:'),
               _('Metadata from Amazon will be fetched using this '
                 'country\'s Amazon website.'), choices=AMAZON_DOMAINS),
        Option('server', 'choices', 'auto', _('Server to get data from:'),
               _(
                   'Amazon has started blocking attempts to download'
                   ' metadata from its servers. To get around this problem,'
                   ' calibre can fetch the Amazon data from many different'
                   ' places where it is cached. Choose the source you prefer.'
               ), choices=SERVERS),
        Option('use_mobi_asin', 'bool', False, _('Use the MOBI-ASIN for metadata search'),
               _(
                   'Enable this option to search for metadata with an'
                   ' ASIN identifier from the MOBI file at the current country website,'
                   ' unless any other amazon id is available. Note that if the'
                   ' MOBI file came from a different Amazon country store, you could get'
                   ' incorrect results.'
               )),
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
    def browser(self):
        br = self._browser
        if br is None:
            ua = 'Mobile '
            while not user_agent_is_ok(ua):
                ua = random_user_agent(allow_ie=False)
            # ua = 'Mozilla/5.0 (Linux; Android 8.0.0; VTR-L29; rv:63.0) Gecko/20100101 Firefox/63.0'
            self._browser = br = browser(user_agent=ua)
            br.set_handle_gzip(True)
            if self.use_search_engine:
                br.addheaders += [
                    ('Accept', accept_header_for_ua(ua)),
                    ('Upgrade-insecure-requests', '1'),
                ]
            else:
                br.addheaders += [
                    ('Accept', accept_header_for_ua(ua)),
                    ('Upgrade-insecure-requests', '1'),
                    ('Referer', self.referrer_for_domain()),
                ]
        return br

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

    def get_domain_and_asin(self, identifiers, extra_domains=()):
        identifiers = {k.lower(): v for k, v in identifiers.items()}
        for key, val in identifiers.items():
            if key in ('amazon', 'asin'):
                return 'com', val
            if key.startswith('amazon_'):
                domain = key.partition('_')[-1]
                if domain and (domain in self.AMAZON_DOMAINS or domain in extra_domains):
                    return domain, val
        if self.prefs['use_mobi_asin']:
            val = identifiers.get('mobi-asin')
            if val is not None:
                return self.domain, val
        return None, None

    def referrer_for_domain(self, domain=None):
        domain = domain or self.domain
        return {
            'uk':  'https://www.amazon.co.uk/',
            'au':  'https://www.amazon.com.au/',
            'br':  'https://www.amazon.com.br/',
            'jp':  'https://www.amazon.co.jp/',
        }.get(domain, 'https://www.amazon.%s/' % domain)

    def _get_book_url(self, identifiers):  # {{{
        domain, asin = self.get_domain_and_asin(
            identifiers, extra_domains=('in', 'au', 'ca'))
        if domain and asin:
            url = None
            r = self.referrer_for_domain(domain)
            if r is not None:
                url = r + 'dp/' + asin
            if url:
                idtype = 'amazon' if domain == 'com' else 'amazon_' + domain
                return domain, idtype, asin, url

    def get_book_url(self, identifiers):
        ans = self._get_book_url(identifiers)
        if ans is not None:
            return ans[1:]

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

    @property
    def server(self):
        x = getattr(self, 'testing_server', None)
        if x is not None:
            return x
        server = self.prefs['server']
        if server not in self.SERVERS:
            server = 'auto'
        return server

    @property
    def use_search_engine(self):
        return self.server != 'amazon'

    def clean_downloaded_metadata(self, mi):
        docase = (
            mi.language == 'eng' or
            (mi.is_null('language') and self.domain in {'com', 'uk', 'au'})
        )
        if mi.title and docase:
            # Remove series information from title
            m = re.search(r'\S+\s+(\(.+?\s+Book\s+\d+\))$', mi.title)
            if m is not None:
                mi.title = mi.title.replace(m.group(1), '').strip()
            mi.title = fixcase(mi.title)
        mi.authors = fixauthors(mi.authors)
        if mi.tags and docase:
            mi.tags = list(map(fixcase, mi.tags))
        mi.isbn = check_isbn(mi.isbn)
        if mi.series and docase:
            mi.series = fixcase(mi.series)
        if mi.title and mi.series:
            for pat in (r':\s*Book\s+\d+\s+of\s+%s$', r'\(%s\)$', r':\s*%s\s+Book\s+\d+$'):
                pat = pat % re.escape(mi.series)
                q = re.sub(pat, '', mi.title, flags=re.I).strip()
                if q and q != mi.title:
                    mi.title = q
                    break

    def get_website_domain(self, domain):
        return {'uk': 'co.uk', 'jp': 'co.jp', 'br': 'com.br', 'au': 'com.au'}.get(domain, domain)

    def create_query(self, log, title=None, authors=None, identifiers={},  # {{{
                     domain=None, for_amazon=True):
        try:
            from urllib.parse import urlencode, unquote_plus
        except ImportError:
            from urllib import urlencode, unquote_plus
        if domain is None:
            domain = self.domain

        idomain, asin = self.get_domain_and_asin(identifiers)
        if idomain is not None:
            domain = idomain

        # See the amazon detailed search page to get all options
        terms = []
        q = {'search-alias': 'aps',
             'unfiltered': '1',
             }

        if domain == 'com':
            q['sort'] = 'relevanceexprank'
        else:
            q['sort'] = 'relevancerank'

        isbn = check_isbn(identifiers.get('isbn', None))

        if asin is not None:
            q['field-keywords'] = asin
            terms.append(asin)
        elif isbn is not None:
            q['field-isbn'] = isbn
            if len(isbn) == 13:
                terms.extend('({} OR {}-{})'.format(isbn, isbn[:3], isbn[3:]).split())
            else:
                terms.append(isbn)
        else:
            # Only return book results
            q['search-alias'] = {'br': 'digital-text',
                                 'nl': 'aps'}.get(domain, 'stripbooks')
            if title:
                title_tokens = list(self.get_title_tokens(title))
                if title_tokens:
                    q['field-title'] = ' '.join(title_tokens)
                    terms.extend(title_tokens)
            if authors:
                author_tokens = list(self.get_author_tokens(authors,
                                                       only_first_author=True))
                if author_tokens:
                    q['field-author'] = ' '.join(author_tokens)
                    terms.extend(author_tokens)

        if not ('field-keywords' in q or 'field-isbn' in q or
                ('field-title' in q)):
            # Insufficient metadata to make an identify query
            return None, None

        if not for_amazon:
            return terms, domain

        if domain == 'jp':
            # magic parameter to enable Japanese Shift_JIS encoding.
            q['__mk_ja_JP'] = 'カタカナ'
        if domain == 'nl':
            q['__mk_nl_NL'] = 'ÅMÅŽÕÑ'
            if 'field-keywords' not in q:
                q['field-keywords'] = ''
            for f in 'field-isbn field-title field-author'.split():
                q['field-keywords'] += ' ' + q.pop(f, '')
            q['field-keywords'] = q['field-keywords'].strip()

        encode_to = 'Shift_JIS' if domain == 'jp' else 'utf-8'
        encoded_q = dict([(x.encode(encode_to, 'ignore'), y.encode(encode_to,
                                                                'ignore')) for x, y in q.items()])
        url_query = urlencode(encoded_q)
        if encode_to == 'utf-8':
            # amazon's servers want IRIs with unicode characters not percent esaped
            parts = []
            for x in url_query.split(b'&' if isinstance(url_query, bytes) else '&'):
                k, v = x.split(b'=' if isinstance(x, bytes) else '=', 1)
                parts.append('{}={}'.format(iri_quote_plus(unquote_plus(k)), iri_quote_plus(unquote_plus(v))))
            url_query = '&'.join(parts)
        url = 'https://www.amazon.%s/s/?' % self.get_website_domain(
            domain) + url_query
        return url, domain

    # }}}

    def get_cached_cover_url(self, identifiers):  # {{{
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

    def parse_results_page(self, root, domain):  # {{{
        from lxml.html import tostring

        matches = []

        def title_ok(title):
            title = title.lower()
            bad = ['bulk pack', '[audiobook]', '[audio cd]',
                   '(a book companion)', '( slipcase with door )', ': free sampler']
            if self.domain == 'com':
                bad.extend(['(%s edition)' % x for x in ('spanish', 'german')])
            for x in bad:
                if x in title:
                    return False
            if title and title[0] in '[{' and re.search(r'\(\s*author\s*\)', title) is not None:
                # Bad entries in the catalog
                return False
            return True

        for query in (
                '//div[contains(@class, "s-result-list")]//h2/a[@href]',
                '//div[contains(@class, "s-result-list")]//div[@data-index]//h5//a[@href]',
                r'//li[starts-with(@id, "result_")]//a[@href and contains(@class, "s-access-detail-page")]',
        ):
            result_links = root.xpath(query)
            if result_links:
                break
        for a in result_links:
            title = tostring(a, method='text', encoding='unicode')
            if title_ok(title):
                url = a.get('href')
                if url.startswith('/'):
                    url = 'https://www.amazon.%s%s' % (
                        self.get_website_domain(domain), url)
                matches.append(url)

        if not matches:
            # Previous generation of results page markup
            for div in root.xpath(r'//div[starts-with(@id, "result_")]'):
                links = div.xpath(r'descendant::a[@class="title" and @href]')
                if not links:
                    # New amazon markup
                    links = div.xpath('descendant::h3/a[@href]')
                for a in links:
                    title = tostring(a, method='text', encoding='unicode')
                    if title_ok(title):
                        url = a.get('href')
                        if url.startswith('/'):
                            url = 'https://www.amazon.%s%s' % (
                                self.get_website_domain(domain), url)
                        matches.append(url)
                    break

        if not matches:
            # This can happen for some user agents that Amazon thinks are
            # mobile/less capable
            for td in root.xpath(
                    r'//div[@id="Results"]/descendant::td[starts-with(@id, "search:Td:")]'):
                for a in td.xpath(r'descendant::td[@class="dataColumn"]/descendant::a[@href]/span[@class="srTitle"]/..'):
                    title = tostring(a, method='text', encoding='unicode')
                    if title_ok(title):
                        url = a.get('href')
                        if url.startswith('/'):
                            url = 'https://www.amazon.%s%s' % (
                                self.get_website_domain(domain), url)
                        matches.append(url)
                    break
        if not matches and root.xpath('//form[@action="/errors/validateCaptcha"]'):
            raise CaptchaError('Amazon returned a CAPTCHA page. Recently Amazon has begun using statistical'
                               ' profiling to block access to its website. As such this metadata plugin is'
                               ' unlikely to ever work reliably.')

        # Keep only the top 3 matches as the matches are sorted by relevance by
        # Amazon so lower matches are not likely to be very relevant
        return matches[:3]
    # }}}

    def search_amazon(self, br, testing, log, abort, title, authors, identifiers, timeout):  # {{{
        from calibre.utils.cleantext import clean_ascii_chars
        from calibre.ebooks.chardet import xml_to_unicode
        matches = []
        query, domain = self.create_query(log, title=title, authors=authors,
                                          identifiers=identifiers)
        if query is None:
            log.error('Insufficient metadata to construct query')
            raise SearchFailed()
        try:
            raw = br.open_novisit(query, timeout=timeout).read().strip()
        except Exception as e:
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                log.error('Query malformed: %r' % query)
                raise SearchFailed()
            attr = getattr(e, 'args', [None])
            attr = attr if attr else [None]
            if isinstance(attr[0], socket.timeout):
                msg = _('Amazon timed out. Try again later.')
                log.error(msg)
            else:
                msg = 'Failed to make identify query: %r' % query
                log.exception(msg)
            raise SearchFailed()

        raw = clean_ascii_chars(xml_to_unicode(raw,
                                               strip_encoding_pats=True, resolve_entities=True)[0])

        if testing:
            import tempfile
            with tempfile.NamedTemporaryFile(prefix='amazon_results_',
                                             suffix='.html', delete=False) as f:
                f.write(raw.encode('utf-8'))
            print('Downloaded html for results page saved in', f.name)

        matches = []
        found = '<title>404 - ' not in raw

        if found:
            try:
                root = parse_html(raw)
            except Exception:
                msg = 'Failed to parse amazon page for query: %r' % query
                log.exception(msg)
                raise SearchFailed()

        matches = self.parse_results_page(root, domain)

        return matches, query, domain, None
    # }}}

    def search_search_engine(self, br, testing, log, abort, title, authors, identifiers, timeout, override_server=None):  # {{{
        from calibre.ebooks.metadata.sources.update import search_engines_module
        terms, domain = self.create_query(log, title=title, authors=authors,
                                          identifiers=identifiers, for_amazon=False)
        site = self.referrer_for_domain(
            domain)[len('https://'):].partition('/')[0]
        matches = []
        se = search_engines_module()
        server = override_server or self.server
        if server in ('bing',):
            urlproc, sfunc = se.bing_url_processor, se.bing_search
        elif server in ('auto', 'google'):
            urlproc, sfunc = se.google_url_processor, se.google_search
        elif server == 'wayback':
            urlproc, sfunc = se.wayback_url_processor, se.ddg_search
        results, qurl = sfunc(terms, site, log=log, br=br, timeout=timeout)
        br.set_current_header('Referer', qurl)
        for result in results:
            if abort.is_set():
                return matches, terms, domain, None

            purl = urlparse(result.url)
            if '/dp/' in purl.path and site in purl.netloc:
                url = result.cached_url
                if url is None:
                    url = se.wayback_machine_cached_url(
                        result.url, br, timeout=timeout)
                if url is None:
                    log('Failed to find cached page for:', result.url)
                    continue
                if url not in matches:
                    matches.append(url)
                if len(matches) >= 3:
                    break
            else:
                log('Skipping non-book result:', result)
        if not matches:
            log('No search engine results for terms:', ' '.join(terms))
            if urlproc is se.google_url_processor:
                # Google does not cache adult titles
                log('Trying the bing search engine instead')
                return self.search_search_engine(br, testing, log, abort, title, authors, identifiers, timeout, 'bing')
        return matches, terms, domain, urlproc
    # }}}

    def identify(self, log, result_queue, abort, title=None, authors=None,  # {{{
                 identifiers={}, timeout=60):
        '''
        Note this method will retry without identifiers automatically if no
        match is found with identifiers.
        '''

        testing = getattr(self, 'running_a_test', False)

        udata = self._get_book_url(identifiers)
        br = self.browser
        log('User-agent:', br.current_user_agent())
        log('Server:', self.server)
        if testing:
            print('User-agent:', br.current_user_agent())
        if udata is not None and not self.use_search_engine:
            # Try to directly get details page instead of running a search
            # Cannot use search engine as the directly constructed URL is
            # usually redirected to a full URL by amazon, and is therefore
            # not cached
            domain, idtype, asin, durl = udata
            if durl is not None:
                preparsed_root = parse_details_page(
                    durl, log, timeout, br, domain)
                if preparsed_root is not None:
                    qasin = parse_asin(preparsed_root[1], log, durl)
                    if qasin == asin:
                        w = Worker(durl, result_queue, br, log, 0, domain,
                                   self, testing=testing, preparsed_root=preparsed_root, timeout=timeout)
                        try:
                            w.get_details()
                            return
                        except Exception:
                            log.exception(
                                'get_details failed for url: %r' % durl)
        func = self.search_search_engine if self.use_search_engine else self.search_amazon
        try:
            matches, query, domain, cover_url_processor = func(
                br, testing, log, abort, title, authors, identifiers, timeout)
        except SearchFailed:
            return

        if abort.is_set():
            return

        if not matches:
            if identifiers and title and authors:
                log('No matches found with identifiers, retrying using only'
                    ' title and authors. Query: %r' % query)
                time.sleep(1)
                return self.identify(log, result_queue, abort, title=title,
                                     authors=authors, timeout=timeout)
            log.error('No matches found with query: %r' % query)
            return

        workers = [Worker(
            url, result_queue, br, log, i, domain, self, testing=testing, timeout=timeout,
            cover_url_processor=cover_url_processor, filter_result=partial(
                self.filter_result, title, authors, identifiers)) for i, url in enumerate(matches)]

        for w in workers:
            # Don't send all requests at the same time
            time.sleep(1)
            w.start()
            if abort.is_set():
                return

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

    def filter_result(self, title, authors, identifiers, mi, log):  # {{{
        if not self.use_search_engine:
            return True
        if title is not None:
            tokens = {icu_lower(x).rstrip(':') for x in title.split() if len(x) > 3}
            if tokens:
                result_tokens = {icu_lower(x).rstrip(':') for x in mi.title.split()}
                if not tokens.intersection(result_tokens):
                    log('Ignoring result:', mi.title, 'as its title does not match')
                    return False
        if authors:
            author_tokens = set()
            for author in authors:
                author_tokens |= {icu_lower(x) for x in author.split() if len(x) > 2}
            result_tokens = set()
            for author in mi.authors:
                result_tokens |= {icu_lower(x) for x in author.split() if len(x) > 2}
            if author_tokens and not author_tokens.intersection(result_tokens):
                log('Ignoring result:', mi.title, 'by', ' & '.join(mi.authors), 'as its author does not match')
                return False
        return True
    # }}}

    def download_cover(self, log, result_queue, abort,  # {{{
                       title=None, authors=None, identifiers={}, timeout=60, get_best_cover=False):
        cached_url = self.get_cached_cover_url(identifiers)
        if cached_url is None:
            log.info('No cached cover found, running identify')
            rq = Queue()
            self.identify(log, rq, abort, title=title, authors=authors,
                          identifiers=identifiers)
            if abort.is_set():
                return
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
        log('Downloading cover from:', cached_url)
        br = self.browser
        if self.use_search_engine:
            br = br.clone_browser()
            br.set_current_header('Referer', self.referrer_for_domain(self.domain))
        try:
            time.sleep(1)
            cdata = br.open_novisit(
                cached_url, timeout=timeout).read()
            result_queue.put((self, cdata))
        except:
            log.exception('Failed to download cover from:', cached_url)
    # }}}


def manual_tests(domain, **kw):  # {{{
    # To run these test use:
    # calibre-debug -c "from calibre.ebooks.metadata.sources.amazon import *; manual_tests('com')"
    from calibre.ebooks.metadata.sources.test import (test_identify_plugin,
                                                      isbn_test, title_test, authors_test, comments_test, series_test)
    all_tests = {}
    all_tests['com'] = [  # {{{
        (   # Paperback with series
            {'identifiers': {'amazon': '1423146786'}},
            [title_test('The Heroes of Olympus, Book Five The Blood of Olympus',
                        exact=True), series_test('Heroes of Olympus', 5)]
        ),

        (   # Kindle edition with series
            {'identifiers': {'amazon': 'B0085UEQDO'}},
            [title_test('Three Parts Dead', exact=True),
             series_test('Craft Sequence', 1)]
        ),

        (  # + in title and uses id="main-image" for cover
            {'identifiers': {'amazon': '1933988770'}},
            [title_test(
                'C++ Concurrency in Action: Practical Multithreading', exact=True)]
        ),


        (  # Different comments markup, using Book Description section
            {'identifiers': {'amazon': '0982514506'}},
            [title_test(
                "Griffin's Destiny: Book Three: The Griffin's Daughter Trilogy",
                exact=True),
             comments_test('Jelena'), comments_test('Ashinji'),
             ]
        ),

        (  # # in title
            {'title': 'Expert C# 2008 Business Objects',
             'authors': ['Lhotka']},
            [title_test('Expert C#'),
             authors_test(['Rockford Lhotka'])
             ]
        ),

        (  # No specific problems
            {'identifiers': {'isbn': '0743273567'}},
            [title_test('The great gatsby', exact=True),
             authors_test(['F. Scott Fitzgerald'])]
        ),

    ]

    # }}}

    all_tests['de'] = [  # {{{
        (  # umlaut in title/authors
            {'title': 'Flüsternde Wälder',
             'authors': ['Nicola Förg']},
            [title_test('Flüsternde Wälder'),
             authors_test(['Nicola Förg'])
             ]
        ),


        (
            {'identifiers': {'isbn': '9783453314979'}},
            [title_test('Die letzten Wächter: Roman',
                        exact=False), authors_test(['Sergej Lukianenko'])
             ]

        ),

        (
            {'identifiers': {'isbn': '3548283519'}},
            [title_test('Wer Wind Sät: Der Fünfte Fall Für Bodenstein Und Kirchhoff',
                        exact=False), authors_test(['Nele Neuhaus'])
             ]

        ),
    ]  # }}}

    all_tests['it'] = [  # {{{
        (
            {'identifiers': {'isbn': '8838922195'}},
            [title_test('La briscola in cinque',
                        exact=True), authors_test(['Marco Malvaldi'])
             ]

        ),
    ]  # }}}

    all_tests['fr'] = [  # {{{
        (
            {'identifiers': {'amazon_fr': 'B07L7ST4RS'}},
            [title_test('Le secret de Lola', exact=True),
                authors_test(['Amélie BRIZIO'])
            ]
        ),
        (
            {'identifiers': {'isbn': '2221116798'}},
            [title_test('L\'étrange voyage de Monsieur Daldry',
                        exact=True), authors_test(['Marc Levy'])
             ]

        ),
    ]  # }}}

    all_tests['es'] = [  # {{{
        (
            {'identifiers': {'isbn': '8483460831'}},
            [title_test('Tiempos Interesantes',
                        exact=False), authors_test(['Terry Pratchett'])
             ]

        ),
    ]  # }}}

    all_tests['jp'] = [  # {{{
        (  # Adult filtering test
            {'identifiers': {'isbn': '4799500066'}},
            [title_test('Ｂｉｔｃｈ Ｔｒａｐ'), ]
        ),

        (  # isbn -> title, authors
            {'identifiers': {'isbn': '9784101302720'}},
            [title_test('精霊の守り人',
                        exact=True), authors_test(['上橋 菜穂子'])
             ]
        ),
        (  # title, authors -> isbn (will use Shift_JIS encoding in query.)
            {'title': '考えない練習',
             'authors': ['小池 龍之介']},
            [isbn_test('9784093881067'), ]
        ),
    ]  # }}}

    all_tests['br'] = [  # {{{
        (
            {'title': 'Guerra dos Tronos'},
            [title_test('A Guerra dos Tronos - As Crônicas de Gelo e Fogo',
                        exact=True), authors_test(['George R. R. Martin'])
             ]

        ),
    ]  # }}}

    all_tests['nl'] = [  # {{{
        (
            {'title': 'Freakonomics'},
            [title_test('Freakonomics',
                        exact=True), authors_test(['Steven Levitt & Stephen Dubner & R. Kuitenbrouwer & O. Brenninkmeijer & A. van Den Berg'])
             ]

        ),
    ]  # }}}

    all_tests['cn'] = [  # {{{
        (
            {'identifiers': {'isbn': '9787115369512'}},
            [title_test('若为自由故 自由软件之父理查德斯托曼传', exact=True),
             authors_test(['[美]sam Williams', '邓楠，李凡希'])]
        ),
        (
            {'title': '爱上Raspberry Pi'},
            [title_test('爱上Raspberry Pi',
                        exact=True), authors_test(['Matt Richardson', 'Shawn Wallace', '李凡希'])
             ]

        ),
    ]  # }}}

    all_tests['ca'] = [  # {{{
        (   # Paperback with series
            {'identifiers': {'isbn': '9781623808747'}},
            [title_test('Parting Shot', exact=True),
             authors_test(['Mary Calmes'])]
        ),
        (  # # in title
            {'title': 'Expert C# 2008 Business Objects',
             'authors': ['Lhotka']},
            [title_test('Expert C# 2008 Business Objects'),
             authors_test(['Rockford Lhotka'])]
        ),
        (  # noscript description
            {'identifiers': {'amazon_ca': '162380874X'}},
            [title_test('Parting Shot', exact=True), authors_test(['Mary Calmes'])
             ]
        ),
    ]  # }}}

    def do_test(domain, start=0, stop=None, server='auto'):
        tests = all_tests[domain]
        if stop is None:
            stop = len(tests)
        tests = tests[start:stop]
        test_identify_plugin(Amazon.name, tests, modify_plugin=lambda p: (
            setattr(p, 'testing_domain', domain),
            setattr(p, 'touched_fields', p.touched_fields - {'tags'}),
            setattr(p, 'testing_server', server),
        ))

    do_test(domain, **kw)
# }}}
