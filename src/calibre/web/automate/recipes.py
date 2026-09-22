#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""
Fetch news for calibre recipes using the Camoufox browser.

Recipes download articles on a pool of threads, so this module is split in two
halves. The client half runs in the process the recipe runs in and presents
:class:`Browser`, which looks enough like a mechanize browser to be used as
``BasicNewsRecipe.browser``. The server half runs in a worker process, where a
single Camoufox instance is launched, warmed up by visiting a few commonly
browsed sites, and then driven by an asyncio event loop. The two halves talk
over the socket based protocol in :mod:`calibre.web.automate.worker`, which
blocks the calling thread for the duration of a request and handles any number
of them at once, which is exactly the shape the recipe thread pool needs.

Each :meth:`Browser.clone_browser` gets a *session*, and each session gets a
tab of its own in the browser. Since a recipe clones its browser once per
article being downloaded, an article and all of its images are handled by one
tab. That matters because the images of an article have, by the time the
recipe asks for them, already been loaded by the tab that rendered the article,
so they are served out of the browser's own record of the responses without
being fetched a second time.
"""

import asyncio
import atexit
import base64
import secrets
import time
import weakref
from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import suppress
from http import HTTPStatus
from io import BytesIO
from threading import RLock
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request

from calibre.web.automate.camoufox import DEFAULT_TIMEOUT, Error, Page, TimeoutExceeded, debug, remove_profile_dir
from calibre.web.automate.worker import make_request, start_worker

# The recipe thread pool defaults to five threads and a tab costs real memory,
# so the pool of them is kept to a size that a download actually uses
DEFAULT_MAX_TABS = 5
# How long to go on waiting for the DOM of a page whose load event never
# arrived, usually because some tracker or advert is still spinning
DOM_READY_GRACE = 10.0  # seconds
# Statuses that mean the server was busy rather than that the URL is wrong, so
# that RecursiveFetcher knows to try once more
RETRY_STATUSES = frozenset({
    HTTPStatus.REQUEST_TIMEOUT,
    HTTPStatus.TOO_MANY_REQUESTS,
    HTTPStatus.INTERNAL_SERVER_ERROR,
    HTTPStatus.BAD_GATEWAY,
    HTTPStatus.SERVICE_UNAVAILABLE,
    HTTPStatus.GATEWAY_TIMEOUT,
})
# Only these are handed back as rendered markup. Anything else, JSON in
# particular, which a recipe reading an API expects to get verbatim, is handed
# back as the bytes the server sent, since what the browser renders for it is a
# viewer of its own making rather than the content
RENDERED_CONTENT_TYPES = frozenset({'text/html', 'application/xhtml+xml'})

WORKER_MODULE = 'calibre.web.automate.recipes'

BROWSER_PREFS = {
    # Without this a navigation to a JSON document renders the browser's own
    # JSON viewer, whose markup is not what a recipe reading an API asked for
    'devtools.jsonview.enabled': False,
    # Left to itself the browser asks for, and news sites happily serve, AVIF,
    # which calibre cannot decode, so the images would all be thrown away
    # further down the conversion pipeline. This is what Firefox itself sent
    # before it gained AVIF support, so it is not a header a site has never
    # seen, and webp is both smaller than jpeg and readable by calibre.
    'image.http.accept': 'image/webp,*/*',
}


def content_type_of(headers: Iterable[tuple[str, str]]) -> str:
    for name, value in headers:
        if name.lower() == 'content-type':
            return value.partition(';')[0].strip().lower()
    return ''


# Server side, runs in the worker process {{{

# Serializing the document after making it declare the encoding it is about to
# be encoded in. The page's own declaration describes the bytes the server
# sent, which are not the bytes produced here, and RecursiveFetcher decodes
# what it is given by looking for exactly such a declaration.
DOCUMENT_HTML_JS = '''() => {
    const head = document.head || document.documentElement;
    for (const m of Array.from(document.querySelectorAll('meta[charset], meta[http-equiv="Content-Type" i]')))
        m.remove();
    const meta = document.createElement('meta');
    meta.setAttribute('charset', 'utf-8');
    head.insertBefore(meta, head.firstChild);
    return document.documentElement.outerHTML;
}'''

# Making the page load a resource it did not ask for, by putting an image that
# points at it into the document. A cross origin fetch() from the page is
# refused unless the other server opts in with CORS headers, which the image
# servers news sites use do not, but an <img> is an ordinary sub-resource load:
# nothing blocks it, and it carries the document's cookies and referrer, which
# is what hotlink protection looks at. The bytes are then taken out of the
# browser's own record of the response, which CORS has no say over.
LOAD_IMAGE_JS = '''async (url, timeout) => {
    const parent = document.body || document.documentElement;
    const img = document.createElement('img');
    img.style.cssText = 'position:absolute;left:-10000px;top:0;width:1px;height:1px;opacity:0';
    let timer = 0;
    const loaded = new Promise((resolve) => {
        const finish = (ok) => { clearTimeout(timer); img.remove(); resolve(ok); };
        timer = setTimeout(() => finish(false), timeout);
        img.onload = () => finish(true);
        img.onerror = () => finish(false);
    });
    img.src = url;
    parent.appendChild(img);
    return await loaded;
}'''

# Fetching from inside the page, so that the request carries the cookies, the
# referrer and the origin of the document the recipe is working on. Used for
# POSTs and for requests with headers of their own.
PAGE_FETCH_JS = '''async (url, method, headers, body, timeout) => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
        const init = {method: method, credentials: 'include', redirect: 'follow', signal: controller.signal};
        if (headers.length) init.headers = Object.fromEntries(headers);
        if (body) {
            const binary = atob(body);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
            init.body = bytes;
        }
        const response = await fetch(url, init);
        const blob = await response.blob();
        const dataURL = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(reader.error);
            reader.readAsDataURL(blob);
        });
        const headerList = [];
        response.headers.forEach((value, name) => headerList.push([name, value]));
        return {
            status: response.status, statusText: response.statusText, url: response.url,
            headers: headerList, base64: dataURL.slice(dataURL.indexOf(',') + 1),
        };
    } catch (err) {
        return {error: '' + err};
    } finally {
        clearTimeout(timer);
    }
}'''


class Session:
    """One recipe side browser clone, and the tab that serves it."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.page: Page | None = None
        # A tab can only be doing one thing at a time, so requests that arrive
        # for a session while it is busy queue up here
        self.lock = asyncio.Lock()
        self.last_used = time.monotonic()
        # The document this session last navigated to. Kept so that a tab
        # evicted to stay under the tab limit can be put back the way it was
        # if the session turns out not to be finished with it.
        self.document_url = ''

    @property
    def busy(self) -> bool:
        return self.lock.locked()

    async def close(self) -> None:
        page, self.page = self.page, None
        if page is not None:
            with suppress(Error):
                await page.close()


