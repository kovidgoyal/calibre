# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>, ' \
                '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import errno, os, sys, subprocess, shutil, re
from functools import partial

from calibre.ebooks import ConversionError, DRMError
from calibre.ptempfile import PersistentTemporaryFile
from calibre.constants import (isosx, iswindows, islinux, isbsd,
            filesystem_encoding)
from calibre import CurrentDir

PDFTOHTML = 'pdftohtml'
popen = subprocess.Popen
if isosx and hasattr(sys, 'frameworks_dir'):
    PDFTOHTML = os.path.join(getattr(sys, 'frameworks_dir'), PDFTOHTML)
if iswindows and hasattr(sys, 'frozen'):
    PDFTOHTML = os.path.join(os.path.dirname(sys.executable), 'pdftohtml.exe')
    popen = partial(subprocess.Popen, creationflags=0x08) # CREATE_NO_WINDOW=0x08 so that no ugly console is popped up
if (islinux or isbsd) and getattr(sys, 'frozen', False):
    PDFTOHTML = os.path.join(sys.executables_location, 'bin', 'pdftohtml')

def pdftohtml(output_dir, pdf_path, no_images):
    '''
    Convert the pdf into html using the pdftohtml app.
    This will write the html as index.html into output_dir.
    It will also write all extracted images to the output_dir
    '''

    pdfsrc = os.path.join(output_dir, u'src.pdf')
    index = os.path.join(output_dir, u'index.html')

    with open(pdf_path, 'rb') as src, open(pdfsrc, 'wb') as dest:
        shutil.copyfileobj(src, dest)

    with CurrentDir(output_dir):
        # This is necessary as pdftohtml doesn't always (linux) respect
        # absolute paths. Also, it allows us to safely pass only bytestring
        # arguments to subprocess on widows

        # subprocess in python 2 cannot handle unicode arguments on windows
        # that cannot be encoded with mbcs. Ensure all args are
        # bytestrings.
        def a(x):
            return os.path.basename(x).encode('ascii')

        exe = PDFTOHTML.encode(filesystem_encoding) if isinstance(PDFTOHTML,
                unicode) else PDFTOHTML

        cmd = [exe, b'-enc', b'UTF-8', b'-noframes', b'-p', b'-nomerge',
                b'-nodrm', b'-q', a(pdfsrc), a(index)]

        if isbsd:
            cmd.remove(b'-nodrm')
        if no_images:
            cmd.append(b'-i')

        logf = PersistentTemporaryFile(u'pdftohtml_log')
        try:
            p = popen(cmd, stderr=logf._fd, stdout=logf._fd,
                    stdin=subprocess.PIPE)
        except OSError as err:
            if err.errno == errno.ENOENT:
                raise ConversionError(
                    _('Could not find pdftohtml, check it is in your PATH'))
            else:
                raise

        while True:
            try:
                ret = p.wait()
                break
            except OSError as e:
                if e.errno == errno.EINTR:
                    continue
                else:
                    raise
        logf.flush()
        logf.close()
        out = open(logf.name, 'rb').read().strip()
        try:
            os.remove(pdfsrc)
        except:
            pass
        if ret != 0:
            raise ConversionError(out)
        if out:
            print "pdftohtml log:"
            print out
        if not os.path.exists(index) or os.stat(index).st_size < 100:
            raise DRMError()

        with open(index, 'r+b') as i:
            raw = i.read()
            raw = flip_images(raw)
            raw = '<!-- created by calibre\'s pdftohtml -->\n' + raw
            i.seek(0)
            i.truncate()
            # versions of pdftohtml >= 0.20 output self closing <br> tags, this
            # breaks the pdf heuristics regexps, so replace them
            i.write(raw.replace(b'<br/>', b'<br>'))

def flip_image(img, flip):
    from calibre.utils.magick import Image
    im = Image()
    im.open(img)
    if b'x' in flip:
        im.flip(True)
    if b'y' in flip:
        im.flip()
    im.save(img)

def flip_images(raw):
    for match in re.finditer(b'<IMG[^>]+/?>', raw):
        img = match.group()
        m = re.search(br'class="(x|y|xy)flip"', img)
        if m is None: continue
        flip = m.group(1)
        src = re.search(br'src="([^"]+)"', img)
        if src is None: continue
        img = src.group(1)
        if not os.path.exists(img): continue
        print ('Flipping image %s: %s'%(img, flip))
        flip_image(img, flip)
    raw = re.sub(br'<STYLE.+?</STYLE>\s*', b'', raw, flags=re.I|re.DOTALL)
    return raw

