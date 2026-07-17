#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import errno
import hashlib
import json
import os
import subprocess

from setup import Command, build_cache_dir, dump_json, edit_file, iswindows


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
    require_venv = True

    CACHE = 'check.json'

    def add_options(self, parser):
        parser.add_option('--fix', '--auto-fix', default=False, action='store_true',
                help='Try to automatically fix some of the smallest errors instead of opening an editor for bad files.')
        parser.add_option('-f', '--file', dest='files', type='string', action='append',
                help='Specific file to be check. Can be repeat to check severals.')
        parser.add_option('--no-editor', default=False, action='store_true',
                help="Don't open the editor when a bad file is found.")

    def get_files(self):
        yield from checkable_python_files(self.SRC)

        yield from files_walker(self.j(self.d(self.SRC), 'recipes'), '.recipe')

        yield from files_walker(self.j(self.d(self.SRC), 'stubs'), '.pyi')

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

    def _ruff_executable(self):
        ruff = self.j(self.PROJECT_ROOT, '.venv/bin/ruff')
        if iswindows:
            ruff += '.exe'
        if not os.path.exists(ruff):
            import shutil
            ruff = shutil.which('ruff') or 'ruff'
        return ruff

    def file_has_errors(self, f):
        ext = os.path.splitext(f)[1]
        if ext in {'.py', '.pyi', '.recipe'}:
            ruff = self._ruff_executable()
            if self.auto_fix:
                p = subprocess.Popen([ruff, 'check', '-q', '--fix', f], cwd=self.PROJECT_ROOT)
            else:
                p = subprocess.Popen([ruff, 'check', '-q', f], cwd=self.PROJECT_ROOT)
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
        self.files = opts.files
        self.no_editor = opts.no_editor
        self.run_check_files()

    def run_check_files(self):
        cache = {}
        try:
            with open(self.cache_file, 'rb') as f:
                cache = json.load(f)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
        if self.files:
            all_files = tuple(self.files)
        else:
            all_files = tuple(f for f in self.get_files() if not self.is_cache_valid(f, cache))

        python_exts = {'.py', '.pyi', '.recipe'}
        python_files = [f for f in all_files if os.path.splitext(f)[1] in python_exts]
        other_files = [f for f in all_files if os.path.splitext(f)[1] not in python_exts]

        try:
            # Check all Python files with ruff, splitting into safe chunks to
            # avoid hitting the kernel ARG_MAX limit on command-line length.
            bad_python_files = set()
            if python_files:
                ruff = self._ruff_executable()
                ruff_cmd = [ruff, 'check', '-q', '--output-format=json']
                if self.auto_fix:
                    ruff_cmd.insert(3, '--fix')
                # Keep each chunk well under typical ARG_MAX (128 KiB on Linux,
                # 256 KiB on macOS).  We budget 64 KiB for the file-list portion.
                chunk_limit = 64 * 1024
                chunk: list[str] = []
                chunk_len = 0
                chunks: list[list[str]] = []
                for f in python_files:
                    flen = len(f.encode()) + 1  # +1 for the NUL separator
                    if chunk and chunk_len + flen > chunk_limit:
                        chunks.append(chunk)
                        chunk = []
                        chunk_len = 0
                    chunk.append(f)
                    chunk_len += flen
                if chunk:
                    chunks.append(chunk)
                for batch in chunks:
                    p = subprocess.run(
                        ruff_cmd + batch,
                        capture_output=True, text=True,
                        cwd=self.PROJECT_ROOT,
                    )
                    if p.returncode != 0:
                        try:
                            diagnostics = json.loads(p.stdout)
                            bad_python_files.update(d['filename'] for d in diagnostics)
                        except (json.JSONDecodeError, KeyError):
                            bad_python_files.update(batch)
            for f in python_files:
                if f not in bad_python_files:
                    cache[f] = self.file_hash(f)

            # For each Python file that has errors, open editor and re-check individually.
            bad_list = list(bad_python_files)
            for i, f in enumerate(bad_list):
                self.info('\tErrors in', f)
                self.info(f'{len(bad_list) - i - 1} bad Python files remaining')
                e = SystemExit(1)
                if self.no_editor:
                    raise e
                try:
                    edit_file(f)
                except FileNotFoundError:
                    raise e
                if self.file_has_errors(f):
                    raise e
                cache[f] = self.file_hash(f)

            # Check non-Python files one by one as before.
            for i, f in enumerate(other_files):
                self.info('\tChecking', f)
                if self.file_has_errors(f):
                    self.info(f'{len(other_files) - i - 1} files left to check')
                    e = SystemExit(1)
                    if self.no_editor:
                        raise e
                    try:
                        edit_file(f)
                    except FileNotFoundError:
                        raise e
                    if self.file_has_errors(f):
                        raise e
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
            if f.endswith('.py') and f != 'linux-installer.py' and not os.path.isdir(q):
                files.append(q)
        for path in checkable_python_files(self.SRC):
            q = path.replace(os.sep, '/')
            if '/metadata/sources/' in q or '/store/stores/' in q:
                continue
            files.append(q)
        subprocess.call(['pyupgrade', '--py314-plus'] + files)
