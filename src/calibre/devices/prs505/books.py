__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
'''
import re, time, functools
from uuid import uuid4 as _uuid
import xml.dom.minidom as dom
from base64 import b64encode as encode


from calibre.devices.usbms.books import BookList as _BookList
from calibre.devices import strftime as _strftime
from calibre.devices.prs505 import MEDIA_XML, CACHE_XML
from calibre.devices.errors import PathError

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

class BookList(_BookList):

    def __init__(self, oncard, prefix, settings):
        _BookList.__init__(self, oncard, prefix, settings)
        if prefix is None:
            return
        self.sony_id_cache = {}
        self.books_lpath_cache = {}
        opts = settings()
        self.collections = opts.extra_customization.split(',') if opts.extra_customization else []
        db = CACHE_XML if oncard else MEDIA_XML
        xml_file = open(prefix + db, 'rb')
        xml_file.seek(0)
        self.document = dom.parse(xml_file)
        self.root_element = self.document.documentElement
        self.mountpath = prefix
        records = self.root_element.getElementsByTagName('records')

        if records:
            self.prefix = 'xs1:'
            self.root_element = records[0]
        else:
            self.prefix = ''
        for child in self.root_element.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.hasAttribute("id"):
                self.sony_id_cache[child.getAttribute('id')] = child.getAttribute('path')
                # set the key to none. Will be filled in later when booklist is built
                self.books_lpath_cache[child.getAttribute('path')] = None
        self.tag_order = {}

        paths = self.purge_corrupted_files()
        for path in paths:
            try:
                self.del_file(path, end_session=False)
            except PathError: # Incase this is a refetch without a sync in between
                continue


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

    def add_book(self, book, replace_metadata):
        # Add a node into the DOM tree, representing a book. Also add to booklist
        if book in self:
            # replacing metadata for book
            self.delete_node(book.lpath)
        else:
            self.append(book)
            if not replace_metadata:
                if self.books_lpath_cache.has_key(book.lpath):
                    self.books_lpath_cache[book.lpath] = book
                    return
        # Book not in metadata. Add it. Note that we don't need to worry about
        # extra books in the Sony metadata. The reader deletes them for us when
        # we disconnect. That said, if it becomes important one day, we can do
        # it by scanning the books_lpath_cache for None entries and removing the
        # corresponding nodes.
        self.books_lpath_cache[book.lpath] = book
        cid = self.max_id()+1
        node = self.document.createElement(self.prefix + "text")
        self.sony_id_cache[cid] = book.lpath
        mime = MIME_MAP.get(book.lpath.rpartition('.')[-1].lower(), MIME_MAP['epub'])
        try:
            sourceid = str(self[0].sourceid) if len(self) else '1'
        except:
            sourceid = '1'
        attrs = {
                 "title"  : book.title,
                 'titleSorter' : sortable_title(book.title),
                 "author" : book.format_authors() if book.format_authors() else _('Unknown'),
                 "page":"0", "part":"0", "scale":"0", \
                 "sourceid":sourceid,  "id":str(cid), "date":"", \
                 "mime":mime, "path":book.lpath, "size":str(book.size)
                 }
        for attr in attrs.keys():
            node.setAttributeNode(self.document.createAttribute(attr))
            node.setAttribute(attr, attrs[attr])
        try:
            w, h, data = book.thumbnail
        except:
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

        tags = []
        for item in self.collections:
            item = item.strip()
            mitem = getattr(book, item, None)
            titems = []
            if mitem:
                if isinstance(mitem, list):
                    titems = mitem
                else:
                    titems = [mitem]
                if item == 'tags' and titems:
                    litems = []
                    for i in titems:
                        if not i.strip().startswith('[') and not i.strip().endswith(']'):
                            litems.append(i)
                    titems = litems
                tags.extend(titems)
        if tags:
            tags = list(set(tags))
            if hasattr(book, 'tag_order'):
                self.tag_order.update(book.tag_order)
            self.set_playlists(cid, tags)
        return True  # metadata cache has changed. Must sync at end

    def _delete_node(self, node):
        nid = node.getAttribute('id')
        self.remove_from_playlists(nid)
        node.parentNode.removeChild(node)
        node.unlink()

    def delete_node(self, lpath):
        '''
        Remove DOM node corresponding to book with lpath.
        Also remove book from any collections it is part of.
        '''
        for child in self.root_element.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.hasAttribute("id"):
                if child.getAttribute('path') == lpath:
                    self._delete_node(child)
                    break

    def remove_book(self, book):
        '''
        Remove DOM node corresponding to book with C{path == path}.
        Also remove book from any collections it is part of, and remove
        from the booklist
        '''
        self.remove(book)
        self.delete_node(book.lpath)

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
                if hasattr(c, 'tagName') and c.tagName.endswith('item') and \
                    hasattr(c, 'getAttribute'):
                    try:
                        c.getAttribute('id')
                    except: # Unlinked node
                        continue
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

    def next_id(self):
        return self.document.documentElement.getAttribute('nextID')

    def set_next_id(self, id):
        self.document.documentElement.setAttribute('nextID', str(id))

    def write(self, stream):
        """ Write XML representation of DOM tree to C{stream} """
        src = self.document.toxml('utf-8') + '\n'
        stream.write(src.replace("'", '&apos;'))

    def reorder_playlists(self):
        for title in self.tag_order.keys():
            pl = self.playlist_by_title(title)
            if not pl:
                continue
            # make a list of the ids
            sony_ids = [id.getAttribute('id') \
                    for id in pl.childNodes if hasattr(id, 'getAttribute')]
            # convert IDs in playlist to a list of lpaths
            sony_paths = [self.sony_id_cache[id] for id in sony_ids]
            # create list of books containing lpaths
            books = [self.books_lpath_cache.get(p, None) for p in sony_paths]
            # create dict of db_id -> sony_id
            imap = {}
            for book, sony_id in zip(books, sony_ids):
                if book is not None:
                    db_id = book.application_id
                    if db_id is None:
                        db_id = book.db_id
                    if db_id is not None:
                        imap[book.application_id] = sony_id
            # filter the list, removing books not on device but on playlist
            books = [i for i in books if i is not None]
            # filter the order specification to the books we have
            ordered_ids = [db_id for db_id in self.tag_order[title] if db_id in imap]

            # rewrite the playlist in the correct order
            if len(ordered_ids) < len(pl.childNodes):
                continue
            children = [i for i in pl.childNodes if hasattr(i, 'getAttribute')]
            for child in children:
                pl.removeChild(child)
                child.unlink()
            for id in ordered_ids:
                item = self.document.createElement(self.prefix+'item')
                item.setAttribute('id', str(imap[id]))
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
        db.sony_id_cache = {}
        for child in db.root_element.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.hasAttribute("id"):
                db.sony_id_cache[child.getAttribute('id')] = child.getAttribute('path')


    regen_ids(main)
    regen_ids(carda)
    regen_ids(cardb)

    main.set_next_id(str(main.max_id()+1))
