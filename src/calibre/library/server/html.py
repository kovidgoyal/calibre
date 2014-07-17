#!/usr/bin/python2.7
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, os, posixpath, cherrypy, cgi, tempfile, logging, sys, json
from calibre.ebooks.metadata.meta import get_metadata

from calibre import fit_image, guess_type
from calibre.utils.date import fromtimestamp
from calibre.utils.smtp import sendmail, create_mail
from calibre.utils.logging import Log
from calibre.utils.filenames import ascii_filename
from calibre.utils.magick.draw import (save_cover_data_to, Image,
        thumbnail as generate_thumbnail)
from calibre.ebooks.metadata.opf2 import metadata_to_opf
from calibre.ebooks.metadata.meta import set_metadata
from calibre.ebooks.metadata import authors_to_string
from calibre.ebooks.conversion.plumber import Plumber
from calibre.library.caches import SortKeyGenerator
from calibre.library.save_to_disk import find_plugboard

import douban

plugboard_content_server_value = 'content_server'
plugboard_content_server_formats = ['epub']

def day_format(value, format='%Y-%m-%d'):
    try:
        return value.strftime(format)
    except:
        return "1990-01-01"

def T(name):
    from jinja2 import Environment, FileSystemLoader
    loader = FileSystemLoader(sys.resources_location)
    env = Environment(loader=loader, extensions=['jinja2.ext.i18n'])
    env.install_gettext_callables(_, _, newstyle=False)
    env.filters['day'] = day_format
    return env.get_template(name)

