#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import asyncio
import functools
import http.server
import json
import os
import socketserver
import tempfile
import threading
import unittest
from collections import Counter
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request

from calibre.utils.avif_test import STILL_AVIF
from calibre.web.automate import browser as browser_module
from calibre.web.automate import recipes
from calibre.web.automate.bot_check import retry_bot_checks
from calibre.web.automate.browser import Warmup
from calibre.web.automate.test_camoufox import installed_camoufox

ARTICLE_PAGE = '''<!DOCTYPE html><html><head><title>An Article</title>
<link rel="stylesheet" type="text/css" href="style.css">
</head><body>
<h1 id="headline">The Headline</h1>
<p class="body">Some words.</p>
<img id="pic" src="pic.svg" alt="a picture">
<img id="avif-pic" src="pic.avif" alt="a picture in a format only a browser fetches">
<script>
document.addEventListener('DOMContentLoaded', () => {
    const d = document.createElement('div');
    d.id = 'added-by-script'; d.textContent = 'only a browser sees this';
    document.body.appendChild(d);
});
</script>
</body></html>'''

TEST_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8" fill="red"/></svg>'''
TEST_CSS = '''#headline { color: red; }'''
# A feed, which is XML the browser does not render as a document
TEST_FEED = '''<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>A Feed</title>
<item><title>An Article</title><link>article.html</link></item></channel></rss>'''
# The validator of the one page that is served with caching headers, so that
# loading it a second time is answered with a 304 rather than with the page
CACHEABLE_ETAG = '"a-headline"'
CACHEABLE_PATH = '/cacheable.html'
# A page that declares, and is served as, an encoding that is not utf-8
LATIN1_PAGE = '''<!DOCTYPE html><html><head><meta charset="iso-8859-1"><title>Caf\xe9</title></head>
<body><p id="word">na\xefve caf\xe9</p></body></html>'''


class Server:
    """Serves the test pages over HTTP and counts what is asked for."""

    def __init__(self) -> None:
        self.dir = tempfile.mkdtemp(prefix='camoufox-recipes-test-')
        for name, data in (
            ('article.html', ARTICLE_PAGE.encode('utf-8')),
            ('pic.svg', TEST_SVG.encode('utf-8')),
            # A format the browser only ever asks for when its own Accept
            # header for images is left alone
            ('pic.avif', STILL_AVIF),
            ('style.css', TEST_CSS.encode('utf-8')),
            ('latin1.html', LATIN1_PAGE.encode('iso-8859-1')),
        ):
            with open(os.path.join(self.dir, name), 'wb') as f:
                f.write(data)
        self.requests: Counter[str] = Counter()
        self.lock = threading.Lock()
        server = self

        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a: object) -> None:
                pass

            def end_headers(self) -> None:
                # The tests share a browser, so without this a page one of them
                # loads is served to the next one out of the cache and the
                # request counts stop meaning anything. The one page that is
                # about revalidation sends caching headers of its own instead.
                if self.path.partition('?')[0] != CACHEABLE_PATH:
                    self.send_header('Cache-Control', 'no-store')
                super().end_headers()

            def count(self) -> str:
                path = self.path.partition('?')[0]
                with server.lock:
                    server.requests[path] += 1
                return path

            def reply(self, code: int, content_type: str, body: bytes) -> None:
                self.send_response(code)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                match self.count():
                    case '/accept-probe.svg':
                        # Reports back the Accept header the browser asked for
                        # images with, which decides what format it is served
                        accept = self.headers.get('Accept') or ''
                        body = f'<svg xmlns="http://www.w3.org/2000/svg"><desc>{accept}</desc></svg>'
                        self.reply(200, 'image/svg+xml', body.encode())
                    case '/pic.avif':
                        # mimetypes does not know this one on every platform
                        self.reply(200, 'image/avif', STILL_AVIF)
                    case '/api.json':
                        self.reply(200, 'application/json', json.dumps({'articles': ['one', 'two']}).encode())
                    case '/feed.xml':
                        self.reply(200, 'application/xml', TEST_FEED.encode())
                    case _ if self.path.partition('?')[0] == CACHEABLE_PATH:
                        if self.headers.get('If-None-Match') == CACHEABLE_ETAG:
                            self.send_response(304)
                            self.send_header('ETag', CACHEABLE_ETAG)
                            self.send_header('Cache-Control', 'no-cache')
                            self.end_headers()
                            return
                        body = ARTICLE_PAGE.encode('utf-8')
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/html')
                        self.send_header('Content-Length', str(len(body)))
                        self.send_header('ETag', CACHEABLE_ETAG)
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        self.wfile.write(body)
                    case '/missing':
                        self.reply(404, 'text/html', b'<html><body>no such thing</body></html>')
                    case '/busy':
                        self.reply(503, 'text/html', b'<html><body>come back later</body></html>')
                    case '/redirect':
                        self.send_response(302)
                        self.send_header('Location', '/article.html')
                        self.end_headers()
                    case '/latin1.html':
                        with open(os.path.join(server.dir, 'latin1.html'), 'rb') as f:
                            self.reply(200, 'text/html; charset=iso-8859-1', f.read())
                    case _:
                        super().do_GET()

            def do_POST(self) -> None:
                self.count()
                body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
                payload = {'body': body.decode('utf-8', 'replace'), 'header': self.headers.get('X-Recipe-Test') or ''}
                self.reply(200, 'application/json', json.dumps(payload).encode())

        self.httpd = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Handler, directory=self.dir))
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, name='CamoufoxRecipeTestServer', daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.httpd.server_address[1]}/'

    def count_for(self, path: str) -> int:
        with self.lock:
            return self.requests[path]

    def reset_counts(self) -> None:
        with self.lock:
            self.requests.clear()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=10)
        import shutil

        shutil.rmtree(self.dir, ignore_errors=True)


