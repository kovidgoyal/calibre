#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import operator, os, json, re, time
from binascii import hexlify, unhexlify
from collections import OrderedDict

import cherrypy

from calibre.constants import filesystem_encoding, config_dir
from calibre import (isbytestring, force_unicode, fit_image,
        prepare_string_for_xml, sanitize_file_name2)
from calibre.utils.filenames import ascii_filename
from calibre.utils.config import prefs, JSONConfig
from calibre.utils.icu import sort_key
from calibre.utils.magick import Image
from calibre.library.comments import comments_to_html
from calibre.library.server import custom_fields_to_display
from calibre.library.field_metadata import category_icon_map
from calibre.library.server.utils import quote, unquote
from calibre.ebooks.metadata.sources.identify import urls_from_identifiers

def xml(*args, **kwargs):
    ans = prepare_string_for_xml(*args, **kwargs)
    return ans.replace('&apos;', '&#39;')

def render_book_list(ids, prefix, suffix=''): # {{{
    pages = []
    num = len(ids)
    pos = 0
    delta = 25
    while ids:
        page = list(ids[:delta])
        pages.append((page, pos))
        ids = ids[delta:]
        pos += len(page)
    page_template = u'''\
            <div class="page" id="page{0}">
                <div class="load_data" title="{1}">
                    <span class="url" title="{prefix}/browse/booklist_page"></span>
                    <span class="start" title="{start}"></span>
                    <span class="end" title="{end}"></span>
                </div>
                <div class="loading"><img src="{prefix}/static/loading.gif" /> {2}</div>
                <div class="loaded"></div>
            </div>
            '''
    pagelist_template = u'''\
        <div class="pagelist">
            <ul>
                {pages}
            </ul>
        </div>
    '''
    rpages, lpages = [], []
    for i, x in enumerate(pages):
        pg, pos = x
        ld = xml(json.dumps(pg), True)
        start, end = pos+1, pos+len(pg)
        rpages.append(page_template.format(i, ld,
            xml(_('Loading, please wait')) + '&hellip;',
            start=start, end=end, prefix=prefix))
        lpages.append(' '*20 + (u'<li><a href="#" title="Books {start} to {end}"'
            ' onclick="gp_internal(\'{id}\'); return false;"> '
            '{start}&nbsp;to&nbsp;{end}</a></li>').format(start=start, end=end,
                id='page%d'%i))
    rpages = u'\n\n'.join(rpages)
    lpages = u'\n'.join(lpages)
    pagelist = pagelist_template.format(pages=lpages)

    templ = u'''\
            <h3>{0} {suffix}</h3>
            <div id="booklist">
                <div id="pagelist" title="{goto}">{pagelist}</div>
                <div class="listnav topnav">
                {navbar}
                </div>
                {pages}
                <div class="listnav bottomnav">
                {navbar}
                </div>
            </div>
            '''
    gp_start = gp_end = ''
    if len(pages) > 1:
        gp_start = '<a href="#" onclick="goto_page(); return false;" title="%s">' % \
                (_('Go to') + '&hellip;')
        gp_end = '</a>'
    navbar = u'''\
        <div class="navleft">
            <a href="#" onclick="first_page(); return false;">{first}</a>
            <a href="#" onclick="previous_page(); return false;">{previous}</a>
        </div>
        <div class="navmiddle">
            {gp_start}
                <span class="start">0</span> to <span class="end">0</span>
            {gp_end}of {num}
        </div>
        <div class="navright">
            <a href="#" onclick="next_page(); return false;">{next}</a>
            <a href="#" onclick="last_page(); return false;">{last}</a>
        </div>
    '''.format(first=_('First'), last=_('Last'), previous=_('Previous'),
            next=_('Next'), num=num, gp_start=gp_start, gp_end=gp_end)

    return templ.format(_('Browsing %d books')%num, suffix=suffix,
            pages=rpages, navbar=navbar, pagelist=pagelist,
            goto=xml(_('Go to'), True) + '&hellip;')

# }}}

def utf8(x): # {{{
    if isinstance(x, unicode):
        x = x.encode('utf-8')
    return x