class HtmlServer(object):
    '''
    Handles actually serving content files/covers/metadata. Also has
    a few utility methods.
    '''
    def add_routes(self, connect):
        connect(         '/',                       self.index)
        connect(     '/book',                   self.book_list)
        connect(      '/book/add',               self.book_add)
        connect(   '/book/upload',            self.book_upload)
        connect(   '/book/{id}/delete',       self.book_delete)
        connect(     '/book/{id}/edit',         self.book_edit)
        connect(   '/book/{id}/update',       self.book_update)
        connect( '/book/{id}.{fmt}',        self.book_download)
        connect(  '/book/{id}/share/kindle', self.share_kindle)
        connect(   '/book/{id}',              self.book_detail)
        connect(   '/author',                 self.author_list)
        connect( '/author/{name}',          self.author_detail)
        connect( '/author/{name}/update',   self.author_books_update)
        connect(      '/tag',                    self.tag_list)
        connect(    '/tag/{name}',             self.tag_detail)
        connect(      '/pub',                    self.pub_list)
        connect(    '/pub/{name}',             self.pub_detail)
        #connect(    '/pub/{name}/update',      self.pub_update)
        connect(   '/rating',                 self.rating_list)
        connect( '/rating/{name}',          self.rating_detail)
        connect(        '/search',                 self.search_book)
        connect(  '/setting',                self.setting_view)
        connect(  '/setting/save',           self.setting_save)

        connect(     '/get/{fmt}/{id}', self.get,
                conditions=dict(method=["GET", "HEAD"]))
        connect(  '/static/{name:.*?}', self.static,
                conditions=dict(method=["GET", "HEAD"]))

    def html_page(self, template, *args, **kwargs):
        url_prfix = self.opts.url_prefix
        M = "/static/v2/m"
        db = self.db
        vals = dict(*args, **kwargs)
        vals.update( vars() )
        ans = T(template).render(vals)

        cherrypy.response.headers['Content-Type'] = 'text/html; charset=utf-8'
        #updated = self.db.last_modified()
        #cherrypy.response.headers['Last-Modified'] = \
                #self.last_modified(max(updated, self.build_time))
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
        return self.html_index()

    def do_sort(self, items, field, order):
        items.sort(cmp=lambda x,y: cmp(x[field], y[field]), reverse=not order)

    def sort_books(self, items, field):
        self.do_sort(items, 'title', True)
        fm = self.db.field_metadata
        keys = frozenset(fm.sortable_field_keys())
        if field in keys:
            ascending = fm[field]['datatype'] not in ('rating', 'datetime', 'series')
            self.do_sort(items, field, ascending)
        return None

    @cherrypy.expose
    def search_book(self, name=None, start=0, sort='title'):
        title = _('Search for: %s') % name
        ids = self.search_for_books(name)
        books = self.db.get_data_as_dict(ids=ids)
        return self.render_book_list(books, start, sort, vars());

    def html_index(self):
        import random
        logging.error(_)
        title = _('All books')
        ids = self.search_for_books('')
        if not ids:
            raise cherrypy.HTTPError(404, 'This library has no books')

        books = self.db.get_data_as_dict(ids=ids)
        self.sort_books(books, 'datetime')
        books.reverse()
        new_books = random.sample(books[:40], 8)
        try:
            random_books = random.sample(books, 4)
        except:
            pass
        return self.html_page('content_server/v2/index.html', vars())

    @cherrypy.expose
    def book_list(self, start=0, sort='title'):
        title = _('All books')
        category_name = 'books'
        ids = self.search_cache('')
        books = self.db.get_data_as_dict(ids=ids)
        return self.render_book_list(books, start, sort, vars());

    def render_book_list(self, all_books, start, sort, vars_):
        try: start = int(start)
        except: start = 0
        self.sort_books(all_books, sort)
        delta = 20
        page_max = len(all_books) / delta
        page_now = start / delta
        pages = []
        for p in range(page_now-4, page_now+4):
            if 0 <= p and p <= page_max:
                pages.append(p)
        books = all_books[start:start+delta]
        vars_.update(vars())
        return self.html_page('content_server/v2/book/list.html', vars_)

    def book_detail(self, id):
        book_id = int(id)
        books = self.db.get_data_as_dict(ids=[book_id])
        if not books:
            raise cherrypy.HTTPError(404, 'book not found')
        book = books[0]
        try: sizes = [ (f, self.db.sizeof_format(book['id'], f, index_is_id=True)) for f in book['available_formats'] ]
        except: sizes = []
        title = book['title']
        return self.html_page('content_server/v2/book/detail.html', vars())

    def do_book_update(self, id):
        book_id = int(id)
        mi = self.db.get_metadata(book_id, index_is_id=True)
        douban_mi = douban.get_douban_metadata(mi.title)
        if mi.cover_data[0]:
            douban_mi.cover_data = None
        mi.smart_update(douban_mi, replace_metadata=True)
        self.db.set_metadata(book_id, mi)
        return book_id

    def book_update(self, id):
        book_id = self.do_book_update(id)
        raise cherrypy.HTTPRedirect('/book/%d'%book_id, 302)

    @cherrypy.expose
    def book_edit(self, id, field, content):
        book_id = int(id)
        mi = self.db.get_metadata(book_id, index_is_id=True)
        if not mi.has_key(field):
            return json.dumps({'ecode': 1, 'msg': _("field not support")})
        if field == 'pubdate':
            try:
                content = datetime.datetime.strptime(content, "%Y-%m-%d")
            except:
                return json.dumps({'ecode': 2, 'msg': _("date format error!")})
        mi.set(field, content)
        self.db.set_metadata(book_id, mi)
        return json.dumps({'ecode': 0, 'msg': _("edit OK")})

    def book_delete(self, id):
        self.db.delete_book(int(id))
        raise cherrypy.HTTPRedirect("/book", 302)

    def book_download(self, id, fmt):
        fmt = fmt.lower()
        book_id = int(id)
        books = self.db.get_data_as_dict(ids=[book_id])
        book = books[0]
        if 'fmt_%s'%fmt not in book:
            raise cherrypy.HTTPError(404, '%s not found'%(fmt))
        path = book['fmt_%s'%fmt]
        att = u'attachment; filename="%d-%s.%s"' % (book['id'], book['title'], fmt)
        cherrypy.response.headers['Content-Disposition'] = att.encode('UTF-8')
        cherrypy.response.headers['Content-Type'] = 'application/octet-stream'
        with open(path, 'rb') as f:
            ans = f.read()
        return ans;

    def book_add(self, file_input_name="ebook_file"):
        title = _('Upload Book')
        return self.html_page('content_server/v2/book/add.html', vars())

    @cherrypy.expose
    def book_upload(self, ebook_file=None):
        from calibre.ebooks.metadata import MetaInformation
        cherrypy.response.timeout = 3600

        name = ebook_file.filename
        fmt = os.path.splitext(name)[1]
        fmt = fmt[1:] if fmt else None
        if not fmt:
            return "bad file name: %s" % name
        fmt = fmt.lower()

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
        mi = get_metadata(stream, stream_type=fmt, use_libprs_metadata=True)
        books = self.db.books_with_same_title(mi)
        if books:
            book_id = books.pop()
            raise cherrypy.HTTPRedirect('/book/%d'%book_id)

        # convert another format
        new_fmt = {'epub': 'mobi', 'mobi': 'epub'}.get(fmt)
        new_path = '/tmp/calibre-tmp.'+new_fmt
        log = Log()
        plumber = Plumber(fpath, new_path, log)
        plumber.run()

        book_id = self.db.import_book(mi, [fpath, new_path] )
        raise cherrypy.HTTPRedirect('/book/%d'%book_id)

    def tag_list(self):
        title = _('All tags')
        category = "tags"
        tags = self.db.all_tags2()
        return self.html_page('content_server/v2/tag/list.html', vars())

    @cherrypy.expose
    def tag_detail(self, name, start=0, sort="title"):
        title = _('Books of tag: %') % name
        category = "tags"
        tag_id = self.db.get_tag_id(name)
        ids = self.db.get_books_for_category(category, tag_id)
        books = self.db.get_data_as_dict(ids=ids)
        return self.render_book_list(books, start, sort, vars());

    def author_list(self):
        title = _('All authors')
        category = "authors"
        authors = self.db.all_authors()
        authors.sort(cmp=lambda x,y: cmp(ascii_filename(x[1]).lower(), ascii_filename(y[1]).lower()))
        authors.sort(cmp=lambda x,y: cmp(x[1], y[1]))
        logging.error(authors)
        return self.html_page('content_server/v2/author/list.html', vars())

    @cherrypy.expose
    def author_detail(self, name, start=0, sort="title"):
        title = _('Books of author: %s') % name
        category = "authors"
        author_id = self.db.get_author_id(name)
        ids = self.db.get_books_for_category(category, author_id)
        books = self.db.get_data_as_dict(ids=ids)
        return self.render_book_list(books, start, sort, vars());

    @cherrypy.expose
    def author_books_update(self, name):
        cherrypy.response.timeout = 3600
        category = "authors"
        author_id = self.db.get_author_id(name)
        ids = self.db.get_books_for_category(category, author_id)
        for book_id in list(ids)[:40]:
            self.do_book_update(book_id)
        raise cherrypy.HTTPRedirect('/author/%s'%name, 302)

    def pub_list(self):
        title = _('All publishers')
        category = "publisher"
        publishers = self.db.all_publishers()
        return self.html_page('content_server/v2/publisher/list.html', vars())

    @cherrypy.expose
    def pub_detail(self, name, start=0, sort="title"):
        title = _('Books of publisher: %s ') % name
        category = "publisher"
        publisher_id = self.db.get_publisher_id(name)
        logging.error(publisher_id)
        if publisher_id:
            ids = self.db.get_books_for_category(category, publisher_id)
            books = self.db.get_data_as_dict(ids=ids)
        else:
            ids = self.search_for_books('')
            books = self.db.get_data_as_dict(ids=ids)
            books = [ b for b in books if not b['publisher'] ]
        return self.render_book_list(books, start, sort, vars());

    def rating_list(self):
        title = _('All ratings')
        category = "rating"
        ratings = self.db.all_ratings()
        return self.html_page('content_server/v2/rating/list.html', vars())

    @cherrypy.expose
    def rating_detail(self, name, start=0, sort="title"):
        title = _('Books of rating: %s ') % name
        category = "rating"
        rating_id = self.db.get_rating_id(name)
        ids = self.db.get_books_for_category(category, rating_id)
        books = self.db.get_data_as_dict(ids=ids)
        return self.render_book_list(books, start, sort, vars());

    def setting_view(self):
        nav = "setting"
        title = _('Setting')
        msg = None
        prefs = self.db.prefs
        return self.html_page('content_server/v2/setting/view.html', vars())

    @cherrypy.expose
    def setting_save(self, share_kindle="", allow_admin=False, allow_delete=False):
        nav = "setting"
        title = _('Setting')
        self.db.prefs.set('share_kindle', share_kindle)
        self.db.prefs.set('allow_admin', allow_admin)
        self.db.prefs.set('allow_delete', allow_delete)
        msg = _('Saved success!')
        return self.html_page('content_server/v2/setting/view.html', vars())

    def share_kindle(self, id, fmt="mobi"):
        mail_to = self.db.prefs.get('share_kindle', None)
        if not mail_to:
            raise cherrypy.HTTPRedirect("/setting", 302)

        book_id = int(id)
        books = self.db.get_data_as_dict(ids=[book_id])
        if not books:
            raise cherrypy.HTTPError(404, _("Sorry, book not found") )
        book = books[0]

        # check format
        for fmt in ['mobi', 'azw']:
            fpath = book.get("fmt_%s" % fmt, None)
            if fpath:
                return self.do_send_mail(book, mail_to, fmt, fpath)

        # we do no have formats for kindle
        if 'fmt_epub' not in book:
            raise cherrypy.HTTPError(404, _("Sorry, there's no available format for kindle"))
        fmt = 'mobi'
        fpath = '/tmp/%s.%s' % (ascii_filename(book['title']), fmt)
        log = Log()
        plumber = Plumber(book['fmp_epub'], fpath, log)
        plumber.run()
        return self.do_send_mail(book, mail_to, fmt, fpath)

    def do_send_mail(self, book, mail_to, fmt, fpath):
        body = open(fpath).read()

        # read meta info
        author = authors_to_string(book['authors'] if book['authors'] else [_('Unknown')])
        title = book['title'] if book['title'] else _("No Title")
        fname = u'%s - %s.%s'%(title, author, fmt)
        fname = ascii_filename(fname).replace('"', '_')

        # content type
        mt = guess_type('dummy.'+fmt)[0]
        if mt is None:
            mt = 'application/octet-stream'

        # send mail
        mail_from = 'mailer@calibre-ebook.com'
        mail_subject = _('Book of Calibre: ') + title
        mail_body = _('We Send this book to your kindle.')
        success_msg = error_msg = None
        try:
            msg = create_mail(mail_from, mail_to, mail_subject,
                    text = mail_body, attachment_data = body,
                    attachment_type = mt, attachment_name = fname
                    )
            sendmail(msg, from_=mail_from, to=[mail_to], timeout=30)
            success_msg = _('Send to kindle success!! email: %s') % mail_to
        except:
            import traceback
            cherrypy.log.error('Failed to generate cover:')
            cherrypy.log.error(traceback.format_exc())
            error_msg = traceback.format_exc()

        title = _('Send to kindle')
        return self.html_page('content_server/v2/share/email.html', vars())


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

    def get(self, fmt, id):
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
        if fmt == 'thumb' or fmt.startswith('thumb_'):
            try:
                width, height = map(int, fmt.split('_')[1:])
            except:
                width, height = 60, 80
            return self.get_cover(id, thumbnail=True, thumb_width=width,
                    thumb_height=height)
        if fmt == 'cover':
            return self.get_cover(id)
        if fmt == 'opf':
            return self.get_metadata_as_opf(id)
        if fmt == 'json':
            raise cherrypy.InternalRedirect('/ajax/book/%d'%id)
        return self.get_format(id, fmt)

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