class FakeBrowser:
    """The little of a browser that retry_bot_checks() touches."""

    def __init__(self, statuses: list[int | None]) -> None:
        # What each successive request fails with, None meaning it succeeds
        self.statuses = list(statuses)
        self.attempts = 0
        self.clones: list[FakeBrowser] = []

    def open(self, url: str) -> str:
        self.attempts += 1
        status = self.statuses.pop(0) if self.statuses else None
        if status is None:
            return f'the page at {url}'
        err = URLError(f'HTTP {status}')
        setattr(err, 'code', status)
        raise err

    open_novisit = open

    def clone_browser(self) -> FakeBrowser:
        # A real browser hands back one of its own class, knowing nothing of
        # any wrapping done to the instance it was cloned from
        ans = FakeBrowser(self.statuses)
        self.clones.append(ans)
        return ans


class TestRecipeBotCheck(unittest.TestCase):
    """Retrying the interstitial a bot check answers a request with."""

    def test_recipes_bot_check_retried(self) -> None:
        "A request the bot check answers with an interstitial is made again"
        br = retry_bot_checks(FakeBrowser([403, 403]), delay=0)
        self.assertEqual(br.open('u'), 'the page at u')
        self.assertEqual(br.attempts, 3)

    def test_recipes_bot_check_other_errors(self) -> None:
        "An error that is not a bot check is not retried, and neither is the last one"
        br = retry_bot_checks(FakeBrowser([404]), delay=0)
        with self.assertRaises(URLError) as ctx:
            br.open('u')
        self.assertEqual(getattr(ctx.exception, 'code', None), 404)
        self.assertEqual(br.attempts, 1, 'a 404 was retried')

        br = retry_bot_checks(FakeBrowser([403] * 10), retries=3, delay=0)
        with self.assertRaises(URLError) as ctx:
            br.open('u')
        self.assertEqual(getattr(ctx.exception, 'code', None), 403, 'the last failure was not handed back as it stood')
        self.assertEqual(br.attempts, 3)

    def test_recipes_bot_check_survives_cloning(self) -> None:
        "Clones retry too, which is what the download threads rely on"
        br = retry_bot_checks(FakeBrowser([]), delay=0)
        clone = br.clone_browser()
        clone.statuses = [403]
        self.assertEqual(clone.open_novisit('u'), 'the page at u')
        self.assertEqual(clone.attempts, 2)
        # Recipes clone per article, and a tab limit can make a clone of a clone
        grandchild = clone.clone_browser()
        grandchild.statuses = [429]
        self.assertEqual(grandchild.open('u'), 'the page at u')
        self.assertEqual(grandchild.attempts, 2)

    def test_recipes_bot_check_is_idempotent(self) -> None:
        "Wrapping a browser that is already wrapped leaves it alone"
        br = retry_bot_checks(FakeBrowser([403]), delay=0)
        opener = br.open
        self.assertIs(retry_bot_checks(br, delay=0), br)
        self.assertIs(br.open, opener, 'the browser was wrapped a second time')
        self.assertEqual(br.open('u'), 'the page at u')
        self.assertEqual(br.attempts, 2, 'the request was retried twice over')


