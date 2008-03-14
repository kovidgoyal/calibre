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
import uuid
'''Read/Write metadata from Open Packaging Format (.opf) files.'''

import sys, re, os, mimetypes
from urllib import unquote
from urlparse import urlparse
import xml.dom.minidom as dom
from itertools import repeat

from libprs500 import __appname__
from libprs500.ebooks.metadata import MetaInformation
from libprs500.ebooks.BeautifulSoup import BeautifulStoneSoup
from libprs500.ebooks.lrf import entity_to_unicode
from libprs500.ebooks.metadata import get_parser
from libprs500.ebooks.metadata.toc import TOC

class ManifestItem(object):
    def __init__(self, item, cwd):
        self.id = item['id'] if item.has_key('id') else ''
        self.href = urlparse(unquote(item['href']))[2] if item.has_key('href') else ''
        if not os.path.isabs(self.href):
            self.href = os.path.join(cwd, self.href)
        self.href = os.path.normpath(self.href)
        if not os.path.exists(self.href): # Bug in Baen OPF files
            nhref = os.path.join(os.path.dirname(self.href), os.path.basename(self.href).replace('__p_.htm', '__c_.htm'))
            if os.path.exists(nhref):
                self.href = nhref
        self.media_type = item['media-type'] if item.has_key('media-type') else ''
        
    def __unicode__(self):
        return u'<item id="%s" href="%s" media-type="%s" />'%(self.id, self.href, self.media_type)
    
    def __getitem__(self, index):
        if index == 0:
            return self.href
        if index == 1:
            return self.media_type
        raise IndexError('%d out of bounds.'%index)
        

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

class Spine(object):
    
    def __init__(self, soup, manifest):
        self.manifest = manifest
        self.linear_ids, self.nonlinear_ids = [], []
        spine = soup.find('spine')
        if spine is not None:
            for itemref in spine.findAll('itemref'):
                if itemref.has_key('idref'):
                    if itemref.get('linear', 'yes') == 'yes':
                        self.linear_ids.append(itemref['idref'])
                    else:
                        self.nonlinear_ids.append(itemref['idref'])
                    
    def linear_items(self):
        for id in self.linear_ids:
            yield self.manifest.item(id)


    def nonlinear_items(self):
        for id in self.nonlinear_ids:
            yield self.manifest.item(id)
    
    
    def items(self):
        for i in self.linear_ids + self.nonlinear_ids:
            mi = self.manifest.item(i)
            if getattr(mi, 'href', None):
                yield mi  
            
    def __iter__(self):
        for i in self.linear_ids + self.nonlinear_ids:
            yield i

            

class standard_field(object):
    
    def __init__(self, name):
        self.name = name
        
    def __get__(self, obj, typ=None):
        return getattr(obj, 'get_'+self.name)()
    
    def __set__(self, obj, val):
        getattr(obj, 'set_'+self.name)(val)
        
