#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


import errno
import hashlib
import json
import os
import re
import subprocess
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


class Base(Command):

    scan_all_files = False
    EXCLUDED_BASENAMES = {'Zeroconf.py', 'smtplib.py'}

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
            if (path.endswith('.py') and not path.endswith('_ui.py') and not
                    os.path.basename(path) in self.EXCLUDED_BASENAMES):
                yield path

    def file_hash(self, f):
        try:
            return self.fhash_cache[f]
        except KeyError:
            self.fhash_cache[f] = ans = hashlib.sha1(open(f, 'rb').read()).hexdigest()
            return ans

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
            if self.scan_all_files:
                bad_files = []
                for f in dirty_files:
                    if self.file_has_errors(f):
                        bad_files.append(f)
                    else:
                        cache[f] = self.file_hash(f)
                dirty_files = bad_files
            for i, f in enumerate(dirty_files):
                num_left = len(dirty_files) - i - 1
                self.info('\tChecking', f)
                if self.file_has_errors(f):
                    self.report_file_error(f, num_left)
                    self.fhash_cache.pop(f, None)
                cache[f] = self.file_hash(f)
        finally:
            self.save_cache(cache)

    def clean(self):
        try:
            os.remove(self.cache_file)
        except EnvironmentError as err:
            if err.errno != errno.ENOENT:
                raise


class To3(Base):

    description = 'Run 2to3 and fix anything it reports'
    CACHE = 'check2to3.json'

    def report_file_error(self, f, num_left):
        run_2to3(f, show_diffs=True)
        self.info('%d files left to check' % num_left)
        raise SystemExit(1)

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


def edit_file(f):
    subprocess.Popen([
        'vim', '-S', os.path.join(Command.SRC, '../session.vim'), '-f', f
    ]).wait()


class UnicodeCheck(Base):

    description = 'Check for unicode porting status'
    CACHE = 'check_unicode.json'
    scan_all_files = True

    def get_error_statement(self, f):
        uni_pat = re.compile(r'from __future__ import .*\bunicode_literals\b')
        str_pat = re.compile(r'\bstr\(')
        has_unicode_literals = False
        has_str_calls = False
        num_lines = 0
        for i, line in enumerate(open(f, 'rb')):
            line = line.decode('utf-8')
            if not line.strip():
                continue
            num_lines += 1
            if not has_unicode_literals and uni_pat.match(line) is not None:
                has_unicode_literals = True
            if not has_str_calls and str_pat.search(line) is not None:
                has_str_calls = True
            if has_unicode_literals and has_str_calls:
                break
        if num_lines < 1:
            return
        ans = None
        if not has_unicode_literals:
            if has_str_calls:
                ans = 'The file %s does not use unicode literals and has str() calls'
            else:
                ans = 'The file %s does not use unicode literals'
        elif has_str_calls:
            ans = 'The file %s has str() calls'
        return ans % f if ans else None

    def file_has_errors(self, f):
        return self.get_error_statement(f) is not None

    def report_file_error(self, f, num_left):
        edit_file(f)
        self.info('%d files left to check' % num_left)
        if self.file_has_errors(f):
            raise SystemExit(self.get_error_statement(f))


def has_import(text, module, name):
    pat = re.compile(r'^from\s+{}\s+import\s+.*\b{}\b'.format(module, name), re.MULTILINE)
    if pat.search(text) is not None:
        return True
    pat = re.compile(r'^from\s+{}\s+import\s+\([^)]*\b{}\b'.format(module, name), re.MULTILINE | re.DOTALL)
    if pat.search(text) is not None:
        return True
    return False


class IteratorsCheck(Base):

    description = 'Check for builtins changed to return iterators porting status'
    CACHE = 'check_iterators.json'

    def get_errors_in_file(self, f):
        pat = re.compile(r'\b(range|map|filter|zip)\(')
        with open(f, 'rb') as f:
            text = f.read().decode('utf-8')
        matches = tuple(pat.finditer(text))
        if not matches:
            return []
        ans = []
        names = {m.group(1) for m in matches}
        imported_names = {n for n in names if has_import(text, 'polyglot.builtins', n)}
        safe_funcs = 'list|tuple|set|frozenset|join'
        func_pat = r'({})\('.format(safe_funcs)
        for_pat = re.compile(r'\bfor\s+.+?\s+\bin\b')
        for i, line in enumerate(text.splitlines()):
            m = pat.search(line)
            if m is not None:
                itname = m.group(1)
                if itname in imported_names:
                    continue
                start = m.start()
                if start > 0:
                    if line[start-1] == '*':
                        continue
                    if line[start-1] == '(':
                        if re.search(func_pat + itname, line) is not None:
                            continue
                    fm = for_pat.search(line)
                    if fm is not None and fm.start() < start:
                        continue
                    ans.append('%s:%s' % (i, itname))
        return ans

    def file_has_errors(self, f):
        return bool(self.get_errors_in_file(f))

    def report_file_error(self, f, num_left):
        edit_file(f)
        self.info('%d files left to check' % num_left)
        if self.file_has_errors(f):
            raise SystemExit('\n'.join(self.get_errors_in_file(f)))