class State:
    """Everything the worker process owns, created once on first request."""

    def __init__(self, browser: Any, max_tabs: int) -> None:  # noqa: ANN401
        self.browser = browser
        self.max_tabs = max(1, max_tabs)
        self.sessions: OrderedDict[str, Session] = OrderedDict()
        # Held only while tabs are being created or closed, never while one is
        # being used, so it does not serialize the downloads themselves
        self.tab_lock = asyncio.Lock()
        self.applied_headers: tuple[tuple[str, str], ...] = ()

    async def session_for(self, session_id: str) -> Session:
        async with self.tab_lock:
            session = self.sessions.get(session_id)
            if session is None:
                session = self.sessions[session_id] = Session(session_id)
            self.sessions.move_to_end(session_id)
            session.last_used = time.monotonic()
            return session

    async def release(self, session_id: str) -> None:
        async with self.tab_lock:
            session = self.sessions.pop(session_id, None)
        if session is not None:
            await session.close()

    async def evict_idle_tabs(self, keep: Session) -> None:
        """Close the least recently used idle tabs until we are under the limit.

        A session whose tab is closed is not forgotten, only emptied, so that
        it can be restored if it is used again. If every session is busy the
        limit is exceeded rather than deadlocking on one of them.
        """
        async with self.tab_lock:
            live = [s for s in self.sessions.values() if s.page is not None]
            for session in live:
                if len(live) <= self.max_tabs:
                    break
                if session is keep or session.busy:
                    continue
                debug(f'Closing the idle camoufox tab of session {session.session_id} to stay within {self.max_tabs} tabs')
                await session.close()
                live.remove(session)

    async def page_for(self, session: Session, timeout: float) -> Page:
        """The session's tab, created, or put back, if it does not have one."""
        if session.page is not None and not session.page.closed:
            return session.page
        await self.evict_idle_tabs(session)
        session.page = await self.browser.new_page(timeout=timeout)
        if session.document_url:
            # The tab was evicted while the session was still working on a
            # document, and what it asks for next will be a part of that
            # document, which has to be loaded for its origin and cookies to
            # apply
            debug(f'Reloading {session.document_url} to restore the tab of session {session.session_id}')
            with suppress(Error):
                await session.page.open(session.document_url, wait='load', timeout=timeout)
        return session.page

    async def apply_headers(self, headers: Sequence[tuple[str, str]]) -> None:
        """Extra headers are a property of the whole browser rather than of an
        individual request, so they are only sent when they actually change."""
        wanted = tuple(headers)
        if wanted != self.applied_headers:
            await self.browser.set_extra_headers(dict(wanted))
            self.applied_headers = wanted

    async def close(self) -> None:
        for session in tuple(self.sessions.values()):
            await session.close()
        self.sessions.clear()
        await self.browser.close()


