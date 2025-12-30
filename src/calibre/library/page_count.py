#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import os
import subprocess
import sys
from concurrent.futures import Executor, ThreadPoolExecutor
from contextlib import closing, suppress
from multiprocessing import Pipe
from operator import itemgetter

from lxml import etree

from calibre import detect_ncpus
from calibre.constants import iswindows
from calibre.ebooks.oeb.base import XHTML
from calibre.ebooks.oeb.iterator.book import extract_book
from calibre.ebooks.oeb.polish.container import Container as ContainerBase
from calibre.ebooks.oeb.polish.parsing import decode_xml, parse
from calibre.ebooks.oeb.polish.toc import get_toc
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.cleantext import clean_xml_chars
from calibre.utils.ipc import eintr_retry_call
from calibre.utils.logging import DevNull
from calibre_extensions.speedup import get_num_of_significant_chars

if iswindows:
    from multiprocessing.connection import PipeConnection as Connection
else:
    from multiprocessing.connection import Connection


class SimpleContainer(ContainerBase):

    tweak_mode = True


def count_pages_pdf(pathtoebook: str) -> int:
    from calibre.utils.podofo import get_page_count
    return get_page_count(pathtoebook)


def count_pages_cbz(pathtoebook: str) -> int:
    from calibre.ebooks.metadata.archive import fname_ok
    from calibre.utils.zipfile import ZipFile
    with closing(ZipFile(pathtoebook)) as zf:
        return sum(1 for _ in filter(fname_ok, zf.namelist()))


def count_pages_cbr(pathtoebook: str) -> int:
    from calibre.ebooks.metadata.archive import RAR, fname_ok
    with closing(RAR(pathtoebook)) as zf:
        return sum(1 for _ in filter(fname_ok, zf.namelist()))


def count_pages_cb7(pathtoebook: str) -> int:
    from calibre.ebooks.metadata.archive import SevenZip, fname_ok
    with closing(SevenZip(pathtoebook)) as zf:
        return sum(1 for _ in filter(fname_ok, zf.namelist()))


def get_length(root):
    ans = 0
    for body in root.iterchildren(XHTML('body')):
        ans += get_num_of_significant_chars(body)
        for elem in body.iterdescendants():
            ans += get_num_of_significant_chars(elem)
    return ans


CHARS_PER_PAGE = 1000


def get_page_count(root):
    return get_length(root) // CHARS_PER_PAGE


def calculate_number_of_workers(names, in_process_container, max_workers):
    num_workers = min(detect_ncpus(), len(names))
    if max_workers:
        num_workers = min(num_workers, max_workers)
    if num_workers > 1:
        if len(names) < 3 or sum(os.path.getsize(in_process_container.name_path_map[n]) for n in names) < 128 * 1024:
            num_workers = 1
    return num_workers


def decode(data: bytes) -> str:
    html, _ = decode_xml(data, normalize_to_nfc=True)
    return html


def parse_xhtml(path: str):
    with open(path, 'rb') as f:
        data = f.read()
    return parse(data, log=DevNull(), decoder=decode, force_html5_parse=False)


def process(path: str) -> int:
    root = parse_xhtml(path)
    return get_page_count(root)


def count_pages_oeb(pathtoebook: str, tdir: str, executor: Executor | None = None) -> int:
    nulllog = DevNull()
    book_fmt, opfpath, input_fmt = extract_book(pathtoebook, tdir, log=nulllog, only_input_plugin=True)
    container = SimpleContainer(tdir, opfpath, nulllog)
    tocobj = get_toc(container, verify_destinations=False)
    if page_list := getattr(tocobj, 'page_list', ()):
        uniq_page_numbers = frozenset(map(itemgetter('pagenum'), page_list))
        if len(uniq_page_numbers) > 50:
            return len(uniq_page_numbers)
    spine = {name for name, is_linear in container.spine_names}
    paths = {container.get_file_path_for_processing(name, allow_modification=False) for name in spine}
    paths = {p for p in paths if os.path.isfile(p)}

    if executor is None:
        with ThreadPoolExecutor() as executor:
            return sum(executor.map(process, paths))
    return sum(executor.map(process, paths))


