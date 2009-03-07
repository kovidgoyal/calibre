from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re, uuid
from itertools import cycle

from lxml import etree

from calibre.customize.conversion import InputFormatPlugin

class EPUBInput(InputFormatPlugin):
    
    name        = 'EPUB Input'
    author      = 'Kovid Goyal'
    description = 'Convert EPUB files (.epub) to HTML'
    file_types  = set(['epub'])
    
    @classmethod
    def decrypt_font(cls, key, path):
        raw = open(path, 'rb').read()
        crypt = raw[:1024]
        key = cycle(iter(key))
        decrypt = ''.join([chr(ord(x)^key.next()) for x in crypt])
        with open(path, 'wb') as f:
            f.write(decrypt)
            f.write(raw[1024:])
    
    @classmethod
    def process_ecryption(cls, encfile, opf, log):
        key = None
        m = re.search(r'(?i)(urn:uuid:[0-9a-f-]+)', open(opf, 'rb').read())
        if m:
            key = m.group(1)
            key = list(map(ord, uuid.UUID(key).bytes))
        try:
            root = etree.parse(encfile)
            for em in root.xpath('descendant::*[contains(name(), "EncryptionMethod")]'):
                algorithm = em.get('Algorithm', '')
                if algorithm != 'http://ns.adobe.com/pdf/enc#RC':
                    return False
                cr = em.getparent().xpath('descendant::*[contains(name(), "CipherReference")]')[0]
                uri = cr.get('URI')
                path = os.path.abspath(os.path.join(os.path.dirname(encfile), '..', *uri.split('/')))
                if os.path.exists(path):
                    cls.decrypt_font(key, path)
            return True
        except:
            import traceback
            traceback.print_exc()
        return False

    def convert(self, stream, options, file_ext, parse_cache, log):
        from calibre.utils.zipfile import ZipFile
        from calibre import walk
        from calibre.ebooks import DRMError
        zf = ZipFile(stream)
        zf.extractall(os.getcwd())
        encfile = os.path.abspath(os.path.join('META-INF', 'encryption.xml'))
        opf = None
        for f in walk('.'):
            if f.lower().endswith('.opf'):
                opf = f
                break
        path = getattr(stream, 'name', 'stream')
        
        if opf is None:
            raise ValueError('%s is not a valid EPUB file'%path)
        
        if os.path.exists(encfile):
            if not self.process_encryption(encfile, opf, log):
                raise DRMError(os.path.basename(path))
        
        return opf
        
