#!/usr/bin/env python
# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>

import errno
import os
import re
import shutil
import subprocess

from calibre import CurrentDir, prints, xml_replace_entities
from calibre.constants import bundled_binaries_dir, isbsd, iswindows
from calibre.ebooks import ConversionError, DRMError
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.cleantext import clean_xml_chars
from calibre.utils.ipc import eintr_retry_call

PDFTOHTML = 'pdftohtml' + ('.exe' if iswindows else '')
creationflags = subprocess.DETACHED_PROCESS if iswindows else 0


def popen(cmd, **kw):
    if iswindows:
        kw['creationflags'] = creationflags
    return subprocess.Popen(cmd, **kw)


if bbd := bundled_binaries_dir():
    PDFTOHTML = os.path.join(bbd, PDFTOHTML)
PDFTOTEXT = os.path.join(os.path.dirname(PDFTOHTML), 'pdftotext' + ('.exe' if iswindows else ''))


def pdftohtml(output_dir, pdf_path, no_images, as_xml=False):
    '''
    Convert the pdf into html using the pdftohtml app.
    This will write the html as index.html into output_dir.
    It will also write all extracted images to the output_dir
    '''

    pdfsrc = os.path.join(output_dir, 'src.pdf')
    index = os.path.join(output_dir, 'index.'+('xml' if as_xml else 'html'))

    with open(pdf_path, 'rb') as src, open(pdfsrc, 'wb') as dest:
        shutil.copyfileobj(src, dest)

    with CurrentDir(output_dir):

        def a(x):
            return os.path.basename(x)

        exe = PDFTOHTML
        cmd = [exe, '-enc', 'UTF-8', '-noframes', '-p', '-nomerge',
                '-nodrm', a(pdfsrc), a(index)]

        if isbsd:
            cmd.remove('-nodrm')
        if no_images:
            cmd.append('-i')
        if as_xml:
            cmd.append('-xml')

        logf = PersistentTemporaryFile('pdftohtml_log')
        try:
            p = popen(cmd, stderr=logf._fd, stdout=logf._fd,
                    stdin=subprocess.PIPE)
        except OSError as err:
            if err.errno == errno.ENOENT:
                raise ConversionError(
                    _('Could not find pdftohtml, check it is in your PATH'))
            else:
                raise
        ret = eintr_retry_call(p.wait)
        logf.flush()
        logf.close()
        out = open(logf.name, 'rb').read().decode('utf-8', 'replace').strip()
        if ret != 0:
            raise ConversionError(f'pdftohtml failed with return code: {ret}\n{out}')
        if out:
            prints('pdftohtml log:')
            prints(out)
        if not os.path.exists(index) or os.stat(index).st_size < 100:
            raise DRMError()

        if not as_xml:
            with open(index, 'r+b') as i:
                raw = i.read().decode('utf-8', 'replace')
                raw = flip_images(raw)
                raw = raw.replace('<head', "<!-- created by calibre's pdftohtml -->\n  <head", 1)
                i.seek(0)
                i.truncate()
                # versions of pdftohtml >= 0.20 output self closing <br> tags, this
                # breaks the pdf heuristics regexps, so replace them
                raw = raw.replace('<br/>', '<br>')
                raw = re.sub(r'<a\s+name=(\d+)', r'<a id="\1"', raw, flags=re.I)
                raw = re.sub(r'<a id="(\d+)"', r'<a id="p\1"', raw, flags=re.I)
                raw = re.sub(r'<a href="index.html#(\d+)"', r'<a href="#p\1"', raw, flags=re.I)
                raw = xml_replace_entities(raw)
                raw = re.sub(r'[\u00a0\u2029]', ' ', raw)

                i.write(raw.encode('utf-8'))

            cmd = [exe, '-f', '1', '-l', '1', '-xml', '-i', '-enc', 'UTF-8', '-noframes', '-p', '-nomerge',
                    '-nodrm', '-q', '-stdout', a(pdfsrc)]
            if isbsd:
                cmd.remove('-nodrm')
            p = popen(cmd, stdout=subprocess.PIPE)
            raw = p.stdout.read().strip()
            if p.wait() == 0 and raw:
                parse_outline(raw, output_dir)

        try:
            os.remove(pdfsrc)
        except Exception:
            pass


def parse_outline(raw, output_dir):
    from lxml import etree

    from calibre.utils.xml_parse import safe_xml_fromstring
    raw = clean_xml_chars(xml_to_unicode(raw, strip_encoding_pats=True, assume_utf8=True)[0])
    outline = safe_xml_fromstring(raw).xpath('(//outline)[1]')
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
    with open(img, 'r+b') as f:
        img, fmt = image_and_format_from_data(f.read())
        img = flip_image(img, horizontal='x' in flip, vertical='y' in flip)
        f.seek(0), f.truncate()
        f.write(image_to_data(img, fmt=fmt))


def flip_images(raw):
    for match in re.finditer(r'<IMG[^>]+/?>', raw, flags=re.I):
        img = match.group()
        m = re.search(r'class="(x|y|xy)flip"', img)
        if m is None:
            continue
        flip = m.group(1)
        src = re.search(r'src="([^"]+)"', img)
        if src is None:
            continue
        img = src.group(1)
        if not os.path.exists(img):
            continue
        flip_image(img, flip)
    raw = re.sub(r'<STYLE.+?</STYLE>\s*', '', raw, flags=re.I|re.DOTALL)

    counter = 0

    def add_alt(m):
        nonlocal counter
        counter += 1
        return m.group(1).rstrip('/') + f' alt="Image {counter}"/>'

    raw = re.sub(r'(<IMG[^>]+)/?>', add_alt, raw, flags=re.I)
    return raw