class OPF(MetaInformation):
    
    MIMETYPE = 'application/oebps-package+xml'
    ENTITY_PATTERN = re.compile(r'&(\S+?);')
    
    uid            = standard_field('uid')
    application_id = standard_field('application_id')
    title          = standard_field('title')
    authors        = standard_field('authors')
    title_sort     = standard_field('title_sort')
    author_sort    = standard_field('author_sort')
    comments       = standard_field('comments')
    category       = standard_field('category')
    publisher      = standard_field('publisher')
    isbn           = standard_field('isbn')
    cover          = standard_field('cover')
    series         = standard_field('series')
    series_index   = standard_field('series_index')
    rating         = standard_field('rating')
    tags           = standard_field('tags')
    
    HEADER = '''\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE package 
  PUBLIC "+//ISBN 0-9673008-1-9//DTD OEB 1.2 Package//EN"
  "http://openebook.org/dtds/oeb-1.2/oebpkg12.dtd">
'''    
    def __init__(self):
        raise NotImplementedError('Abstract base class')
    
    def _initialize(self):
        if not hasattr(self, 'soup'):
            self.soup = BeautifulStoneSoup(u'''\
%s
<package unique-identifier="%s_id">
    <metadata>
        <dc-metadata
         xmlns:dc="http://purl.org/dc/elements/1.1/"
         xmlns:oebpackage="http://openebook.org/namespaces/oeb-package/1.0/" />
    </metadata>
</package>
'''%(__appname__, self.HEADER))
    
    def _commit(self, doc):
        self.soup = BeautifulStoneSoup(doc.toxml('utf-8'), fromEncoding='utf-8')
        
    def _find_element(self, package, name, attrs=[]):
        tags = package.getElementsByTagName(name)
        for tag in tags:
            match = True
            for attr, vattr in attrs:
                if tag.getAttribute(attr) != vattr:
                    match = False
                    break
            if match:
                return tag
        return None
    
    def _set_metadata_element(self, name, value, attrs=[], 
                              type='dc-metadata', replace=False):
        self._initialize()
        if isinstance(value, basestring):
            value = [value]
            attrs = [attrs]
        
        doc = dom.parseString(self.soup.__str__('UTF-8').strip())
        package = doc.documentElement
        metadata = package.getElementsByTagName('metadata')[0]
            
        dcms = metadata.getElementsByTagName(type)
        if dcms:
            dcm = dcms[0]            
        else:
            dcm = doc.createElement(type)
            metadata.appendChild(dcm)
            metadata.appendChild(doc.createTextNode('\n'))
        tags =  dcm.getElementsByTagName(name)
        if tags and not replace:
            for tag in tags:
                tag.parentNode.removeChild(tag)
                tag.unlink()
        
        for val, vattrs in zip(value, attrs):
            if replace:
                el = self._find_element(package, name, vattrs)
                if el:
                    el.parentNode.removeChild(el)
                    el.unlink()
            el = doc.createElement(name)
            el.appendChild(doc.createTextNode(val))
            for attr, vattr in vattrs:
                el.setAttribute(attr, vattr)
            dcm.appendChild(el)
            dcm.appendChild(doc.createTextNode('\n'))
        self._commit(doc)
            
    
    def get_title(self):
        title = self.soup.package.metadata.find('dc:title')
        if title:
            return self.ENTITY_PATTERN.sub(entity_to_unicode, title.string).strip()
        return self.default_title.strip()
    
    def set_title(self, title):
        if not title:
            title = 'Unknown'
        self._set_metadata_element('dc:title', title)

    def get_authors(self):
        creators = self.soup.package.metadata.findAll('dc:creator')
        for elem in creators:
            role = elem.get('role')
            if not role:
                role = elem.get('opf:role')
            if not role:
                role = 'aut'
            if role == 'aut':
                raw = self.ENTITY_PATTERN.sub(entity_to_unicode, elem.string)
                au = raw.split(',')
                ans = []
                for i in au:
                    ans.extend(i.split('&'))
                return [a.strip() for a in ans]
        return []
    
    def set_authors(self, authors):
        if not authors:
            authors = ['Unknown']
        attrs = list(repeat([('role', 'aut')], len(authors)))
        self._set_metadata_element('dc:creator', authors, attrs)
    
    def get_author_sort(self):
        creators = self.soup.package.metadata.findAll('dc:creator')
        for elem in creators:
            role = elem.get('role')
            if not role:
                role = elem.get('opf:role')
            if role == 'aut':
                fa = elem.get('file-as')
                return self.ENTITY_PATTERN.sub(entity_to_unicode, fa).strip() if fa else None
        return None
    
    def set_author_sort(self, aus):
        if not aus:
            aus = ''
        self._initialize()
        if not self.authors:
            self.set_authors([])
        doc = dom.parseString(self.soup.__str__('UTF-8'))
        package = doc.documentElement
        aut = package.getElementsByTagName('dc:creator')[0]
        aut.setAttribute('file-as', aus)
        self._commit(doc)
        
    def get_title_sort(self):
        title = self.soup.package.find('dc:title')
        if title:
            if title.has_key('file-as'):
                return title['file-as'].strip()
        return None
    
    def set_title_sort(self, title_sort):
        if not title_sort:
            title_sort = ''
        self._initialize()
        if not self.title:
            self.title = None
        doc = dom.parseString(self.soup.__str__('UTF-8'))
        package = doc.documentElement
        tit = package.getElementsByTagName('dc:title')[0]
        tit.setAttribute('file-as', title_sort)
        self._commit(doc)
    
    def get_comments(self):
        comments = self.soup.find('dc:description')
        if comments:
            return self.ENTITY_PATTERN.sub(entity_to_unicode, comments.string).strip()
        return None
    
    def set_comments(self, comments):
        if not comments:
            comments = ''
        self._set_metadata_element('dc:description', comments)
    
    def get_uid(self):
        package = self.soup.find('package')
        if package.has_key('unique-identifier'):
            return package['unique-identifier']
        
    def set_uid(self, uid):
        package = self.soup.find('package')
        package['unique-identifier'] = str(uid)
    
    def get_category(self):
        category = self.soup.find('dc:type')
        if category:
            return self.ENTITY_PATTERN.sub(entity_to_unicode, category.string).strip()
        return None
    
    def set_category(self, category):
        if not category:
            category = ''
        self._set_metadata_element('dc:type', category)
    
    def get_publisher(self):
        publisher = self.soup.find('dc:publisher')
        if publisher:
            return self.ENTITY_PATTERN.sub(entity_to_unicode, publisher.string).strip()
        return None
    
    def set_publisher(self, category):
        if not category:
            category = 'Unknown'
        self._set_metadata_element('dc:publisher', category)
    
       
    def get_isbn(self):
        for item in self.soup.package.metadata.findAll('dc:identifier'):
            scheme = item.get('scheme')
            if not scheme:
                scheme = item.get('opf:scheme')
            if scheme is not None and scheme.lower() == 'isbn':
                return str(item.string).strip()
        return None
    
    def set_isbn(self, isbn):
        if isbn:
            self._set_metadata_element('dc:identifier', isbn, [('scheme', 'ISBN')], 
                                       replace=True)
        
    def get_application_id(self):
        for item in self.soup.package.metadata.findAll('dc:identifier'):
            if item.has_key('scheme') and item['scheme'] == __appname__:
                return str(item.string).strip()
        return None
    
    def set_application_id(self, val):
        if val:
            self._set_metadata_element('dc:identifier', str(val), [('scheme', __appname__), ('id', __appname__+'_id')], 
                                       replace=True)
    
    def get_cover(self):
        guide = self.soup.package.find('guide')
        if guide:
            references = guide.findAll('reference')
            for reference in references:
                type = reference.get('type')
                if not type:
                    continue
                if type.lower() in ['cover', 'other.ms-coverimage-standard', "other.ms-coverimage"]:
                    return reference.get('href')
        return None
    
    def set_cover(self, path):
        self._initialize()
        doc = dom.parseString(self.soup.__str__('UTF-8'))
        package = doc.documentElement
        guide = package.getElementsByTagName('guide')
        if guide:
            guide = guide[0]
        else:
            guide = doc.createElement('guide')
            package.appendChild(guide)
        el = self._find_element(guide, 'reference', [('type', 'cover')])
        if not el:
            el = doc.createElement('reference')
            guide.appendChild(el)
            el.setAttribute('type', 'cover')
        el.setAttribute('href', path)
        self._commit(doc)
    
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
    
    def get_series(self):
        xm = self.soup.package.metadata.find('x-metadata')
        if not xm:
            return None
        s = xm.find('series')
        if s:
            return str(s.string).strip()
        return None
    
    def set_series(self, val):
        if not val:
            val = ''
        self._set_metadata_element('series', val, type='x-metadata')
    
    def get_series_index(self):
        xm = self.soup.package.metadata.find('x-metadata')
        if not xm:
            return None
        s = xm.find('series-index')
        if s:
            try:
                return int(str(s.string).strip())
            except:
                return None
        return None
    
    def set_series_index(self, val):
        if not val:
            val = 1
        self._set_metadata_element('series-index', str(val), type='x-metadata')
    
    def get_rating(self):
        xm = self.soup.package.metadata.find('x-metadata')
        if not xm:
            return None
        s = xm.find('rating')
        if s:
            try:
                return int(str(s.string).strip())
            except:
                return None
        return None
    
    def set_rating(self, val):
        if not val:
            val = 0
        self._set_metadata_element('rating', str(val), type='x-metadata')
        
    def get_tags(self):
        ans = []
        subs = self.soup.findAll('dc:subject')
        for sub in subs:
            val = sub.string
            if val:
                ans.append(val)
        return [unicode(a).strip() for a in ans]
    
    def set_tags(self, tags):
        self._set_metadata_element('dc:subject', tags)
        
    def write(self, stream):
        from lxml import etree 
        root = etree.fromstring(unicode(self.soup))
        root.text = '\n%4s'%' '
        for child in root:
            child.text = '\n%8s'%' '
            child.tail = '\n%4s'%' ' if child is not root[-1] else '\n'
            for grandchild in child:
                grandchild.tail = '\n%8s'%' ' if grandchild is not child[-1] else '\n%4s'%' '
        
        metadata = root.find('metadata')
        if metadata is not None:
            for parent in ['dc-metadata', 'x-metadata']:
                parent = metadata.find(parent)
                if parent is None:
                    continue
                parent.text = '\n%12s'%' '
                for child in parent:
                    child.tail = '\n%8s'%' ' if child is parent[-1] else '\n%12s'%' '
        
        def fix_self_closing_tags(el):
            ''' Makes tags that have only whitespace content self closing '''
            if len(el) == 0 and (el.text is None or el.text.strip() == ''):
                el.text = None
            for child in el:
                fix_self_closing_tags(child)
        
        fix_self_closing_tags(root)
        
        raw = self.HEADER + etree.tostring(root, encoding='UTF-8')
        
        stream.write(raw+'\n')

