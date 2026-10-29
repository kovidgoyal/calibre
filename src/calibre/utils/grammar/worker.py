#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Worker processes that run grammar checks and generate suggestions in the
# background. Checks and suggestions use separate workers so that slow
# suggestions never delay checking. Requests and responses are sent over a
# pair of pipes. Results are cached in the parent process, so unchanged
# paragraphs and sentences are never sent to the worker.

import subprocess
import sys
import traceback
from collections.abc import Callable, Sequence
from contextlib import suppress
from itertools import count
from multiprocessing import Pipe
from queue import Queue
from threading import Lock, Thread
from typing import NamedTuple, Protocol, Self

from calibre.constants import iswindows
from calibre.utils.grammar.backend import Backend, ModelNotDownloaded, Suggestion, SuggestionsAborted, UnsupportedLanguage
from calibre.utils.grammar.cache import ResultCache, model_cache_key
from calibre.utils.grammar.checker import CHECKER_VERSION, DEFAULT_CHECK_OPTIONS, Checker, CheckOptions, ParagraphResult
from calibre.utils.grammar.gpu import DEFAULT_GPU_MODE, GpuMode
from calibre.utils.grammar.models import Task, canonical_lang, default_model, is_usable, suggestion_kinds
from calibre.utils.grammar.rules import (
    RULES_VERSION,
    LanguageDataNotDownloaded,
    UnsupportedRulesLanguage,
    code_for,
    is_language_data_downloaded,
    langtool_version,
)
from calibre.utils.ipc import eintr_retry_call
from calibre.utils.localization import _

if iswindows:
    from multiprocessing.connection import PipeConnection as Connection
else:
    from multiprocessing.connection import Connection

# Number of paragraphs checked between sending partial results to the parent,
# also the granularity at which check requests can be cancelled
CHECK_CHUNK_SIZE = 16


# Messages {{{
class CheckRequest(NamedTuple):
    request_id: int
    paragraphs: tuple[str, ...]
    lang: str
    options: CheckOptions


class SuggestRequest(NamedTuple):
    request_id: int
    sentence: str
    lang: str
    kinds: tuple[str, ...]
    count: int
    num_beams: int
    model_id: str


class CancelRequest(NamedTuple):
    request_id: int


class ShutdownRequest(NamedTuple):
    pass


Request = CheckRequest | SuggestRequest | CancelRequest | ShutdownRequest


class CheckResults(NamedTuple):
    request_id: int
    # Maps indices into the paragraphs of the request to results
    results: dict[int, ParagraphResult]


class ModelMissing(NamedTuple):
    # Sent when a deep check was requested but the checking model has not
    # been downloaded, the check continues using only the rules
    request_id: int
    model_id: str
    variant: str


class SuggestResults(NamedTuple):
    request_id: int
    suggestions: tuple[Suggestion, ...]


class RequestFailed(NamedTuple):
    request_id: int
    error: str
    details: str
    # Set if the request failed because the model needs to be downloaded
    model_id: str = ''
    variant: str = ''
    # Set to the langtool language code if the request failed because the
    # data for checking the language needs to be downloaded
    language_data: str = ''


class RequestDone(NamedTuple):
    request_id: int
    cancelled: bool


WorkerMessage = CheckResults | ModelMissing | SuggestResults | RequestFailed | RequestDone
# }}}


# Worker process {{{
class ServerBackend(Protocol):
    def check_paragraphs(self, paragraphs: Sequence[str], lang: str | None = None, options: CheckOptions = DEFAULT_CHECK_OPTIONS) -> list[ParagraphResult]: ...

    def missing_model(self, lang: str | None) -> ModelNotDownloaded | None: ...

    def suggest(
        self,
        sentence: str,
        lang: str | None = None,
        kinds: Sequence[str] = (),
        count: int = 1,
        num_beams: int = 1,
        model_id: str = '',
        should_abort: Callable[[], bool] | None = None,
    ) -> list[Suggestion]: ...

    def abort(self) -> None: ...


