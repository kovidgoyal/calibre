#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

import os
import sys
import tempfile
from posixpath import normpath
from qt.core import QFile, QIODevice

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
    subdirs = ['images']
    for sb in subdirs:
        lines += [f'[{sb}]', f'Size={sz}', f'MinSize={min_sz}', f'MaxSize={max_sz}', '']
    return '\n'.join(lines)


def compile_icon_dir_as_themes(
    path_to_dir, output_path, theme_name='calibre-default', inherits='',
    for_theme='any', prefix='/icons',
):
    with tempfile.TemporaryDirectory(dir=path_to_dir) as tdir, open(os.path.join(tdir, 'icons.qrc'), 'w') as qrc:
        print('<RCC>', file=qrc)
        print(f'  <qresource prefix="{prefix}">', file=qrc)

        def file(name):
            name = name.replace('\\', '/')
            print(f'    <file>{normpath(name)}</file>', file=qrc)

        specific_themes = []
        if for_theme == 'any':
            specific_themes = [theme_name + '-dark', theme_name + '-light']
        for q in [theme_name] + specific_themes:
            os.mkdir(os.path.join(tdir, q))
            for sd in ['images']:
                os.makedirs(os.path.join(tdir, q, sd))
        with open(os.path.join(tdir, theme_name, 'index.theme'), 'w') as f:
            f.write(index_theme(theme_name, inherits))
            file(f'{theme_name}/index.theme')
        for q in specific_themes:
            with open(os.path.join(tdir, q, 'index.theme'), 'w') as f:
                f.write(index_theme(q, inherits=theme_name))
                file(f'{q}/index.theme')

        def handle_image(image_path):
            image_name = os.path.basename(image_path)
            rp = os.path.relpath(os.path.dirname(image_path), path_to_dir).replace('\\', '/').strip('/').replace('/', '__')
            if rp == '.':
                rp = ''
            else:
                rp += '__'
            base, ext = os.path.splitext(image_name)
            theme_dir = theme_name
            dest_name = image_name
            if ext.lower() not in ('.png',):
                if image_name == 'metadata.json':
                    dest = theme_dir, dest_name
                    os.link(image_path, os.path.join(tdir, *dest))
                    file('/'.join(dest))
                return
            if base.endswith('-for-dark-theme'):
                if for_theme == 'any':
                    theme_dir += '-dark'
                elif for_theme == 'light':
                    return
                dest_name = dest_name.replace('-for-dark-theme', '')
            elif base.endswith('-for-light-theme'):
                if for_theme == 'any':
                    theme_dir += '-light'
                elif for_theme == 'dark':
                    return
                dest_name = dest_name.replace('-for-light-theme', '')
            dest = theme_dir, 'images', (rp + dest_name)
            os.link(image_path, os.path.join(tdir, *dest))
            file('/'.join(dest))

        for dirpath, dirnames, filenames in os.walk(path_to_dir):
            if 'textures' in dirnames:
                dirnames.remove('textures')
            if os.path.basename(tdir) in dirnames:
                dirnames.remove(os.path.basename(tdir))
            for f in filenames:
                handle_image(os.path.join(dirpath, f))

        print('  </qresource>', file=qrc)
        print('</RCC>', file=qrc)
        qrc.close()
        # input(tdir)
        compile_qrc(output_path, qrc.name)
