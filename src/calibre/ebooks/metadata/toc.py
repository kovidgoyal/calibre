#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os, glob
from urlparse import urlparse
from urllib import unquote

from calibre import __appname__
from calibre.ebooks.BeautifulSoup import BeautifulStoneSoup, BeautifulSoup
from calibre.ebooks.chardet import xml_to_unicode

class NCXSoup(BeautifulStoneSoup):
    
    NESTABLE_TAGS = {'navpoint':[]}
    
    def __init__(self, raw):
        BeautifulStoneSoup.__init__(self, raw,  
                                  convertEntities=BeautifulSoup.HTML_ENTITIES,
                                  selfClosingTags=['meta', 'content'])

class TOC(list):
    
    def __init__(self, href=None, fragment=None, text=None, parent=None, play_order=1, 
                 base_path=os.getcwd()):
        self.href = href
        self.fragment = fragment
        self.text = text
        self.parent = parent
        self.base_path = base_path
        self.play_order = play_order
        
    def add_item(self, href, fragment, text):
        self.append(TOC(href=href, fragment=fragment, text=text, parent=self, base_path=self.base_path))
        return self[-1]
    
    def top_level_items(self):
        for item in self:
            if item.text is not None:
                yield item
    
    def depth(self):
        depth = 1
        for obj in self:
            c = obj.depth()
            if c > depth - 1:
                depth = c + 1
        return depth
    
    @apply
    def abspath():
        doc='Return the file this toc entry points to as a absolute path to a file on the system.'
        def fget(self):
            path = self.href.replace('/', os.sep)
            if not os.path.isabs(path):
                path = os.path.join(self.base_path, path)
            return path
        return property(fget=fget, doc=doc) 
    
    def read_from_opf(self, opfreader):
        toc = opfreader.soup.find('spine', toc=True)
        if toc is not None:
            toc = toc['toc']
        if toc is None:
            try:
                toc = opfreader.soup.find('guide').find('reference', attrs={'type':'toc'})['href']
            except:
                for item in opfreader.manifest:
                    if 'toc' in item.href.lower():
                        toc = item.href
                        break
        
        if toc is not None:
            if toc.lower() != 'ncx':
                toc = urlparse(unquote(toc))[2]
                toc = toc.replace('/', os.sep)
                if not os.path.isabs(toc):
                    toc = os.path.join(self.base_path, toc)
                try:
                    if not os.path.exists(toc):
                        bn  = os.path.basename(toc)
                        bn  = bn.replace('_top.htm', '_toc.htm') # Bug in BAEN OPF files
                        toc = os.path.join(os.path.dirname(toc), bn)
                    
                    self.read_html_toc(toc)
                except:
                    print 'WARNING: Could not read Table of Contents:'
                    import traceback
                    traceback.print_exc()
                    print 'Continuing anyway'
            else:
                cwd = os.path.abspath(self.base_path)
                m = glob.glob(os.path.join(cwd, '*.ncx'))
                if m:
                    toc = m[0]
                    self.read_ncx_toc(toc)
                    
    def read_ncx_toc(self, toc):
        self.base_path = os.path.dirname(toc)
        print xml_to_unicode(open(toc, 'rb').read(), True)[1]
        soup = NCXSoup(xml_to_unicode(open(toc, 'rb').read())[0])
        print unicode(soup).encode('utf8')
        
        def process_navpoint(np, dest):
            play_order = np.get('playOrder', 1)
            href = fragment = text = None
            nl = np.find('navlabel')
            if nl is not None:
                text = u''
                for txt in nl.findAll('text'):
                    text += ''.join([unicode(s) for s in txt.findAll(text=True)])
                content = elem.find('content')
                if content is None or not content.has_key('src') or not txt:
                    return
                
                purl = urlparse(unquote(content['src']))
                href, fragment = purl[2], purl[5]
            nd = dest.add_item(href, fragment, text)
            nd.play_order = play_order
                
            for c in np:
                if getattr(c, 'name', None) == 'navpoint':
                    process_navpoint(c, nd)
            
        nm = soup.find('navmap')
        for elem in nm:
            if getattr(elem, 'name', None) == 'navpoint':
                process_navpoint(elem, self)
            
        
    def read_html_toc(self, toc):
        self.base_path = os.path.dirname(toc)
        soup = BeautifulSoup(open(toc, 'rb').read(), convertEntities=BeautifulSoup.HTML_ENTITIES)
        for a in soup.findAll('a'):
            if not a.has_key('href'):
                continue
            purl = urlparse(unquote(a['href']))
            href, fragment = purl[2], purl[5]
            txt = ''.join([unicode(s).strip() for s in a.findAll(text=True)])
            self.add_item(href, fragment, txt)

    def render(self, stream, uid):
        from calibre.resources import ncx_template
        from genshi.template import MarkupTemplate
        doctype = ('ncx', "-//NISO//DTD ncx 2005-1//EN", "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd")
        template = MarkupTemplate(ncx_template)
        raw = template.generate(uid=uid, toc=self, __appname__=__appname__)
        raw = raw.render(doctype=doctype)
        stream.write(raw)