class Server:
    def __init__(self, requests: Connection, responses: Connection, backend: ServerBackend):
        self.requests, self.responses = requests, responses
        self.backend = backend
        self.queue: Queue[Request] = Queue()
        self.lock = Lock()
        self.cancelled: set[int] = set()
        self.current_request = -1

    def read_requests(self) -> None:
        try:
            while True:
                req: Request = eintr_retry_call(self.requests.recv)
                if isinstance(req, CancelRequest):
                    with self.lock:
                        self.cancelled.add(req.request_id)
                        is_current = req.request_id == self.current_request
                    if is_current:
                        self.backend.abort()
                    continue
                self.queue.put(req)
                if isinstance(req, ShutdownRequest):
                    break
        except EOFError, OSError:
            pass
        self.queue.put(ShutdownRequest())

    def send(self, msg: WorkerMessage) -> bool:
        try:
            eintr_retry_call(self.responses.send, msg)
        except EOFError, OSError, BrokenPipeError:
            return False
        return True

    def is_cancelled(self, request_id: int) -> bool:
        with self.lock:
            return request_id in self.cancelled

    def finish(self, request_id: int) -> bool:
        with self.lock:
            cancelled = request_id in self.cancelled
            self.cancelled.discard(request_id)
            self.current_request = -1
        return self.send(RequestDone(request_id, cancelled))

    def run(self) -> None:
        Thread(target=self.read_requests, name='GrammarRequests', daemon=True).start()
        while True:
            req = self.queue.get()
            if isinstance(req, ShutdownRequest):
                break
            if isinstance(req, CancelRequest):
                continue
            with self.lock:
                if req.request_id in self.cancelled:
                    self.cancelled.discard(req.request_id)
                    cancelled = True
                else:
                    self.current_request = req.request_id
                    cancelled = False
            if cancelled:
                if not self.send(RequestDone(req.request_id, True)):
                    break
                continue
            if not self.handle(req) or not self.finish(req.request_id):
                break

    def handle(self, req: CheckRequest | SuggestRequest) -> bool:
        try:
            if isinstance(req, CheckRequest):
                return self.check(req)
            return self.suggest(req)
        except ModelNotDownloaded as e:
            return self.send(RequestFailed(req.request_id, str(e), '', e.model_id, e.variant))
        except LanguageDataNotDownloaded as e:
            return self.send(RequestFailed(req.request_id, str(e), '', language_data=e.code))
        except (UnsupportedLanguage, UnsupportedRulesLanguage) as e:
            return self.send(RequestFailed(req.request_id, str(e), ''))
        except SuggestionsAborted:
            return True
        except Exception as e:
            return self.send(RequestFailed(req.request_id, str(e), traceback.format_exc()))

    def check(self, req: CheckRequest) -> bool:
        if req.options.deep and (e := self.backend.missing_model(req.lang)) is not None:
            if not self.send(ModelMissing(req.request_id, e.model_id, e.variant)):
                return False
        for start in range(0, len(req.paragraphs), CHECK_CHUNK_SIZE):
            if self.is_cancelled(req.request_id):
                break
            chunk = req.paragraphs[start : start + CHECK_CHUNK_SIZE]
            results = self.backend.check_paragraphs(chunk, req.lang, req.options)
            if not self.send(CheckResults(req.request_id, {start + i: r for i, r in enumerate(results)})):
                return False
        return True

    def suggest(self, req: SuggestRequest) -> bool:
        suggestions = self.backend.suggest(
            req.sentence, req.lang, req.kinds, req.count, req.num_beams, req.model_id, should_abort=lambda: self.is_cancelled(req.request_id)
        )
        if self.is_cancelled(req.request_id):
            return True
        return self.send(SuggestResults(req.request_id, tuple(suggestions)))


def worker_main(requests_fd: int, responses_fd: int, gpu_mode: GpuMode, num_threads: int) -> None:
    with Connection(requests_fd, True, False) as requests, Connection(responses_fd, False, True) as responses:
        with suppress(KeyboardInterrupt):
            Server(requests, responses, Checker(Backend(gpu_mode, num_threads))).run()


