#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, traceback, cStringIO, re, shutil
from functools import partial

from calibre.constants import DEBUG
from calibre.utils.config import Config, StringConfig, tweaks
from calibre.utils.formatter import TemplateFormatter
from calibre.utils.filenames import shorten_components_to, supports_long_names, \
                                    ascii_filename, sanitize_file_name
from calibre.ebooks.metadata.opf2 import metadata_to_opf
from calibre.ebooks.metadata.meta import set_metadata
from calibre.constants import preferred_encoding, filesystem_encoding
from calibre.ebooks.metadata import fmt_sidx
from calibre.ebooks.metadata import title_sort
from calibre import strftime, prints

plugboard_any_device_value = 'any device'
plugboard_any_format_value = 'any format'
plugboard_save_to_disk_value = 'save_to_disk'


DEFAULT_TEMPLATE = '{author_sort}/{title}/{title} - {authors}'
DEFAULT_SEND_TEMPLATE = '{author_sort}/{title} - {authors}'

FORMAT_ARG_DESCS = dict(
        title=_('The title'),
        authors=_('The authors'),
        author_sort=_('The author sort string. To use only the first letter '
            'of the name use {author_sort[0]}'),
        tags=_('The tags'),
        series=_('The series'),
        series_index=_('The series number. '
            'To get leading zeros use {series_index:0>3s} or '
            '{series_index:>3s} for leading spaces'),
        rating=_('The rating'),
        isbn=_('The ISBN'),
        publisher=_('The publisher'),
        timestamp=_('The date'),
        pubdate=_('The published date'),
        id=_('The calibre internal id')
        )

FORMAT_ARGS = {}
for x in FORMAT_ARG_DESCS:
    FORMAT_ARGS[x] = ''


def config(defaults=None):
    if defaults is None:
        c = Config('save_to_disk', _('Options to control saving to disk'))
    else:
        c = StringConfig(defaults)

    x = c.add_opt
    x('update_metadata', default=True,
            help=_('Normally, calibre will update the metadata in the saved files from what is'
            ' in the calibre library. Makes saving to disk slower.'))
    x('write_opf', default=True,
            help=_('Normally, calibre will write the metadata into a separate OPF file along with the'
                ' actual e-book files.'))
    x('save_cover', default=True,
            help=_('Normally, calibre will save the cover in a separate file along with the '
                'actual e-book file(s).'))
    x('formats', default='all',
            help=_('Comma separated list of formats to save for each book.'
                ' By default all available formats are saved.'))
    x('template', default=DEFAULT_TEMPLATE,
            help=_('The template to control the filename and directory structure of the saved files. '
                'Default is "%s" which will save books into a per-author '
                'subdirectory with filenames containing title and author. '
                'Available controls are: {%s}')%(DEFAULT_TEMPLATE, ', '.join(FORMAT_ARGS)))
    x('send_template', default=DEFAULT_SEND_TEMPLATE,
            help=_('The template to control the filename and directory structure of files '
                'sent to the device. '
                'Default is "%s" which will save books into a per-author '
                'directory with filenames containing title and author. '
                'Available controls are: {%s}')%(DEFAULT_SEND_TEMPLATE, ', '.join(FORMAT_ARGS)))

    x('asciiize', default=True,
            help=_('Normally, calibre will convert all non English characters into English equivalents '
                'for the file names. '
                'WARNING: If you turn this off, you may experience errors when '
                'saving, depending on how well the filesystem you are saving '
                'to supports unicode.'))
    x('timefmt', default='%b, %Y',
            help=_('The format in which to display dates. %d - day, %b - month, '
                '%Y - year. Default is: %b, %Y'))
    x('send_timefmt', default='%b, %Y',
            help=_('The format in which to display dates. %d - day, %b - month, '
                '%Y - year. Default is: %b, %Y'))
    x('to_lowercase', default=False,
            help=_('Convert paths to lowercase.'))
    x('replace_whitespace', default=False,
            help=_('Replace whitespace with underscores.'))
    return c

def preprocess_template(template):
    template = template.replace('//', '/')
    template = template.replace('{author}', '{authors}')
    template = template.replace('{tag}', '{tags}')
    if not isinstance(template, unicode):
        template = template.decode(preferred_encoding, 'replace')
    return template

