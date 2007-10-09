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

import sys, re

from libprs500.ebooks.metadata import MetaInformation
from libprs500.ebooks.BeautifulSoup import BeautifulStoneSoup
from libprs500.ebooks.lrf import entity_to_unicode

class OPFReader(MetaInformation):
    
    ENTITY_PATTERN = re.compile(r'&(\S+);')
    
    def __init__(self, stream):
        self.default_title = stream.name if hasattr(stream, 'name') else 'Unknown' 
        if hasattr(stream, 'seek'):
            stream.seek(0)
        self.soup = BeautifulStoneSoup(stream.read())
        self.series = self.series_index = self.rating = None
        
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
                    au = elem.string.split(',')
                    ans = []
                    for i in au:
                        ans.extend(i.split('&'))
                    return self.ENTITY_PATTERN.sub(entity_to_unicode, ans)
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
    return 0

if __name__ == '__main__':
    sys.exit(main())