state: State | None = None


def error_result(error: str, *, status: int = 0, worth_retry: bool = False, url: str = '') -> dict[str, Any]:
    return {'error': error, 'status': status, 'worth_retry': worth_retry, 'url': url, 'headers': [], 'data': b''}


def result_from_response(url: str, status: int, reason: str, headers: Sequence[tuple[str, str]], data: bytes) -> dict[str, Any]:
    if not (200 <= status < 300) and status:
        return error_result(f'HTTP {status} {reason}'.strip(), status=status, worth_retry=status in RETRY_STATUSES, url=url)
    return {'url': url, 'status': status or int(HTTPStatus.OK), 'reason': reason, 'headers': list(headers), 'data': data, 'worth_retry': False}


async def page_fetch(page: Page, url: str, method: str, headers: Sequence[tuple[str, str]], data: bytes, timeout: float) -> dict[str, Any]:
    """Fetch url from inside page, with the document's cookies and referrer."""
    body = base64.b64encode(data).decode('ascii') if data else ''
    result = await page.call(PAGE_FETCH_JS, url, method, [list(h) for h in headers], body, int(timeout * 1000), timeout=timeout + DOM_READY_GRACE)
    if not isinstance(result, dict):
        return error_result(f'Fetching {url} from the page returned nothing', worth_retry=True, url=url)
    if result.get('error'):
        return error_result(str(result['error']), worth_retry=True, url=url)
    response_headers = [(str(n), str(v)) for n, v in result.get('headers') or ()]
    return result_from_response(
        str(result.get('url') or url),
        int(result.get('status') or 0),
        str(result.get('statusText') or ''),
        response_headers,
        base64.b64decode(result.get('base64') or ''),
    )


async def fetch_document(session: Session, page: Page, url: str, timeout: float) -> dict[str, Any]:
    """Navigate the session's tab to url and hand back what it renders.

    Navigating, rather than fetching, is the whole point of using this browser:
    the page runs its scripts and the request looks like the one a person
    sitting in front of the browser would have made.
    """
    try:
        await page.open(url, wait='load', timeout=timeout)
    except TimeoutExceeded:
        # A page kept from firing its load event by some straggling tracker is
        # still perfectly usable as long as its DOM has been built
        debug(f'{url} did not finish loading within {timeout} seconds, using it as it stands')
        await page.wait_for_dom_ready(DOM_READY_GRACE)
    final_url = await page.current_url()
    session.document_url = final_url
    response = page.response_for(final_url) or page.response_for(page.url) or page.response_for(url)
    status = response.status if response is not None else int(HTTPStatus.OK)
    reason = response.status_text if response is not None else ''
    headers = list(response.headers) if response is not None else []
    if status == HTTPStatus.NOT_MODIFIED:
        # The browser revalidated a document it already had and was told to use
        # its own copy, which it did, so the tab is showing the document even
        # though the status code on its own reads as a failure. This is routine
        # for a recipe that retries a request the site answered with a bot
        # check, since by then the browser has the page from the attempt that
        # the check's own scripts reloaded. A 304 carries neither a body nor a
        # content type, so the rendered document in the tab is both all there
        # is to hand back and the only thing the status says anything about.
        status, reason, headers = int(HTTPStatus.OK), '', []
    if not (200 <= status < 300) and status:
        return error_result(f'HTTP {status} {reason}'.strip(), status=status, worth_retry=status in RETRY_STATUSES, url=final_url)
    if content_type_of(headers) not in RENDERED_CONTENT_TYPES and headers:
        # Something the browser does not render as a document, such as the JSON
        # an API returns or the XML of a feed. Hand back the bytes the server
        # actually sent.
        #
        # The tab is left holding something that is not an HTML document, which
        # has no sub-resources for a later fetch_resource() to take out of it
        # and, being a bare XML document, cannot even host the <img> used to
        # ask for one. So the session is recorded as not working on a document
        # at all and whatever it asks for next is navigated to instead.
        session.document_url = ''
        resource = await page.get_resource(final_url, timeout=timeout)
        return result_from_response(final_url, status, reason, headers, resource.data)
    html = await page.call(DOCUMENT_HTML_JS, timeout=timeout)
    headers = [(n, v) for n, v in headers if n.lower() != 'content-type']
    headers.append(('Content-Type', 'text/html; charset=utf-8'))
    return result_from_response(final_url, status, reason, headers, str(html).encode('utf-8'))