# }}}


# Client {{{
class CheckResponse(NamedTuple):
    request_id: int
    # Maps indices into the paragraphs passed to check() to results. Can be
    # empty, for example, for the final response or when there is an error.
    results: dict[int, ParagraphResult]
    # True for the last response to a request
    done: bool = False
    error: str = ''
    details: str = ''
    # Set in a response with done=False if a deep check was requested but this
    # model variant needs to be downloaded, the results are then only from the
    # rules
    model_id: str = ''
    variant: str = ''
    cancelled: bool = False
    # Set to the langtool language code if the request failed because the data
    # for checking the language needs to be downloaded, see
    # calibre.utils.grammar.rules.download_language_data()
    language_data: str = ''


class SuggestResponse(NamedTuple):
    request_id: int
    suggestions: tuple[Suggestion, ...]
    done: bool = False
    error: str = ''
    details: str = ''
    model_id: str = ''
    variant: str = ''
    cancelled: bool = False


class PendingCheck(NamedTuple):
    callback: Callable[[CheckResponse], None]
    checker_key: str
    # Maps indices in the request sent to the worker, to indices in the
    # paragraphs passed to check(), as only uncached, unique paragraphs are sent
    index_map: tuple[tuple[int, ...], ...]
    paragraphs: tuple[str, ...]
    # Whether the results are expected to be from a deep check and to have
    # ranked replacements, results that are not are not cached
    deep: bool
    ranked: bool


class PendingSuggest(NamedTuple):
    callback: Callable[[SuggestResponse], None]
    model_key: str
    sentence: str
    kinds: tuple[str, ...]
    count: int
    num_beams: int


request_counter = count(1)


