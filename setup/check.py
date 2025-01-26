#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import errno
import hashlib
import json
import os
import subprocess

from setup import Command, build_cache_dir, dump_json, edit_file, require_clean_git, require_git_master


class Message:

    def __init__(self, filename, lineno, msg):
        self.filename, self.lineno, self.msg = filename, lineno, msg

    def __str__(self):
        return f'{self.filename}:{self.lineno}: {self.msg}'


def files_walker(root_path, ext):
    for x in os.walk(root_path):
        for f in x[-1]:
            y = os.path.join(x[0], f)
            if f.endswith(ext):
                yield y


def checkable_python_files(SRC):
    for dname in ('odf', 'calibre'):
        for f in files_walker(os.path.join(SRC, dname), '.py'):
            if not f.endswith('_ui.py'):
                yield f


class Check(Command):

    description = 'Check for errors in the calibre source code'

    CACHE = 'check.json'

    def add_options(self, parser):
        parser.add_option('--fix', '--auto-fix', default=False, action='store_true',
                help='Try to automatically fix some of the smallest errors instead of opening an editor for bad files.')

    def get_files(self):
        yield from checkable_python_files(self.SRC)

        yield from files_walker(self.j(self.d(self.SRC), 'recipes'), '.recipe')

        yield from files_walker(self.j(self.SRC, 'pyj'), '.pyj')

        if self.has_changelog_check:
            yield self.j(self.d(self.SRC), 'Changelog.txt')

    def read_file(self, f):
        with open(f, 'rb') as f:
            return f.read()

    def file_hash(self, f):
        try:
            return self.fhash_cache[f]
        except KeyError:
            self.fhash_cache[f] = ans = hashlib.sha1(self.read_file(f)).hexdigest()
            return ans

    def is_cache_valid(self, f, cache):
        return cache.get(f) == self.file_hash(f)

    @property
    def cache_file(self):
        return self.j(build_cache_dir(), self.CACHE)

    def save_cache(self, cache):
        dump_json(cache, self.cache_file)

    def file_has_errors(self, f):
        ext = os.path.splitext(f)[1]
        if ext in {'.py', '.recipe'}:
            p = subprocess.Popen(['ruff', 'check', f])
            return p.wait() != 0
        if ext == '.pyj':
            p = subprocess.Popen(['rapydscript', 'lint', f])
            return p.wait() != 0
        if ext == '.yaml':
            p = subprocess.Popen(['python', self.j(self.wn_path, 'whats_new.py'), f])
            return p.wait() != 0

    def run(self, opts):
        self.fhash_cache = {}
        self.wn_path = os.path.expanduser('~/work/srv/main/static')
        self.has_changelog_check = os.path.exists(self.wn_path)
        self.auto_fix = opts.fix
        if self.auto_fix:
            self.run_auto_fix()
        self.run_check_files()

    def run_auto_fix(self):
        self.info('\tAuto-fixing')
        cp = subprocess.run(['ruff', 'check', '--fix-only'], stdout=subprocess.PIPE)
        if cp.returncode != 0:
            raise SystemExit('ruff auto-fixing failed')
        msg = cp.stdout.decode('utf-8') or 'Fixed 0 errors.'
        self.info(msg+'\n')

    def run_check_files(self):
        cache = {}
        try:
            with open(self.cache_file, 'rb') as f:
                cache = json.load(f)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
        dirty_files = tuple(f for f in self.get_files() if not self.is_cache_valid(f, cache))
        try:
            for i, f in enumerate(dirty_files):
                self.info('\tChecking', f)
                if self.file_has_errors(f):
                    self.info('{} files left to check'.format(len(dirty_files) - i - 1))
                    try:
                        edit_file(f)
                    except FileNotFoundError:
                        pass  # continue if the configured editor fail to be open
                    if self.file_has_errors(f):
                        raise SystemExit(1)
                cache[f] = self.file_hash(f)
        finally:
            self.save_cache(cache)

    def report_errors(self, errors):
        for err in errors:
            self.info('\t\t', str(err))

    def clean(self):
        try:
            os.remove(self.cache_file)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise


class UpgradeSourceCode(Command):

    description = 'Upgrade python source code'

    def run(self, opts):
        files = []
        for f in os.listdir(os.path.dirname(os.path.abspath(__file__))):
            q = os.path.join('setup', f)
            if f.endswith('.py') and f not in ('linux-installer.py',) and not os.path.isdir(q):
                files.append(q)
        for path in checkable_python_files(self.SRC):
            q = path.replace(os.sep, '/')
            if '/metadata/sources/' in q or '/store/stores/' in q:
                continue
            files.append(q)
        subprocess.call(['pyupgrade', '--py310-plus'] + files)