async def fetch_resource(page: Page, url: str, timeout: float) -> dict[str, Any]:
    """Hand back a part of the document the session is working on.

    The images and stylesheets of an article have already been loaded by the
    tab that rendered it, and the browser still has the responses, so those
    cost nothing at all. Anything else is loaded by the page first, so that the
    request is made the way the page's own requests are made.
    """
    if page.response_for(url) is None:
        # Not something the page asked for. Usually an image the recipe picked
        # out of a srcset that the browser chose a different candidate from,
        # or one a recipe's image_url_processor built for itself.
        await page.call(LOAD_IMAGE_JS, url, int(timeout * 1000), timeout=timeout + DOM_READY_GRACE)
    try:
        resource = await page.get_resource(url, timeout=timeout)
    except Error as err:
        response = page.response_for(url)
        status = response.status if response is not None else 0
        return error_result(str(err), status=status, worth_retry=not status or status in RETRY_STATUSES, url=url)
    headers = [('Content-Type', resource.content_type)] if resource.content_type else []
    status = resource.status
    if status == HTTPStatus.NOT_MODIFIED and resource.data:
        # Revalidated out of the browser's cache, which happens for an image
        # two articles share. The bytes came from the browser rather than from
        # the wire, so having them is what makes this a success.
        status = int(HTTPStatus.OK)
    return result_from_response(url, status, '', headers, resource.data)


async def do_fetch(state: State, request: Mapping[str, Any]) -> dict[str, Any]:
    url = str(request['url'])
    timeout = float(request.get('timeout') or DEFAULT_TIMEOUT)
    headers = [(str(n), str(v)) for n, v in request.get('headers') or ()]
    data = request.get('data') or b''
    method = str(request.get('method') or 'GET').upper()
    session = await state.session_for(str(request['session']))
    async with session.lock:
        session.last_used = time.monotonic()
        page = await state.page_for(session, timeout)
        if method != 'GET' or headers:
            # Neither a body nor per request headers can be attached to a
            # navigation, so these go through the page's own fetch()
            if not session.document_url:
                # Nothing has been loaded in this tab, so a fetch from it would
                # be made from about:blank, with no cookies and no origin
                with suppress(Error):
                    await page.open(origin_of(url), wait='domcontentloaded', timeout=timeout)
                    session.document_url = await page.current_url()
            return await page_fetch(page, url, method, headers, data, timeout)
        if request.get('as_document') or not session.document_url:
            return await fetch_document(session, page, url, timeout)
        return await fetch_resource(page, url, timeout)


def origin_of(url: str) -> str:
    parts = urlparse(url)
    return f'{parts.scheme}://{parts.netloc}/' if parts.scheme and parts.netloc else url


async def setup_browser(input_data: Mapping[str, Any]) -> None:
    """Launch and warm up the browser. Called once, on the first request."""
    global state
    from calibre.web.automate.browser import Browser, Warmup

    warmup = None
    if input_data.get('warmup', True):
        warmup = Warmup(excluded_domains=input_data.get('warmup_excluded_domains') or ())
        debug(f'Warming up camoufox on: {", ".join(warmup.urls)}')
    browser = Browser(
        headless=bool(input_data.get('headless', True)),
        warmup=warmup,
        block_images=bool(input_data.get('block_images', False)),
        ignore_https_errors=not input_data.get('verify_ssl_certificates', False),
        firefox_user_prefs=BROWSER_PREFS,
    )
    started = time.monotonic()
    await browser.launch()
    debug(f'Camoufox ready in {time.monotonic() - started:.1f} seconds')
    state = State(browser, int(input_data.get('max_tabs') or DEFAULT_MAX_TABS))


