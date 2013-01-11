#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, os, posixpath

import cherrypy

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

class ContentServer(object):

    '''
    Handles actually serving content files/covers/metadata. Also has
    a few utility methods.
    '''

    def add_routes(self, connect):
        connect('root', '/', self.index)
        connect('old', '/old', self.old)
        connect('get', '/get/{what}/{id}', self.get,
                conditions=dict(method=["GET", "HEAD"]),
                android_workaround=True)
        connect('static', '/static/{name:.*?}', self.static,
                conditions=dict(method=["GET", "HEAD"]))
        connect('favicon', '/favicon.png', self.favicon,
                conditions=dict(method=["GET", "HEAD"]))

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
            raise cherrypy.HTTPError(404, '%s not found'%name)
        if self.opts.develop:
            lm = fromtimestamp(os.stat(path).st_mtime)
            cherrypy.response.headers['Last-Modified'] = self.last_modified(lm)
        with open(path, 'rb') as f:
            ans = f.read()
        if path.endswith('.css'):
            ans = ans.replace('/static/', self.opts.url_prefix + '/static/')
        return ans

    def favicon(self):
        data = I('lt.png', data=True)
        cherrypy.response.headers['Content-Type'] = 'image/png'
        cherrypy.response.headers['Last-Modified'] = self.last_modified(
                self.build_time)
        return data

    def index(self, **kwargs):
        'The / URL'
        ua = cherrypy.request.headers.get('User-Agent', '').strip()
        want_opds = \
            cherrypy.request.headers.get('Stanza-Device-Name', 919) != 919 or \
            cherrypy.request.headers.get('Want-OPDS-Catalog', 919) != 919 or \
            ua.startswith('Stanza')

        want_mobile = self.is_mobile_browser(ua)
        if self.opts.develop and not want_mobile:
            cherrypy.log('User agent: '+ua)

        if want_opds:
            return self.opds(version=0)

        if want_mobile:
            return self.mobile()

        return self.browse_catalog()

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

        if format in {'MOBI', 'EPUB', 'AZW3'}:
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


