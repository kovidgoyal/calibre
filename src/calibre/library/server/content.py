#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, os, cStringIO, operator

import cherrypy
try:
    from PIL import Image as PILImage
    PILImage
except ImportError:
    import Image as PILImage

from calibre import fit_image, guess_type
from calibre.utils.date import fromtimestamp
from calibre.ebooks.metadata import title_sort

class ContentServer(object):

    '''
    Handles actually serving content files/covers. Also has
    a few utility methods.
    '''

    def add_routes(self, connect):
        connect('root', '/', self.index)
        connect('get', '/get/{what}/{id}', self.get,
                conditions=dict(method=["GET", "HEAD"]))
        connect('static', '/static/{name}', self.static,
                conditions=dict(method=["GET", "HEAD"]))

    # Utility methods {{{
    def last_modified(self, updated):
        '''
        Generates a local independent, english timestamp from a datetime
        object
        '''
        lm = updated.strftime('day, %d month %Y %H:%M:%S GMT')
        day ={0:'Sun', 1:'Mon', 2:'Tue', 3:'Wed', 4:'Thu', 5:'Fri', 6:'Sat'}
        lm = lm.replace('day', day[int(updated.strftime('%w'))])
        month = {1:'Jan', 2:'Feb', 3:'Mar', 4:'Apr', 5:'May', 6:'Jun', 7:'Jul',
                 8:'Aug', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dec'}
        return lm.replace('month', month[updated.month])


    def sort(self, items, field, order):
        field = field.lower().strip()
        if field == 'author':
            field = 'authors'
        if field == 'date':
            field = 'timestamp'
        if field not in ('title', 'authors', 'rating', 'timestamp', 'tags', 'size', 'series'):
            raise cherrypy.HTTPError(400, '%s is not a valid sort field'%field)
        cmpf = cmp if field in ('rating', 'size', 'timestamp') else \
                lambda x, y: cmp(x.lower() if x else '', y.lower() if y else '')
        if field == 'series':
            items.sort(cmp=self.seriescmp, reverse=not order)
        else:
            lookup = 'sort' if field == 'title' else field
            lookup = 'author_sort' if field == 'authors' else field
            field = self.db.FIELD_MAP[lookup]
            getter = operator.itemgetter(field)
            items.sort(cmp=lambda x, y: cmpf(getter(x), getter(y)), reverse=not order)

    def seriescmp(self, x, y):
        si = self.db.FIELD_MAP['series']
        try:
            ans = cmp(title_sort(x[si].lower()), title_sort(y[si].lower()))
        except AttributeError: # Some entries may be None
            ans = cmp(x[si], y[si])
        if ans != 0: return ans
        return cmp(x[self.db.FIELD_MAP['series_index']], y[self.db.FIELD_MAP['series_index']])
    # }}}


    def get(self, what, id):
        'Serves files, covers, thumbnails from the calibre database'
        try:
            id = int(id)
        except ValueError:
            id = id.rpartition('_')[-1].partition('.')[0]
            match = re.search(r'\d+', id)
            if not match:
                raise cherrypy.HTTPError(400, 'id:%s not an integer'%id)
            id = int(match.group())
        if not self.db.has_id(id):
            raise cherrypy.HTTPError(400, 'id:%d does not exist in database'%id)
        if what == 'thumb':
            return self.get_cover(id, thumbnail=True)
        if what == 'cover':
            return self.get_cover(id)
        return self.get_format(id, what)

    def static(self, name):
        'Serves static content'
        name = name.lower()
        cherrypy.response.headers['Content-Type'] = {
                     'js'   : 'text/javascript',
                     'css'  : 'text/css',
                     'png'  : 'image/png',
                     'gif'  : 'image/gif',
                     'html' : 'text/html',
                     ''      : 'application/octet-stream',
                     }[name.rpartition('.')[-1].lower()]
        cherrypy.response.headers['Last-Modified'] = self.last_modified(self.build_time)
        path = P('content_server/'+name)
        if not os.path.exists(path):
            raise cherrypy.HTTPError(404, '%s not found'%name)
        if self.opts.develop:
            lm = fromtimestamp(os.stat(path).st_mtime)
            cherrypy.response.headers['Last-Modified'] = self.last_modified(lm)
        return open(path, 'rb').read()

    def index(self, **kwargs):
        'The / URL'
        ua = cherrypy.request.headers.get('User-Agent', '').strip()
        want_opds = \
            cherrypy.request.headers.get('Stanza-Device-Name', 919) != 919 or \
            cherrypy.request.headers.get('Want-OPDS-Catalog', 919) != 919 or \
            ua.startswith('Stanza')

        # A better search would be great
        want_mobile = self.MOBILE_UA.search(ua) is not None
        if self.opts.develop and not want_mobile:
            cherrypy.log('User agent: '+ua)

        if want_opds:
            return self.opds(version=0)

        if want_mobile:
            return self.mobile()

        return self.static('index.html')



    # Actually get content from the database {{{
    def get_cover(self, id, thumbnail=False):
        cover = self.db.cover(id, index_is_id=True, as_file=False)
        if cover is None:
            cover = self.default_cover
        cherrypy.response.headers['Content-Type'] = 'image/jpeg'
        cherrypy.response.timeout = 3600
        path = getattr(cover, 'name', False)
        updated = fromtimestamp(os.stat(path).st_mtime) if path and \
            os.access(path, os.R_OK) else self.build_time
        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        try:
            f = cStringIO.StringIO(cover)
            try:
                im = PILImage.open(f)
            except IOError:
                raise cherrypy.HTTPError(404, 'No valid cover found')
            width, height = im.size
            scaled, width, height = fit_image(width, height,
                60 if thumbnail else self.max_cover_width,
                80 if thumbnail else self.max_cover_height)
            if not scaled:
                return cover
            im = im.resize((int(width), int(height)), PILImage.ANTIALIAS)
            of = cStringIO.StringIO()
            im.convert('RGB').save(of, 'JPEG')
            return of.getvalue()
        except Exception, err:
            import traceback
            cherrypy.log.error('Failed to generate cover:')
            cherrypy.log.error(traceback.print_exc())
            raise cherrypy.HTTPError(404, 'Failed to generate cover: %s'%err)

    def get_format(self, id, format):
        format = format.upper()
        fmt = self.db.format(id, format, index_is_id=True, as_file=True,
                mode='rb')
        if fmt is None:
            raise cherrypy.HTTPError(404, 'book: %d does not have format: %s'%(id, format))
        if format == 'EPUB':
            from tempfile import TemporaryFile
            from calibre.ebooks.metadata.meta import set_metadata
            raw = fmt.read()
            fmt = TemporaryFile()
            fmt.write(raw)
            fmt.seek(0)
            set_metadata(fmt, self.db.get_metadata(id, index_is_id=True,
                get_cover=True),
                    'epub')
            fmt.seek(0)
        mt = guess_type('dummy.'+format.lower())[0]
        if mt is None:
            mt = 'application/octet-stream'
        cherrypy.response.headers['Content-Type'] = mt
        cherrypy.response.timeout = 3600
        path = getattr(fmt, 'name', None)
        if path and os.path.exists(path):
            updated = fromtimestamp(os.stat(path).st_mtime)
            cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        return fmt.read()
    # }}}