class SafeFormat(TemplateFormatter):
    '''
    Provides a format function that substitutes '' for any missing value
    '''

    def get_value(self, key, args, kwargs):
        try:
            key = key.lower()
            try:
                b = self.book.get_user_metadata(key, False)
            except:
                traceback.print_exc()
                b = None
            if b is not None and b['datatype'] == 'composite':
                if key in self.composite_values:
                    return self.composite_values[key]
                self.composite_values[key] = 'RECURSIVE_COMPOSITE FIELD (S2D) ' + key
                self.composite_values[key] = \
                    self.vformat(b['display']['composite_template'], [], kwargs)
                return self.composite_values[key]
            if key in kwargs:
                val = kwargs[key]
                return val.replace('/', '_').replace('\\', '_')
            return ''
        except:
            traceback.print_exc()
            return key

def get_components(template, mi, id, timefmt='%b %Y', length=250,
        sanitize_func=ascii_filename, replace_whitespace=False,
        to_lowercase=False):
    tsfmt = partial(title_sort, order=tweaks['save_template_title_series_sorting'])
    format_args = FORMAT_ARGS.copy()
    format_args.update(mi.all_non_none_fields())
    if mi.title:
        format_args['title'] = tsfmt(mi.title)
    if mi.authors:
        format_args['authors'] = mi.format_authors()
        format_args['author'] = format_args['authors']
    if mi.tags:
        format_args['tags'] = mi.format_tags()
        if format_args['tags'].startswith('/'):
            format_args['tags'] = format_args['tags'][1:]
    else:
        format_args['tags'] = ''
    if mi.series:
        format_args['series'] = tsfmt(mi.series)
        if mi.series_index is not None:
            format_args['series_index'] = mi.format_series_index()
    else:
        template = re.sub(r'\{series_index[^}]*?\}', '', template)
    if mi.rating is not None:
        format_args['rating'] = mi.format_rating()
    if hasattr(mi.timestamp, 'timetuple'):
        format_args['timestamp'] = strftime(timefmt, mi.timestamp.timetuple())
    if hasattr(mi.pubdate, 'timetuple'):
        format_args['pubdate'] = strftime(timefmt, mi.pubdate.timetuple())
    format_args['id'] = str(id)
    # Now format the custom fields
    custom_metadata = mi.get_all_user_metadata(make_copy=False)
    for key in custom_metadata:
        if key in format_args:
            cm = custom_metadata[key]
            ## TODO: NEWMETA: should ratings be divided by 2? The standard rating isn't...
            if cm['datatype'] == 'series':
                format_args[key] = tsfmt(format_args[key])
                if key+'_index' in format_args:
                    format_args[key+'_index'] = fmt_sidx(format_args[key+'_index'])
            elif cm['datatype'] == 'datetime':
                format_args[key] = strftime(timefmt, format_args[key].timetuple())
            elif cm['datatype'] == 'bool':
                format_args[key] = _('yes') if format_args[key] else _('no')
            elif cm['datatype'] in ['int', 'float']:
                if format_args[key] != 0:
                    format_args[key] = unicode(format_args[key])
                else:
                    format_args[key] = ''
    components = SafeFormat().safe_format(template, format_args,
                                            'G_C-EXCEPTION!', mi)
    components = [x.strip() for x in components.split('/') if x.strip()]
    components = [sanitize_func(x) for x in components if x]
    if not components:
        components = [str(id)]
    components = [x.encode(filesystem_encoding, 'replace') if isinstance(x,
        unicode) else x for x in components]
    if to_lowercase:
        components = [x.lower() for x in components]
    if replace_whitespace:
        components = [re.sub(r'\s', '_', x) for x in components]

    return shorten_components_to(length, components)


def save_book_to_disk(id_, db, root, opts, length):
    mi = db.get_metadata(id_, index_is_id=True)
    cover = db.cover(id_, index_is_id=True, as_path=True)
    plugboards = db.prefs.get('plugboards', {})

    available_formats = db.formats(id_, index_is_id=True)
    if not available_formats:
        available_formats = []
    else:
        available_formats = [x.lower().strip() for x in
                available_formats.split(',')]
    formats = {}
    fmts = db.formats(id_, index_is_id=True, verify_formats=False)
    if fmts:
        fmts = fmts.split(',')
        for fmt in fmts:
            fpath = db.format_abspath(id_, fmt, index_is_id=True)
            if fpath is not None:
                formats[fmt.lower()] = fpath

    return do_save_book_to_disk(id_, mi, cover, plugboards,
            formats, root, opts, length)


