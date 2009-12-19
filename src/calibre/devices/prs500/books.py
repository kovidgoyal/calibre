__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
"""
This module contains the logic for dealing with XML book lists found
in the reader cache.
"""
import xml.dom.minidom as dom
from base64 import b64decode as decode
from base64 import b64encode as encode
import re

from calibre.devices.interface import BookList as _BookList
from calibre.devices import strftime, strptime

MIME_MAP   = { \
                        "lrf":"application/x-sony-bbeb", \
                        'lrx':'application/x-sony-bbeb', \
                        "rtf":"application/rtf", \
                        "pdf":"application/pdf", \
                        "txt":"text/plain" \
                      }

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
                            formatter=lambda x: x if x and x.strip() else "Unknown")
    mime         = book_metadata_field("mime")
    rpath        = book_metadata_field("path")
    id           = book_metadata_field("id", formatter=int)
    sourceid     = book_metadata_field("sourceid", formatter=int)
    size         = book_metadata_field("size", formatter=int)
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
            return self.root + self.rpath
        return property(fget=fget, doc=doc)

    @dynamic_property
    def db_id(self):
        doc = '''The database id in the application database that this file corresponds to'''
        def fget(self):
            match = re.search(r'_(\d+)$', self.rpath.rpartition('.')[0])
            if match:
                return int(match.group(1))
        return property(fget=fget, doc=doc)

    def __init__(self, node, tags=[], prefix="", root="/Data/media/"):
        self.elem   = node
        self.prefix = prefix
        self.root   = root
        self.tags   = tags

    def __str__(self):
        """ Return a utf-8 encoded string with title author and path information """
        return self.title.encode('utf-8') + " by " + \
               self.authors.encode('utf-8') + " at " + self.path.encode('utf-8')


def fix_ids(media, cache, *args):
    '''
    Adjust ids in cache to correspond with media.
    '''
    media.purge_empty_playlists()
    media.reorder_playlists()
    if cache.root:
        sourceid = media.max_id()
        cid = sourceid + 1
        for child in cache.root.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.hasAttribute("sourceid"):
                child.setAttribute("sourceid", str(sourceid))
                child.setAttribute("id", str(cid))
                cid += 1
        media.set_next_id(str(cid))


class BookList(_BookList):
    """
    A list of L{Book}s. Created from an XML file. Can write list
    to an XML file.
    """
    __getslice__ = None
    __setslice__ = None

    def __init__(self, root="/Data/media/", sfile=None):
        _BookList.__init__(self)
        self.tag_order = {}
        self.root = self.document = self.proot = None
        if sfile:
            sfile.seek(0)
            src = sfile.read()
            try:
                src = src.decode('utf8')
            except UnicodeDecodeError:
                try:
                    src = src.decode('latin1')
                except UnicodeDecodeError:
                    src = src.decode('cp1252')
            src = src.replace('<cache:', '<xs1:').replace('</cache:', '</xs1:').replace('xmlns:cache', 'xmlns:xs1')
            self.document = dom.parseString(src.encode('utf8'))
            self.root = self.document.documentElement
            self.prefix = ''
            records = self.root.getElementsByTagName('records')
            if records:
                self.prefix = 'xs1:'
                self.root = records[0]
            self.proot = root

            for book in self.document.getElementsByTagName(self.prefix + "text"):
                id = book.getAttribute('id')
                pl = [i.getAttribute('title') for i in self.get_playlists(id)]
                self.append(Book(book, root=root, prefix=self.prefix, tags=pl))

    def supports_tags(self):
        return bool(self.prefix)

    def playlists(self):
        return self.root.getElementsByTagName(self.prefix+'playlist')

    def playlist_items(self):
        plitems = []
        for pl in self.playlists():
            plitems.extend(pl.getElementsByTagName(self.prefix+'item'))
        return plitems

    def purge_corrupted_files(self):
        if not self.root:
            return []
        corrupted = self.root.getElementsByTagName(self.prefix+'corrupted')
        paths = []
        proot = self.proot if self.proot.endswith('/') else self.proot + '/'
        for c in corrupted:
            paths.append(proot + c.getAttribute('path'))
            c.parentNode.removeChild(c)
            c.unlink()
        return paths

    def purge_empty_playlists(self):
        ''' Remove all playlist entries that have no children. '''
        for pl in self.playlists():
            if not pl.getElementsByTagName(self.prefix + 'item'):
                pl.parentNode.removeChild(pl)
                pl.unlink()

    def _delete_book(self, node):
        nid = node.getAttribute('id')
        node.parentNode.removeChild(node)
        node.unlink()
        self.remove_from_playlists(nid)


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

    def next_id(self):
        return self.document.documentElement.getAttribute('nextID')

    def set_next_id(self, id):
        self.document.documentElement.setAttribute('nextID', str(id))

    def max_id(self):
        max = 0
        for child in self.root.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.hasAttribute("id"):
                nid = int(child.getAttribute('id'))
                if nid > max:
                    max = nid
        return max

    def book_by_path(self, path):
        for child in self.root.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.hasAttribute("path"):
                if path == child.getAttribute('path'):
                    return child
        return None

    def add_book(self, info, name, size, ctime):
        """ Add a node into DOM tree representing a book """
        book = self.book_by_path(name)
        if book is not None:
            self.remove_book(name)
        node = self.document.createElement(self.prefix + "text")
        mime = MIME_MAP[name[name.rfind(".")+1:].lower()]
        cid = self.max_id()+1
        sourceid = str(self[0].sourceid) if len(self) else "1"
        attrs = {
                 "title"  : info["title"],
                 'titleSorter' : sortable_title(info['title']),
                 "author" : info["authors"] if info['authors'] else 'Unknown', \
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
        self.root.appendChild(node)
        book = Book(node, root=self.proot, prefix=self.prefix)
        book.datetime = ctime
        self.append(book)
        self.set_next_id(cid+1)
        if self.prefix and info.has_key('tags'): # Playlists only supportted in main memory
            if info.has_key('tag order'):
                self.tag_order.update(info['tag order'])
            self.set_playlists(book.id, info['tags'])


    def playlist_by_title(self, title):
        for pl in self.playlists():
            if pl.getAttribute('title').lower() == title.lower():
                return pl

    def add_playlist(self, title):
        cid = self.max_id()+1
        pl = self.document.createElement(self.prefix+'playlist')
        pl.setAttribute('sourceid', '0')
        pl.setAttribute('id', str(cid))
        pl.setAttribute('title', title)
        for child in self.root.childNodes:
            try:
                if child.getAttribute('id') == '1':
                    self.root.insertBefore(pl, child)
                    self.set_next_id(cid+1)
                    break
            except AttributeError:
                continue
        return pl


    def remove_from_playlists(self, id):
        for pli in self.playlist_items():
            if pli.getAttribute('id') == str(id):
                pli.parentNode.removeChild(pli)
                pli.unlink()

    def set_tags(self, book, tags):
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

    def get_playlists(self, id):
        ans = []
        for pl in self.playlists():
            for item in pl.getElementsByTagName(self.prefix+'item'):
                if item.getAttribute('id') == str(id):
                    ans.append(pl)
                    continue
        return ans

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

    def write(self, stream):
        """ Write XML representation of DOM tree to C{stream} """
        stream.write(self.document.toxml('utf-8'))
