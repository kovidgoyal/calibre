#!/usr/bin/env python
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>

import os
from queue import Queue
from threading import Thread

from calibre import detect_ncpus
from calibre.utils.img import encode_jpeg, optimize_jpeg


def compress_worker(input_queue, output_queue, jpeg_quality):
    while True:
        task = input_queue.get()
        if task is None:
            break
        book_id, path = task
        try:
            if jpeg_quality >= 100:
                stderr = optimize_jpeg(path)
            else:
                stderr = encode_jpeg(path, jpeg_quality)
        except Exception:
            import traceback
            stderr = traceback.format_exc()
        if stderr:
            output_queue.put((book_id, stderr))
        else:
            try:
                sz = os.path.getsize(path)
            except OSError as err:
                sz = str(err)
            output_queue.put((book_id, sz))


def compress_covers(path_map, jpeg_quality, progress_callback):
    input_queue = Queue()
    output_queue = Queue()
    num_workers = detect_ncpus()
    sz_map = {}
    for book_id, (path, sz) in path_map.items():
        input_queue.put((book_id, path))
        sz_map[book_id] = sz
    workers = [
        Thread(target=compress_worker, args=(input_queue, output_queue, jpeg_quality), daemon=True, name=f'CCover-{i}')
        for i in range(num_workers)
    ]
    [w.start() for w in workers]
    pending = set(path_map)
    while pending:
        book_id, new_sz = output_queue.get()
        pending.remove(book_id)
        progress_callback(book_id, sz_map[book_id], new_sz)
    for w in workers:
        input_queue.put(None)
    for w in workers:
        w.join()
