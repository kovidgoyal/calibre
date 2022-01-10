#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

import os
import sys
import tempfile
from posixpath import normpath
from qt.core import QFile, QIODevice

from calibre.constants import icons_subdirs
from calibre_extensions import rcc_backend


def compile_qrc(output_path, *qrc_file_paths):
    rcc = rcc_backend.RCCResourceLibrary()
    err_device = QFile()
    if not err_device.open(sys.stderr.fileno(), QIODevice.OpenModeFlag.WriteOnly | QIODevice.OpenModeFlag.Text):
        raise ValueError('Failed to open STDERR for writing')
    if not qrc_file_paths:
        raise TypeError('Must specify at least one .qrc file')
    rcc.setInputFiles(list(qrc_file_paths))
    if not rcc.readFiles(False, err_device):
        raise ValueError('Failed to read qrc files')
    with open(output_path, 'wb') as f:
        out = QFile(output_path)
        if not out.open(f.fileno(), QIODevice.OpenModeFlag.WriteOnly):
            raise RuntimeError(f'Failed to open {output_path} for writing')
        ok = rcc.output(out, QFile(), err_device)
    if not ok:
        os.remove(output_path)
        raise ValueError('Failed to write output')


def index_theme(name, inherits=''):
    min_sz, sz, max_sz = 16, 128, 512
    lines = ['[Icon Theme]', f'Name={name}', 'Comment=Icons for calibre']
    if inherits:
        lines.append(f'Inherits={inherits}')
    lines.append('')
    subdirs = ['images'] + [f'images/{x}' for x in icons_subdirs]
    for sb in subdirs:
        lines += [f'[{sb}]', f'Size={sz}', f'MinSize={min_sz}', f'MaxSize={max_sz}', '']
    return '\n'.join(lines)


def compile_icon_dir_as_themes(path_to_dir, output_path, theme_name='calibre-default', inherits='', prefix='/icons'):
    with tempfile.TemporaryDirectory(dir=path_to_dir) as tdir, open(os.path.join(tdir, 'icons.qrc'), 'w') as qrc:
        print('<RCC>', file=qrc)
        print(f'  <qresource prefix="{prefix}">', file=qrc)

        def file(name):
            print(f'    <file>{normpath(name)}</file>', file=qrc)

        for q in (theme_name, theme_name + '-dark', theme_name + '-light'):
            os.mkdir(os.path.join(tdir, q))
            for sd in ['images'] + [f'images/{x}' for x in icons_subdirs]:
                os.makedirs(os.path.join(tdir, q, sd))
        with open(os.path.join(tdir, theme_name, 'index.theme'), 'w') as f:
            f.write(index_theme(theme_name, inherits))
            file(f'{theme_name}/index.theme')
        for q in (theme_name + '-dark', theme_name + '-light'):
            with open(os.path.join(tdir, q, 'index.theme'), 'w') as f:
                f.write(index_theme(q, inherits=theme_name))
                file(f'{q}/index.theme')

        for sdir in ('.',) + icons_subdirs:
            s = os.path.join(path_to_dir, sdir)
            for x in os.listdir(s):
                base, ext = os.path.splitext(x)
                if ext.lower() not in ('.png',):
                    continue
                theme_dir = theme_name
                dest_name = x
                if base.endswith('-for-dark-theme'):
                    theme_dir += '-dark'
                    dest_name = x.replace('-for-dark-theme', '')
                elif base.endswith('-for-light-theme'):
                    theme_dir += '-light'
                    dest_name = x.replace('-for-light-theme', '')
                dest = theme_dir, 'images', sdir, dest_name
                os.link(os.path.join(s, x), os.path.join(tdir, *dest))
                file('/'.join(dest))
        print('  </qresource>', file=qrc)
        print('</RCC>', file=qrc)
        qrc.close()
        # input(tdir)
        compile_qrc(output_path, qrc.name)