class WorkerClient:
    """
    Base class for the clients that talk to the worker processes. Callbacks are
    called from a background thread, or for cached results, from the thread that
    made the request, so GUI code must take care to process the responses in the
    GUI thread.
    """

    TASK: Task = 'check'
    THREAD_NAME = 'GrammarWorker'

    def __init__(self, gpu_mode: GpuMode = DEFAULT_GPU_MODE, num_threads: int = 0, priority: str = 'low', cache: ResultCache | None = None):
        self.gpu_mode = gpu_mode
        self.num_threads = num_threads
        self.priority = priority
        self.cache = cache if cache is not None else ResultCache(None)
        self.lock = Lock()
        self.worker: subprocess.Popen[bytes] | None = None
        self.requests: Connection | None = None
        self.pending: dict[int, PendingCheck | PendingSuggest] = {}
        self.shutting_down = False

    def ensure_worker(self) -> Connection:
        if self.worker is not None and self.requests is not None and self.worker.poll() is None:
            return self.requests
        from calibre.utils.ipc.simple_worker import start_pipe_worker
        from calibre.web.automate.worker import relay_stderr, worker_stderr_kwargs

        self.cleanup_worker()
        req_read, req_write = Pipe(False)
        resp_read, resp_write = Pipe(False)
        with req_read, resp_write:
            cmd = (
                'from calibre.utils.grammar.worker import worker_main; '
                f'worker_main({req_read.fileno()}, {resp_write.fileno()}, {self.gpu_mode!r}, {self.num_threads})'
            )
            self.worker = start_pipe_worker(
                cmd,
                pass_fds=(req_read.fileno(), resp_write.fileno()),
                stdout=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                priority=self.priority,
                **worker_stderr_kwargs(),
            )
        if self.worker.stderr is not None:
            Thread(target=relay_stderr, args=(self.worker.stderr,), name=self.THREAD_NAME + 'Stderr', daemon=True).start()
        self.requests = req_write
        Thread(target=self.read_responses, args=(resp_read, self.worker), name=self.THREAD_NAME, daemon=True).start()
        return req_write

    def cleanup_worker(self) -> None:
        if self.requests is not None:
            with suppress(OSError):
                self.requests.close()
            self.requests = None
        if self.worker is not None:
            w, self.worker = self.worker, None
            try:
                w.wait(1)
            except subprocess.TimeoutExpired:
                w.kill()
                w.wait()

    def send(self, req: Request) -> None:
        with self.lock:
            conn = self.ensure_worker()
            try:
                eintr_retry_call(conn.send, req)
            except OSError, EOFError:
                # The worker died, start a new one and try again
                self.cleanup_worker()
                conn = self.ensure_worker()
                eintr_retry_call(conn.send, req)

    def read_responses(self, conn: Connection, worker: subprocess.Popen[bytes] | None) -> None:
        with conn:
            while True:
                try:
                    msg: WorkerMessage = eintr_retry_call(conn.recv)
                except EOFError, OSError:
                    break
                try:
                    self.dispatch(msg)
                except Exception:
                    traceback.print_exc()
        # The worker has exited, fail any requests it was handling
        with self.lock:
            if self.worker is worker:
                self.cleanup_worker()
            pending, self.pending = self.pending, {}
            shutting_down = self.shutting_down
        if not shutting_down:
            for request_id, p in pending.items():
                self.fail(request_id, p, _('The grammar checking worker process crashed'), f'Exit code: {worker.poll() if worker else None}')

    def pop_pending(self, request_id: int, remove: bool) -> PendingCheck | PendingSuggest | None:
        with self.lock:
            return self.pending.pop(request_id, None) if remove else self.pending.get(request_id)

    def dispatch(self, msg: WorkerMessage) -> None:
        raise NotImplementedError()

    def fail(
        self, request_id: int, p: PendingCheck | PendingSuggest, error: str, details: str = '', model_id: str = '', variant: str = '', language_data: str = ''
    ) -> None:
        raise NotImplementedError()

    def model_key(self, lang: str | None, model_id: str) -> str:
        if not model_id:
            model_id = default_model(self.TASK, lang) or ''
            if not model_id:
                raise UnsupportedLanguage(self.TASK, canonical_lang(lang))
        return model_cache_key(model_id)

    def cancel(self, request_id: int) -> None:
        """Cancel the specified request. The callback will be called with a final response with cancelled=True."""
        with self.lock:
            if request_id not in self.pending or self.requests is None:
                return
        with suppress(OSError, EOFError):
            self.send(CancelRequest(request_id))

    def cancel_all(self) -> None:
        with self.lock:
            ids = tuple(self.pending)
        for request_id in ids:
            self.cancel(request_id)

    def shutdown(self) -> None:
        with self.lock:
            self.shutting_down = True
            if self.requests is not None:
                with suppress(OSError, EOFError):
                    self.requests.send(ShutdownRequest())
            self.cleanup_worker()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *a: object) -> None:
        self.shutdown()


