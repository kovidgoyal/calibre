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

    def fix_self_in_qt_stubs(self) -> None:
        # The PyQt stub generator (sip >= 6.17) replaces all references to the
        # enclosing class with typing.Self, which is wrong, for example,
        # QWidget.__init__(parent: typing.Self) means a QDialog can only have
        # a QDialog as its parent. It also drops the | None for pointer
        # types. Replace typing.Self with the actual class name, adding |
        # None for QObject sub-classes and parameters with default values.
        stubs = glob.glob('.venv/lib/python*/site-packages/PyQt*/*.pyi')
        class_pat = re.compile(r'^(\s*)class (\w+)(?:\((.*)\))?:', re.MULTILINE)
        bases: dict[str, list[str]] = {}
        sources: dict[str, str] = {}
        for path in stubs:
            with open(path) as f:
                sources[path] = raw = f.read()
            for m in class_pat.finditer(raw):
                bases.setdefault(m.group(2), []).extend(x.strip().rpartition('.')[2] for x in (m.group(3) or '').split(','))

        def is_qobject(name: str, seen: frozenset[str] = frozenset()) -> bool:
            if name == 'QObject':
                return True
            if name in seen:
                return False
            return any(is_qobject(b, seen | {name}) for b in bases.get(name, ()))

        for path, raw in sources.items():
            if 'typing.Self' not in raw:
                continue
            stack: list[tuple[int, str]] = []
            lines = raw.splitlines(keepends=True)
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                indent = len(line) - len(line.lstrip())
                while stack and stack[-1][0] >= indent:
                    stack.pop()
                if m := class_pat.match(line):
                    stack.append((indent, m.group(2)))
                    continue
                if not stack or 'typing.Self' not in line:
                    continue
                qualname = '.'.join(x[1] for x in stack)
                nullable = f'{qualname} | None'
                ptr = nullable if is_qobject(stack[-1][1]) else qualname
                params, sep, ret = line.rpartition(' -> ')
                if not sep:
                    params, ret = line, ''
                params = re.sub(r': typing\.Self = ', f': {nullable} = ', params)
                params = re.sub(r': typing\.Self\b', f': {ptr}', params)
                ret = re.sub(r'^typing\.Self:', f'{ptr}:', ret)
                lines[i] = (params + sep + ret).replace('typing.Self', qualname)
            q = ''.join(lines)
            if q != raw:
                os.unlink(path)  # uv uses hard links apparently
                with open(path, 'w') as f:
                    f.write(q)

    def patch_qt_stubs(self, version: int = 2):
        def patch(mod: str, changes: dict[str, list[str]]) -> str:
            core = glob.glob(f'.venv/lib/python*/site-packages/PyQt*/{mod}.pyi')[0]
            with open(core) as f:
                raw = f.read()
            sentinel = f'# calibre-patch-version: {version}'
            if raw.startswith(sentinel):
                return
            if raw.startswith('# calibre-patch-version: '):
                # Patched by an older version, strip the old sentinel, the patches below are idempotent
                raw = raw.partition('\n')[2]
            raw = sentinel + '\n' + raw
            prefix = '\n    '
            for cls, lines in changes.items():
                if cls.startswith('!'):
                    raw = re.sub(cls[1:], lines[0], raw)
                    continue
                body = prefix.join(lines)
                if prefix + body in raw:
                    continue
                raw = re.sub(rf'(class {cls}\(.+)', rf'\1{prefix}{body}', raw)
            os.unlink(core)  # uv uses hard links apparently
            with open(core, 'w') as f:
                f.write(raw)

        patch(
            'QtCore',
            {
                # pyqtSignal() does not require the arguments parameter
                '!' + re.escape(', arguments: collections.abc.Sequence[str]) -> None: ...'): [', arguments: collections.abc.Sequence[str] = ...) -> None: ...'],
            },
        )
        patch(
            'QtGui',
            {
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
            },
        )
        patch(
            'QtWidgets',
            {
                'QWidget': '''\
def save_geometry(self, prefs: Prefs, name: str) -> None: ...
def restore_geometry(self, prefs: Prefs, name: str, get_legacy_saved_geometry: typing.Callable[[], bytes] | None = None) -> bool: ...
def raise_and_focus(self) -> None: ...
def raise_without_focus(self) -> None: ...
'''.splitlines(),
            },
        )

    def run(self, opts):
        ty = self.j(self.PROJECT_ROOT, '.venv/bin/ty')
        if iswindows:
            ty += '.exe'
        self.fix_self_in_qt_stubs()
        self.patch_qt_stubs()
        cp = subprocess.run([ty, 'check'] + list(opts.cli_args), cwd=self.PROJECT_ROOT)
        if cp.returncode != 0:
            raise SystemExit(cp.returncode)