def do_save_book_to_disk(id_, mi, cover, plugboards,
        format_map, root, opts, length):
    available_formats = [x.lower().strip() for x in format_map.keys()]
    if opts.formats == 'all':
        asked_formats = available_formats
    else:
        asked_formats = [x.lower().strip() for x in opts.formats.split(',')]
    formats = set(available_formats).intersection(set(asked_formats))
    if not formats:
        return True, id_, mi.title

    components = get_components(opts.template, mi, id_, opts.timefmt, length,
            ascii_filename if opts.asciiize else sanitize_file_name,
            to_lowercase=opts.to_lowercase,
            replace_whitespace=opts.replace_whitespace)
    base_path = os.path.join(root, *components)
    base_name = os.path.basename(base_path)
    dirpath = os.path.dirname(base_path)
    # Don't test for existence first as the test could fail but
    # another worker process could create the directory before
    # the call to makedirs
    try:
        os.makedirs(dirpath)
    except BaseException:
        if not os.path.exists(dirpath):
            raise

    ocover = mi.cover
    if opts.save_cover and cover and os.access(cover, os.R_OK):
        with open(base_path+'.jpg', 'wb') as f:
            with open(cover, 'rb') as s:
                shutil.copyfileobj(s, f)
        mi.cover = base_name+'.jpg'
    else:
        mi.cover = None

    if opts.write_opf:
        opf = metadata_to_opf(mi)
        with open(base_path+'.opf', 'wb') as f:
            f.write(opf)

    mi.cover = ocover

    written = False
    for fmt in formats:
        global plugboard_save_to_disk_value, plugboard_any_format_value
        dev_name = plugboard_save_to_disk_value
        cpb = None
        if fmt in plugboards:
            cpb = plugboards[fmt]
            if dev_name in cpb:
                cpb = cpb[dev_name]
            else:
                cpb = None
        if cpb is None and plugboard_any_format_value in plugboards:
            cpb = plugboards[plugboard_any_format_value]
            if dev_name in cpb:
                cpb = cpb[dev_name]
            else:
                cpb = None
        # Leave this here for a while, in case problems arise.
        if cpb is not None:
            prints('Save-to-disk using plugboard:', fmt, cpb)
        fp = format_map.get(fmt, None)
        if fp is None:
            continue
        with open(fp, 'rb') as f:
            data = f.read()
        written = True
        if opts.update_metadata:
            stream = cStringIO.StringIO()
            stream.write(data)
            stream.seek(0)
            try:
                if cpb:
                    newmi = mi.deepcopy_metadata()
                    newmi.template_to_attribute(mi, cpb)
                else:
                    newmi = mi
                set_metadata(stream, newmi, fmt)
            except:
                if DEBUG:
                    traceback.print_exc()
            stream.seek(0)
            data = stream.read()
        fmt_path = base_path+'.'+str(fmt)
        with open(fmt_path, 'wb') as f:
            f.write(data)

    return not written, id_, mi.title

def _sanitize_args(root, opts):
    if opts is None:
        opts = config().parse()
    if isinstance(root, unicode):
        root = root.encode(filesystem_encoding)
    root = os.path.abspath(root)

    opts.template = preprocess_template(opts.template)
    length = 1000 if supports_long_names(root) else 250
    length -= len(root)
    if length < 5:
        raise ValueError('%r is too long.'%root)
    return root, opts, length

def save_to_disk(db, ids, root, opts=None, callback=None):
    '''
    Save books from the database ``db`` to the path specified by ``root``.

    :param:`ids` iterable of book ids to save from the database.
    :param:`callback` is an optional callable that is called on after each
    book is processed with the arguments: id, title, failed, traceback.
    If the callback returns False, further processing is terminated and
    the function returns.
    :return: A list of failures. Each element of the list is a tuple
    (id, title, traceback)
    '''
    root, opts, length = _sanitize_args(root, opts)
    failures = []
    for x in ids:
        tb = ''
        try:
            failed, id, title = save_book_to_disk(x, db, root, opts, length)
            tb = _('Requested formats not available')
        except:
            failed, id, title = True, x, db.title(x, index_is_id=True)
            tb = traceback.format_exc()
        if failed:
            failures.append((id, title, tb))
        if callable(callback):
            if not callback(int(id), title, failed, tb):
                break
    return failures

def save_serialized_to_disk(ids, data, plugboards, root, opts, callback):
    from calibre.ebooks.metadata.opf2 import OPF
    root, opts, length = _sanitize_args(root, opts)
    failures = []
    for x in ids:
        opf, cover, format_map = data[x]
        if isinstance(opf, unicode):
            opf = opf.encode('utf-8')
        mi = OPF(cStringIO.StringIO(opf)).to_book_metadata()
        tb = ''
        try:
            failed, id, title = do_save_book_to_disk(x, mi, cover, plugboards,
                    format_map, root, opts, length)
            tb = _('Requested formats not available')
        except:
            failed, id, title = True, x, mi.title
            tb = traceback.format_exc()
        if failed:
            failures.append((id, title, tb))
        if callable(callback):
            if not callback(int(id), title, failed, tb):
                break

    return failures

