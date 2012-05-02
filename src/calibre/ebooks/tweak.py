#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, shlex, subprocess

from calibre import prints, as_unicode, walk
from calibre.constants import iswindows, __appname__
from calibre.ptempfile import TemporaryDirectory
from calibre.libunzip import extract as zipextract
from calibre.utils.zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
from calibre.utils.ipc.simple_worker import WorkerError

class Error(ValueError):
    pass

def ask_cli_question(msg):
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
            try:
                ans = sys.stdin.read(1)
            except KeyboardInterrupt:
                ans = b''
        finally:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
    print()
    return ans == b'y'

def mobi_exploder(path, tdir, question=lambda x:True):
    from calibre.ebooks.mobi.tweak import explode, BadFormat
    try:
        return explode(path, tdir, question=question)
    except BadFormat as e:
        raise Error(as_unicode(e))

def zip_exploder(path, tdir, question=lambda x:True):
    zipextract(path, tdir)
    for f in walk(tdir):
        if f.lower().endswith('.opf'):
            return f
    raise Error('Invalid book: Could not find .opf')

def zip_rebuilder(tdir, path):
    with ZipFile(path, 'w', compression=ZIP_DEFLATED) as zf:
        # Write mimetype
        mt = os.path.join(tdir, 'mimetype')
        if os.path.exists(mt):
            zf.write(mt, 'mimetype', compress_type=ZIP_STORED)
        # Write everything else
        exclude_files = {'.DS_Store', 'mimetype', 'iTunesMetadata.plist'}
        for root, dirs, files in os.walk(tdir):
            for fn in files:
                if fn in exclude_files:
                    continue
                absfn = os.path.join(root, fn)
                zfn = os.path.relpath(absfn, tdir).replace(os.sep, '/')
                zf.write(absfn, zfn)

def get_tools(fmt):
    fmt = fmt.lower()

    if fmt in {'mobi', 'azw', 'azw3'}:
        from calibre.ebooks.mobi.tweak import rebuild
        ans = mobi_exploder, rebuild
    elif fmt in {'epub', 'htmlz'}:
        ans = zip_exploder, zip_rebuilder
    else:
        ans = None, None

    return ans

def tweak(ebook_file):
    ''' Command line interface to the Tweak Book tool '''
    fmt = ebook_file.rpartition('.')[-1].lower()
    exploder, rebuilder = get_tools(fmt)
    if exploder is None:
        prints('Cannot tweak %s files. Supported formats are: EPUB, HTMLZ, AZW3, MOBI'
                , file=sys.stderr)
        raise SystemExit(1)

    with TemporaryDirectory('_tweak_'+
            os.path.basename(ebook_file).rpartition('.')[0]) as tdir:
        try:
            opf = exploder(ebook_file, tdir, question=ask_cli_question)
        except WorkerError as e:
            prints('Failed to unpack', ebook_file)
            prints(e.orig_tb)
            raise SystemExit(1)
        except Error as e:
            prints(as_unicode(e), file=sys.stderr)
            raise SystemExit(1)

        if opf is None:
            # The question was answered with No
            return

        ed = os.environ.get('EDITOR', None)
        proceed = False
        if ed is None:
            prints('Book extracted to', tdir)
            prints('Make your tweaks and once you are done,', __appname__,
                    'will rebuild', ebook_file, 'from', tdir)
            print()
            proceed = ask_cli_question('Rebuild ' + ebook_file + '?')
        else:
            cmd = shlex.split(ed)
            try:
                subprocess.check_call(cmd + [tdir])
            except:
                prints(ed, 'failed, aborting...')
                raise SystemExit(1)
            proceed = True

        if proceed:
            prints('Rebuilding', ebook_file, 'please wait ...')
            try:
                rebuilder(tdir, ebook_file)
            except WorkerError as e:
                prints('Failed to rebuild', ebook_file)
                prints(e.orig_tb)
                raise SystemExit(1)
            prints(ebook_file, 'successfully tweaked')