def count_pages_txt(pathtoebook: str) -> int:
    with open(pathtoebook, 'rb') as f:
        text = f.read().decode('utf-8', 'replace')
    e = etree.Element('r')
    e.tail = clean_xml_chars(text)
    return get_num_of_significant_chars(e) // CHARS_PER_PAGE


def count_pages(pathtoebook: str, executor: Executor | None = None) -> int:
    ext = pathtoebook.rpartition('.')[-1].lower()
    match ext:
        case 'pdf':
            return count_pages_pdf(pathtoebook)
        case 'cbz':
            return count_pages_cbz(pathtoebook)
        case 'cbr':
            return count_pages_cbr(pathtoebook)
        case 'cb7':
            return count_pages_cb7(pathtoebook)
        case 'txt' | 'text' | 'md' | 'textile' | 'markdown':
            return count_pages_txt(pathtoebook)
        case _:
            with TemporaryDirectory() as tdir:
                return count_pages_oeb(pathtoebook, tdir, executor=executor)


class Server:

    ALGORITHM = 1

    def __init__(self, max_jobs_per_worker: int = 2048):
        self.worker: subprocess.Popoen | None = None
        self.tasks_run_by_worker = 0
        self.max_jobs_per_worker = max_jobs_per_worker

    def ensure_worker(self) -> None:
        if self.worker is not None:
            if self.tasks_run_by_worker < self.max_jobs_per_worker:
                return
            self.shutdown_worker()
        self.read_pipe, write_pipe = Pipe(False)
        with write_pipe:
            cmd = f'from calibre.library.page_count import worker_main; worker_main({write_pipe.fileno()})'
            from calibre.utils.ipc.simple_worker import start_pipe_worker
            self.worker = start_pipe_worker(cmd, pass_fds=(write_pipe.fileno(),), stdout=subprocess.DEVNULL)
        self.tasks_run_by_worker = 0

    def shutdown_worker(self) -> None:
        if self.worker is not None:
            w, self.worker = self.worker, None
            self.read_pipe.close()
            w.stdin.close()
            if w.wait(1) is None:
                w.kill()
                w.wait()

    def count_pages(self, path: str) -> int | tuple[str, str]:
        self.ensure_worker()
        encoded_path = path.encode().hex() + os.linesep
        self.worker.stdin.write(encoded_path.encode())
        self.worker.stdin.flush()
        self.tasks_run_by_worker += 1
        return eintr_retry_call(self.read_pipe.recv)

    def __enter__(self) -> 'Server':
        return self

    def __exit__(self, *a) -> None:
        self.shutdown_worker()


def serve_requests(pipe: Connection) -> None:
    executor = ThreadPoolExecutor()
    for line in sys.stdin:
        path = bytes.fromhex(line.rstrip()).decode()
        try:
            result = count_pages(path, executor)
        except Exception as e:
            import traceback
            result = str(e), traceback.format_exc()
        try:
            eintr_retry_call(pipe.send, result)
        except EOFError:
            break


def worker_main(pipe_fd: int) -> None:
    with suppress(KeyboardInterrupt), Connection(pipe_fd, False, True) as pipe:
        serve_requests(pipe)


def test_page_count() -> None:
    files = (
        P('quick_start/eng.epub'), P('quick_start/swe.epub'), P('quick_start/fra.epub'),
        P('common-english-words.txt'))
    with Server(max_jobs_per_worker=2) as s:
        for x in files:
            res = s.count_pages(x)
            if not isinstance(res, int):
                raise AssertionError(f'Counting pages for {x} failed with result: {res}')


def develop():
    import time
    paths = sys.argv[1:]
    executor = ThreadPoolExecutor()
    for x in paths:
        st = time.monotonic()
        res = count_pages(x, executor)
        print(x, f'{time.monotonic() - st:.2f}', res, flush=True)


if __name__ == '__main__':
    develop()