class GrammarCheckWorker(WorkerClient):
    """Check paragraphs for grammar, style and typography issues in a background process"""

    TASK = 'check'
    THREAD_NAME = 'GrammarCheckWorker'

    def checker_key(self, lang: str | None, options: CheckOptions) -> tuple[str, bool, bool]:
        """
        Return the key for caching results and whether the results are
        expected to be from a deep check and to have ranked replacements.
        Raises UnsupportedRulesLanguage if the language is not supported.
        """
        parts = [f'rules:{CHECKER_VERSION}:{RULES_VERSION}:{langtool_version()}:{code_for(lang)}:{options.rules.cache_key}']
        model_id = default_model('check', lang) or ''
        deep = options.deep and bool(model_id)
        ranked = options.rank and bool(model_id) and is_usable(model_id)
        if deep:
            # Results depend on the threshold so it is part of the cache key
            parts.append(f'deep:{model_cache_key(model_id)}:{options.error_threshold}')
        if ranked:
            parts.append(f'rank:{model_cache_key(model_id)}')
        return '\n'.join(parts), deep, ranked

    def check(
        self,
        paragraphs: Sequence[str],
        callback: Callable[[CheckResponse], None],
        lang: str | None = None,
        options: CheckOptions = DEFAULT_CHECK_OPTIONS,
    ) -> int:
        """
        Check the specified paragraphs, returning the request id. callback is
        called with the results as they become available, and finally with a
        response that has done=True. Results for paragraphs that are in the
        cache are delivered before this method returns.
        """
        request_id = next(request_counter)
        paragraphs = tuple(paragraphs)
        try:
            checker_key, deep, ranked = self.checker_key(lang, options)
        except UnsupportedRulesLanguage as e:
            callback(CheckResponse(request_id, {}, done=True, error=str(e)))
            return request_id
        cached = self.cache.get_paragraph_results(checker_key, paragraphs)
        if cached:
            callback(CheckResponse(request_id, cached))
        # Send only unique, uncached paragraphs to the worker
        unique: dict[str, list[int]] = {}
        for i, s in enumerate(paragraphs):
            if i not in cached:
                unique.setdefault(s, []).append(i)
        if not unique:
            callback(CheckResponse(request_id, {}, done=True))
            return request_id
        p = PendingCheck(callback, checker_key, tuple(tuple(x) for x in unique.values()), paragraphs, deep, ranked)
        with self.lock:
            self.pending[request_id] = p
        req = CheckRequest(request_id, tuple(unique), lang or '', options)
        try:
            self.send(req)
        except (OSError, EOFError) as e:
            self.pop_pending(request_id, True)
            self.fail(request_id, p, _('Failed to start the grammar checking worker process'), str(e))
        return request_id

    def dispatch(self, msg: WorkerMessage) -> None:
        p = self.pop_pending(msg.request_id, isinstance(msg, (RequestDone, RequestFailed)))
        if not isinstance(p, PendingCheck):
            return
        if isinstance(msg, CheckResults):
            self.cache.set_paragraph_results(p.checker_key, (r for r in msg.results.values() if r.deep_checked == p.deep and r.ranked == p.ranked))
            results: dict[int, ParagraphResult] = {}
            for i, r in msg.results.items():
                for orig in p.index_map[i]:
                    results[orig] = r
            p.callback(CheckResponse(msg.request_id, results))
        elif isinstance(msg, ModelMissing):
            p.callback(CheckResponse(msg.request_id, {}, model_id=msg.model_id, variant=msg.variant))
        elif isinstance(msg, RequestDone):
            p.callback(CheckResponse(msg.request_id, {}, done=True, cancelled=msg.cancelled))
        elif isinstance(msg, RequestFailed):
            self.fail(msg.request_id, p, msg.error, msg.details, msg.model_id, msg.variant, msg.language_data)

    def fail(
        self, request_id: int, p: PendingCheck | PendingSuggest, error: str, details: str = '', model_id: str = '', variant: str = '', language_data: str = ''
    ) -> None:
        if isinstance(p, PendingCheck):
            p.callback(CheckResponse(request_id, {}, done=True, error=error, details=details, model_id=model_id, variant=variant, language_data=language_data))


def suggestion_filter_key(lang: str | None) -> str:
    """Suggestions are filtered with the rules only if the data for the language has been downloaded, so this is part of the cache key"""
    try:
        ready = is_language_data_downloaded(lang)
    except UnsupportedRulesLanguage:
        return ''
    return f':rules:{RULES_VERSION}:{langtool_version()}' if ready else ''


