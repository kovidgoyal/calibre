#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, glob, sys, shlex, subprocess

from calibre import CurrentDir, as_unicode, prints
from calibre.ebooks.mobi import MobiError
from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.ebooks.mobi.reader.headers import MetadataHeader
from calibre.utils.logging import default_log
from calibre.ebooks import DRMError
from calibre.ebooks.mobi.reader.mobi8 import Mobi8Reader
from calibre.ebooks.conversion.plumber import Plumber, create_oebbook
from calibre.ptempfile import TemporaryDirectory
from calibre.constants import __appname__, iswindows
from calibre.customize.ui import (plugin_for_input_format,
        plugin_for_output_format)

class BadFormat(ValueError):
    pass

def explode(stream, dest, split_callback=lambda x:True):
    raw = stream.read(3)
    stream.seek(0)
    if raw == b'TPZ':
        raise BadFormat(_('This is not a MOBI file. It is a Topaz file.'))

    try:
        header = MetadataHeader(stream, default_log)
    except MobiError:
        raise BadFormat(_('This is not a MOBI file.'))

    if header.encryption_type != 0:
        raise DRMError(_('This file is locked with DRM. It cannot be tweaked.'))

    stream.seek(0)
    mr = MobiReader(stream, default_log, None, None)

    if mr.kf8_type is None:
        raise BadFormat('This MOBI file does not contain a KF8 format book')

    if mr.kf8_type == 'joint':
        if not split_callback(_('This MOBI file contains both KF8 and '
            'older Mobi6 data. Tweaking it will remove the Mobi6 data, which '
            ' means the file will not be usable on older Kindles. Are you '
            'sure?')):
            return None

    with CurrentDir(dest):
        mr = Mobi8Reader(mr, default_log)
        opf = os.path.abspath(mr())

    return opf

def rebuild(src_dir, dest_path):
    opf = glob.glob(os.path.join(src_dir, '*.opf'))
    if not opf:
        raise ValueError('No OPF file found in %s'%src_dir)
    opf = opf[0]
    plumber = Plumber(opf, dest_path, default_log)
    plumber.setup_options()
    inp = plugin_for_input_format('azw3')
    outp = plugin_for_output_format('azw3')

    plumber.opts.mobi_passthrough = True
    oeb = create_oebbook(default_log, opf, plumber.opts)
    outp.convert(oeb, dest_path, inp, plumber.opts, default_log)

def ask_question(msg):
    prints(msg, end=' [y/N]: ')
    sys.stdout.flush()

    if iswindows:
        import msvcrt
        ans = msvcrt.getch()
    else:
        import tty, termios
        old_settings = termios.tcgetattr(sys.stdin.fileno())
        try:
            tty.setraw(sys.stdin.fileno())
            ans = sys.stdin.read(1)
        finally:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
    print()
    return ans == b'y'

def tweak(mobi_file):
    with TemporaryDirectory('_tweak_'+os.path.basename(mobi_file)) as tdir:
        with open(mobi_file, 'rb') as stream:
            try:
                opf = explode(stream, tdir, split_callback=ask_question)
            except BadFormat as e:
                prints(as_unicode(e), file=sys.stderr)
                raise SystemExit(1)
        if opf is None:
            return

        ed = os.environ.get('EDITOR', None)
        proceed = False
        if ed is None:
            prints('KF8 extracted to', tdir)
            prints('Make your tweaks and once you are done,', __appname__,
                    'will rebuild', mobi_file, 'from', tdir)
            proceed = ask_question('Rebuild ' + mobi_file + '?')
        else:
            cmd = shlex.split(ed)
            try:
                subprocess.check_call(cmd + [tdir])
            except:
                prints(ed, 'failed, aborting...')
                raise SystemExit(1)
            proceed = True

        if proceed:
            rebuild(tdir, mobi_file)
            prints(mobi_file, 'successfully tweaked')

