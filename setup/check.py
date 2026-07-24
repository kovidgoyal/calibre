#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import concurrent.futures
import json
import os
import re
import subprocess
import sys

from setup import Command, edit_file, iswindows


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
    usage_help = 'To check specific files, specify them as command line arguments'
    require_venv = True

    def add_options(self, parser):
        parser.add_option('--no-editor', default=False, action='store_true', help="Don't open the editor when a bad file is found.")
        parser.add_option('--fix', '--auto-fix', default=False, action='store_true', help='Try to automatically fix errors with ruff.')

    def _ruff_executable(self):
        import shutil

        ruff = self.j(self.PROJECT_ROOT, '.venv/bin/ruff')
        if iswindows:
            ruff += '.exe'
        if not os.path.exists(ruff):
            ruff = shutil.which('ruff') or 'ruff'
        self._ruff_executable = lambda: ruff
        return ruff

    def _rapydscript_executable(self):
        import shutil

        rs = self.j(self.PROJECT_ROOT, '.venv/bin/rapydscript')
        if iswindows:
            rs += '.exe'
        if not os.path.exists(rs):
            rs = shutil.which('rapydscript') or 'rapydscript'
        self._rapydscript_executable = lambda: rs
        return rs

    def _run_ruff(self, targets):
        ruff = self._ruff_executable()
        cmd = [ruff, 'check', '--output-format=json']
        if self.auto_fix:
            cmd.append('--fix')
        p = subprocess.run(
            cmd + targets,
            capture_output=True,
            text=True,
            cwd=self.PROJECT_ROOT,
        )
        output_lines = []
        files_with_errors = set()
        if p.stdout:
            try:
                for d in json.loads(p.stdout):
                    fname = d['filename']
                    if not os.path.isabs(fname):
                        fname = os.path.join(self.PROJECT_ROOT, fname)
                    loc = d.get('location', {})
                    row = loc.get('row', 0)
                    col = loc.get('column', 0)
                    code = d.get('code', '')
                    msg = d.get('message', '')
                    output_lines.append(f'{fname}:{row}:{col}: {code} {msg}')
                    files_with_errors.add(fname)
            except json.JSONDecodeError, KeyError:
                output_lines.append(p.stdout.strip())
        if p.stderr.strip():
            output_lines.append(p.stderr.strip())
        return p.returncode, '\n'.join(filter(None, output_lines)), files_with_errors

    def _run_rapydscript(self, targets):
        p = subprocess.run(
            [self._rapydscript_executable(), 'lint'] + targets,
            capture_output=True,
            text=True,
        )
        combined = (p.stdout + p.stderr).strip()
        files_with_errors = set()
        if p.returncode != 0:
            for line in combined.splitlines():
                m = re.match(r'^(.+\.pyj):\d+', line)
                if m:
                    fname = m.group(1)
                    if not os.path.isabs(fname):
                        fname = os.path.join(self.PROJECT_ROOT, fname)
                    files_with_errors.add(fname)
        return p.returncode, combined, files_with_errors

    def _run_changelog(self, wn_path):
        changelog_file = self.j(self.d(self.SRC), 'Changelog.txt')
        p = subprocess.run(
            ['python', self.j(wn_path, 'whats_new.py'), changelog_file],
            capture_output=True,
            text=True,
        )
        return p.returncode, (p.stdout + p.stderr).strip()

    def _check_file(self, f):
        ext = os.path.splitext(f)[1]
        if ext in {'.py', '.pyi', '.recipe'}:
            ruff = self._ruff_executable()
            p = subprocess.run([ruff, 'check', f], capture_output=True, text=True, cwd=self.PROJECT_ROOT)
            output = (p.stdout + p.stderr).strip()
            if p.returncode != 0 and output:
                print(output, file=sys.stderr)
            return p.returncode != 0
        if ext == '.pyj':
            p = subprocess.run([self._rapydscript_executable(), 'lint', f], capture_output=True, text=True)
            output = (p.stdout + p.stderr).strip()
            if p.returncode != 0 and output:
                print(output, file=sys.stderr)
            return p.returncode != 0
        return False

    def run(self, opts):
        no_editor = opts.no_editor
        self.auto_fix = opts.fix
        cli_args = opts.cli_args

        python_exts = {'.py', '.pyi', '.recipe'}
        wn_path = os.path.expanduser('~/work/srv/main/static')
        has_changelog = os.path.exists(wn_path) and not cli_args

        if cli_args:
            ruff_targets = []
            rapydscript_targets = []
            for f in cli_args:
                ext = os.path.splitext(f)[1]
                if ext in python_exts:
                    ruff_targets.append(f)
                elif ext == '.pyj':
                    rapydscript_targets.append(f)
                else:
                    ruff_targets.append(f)
                    rapydscript_targets.append(f)
        else:
            ruff_targets = ['.']
            rapydscript_targets = [self.j(self.SRC, 'pyj')]

        with concurrent.futures.ThreadPoolExecutor() as ex:
            futures = {}
            if ruff_targets:
                futures['ruff'] = ex.submit(self._run_ruff, ruff_targets)
            if rapydscript_targets:
                futures['rapydscript'] = ex.submit(self._run_rapydscript, rapydscript_targets)
            if has_changelog:
                futures['changelog'] = ex.submit(self._run_changelog, wn_path)
            results = {name: f.result() for name, f in futures.items()}

        ruff_rc, ruff_output, ruff_files = results.get('ruff', (0, '', set()))
        rs_rc, rs_output, rs_files = results.get('rapydscript', (0, '', set()))
        cl_rc, cl_output = results.get('changelog', (0, ''))

        if ruff_output:
            print(ruff_output, file=sys.stderr)
        if rs_output:
            print(rs_output, file=sys.stderr)
        if cl_output:
            print(cl_output, file=sys.stderr)

        had_errors = ruff_rc != 0 or rs_rc != 0 or cl_rc != 0

        if no_editor:
            raise SystemExit(1 if had_errors else 0)

        # Errors that can't be resolved by opening a file in the editor
        unresolvable = cl_rc != 0
        if ruff_rc != 0 and not ruff_files:
            unresolvable = True
        if rs_rc != 0 and not rs_files:
            unresolvable = True

        for f in sorted(ruff_files | rs_files):
            try:
                edit_file(f)
            except FileNotFoundError:
                raise SystemExit(1)
            if self._check_file(f):
                raise SystemExit(1)

        if unresolvable:
            raise SystemExit(1)


class CheckAll(Command):
    description = 'Perform every quality code test suite'
    usage_help = 'To check specific files, specify them as command line arguments'

    sub_commands = [
        'type_check',
        'check',
        'fmt',
    ]


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
