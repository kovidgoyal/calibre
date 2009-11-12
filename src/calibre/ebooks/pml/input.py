# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import glob
import os
import shutil

from calibre.customize.conversion import InputFormatPlugin
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.zipfile import ZipFile
from calibre.ebooks.pml.pmlconverter import pml_to_html
from calibre.ebooks.metadata.opf2 import OPFCreator

class PMLInput(InputFormatPlugin):

    name        = 'PML Input'
    author      = 'John Schember'
    description = 'Convert PML to OEB'
    # pmlz is a zip file containing pml files and png images.
    file_types  = set(['pml', 'pmlz'])

    def process_pml(self, pml_path, html_path):
        pclose = False
        hclose = False
    
        if not hasattr(pml_path, 'read'):
            pml_stream = open(pml_path, 'rb')
            pclose = True
        else:
            pml_stream = pml_path
            
        if not hasattr(html_path, 'write'):
            html_stream = open(html_path, 'wb')
            hclose = True
        else:
            html_stream = html_path
        
        ienc = pml_stream.encoding if pml_stream.encoding else 'utf-8'
        if self.options.input_encoding:
            ienc = self.options.input_encoding

        style = '''
<style>
.s {font-size: 1em}
.l {font-size: 1.5em}
.k {font-size: 0.75em}
.c {text-align: center; margin: auto}
.r {text-align: right}
.t {margin-left: 5%}
.p {page-break-after: always}
.x {page-break-before: always}
</style>
'''
        self.log.debug('Converting PML to HTML...')
        html = pml_to_html(pml_stream.read().decode(ienc)) 
        html_stream.write('<html><head><title />%s</head><body>' % style)
        html_stream.write(html.encode('utf-8', 'replace'))
        html_stream.write('</body></html>') 

        if pclose:
            pml_stream.close()
        if hclose:
            html_stream.close()

    def convert(self, stream, options, file_ext, log,
                accelerators):
        self.options = options
        self.log = log
        pages, images = [], []

        if file_ext == 'pmlz':
            log.debug('De-compressing content to temporary directory...')
            with TemporaryDirectory('_unpmlz') as tdir:
                zf = ZipFile(stream)
                zf.extractall(tdir)
            
                pmls = glob.glob(os.path.join(tdir, '*.pml'))
                for pml in pmls:
                    html_name = os.path.splitext(os.path.basename(pml))[0]+'.html'
                    html_path = os.path.join(os.getcwd(), html_name)
                    
                    pages.append(html_name)
                    log.debug('Processing PML item %s...' % pml)
                    self.process_pml(pml, html_path)
                    
                imgs = glob.glob(os.path.join(tdir, '*.png'))
                if len(imgs) > 0:
                    os.makedirs(os.path.join(os.getcwd(), 'images'))
                for img in imgs:
                    pimg_name = os.path.basename(img)
                    pimg_path = os.path.join(os.getcwd(), 'images', pimg_name)
                    
                    images.append('images/' + pimg_name)
                    
                    shutil.move(img, pimg_path)
        else:
            self.process_pml(stream, 'index.html')

            pages.append('index.html')
            images = []

        # We want pages to be orded alphabetically.
        pages.sort()

        manifest_items = []
        for item in pages+images:
            manifest_items.append((item, None))
        
        from calibre.ebooks.metadata.meta import get_metadata
        log.debug('Reading metadata from input file...')
        mi = get_metadata(stream, 'pml')
        opf = OPFCreator(os.getcwd(), mi)
        log.debug('Generating manifest...')
        opf.create_manifest(manifest_items)
        opf.create_spine(pages)
        with open('metadata.opf', 'wb') as opffile:
            opf.render(opffile)
        
        return os.path.join(os.getcwd(), 'metadata.opf')
