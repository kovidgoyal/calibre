#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import operator, os

import cherrypy

from calibre.constants import filesystem_encoding
from calibre import isbytestring, force_unicode, prepare_string_for_xml as xml

class BrowseServer(object):

    def add_routes(self, connect):
        base_href = '/browse'
        connect('browse', base_href, self.browse_catalog)
        connect('browse_catalog', base_href+'/category/{category}',
                self.browse_catalog)
        connect('browse_list', base_href+'/list/{query}', self.browse_list)
        connect('browse_search', base_href+'/search/{query}',
                self.browse_search)
        connect('browse_book', base_href+'/book/{uuid}', self.browse_book)
        connect('browse_json', base_href+'/json/{query}', self.browse_json)

    def browse_template(self, category=True):

        def generate():
            if category:
                sort_opts = [('rating', _('Average rating')), ('name',
                    _('Name')), ('popularity', _('Popularity'))]
            else:
                fm = self.db.field_metadata
                sort_opts = [(x, fm[x]['name']) for x in fm.sortable_field_keys()
                        if fm[x]['name']]
            prefix = 'category' if category else 'book'
            ans = P('content_server/browse/browse.html', data=True)
            ans = ans.replace('{sort_select_label}', xml(_('Sort by')+':'))
            opts = ['<option value="%s_%s">%s</option>' % (prefix, xml(k),
                xml(n)) for k, n in
                    sorted(sort_opts, key=operator.itemgetter(1))]
            opts = ['<option value="_default">'+xml(_('Select one')) +
                    '&hellip;</option>'] + opts
            ans = ans.replace('{sort_select_options}', '\n\t\t\t'.join(opts))
            lp = self.db.library_path
            if isbytestring(lp):
                lp = force_unicode(lp, filesystem_encoding)
            if isinstance(ans, unicode):
                ans = ans.encode('utf-8')
            ans = ans.replace('{library_name}', xml(os.path.basename(lp)))
            ans = ans.replace('{library_path}', xml(lp, True))
            return ans

        if self.opts.develop:
            return generate()
        if not hasattr(self, '__browse_template__'):
            self.__browse_template__ = generate()
        return self.__browse_template__


    # Catalogs {{{
    def browse_catalog(self, category=None):
        if category == None:
            #categories = self.categories_cache()
            ans = self.browse_template().format(title='',
                    script='toplevel();')
        else:
            raise cherrypy.HTTPError(404, 'Not found')
        cherrypy.response.headers['Content-Type'] = 'text/html'
        cherrypy.response.headers['Last-Modified'] = self.last_modified(self.build_time)
        return ans

    # }}}

    # Book Lists {{{
    def browse_list(self, query=None):
        raise NotImplementedError()
    # }}}

    # Search {{{
    def browse_search(self, query=None):
        raise NotImplementedError()
    # }}}

    # Book {{{
    def browse_book(self, uuid=None):
        raise NotImplementedError()
    # }}}

    # JSON {{{
    def browse_json(self, query=None):
        raise NotImplementedError()
    # }}}

