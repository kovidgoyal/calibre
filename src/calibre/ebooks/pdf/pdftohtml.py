# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>, ' \
                '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import errno
import os
import sys
import subprocess
from functools import partial

from calibre.ebooks import ConversionError, DRMError
from calibre.ptempfile import PersistentTemporaryFile
from calibre import isosx, iswindows, islinux, isfreebsd
from calibre import CurrentDir

PDFTOHTML = 'pdftohtml'
popen = subprocess.Popen
if isosx and hasattr(sys, 'frameworks_dir'):
    PDFTOHTML = os.path.join(getattr(sys, 'frameworks_dir'), PDFTOHTML)
if iswindows and hasattr(sys, 'frozen'):
    PDFTOHTML = os.path.join(os.path.dirname(sys.executable), 'pdftohtml.exe')
    popen = partial(subprocess.Popen, creationflags=0x08) # CREATE_NO_WINDOW=0x08 so that no ugly console is popped up
if (islinux or isfreebsd) and getattr(sys, 'frozen', False):
    PDFTOHTML = os.path.join(sys.executables_location, 'bin', 'pdftohtml')

def pdftohtml(output_dir, pdf_path, no_images):
    '''
    Convert the pdf into html using the pdftohtml app.
    This will write the html as index.html into output_dir.
    It will also wirte all extracted images to the output_dir
    '''

    if isinstance(pdf_path, unicode):
        pdf_path = pdf_path.encode(sys.getfilesystemencoding())
    if not os.access(pdf_path, os.R_OK):
        raise ConversionError('Cannot read from ' + pdf_path)

    with CurrentDir(output_dir):
        index = os.path.join(os.getcwd(), 'index.html')
        # This is neccessary as pdftohtml doesn't always (linux) respect absolute paths
        pdf_path = os.path.abspath(pdf_path)
        cmd = [PDFTOHTML, '-enc', 'UTF-8', '-noframes', '-p', '-nomerge', '-nodrm', '-q', pdf_path, os.path.basename(index)]
        if no_images:
            cmd.append('-i')

        logf = PersistentTemporaryFile('pdftohtml_log')
        try:
            p = popen(cmd, stderr=logf._fd, stdout=logf._fd,
                    stdin=subprocess.PIPE)
        except OSError, err:
            if err.errno == 2:
                raise ConversionError(_('Could not find pdftohtml, check it is in your PATH'))
            else:
                raise

        while True:
            try:
                ret = p.wait()
                break
            except OSError, e:
                if e.errno == errno.EINTR:
                    continue
                else:
                    raise
        logf.flush()
        logf.close()
        out = open(logf.name, 'rb').read()
        if ret != 0:
            raise ConversionError(out)
        print "pdftohtml log:"
        print out
        if not os.path.exists(index) or os.stat(index).st_size < 100:
            raise DRMError()

        with open(index, 'r+b') as i:
            raw = i.read()
            raw = '<!-- created by calibre\'s pdftohtml -->\n' + raw
            i.seek(0)
            i.truncate()
            i.write(raw)
