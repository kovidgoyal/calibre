#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

import os
import sys
from qt.core import QFile, QIODevice

from calibre_extensions import rcc_backend


def compile_qrc(output_path, *qrc_file_paths):
    rcc = rcc_backend.RCCResourceLibrary()
    err_device = QFile()
    if not err_device.open(sys.stderr.fileno(), QIODevice.OpenModeFlag.WriteOnly | QIODevice.OpenModeFlag.Text):
        raise ValueError('Failed to open stderr for writing')
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
