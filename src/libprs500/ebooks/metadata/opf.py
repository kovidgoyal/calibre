##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
'''Read/Write metadata from Open Packaging Format (.opf) files.'''

import sys, re, os
from urllib import unquote
from urlparse import urlparse

from libprs500.ebooks.metadata import MetaInformation
from libprs500.ebooks.BeautifulSoup import BeautifulStoneSoup, BeautifulSoup
from libprs500.ebooks.lrf import entity_to_unicode

class ManifestItem(object):
    def __init__(self, item, cwd):
        self.id = item['id'] if item.has_key('id') else ''
        self.href = urlparse(unquote(item['href']))[2] if item.has_key('href') else ''
        if not os.path.isabs(self.href):
            self.href = os.path.join(cwd, self.href)
        self.href = os.path.normpath(self.href)
        self.media_type = item['media-type'] if item.has_key('media-type') else ''
        
    def __unicode__(self):
        return u'<item id="%s" href="%s" media-type="%s" />'%(self.id, self.href, self.media_type)

class Manifest(list):
    
    def __init__(self, soup, dir):
        manifest = soup.find('manifest')
        if manifest is not None:
            for item in manifest.findAll('item'):
                self.append(ManifestItem(item, dir))
                
    def item(self, id):
        for i in self:
            if i.id == id:
                return i    

class Spine(list):
    
    def __init__(self, soup, manifest):
        self.manifest = manifest
        spine = soup.find('spine')
        if spine is not None:
            for itemref in spine.findAll('itemref'):
                if itemref.has_key('idref'):
                    self.append(itemref['idref'])
                    
    def items(self):
        for i in self:
            yield  self.manifest.item(i)

class TOC(list):
    
    def __init__(self, opfreader, cwd):
        self.toc = toc = None
        try:
            toc = opfreader.soup.find('guide').find('reference', attrs={'type':'toc'})['href']
        except:
            for item in opfreader.manifest:
                if 'toc' in item.href.lower():
                    toc = item.href
                    break
        if toc is not None:
            toc = urlparse(unquote(toc))[2]
            if not os.path.isabs(toc):
                toc = os.path.join(cwd, toc)
            self.toc = toc
    
            soup = BeautifulSoup(open(toc, 'rb').read(), convertEntities=BeautifulSoup.HTML_ENTITIES)
            for a in soup.findAll('a'):
                if not a.has_key('href'):
                    continue
                purl = urlparse(unquote(a['href']))
                href, fragment = purl[2], purl[5]
                if not os.path.isabs(href):
                    href = os.path.join(cwd, href)
                txt = ''.join([unicode(s).strip() for s in a.findAll(text=True)])
                self.append((href, fragment, txt))
            

class OPFReader(MetaInformation):
    
    ENTITY_PATTERN = re.compile(r'&(\S+);')
    
    def __init__(self, stream, dir=os.getcwd()):
        self.default_title = stream.name if hasattr(stream, 'name') else 'Unknown' 
        if hasattr(stream, 'seek'):
            stream.seek(0)
        self.soup = BeautifulStoneSoup(stream.read())
        self.series = self.series_index = self.rating = None
        self.manifest = Manifest(self.soup, dir)
        self.spine = Spine(self.soup, self.manifest)
        self.toc = TOC(self, dir)
        
    @apply
    def title():
        doc = '''title'''
        def fget(self):
            title = self.soup.package.metadata.find('dc:title')
            if title:
                return self.ENTITY_PATTERN.sub(entity_to_unicode, title.string)
            return self.default_title
        return property(doc=doc, fget=fget)
    
    @apply
    def authors():
        doc = '''authors'''
        def fget(self):
            creators = self.soup.package.metadata.findAll('dc:creator')
            for elem in creators:
                role = elem.get('role')
                if not role:
                    role = elem.get('opf:role')
                if role == 'aut':
                    raw = self.ENTITY_PATTERN.sub(entity_to_unicode, elem.string)
                    au = raw.split(',')
                    ans = []
                    for i in au:
                        ans.extend(i.split('&'))
                    return ans
            return None
        return property(doc=doc, fget=fget)
    
    @apply
    def author_sort():
        doc = '''author sort'''
        def fget(self):
            creators = self.soup.package.metadata.findAll('dc:creator')
            for elem in creators:
                role = elem.get('role')
                if not role:
                    role = elem.get('opf:role')
                if role == 'aut':
                    fa = elem.get('file-as')
                    return self.ENTITY_PATTERN.sub(entity_to_unicode, fa) if fa else None
        return property(doc=doc, fget=fget)
        
    @apply
    def title_sort():
        doc = 'title sort'
        def fget(self):
            return None
        return property(doc=doc, fget=fget)
    
    @apply
    def comments():
        doc = 'comments'
        def fget(self):
            comments = self.soup.find('dc:description')
            if comments:
                return self.ENTITY_PATTERN.sub(entity_to_unicode, comments.string)
            return None
        return property(doc=doc, fget=fget)
    
    @apply
    def category():
        doc = 'category'
        def fget(self):
            category = self.soup.find('dc:type')
            if category:
                return self.ENTITY_PATTERN.sub(entity_to_unicode, category.string)
            return None
        return property(doc=doc, fget=fget)
    
    @apply
    def publisher():
        doc = 'publisher'
        def fget(self):
            publisher = self.soup.find('dc:publisher')
            if publisher:
                return self.ENTITY_PATTERN.sub(entity_to_unicode, publisher.string)
            return None
        return property(doc=doc, fget=fget)
    
    @apply
    def isbn():
        doc = 'ISBN number'
        def fget(self):
            for item in self.soup.package.metadata.findAll('dc:identifier'):
                scheme = item.get('scheme')
                if not scheme:
                    scheme = item.get('opf:scheme')
                if scheme.lower() == 'isbn':
                    return item.string
            return None
        return property(doc=doc, fget=fget)
    
    @apply
    def cover():
        doc = 'cover'
        def fget(self):
            guide = self.soup.package.find('guide')
            if guide:
                references = guide.findAll('reference')
                for reference in references:
                    type = reference.get('type')
                    if not type:
                        continue
                    if type.lower() in ['cover', 'other.ms-coverimage-standard']:
                        return reference.get('href')
            return None
        return property(doc=doc, fget=fget)
    
    def possible_cover_prefixes(self):
        isbn, ans = [], []
        for item in self.soup.package.metadata.findAll('dc:identifier'):
            scheme = item.get('scheme')
            if not scheme:
                scheme = item.get('opf:scheme')
            isbn.append((scheme, item.string))
        for item in isbn:
            ans.append(item[1].replace('-', ''))
        return ans
    
    
def main(args=sys.argv):
    r = OPFReader(open(args[1], 'rb'))
    return 0

if __name__ == '__main__':
    sys.exit(main())