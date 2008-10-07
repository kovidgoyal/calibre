#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
lxml based OPF parser.
'''

import sys, unittest, functools, os, mimetypes, uuid, glob
from urllib import unquote
from urlparse import urlparse

from lxml import etree

from calibre.ebooks.chardet import xml_to_unicode
from calibre import relpath
from calibre.constants import __appname__, __version__
from calibre.ebooks.metadata.toc import TOC
from calibre.ebooks.metadata import MetaInformation


class Resource(object):
    '''
    Represents a resource (usually a file on the filesystem or a URL pointing 
    to the web. Such resources are commonly referred to in OPF files.
    
    They have the interface:
    
    :member:`path`
    :member:`mime_type`
    :method:`href`
    
    '''
    
    def __init__(self, href_or_path, basedir=os.getcwd(), is_path=True):
        self._href = None
        self._basedir = basedir
        self.path = None
        self.fragment = ''
        try:
            self.mime_type = mimetypes.guess_type(href_or_path)[0]
        except:
            self.mime_type = None
        if self.mime_type is None:
            self.mime_type = 'application/octet-stream'
        if is_path:
            path = href_or_path
            if not os.path.isabs(path):
                path = os.path.abspath(os.path.join(basedir, path))
            if isinstance(path, str):
                path = path.decode(sys.getfilesystemencoding())
            self.path = path
        else:
            href_or_path = href_or_path
            url = urlparse(href_or_path)
            if url[0] not in ('', 'file'):
                self._href = href_or_path
            else:
                pc = url[2]
                if isinstance(pc, unicode):
                    pc = pc.encode('utf-8')
                pc = pc.decode('utf-8')
                self.path = os.path.abspath(os.path.join(basedir, pc.replace('/', os.sep)))
                self.fragment = url[-1]
        
    
    def href(self, basedir=None):
        '''
        Return a URL pointing to this resource. If it is a file on the filesystem
        the URL is relative to `basedir`.
        
        `basedir`: If None, the basedir of this resource is used (see :method:`set_basedir`).
        If this resource has no basedir, then the current working directory is used as the basedir.
        '''
        if basedir is None:
            if self._basedir:
                basedir = self._basedir
            else:
                basedir = os.getcwd()
        if self.path is None:
            return self._href
        f = self.fragment.encode('utf-8') if isinstance(self.fragment, unicode) else self.fragment
        frag = '#'+f if self.fragment else ''
        if self.path == basedir:
            return ''+frag
        try:
            rpath = relpath(self.path, basedir)
        except OSError: # On windows path and basedir could be on different drives
            rpath = self.path
        if isinstance(rpath, unicode):
            rpath = rpath.encode('utf-8')
        return rpath.replace(os.sep, '/')+frag
    
    def set_basedir(self, path):
        self._basedir = path
        
    def basedir(self):
        return self._basedir
    
    def __repr__(self):
        return 'Resource(%s, %s)'%(repr(self.path), repr(self.href()))
        
        
class ResourceCollection(object):
    
    def __init__(self):
        self._resources = []
        
    def __iter__(self):
        for r in self._resources:
            yield r
            
    def __len__(self):
        return len(self._resources)
    
    def __getitem__(self, index):
        return self._resources[index]
    
    def __bool__(self):
        return len(self._resources) > 0
    
    def __str__(self):
        resources = map(repr, self)
        return '[%s]'%', '.join(resources)
    
    def __repr__(self):
        return str(self)
    
    def append(self, resource):
        if not isinstance(resource, Resource):
            raise ValueError('Can only append objects of type Resource')
        self._resources.append(resource)
        
    def remove(self, resource):
        self._resources.remove(resource)
    
    def replace(self, start, end, items):
        'Same as list[start:end] = items'
        self._resources[start:end] = items
        
    @staticmethod
    def from_directory_contents(top, topdown=True):
        collection = ResourceCollection()
        for spec in os.walk(top, topdown=topdown):
            path = os.path.abspath(os.path.join(spec[0], spec[1]))
            res = Resource.from_path(path)
            res.set_basedir(top)
            collection.append(res)
        return collection
    
    def set_basedir(self, path):
        for res in self:
            res.set_basedir(path)
        



class ManifestItem(Resource):
    
    @staticmethod
    def from_opf_manifest_item(item, basedir):
        href = item.get('href', None)
        if href:
            res = ManifestItem(href, basedir=basedir, is_path=True)
            mt = item.get('media-type', '').strip()
            if mt:
                res.mime_type = mt
            return res
    
    @apply
    def media_type():
        def fget(self):
            return self.mime_type
        def fset(self, val):
            self.mime_type = val
        return property(fget=fget, fset=fset)
    
        
    def __unicode__(self):
        return u'<item id="%s" href="%s" media-type="%s" />'%(self.id, self.href(), self.media_type)
    
    def __str__(self):
        return unicode(self).encode('utf-8')
    
    def __repr__(self):
        return unicode(self)
        
    
    def __getitem__(self, index):
        if index == 0:
            return self.href()
        if index == 1:
            return self.media_type
        raise IndexError('%d out of bounds.'%index)


class Manifest(ResourceCollection):
    
    @staticmethod
    def from_opf_manifest_element(items, dir):
        m = Manifest()
        for item in items:
            try:
                m.append(ManifestItem.from_opf_manifest_item(item, dir))
                id = item.get('id', '')
                if not id:
                    id = 'id%d'%m.next_id
                m[-1].id = id
                m.next_id += 1
            except ValueError:
                continue
        return m
    
    @staticmethod
    def from_paths(entries):
        '''
        `entries`: List of (path, mime-type) If mime-type is None it is autodetected
        '''
        m = Manifest()
        for path, mt in entries:
            mi = ManifestItem(path, is_path=True)
            if mt:
                mi.mime_type = mt
            mi.id = 'id%d'%m.next_id
            m.next_id += 1
            m.append(mi)
        return m
    
    def add_item(self, path, mime_type=None):
        mi = ManifestItem(path, is_path=True)
        if mime_type:
            mi.mime_type = mime_type
        mi.id = 'id%d'%self.next_id
        self.next_id += 1
        self.append(mi)
        return mi.id
    
    def __init__(self):
        ResourceCollection.__init__(self)
        self.next_id = 1
            
                
    def item(self, id):
        for i in self:
            if i.id == id:
                return i
            
    def id_for_path(self, path):
        path = os.path.normpath(os.path.abspath(path))
        for i in self:
            if i.path and os.path.normpath(i.path) == path:
                return i.id    
            
    def path_for_id(self, id):
        for i in self:
            if i.id == id:
                return i.path

class Spine(ResourceCollection):
    
    class Item(Resource):
        
        def __init__(self, idfunc, *args, **kwargs):
            Resource.__init__(self, *args, **kwargs)
            self.is_linear = True
            self.id = idfunc(self.path)
        
    @staticmethod
    def from_opf_spine_element(itemrefs, manifest):
        s = Spine(manifest)
        for itemref in itemrefs:
            idref = itemref.get('idref', None)
            if idref is not None:
                r = Spine.Item(s.manifest.id_for_path,
                               s.manifest.path_for_id(idref), is_path=True)
                r.is_linear = itemref.get('linear', 'yes') == 'yes'
                s.append(r)
        return s
                
    @staticmethod
    def from_paths(paths, manifest):
        s = Spine(manifest)
        for path in paths:
            try:
                s.append(Spine.Item(s.manifest.id_for_path, path, is_path=True))
            except:
                continue
        return s
            
            
    
    def __init__(self, manifest):
        ResourceCollection.__init__(self)
        self.manifest = manifest
            
            
    def replace(self, start, end, ids):
        '''
        Replace the items between start (inclusive) and end (not inclusive) with
        with the items identified by ids. ids can be a list of any length.
        '''
        items = []
        for id in ids:
            path = self.manifest.path_for_id(id)
            if path is None:
                raise ValueError('id %s not in manifest')
            items.append(Spine.Item(lambda x: id, path, is_path=True))
        ResourceCollection.replace(start, end, items)
                    
    def linear_items(self):
        for r in self:
            if r.is_linear:
                yield r.path

    def nonlinear_items(self):
        for r in self:
            if not r.is_linear:
                yield r.path
        
    def items(self):
        for i in self:
            yield i.path
    
class Guide(ResourceCollection):
    
    class Reference(Resource):
        
        @staticmethod
        def from_opf_resource_item(ref, basedir):
            title, href, type = ref.get('title', ''), ref.get('href'), ref.get('type')
            res = Guide.Reference(href, basedir, is_path=False)
            res.title = title
            res.type = type
            return res
        
        def __repr__(self):
            ans = '<reference type="%s" href="%s" '%(self.type, self.href())
            if self.title:
                ans += 'title="%s" '%self.title
            return ans + '/>'
        
        
    @staticmethod
    def from_opf_guide(references, base_dir=os.getcwdu()):
        coll = Guide()
        for ref in references:
            try:
                ref = Guide.Reference.from_opf_resource_item(ref, base_dir)
                coll.append(ref)
            except:
                continue
        return coll
        
    def set_cover(self, path):
        map(self.remove, [i for i in self if 'cover' in i.type.lower()])
        for type in ('cover', 'other.ms-coverimage-standard', 'other.ms-coverimage'):
            self.append(Guide.Reference(path, is_path=True))
            self[-1].type = type
            self[-1].title = ''


class MetadataField(object):
    
    def __init__(self, name, is_dc=True, formatter=None, none_is=None):
        self.name      = name
        self.is_dc     = is_dc
        self.formatter = formatter
        self.none_is   = none_is
        
    def __real_get__(self, obj, type=None):
        ans = obj.get_metadata_element(self.name)
        if ans is None:
            return None
        ans = obj.get_text(ans)
        if ans is None:
            return ans
        if self.formatter is not None:
            try:
                ans = self.formatter(ans)
            except:
                return None
        return ans
    
    def __get__(self, obj, type=None):
        ans = self.__real_get__(obj, type)
        if ans is None:
            ans = self.none_is
        return ans
    
    def __set__(self, obj, val):
        elem = obj.get_metadata_element(self.name)
        if elem is None:
            elem = obj.create_metadata_element(self.name, ns='dc' if self.is_dc else 'opf')
        elem.text = unicode(val)

class OPF(object):
    MIMETYPE         = 'application/oebps-package+xml'
    PARSER           = etree.XMLParser(recover=True)
    NAMESPACES       = {
                        None  : "http://www.idpf.org/2007/opf",
                        'dc'  : "http://purl.org/dc/elements/1.1/",
                        'opf' : "http://www.idpf.org/2007/opf",
                       }
    xpn = NAMESPACES.copy()
    xpn.pop(None)
    xpn['re'] = 'http://exslt.org/regular-expressions'
    XPath = functools.partial(etree.XPath, namespaces=xpn)
    TEXT             = XPath('string()')
    
    
    metadata_path   = XPath('descendant::*[re:match(name(), "metadata", "i")]')
    metadata_elem_path = XPath('descendant::*[re:match(name(), $name, "i")]')
    series_path     = XPath('descendant::*[re:match(name(), "series$", "i")]')
    authors_path    = XPath('descendant::*[re:match(name(), "creator", "i") and (@role="aut" or @opf:role="aut")]')
    bkp_path        = XPath('descendant::*[re:match(name(), "contributor", "i") and (@role="bkp" or @opf:role="bkp")]')
    tags_path       = XPath('descendant::*[re:match(name(), "subject", "i")]')
    isbn_path       = XPath('descendant::*[re:match(name(), "identifier", "i") and '+
                            '(re:match(@scheme, "isbn", "i") or re:match(@opf:scheme, "isbn", "i"))]')
    manifest_path   = XPath('descendant::*[re:match(name(), "manifest", "i")]/*[re:match(name(), "item", "i")]') 
    spine_path      = XPath('descendant::*[re:match(name(), "spine", "i")]/*[re:match(name(), "itemref", "i")]')
    guide_path      = XPath('descendant::*[re:match(name(), "guide", "i")]/*[re:match(name(), "reference", "i")]')
    
    title           = MetadataField('title')
    publisher       = MetadataField('publisher')
    language        = MetadataField('language')
    comments        = MetadataField('description')
    category        = MetadataField('category')
    series_index    = MetadataField('series_index', is_dc=False, formatter=int, none_is=1)
    rating          = MetadataField('rating', is_dc=False, formatter=int)
    
    
    def __init__(self, stream, basedir=os.getcwdu()):
        if not hasattr(stream, 'read'):
            stream = open(stream, 'rb')
        self.basedir  = self.base_dir = basedir
        raw, self.encoding = xml_to_unicode(stream.read(), strip_encoding_pats=True, resolve_entities=True)
        
        self.root     = etree.fromstring(raw, self.PARSER)
        self.metadata = self.metadata_path(self.root)
        if not self.metadata:
            raise ValueError('Malformed OPF file: No <metadata> element')
        self.metadata      = self.metadata[0]
        self.unquote_urls()
        self.manifest = Manifest()
        m = self.manifest_path(self.root)
        if m:
            self.manifest = Manifest.from_opf_manifest_element(m, basedir)
        self.spine = None
        s = self.spine_path(self.root)
        if s:
            self.spine = Spine.from_opf_spine_element(s, self.manifest)
        self.guide = None
        guide = self.guide_path(self.root)
        self.guide = Guide.from_opf_guide(guide, basedir) if guide else None
        self.cover_data = (None, None)
        self.find_toc()
        
    def find_toc(self):
        self.toc = None
        try:
            spine = self.XPath('descendant::*[re:match(name(), "spine", "i")]')(self.root)
            toc = None
            if spine:
                spine = spine[0]
                toc = spine.get('toc', None)
            if toc is None and self.guide:
                for item in self.guide:
                    if item.type and item.type.lower() == 'toc':
                        toc = item.path
            if toc is None:
                for item in self.manifest:
                    if 'toc' in item.href().lower():
                        toc = item.path
            
            if toc is None: return
            self.toc = TOC(base_path=self.base_dir)
            if toc.lower() in ('ncx', 'ncxtoc'):
                path = self.manifest.path_for_id(toc)
                if path:
                    self.toc.read_ncx_toc(path)
                else:
                    f = glob.glob(os.path.join(self.base_dir, '*.ncx'))
                    if f:
                        self.toc.read_ncx_toc(f[0])
            else:
                self.toc.read_html_toc(toc)
        except:
            pass        
            
    
        
    def get_text(self, elem):
        return u''.join(self.TEXT(elem))
    
    def itermanifest(self):
        return self.manifest_path(self.root)
    
    def create_manifest_item(self, href, media_type):
        ids = [i.get('id', None) for i in self.itermanifest()]
        id = None
        for c in xrange(1, sys.maxint):
            id = 'id%d'%c
            if id not in ids:
                break
        if not media_type:
            media_type = 'application/xhtml+xml'
        ans = etree.Element('{%s}item'%self.NAMESPACES['opf'], 
                             attrib={'id':id, 'href':href, 'media-type':media_type})
        ans.tail = '\n\t\t'
        return ans
    
    def replace_manifest_item(self, item, items):
        items = [self.create_manifest_item(*i) for i in items]
        for i, item2 in enumerate(items):
            item2.set('id', item.get('id')+'.%d'%(i+1))
        manifest = item.getparent()
        index = manifest.index(item)
        manifest[index:index+1] = items
        return [i.get('id') for i in items]
    
    def iterspine(self):
        return self.spine_path(self.root)
    
    def create_spine_item(self, idref):
        ans = etree.Element('{%s}itemref'%self.NAMESPACES['opf'], idref=idref)
        ans.tail = '\n\t\t'
        return ans
    
    def replace_spine_items_by_idref(self, idref, new_idrefs):
        items = list(map(self.create_spine_item, new_idrefs))
        spine = self.XPath('/opf:package/*[re:match(name(), "spine", "i")]')(self.root)[0]
        old = [i for i in self.iterspine() if i.get('idref', None) == idref]
        for x in old:
            i = spine.index(x)
            spine[i:i+1] = items
    
    def create_guide_element(self):
        e = etree.SubElement(self.root, '{%s}guide'%self.NAMESPACES['opf'])
        e.text = '\n        '
        e.tail =  '\n'
        return e
    
    def remove_guide(self):
        self.guide = None
        for g in self.root.xpath('./*[re:match(name(), "guide", "i")]', namespaces={'re':'http://exslt.org/regular-expressions'}):
            self.root.remove(g)
    
    def create_guide_item(self, type, title, href):
        e = etree.Element('{%s}reference'%self.NAMESPACES['opf'], 
                             type=type, title=title, href=href)
        e.tail='\n'
        return e
        
    def add_guide_item(self, type, title, href):
        g = self.root.xpath('./*[re:match(name(), "guide", "i")]', namespaces={'re':'http://exslt.org/regular-expressions'})[0]
        g.append(self.create_guide_item(type, title, href))
        
    def iterguide(self):
        return self.guide_path(self.root)
    
    def unquote_urls(self):
        def get_href(item):
            raw = unquote(item.get('href', ''))
            if not isinstance(raw, unicode):
                raw = raw.decode('utf-8')
            return raw
        for item in self.itermanifest():
            item.set('href', get_href(item))
        for item in self.iterguide():
            item.set('href', get_href(item))
    
    @apply
    def authors():
        
        def fget(self):
            ans = []
            for elem in self.authors_path(self.metadata):
                ans.extend([x.strip() for x in self.get_text(elem).split(',')])
            return ans
        
        def fset(self, val):
            remove = list(self.authors_path(self.metadata))
            for elem in remove:
                self.metadata.remove(elem)
            for author in val:
                elem = self.create_metadata_element('creator', ns='dc',
                                                    attrib={'{%s}role'%self.NAMESPACES['opf']:'aut'})
                elem.text = author
        
        return property(fget=fget, fset=fset)
    
    @apply
    def author_sort():
        
        def fget(self):
            matches = self.authors_path(self.metadata)
            if matches:
                ans = matches[0].get('opf:file-as', None)
                return ans if ans else matches[0].get('file-as', None)
            
        def fset(self, val):
            matches = self.authors_path(self.metadata)
            if matches:
                matches[0].set('file-as', unicode(val))
            
        return property(fget=fget, fset=fset)
    
    @apply
    def tags():
        
        def fget(self):
            ans = []
            for tag in self.tags_path(self.metadata):
                ans.append(self.get_text(tag))
            return ans
        
        def fset(self, val):
            for tag in list(self.tags_path(self.metadata)):
                self.metadata.remove(tag)
            for tag in val:
                elem = self.create_metadata_element('subject', ns='dc')
                elem.text = unicode(tag)
        
        return property(fget=fget, fset=fset)
    
    @apply
    def isbn():
        
        def fget(self):
            for match in self.isbn_path(self.metadata):
                return match.text if match.text else None
            
        def fset(self, val):
            matches = self.isbn_path(self.metadata)
            if not matches:
                matches = [self.create_metadata_element('identifier', ns='dc',
                                                attrib={'{%s}scheme'%self.NAMESPACES['opf']:'ISBN'})]
            matches[0].text = unicode(val)

        return property(fget=fget, fset=fset)
    
    @apply
    def series():
        
        def fget(self):
            for match in self.series_path(self.metadata):
                return match.text if match.text else None
        
        def fset(self, val):
            matches = self.series_path(self.metadata)
            if not matches:
                matches = [self.create_metadata_element('series')]
            matches[0].text = unicode(val)
        
        return property(fget=fget, fset=fset)
    
    
    
    @apply
    def book_producer():
        
        def fget(self):
            for match in self.bkp_path(self.metadata):
                return match.text if match.text else None
            
        def fset(self, val):
            matches = self.bkp_path(self.metadata)
            if not matches:
                matches = [self.create_metadata_element('contributor', ns='dc',
                                                attrib={'{%s}role'%self.NAMESPACES['opf']:'bkp'})]
            matches[0].text = unicode(val)
        return property(fget=fget, fset=fset)
    
    
    @apply
    def cover():
        
        def fget(self):
            if self.guide is not None:
                for t in ('cover', 'other.ms-coverimage-standard', 'other.ms-coverimage'):
                    for item in self.guide:
                        if item.type.lower() == t:
                            return item.path
                        
        def fset(self, path):
            if self.guide is not None:
                self.guide.set_cover(path)
                for item in list(self.iterguide()):
                    if 'cover' in item.get('type', ''):
                        item.getparent().remove(item)
                        
            else:
                g = self.create_guide_element()
                self.guide = Guide()
                self.guide.set_cover(path)
                etree.SubElement(g, 'opf:reference', nsmap=self.NAMESPACES, 
                                 attrib={'type':'cover', 'href':self.guide[-1].href()})
            id = self.manifest.id_for_path(self.cover)
            if id is None:
                for t in ('cover', 'other.ms-coverimage-standard', 'other.ms-coverimage'):
                    for item in self.guide:
                        if item.type.lower() == t:
                            self.create_manifest_item(item.href(), mimetypes.guess_type(path)[0])
                 
        return property(fget=fget, fset=fset)                    
            
    def get_metadata_element(self, name):
        matches = self.metadata_elem_path(self.metadata, name=name)
        if matches:
            return matches[-1]
        
    def create_metadata_element(self, name, attrib=None, ns='opf'):
        elem = etree.SubElement(self.metadata, '{%s}%s'%(self.NAMESPACES[ns], name), 
                                attrib=attrib, nsmap=self.NAMESPACES)
        elem.tail = '\n'
        return elem
        
    def render(self, encoding='utf-8'):
        return etree.tostring(self.root, encoding='utf-8', pretty_print=True)
    
    def smart_update(self, mi):
        for attr in ('author_sort', 'title_sort', 'comments', 'category',
                     'publisher', 'series', 'series_index', 'rating',
                     'isbn', 'language', 'tags', 'title', 'authors'):
            val = getattr(mi, attr, None)
            if val is not None and val != [] and val != (None, None):
                setattr(self, attr, val)
    
    
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
        if not isinstance(self.toc, TOC):
            self.toc = None
        if not self.authors:
            self.authors = [_('Unknown')]
        if self.guide is None:
            self.guide = Guide()
        if self.cover:
            self.guide.set_cover(self.cover)
        
        
    def create_manifest(self, entries):
        '''
        Create <manifest>
        
        `entries`: List of (path, mime-type) If mime-type is None it is autodetected
        '''
        entries = map(lambda x: x if os.path.isabs(x[0]) else 
                      (os.path.abspath(os.path.join(self.base_path, x[0])), x[1]),
                      entries)
        self.manifest = Manifest.from_paths(entries)
        self.manifest.set_basedir(self.base_path)
        
    def create_manifest_from_files_in(self, files_and_dirs):
        entries = []
        
        def dodir(dir):
            for spec in os.walk(dir):
                root, files = spec[0], spec[-1]
                for name in files:
                    path = os.path.join(root, name)
                    if os.path.isfile(path):
                        entries.append((path, None)) 
        
        for i in files_and_dirs:
            if os.path.isdir(i):
                dodir(i)
            else:
                entries.append((i, None))
                
        self.create_manifest(entries)    
            
    def create_spine(self, entries):
        '''
        Create the <spine> element. Must first call :method:`create_manifest`.
        
        `entries`: List of paths
        '''
        entries = map(lambda x: x if os.path.isabs(x) else 
                      os.path.abspath(os.path.join(self.base_path, x)), entries)
        self.spine = Spine.from_paths(entries, self.manifest)
        
    def set_toc(self, toc):
        '''
        Set the toc. You must call :method:`create_spine` before calling this
        method.
        
        :param toc: A :class:`TOC` object
        '''
        self.toc = toc
        
    def create_guide(self, guide_element):
        self.guide = Guide.from_opf_guide(guide_element, self.base_path)
        self.guide.set_basedir(self.base_path)
            
    def render(self, opf_stream, ncx_stream=None, ncx_manifest_entry=None):
        from calibre.resources import opf_template
        from calibre.utils.genshi.template import MarkupTemplate
        template = MarkupTemplate(opf_template)
        if self.manifest:
            self.manifest.set_basedir(self.base_path)
            if ncx_manifest_entry is not None:
                if not os.path.isabs(ncx_manifest_entry):
                    ncx_manifest_entry = os.path.join(self.base_path, ncx_manifest_entry)
                remove = [i for i in self.manifest if i.id == 'ncx']
                for item in remove:
                    self.manifest.remove(item)
                self.manifest.append(ManifestItem(ncx_manifest_entry, self.base_path))
                self.manifest[-1].id = 'ncx'
                self.manifest[-1].mime_type = 'application/x-dtbncx+xml'
        if not self.guide:
            self.guide = Guide()
        if self.cover:
            cover = self.cover
            if not os.path.isabs(cover):
                cover = os.path.abspath(os.path.join(self.base_path, cover))
            self.guide.set_cover(cover)
        self.guide.set_basedir(self.base_path)
        opf = template.generate(__appname__=__appname__, mi=self, __version__=__version__).render('xml')
        opf_stream.write(opf)
        opf_stream.flush()
        toc = getattr(self, 'toc', None)
        if toc is not None and ncx_stream is not None:
            toc.render(ncx_stream, self.application_id)
            ncx_stream.flush()


class OPFTest(unittest.TestCase):
    
    def setUp(self):
        import cStringIO
        self.stream = cStringIO.StringIO(
'''\
<?xml version="1.0"  encoding="UTF-8"?>
<package version="2.0" xmlns="http://www.idpf.org/2007/opf" >
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>A Cool &amp; &copy; &#223; Title</dc:title>
    <creator opf:role="aut" file-as="Monkey">Monkey Kitchen, Next</creator>
    <dc:subject>One</dc:subject><dc:subject>Two</dc:subject>
    <dc:identifier scheme="ISBN">123456789</dc:identifier>
    <x-metadata>
        <series>A one book series</series>
    </x-metadata>
</metadata>
<manifest>
    <item id="1" href="a%20%7E%20b" media-type="text/txt" />
</manifest>
</package>
'''
        )
        self.opf = OPF(self.stream, os.getcwd())
        
    def testReading(self):
        opf = self.opf
        self.assertEqual(opf.title, u'A Cool & \xa9 \xdf Title')
        self.assertEqual(opf.authors, u'Monkey Kitchen,Next'.split(','))
        self.assertEqual(opf.author_sort, 'Monkey')
        self.assertEqual(opf.tags, ['One', 'Two'])
        self.assertEqual(opf.isbn, '123456789')
        self.assertEqual(opf.series, 'A one book series')
        self.assertEqual(opf.series_index, None)
        self.assertEqual(list(opf.itermanifest())[0].get('href'), 'a ~ b')
        
    def testWriting(self):
        for test in [('title', 'New & Title'), ('authors', ['One', 'Two']),
                     ('author_sort', "Kitchen"), ('tags', ['Three']),
                     ('isbn', 'a'), ('rating', 3), ('series_index', 1)]:
            setattr(self.opf, *test)
            self.assertEqual(getattr(self.opf, test[0]), test[1])
        
        self.opf.render()

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(OPFTest)
    
def test():
    unittest.TextTestRunner(verbosity=2).run(suite())

if __name__ == '__main__':
    sys.exit(test())