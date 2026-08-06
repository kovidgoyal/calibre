#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import hashlib
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from setup import Command, iswindows

C_EXTENSIONS = ('.c', '.cpp', '.h', '.m')
C_FORMAT_DIRS = ('src', 'bypy/linux', 'bypy/macos', 'bypy/windows')


def md5_of_file(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def run_captured(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True)


def show_output(result):
    if result.stdout:
        sys.stdout.buffer.write(result.stdout)
        sys.stdout.buffer.flush()
    if result.stderr:
        sys.stderr.buffer.write(result.stderr)
        sys.stderr.buffer.flush()


class AutoFormat(Command):
    description = 'Autoformat source code'
    usage_help = 'To format specific files specify them on the command line'
    require_venv = True

    def add_options(self, parser):
        parser.add_option('--check-only', default=False, action='store_true', help='Only check for formatting issues dont fix them')

    def clang_format_cache_dir(self):
        d = self.j(self.PROJECT_ROOT, '.cache', 'clang-format')
        os.makedirs(d, exist_ok=True)
        return d

    def clang_format_file(self, path, cache_dir, check_only):
        # Cache file keyed by path hash; stores MD5 of last formatted content
        path_hash = hashlib.md5(os.path.abspath(path).encode()).hexdigest()
        cache_file = os.path.join(cache_dir, path_hash)
        current_md5 = md5_of_file(path)

        if not check_only:
            try:
                with open(cache_file) as f:
                    if f.read().strip() == current_md5:
                        return None  # already formatted, skip
            except FileNotFoundError:
                pass

        cf = self.j(self.PROJECT_ROOT, '.venv/bin/clang-format')
        cmd = [cf, '-style=file']
        if check_only:
            cmd += ['--dry-run', '--Werror', path]
        else:
            cmd += ['-i', path]

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode == 0 and not check_only:
            new_md5 = md5_of_file(path)
            tmp = cache_file + '.tmp'
            with open(tmp, 'w') as f:
                f.write(new_md5)
            os.replace(tmp, cache_file)

        return result

    def find_c_files(self):
        files = []
        for d in C_FORMAT_DIRS:
            dirpath = self.j(self.PROJECT_ROOT, d)
            for root, _, filenames in os.walk(dirpath):
                for fn in filenames:
                    if fn.endswith(C_EXTENSIONS):
                        files.append(os.path.join(root, fn))
        return files

    def run(self, opts):
        rapydscript = self.j(self.PROJECT_ROOT, '.venv/bin/rapydscript')
        ruff = self.j(self.PROJECT_ROOT, '.venv/bin/ruff')
        if iswindows:
            rapydscript += '.exe'
            ruff += '.exe'

        py_files = ()
        pyj_files = ()
        c_files = None  # None means auto-discover all

        if opts.cli_args:
            py_files = tuple(x for x in opts.cli_args if x.endswith(('.py', '.recipe')))
            pyj_files = tuple(x for x in opts.cli_args if x.endswith('.pyj'))
            c_files = [x for x in opts.cli_args if x.endswith(C_EXTENSIONS)]
            if not py_files and not pyj_files and not c_files:
                return
        else:
            c_files = self.find_c_files()

        run_py = not opts.cli_args or bool(py_files)
        run_pyj = not opts.cli_args or bool(pyj_files)

        import tomllib

        with open(self.j(self.PROJECT_ROOT, 'pyproject.toml')) as f:
            m = tomllib.loads(f.read())
            line_length = m['tool']['ruff']['line-length']

        failed = []

        # Phase 1: ruff check --fix-only must complete before ruff format runs
        if run_py:
            cmd = [ruff, 'check', '--fix-only']
            if opts.check_only:
                cmd.append('--diff')
            result = run_captured(cmd + list(py_files), self.PROJECT_ROOT)
            if result.returncode != 0:
                show_output(result)
                failed.append('ruff check --fix-only')

        if failed:
            raise SystemExit(1)

        # Phase 2: ruff format, rapydscript fmt, and clang-format all in parallel
        cache_dir = self.clang_format_cache_dir()

        with ThreadPoolExecutor() as executor:
            futures = {}

            if run_py:
                cmd = [ruff, 'format']
                if opts.check_only:
                    cmd.append('--check')
                futures[executor.submit(run_captured, cmd + list(py_files), self.PROJECT_ROOT)] = 'ruff format'

            if run_pyj:
                cmd = [rapydscript, 'fmt', '--line-length', str(line_length)]
                if opts.check_only:
                    cmd.append('--check-only')
                futures[executor.submit(run_captured, cmd + (list(pyj_files) or ['src/pyj']), self.PROJECT_ROOT)] = 'rapydscript fmt'

            for path in c_files:
                rel = os.path.relpath(path, self.PROJECT_ROOT)
                fut = executor.submit(self.clang_format_file, path, cache_dir, opts.check_only)
                futures[fut] = f'clang-format:{rel}'

            for fut in as_completed(futures):
                label = futures[fut]
                result = fut.result()
                if result is None:
                    continue  # cache hit, skipped
                if result.returncode != 0:
                    show_output(result)
                    failed.append(label)

        if failed:
            print(f'Formatting failed: {", ".join(failed)}', file=sys.stderr)
            raise SystemExit(1)