class TestRecipeWarmupUrls(unittest.TestCase):
    """The choice of sites to warm up on, which needs no browser."""

    # The selection is random, so one draw of it proves little: a bad draw
    # happens only every few runs, which on CI means an occasional failure
    # rather than a reproducible one
    num_draws = 64

    def test_recipes_warmup_urls(self) -> None:
        for _ in range(self.num_draws):
            w = Warmup(min_num=2, max_num=3)
            self.assertGreaterEqual(len(w.urls), 2)
            self.assertLessEqual(len(w.urls), 3)
            self.assertEqual(len(set(w.urls)), len(w.urls), f'the same site was warmed up on twice: {w.urls}')

            w = Warmup('https://example.com/forced', min_num=1, max_num=1)
            self.assertIn('https://example.com/forced', w.urls)
            self.assertEqual(len(w.urls), 2)

            # Asking for more sites than there are gets all of them, and the
            # sites that contribute several pages must contribute a different
            # page each time
            pages_per_host = Counter(urlparse(u).hostname for u in Warmup(min_num=99, max_num=99).urls)
            for host in ('www.foxnews.com', 'www.bbc.com', 'en.wikipedia.org', 'www.reddit.com'):
                self.assertEqual(pages_per_host[host], 2, f'{host} was warmed up on with the same page twice')

            # A forced URL that is also one of the built-in sites is visited once
            w = Warmup('https://x.com', min_num=10, max_num=10)
            self.assertEqual(w.urls.count('https://x.com'), 1, f'a forced URL was warmed up on twice: {w.urls}')
            self.assertEqual(len(set(w.urls)), len(w.urls), f'the same site was warmed up on twice: {w.urls}')

            # The site about to be downloaded from must not be part of the warmup
            w = Warmup(min_num=3, max_num=3, excluded_domains=('bbc.com', 'reddit.com'))
            for url in w.urls:
                self.assertNotIn('bbc.com', url)
                self.assertNotIn('reddit.com', url)

            # Excluding everything must not ask for more sites than are left
            every_domain = ('amazon.com', 'x.com', 'youtube.com', 'foxnews.com', 'bbc.com', 'wikipedia.org', 'reddit.com')
            self.assertEqual(Warmup(min_num=3, max_num=3, excluded_domains=every_domain).urls, ())


