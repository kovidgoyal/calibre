#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import glob
import os
import re
import subprocess

from setup import Command


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

    def patch_qt_stubs(self, version: int = 1):
        def patch(mod: str, changes: dict[str, list[str]]) -> str:
            core = glob.glob(f'.venv/lib/python*/site-packages/PyQt*/{mod}.pyi')[0]
            with open(core) as f:
                raw = f.read()
            sentinel = f'# calibre-patch-version: {version}'
            if raw.startswith(sentinel):
                return
            raw = sentinel + '\n' + raw
            prefix = '\n    '
            for cls, lines in changes.items():
                if cls.startswith('!'):
                    raw = re.sub(cls[1:], lines[0], raw)
                    continue
                body = prefix.join(lines)
                raw = re.sub(rf'(class {cls}\(.+)', rf'\1{prefix}{body}', raw)
            os.unlink(core)  # uv uses hard links apparently
            with open(core, 'w') as f:
                f.write(raw)
        patch('QtCore', {
            'QByteArray': ['def __buffer__(self, flags: int, /) -> memoryview: ...'],
            '!' + re.escape("def connect(self, slot: 'PYQT_SLOT') -> 'QMetaObject.Connection': ..."):
            ["def connect(self, slot: 'PYQT_SLOT', type: Qt.ConnectionType = ...) -> 'QMetaObject.Connection': ..."],
        })
        patch('QtGui', {
            'QIcon': '''\
@classmethod
def ic(cls, name: str, fallback: bytes = b'') -> QIcon: ...

@classmethod
def icon_as_png(cls, name: str, as_bytearray: bool = False, compression_level: int = 9) -> QIcon: ...

@classmethod
def cached_icon(cls, name: str) -> QIcon: ...

def is_ok(self) -> bool: ...

'''.splitlines(),
            'QPalette': '''\
def is_dark_theme(self) -> bool: ...
def serialize_as_bytes(self) -> bytes: ...
def serialize_as_python(self) -> str: ...
def unserialize_from_bytes(self, b: bytes) -> None: ...
'''.splitlines(),
        })
        patch('QtWidgets', {'QWidget': '''\
def save_geometry(self, prefs: Prefs, name: str) -> None: ...
def restore_geometry(self, prefs: Prefs, name: str, get_legacy_saved_geometry: typing.Callable[[], bytes] | None = None) -> bool: ...
def saveGeometry(self) -> QByteArray: ...
def raise_and_focus(self) -> None: ...
def raise_without_focus(self) -> None: ...
'''.splitlines()})

    def run(self, opts):
        self.ensure_venv()
        ty = os.path.abspath('.venv/bin/ty')
        self.patch_qt_stubs()
        cp = subprocess.run([ty, 'check'] + list(opts.cli_args), cwd=self.project_root)
        if cp.returncode != 0:
            raise SystemExit(cp.returncode)
