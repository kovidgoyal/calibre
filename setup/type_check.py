#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import shutil
import subprocess

from setup import Command, is_ci


class TypeCheck(Command):

    description = 'Run the ty type checker over the calibre source code'
    usage_help = 'To type check specific files, specify them as command line arguments'

    @property
    def project_root(self):
        return self.d(self.SRC)

    @property
    def venv_dir(self):
        return self.j(self.project_root, '.venv')

    def ensure_venv(self):
        if not self.e(self.venv_dir):
            subprocess.check_call(['uv', 'venv'], cwd=self.project_root)
        deps = subprocess.check_output(['uv', 'pip', 'compile', 'pyproject.toml', '--group', 'dev'], cwd=self.project_root)
        subprocess.run(['uv', 'pip', 'sync', '-'], check=True, input=deps, cwd=self.project_root)

    def run(self, opts):
        if not is_ci:
            self.ensure_venv()
        ty = shutil.which('ty') or '.venv/bin/ty'
        cp = subprocess.run([ty, 'check'] + list(opts.cli_args), cwd=self.project_root)
        if cp.returncode != 0:
            raise SystemExit(cp.returncode)