@unittest.skipIf(installed_camoufox() is None, 'the camoufox browser is not installed')
class TestRecipeBrowser(unittest.TestCase):
    """Tests that drive the real browser. Skipped unless it is already installed."""

    server: Server
    browser: recipes.Browser | None

    # Every one of these needs a browser, which is slow to start and heavy to
    # run, so the parallel test runner keeps them to a few of its workers
    max_parallel_workers = 4

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = Server()
        # One browser for all of them, started on first use. Warming up visits
        # real web sites, which a test must not do.
        cls.browser = None

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            if (browser := cls.browser) is not None:
                cls.browser = None
                browser.shutdown()
        finally:
            cls.server.close()

    @classmethod
    def shared_browser(cls) -> recipes.Browser:
        if cls.browser is None:
            cls.browser = recipes.Browser(warmup=False, max_tabs=6)
        return cls.browser

    def setUp(self) -> None:
        self.server.reset_counts()

    def test_recipes_document(self) -> None:
        "A document is navigated to, so its scripts have run by the time we see it"
        br = self.shared_browser().clone_browser()
        with br.open(self.server.base + 'article.html') as response:
            raw = response.read()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.geturl(), self.server.base + 'article.html')
            self.assertEqual(response.headers.get_content_type(), 'text/html')
            self.assertEqual(response.headers.get_content_charset(), 'utf-8')
        html = raw.decode('utf-8')
        self.assertIn('The Headline', html)
        self.assertIn('added-by-script', html, 'the page was fetched rather than rendered')
        br.release()

    def test_recipes_resources_come_from_the_tab(self) -> None:
        "The parts of an article are taken from the tab that rendered it, not downloaded again"
        br = self.shared_browser().clone_browser()
        br.open(self.server.base + 'article.html').close()
        self.assertGreaterEqual(self.server.count_for('/pic.svg'), 1, 'the page did not load its own image')
        # How many times the page itself asked for each of these is the
        # browser's business, what matters is that asking for them again costs
        # nothing
        after_load = {path: self.server.count_for(path) for path in ('/pic.svg', '/style.css')}

        with br.open_novisit(self.server.base + 'pic.svg') as response:
            self.assertEqual(response.read().decode('utf-8'), TEST_SVG)
            self.assertEqual(response.headers.get_content_type(), 'image/svg+xml')
        with br.open_novisit(self.server.base + 'style.css') as response:
            self.assertEqual(response.read().decode('utf-8'), TEST_CSS)
        for path, before in after_load.items():
            self.assertEqual(self.server.count_for(path), before, f'{path} was downloaded again instead of coming from the tab')
        br.release()

    def test_recipes_resource_the_page_did_not_load(self) -> None:
        "A resource the page never asked for is fetched from within it"
        br = self.shared_browser().clone_browser()
        br.open(self.server.base + 'article.html').close()
        # What a recipe's image_url_processor, or a srcset the browser did not
        # pick from, produces: a URL of the site that is not in the document
        with br.open_novisit(self.server.base + 'pic.svg?variant=large') as response:
            self.assertEqual(response.read().decode('utf-8'), TEST_SVG)
        self.assertEqual(self.server.count_for('/pic.svg'), 2)
        br.release()

    def test_recipes_cross_origin_resource(self) -> None:
        "An image on another server, which CORS forbids fetching, still comes back"
        br = self.shared_browser().clone_browser()
        br.open(self.server.base + 'article.html').close()
        # Same server, but localhost and 127.0.0.1 are different origins as far
        # as the browser is concerned, which is the situation every news site
        # with a separate image host puts us in. A fetch() from the page would
        # be refused, since the server sends no CORS headers.
        cross_origin = self.server.base.replace('127.0.0.1', 'localhost') + 'pic.svg'
        with br.open_novisit(cross_origin) as response:
            self.assertEqual(response.read().decode('utf-8'), TEST_SVG)
        br.release()

    def test_recipes_image_accept_header(self) -> None:
        "The browser's own Accept header for images is left alone"
        br = self.shared_browser().clone_browser()
        br.open(self.server.base + 'article.html').close()
        with br.open_novisit(self.server.base + 'accept-probe.svg') as response:
            accept = response.read().decode('utf-8').partition('<desc>')[2].partition('</desc>')[0]
        # calibre reads AVIF, via the image format plugin in
        # calibre.utils.avif, so there is no reason to talk the sites that
        # serve it out of doing so: asking for anything less than what the
        # browser asks for by itself is one more thing to tell us apart by
        self.assertIn('image/avif', accept)
        br.release()

    def test_recipes_first_request_is_a_document(self) -> None:
        "open_novisit on a fresh browser renders, since there is no page for it to be part of"
        br = self.shared_browser().clone_browser()
        with br.open_novisit(self.server.base + 'article.html') as response:
            self.assertIn('added-by-script', response.read().decode('utf-8'))
        br.release()

    def test_recipes_non_html_is_not_rendered(self) -> None:
        "JSON comes back as the bytes the server sent, not as the browser's viewer for it"
        br = self.shared_browser().clone_browser()
        with br.open(self.server.base + 'api.json') as response:
            self.assertEqual(json.loads(response.read()), {'articles': ['one', 'two']})
        br.release()

    def test_recipes_non_html_leaves_no_document_behind(self) -> None:
        "After the tab loads a feed, the next thing asked for is navigated to rather than taken out of it"
        br = self.shared_browser().clone_browser()
        with br.open(self.server.base + 'feed.xml') as response:
            self.assertIn(b'<rss', response.read())
        # A bare XML document has no sub-resources to take anything out of and
        # cannot host the <img> that asking for one would use, so the session
        # must not be left thinking it is working on a document
        with br.open_novisit(self.server.base + 'article.html') as response:
            self.assertIn('added-by-script', response.read().decode('utf-8'))
        br.release()

    def test_recipes_not_modified(self) -> None:
        "A navigation the browser satisfies out of its own cache is a success, not a 304 failure"
        br = self.shared_browser().clone_browser()
        for _ in range(2):
            # The second time round the browser revalidates and is told to use
            # the copy it has, which is what a recipe retrying a request the
            # site answered with a bot check runs into
            with br.open(self.server.base + CACHEABLE_PATH.lstrip('/')) as response:
                self.assertEqual(response.status, 200)
                self.assertIn('The Headline', response.read().decode('utf-8'))
        self.assertEqual(self.server.count_for(CACHEABLE_PATH), 2, 'the page was not revalidated, so nothing was tested')
        br.release()

    def test_recipes_redirect(self) -> None:
        "The URL a redirect lands on is what is reported back"
        br = self.shared_browser().clone_browser()
        with br.open(self.server.base + 'redirect') as response:
            self.assertEqual(response.geturl(), self.server.base + 'article.html')
            self.assertIn('The Headline', response.read().decode('utf-8'))
        br.release()

    def test_recipes_encoding(self) -> None:
        "A page in another encoding is re-encoded and says so, so it can be decoded again"
        from calibre.ebooks.chardet import xml_to_unicode

        br = self.shared_browser().clone_browser()
        with br.open(self.server.base + 'latin1.html') as response:
            raw = response.read()
        self.assertIn('na\xefve caf\xe9'.encode(), raw, 'the page was not re-encoded as utf-8')
        self.assertNotIn(b'iso-8859-1', raw.lower(), 'the stale encoding declaration was left in place')
        # This is how RecursiveFetcher decodes what it is given
        self.assertIn('na\xefve caf\xe9', xml_to_unicode(raw)[0])
        br.release()

    def test_recipes_http_errors(self) -> None:
        "Failures are reported the way RecursiveFetcher expects them"
        br = self.shared_browser().clone_browser()
        with self.assertRaises(URLError) as ctx:
            br.open(self.server.base + 'missing')
        self.assertEqual(getattr(ctx.exception, 'code', None), 404)
        self.assertFalse(getattr(ctx.exception, 'worth_retry', False), 'a 404 is not worth retrying')

        with self.assertRaises(URLError) as ctx:
            br.open(self.server.base + 'busy')
        self.assertEqual(getattr(ctx.exception, 'code', None), 503)
        self.assertTrue(getattr(ctx.exception, 'worth_retry', False), 'a 503 is worth retrying')
        br.release()

    def test_recipes_post(self) -> None:
        "A POST, with headers of its own, goes through the page's own fetch()"
        br = self.shared_browser().clone_browser()
        br.open(self.server.base + 'article.html').close()
        request = Request(self.server.base + 'echo', data=b'hello=world', headers={'X-Recipe-Test': 'yes'})
        with br.open(request) as response:
            self.assertEqual(json.loads(response.read()), {'body': 'hello=world', 'header': 'yes'})
        br.release()

    def test_recipes_parallel_downloads(self) -> None:
        "Every download thread gets a tab of its own and they run at the same time"
        shared = self.shared_browser()
        num = 5
        results: dict[int, object] = {}
        started = threading.Barrier(num, timeout=120)

        def download(i: int) -> None:
            try:
                br = shared.clone_browser()
                started.wait()
                with br.open(self.server.base + 'article.html') as response:
                    html = response.read().decode('utf-8')
                with br.open_novisit(self.server.base + 'pic.svg') as image:
                    svg = image.read().decode('utf-8')
                results[i] = ('added-by-script' in html, svg)
                br.release()
            except Exception as err:
                results[i] = err

        threads = [threading.Thread(target=download, args=(i,), name=f'RecipeDownload{i}') for i in range(num)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=180)
            self.assertFalse(t.is_alive(), 'a download thread never finished')
        self.assertEqual(len(results), num)
        for i, result in sorted(results.items()):
            if isinstance(result, Exception):
                raise AssertionError(f'download {i} failed: {result}') from result
            rendered, svg = result
            self.assertTrue(rendered, f'download {i} was not rendered')
            self.assertEqual(svg, TEST_SVG, f'download {i} got the wrong image')
        # One page load per thread, and each thread's image came from its own tab
        self.assertEqual(self.server.count_for('/article.html'), num)
        self.assertEqual(self.server.count_for('/pic.svg'), num)

    def test_recipes_tab_limit(self) -> None:
        "More sessions than tabs still works, the idle ones are closed and put back"
        br = recipes.Browser(warmup=False, max_tabs=2)
        try:
            clones = [br.clone_browser() for _ in range(4)]
            for clone in clones:
                with clone.open(self.server.base + 'article.html') as response:
                    self.assertIn('added-by-script', response.read().decode('utf-8'))
            # The first clones will have had their tabs taken away by the last
            # ones, so this makes them ask for something out of a tab that is
            # no longer there
            for clone in clones:
                with clone.open_novisit(self.server.base + 'pic.svg') as response:
                    self.assertEqual(response.read().decode('utf-8'), TEST_SVG)
            for clone in clones:
                clone.release()
        finally:
            br.shutdown()

    def test_recipes_warmup_visits(self) -> None:
        "Warming up actually loads the sites it was given"
        urls = (self.server.base + 'article.html', self.server.base + 'latin1.html')
        warmup = Warmup(*urls, min_num=0, max_num=0)
        self.assertEqual(warmup.urls, urls)

        async def main() -> None:
            browser = browser_module.Browser(headless=True, warmup=warmup)
            try:
                await browser.launch()
            finally:
                await browser.close()

        # A visit dwells on the page for a few seconds so that it looks like
        # someone reading it, which is several times the cost of everything
        # else in this file put together. The pauses are of a length chosen to
        # fool a web site rather than one that scales with anything, so they
        # are shortened here: what this checks is that the sites are visited,
        # not how long a reader lingers on them.
        with patch.object(browser_module, 'MIN_DWELL_TIME', 0.0), patch.object(browser_module, 'MAX_DWELL_TIME', 0.01):
            asyncio.run(main())
        self.assertEqual(self.server.count_for('/article.html'), 1)
        self.assertEqual(self.server.count_for('/latin1.html'), 1)


def find_tests() -> unittest.TestSuite:
    ans = unittest.TestSuite()
    for cls in (TestRecipeBotCheck, TestRecipeWarmupUrls, TestRecipeBrowser):
        ans.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    return ans


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(find_tests())
