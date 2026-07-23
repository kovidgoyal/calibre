#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>


import subprocess

from setup import Command, iswindows


class AutoFormat(Command):
    description = 'Autoformat source code'
    usage_help = 'To format specific files specify them on the command line'
    require_venv = True

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
        cp = subprocess.run([ruff, 'format', '--extension', 'recipe:python'] + list(py_files), cwd=self.PROJECT_ROOT)
        if cp.returncode != 0:
            raise SystemExit(cp.returncode)
        print('Formatting RapydScript files...')
        cp = subprocess.run([rapydscript, 'fmt', '--line-length', str(line_length)] + (list(pyj_files) or ['src/pyj']), cwd=self.PROJECT_ROOT)
        if cp.returncode != 0:
            raise SystemExit(cp.returncode)