async def handle_request(input_data: Mapping[str, Any], request: Mapping[str, Any]) -> Any:  # noqa: ANN401
    """Handle one request from the recipe process."""
    assert state is not None
    action = str(request.get('action') or '')
    match action:
        case 'fetch':
            await state.apply_headers([(str(n), str(v)) for n, v in request.get('extra_headers') or ()])
            return await do_fetch(state, request)
        case 'release':
            await state.release(str(request['session']))
            return True
        case 'set_cookies':
            await state.browser.set_cookies(request['cookies'])
            return True
        case 'get_cookies':
            return await state.browser.cookies()
        case 'user_agent':
            return await state.browser.user_agent()
    raise KeyError(f'Unknown action for the camoufox recipe worker: {action}')


def finalize(input_data: Mapping[str, Any]) -> None:
    """Shut the browser down when the worker's server stops.

    This is called from inside the worker's event loop, so it cannot await
    anything. It does not need to: closing the browser is blocking work from
    beginning to end, which is why Browser.close() farms it out to a thread.
    Skipping it would leave the browser process running once its parent exits.
    """
    global state
    current, state = state, None
    if current is None:
        return
    browser = current.browser
    process, browser.process = browser.process, None
    with suppress(Exception):
        if process is not None:
            if not browser.closed:
                with suppress(Exception):
                    browser.connection.send_nowait('Browser.close')
            browser.reap(process, browser.connection.transport)
    browser.closed = True
    profile_dir, browser.profile_dir = browser.profile_dir, ''
    if profile_dir:
        with suppress(Exception):
            remove_profile_dir(profile_dir)


# }}}


# Client side, runs in the process the recipe runs in {{{


class Response:
    """What :meth:`Browser.open` hands back, shaped like an HTTP response.

    The request has already completed by the time this exists, since the worker
    protocol blocks the calling thread, so unlike the response objects of the
    other scraper backends nothing here has to wait for anything.
    """

    def __init__(self, result: Mapping[str, Any]) -> None:
        self.final_url = str(result.get('url') or '')
        self._status = int(result.get('status') or 0)
        self._reason = str(result.get('reason') or '')
        if not self._reason and self._status:
            with suppress(ValueError):
                self._reason = HTTPStatus(self._status).phrase
        self._headers = [(str(n), str(v)) for n, v in result.get('headers') or ()]
        self._data = BytesIO(result.get('data') or b'')

    def read(self, *a: Any) -> bytes:  # noqa: ANN401
        return self._data.read(*a)

    def seek(self, *a: Any) -> int:  # noqa: ANN401
        return self._data.seek(*a)

    def tell(self) -> int:
        return self._data.tell()

    @property
    def url(self) -> str:
        return self.final_url

    @property
    def status(self) -> int:
        return self._status

    code = status

    @property
    def headers(self) -> Any:  # noqa: ANN401
        from email.message import EmailMessage

        ans = EmailMessage()
        for name, value in self._headers:
            ans[name] = value
        return ans

    @property
    def reason(self) -> str:
        return self._reason

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self.url

    def getinfo(self) -> Any:  # noqa: ANN401
        return self.headers

    def close(self) -> None:
        self._data.close()

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *a: Any) -> None:  # noqa: ANN401
        self.close()


class Worker:
    """The browser subprocess, shared by a browser and all of its clones."""

    def __init__(self, input_data: dict[str, Any]) -> None:
        self.input_data = input_data
        self.lock = RLock()
        self.path = ''
        self.close_worker: Callable[[], int] | None = None
        self.shutting_down = False

    def ensure_started(self) -> str:
        with self.lock:
            if self.shutting_down:
                raise URLError('The camoufox browser has been shut down')
            if not self.path:
                self.path, self.close_worker = start_worker(
                    f'{WORKER_MODULE}:handle_request',
                    f'{WORKER_MODULE}:setup_browser',
                    f'{WORKER_MODULE}:finalize',
                    input_data=self.input_data,
                )
            return self.path

    def request(self, payload: Mapping[str, Any]) -> Any:  # noqa: ANN401
        # Deliberately not holding self.lock: every request gets a connection
        # of its own and the worker serves them concurrently, which is what
        # lets the recipe's download threads make progress in parallel
        path = self.ensure_started()
        response = make_request(path, payload)
        if response.exception:
            raise URLError(f'The camoufox browser failed: {response.exception}')
        return response.response

    def shutdown(self) -> None:
        with self.lock:
            self.shutting_down = True
            close_worker, self.close_worker = self.close_worker, None
            self.path = ''
        if close_worker is not None:
            with suppress(Exception):
                close_worker()