# }}}

def render_rating(rating, url_prefix, container='span', prefix=None): # {{{
    if rating < 0.1:
        return '', ''
    added = 0
    if prefix is None:
        prefix = _('Average rating')
    rstring = xml(_('%(prefix)s: %(rating).1f stars')%dict(
        prefix=prefix, rating=rating if rating else 0.0),
            True)
    ans = ['<%s class="rating">' % (container)]
    for i in range(5):
        n = rating - added
        x = 'half'
        if n <= 0.1:
            x = 'off'
        elif n >= 0.9:
            x = 'on'
        ans.append(
            u'<img alt="{0}" title="{0}" src="{2}/static/star-{1}.png" />'.format(
                rstring, x, url_prefix))
        added += 1
    ans.append('</%s>'%container)
    return u''.join(ans), rstring

# }}}

def get_category_items(category, items, datatype, prefix): # {{{

    def item(i):
        templ = (u'<div title="{4}" class="category-item">'
                '<div class="category-name">'
                '<a href="{5}{3}" title="{4}">{0}</a></div>'
                '<div>{1}</div>'
                '<div>{2}</div></div>')
        rating, rstring = render_rating(i.avg_rating, prefix)
        if i.use_sort_as_name:
            name = xml(i.sort)
        else:
            name = xml(i.name)
        if datatype == 'rating':
            name = xml(_('%d stars')%int(i.avg_rating))
        id_ = i.id
        if id_ is None:
            id_ = hexlify(force_unicode(name).encode('utf-8'))
        id_ = xml(str(id_))
        desc = ''
        if i.count > 0:
            desc += '[' + _('%d books')%i.count + ']'
        q = i.category
        if not q:
            q = category
        href = '/browse/matches/%s/%s'%(quote(q), quote(id_))
        return templ.format(xml(name), rating,
                xml(desc), xml(href, True), rstring, prefix)

    items = list(map(item, items))
    return '\n'.join(['<div class="category-container">'] + items + ['</div>'])

# }}}

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

