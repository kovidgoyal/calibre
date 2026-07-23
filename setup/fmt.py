#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>


import subprocess

from setup import Command, iswindows


class AutoFormat(Command):
    description = 'Autoformat source code'
    usage_help = 'To format specific files specify them on the command line'
    require_venv = True

    def add_options(self, parser):
        parser.add_option('--check-only', default=False, action='store_true', help='Only check for formatting issues dont fix them')

    def run(self, opts):
        rapydscript = self.j(self.PROJECT_ROOT, '.venv/bin/rapydscript')
        ruff = self.j(self.PROJECT_ROOT, '.venv/bin/ruff')
        if iswindows:
            rapydscript += '.exe'
            ruff += '.exe'
        py_files = pyj_files = ()
        if opts.cli_args:
            pyj_files = tuple(x for x in opts.cli_args if x.endswith('.pyj'))
            py_files = tuple(x for x in opts.cli_args if x.endswith(('.py', '.recipe')))
            if not pyj_files and not py_files:
                return
        import tomllib

        with open(self.j(self.PROJECT_ROOT, 'pyproject.toml')) as f:
            m = tomllib.loads(f.read())
            line_length = m['tool']['ruff']['line-length']
        print('Formatting Python files...')
        cmd = [ruff, 'check', '--fix-only']
        if opts.check_only:
            cmd.append('--diff')
        fp = subprocess.run(cmd + list(py_files), cwd=self.PROJECT_ROOT)
        cmd = [ruff, 'format']
        if opts.check_only:
            cmd.append('--check')
        pp = subprocess.run(cmd + list(py_files), cwd=self.PROJECT_ROOT)
        print('Formatting RapydScript files...')
        cmd = [rapydscript, 'fmt', '--line-length', str(line_length)]
        if opts.check_only:
            cmd.append('--check-only')
        cp = subprocess.run(cmd + (list(pyj_files) or ['src/pyj']), cwd=self.PROJECT_ROOT)
        if fp.returncode != 0 or cp.returncode != 0 or pp.returncode != 0:
            raise SystemExit(1)
