# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>, ' \
                '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import errno, os, sys, subprocess, shutil, re
from functools import partial

from calibre.ebooks import ConversionError, DRMError
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ptempfile import PersistentTemporaryFile
from calibre.constants import (isosx, iswindows, islinux, isbsd,
            filesystem_encoding)
from calibre import CurrentDir
from calibre.utils.cleantext import clean_xml_chars

PDFTOHTML = 'pdftohtml'
popen = subprocess.Popen
if isosx and hasattr(sys, 'frameworks_dir'):
    PDFTOHTML = os.path.join(getattr(sys, 'frameworks_dir'), PDFTOHTML)
if iswindows and hasattr(sys, 'frozen'):
    base = sys.extensions_location if hasattr(sys, 'new_app_layout') else os.path.dirname(sys.executable)
    PDFTOHTML = os.path.join(base, 'pdftohtml.exe')
    popen = partial(subprocess.Popen, creationflags=0x08)  # CREATE_NO_WINDOW=0x08 so that no ugly console is popped up
if (islinux or isbsd) and getattr(sys, 'frozen', False):
    PDFTOHTML = os.path.join(sys.executables_location, 'bin', 'pdftohtml')


def pdftohtml(output_dir, pdf_path, no_images, as_xml=False):
    '''
    Convert the pdf into html using the pdftohtml app.
    This will write the html as index.html into output_dir.
    It will also write all extracted images to the output_dir
    '''

    pdfsrc = os.path.join(output_dir, u'src.pdf')
    index = os.path.join(output_dir, u'index.'+('xml' if as_xml else 'html'))

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
                b'-nodrm', a(pdfsrc), a(index)]

        if isbsd:
            cmd.remove(b'-nodrm')
        if no_images:
            cmd.append(b'-i')
        if as_xml:
            cmd.append('-xml')

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
        if ret != 0:
            raise ConversionError(b'pdftohtml failed with return code: %d\n%s' % (ret, out))
        if out:
            print "pdftohtml log:"
            print out
        if not os.path.exists(index) or os.stat(index).st_size < 100:
            raise DRMError()

        if not as_xml:
            with lopen(index, 'r+b') as i:
                raw = i.read()
                raw = flip_images(raw)
                raw = '<!-- created by calibre\'s pdftohtml -->\n' + raw
                i.seek(0)
                i.truncate()
                # versions of pdftohtml >= 0.20 output self closing <br> tags, this
                # breaks the pdf heuristics regexps, so replace them
                raw = raw.replace(b'<br/>', b'<br>')
                raw = re.sub(br'<a\s+name=(\d+)', br'<a id="\1"', raw, flags=re.I)
                raw = re.sub(br'<a id="(\d+)"', br'<a id="p\1"', raw, flags=re.I)
                raw = re.sub(br'<a href="index.html#(\d+)"', br'<a href="#p\1"', raw, flags=re.I)

                i.write(raw)

            cmd = [exe, b'-f', b'1', '-l', '1', b'-xml', b'-i', b'-enc', b'UTF-8', b'-noframes', b'-p', b'-nomerge',
                    b'-nodrm', b'-q', b'-stdout', a(pdfsrc)]
            p = popen(cmd, stdout=subprocess.PIPE)
            raw = p.stdout.read().strip()
            if p.wait() == 0 and raw:
                parse_outline(raw, output_dir)

            if isbsd:
                cmd.remove(b'-nodrm')

        try:
            os.remove(pdfsrc)
        except:
            pass


def parse_outline(raw, output_dir):
    from lxml import etree
    from calibre.ebooks.oeb.parse_utils import RECOVER_PARSER
    raw = clean_xml_chars(xml_to_unicode(raw, strip_encoding_pats=True, assume_utf8=True)[0])
    outline = etree.fromstring(raw, parser=RECOVER_PARSER).xpath('(//outline)[1]')
    if outline:
        from calibre.ebooks.oeb.polish.toc import TOC, create_ncx
        outline = outline[0]
        toc = TOC()
        count = [0]

        def process_node(node, toc):
            for child in node.iterchildren('*'):
                if child.tag == 'outline':
                    parent = toc.children[-1] if toc.children else toc
                    process_node(child, parent)
                else:
                    if child.text:
                        page = child.get('page', '1')
                        toc.add(child.text, 'index.html', 'p' + page)
                        count[0] += 1
        process_node(outline, toc)
        if count[0] > 2:
            root = create_ncx(toc, (lambda x:x), 'pdftohtml', 'en', 'pdftohtml')
            with open(os.path.join(output_dir, 'toc.ncx'), 'wb') as f:
                f.write(etree.tostring(root, pretty_print=True, with_tail=False, encoding='utf-8', xml_declaration=True))


def flip_image(img, flip):
    from calibre.utils.img import flip_image, image_and_format_from_data, image_to_data
    with lopen(img, 'r+b') as f:
        img, fmt = image_and_format_from_data(f.read())
        img = flip_image(img, horizontal=b'x' in flip, vertical=b'y' in flip)
        f.seek(0), f.truncate()
        f.write(image_to_data(img, fmt=fmt))


def flip_images(raw):
    for match in re.finditer(b'<IMG[^>]+/?>', raw, flags=re.I):
        img = match.group()
        m = re.search(br'class="(x|y|xy)flip"', img)
        if m is None:
            continue
        flip = m.group(1)
        src = re.search(br'src="([^"]+)"', img)
        if src is None:
            continue
        img = src.group(1)
        if not os.path.exists(img):
            continue
        flip_image(img, flip)
    raw = re.sub(br'<STYLE.+?</STYLE>\s*', b'', raw, flags=re.I|re.DOTALL)
    return raw
