#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, subprocess, shutil

from lxml import etree

from calibre.constants import iswindows
from calibre.customize.ui import plugin_for_output_format
from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks.mobi.utils import detect_periodical
from calibre import CurrentDir

exe = 'kindlegen.exe' if iswindows else 'kindlegen'

def refactor_opf(opf, is_periodical, toc):
    with open(opf, 'rb') as f:
        root = etree.fromstring(f.read())
    '''
    for spine in root.xpath('//*[local-name() = "spine" and @toc]'):
        # Do not use the NCX toc as kindlegen requires the section structure
        # in the TOC to be duplicated in the HTML, asinine!
        del spine.attrib['toc']
    '''
    if is_periodical:
        metadata = root.xpath('//*[local-name() = "metadata"]')[0]
        xm = etree.SubElement(metadata, 'x-metadata')
        xm.tail = '\n'
        xm.text = '\n\t'
        mobip = etree.SubElement(xm, 'output', attrib={'encoding':"utf-8",
            'content-type':"application/x-mobipocket-subscription-magazine"})
        mobip.tail = '\n\t'
    with open(opf, 'wb') as f:
        f.write(etree.tostring(root, method='xml', encoding='utf-8',
            xml_declaration=True))


def refactor_guide(oeb):
    for key in list(oeb.guide):
        if key not in ('toc', 'start', 'masthead'):
            oeb.guide.remove(key)

def run_kindlegen(opf, log):
    log.info('Running kindlegen on MOBIML created by calibre')
    oname = os.path.splitext(opf)[0] + '.mobi'
    p = subprocess.Popen([exe, opf, '-c1', '-verbose', '-o', oname],
        stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
    ko = p.stdout.read()
    returncode = p.wait()
    log.debug('kindlegen verbose output:')
    log.debug(ko.decode('utf-8', 'replace'))
    log.info('kindlegen returned returncode: %d'%returncode)
    if not os.path.exists(oname) or os.stat(oname).st_size < 100:
        raise RuntimeError('kindlegen did not produce any output. '
                'kindlegen return code: %d'%returncode)
    return oname

def kindlegen(oeb, opts, input_plugin, output_path):
    is_periodical = detect_periodical(oeb.toc, oeb.log)
    refactor_guide(oeb)
    with TemporaryDirectory('_kindlegen_output') as tdir:
        oeb_output = plugin_for_output_format('oeb')
        oeb_output.convert(oeb, tdir, input_plugin, opts, oeb.log)
        opf = [x for x in os.listdir(tdir) if x.endswith('.opf')][0]
        refactor_opf(os.path.join(tdir, opf), is_periodical, oeb.toc)
        try:
            if os.path.exists('/tmp/kindlegen'):
                shutil.rmtree('/tmp/kindlegen')
            shutil.copytree(tdir, '/tmp/kindlegen')
            oeb.log('kindlegen intermediate output stored in: /tmp/kindlegen')
        except:
            pass

        with CurrentDir(tdir):
            oname = run_kindlegen(opf, oeb.log)
            shutil.copyfile(oname, output_path)


