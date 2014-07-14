#!/usr/bin/python2.7
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, os, posixpath, cherrypy, cgi, tempfile, logging
from utils import T
from calibre.ebooks.metadata.meta import get_metadata

from calibre import fit_image, guess_type
from calibre.utils.date import fromtimestamp
from calibre.library.caches import SortKeyGenerator
from calibre.library.save_to_disk import find_plugboard
from calibre.ebooks.metadata import authors_to_string
from calibre.utils.magick.draw import (save_cover_data_to, Image,
        thumbnail as generate_thumbnail)
from calibre.utils.filenames import ascii_filename
from calibre.ebooks.metadata.opf2 import metadata_to_opf

plugboard_content_server_value = 'content_server'
plugboard_content_server_formats = ['epub']

class CSSortKeyGenerator(SortKeyGenerator):

    def __init__(self, fields, fm, db_prefs):
        SortKeyGenerator.__init__(self, fields, fm, None, db_prefs)

    def __call__(self, record):
        return self.itervals(record).next()

class Endpoint(object): # {{{
    'Manage encoding, mime-type, last modified, cookies, etc.'

    def __init__(self, mimetype='text/html; charset=utf-8', sort_type='category'):
        self.mimetype = mimetype
        self.sort_type = sort_type
        self.sort_kwarg = sort_type + '_sort'
        self.sort_cookie_name = 'calibre_browse_server_sort_'+self.sort_type

    def __call__(eself, func):
        def do(self, *args, **kwargs):
            if 'json' not in eself.mimetype:
                sort_val = None
                cookie = cherrypy.request.cookie
                if cookie.has_key(eself.sort_cookie_name):
                    sort_val = cookie[eself.sort_cookie_name].value
                kwargs[eself.sort_kwarg] = sort_val

            # Remove AJAX caching disabling jquery workaround arg
            kwargs.pop('_', None)

            ans = func(self, *args, **kwargs)
            cherrypy.response.headers['Content-Type'] = eself.mimetype
            updated = self.db.last_modified()
            cherrypy.response.headers['Last-Modified'] = \
                self.last_modified(max(updated, self.build_time))
            ans = utf8(ans)
            return ans

        do.__name__ = func.__name__

        return do
# }}}

