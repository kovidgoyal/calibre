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


def get_ruff_config(is_strict_check):
    if is_strict_check:
        return ['--config=ruff-strict-pep8.toml']
    else:
        return []


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
    CACHE_STRICT = 'check-strict.json'

    def add_options(self, parser):
        parser.add_option('--fix', '--auto-fix', default=False, action='store_true',
                help='Try to automatically fix some of the smallest errors')
        parser.add_option('--pep8', '--pep8-commit', default=False, action='store_true',
                help='Try to automatically fix some of the smallest errors, then perform a pep8 commit')
        parser.add_option('--strict', '--strict-pep8', default=False, action='store_true',
                help='Perform the checking more strictely. See the file "strict-pep8.toml"')

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
        return self.j(build_cache_dir(), self.CACHE_STRICT if self.is_strict_check else self.CACHE)

    def save_cache(self, cache):
        dump_json(cache, self.cache_file)

    def file_has_errors(self, f):
        ext = os.path.splitext(f)[1]
        if ext in {'.py', '.recipe'}:
            p = subprocess.Popen(['ruff', 'check', f] + get_ruff_config(self.is_strict_check))
            return p.wait() != 0
        if ext == '.pyj':
            p = subprocess.Popen(['rapydscript', 'lint', f])
            return p.wait() != 0
        if ext == '.yaml':
            p = subprocess.Popen(['python', self.j(self.wn_path, 'whats_new.py'), f])
            return p.wait() != 0

    def perform_auto_fix(self):
        cp = subprocess.run(['ruff', 'check', '--fix-only'], stdout=subprocess.PIPE)
        if cp.returncode != 0:
            raise SystemExit('ruff fixing failed')
        return cp.stdout.decode('utf-8') or 'Fixed 0 errors.'

    def perform_pep8_git_commit(self):
        return subprocess.run(['git', 'commit', '--all', '-m', 'pep8']).returncode != 0

    def check_errors_remain(self):
        return subprocess.run(['ruff', 'check', '--statistics']).returncode != 0

    def run(self, opts):
        if opts.fix and opts.pep8:
            self.info('setup.py check: error: options --fix and --pep8 are mutually exclusive')
            raise SystemExit(2)
        if opts.strict and opts.pep8:
            self.info('setup.py check: error: options --strict and --pep8 are mutually exclusive')
            raise SystemExit(2)

        self.fhash_cache = {}
        self.wn_path = os.path.expanduser('~/work/srv/main/static')
        self.has_changelog_check = os.path.exists(self.wn_path)
        self.auto_fix = opts.fix
        self.is_strict_check = opts.strict
        if opts.pep8:
            self.run_pep8_commit()
        else:
            self.run_check_files()

    def run_check_files(self):
        cache = {}
        try:
            with open(self.cache_file, 'rb') as f:
                cache = json.load(f)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
        if self.auto_fix:
            self.info('\tAuto-fixing')
            msg = self.perform_auto_fix()
            self.info(msg+'\n')
        dirty_files = tuple(f for f in self.get_files() if not self.is_cache_valid(f, cache))
        try:
            for i, f in enumerate(dirty_files):
                self.info('\tChecking', f)
                if self.file_has_errors(f):
                    self.info('%d files left to check' % (len(dirty_files) - i - 1))
                    try:
                        edit_file(f)
                    except FileNotFoundError:
                        pass  # continue if the configured editor fail to be open
                    if self.file_has_errors(f):
                        raise SystemExit(1)
                cache[f] = self.file_hash(f)
        finally:
            self.save_cache(cache)

    def run_pep8_commit(self):
        require_git_master()
        require_clean_git()
        msg = self.perform_auto_fix()
        self.info(msg+'\n')
        self.info('Commit the pep8 change...')
        self.perform_pep8_git_commit()
        self.info()
        if self.check_errors_remain():
            self.info('There are remaining errors. Execute "setup.py check" without options to locate them.')

    def report_errors(self, errors):
        for err in errors:
            self.info('\t\t', str(err))

    def clean(self):
        for cache_file in [self.j(build_cache_dir(), self.CACHE), self.j(build_cache_dir(), self.CACHE_STRICT)]:
            try:
                os.remove(cache_file)
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
        subprocess.call(['pyupgrade', '--py38-plus'] + files)