class BrowseServer(object):

    def add_routes(self, connect):
        base_href = '/browse'
        connect('browse', base_href, self.browse_catalog)
        connect('browse_catalog', base_href+'/category/{category}',
                self.browse_catalog)
        connect('browse_category_group',
                base_href+'/category_group/{category}/{group}',
                self.browse_category_group)
        connect('browse_matches',
                base_href+'/matches/{category}/{cid}',
                self.browse_matches)
        connect('browse_booklist_page',
                base_href+'/booklist_page',
                self.browse_booklist_page)
        connect('browse_search', base_href+'/search',
                self.browse_search)
        connect('browse_details', base_href+'/details/{id}',
                self.browse_details)
        connect('browse_book', base_href+'/book/{id}',
                self.browse_book)
        connect('browse_random', base_href+'/random',
                self.browse_random)
        connect('browse_category_icon', base_href+'/icon/{name}',
                self.browse_icon)

        self.icon_map = JSONConfig('gui').get('tags_browser_category_icons', {})

    # Templates {{{
    def browse_template(self, sort, category=True, initial_search=''):

        if not hasattr(self, '__browse_template__') or \
                self.opts.develop:
            self.__browse_template__ = \
                P('content_server/browse/browse.html', data=True).decode('utf-8')

        ans = self.__browse_template__
        scn = 'calibre_browse_server_sort_'

        if category:
            sort_opts = [('rating', _('Average rating')), ('name',
                _('Name')), ('popularity', _('Popularity'))]
            scn += 'category'
        else:
            scn += 'list'
            fm = self.db.field_metadata
            sort_opts, added = [], set([])
            displayed_custom_fields = custom_fields_to_display(self.db)
            for x in fm.sortable_field_keys():
                if x in ('ondevice', 'formats', 'sort'):
                    continue
                if fm.is_ignorable_field(x) and x not in displayed_custom_fields:
                    continue
                if x == 'comments' or fm[x]['datatype'] == 'comments':
                    continue
                n = fm[x]['name']
                if n not in added:
                    added.add(n)
                    sort_opts.append((x, n))

        ans = ans.replace('{sort_select_label}', xml(_('Sort by')+':'))
        ans = ans.replace('{sort_cookie_name}', scn)
        ans = ans.replace('{prefix}', self.opts.url_prefix)
        ans = ans.replace('{library}', _('library'))
        ans = ans.replace('{home}', _('home'))
        ans = ans.replace('{Search}', _('Search'))
        opts = ['<option %svalue="%s">%s</option>' % (
            'selected="selected" ' if k==sort else '',
            xml(k), xml(n), ) for k, n in
                sorted(sort_opts, key=lambda x: sort_key(operator.itemgetter(1)(x))) if k and n]
        ans = ans.replace('{sort_select_options}', ('\n'+' '*20).join(opts))
        lp = self.db.library_path
        if isbytestring(lp):
            lp = force_unicode(lp, filesystem_encoding)
        ans = ans.replace('{library_name}', xml(os.path.basename(lp)))
        ans = ans.replace('{library_path}', xml(lp, True))
        ans = ans.replace('{initial_search}', initial_search)
        return ans

    @property
    def browse_summary_template(self):
        if not hasattr(self, '__browse_summary_template__') or \
                self.opts.develop:
            self.__browse_summary_template__ = \
                P('content_server/browse/summary.html', data=True).decode('utf-8')
        return self.__browse_summary_template__.replace('{prefix}',
                self.opts.url_prefix)

    @property
    def browse_details_template(self):
        if not hasattr(self, '__browse_details_template__') or \
                self.opts.develop:
            self.__browse_details_template__ = \
                P('content_server/browse/details.html', data=True).decode('utf-8')
        return self.__browse_details_template__.replace('{prefix}',
                self.opts.url_prefix)

    # }}}

    # Catalogs {{{
    def browse_icon(self, name='blank.png'):
        cherrypy.response.headers['Content-Type'] = 'image/png'
        cherrypy.response.headers['Last-Modified'] = self.last_modified(self.build_time)

        if not hasattr(self, '__browse_icon_cache__'):
            self.__browse_icon_cache__ = {}
        if name not in self.__browse_icon_cache__:
            if name.startswith('_'):
                name = sanitize_file_name2(name[1:])
                try:
                    with open(os.path.join(config_dir, 'tb_icons', name), 'rb') as f:
                        data = f.read()
                except:
                    raise cherrypy.HTTPError(404, 'no icon named: %r'%name)
            else:
                try:
                    data = I(name, data=True)
                except:
                    raise cherrypy.HTTPError(404, 'no icon named: %r'%name)
            img = Image()
            img.load(data)
            width, height = img.size
            scaled, width, height = fit_image(width, height, 48, 48)
            if scaled:
                img.size = (width, height)

            self.__browse_icon_cache__[name] = img.export('png')
        return self.__browse_icon_cache__[name]

    def browse_toplevel(self):
        categories = self.categories_cache()
        category_meta = self.db.field_metadata
        cats = [
                (_('Newest'), 'newest', 'forward.png'),
                (_('All books'), 'allbooks', 'book.png'),
                (_('Random book'), 'randombook', 'random.png'),
                ]

        def getter(x):
            return category_meta[x]['name'].lower()

        displayed_custom_fields = custom_fields_to_display(self.db)
        uc_displayed = set()
        for category in sorted(categories, key=lambda x: sort_key(getter(x))):
            if len(categories[category]) == 0:
                continue
            if category in ('formats', 'identifiers'):
                continue
            meta = category_meta.get(category, None)
            if meta is None:
                continue
            if self.db.field_metadata.is_ignorable_field(category) and \
                        category not in displayed_custom_fields:
                continue
            # get the icon files
            main_cat = (category.partition('.')[0]) if hasattr(category,
                                                    'partition') else category
            if main_cat in self.icon_map:
                icon = '_'+quote(self.icon_map[main_cat])
            elif category in category_icon_map:
                icon = category_icon_map[category]
            elif meta['is_custom']:
                icon = category_icon_map['custom:']
            elif meta['kind'] == 'user':
                icon = category_icon_map['user:']
            else:
                icon = 'blank.png'

            if meta['kind'] == 'user':
                dot = category.find('.')
                if dot > 0:
                    cat = category[:dot]
                    if cat not in uc_displayed:
                        cats.append((meta['name'][:dot-1], cat, icon))
                        uc_displayed.add(cat)
                else:
                    cats.append((meta['name'], category, icon))
                    uc_displayed.add(category)
            else:
                cats.append((meta['name'], category, icon))

        cats = [(u'<li><a title="{2} {0}" href="{3}/browse/category/{1}">&nbsp;</a>'
                 u'<img src="{3}{src}" alt="{0}" />'
                 u'<span class="label">{0}</span>'
                 u'</li>')
                .format(xml(x, True), xml(quote(y)), xml(_('Browse books by')),
                    self.opts.url_prefix, src='/browse/icon/'+z)
                for x, y, z in cats]

        main = u'<div class="toplevel"><h3>{0}</h3><ul>{1}</ul></div>'\
                .format(_('Choose a category to browse by:'), u'\n\n'.join(cats))
        return self.browse_template('name').format(title='',
                    script='toplevel();', main=main)

    def browse_sort_categories(self, items, sort):
        if sort not in ('rating', 'name', 'popularity'):
            sort = 'name'
        items.sort(key=lambda x: sort_key(getattr(x, 'sort', x.name)))
        if sort == 'popularity':
            items.sort(key=operator.attrgetter('count'), reverse=True)
        elif sort == 'rating':
            items.sort(key=operator.attrgetter('avg_rating'), reverse=True)
        return sort

    def browse_category(self, category, sort):
        categories = self.categories_cache()
        if category not in categories:
            raise cherrypy.HTTPError(404, 'category not found')
        category_meta = self.db.field_metadata
        category_name = category_meta[category]['name']
        datatype = category_meta[category]['datatype']

        # See if we have any sub-categories to display. As we find them, add
        # them to the displayed set to avoid showing the same item twice
        uc_displayed = set()
        cats = []
        for ucat in sorted(categories.keys(), key=sort_key):
            if len(categories[ucat]) == 0:
                continue
            if category == 'formats':
                continue
            meta = category_meta.get(ucat, None)
            if meta is None:
                continue
            if meta['kind'] != 'user':
                continue
            cat_len = len(category)
            if not (len(ucat) > cat_len and ucat.startswith(category+'.')):
                continue

            if ucat in self.icon_map:
                icon = '_'+quote(self.icon_map[ucat])
            else:
                icon = category_icon_map['user:']
            # we have a subcategory. Find any further dots (further subcats)
            cat_len += 1
            cat = ucat[cat_len:]
            dot = cat.find('.')
            if dot > 0:
                # More subcats
                cat = cat[:dot]
                if cat not in uc_displayed:
                    cats.append((cat, ucat[:cat_len+dot], icon))
                    uc_displayed.add(cat)
            else:
                # This is the end of the chain
                cats.append((cat, ucat, icon))
                uc_displayed.add(cat)

        cats = u'\n\n'.join(
                [(u'<li><a title="{2} {0}" href="{3}/browse/category/{1}">&nbsp;</a>'
                 u'<img src="{3}{src}" alt="{0}" />'
                 u'<span class="label">{0}</span>'
                 u'</li>')
                .format(xml(x, True), xml(quote(y)), xml(_('Browse books by')),
                    self.opts.url_prefix, src='/browse/icon/'+z)
                for x, y, z in cats])
        if cats:
            cats = (u'\n<div class="toplevel">\n'
                     '{0}</div>').format(cats)
            script = 'toplevel();'
        else:
            script = 'true'

        # Now do the category items
        items = categories[category]
        sort = self.browse_sort_categories(items, sort)

        if not cats and len(items) == 1:
            # Only one item in category, go directly to book list
            html = get_category_items(category, items,
                    datatype, self.opts.url_prefix)
            href = re.search(r'<a href="([^"]+)"', html)
            if href is not None:
                raise cherrypy.HTTPRedirect(href.group(1))

        if len(items) <= self.opts.max_opds_ungrouped_items:
            script = 'false'
            items = get_category_items(category, items,
                    datatype, self.opts.url_prefix)
        else:
            getter = lambda x: unicode(getattr(x, 'sort', x.name))
            starts = set([])
            for x in items:
                val = getter(x)
                if not val:
                    val = u'A'
                starts.add(val[0].upper())
            category_groups = OrderedDict()
            for x in sorted(starts):
                category_groups[x] = len([y for y in items if
                    getter(y).upper().startswith(x)])
            items = [(u'<h3 title="{0}"><a class="load_href" title="{0}"'
                      u' href="{4}{3}"><strong>{0}</strong> [{2}]</a></h3><div>'
                      u'<div class="loaded" style="display:none"></div>'
                      u'<div class="loading"><img alt="{1}" src="{4}/static/loading.gif" /><em>{1}</em></div>'
                      u'</div>').format(
                        xml(s, True),
                        xml(_('Loading, please wait'))+'&hellip;',
                        unicode(c),
                        xml(u'/browse/category_group/%s/%s'%(
                            hexlify(category.encode('utf-8')),
                            hexlify(s.encode('utf-8'))), True),
                        self.opts.url_prefix)
                    for s, c in category_groups.items()]
            items = '\n\n'.join(items)
            items = u'<div id="groups">\n{0}</div>'.format(items)



        if cats:
            script = 'toplevel();category(%s);'%script
        else:
            script = 'category(%s);'%script

        main = u'''
            <div class="category">
                <h3>{0}</h3>
                    <a class="navlink" href="{3}/browse"
                        title="{2}">{2}&nbsp;&uarr;</a>
                {1}
            </div>
        '''.format(
                xml(_('Browsing by')+': ' + category_name), cats + items,
                xml(_('Up'), True), self.opts.url_prefix)

        return self.browse_template(sort).format(title=category_name,
                script=script, main=main)

    @Endpoint(mimetype='application/json; charset=utf-8')
    def browse_category_group(self, category=None, group=None, sort=None):
        if sort == 'null':
            sort = None
        if sort not in ('rating', 'name', 'popularity'):
            sort = 'name'
        try:
            category = unhexlify(category)
            if isbytestring(category):
                category = category.decode('utf-8')
        except:
            raise cherrypy.HTTPError(404, 'invalid category')

        categories = self.categories_cache()
        if category not in categories:
            raise cherrypy.HTTPError(404, 'category not found')

        category_meta = self.db.field_metadata
        datatype = category_meta[category]['datatype']

        try:
            group = unhexlify(group)
            if isbytestring(group):
                group = group.decode('utf-8')
        except:
            raise cherrypy.HTTPError(404, 'invalid group')

        items = categories[category]
        entries = []
        getter = lambda x: unicode(getattr(x, 'sort', x.name))
        for x in items:
            val = getter(x)
            if not val:
                val = u'A'
            if val.upper().startswith(group):
                entries.append(x)

        sort = self.browse_sort_categories(entries, sort)
        entries = get_category_items(category, entries,
                datatype, self.opts.url_prefix)
        return json.dumps(entries, ensure_ascii=True)


    @Endpoint()
    def browse_catalog(self, category=None, category_sort=None):
        'Entry point for top-level, categories and sub-categories'
        prefix = '' if self.is_wsgi else self.opts.url_prefix
        if category == None:
            ans = self.browse_toplevel()
        elif category == 'newest':
            raise cherrypy.InternalRedirect(prefix +
                    '/browse/matches/newest/dummy')
        elif category == 'allbooks':
            raise cherrypy.InternalRedirect(prefix +
                    '/browse/matches/allbooks/dummy')
        elif category == 'randombook':
            raise cherrypy.InternalRedirect(prefix +
                    '/browse/random')
        else:
            ans = self.browse_category(category, category_sort)

        return ans

    # }}}

    # Book Lists {{{

    def browse_sort_book_list(self, items, sort):
        fm = self.db.field_metadata
        keys = frozenset(fm.sortable_field_keys())
        if sort not in keys:
            sort = 'title'
        self.sort(items, 'title', True)
        if sort != 'title':
            ascending = fm[sort]['datatype'] not in ('rating', 'datetime',
                    'series')
            self.sort(items, sort, ascending)
        return sort

    @Endpoint(sort_type='list')
    def browse_matches(self, category=None, cid=None, list_sort=None):
        if list_sort:
            list_sort = unquote(list_sort)
        if not cid:
            raise cherrypy.HTTPError(404, 'invalid category id: %r'%cid)
        categories = self.categories_cache()

        if category not in categories and \
                category not in ('newest', 'allbooks'):
            raise cherrypy.HTTPError(404, 'category not found')
        fm = self.db.field_metadata
        try:
            category_name = fm[category]['name']
            dt = fm[category]['datatype']
        except:
            if category not in ('newest', 'allbooks'):
                raise
            category_name = {
                    'newest' : _('Newest'),
                    'allbooks' : _('All books'),
            }[category]
            dt = None

        hide_sort = 'true' if dt == 'series' else 'false'
        if category == 'search':
            which = unhexlify(cid).decode('utf-8')
            try:
                ids = self.search_cache('search:"%s"'%which)
            except:
                raise cherrypy.HTTPError(404, 'Search: %r not understood'%which)
        else:
            all_ids = self.search_cache('')
            if category == 'newest':
                ids = all_ids
                hide_sort = 'true'
            elif category == 'allbooks':
                ids = all_ids
            else:
                if fm.get(category, {'datatype':None})['datatype'] == 'composite':
                    cid = cid.decode('utf-8')
                q = category
                if q == 'news':
                    q = 'tags'
                ids = self.db.get_books_for_category(q, cid)
                ids = [x for x in ids if x in all_ids]

        items = [self.db.data._data[x] for x in ids]
        if category == 'newest':
            list_sort = 'timestamp'
        if dt == 'series':
            list_sort = category
        sort = self.browse_sort_book_list(items, list_sort)
        ids = [x[0] for x in items]
        html = render_book_list(ids, self.opts.url_prefix,
                suffix=_('in') + ' ' + category_name)

        return self.browse_template(sort, category=False).format(
                title=_('Books in') + " " +category_name,
                script='booklist(%s);'%hide_sort, main=html)

    def browse_get_book_args(self, mi, id_, add_category_links=False):
        fmts = self.db.formats(id_, index_is_id=True)
        if not fmts:
            fmts = ''
        fmts = [x.lower() for x in fmts.split(',') if x]
        pf = prefs['output_format'].lower()
        try:
            fmt = pf if pf in fmts else fmts[0]
        except:
            fmt = None
        args = {'id':id_, 'mi':mi,
                }
        ccache = self.categories_cache() if add_category_links else {}
        ftitle = fauthors = ''
        for key in mi.all_field_keys():
            val = mi.format_field(key)[1]
            if not val:
                val = ''
            if key == 'title':
                ftitle = xml(val, True)
            elif key == 'authors':
                fauthors = xml(val, True)
            if add_category_links:
                added_key = False
                fm = mi.metadata_for_field(key)
                if val and fm and fm['is_category'] and not fm['is_csp'] and\
                        key != 'formats' and fm['datatype'] not in ['rating']:
                    categories = mi.get(key)
                    if isinstance(categories, basestring):
                        categories = [categories]
                    dbtags = []
                    for category in categories:
                        dbtag = None
                        for tag in ccache[key]:
                            if tag.name == category:
                                dbtag = tag
                                break
                        dbtags.append(dbtag)
                    if None not in dbtags:
                        vals = []
                        for tag in dbtags:
                            tval = ('<a title="Browse books by {3}: {0}"'
                            ' href="{1}" class="details_category_link">{2}</a>')
                            href='%s/browse/matches/%s/%s' % \
                            (self.opts.url_prefix, quote(tag.category), quote(str(tag.id)))
                            vals.append(tval.format(xml(tag.name, True),
                                xml(href, True),
                                xml(val if len(dbtags) == 1 else tag.name),
                                xml(key, True)))
                        join = ' &amp; ' if key == 'authors' or \
                                            (fm['is_custom'] and
                                             fm['display'].get('is_names', False)) \
                                         else ', '
                        args[key] = join.join(vals)
                        added_key = True
                if not added_key:
                    args[key] = xml(val, True)
            else:
                args[key] = xml(val, True)
        fname = quote(ascii_filename(ftitle) + ' - ' +
                ascii_filename(fauthors))
        return args, fmt, fmts, fname

    @Endpoint(mimetype='application/json; charset=utf-8')
    def browse_booklist_page(self, ids=None, sort=None):
        if sort == 'null':
            sort = None
        if ids is None:
            ids = json.dumps('[]')
        try:
            ids = json.loads(ids)
        except:
            raise cherrypy.HTTPError(404, 'invalid ids')
        summs = []
        for id_ in ids:
            try:
                id_ = int(id_)
                mi = self.db.get_metadata(id_, index_is_id=True)
            except:
                continue
            args, fmt, fmts, fname = self.browse_get_book_args(mi, id_)
            args['other_formats'] = ''
            args['fmt'] = fmt
            if fmts and fmt:
                other_fmts = [x for x in fmts if x.lower() != fmt.lower()]
                if other_fmts:
                    ofmts = [u'<a href="{4}/get/{0}/{1}_{2}.{0}" title="{3}">{3}</a>'\
                            .format(f, fname, id_, f.upper(),
                                self.opts.url_prefix) for f in
                            other_fmts]
                    ofmts = ', '.join(ofmts)
                    args['other_formats'] = u'<strong>%s: </strong>' % \
                            _('Other formats') + ofmts

            args['details_href'] = self.opts.url_prefix + '/browse/details/'+str(id_)

            if fmt:
                href = self.opts.url_prefix + '/get/%s/%s_%d.%s'%(
                        fmt, fname, id_, fmt)
                rt = xml(_('Read %(title)s in the %(fmt)s format')% \
                        {'title':args['title'], 'fmt':fmt.upper()}, True)

                args['get_button'] = \
                        '<a href="%s" class="read" title="%s">%s</a>' % \
                        (xml(href, True), rt, xml(_('Get')))
                args['get_url'] = xml(href, True)
            else:
                args['get_button'] = args['get_url'] = ''
            args['comments'] = comments_to_html(mi.comments)
            args['stars'] = ''
            if mi.rating:
                args['stars'] = render_rating(mi.rating/2.0,
                        self.opts.url_prefix, prefix=_('Rating'))[0]
            if args['tags']:
                args['tags'] = u'<strong>%s: </strong>'%xml(_('Tags')) + \
                    args['tags']
            if args['series']:
                args['series'] = args['series']
            args['details'] = xml(_('Details'), True)
            args['details_tt'] = xml(_('Show book details'), True)
            args['permalink'] = xml(_('Permalink'), True)
            args['permalink_tt'] = xml(_('A permanent link to this book'), True)

            summs.append(self.browse_summary_template.format(**args))


        raw = json.dumps('\n'.join(summs), ensure_ascii=True)
        return raw

    def browse_render_details(self, id_, add_random_button=False):
        try:
            mi = self.db.get_metadata(id_, index_is_id=True)
        except:
            return _('This book has been deleted')
        else:
            args, fmt, fmts, fname = self.browse_get_book_args(mi, id_,
                    add_category_links=True)
            args['fmt'] = fmt
            if fmt:
                args['get_url'] = xml(self.opts.url_prefix + '/get/%s/%s_%d.%s'%(
                    fmt, fname, id_, fmt), True)
            else:
                args['get_url'] = ''
            args['formats'] = ''
            if fmts:
                ofmts = [u'<a href="{4}/get/{0}/{1}_{2}.{0}" title="{3}">{3}</a>'\
                        .format(xfmt, fname, id_, xfmt.upper(),
                            self.opts.url_prefix) for xfmt in fmts]
                ofmts = ', '.join(ofmts)
                args['formats'] = ofmts
            fields, comments = [], []
            displayed_custom_fields = custom_fields_to_display(self.db)
            for field, m in list(mi.get_all_standard_metadata(False).items()) + \
                    list(mi.get_all_user_metadata(False).items()):
                if self.db.field_metadata.is_ignorable_field(field) and \
                                field not in displayed_custom_fields:
                    continue
                if m['datatype'] == 'comments' or field == 'comments' or (
                        m['datatype'] == 'composite' and \
                            m['display'].get('contains_html', False)):
                    val = mi.get(field, '')
                    if val and val.strip():
                        comments.append((m['name'], comments_to_html(val)))
                    continue
                if field in ('title', 'formats') or not args.get(field, False) \
                        or not m['name']:
                    continue
                if field == 'identifiers':
                    urls = urls_from_identifiers(mi.get(field, {}))
                    links = [u'<a class="details_category_link" target="_new" href="%s" title="%s:%s">%s</a>' % (url, id_typ, id_val, name)
                            for name, id_typ, id_val, url in urls]
                    links = u', '.join(links)
                    if links:
                        fields.append((m['name'], u'<strong>%s: </strong>%s'%(
                            _('Ids'), links)))
                        continue

                if m['datatype'] == 'rating':
                    r = u'<strong>%s: </strong>'%xml(m['name']) + \
                            render_rating(mi.get(field)/2.0, self.opts.url_prefix,
                                    prefix=m['name'])[0]
                else:
                    r = u'<strong>%s: </strong>'%xml(m['name']) + \
                                args[field]
                fields.append((m['name'], r))

            fields.sort(key=lambda x: sort_key(x[0]))
            fields = [u'<div class="field">{0}</div>'.format(f[1]) for f in
                    fields]
            fields = u'<div class="fields">%s</div>'%('\n\n'.join(fields))

            comments.sort(key=lambda x: x[0].lower())
            comments = [(u'<div class="field"><strong>%s: </strong>'
                         u'<div class="comment">%s</div></div>') % (xml(c[0]),
                             c[1]) for c in comments]
            comments = u'<div class="comments">%s</div>'%('\n\n'.join(comments))
            random = ''
            if add_random_button:
                href = '%s/browse/random?v=%s'%(
                    self.opts.url_prefix, time.time())
                random = '<a href="%s" id="random_button" title="%s">%s</a>' % (
                    xml(href, True), xml(_('Choose another random book'), True),
                    xml(_('Another random book')))

            return self.browse_details_template.format(
                id=id_, title=xml(mi.title, True), fields=fields,
                get_url=args['get_url'], fmt=args['fmt'],
                formats=args['formats'], comments=comments, random=random)

    @Endpoint(mimetype='application/json; charset=utf-8')
    def browse_details(self, id=None):
        try:
            id_ = int(id)
        except:
            raise cherrypy.HTTPError(404, 'invalid id: %r'%id)

        ans = self.browse_render_details(id_)

        return json.dumps(ans, ensure_ascii=True)

    @Endpoint()
    def browse_random(self, *args, **kwargs):
        import random
        book_id = random.choice(self.db.search_getting_ids(
            '', self.search_restriction))
        ans = self.browse_render_details(book_id, add_random_button=True)
        return self.browse_template('').format(
                title='', script='book();', main=ans)

    @Endpoint()
    def browse_book(self, id=None, category_sort=None):
        try:
            id_ = int(id)
        except:
            raise cherrypy.HTTPError(404, 'invalid id: %r'%id)

        ans = self.browse_render_details(id_)
        return self.browse_template('').format(
                title='', script='book();', main=ans)


    # }}}

    # Search {{{
    @Endpoint(sort_type='list')
    def browse_search(self, query='', list_sort=None):
        if isbytestring(query):
            query = query.decode('UTF-8')
        ids = self.db.search_getting_ids(query.strip(), self.search_restriction)
        items = [self.db.data._data[x] for x in ids]
        sort = self.browse_sort_book_list(items, list_sort)
        ids = [x[0] for x in items]
        html = render_book_list(ids, self.opts.url_prefix,
                suffix=_('in search')+': '+xml(query))
        return self.browse_template(sort, category=False, initial_search=query).format(
                title=_('Matching books'),
                script='search_result();', main=html)

    # }}}


