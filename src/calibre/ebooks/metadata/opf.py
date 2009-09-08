__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''Read/Write metadata from Open Packaging Format (.opf) files.'''

import re, os
import uuid
from urllib import unquote, quote

from calibre.constants import __appname__, __version__
from calibre.ebooks.metadata import MetaInformation, string_to_authors
from calibre.ebooks.BeautifulSoup import BeautifulStoneSoup, BeautifulSoup
from calibre.ebooks.lrf import entity_to_unicode
from calibre.ebooks.metadata import Resource, ResourceCollection
from calibre.ebooks.metadata.toc import TOC

class OPFSoup(BeautifulStoneSoup):

    def __init__(self, raw):
        BeautifulStoneSoup.__init__(self, raw,
                                  convertEntities=BeautifulSoup.HTML_ENTITIES,
                                  selfClosingTags=['item', 'itemref', 'reference'])

class ManifestItem(Resource):

    @staticmethod
    def from_opf_manifest_item(item, basedir):
        if item.has_key('href'):
            href = item['href']
            if unquote(href) == href:
                try:
                    href = quote(href)
                except KeyError:
                    pass
            res = ManifestItem(href, basedir=basedir, is_path=False)
            mt = item.get('media-type', '').strip()
            if mt:
                res.mime_type = mt
            return res

    @dynamic_property
    def media_type(self):
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
    def from_opf_manifest_element(manifest, dir):
        m = Manifest()
        for item in manifest.findAll(re.compile('item')):
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
    def from_opf_spine_element(spine, manifest):
        s = Spine(manifest)
        for itemref in spine.findAll(re.compile('itemref')):
            if itemref.has_key('idref'):
                r = Spine.Item(s.manifest.id_for_path,
                               s.manifest.path_for_id(itemref['idref']), is_path=True)
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
            title, href, type = ref.get('title', ''), ref['href'], ref['type']
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
    def from_opf_guide(guide_elem, base_dir=os.getcwdu()):
        coll = Guide()
        for ref in guide_elem.findAll('reference'):
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


class standard_field(object):

    def __init__(self, name):
        self.name = name

    def __get__(self, obj, typ=None):
        return getattr(obj, 'get_'+self.name)()


class OPF(MetaInformation):

    MIMETYPE = 'application/oebps-package+xml'
    ENTITY_PATTERN = re.compile(r'&(\S+?);')

    uid            = standard_field('uid')
    application_id = standard_field('application_id')
    title          = standard_field('title')
    authors        = standard_field('authors')
    language       = standard_field('language')
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

    def __init__(self):
        raise NotImplementedError('Abstract base class')

    @dynamic_property
    def package(self):
        def fget(self):
            return self.soup.find(re.compile('package'))
        return property(fget=fget)

    @dynamic_property
    def metadata(self):
        def fget(self):
            return self.package.find(re.compile('metadata'))
        return property(fget=fget)


    def get_title(self):
        title = self.metadata.find('dc:title')
        if title and title.string:
            return self.ENTITY_PATTERN.sub(entity_to_unicode, title.string).strip()
        return self.default_title.strip()

    def get_authors(self):
        creators = self.metadata.findAll('dc:creator')
        for elem in creators:
            role = elem.get('role')
            if not role:
                role = elem.get('opf:role')
            if not role:
                role = 'aut'
            if role == 'aut' and elem.string:
                raw = self.ENTITY_PATTERN.sub(entity_to_unicode, elem.string)
                return string_to_authors(raw)
        return []

    def get_author_sort(self):
        creators = self.metadata.findAll('dc:creator')
        for elem in creators:
            role = elem.get('role')
            if not role:
                role = elem.get('opf:role')
            if role == 'aut':
                fa = elem.get('file-as')
                return self.ENTITY_PATTERN.sub(entity_to_unicode, fa).strip() if fa else None
        return None

    def get_title_sort(self):
        title = self.package.find('dc:title')
        if title:
            if title.has_key('file-as'):
                return title['file-as'].strip()
        return None

    def get_comments(self):
        comments = self.soup.find('dc:description')
        if comments and comments.string:
            return self.ENTITY_PATTERN.sub(entity_to_unicode, comments.string).strip()
        return None

    def get_uid(self):
        package = self.package
        if package.has_key('unique-identifier'):
            return package['unique-identifier']

    def get_category(self):
        category = self.soup.find('dc:type')
        if category and category.string:
            return self.ENTITY_PATTERN.sub(entity_to_unicode, category.string).strip()
        return None

    def get_publisher(self):
        publisher = self.soup.find('dc:publisher')
        if publisher and publisher.string:
            return self.ENTITY_PATTERN.sub(entity_to_unicode, publisher.string).strip()
        return None

    def get_isbn(self):
        for item in self.metadata.findAll('dc:identifier'):
            scheme = item.get('scheme')
            if not scheme:
                scheme = item.get('opf:scheme')
            if scheme is not None and scheme.lower() == 'isbn' and item.string:
                return str(item.string).strip()
        return None

    def get_language(self):
        item = self.metadata.find('dc:language')
        if not item:
            return _('Unknown')
        return ''.join(item.findAll(text=True)).strip()

    def get_application_id(self):
        for item in self.metadata.findAll('dc:identifier'):
            scheme = item.get('scheme', None)
            if scheme is None:
                scheme = item.get('opf:scheme', None)
            if scheme in ['libprs500', 'calibre']:
                return str(item.string).strip()
        return None

    def get_cover(self):
        guide = getattr(self, 'guide', [])
        if not guide:
            guide = []
        references = [ref for ref in guide if 'cover' in ref.type.lower()]
        for candidate in ('cover', 'other.ms-coverimage-standard', 'other.ms-coverimage'):
            matches = [r for r in references if r.type.lower() == candidate and r.path]
            if matches:
                return matches[0].path

    def possible_cover_prefixes(self):
        isbn, ans = [], []
        for item in self.metadata.findAll('dc:identifier'):
            scheme = item.get('scheme')
            if not scheme:
                scheme = item.get('opf:scheme')
            isbn.append((scheme, item.string))
        for item in isbn:
            ans.append(item[1].replace('-', ''))
        return ans

    def get_series(self):
        s = self.metadata.find('series')
        if s is not None:
            return str(s.string).strip()
        return None

    def get_series_index(self):
        s = self.metadata.find('series-index')
        if s and s.string:
            try:
                return float(str(s.string).strip())
            except:
                return None
        return None

    def get_rating(self):
        s = self.metadata.find('rating')
        if s and s.string:
            try:
                return int(str(s.string).strip())
            except:
                return None
        return None

    def get_tags(self):
        ans = []
        subs = self.soup.findAll('dc:subject')
        for sub in subs:
            val = sub.string
            if val:
                ans.append(val)
        return [unicode(a).strip() for a in ans]


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
        self.soup = OPFSoup(stream.read())
        if manage:
            stream.close()
        self.manifest = Manifest()
        m = self.soup.find(re.compile('manifest'))
        if m is not None:
            self.manifest = Manifest.from_opf_manifest_element(m, dir)
        self.spine = None
        spine = self.soup.find(re.compile('spine'))
        if spine is not None:
            self.spine = Spine.from_opf_spine_element(spine, self.manifest)

        self.toc = TOC(base_path=dir)
        self.toc.read_from_opf(self)
        guide = self.soup.find(re.compile('guide'))
        if guide is not None:
            self.guide = Guide.from_opf_guide(guide, dir)
        self.base_dir = dir
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
        from calibre.utils.genshi.template import MarkupTemplate
        opf_template = open(P('templates/opf.xml'), 'rb').read()
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
        if not opf.startswith('<?xml '):
            opf = '<?xml version="1.0"  encoding="UTF-8"?>\n'+opf
        opf_stream.write(opf)
        opf_stream.flush()
        toc = getattr(self, 'toc', None)
        if toc is not None and ncx_stream is not None:
            toc.render(ncx_stream, self.application_id)
            ncx_stream.flush()

