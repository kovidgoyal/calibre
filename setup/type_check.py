#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import glob
import os
import re
import subprocess

from setup import Command, iswindows


class TypeCheck(Command):

    description = 'Run the ty type checker over the calibre source code'
    usage_help = 'To type check specific files, specify them as command line arguments'
    require_venv = True

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
            # QByteArray supports Buffer protocol
            'QByteArray': ['def __buffer__(self, flags: int, /) -> memoryview: ...'],

            # signal.connect() accepts type parameter
            '!' + re.escape("def connect(self, slot: 'PYQT_SLOT') -> 'QMetaObject.Connection': ..."):
            ["def connect(self, slot: 'PYQT_SLOT', type: Qt.ConnectionType = ...) -> 'QMetaObject.Connection': ..."],

            # QObject::findChild() can return None
            '!' + re.escape('def findChild(self, type: type[QObjectT], name: typing.Optional[str] = ..., options: Qt.FindChildOption = ...) -> QObjectT: ...'):
            ['def findChild(self, type: type[QObjectT], name: typing.Optional[str] = ..., options: Qt.FindChildOption = ...) -> QObjectT | None: ...'],
            '!' + re.escape(
                'def findChild(self, types: tuple[type[QObjectT], ...], name: typing.Optional[str] = ..., options: Qt.FindChildOption = ...) -> QObjectT: ...'):
            ['def findChild('
            'self, types: tuple[type[QObjectT], ...], name: typing.Optional[str] = ..., options: Qt.FindChildOption = ...) -> QObjectT | None: ...'],
        })
        patch('QtGui', {
            'QIcon': '''\
@classmethod
def ic(cls, name: str | QIcon | None, fallback: bytes = b'') -> QIcon: ...
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
        patch('QtWidgets', {
            # QLayout.getContentsMargins() never returns None
            '!' + re.escape('    def getContentsMargins(self) -> typing.Tuple['
            'typing.Optional[int], typing.Optional[int], typing.Optional[int], typing.Optional[int]]: ...'):
            ['    def getContentsMargins(self) -> typing.Tuple[int, int, int, int]: ...'],

            'QWidget': '''\
def save_geometry(self, prefs: Prefs, name: str) -> None: ...
def restore_geometry(self, prefs: Prefs, name: str, get_legacy_saved_geometry: typing.Callable[[], bytes] | None = None) -> bool: ...
def raise_and_focus(self) -> None: ...
def raise_without_focus(self) -> None: ...
'''.splitlines()})

    def run(self, opts):
        ty = self.j(self.PROJECT_ROOT, '.venv/bin/ty')
        if iswindows:
            ty += '.exe'
        self.patch_qt_stubs()
        cp = subprocess.run([ty, 'check'] + list(opts.cli_args), cwd=self.PROJECT_ROOT)
        if cp.returncode != 0:
            raise SystemExit(cp.returncode)