def shutdown_worker(ref: weakref.ReferenceType[Worker]) -> None:
    worker = ref()
    if worker is not None:
        worker.shutdown()


class Browser:
    """A mechanize workalike backed by Camoufox, for ``BasicNewsRecipe.browser``.

    :param user_agent: ignored, see :meth:`set_user_agent`
    :param headers: headers to send with every request
    :param verify_ssl_certificates: refuse to load pages whose TLS certificates
        do not validate
    :param headless: run the browser without a visible window
    :param warmup: visit a few commonly browsed sites before the first download
    :param warmup_excluded_domains: sites the warmup must stay away from,
        normally the ones the recipe is about to download from
    :param max_tabs: the most tabs to keep open at once, which should be at
        least the number of threads the recipe downloads on
    :param block_images: do not load images at all, for a recipe that does not
        want them
    :param start_worker: launch the browser now rather than on first use
    """

    # Read by RecursiveFetcher, which knows which of the URLs it asks for are
    # documents and which are parts of the document it last fetched, a
    # distinction this browser, unlike the others, can act on
    accepts_as_document = True

    def __init__(
        self,
        user_agent: str = '',
        headers: Iterable[tuple[str, str]] = (),
        verify_ssl_certificates: bool = False,
        *,
        headless: bool = True,
        warmup: bool = True,
        warmup_excluded_domains: Iterable[str] = (),
        max_tabs: int = DEFAULT_MAX_TABS,
        block_images: bool = False,
        start_worker: bool = False,
    ) -> None:
        self.addheaders: list[tuple[str, str]] = list(headers)
        self.session_id = secrets.token_hex(16)
        self.owns_worker = True
        self.worker = Worker({
            'headless': headless,
            'warmup': warmup,
            'warmup_excluded_domains': list(warmup_excluded_domains),
            'max_tabs': max_tabs,
            'block_images': block_images,
            'verify_ssl_certificates': verify_ssl_certificates,
        })
        atexit.register(shutdown_worker, weakref.ref(self.worker))
        if user_agent:
            # Saying so rather than quietly ignoring it, because a recipe that
            # sets one is usually trying to work around bot detection, which is
            # the very thing this browser is for
            debug(f'Ignoring the requested user agent {user_agent!r}, camoufox uses one that matches the rest of its fingerprint')
        if start_worker:
            self.worker.ensure_started()

    def clone_browser(self) -> Browser:
        """A browser sharing this one's Camoufox instance but with a tab of its own.

        Recipes clone once per article, on the thread that downloads it, so
        this is what gives every download thread a tab to itself.
        """
        ans = Browser.__new__(Browser)
        ans.addheaders = list(self.addheaders)
        ans.session_id = secrets.token_hex(16)
        ans.owns_worker = False
        ans.worker = self.worker
        return ans

    # Fetching {{{

    def _open(self, url_or_request: Request | str, data: Any = None, timeout: float | None = None, as_document: bool = False) -> Response:  # noqa: ANN401
        method = 'POST' if data else 'GET'
        headers: list[tuple[str, str]] = []
        if isinstance(url_or_request, Request):
            method = url_or_request.get_method()
            data = data or url_or_request.data
            headers = list(url_or_request.header_items())
            url = url_or_request.full_url
        else:
            url = url_or_request

        def has_header(name: str) -> bool:
            name = name.lower()
            return any(h.lower() == name for h, _ in headers)

        if isinstance(data, dict):
            headers.append(('Content-Type', 'application/x-www-form-urlencoded'))
            data = urlencode(data)
        if isinstance(data, str):
            data = data.encode('utf-8')
            if not has_header('Content-Type'):
                headers.append(('Content-Type', 'text/plain'))
        if (read := getattr(data, 'read', None)) is not None:
            data = read()
        if data and not has_header('Content-Type'):
            headers.append(('Content-Type', 'application/x-www-form-urlencoded'))
        if not self.is_method_ok(method):
            raise KeyError(f'The HTTP {method} request method is not supported')

        result = self.worker.request({
            'action': 'fetch',
            'session': self.session_id,
            'url': url,
            'method': method,
            'headers': headers,
            'extra_headers': self.addheaders,
            'data': data or b'',
            'timeout': timeout,
            'as_document': as_document,
        })
        if result.get('error'):
            err = URLError(result['error'])
            setattr(err, 'worth_retry', bool(result.get('worth_retry')))
            if result.get('status'):
                setattr(err, 'code', int(result['status']))
            raise err
        return Response(result)

    def open(self, url_or_request: Request | str, data: Any = None, timeout: float | None = None, as_document: bool = True) -> Response:  # noqa: ANN401
        """Load a URL the way a person clicking a link would.

        Unless as_document is False the page is navigated to in this browser's
        tab, so its scripts run and what comes back is the rendered document.
        """
        return self._open(url_or_request, data, timeout, as_document)

    def open_novisit(self, url_or_request: Request | str, data: Any = None, timeout: float | None = None, as_document: bool = False) -> Response:  # noqa: ANN401
        """Get a URL without navigating to it.

        Used for the images and stylesheets of the document this browser last
        opened, which the browser has usually already loaded, in which case
        nothing goes over the network. The first such call on a browser that
        has not opened anything yet is treated as a document, since there is no
        page for it to be a part of.
        """
        return self._open(url_or_request, data, timeout, as_document)

    def is_method_ok(self, method: str) -> bool:
        return True

    # }}}

    # Browser wide settings {{{

    def set_simple_cookie(self, name: str, value: str, domain: str | None = None, path: str | None = '/') -> None:
        """Set a cookie for all the tabs of the shared browser.

        If domain is specified the cookie is only sent to matching domains, the
        leading dot being optional, otherwise it is sent everywhere.
        """
        cookie = {'name': name, 'value': value, 'path': path or '/'}
        if domain:
            cookie['domain'] = domain
        self.worker.request({'action': 'set_cookies', 'session': self.session_id, 'cookies': [cookie]})

    set_cookie = set_simple_cookie

    def cookies(self) -> list[dict[str, Any]]:
        return self.worker.request({'action': 'get_cookies', 'session': self.session_id}) or []

    def set_user_agent(self, val: str = '') -> None:
        """Does nothing, and says so.

        Camoufox reports a user agent that matches the rest of the fingerprint
        it presents, down to the platform and the list of fonts. Replacing just
        that one string is exactly the inconsistency bot detection looks for,
        so the request is refused rather than honoured badly.
        """
        if val:
            debug(f'Refusing to set the user agent to {val!r}, camoufox uses one that matches the rest of its fingerprint')

    def user_agent(self) -> str:
        return str(self.worker.request({'action': 'user_agent', 'session': self.session_id}) or '')

    # }}}

    def release(self) -> None:
        """Let the worker close the tab this browser was using."""
        with suppress(Exception):
            self.worker.request({'action': 'release', 'session': self.session_id})

    def shutdown(self) -> None:
        if self.owns_worker:
            self.worker.shutdown()
        else:
            self.release()

    def __del__(self) -> None:
        with suppress(Exception):
            self.shutdown()


