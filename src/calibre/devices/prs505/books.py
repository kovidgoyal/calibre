__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
'''
import re, time, functools
from uuid import uuid4 as _uuid
import xml.dom.minidom as dom
from base64 import b64decode as decode
from base64 import b64encode as encode


from calibre.devices.interface import BookList as _BookList
from calibre.devices import strftime as _strftime
from calibre.devices import strptime

strftime = functools.partial(_strftime, zone=time.gmtime)

MIME_MAP   = {
                "lrf" : "application/x-sony-bbeb",
                'lrx' : 'application/x-sony-bbeb',
                "rtf" : "application/rtf",
                "pdf" : "application/pdf",
                "txt" : "text/plain" ,
                'epub': 'application/epub+zip',
              }

def uuid():
    return str(_uuid()).replace('-', '', 1).upper()

def sortable_title(title):
    return re.sub('^\s*A\s+|^\s*The\s+|^\s*An\s+', '', title).rstrip()

class book_metadata_field(object):
    """ Represents metadata stored as an attribute """
    def __init__(self, attr, formatter=None, setter=None):
        self.attr = attr
        self.formatter = formatter
        self.setter = setter

    def __get__(self, obj, typ=None):
        """ Return a string. String may be empty if self.attr is absent """
        return self.formatter(obj.elem.getAttribute(self.attr)) if \
                           self.formatter else obj.elem.getAttribute(self.attr).strip()

    def __set__(self, obj, val):
        """ Set the attribute """
        val = self.setter(val) if self.setter else val
        if not isinstance(val, unicode):
            val = unicode(val, 'utf8', 'replace')
        obj.elem.setAttribute(self.attr, val)


class Book(object):
    """ Provides a view onto the XML element that represents a book """

    title        = book_metadata_field("title")
    authors      = book_metadata_field("author", \
                            formatter=lambda x: x if x and x.strip() else _('Unknown'))
    mime         = book_metadata_field("mime")
    rpath        = book_metadata_field("path")
    id           = book_metadata_field("id", formatter=int)
    sourceid     = book_metadata_field("sourceid", formatter=int)
    size         = book_metadata_field("size", formatter=lambda x : int(float(x)))
    # When setting this attribute you must use an epoch
    datetime     = book_metadata_field("date", formatter=strptime, setter=strftime)

    @dynamic_property
    def title_sorter(self):
        doc = '''String to sort the title. If absent, title is returned'''
        def fget(self):
            src = self.elem.getAttribute('titleSorter').strip()
            if not src:
                src = self.title
            return src
        def fset(self, val):
            self.elem.setAttribute('titleSorter', sortable_title(unicode(val)))
        return property(doc=doc, fget=fget, fset=fset)

    @dynamic_property
    def thumbnail(self):
        doc = \
        """
        The thumbnail. Should be a height 68 image.
        Setting is not supported.
        """
        def fget(self):
            th = self.elem.getElementsByTagName(self.prefix + "thumbnail")
            if not len(th):
                th = self.elem.getElementsByTagName("cache:thumbnail")
            if len(th):
                for n in th[0].childNodes:
                    if n.nodeType == n.ELEMENT_NODE:
                        th = n
                        break
                rc = ""
                for node in th.childNodes:
                    if node.nodeType == node.TEXT_NODE:
                        rc += node.data
                return decode(rc)
        return property(fget=fget, doc=doc)

    @dynamic_property
    def path(self):
        doc = """ Absolute path to book on device. Setting not supported. """
        def fget(self):
            return self.mountpath + self.rpath
        return property(fget=fget, doc=doc)

    @dynamic_property
    def db_id(self):
        doc = '''The database id in the application database that this file corresponds to'''
        def fget(self):
            match = re.search(r'_(\d+)$', self.rpath.rpartition('.')[0])
            if match:
                return int(match.group(1))
        return property(fget=fget, doc=doc)

    def __init__(self, node, mountpath, tags, prefix=""):
        self.elem      = node
        self.prefix    = prefix
        self.tags      = tags
        self.mountpath = mountpath

    def __str__(self):
        """ Return a utf-8 encoded string with title author and path information """
        return self.title.encode('utf-8') + " by " + \
               self.authors.encode('utf-8') + " at " + self.path.encode('utf-8')


class BookList(_BookList):

    def __init__(self, xml_file, mountpath, report_progress=None):
        _BookList.__init__(self)
        xml_file.seek(0)
        self.document = dom.parse(xml_file)
        self.root_element = self.document.documentElement
        self.mountpath = mountpath
        records = self.root_element.getElementsByTagName('records')
        self.tag_order = {}

        if records:
            self.prefix = 'xs1:'
            self.root_element = records[0]
        else:
            self.prefix = ''

        nodes = self.root_element.childNodes
        for i, book in enumerate(nodes):
            if report_progress:
                report_progress((i+1) / float(len(nodes)), _('Getting list of books on device...'))
            if hasattr(book, 'tagName') and book.tagName.endswith('text'):
                tags = [i.getAttribute('title') for i in self.get_playlists(book.getAttribute('id'))]
                self.append(Book(book, mountpath, tags, prefix=self.prefix))

    def max_id(self):
        max = 0
        for child in self.root_element.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.hasAttribute("id"):
                nid = int(child.getAttribute('id'))
                if nid > max:
                    max = nid
        return max

    def is_id_valid(self, id):
        '''Return True iff there is an element with C{id==id}.'''
        id = str(id)
        for child in self.root_element.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.hasAttribute("id"):
                if child.getAttribute('id') == id:
                    return True
        return False

    def supports_tags(self):
        return True

    def book_by_path(self, path):
        for child in self.root_element.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.hasAttribute("path"):
                if path == child.getAttribute('path'):
                    return child
        return None

    def add_book(self, info, name, size, ctime):
        """ Add a node into the DOM tree, representing a book """
        book = self.book_by_path(name)
        if book is not None:
            self.remove_book(name)

        node = self.document.createElement(self.prefix + "text")
        mime = MIME_MAP[name.rpartition('.')[-1].lower()]
        cid = self.max_id()+1
        try:
            sourceid = str(self[0].sourceid) if len(self) else '1'
        except:
            sourceid = '1'
        attrs = {
                 "title"  : info["title"],
                 'titleSorter' : sortable_title(info['title']),
                 "author" : info["authors"] if info['authors'] else _('Unknown'),
                 "page":"0", "part":"0", "scale":"0", \
                 "sourceid":sourceid,  "id":str(cid), "date":"", \
                 "mime":mime, "path":name, "size":str(size)
                 }
        for attr in attrs.keys():
            node.setAttributeNode(self.document.createAttribute(attr))
            node.setAttribute(attr, attrs[attr])
        try:
            w, h, data = info["cover"]
        except TypeError:
            w, h, data = None, None, None

        if data:
            th = self.document.createElement(self.prefix + "thumbnail")
            th.setAttribute("width", str(w))
            th.setAttribute("height", str(h))
            jpeg = self.document.createElement(self.prefix + "jpeg")
            jpeg.appendChild(self.document.createTextNode(encode(data)))
            th.appendChild(jpeg)
            node.appendChild(th)
        self.root_element.appendChild(node)
        book = Book(node, self.mountpath, [], prefix=self.prefix)
        book.datetime = ctime
        self.append(book)
        if info.has_key('tags'):
            if info.has_key('tag order'):
                self.tag_order.update(info['tag order'])
            self.set_tags(book, info['tags'])

    def _delete_book(self, node):
        nid = node.getAttribute('id')
        self.remove_from_playlists(nid)
        node.parentNode.removeChild(node)
        node.unlink()

    def delete_book(self, cid):
        '''
        Remove DOM node corresponding to book with C{id == cid}.
        Also remove book from any collections it is part of.
        '''
        for book in self:
            if str(book.id) == str(cid):
                self.remove(book)
                self._delete_book(book.elem)
                break

    def remove_book(self, path):
        '''
        Remove DOM node corresponding to book with C{path == path}.
        Also remove book from any collections it is part of.
        '''
        for book in self:
            if path.endswith(book.rpath):
                self.remove(book)
                self._delete_book(book.elem)
                break

    def playlists(self):
        ans = []
        for c in self.root_element.childNodes:
            if hasattr(c, 'tagName')  and c.tagName.endswith('playlist'):
                ans.append(c)
        return ans

    def playlist_items(self):
        plitems = []
        for pl in self.playlists():
            for c in pl.childNodes:
                if hasattr(c, 'tagName')  and c.tagName.endswith('item'):
                    plitems.append(c)
        return plitems

    def purge_corrupted_files(self):
        if not self.root_element:
            return []
        corrupted = self.root_element.getElementsByTagName(self.prefix+'corrupted')
        paths = []
        for c in corrupted:
            paths.append(c.getAttribute('path'))
            c.parentNode.removeChild(c)
            c.unlink()
        return paths

    def purge_empty_playlists(self):
        ''' Remove all playlists that have no children. Also removes any invalid playlist items.'''
        for pli in self.playlist_items():
            try:
                if not self.is_id_valid(pli.getAttribute('id')):
                    pli.parentNode.removeChild(pli)
                    pli.unlink()
            except:
                continue
        for pl in self.playlists():
            empty = True
            for c in pl.childNodes:
                if hasattr(c, 'tagName') and c.tagName.endswith('item'):
                    empty = False
                    break
            if empty:
                pl.parentNode.removeChild(pl)
                pl.unlink()

    def playlist_by_title(self, title):
        for pl in self.playlists():
            if pl.getAttribute('title').lower() == title.lower():
                return pl

    def add_playlist(self, title):
        cid = self.max_id()+1
        pl = self.document.createElement(self.prefix+'playlist')
        pl.setAttribute('id', str(cid))
        pl.setAttribute('title', title)
        pl.setAttribute('uuid', uuid())
        self.root_element.insertBefore(pl, self.root_element.childNodes[-1])
        return pl

    def remove_from_playlists(self, id):
        for pli in self.playlist_items():
            if pli.getAttribute('id') == str(id):
                pli.parentNode.removeChild(pli)
                pli.unlink()

    def set_tags(self, book, tags):
        tags = [t for t in tags if t]
        book.tags = tags
        self.set_playlists(book.id, tags)

    def set_playlists(self, id, collections):
        self.remove_from_playlists(id)
        for collection in set(collections):
            coll = self.playlist_by_title(collection)
            if not coll:
                coll = self.add_playlist(collection)
            item = self.document.createElement(self.prefix+'item')
            item.setAttribute('id', str(id))
            coll.appendChild(item)

    def get_playlists(self, bookid):
        ans = []
        for pl in self.playlists():
            for item in pl.childNodes:
                if hasattr(item, 'tagName') and item.tagName.endswith('item'):
                    if item.getAttribute('id') == str(bookid):
                        ans.append(pl)
        return ans

    def next_id(self):
        return self.document.documentElement.getAttribute('nextID')

    def set_next_id(self, id):
        self.document.documentElement.setAttribute('nextID', str(id))

    def write(self, stream):
        """ Write XML representation of DOM tree to C{stream} """
        src = self.document.toxml('utf-8') + '\n'
        stream.write(src.replace("'", '&apos;'))

    def book_by_id(self, id):
        for book in self:
            if str(book.id) == str(id):
                return book

    def reorder_playlists(self):
        for title in self.tag_order.keys():
            pl = self.playlist_by_title(title)
            if not pl:
                continue
            db_ids = [i.getAttribute('id') for i in pl.childNodes if hasattr(i, 'getAttribute')]
            pl_book_ids = [self.book_by_id(i.getAttribute('id')).db_id for i in pl.childNodes  if hasattr(i, 'getAttribute')]
            map = {}
            for i, j in zip(pl_book_ids, db_ids):
                map[i] = j
            pl_book_ids = [i for i in pl_book_ids if i is not None]
            ordered_ids = [i for i in self.tag_order[title] if i in pl_book_ids]

            if len(ordered_ids) < len(pl.childNodes):
                continue
            children = [i for i in pl.childNodes  if hasattr(i, 'getAttribute')]
            for child in children:
                pl.removeChild(child)
                child.unlink()
            for id in ordered_ids:
                item = self.document.createElement(self.prefix+'item')
                item.setAttribute('id', str(map[id]))
                pl.appendChild(item)

def fix_ids(main, carda, cardb):
    '''
    Adjust ids the XML databases.
    '''
    if hasattr(main, 'purge_empty_playlists'):
        main.purge_empty_playlists()
    if hasattr(carda, 'purge_empty_playlists'):
        carda.purge_empty_playlists()
    if hasattr(cardb, 'purge_empty_playlists'):
        cardb.purge_empty_playlists()

    def regen_ids(db):
        if not hasattr(db, 'root_element'):
            return
        id_map = {}
        db.purge_empty_playlists()
        cid = 0 if db == main else 1
        for child in db.root_element.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.hasAttribute('id'):
                id_map[child.getAttribute('id')] = str(cid)
                child.setAttribute("sourceid",
                    '0' if getattr(child, 'tagName', '').endswith('playlist') else '1')
                child.setAttribute('id', str(cid))
                cid += 1

        for item in db.playlist_items():
            oid = item.getAttribute('id')
            try:
                item.setAttribute('id', id_map[oid])
            except KeyError:
                item.parentNode.removeChild(item)
                item.unlink()

        db.reorder_playlists()

    regen_ids(main)
    regen_ids(carda)
    regen_ids(cardb)

    main.set_next_id(str(main.max_id()+1))
