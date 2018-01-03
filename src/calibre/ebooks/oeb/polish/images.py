#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import os
from functools import partial
from threading import Thread, Event
from Queue import Queue, Empty

from calibre import detect_ncpus, human_readable, force_unicode, filesystem_encoding


class Worker(Thread):

    daemon = True

    def __init__(self, abort, name, queue, results, container, jpeg_quality, progress_callback):
        Thread.__init__(self, name=name)
        self.queue, self.results, self.container = queue, results, container
        self.progress_callback = progress_callback
        self.jpeg_quality = jpeg_quality
        self.abort = abort
        self.start()

    def run(self):
        while not self.abort.is_set():
            try:
                name = self.queue.get_nowait()
            except Empty:
                break
            try:
                self.compress(name)
            except Exception:
                import traceback
                self.results[name] = (False, traceback.format_exc())
            finally:
                try:
                    self.progress_callback(name)
                except Exception:
                    import traceback
                    traceback.print_exc()
                self.queue.task_done()

    def compress(self, name):
        from calibre.utils.img import optimize_png, optimize_jpeg, encode_jpeg
        mt = self.container.mime_map[name]
        if 'png' in mt:
            func = optimize_png
        elif self.jpeg_quality is None:
            func = optimize_jpeg
        else:
            func = partial(encode_jpeg, quality=self.jpeg_quality)
        path = self.container.get_file_path_for_processing(name)
        before = os.path.getsize(path)
        with lopen(path, 'rb') as f:
            old_data = f.read()
        func(path)
        after = os.path.getsize(path)
        if after >= before:
            with lopen(path, 'wb') as f:
                f.write(old_data)
            after = before
        self.results[name] = (True, (before, after))


def get_compressible_images(container):
    mt_map = container.manifest_type_map
    images = set()
    for mt in 'png jpg jpeg'.split():
        images |= set(mt_map.get('image/' + mt, ()))
    return images


def compress_images(container, report=None, names=None, jpeg_quality=None, progress_callback=lambda n, t, name:True):
    images = get_compressible_images(container)
    if names is not None:
        images &= set(names)
    results = {}
    queue = Queue()
    abort = Event()
    for name in images:
        queue.put(name)

    def pc(name):
        keep_going = progress_callback(len(results), len(images), name)
        if not keep_going:
            abort.set()
    progress_callback(0, len(images), '')
    [Worker(abort, 'CompressImage%d' % i, queue, results, container, jpeg_quality, pc) for i in xrange(min(detect_ncpus(), len(images)))]
    queue.join()
    before_total = after_total = 0
    for name, (ok, res) in results.iteritems():
        name = force_unicode(name, filesystem_encoding)
        if ok:
            before, after = res
            before_total += before
            after_total += after
            if report:
                if before != after:
                    report(_('{0} compressed from {1} to {2} bytes [{3:.1%} reduction]').format(
                        name, human_readable(before), human_readable(after), (before - after)/before))
                else:
                    report(_('{0} could not be further compressed').format(name))
        else:
            report(_('Failed to process {0} with error:').format(name))
            report(res)
    if report:
        if before_total > 0:
            report('')
            report(_('Total image filesize reduced from {0} to {1} [{2:.1%} reduction]').format(
                human_readable(before_total), human_readable(after_total), (before_total - after_total)/before_total))
        else:
            report(_('Images are already fully optimized'))
    return before_total > 0, results
