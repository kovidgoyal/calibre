# -*- coding: utf-8 -*-
from __future__ import with_statement

__license__ = 'GPL 3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>, ' \
                '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import errno, os, re, sys, subprocess
from functools import partial

from calibre.ebooks import ConversionError, DRMError
from calibre import isosx, iswindows, islinux
from calibre import CurrentDir
from calibre.ptempfile import TemporaryDirectory

PDFTOHTML = 'pdftohtml'
popen = subprocess.Popen
if isosx and hasattr(sys, 'frameworks_dir'):
    PDFTOHTML = os.path.join(getattr(sys, 'frameworks_dir'), PDFTOHTML)
if iswindows and hasattr(sys, 'frozen'):
    PDFTOHTML = os.path.join(os.path.dirname(sys.executable), 'pdftohtml.exe')
    popen = partial(subprocess.Popen, creationflags=0x08) # CREATE_NO_WINDOW=0x08 so that no ugly console is popped up
if islinux and getattr(sys, 'frozen_path', False):
    PDFTOHTML = os.path.join(getattr(sys, 'frozen_path'), 'pdftohtml')

def pdftohtml(pdf_path):
    '''
    Convert the pdf into html using the pdftohtml app.
    @return: The HTML as a unicode string.
    '''

    if isinstance(pdf_path, unicode):
        pdf_path = pdf_path.encode(sys.getfilesystemencoding())
    if not os.access(pdf_path, os.R_OK):
        raise ConversionError, 'Cannot read from ' + pdf_path

    with TemporaryDirectory('_pdftohtml') as tdir:
        index = os.path.join(tdir, 'index.html')
        # This is neccessary as pdftohtml doesn't always (linux) respect absolute paths
        pdf_path = os.path.abspath(pdf_path)
        cmd = (PDFTOHTML, '-enc', 'UTF-8', '-noframes', '-p', '-nomerge', '-i', '-q', pdf_path, os.path.basename(index))
        cwd = os.getcwd()

        with CurrentDir(tdir):
            try:
                p = popen(cmd, stderr=subprocess.PIPE)
            except OSError, err:
                if err.errno == 2:
                    raise ConversionError(_('Could not find pdftohtml, check it is in your PATH'), True)
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

            if ret != 0:
                err = p.stderr.read()
                raise ConversionError, err
            if not os.path.exists(index) or os.stat(index).st_size < 100:
                raise DRMError()
        
            with open(index, 'rb') as i:
                raw = i.read()
            if not '<br' in raw[:4000]:
                raise ConversionError(os.path.basename(pdf_path) + _(' is an image based PDF. Only conversion of text based PDFs is supported.'), True)

            return '<!-- created by calibre\'s pdftohtml -->\n' + raw