# }}}


def develop(args: Sequence[str] = ()) -> None:
    """Fetch the URLs given on the command line, for testing this module by hand."""
    import sys

    args = args or sys.argv[1:]
    urls = [x for x in args if not x.startswith('-')]
    br = Browser(warmup='--warmup' in args, headless='--headful' not in args)
    try:
        print('User agent:', br.user_agent())
        for url in urls:
            clone = br.clone_browser()
            started = time.monotonic()
            with clone.open(url) as response:
                html = response.read()
            print(f'{url} -> {response.geturl()} [{response.status}] {len(html)} bytes in {time.monotonic() - started:.1f}s')
            for src in image_urls(html, response.geturl())[:5]:
                try:
                    with clone.open_novisit(src) as image:
                        print(f'  {len(image.read())} bytes of {image.headers.get("Content-Type")} from {src}')
                except URLError as err:
                    print(f'  failed to get {src}: {err}')
    finally:
        br.shutdown()


def image_urls(html: bytes, base_url: str) -> list[str]:
    import re
    from urllib.parse import urljoin

    found = re.findall(rb'''<img[^>]+src=["']([^"']+)["']''', html, flags=re.IGNORECASE)
    seen = {urljoin(base_url, x.decode('utf-8', 'replace')) for x in found}
    return sorted(x for x in seen if not x.startswith('data:'))


if __name__ == '__main__':
    develop()