class HtmlServer(object):
    '''
    Handles actually serving content files/covers/metadata. Also has
    a few utility methods.
    '''
    def add_routes(self, connect):
        connect('index',         '/',             self.index)
        connect('book_list',     '/book',         self.book_list)
        connect('book_add',      '/book/add',     self.book_add)
        connect('book_upload',   '/book/upload',  self.book_upload)
        connect('book_delete',   '/book/{id}/delete',  self.book_delete)
        connect('book_download', '/book/{id}.{fmt}',   self.book_download)
        connect('book_detail',   '/book/{id}',    self.book_detail)
        connect('author_list',   '/author',       self.author_list)
        connect('author_detail', '/author/{name}',self.author_detail)
        connect('tag_list',      '/tag',          self.tag_list)
        connect('tag_detail',    '/tag/{name}',   self.tag_detail)
        connect('pub_list',      '/pub',          self.pub_list)
        connect('pub_detail',    '/pub/{name}',   self.pub_detail)
        connect('rating_list',   '/rating',       self.rating_list)
        connect('rating_detail', '/rating/{name}',self.rating_detail)

        connect('get',     '/get/{what}/{id}', self.get,
                conditions=dict(method=["GET", "HEAD"]))
        connect('static',  '/static/{name:.*?}', self.static,
                conditions=dict(method=["GET", "HEAD"]))

    def cache_html(self, template, *args, **kwargs):
        url_prfix = self.opts.url_prefix
        M = "/static/v2/m"
        db = self.db
        vals = dict(*args, **kwargs)
        vals.update( vars() )
        ans = T(template).render(vals)

        cherrypy.response.headers['Content-Type'] = 'text/html; charset=utf-8'
        updated = self.db.last_modified()
        cherrypy.response.headers['Last-Modified'] = \
                self.last_modified(max(updated, self.build_time))
        if isinstance(ans, unicode):
            ans = ans.encode('utf-8')
        return ans

    def index(self, **kwargs):
        'The / URL'
        ua = cherrypy.request.headers.get('User-Agent', '').strip()
        want_opds = \
            cherrypy.request.headers.get('Stanza-Device-Name', 919) != 919 or \
            cherrypy.request.headers.get('Want-OPDS-Catalog', 919) != 919 or \
            ua.startswith('Stanza')

        if want_opds:
            return self.opds(version=0)
        return self.cache_html('content_server/v2/index.html', vars())

    def book_list(self):
        title = _('All books')
        delta = 20
        try: page = int(page)
        except: page = 0

        category_type = "list_all"
        category_name = _('All books')
        ids = self.search_cache('')
        page_now = page*delta
        page_max = len(ids)
        page_prev = None if page - 1 < 0 else page - 1
        page_next = None if page + 1 > page_max else page + 1
        books = self.db.get_data_as_dict(ids=ids)[page:page+delta]
        return self.cache_html('content_server/v2/book/list.html', vars())

    def book_detail(self, id):
        book_id = int(id)
        books = self.db.get_data_as_dict(ids=[book_id])
        book = books[0]
        try: sizes = [ (f, self.db.sizeof_format(book['id'], f, index_is_id=True)) for f in book['available_formats'] ]
        except: sizes = []
        return self.cache_html('content_server/v2/book/detail.html', vars())

    def book_delete(self, id):
        self.db.delete_book(int(id))
        raise cherrypy.HTTPRedirect("/book", 302)

    def book_download(self, id, fmt):
        book_id = int(id)
        books = self.db.get_data_as_dict(ids=[book_id])
        book = books[0]
        if 'fmt_%s'%fmt not in book:
            raise cherrypy.HTTPError(404, '%s.%s not found'%(name,fmt))
        path = book['fmt_%s'%fmt]
        att = 'attachment; filename="%s"' % (book['title'])
        cherrypy.response.headers['Content-Disposition'] = att
        cherrypy.response.headers['Content-Type'] = 'application/octet-stream'
        with open(path, 'rb') as f:
            ans = f.read()
        return ans;

    def book_add(self, file_input_name="ebook_file"):
        title = _('Upload Book')
        return self.cache_html('content_server/v2/book/add.html', vars())

    @cherrypy.expose
    def book_upload(self, ebook_file=None):
        from calibre.ebooks.metadata import MetaInformation
        cherrypy.response.timeout = 3600

        name = ebook_file.filename
        format = os.path.splitext(name)[1]
        format = format[1:] if format else None
        if not format:
            return "bad file name: %s" % name

        # save file
        data = ''
        while True:
            d = ebook_file.file.read(8192)
            data += d
            if not d: break;

        fpath = "/tmp/" + name
        open(fpath, "wb").write(data)

        # read ebook meta
        stream = open(fpath, 'rb')
        mi = get_metadata(stream, stream_type=format, use_libprs_metadata=True)
        ret = self.db.import_book(mi, [fpath] )
        raise cherrypy.HTTPRedirect('/book/%d'%ret)

    def tag_list(self):
        title = _('All tags')
        category = "tags"
        tags = self.db.all_tags2()
        return self.cache_html('content_server/v2/tag/list.html', vars())

    def tag_detail(self, name):
        title = _('Books of tag: ') + name
        category = "tags"
        tag_id = self.db.tag_id(name)
        ids = self.db.get_books_for_category(category, tag_id)
        books = self.db.get_data_as_dict(ids=ids)
        return self.cache_html('content_server/v2/book/list.html', vars())

    def author_list(self):
        title = _('All authors')
        category = "authors"
        authors = self.db.all_authors()
        return self.cache_html('content_server/v2/author/list.html', vars())

    def author_detail(self, name):
        title = _('Books of author: ') + name
        category = "authors"
        author_id = self.db.author_id(name)
        ids = self.db.get_books_for_category(category, author_id)
        books = self.db.get_data_as_dict(ids=ids)
        return self.cache_html('content_server/v2/book/list.html', vars())

    def pub_list(self):
        title = _('All publishers')
        category = "publishers"
        publishers = self.db.all_publishers()
        return self.cache_html('content_server/v2/publisher/list.html', vars())

    def pub_detail(self, name):
        title = _('Books of publisher: ') + name
        category = "publishers"
        publisher_id = self.db.publisher_id(name)
        ids = self.db.get_books_for_category(category, publisher_id)
        books = self.db.get_data_as_dict(ids=ids)
        return self.cache_html('content_server/v2/book/list.html', vars())

    def rating_list(self):
        title = _('All ratings')
        category = "ratings"
        ratings = self.db.all_ratings()
        return self.cache_html('content_server/v2/rating/list.html', vars())

    def rating_detail(self, name):
        title = _('Books of rating: ') + name
        category = "ratings"
        rating_id = self.db.rating_id(name)
        ids = self.db.get_books_for_category(category, rating_id)
        books = self.db.get_data_as_dict(ids=ids)
        return self.cache_html('content_server/v2/book/list.html', vars())

    # Utility methods {{{
    def last_modified(self, updated):
        '''
        Generates a locale independent, english timestamp from a datetime
        object
        '''
        lm = updated.strftime('day, %d month %Y %H:%M:%S GMT')
        day ={0:'Sun', 1:'Mon', 2:'Tue', 3:'Wed', 4:'Thu', 5:'Fri', 6:'Sat'}
        lm = lm.replace('day', day[int(updated.strftime('%w'))])
        month = {1:'Jan', 2:'Feb', 3:'Mar', 4:'Apr', 5:'May', 6:'Jun', 7:'Jul',
                 8:'Aug', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dec'}
        return lm.replace('month', month[updated.month])


    def sort(self, items, field, order):
        field = self.db.data.sanitize_sort_field_name(field)
        if field not in self.db.field_metadata.sortable_field_keys():
            raise cherrypy.HTTPError(400, '%s is not a valid sort field'%field)
        keyg = CSSortKeyGenerator([(field, order)], self.db.field_metadata,
                                  self.db.prefs)
        items.sort(key=keyg, reverse=not order)

    # }}}

    def get(self, what, id):
        'Serves files, covers, thumbnails, metadata from the calibre database'
        try:
            id = int(id)
        except ValueError:
            id = id.rpartition('_')[-1].partition('.')[0]
            match = re.search(r'\d+', id)
            if not match:
                raise cherrypy.HTTPError(404, 'id:%s not an integer'%id)
            id = int(match.group())
        if not self.db.has_id(id):
            raise cherrypy.HTTPError(404, 'id:%d does not exist in database'%id)
        if what == 'thumb' or what.startswith('thumb_'):
            try:
                width, height = map(int, what.split('_')[1:])
            except:
                width, height = 60, 80
            return self.get_cover(id, thumbnail=True, thumb_width=width,
                    thumb_height=height)
        if what == 'cover':
            return self.get_cover(id)
        if what == 'opf':
            return self.get_metadata_as_opf(id)
        if what == 'json':
            raise cherrypy.InternalRedirect('/ajax/book/%d'%id)
        return self.get_format(id, what)

    def static(self, name):
        'Serves static content'
        name = name.lower()
        fname = posixpath.basename(name)
        try:
            cherrypy.response.headers['Content-Type'] = {
                     'js'   : 'text/javascript',
                     'css'  : 'text/css',
                     'png'  : 'image/png',
                     'gif'  : 'image/gif',
                     'html' : 'text/html',
                     'woff' : 'application/x-font-woff',
                     'ttf'  : 'application/octet-stream',
                     'svg'  : 'image/svg+xml',
                     }[fname.rpartition('.')[-1].lower()]
        except KeyError:
            raise cherrypy.HTTPError(404, '%r not a valid resource type'%name)
        cherrypy.response.headers['Last-Modified'] = self.last_modified(self.build_time)
        basedir = os.path.abspath(P('content_server'))
        path = os.path.join(basedir, name.replace('/', os.sep))
        path = os.path.abspath(path)
        if not path.startswith(basedir):
            raise cherrypy.HTTPError(403, 'Access to %s is forbidden'%name)
        if not os.path.exists(path) or not os.path.isfile(path):
            raise cherrypy.HTTPError(404, '%s not found'%path)
        if self.opts.develop:
            lm = fromtimestamp(os.stat(path).st_mtime)
            cherrypy.response.headers['Last-Modified'] = self.last_modified(lm)
        with open(path, 'rb') as f:
            ans = f.read()
        if path.endswith('.css'):
            ans = ans.replace('/static/', self.opts.url_prefix + '/static/')
        return ans

    def old(self, **kwargs):
        return self.static('index.html').replace('{prefix}',
                self.opts.url_prefix)

    # Actually get content from the database {{{
    def get_cover(self, id, thumbnail=False, thumb_width=60, thumb_height=80):
        try:
            cherrypy.response.headers['Content-Type'] = 'image/jpeg'
            cherrypy.response.timeout = 3600
            cover = self.db.cover(id, index_is_id=True)
            if cover is None:
                cover = self.default_cover
                updated = self.build_time
            else:
                updated = self.db.cover_last_modified(id, index_is_id=True)
            cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)

            if thumbnail:
                return generate_thumbnail(cover,
                        width=thumb_width, height=thumb_height)[-1]

            img = Image()
            img.load(cover)
            width, height = img.size
            scaled, width, height = fit_image(width, height,
                thumb_width if thumbnail else self.max_cover_width,
                thumb_height if thumbnail else self.max_cover_height)
            if not scaled:
                return cover
            return save_cover_data_to(img, 'img.jpg', return_data=True,
                    resize_to=(width, height))
        except Exception as err:
            import traceback
            cherrypy.log.error('Failed to generate cover:')
            cherrypy.log.error(traceback.print_exc())
            raise cherrypy.HTTPError(404, 'Failed to generate cover: %r'%err)

    def get_metadata_as_opf(self, id_):
        cherrypy.response.headers['Content-Type'] = \
                'application/oebps-package+xml; charset=UTF-8'
        mi = self.db.get_metadata(id_, index_is_id=True)
        data = metadata_to_opf(mi)
        cherrypy.response.timeout = 3600
        cherrypy.response.headers['Last-Modified'] = \
                self.last_modified(mi.last_modified)

        return data

    def get_format(self, id, format):
        format = format.upper()
        fm = self.db.format_metadata(id, format, allow_cache=False)
        if not fm:
            raise cherrypy.HTTPError(404, 'book: %d does not have format: %s'%(id, format))
        mi = newmi = self.db.get_metadata(id, index_is_id=True)

        cherrypy.response.headers['Last-Modified'] = \
            self.last_modified(max(fm['mtime'], mi.last_modified))

        fmt = self.db.format(id, format, index_is_id=True, as_file=True,
                mode='rb')
        if fmt is None:
            raise cherrypy.HTTPError(404, 'book: %d does not have format: %s'%(id, format))
        mt = guess_type('dummy.'+format.lower())[0]
        if mt is None:
            mt = 'application/octet-stream'
        cherrypy.response.headers['Content-Type'] = mt

        if format == 'EPUB':
            # Get the original metadata

            # Get any EPUB plugboards for the content server
            plugboards = self.db.prefs.get('plugboards', {})
            cpb = find_plugboard(plugboard_content_server_value,
                                 'epub', plugboards)
            if cpb:
                # Transform the metadata via the plugboard
                newmi = mi.deepcopy_metadata()
                newmi.template_to_attribute(mi, cpb)

        if format in ('MOBI', 'EPUB'):
            # Write the updated file
            from calibre.ebooks.metadata.meta import set_metadata
            set_metadata(fmt, newmi, format.lower())
            fmt.seek(0)

        fmt.seek(0, 2)
        cherrypy.response.headers['Content-Length'] = fmt.tell()
        fmt.seek(0)

        au = authors_to_string(newmi.authors if newmi.authors else
                [_('Unknown')])
        title = newmi.title if newmi.title else _('Unknown')
        fname = u'%s - %s_%s.%s'%(title[:30], au[:30], id, format.lower())
        fname = ascii_filename(fname).replace('"', '_')
        cherrypy.response.headers['Content-Disposition'] = \
                b'attachment; filename="%s"'%fname
        cherrypy.response.body = fmt
        cherrypy.response.timeout = 3600
        return fmt
    # }}}


