#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, subprocess, tempfile

from calibre.constants import iswindows
from calibre.customize.ui import plugin_for_output_format
from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks.mobi.utils import detect_periodical
from calibre import CurrentDir

exe = 'kindlegen.exe' if iswindows else 'kindlegen'

def refactor_opf(opf, is_periodical):
    pass

def refactor_guide(oeb):
    for key in list(oeb.guide):
        if key not in ('toc', 'start'):
            oeb.guide.remove(key)

def run_kindlegen(opf, log):
    log.info('Running kindlegen on MOBIML created by calibre')
    oname = os.path.splitext(opf)[0] + '.mobi'
    with tempfile.NamedTemporaryFile('_kindlegen_output.txt') as tfile:
        p = subprocess.Popen([exe, opf, '-c1', '-verbose', '-o', oname],
            stderr=subprocess.STDOUT, stdout=tfile)
        returncode = p.wait()
        tfile.seek(0)
        log.debug('kindlegen verbose output:')
        log.debug(tfile.read())
        log.info('kindlegen returned returncode: %d'%returncode)
    if not os.path.exists(oname) or os.stat(oname).st_size < 100:
        raise RuntimeError('kindlegen did not produce any output. '
                'kindlegen return code: %d'%returncode)
    return oname

def kindlegen(oeb, opts, input_plugin, output_path):
    is_periodical = detect_periodical(oeb.toc, oeb.log)
    refactor_guide(oeb)
    with TemporaryDirectory('_epub_output') as tdir:
        oeb_output = plugin_for_output_format('oeb')
        oeb_output.convert(oeb, tdir, input_plugin, opts, oeb.log)
        opf = [x for x in os.listdir(tdir) if x.endswith('.opf')][0]
        refactor_opf(opf, is_periodical)
        with CurrentDir(tdir):
            run_kindlegen(opf, oeb.log)

