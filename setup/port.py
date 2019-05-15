#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import errno
import hashlib
import json
import os
import re
import sys
from contextlib import contextmanager

from setup import Command, build_cache_dir, dump_json


@contextmanager
def modified_file(path, modify):
    with open(path, 'r+b') as f:
        raw = f.read()
        nraw = modify(raw)
        modified = nraw != raw
        if modified:
            f.seek(0), f.truncate(), f.write(nraw), f.flush()
        f.seek(0)
        try:
            yield
        finally:
            if modified:
                f.seek(0), f.truncate(), f.write(raw)


def no2to3(raw):
    return re.sub(br'^.+?\s+# no2to3$', b'', raw, flags=re.M)


def run_2to3(path, show_diffs=False):
    from lib2to3.main import main
    with modified_file(path, no2to3):
        cmd = [
                '-f', 'all',
                '-f', 'buffer',
                '-f', 'idioms',
                '-f', 'set_literal',
                '-x', 'future',
                path,
        ]
        if not show_diffs:
            cmd.append('--no-diffs')

        ret = main('lib2to3.fixes', cmd + [path])
    return ret


class To3(Command):

    description = 'Run 2to3 and fix anything it reports'
    CACHE = 'check2to3.json'

    @property
    def cache_file(self):
        return self.j(build_cache_dir(), self.CACHE)

    def is_cache_valid(self, f, cache):
        return cache.get(f) == self.file_hash(f)

    def save_cache(self, cache):
        dump_json(cache, self.cache_file)

    def get_files(self):
        from calibre import walk
        for path in walk(os.path.join(self.SRC, 'calibre')):
            if path.endswith('.py'):
                yield path

    def file_hash(self, f):
        try:
            return self.fhash_cache[f]
        except KeyError:
            self.fhash_cache[f] = ans = hashlib.sha1(open(f, 'rb').read()).hexdigest()
            return ans

    def file_has_errors(self, f):
        from polyglot.io import PolyglotStringIO
        oo, oe = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = buf = PolyglotStringIO()
        try:
            ret = run_2to3(f)
        finally:
            sys.stdout, sys.stderr = oo, oe
        if ret:
            raise SystemExit('Could not parse: ' + f)
        output = buf.getvalue()
        return re.search(r'^RefactoringTool: No changes to ' + f, output, flags=re.M) is None

    def run(self, opts):
        self.fhash_cache = {}
        cache = {}
        try:
            cache = json.load(open(self.cache_file, 'rb'))
        except EnvironmentError as err:
            if err.errno != errno.ENOENT:
                raise
        dirty_files = tuple(f for f in self.get_files() if not self.is_cache_valid(f, cache))
        try:
            for i, f in enumerate(dirty_files):
                self.info('\tChecking', f)
                if self.file_has_errors(f):
                    run_2to3(f, show_diffs=True)
                    self.info('%d files left to check' % (len(dirty_files) - i - 1))
                    raise SystemExit(1)
                cache[f] = self.file_hash(f)
        finally:
            self.save_cache(cache)

    def clean(self):
        try:
            os.remove(self.cache_file)
        except EnvironmentError as err:
            if err.errno != errno.ENOENT:
                raise
