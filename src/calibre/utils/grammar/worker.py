#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Worker processes that run grammar checks and generate suggestions in the
# background. Checks and suggestions use separate workers so that slow
# suggestions never delay checking. Requests and responses are sent over a
# pair of pipes. Results are cached in the parent process, so unchanged
# sentences are never sent to the worker.

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
from calibre.utils.grammar.backend import DEFAULT_ERROR_THRESHOLD, Backend, CheckResult, ModelNotDownloaded, Suggestion, SuggestionsAborted, UnsupportedLanguage
from calibre.utils.grammar.cache import ResultCache, model_cache_key
from calibre.utils.grammar.gpu import DEFAULT_GPU_MODE, GpuMode
from calibre.utils.grammar.models import Task, canonical_lang, default_model, suggestion_kinds
from calibre.utils.ipc import eintr_retry_call
from calibre.utils.localization import _

if iswindows:
    from multiprocessing.connection import PipeConnection as Connection
else:
    from multiprocessing.connection import Connection

# Number of sentences checked between sending partial results to the parent,
# also the granularity at which check requests can be cancelled
CHECK_CHUNK_SIZE = 16


# Messages {{{
class CheckRequest(NamedTuple):
    request_id: int
    sentences: tuple[str, ...]
    lang: str
    model_id: str
    error_threshold: float


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
    # Maps indices into the sentences of the request to results
    results: dict[int, CheckResult]


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


class RequestDone(NamedTuple):
    request_id: int
    cancelled: bool


WorkerMessage = CheckResults | SuggestResults | RequestFailed | RequestDone
# }}}


# Worker process {{{
class ServerBackend(Protocol):
    def check_sentences(
        self, sentences: Sequence[str], lang: str | None = None, model_id: str = '', error_threshold: float = DEFAULT_ERROR_THRESHOLD
    ) -> list[CheckResult]: ...

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
        except UnsupportedLanguage as e:
            return self.send(RequestFailed(req.request_id, str(e), ''))
        except SuggestionsAborted:
            return True
        except Exception as e:
            return self.send(RequestFailed(req.request_id, str(e), traceback.format_exc()))

    def check(self, req: CheckRequest) -> bool:
        for start in range(0, len(req.sentences), CHECK_CHUNK_SIZE):
            if self.is_cancelled(req.request_id):
                break
            chunk = req.sentences[start : start + CHECK_CHUNK_SIZE]
            results = self.backend.check_sentences(chunk, req.lang, req.model_id, req.error_threshold)
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
            Server(requests, responses, Backend(gpu_mode, num_threads)).run()


# }}}


# Client {{{
class CheckResponse(NamedTuple):
    request_id: int
    # Maps indices into the sentences passed to check() to results. Can be
    # empty, for example, for the final response or when there is an error.
    results: dict[int, CheckResult]
    # True for the last response to a request
    done: bool = False
    error: str = ''
    details: str = ''
    # Set if the request failed because this model variant needs to be downloaded
    model_id: str = ''
    variant: str = ''
    cancelled: bool = False


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
    model_key: str
    # Maps indices in the request sent to the worker, to indices in the
    # sentences passed to check(), as only uncached, unique sentences are sent
    index_map: tuple[tuple[int, ...], ...]
    sentences: tuple[str, ...]


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

    def fail(self, request_id: int, p: PendingCheck | PendingSuggest, error: str, details: str = '', model_id: str = '', variant: str = '') -> None:
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
    """Check sentences for grammatical errors in a background process"""

    TASK = 'check'
    THREAD_NAME = 'GrammarCheckWorker'

    def check(
        self,
        sentences: Sequence[str],
        callback: Callable[[CheckResponse], None],
        lang: str | None = None,
        model_id: str = '',
        error_threshold: float = DEFAULT_ERROR_THRESHOLD,
    ) -> int:
        """
        Check the specified sentences, returning the request id. callback is
        called with the results as they become available, and finally with a
        response that has done=True. Results for sentences that are in the cache
        are delivered before this method returns.
        """
        request_id = next(request_counter)
        sentences = tuple(sentences)
        try:
            # Results depend on the threshold so it is part of the cache key
            model_key = f'{self.model_key(lang, model_id)}:{error_threshold}'
        except UnsupportedLanguage as e:
            callback(CheckResponse(request_id, {}, done=True, error=str(e)))
            return request_id
        cached = self.cache.get_check_results(model_key, sentences)
        if cached:
            callback(CheckResponse(request_id, cached))
        # Send only unique, uncached sentences to the worker
        unique: dict[str, list[int]] = {}
        for i, s in enumerate(sentences):
            if i not in cached:
                unique.setdefault(s, []).append(i)
        if not unique:
            callback(CheckResponse(request_id, {}, done=True))
            return request_id
        p = PendingCheck(callback, model_key, tuple(tuple(x) for x in unique.values()), sentences)
        with self.lock:
            self.pending[request_id] = p
        req = CheckRequest(request_id, tuple(unique), lang or '', model_id, error_threshold)
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
            self.cache.set_check_results(p.model_key, msg.results.values())
            results: dict[int, CheckResult] = {}
            for i, r in msg.results.items():
                for orig in p.index_map[i]:
                    results[orig] = r
            p.callback(CheckResponse(msg.request_id, results))
        elif isinstance(msg, RequestDone):
            p.callback(CheckResponse(msg.request_id, {}, done=True, cancelled=msg.cancelled))
        elif isinstance(msg, RequestFailed):
            self.fail(msg.request_id, p, msg.error, msg.details, msg.model_id, msg.variant)

    def fail(self, request_id: int, p: PendingCheck | PendingSuggest, error: str, details: str = '', model_id: str = '', variant: str = '') -> None:
        if isinstance(p, PendingCheck):
            p.callback(CheckResponse(request_id, {}, done=True, error=error, details=details, model_id=model_id, variant=variant))


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
            model_key = self.model_key(lang, model_id)
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

    def fail(self, request_id: int, p: PendingCheck | PendingSuggest, error: str, details: str = '', model_id: str = '', variant: str = '') -> None:
        if isinstance(p, PendingSuggest):
            p.callback(SuggestResponse(request_id, (), done=True, error=error, details=details, model_id=model_id, variant=variant))


# }}}


def develop() -> None:
    import time
    from threading import Event

    sentences = sys.argv[1:] or [
        'She go to school yesterday and buyed three apple.',
        'The quick brown fox jumps over the lazy dog.',
        'Despite of the rain, we goes outside.',
        'The quick brown fox jumps over the lazy dog.',
    ]
    done = Event()

    def on_check(r: CheckResponse) -> None:
        for i, res in sorted(r.results.items()):
            print(f'{i}: correct={res.correct} {res.corrected}')
        if r.error:
            print('Error:', r.error, r.details, r.model_id, r.variant)
        if r.done:
            done.set()

    cache = ResultCache(None)
    with GrammarCheckWorker(cache=cache, gpu_mode='off') as w:
        for attempt in range(2):
            done.clear()
            st = time.perf_counter()
            w.check(sentences, on_check)
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
        sw.suggest(sentences[0], on_suggest, kinds=('fluency', 'formal'))
        done.wait()
        print(f'Suggestions took {time.perf_counter() - st:.2f} seconds')