class SuggestionWorker(WorkerClient):
    """Generate suggestions for improving sentences in a background process"""

    TASK = 'suggest'
    THREAD_NAME = 'GrammarSuggestionWorker'

    def suggest(
        self,
        sentence: str,
        callback: Callable[[SuggestResponse], None],
        lang: str | None = None,
        kinds: Sequence[str] = (),
        count: int = 1,
        num_beams: int = 1,
        model_id: str = '',
        cancel_previous: bool = True,
    ) -> int:
        """
        Generate suggestions for improving the sentence, returning the request
        id. callback is called with the suggestions and then with a final
        response that has done=True. If cancel_previous is True, all previous
        requests are cancelled, as typically only suggestions for the most
        recently selected sentence are wanted.
        """
        request_id = next(request_counter)
        if cancel_previous:
            self.cancel_all()
        try:
            model_key = self.model_key(lang, model_id) + suggestion_filter_key(lang)
            kinds = tuple(kinds) or suggestion_kinds(model_id or default_model('suggest', lang) or '')
        except (UnsupportedLanguage, KeyError) as e:
            callback(SuggestResponse(request_id, (), done=True, error=str(e)))
            return request_id
        num_beams = max(num_beams, count)
        if (cached := self.cache.get_suggestions(model_key, sentence, kinds, count, num_beams)) is not None:
            callback(SuggestResponse(request_id, tuple(cached)))
            callback(SuggestResponse(request_id, (), done=True))
            return request_id
        p = PendingSuggest(callback, model_key, sentence, kinds, count, num_beams)
        with self.lock:
            self.pending[request_id] = p
        try:
            self.send(SuggestRequest(request_id, sentence, lang or '', kinds, count, num_beams, model_id))
        except (OSError, EOFError) as e:
            self.pop_pending(request_id, True)
            self.fail(request_id, p, _('Failed to start the grammar suggestions worker process'), str(e))
        return request_id

    def dispatch(self, msg: WorkerMessage) -> None:
        p = self.pop_pending(msg.request_id, isinstance(msg, (RequestDone, RequestFailed)))
        if not isinstance(p, PendingSuggest):
            return
        if isinstance(msg, SuggestResults):
            self.cache.set_suggestions(p.model_key, p.sentence, p.kinds, p.count, p.num_beams, msg.suggestions)
            p.callback(SuggestResponse(msg.request_id, msg.suggestions))
        elif isinstance(msg, RequestDone):
            p.callback(SuggestResponse(msg.request_id, (), done=True, cancelled=msg.cancelled))
        elif isinstance(msg, RequestFailed):
            self.fail(msg.request_id, p, msg.error, msg.details, msg.model_id, msg.variant)

    def fail(
        self, request_id: int, p: PendingCheck | PendingSuggest, error: str, details: str = '', model_id: str = '', variant: str = '', language_data: str = ''
    ) -> None:
        if isinstance(p, PendingSuggest):
            p.callback(SuggestResponse(request_id, (), done=True, error=error, details=details, model_id=model_id, variant=variant))


# }}}


def develop() -> None:
    import time
    from threading import Event

    paragraphs = sys.argv[1:] or [
        'She go to school yesterday and buyed three apple.',
        'The quick brown fox jumps over the lazy dog.',
        'Despite of the rain, we goes outside.',
        'The quick brown fox jumps over the lazy dog.',
    ]
    done = Event()

    def on_check(r: CheckResponse) -> None:
        for i, res in sorted(r.results.items()):
            print(f'{i}: {res.text}')
            for issue in res.issues:
                print(f'    {res.text[issue.start : issue.end]!r} -> {list(issue.replacements[:4])} [{issue.source}:{issue.rule_id}]')
        if r.error or r.model_id:
            print('Error:', r.error, r.details, r.model_id, r.variant, r.language_data)
        if r.done:
            done.set()

    cache = ResultCache(None)
    with GrammarCheckWorker(cache=cache, gpu_mode='off') as w:
        for attempt in range(2):
            done.clear()
            st = time.perf_counter()
            w.check(paragraphs, on_check, options=CheckOptions(deep=True))
            done.wait()
            print(f'Attempt {attempt + 1} took {time.perf_counter() - st:.2f} seconds')

    def on_suggest(r: SuggestResponse) -> None:
        for s in r.suggestions:
            print(f'{s.kind}: {s.text}')
        if r.error:
            print('Error:', r.error, r.details)
        if r.done:
            done.set()

    with SuggestionWorker(cache=cache, gpu_mode='off') as sw:
        done.clear()
        st = time.perf_counter()
        sw.suggest(paragraphs[0], on_suggest, kinds=('fluency', 'formal'))
        done.wait()
        print(f'Suggestions took {time.perf_counter() - st:.2f} seconds')