class OPFReader(OPF):
    
    def __init__(self, stream, dir=os.getcwdu()):
        manage = False
        if not hasattr(stream, 'read'):
            manage = True
            dir = os.path.dirname(stream)
            stream = open(stream, 'rb')
        self.default_title = stream.name if hasattr(stream, 'name') else 'Unknown' 
        if hasattr(stream, 'seek'):
            stream.seek(0)
        self.soup = BeautifulStoneSoup(stream.read())
        if manage:
            stream.close()
        self.manifest = Manifest(self.soup, dir)
        self.spine = Spine(self.soup, self.manifest)
        self.toc = TOC()
        self.toc.read_from_opf(self)
        self.cover_data = (None, None)
        
class OPFCreator(MetaInformation):
    
    def __init__(self, base_path, *args, **kwargs):
        '''
        Initialize.
        @param base_path: An absolute path to the directory in which this OPF file
        will eventually be. This is used by the L{create_manifest} method
        to convert paths to files into relative paths.
        '''
        MetaInformation.__init__(self, *args, **kwargs)
        self.base_path = os.path.abspath(base_path)
        if self.application_id is None:
            self.application_id = str(uuid.uuid4())
        self.toc = None
        if isinstance(self.manifest, Manifest):
            manifest = []
            for path, mt in self.manifest:
                if not path.startswith(self.base_path):
                    raise ValueError('Inavlid manifest item %s for base path %s'%(path, self.base_path))
                path = path[len(self.base_path)+1:]
                manifest.append((path, mt))
            self.manifest = manifest
    
    def create_manifest(self, entries):
        '''
        Create <manifest>
        @param entries: List of (path, mime-type)
        @param base_path: It is used to convert each path into a path relative to itself
        @type entries: list of 2-tuples
        '''
        rentries = []
        base_path = self.base_path
        mimetypes.init()
        for href, mt in entries:
            href = os.path.abspath(href)
            if not href.startswith(base_path):
                raise ValueError('OPF should only refer to files below it. %s is above %s'%(href, base_path))
            href = href[len(base_path)+1:].replace(os.sep, '/')
            if not mt:
                mt = mimetypes.guess_type(href)[0]
                if not mt:
                    mt = ''
            rentries.append((href, mt))
            
        self.manifest = rentries
        
    def create_manifest_from_files_in(self, files_and_dirs):
        entries = []
        
        def dodir(dir):
            for root, dirs, files in os.walk(dir):
                for name in files:
                    path = os.path.join(root, name)
                    entries.append((path, None)) 
        
        for i in files_and_dirs:
            if os.path.isdir(i):
                dodir(i)
            else:
                entries.append((i, None))
                
        self.create_manifest(entries)    
            
    def create_spine(self, entries):
        '''
        Create the <spine> element. Must first call L{create_manifest}.
        @param: List of paths
        @type param: list of strings
        '''
        self.spine = []
        
        for path in entries:
            if not os.path.isabs(path):
                path = os.path.join(self.base_path, path)
            if not path.startswith(self.base_path):
                raise ValueError('Invalid entry %s for base path %s'%(path, self.base_path))
            href = path[len(self.base_path)+1:]
            in_manifest = False
            for i, m in enumerate(self.manifest):
                if m[0] == href:
                    in_manifest = True
                    break
            if not in_manifest:
                raise ValueError('%s is not in the manifest. (%s)'%(href, path))
            self.spine.append(i)
         
            
        
    def set_toc(self, toc):
        '''
        Set the toc. You must call L{create_spine} before calling this
        method.
        @param toc: A Table of Contents
        @type toc: L{TOC}
        '''
        self.toc = toc
        
    def render(self, opf_stream, ncx_stream=None):
        from libprs500.resources import opf_template
        from genshi.template import MarkupTemplate
        template = MarkupTemplate(opf_template)
        opf = template.generate(__appname__=__appname__, mi=self).render('xml')
        opf_stream.write(opf)
        toc = getattr(self, 'toc', None)
        if toc is not None and ncx_stream is not None:
            toc.render(ncx_stream, self.application_id)
    
def option_parser():
    return get_parser('opf')

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        return 1
    mi = MetaInformation(OPFReader(open(args[1], 'rb')))
    if opts.title is not None:
        mi.title = opts.title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if opts.authors is not None:
        aus = [i.strip().replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;') for i in opts.authors.split(',')]
        mi.authors = aus
    if opts.category is not None:
        mi.category = opts.category.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if opts.comment is not None:
        mi.comments = opts.comment.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    print mi
    mo = OPFCreator(os.getcwd(), mi)
    mo.render(open(args[1], 'wb'))
    return 0

if __name__ == '__main__':
    sys.exit(main())
