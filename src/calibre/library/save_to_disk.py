#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, traceback, re, errno

from calibre.constants import DEBUG
from calibre.db.errors import NoSuchFormat
from calibre.utils.config import Config, StringConfig, tweaks
from calibre.utils.formatter import TemplateFormatter
from calibre.utils.filenames import shorten_components_to, ascii_filename
from calibre.constants import preferred_encoding
from calibre.ebooks.metadata import fmt_sidx
from calibre.ebooks.metadata import title_sort
from calibre.utils.date import as_local_time
from calibre import strftime, prints, sanitize_file_name
from calibre.db.lazy import FormatsList

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
        last_modified=_('The date when the metadata for this book record'
            ' was last modified'),
        languages=_('The language(s) of this book'),
        id=_('The calibre internal id')
        )

FORMAT_ARGS = {}
for x in FORMAT_ARG_DESCS:
    FORMAT_ARGS[x] = ''


def find_plugboard(device_name, format, plugboards):
    cpb = None
    if format in plugboards:
        pb = plugboards[format]
        if device_name in pb:
            cpb = pb[device_name]
        elif plugboard_any_device_value in pb:
            cpb = pb[plugboard_any_device_value]
    if not cpb and plugboard_any_format_value in plugboards:
        pb = plugboards[plugboard_any_format_value]
        if device_name in pb:
            cpb = pb[device_name]
        elif plugboard_any_device_value in pb:
            cpb = pb[plugboard_any_device_value]
    if DEBUG:
        prints('Device using plugboard', format, device_name, cpb)
    return cpb


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
                'actual e-book files.'))
    x('formats', default='all',
            help=_('Comma separated list of formats to save for each book.'
                ' By default all available formats are saved.'))
    x('template', default=DEFAULT_TEMPLATE,
            help=_('The template to control the filename and folder structure of the saved files. '
                'Default is "%(templ)s" which will save books into a per-author '
                'subfolder with filenames containing title and author. '
                'Available controls are: {%(controls)s}')%dict(
                    templ=DEFAULT_TEMPLATE, controls=', '.join(sorted(FORMAT_ARGS))))
    x('send_template', default=DEFAULT_SEND_TEMPLATE,
            help=_('The template to control the filename and folder structure of files '
                'sent to the device. '
                'Default is "%(templ)s" which will save books into a per-author '
                'folder with filenames containing title and author. '
                'Available controls are: {%(controls)s}')%dict(
                    templ=DEFAULT_SEND_TEMPLATE, controls=', '.join(FORMAT_ARGS)))
    x('asciiize', default=False,
            help=_('Have calibre convert all non English characters into English equivalents '
                'for the file names. This is useful if saving to a legacy filesystem '
                'without full support for Unicode filenames.'))
    x('timefmt', default='%b, %Y',
            help=_('The format in which to display dates. %(day)s - day,'
                ' %(month)s - month, %(mn)s - month number, %(year)s - year. Default is: %(default)s'
                )%dict(day='%d', month='%b', mn='%m', year='%Y', default='%b, %Y'))
    x('send_timefmt', default='%b, %Y',
            help=_('The format in which to display dates. %(day)s - day,'
                ' %(month)s - month, %(mn)s - month number, %(year)s - year. Default is: %(default)s'
                )%dict(day='%d', month='%b', mn='%m', year='%Y', default='%b, %Y'))
    x('to_lowercase', default=False,
            help=_('Convert paths to lowercase.'))
    x('replace_whitespace', default=False,
            help=_('Replace whitespace with underscores.'))
    x('single_dir', default=False,
            help=_('Save into a single folder, ignoring the template'
                ' folder structure'))
    return c


def preprocess_template(template):
    template = template.replace('//', '/')
    template = template.replace('{author}', '{authors}')
    template = template.replace('{tag}', '{tags}')
    if not isinstance(template, str):
        template = template.decode(preferred_encoding, 'replace')
    return template


class Formatter(TemplateFormatter):
    '''
    Provides a format function that substitutes '' for any missing value
    '''

    def get_value(self, key, args, kwargs):
        if key == '':
            return ''
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
                    self.evaluate(b['display']['composite_template'], [], kwargs, {})
                return self.composite_values[key]
            if key in kwargs:
                val = kwargs[key]
                if isinstance(val, list) or isinstance(val, FormatsList):
                    val = ','.join(val)
                return val.replace('/', '_').replace('\\', '_')
            return ''
        except:
            traceback.print_exc()
            return key


def get_components(template, mi, id, timefmt='%b %Y', length=250,
        sanitize_func=ascii_filename, replace_whitespace=False,
        to_lowercase=False, safe_format=True, last_has_extension=True,
        single_dir=False):
    tsorder = tweaks['save_template_title_series_sorting']
    format_args = FORMAT_ARGS.copy()
    format_args.update(mi.all_non_none_fields())
    if mi.title:
        if tsorder == 'strictly_alphabetic':
            v = mi.title
        else:
            # title_sort might be missing or empty. Check both conditions
            v = mi.get('title_sort', None)
            if not v:
                v = title_sort(mi.title, order=tsorder)
        format_args['title'] = v
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
        format_args['series'] = title_sort(mi.series, order=tsorder)
        if mi.series_index is not None:
            format_args['series_index'] = mi.format_series_index()
    else:
        template = re.sub(r'\{series_index[^}]*?\}', '', template)
    if mi.rating is not None:
        format_args['rating'] = mi.format_rating(divide_by=2.0)
    if mi.identifiers:
        format_args['identifiers'] = mi.format_field_extended('identifiers')[1]
    else:
        format_args['identifiers'] = ''

    if hasattr(mi.timestamp, 'timetuple'):
        format_args['timestamp'] = strftime(timefmt, mi.timestamp.timetuple())
    if hasattr(mi.pubdate, 'timetuple'):
        format_args['pubdate'] = strftime(timefmt, mi.pubdate.timetuple())
    if hasattr(mi, 'last_modified') and hasattr(mi.last_modified, 'timetuple'):
        format_args['last_modified'] = strftime(timefmt, mi.last_modified.timetuple())

    format_args['id'] = str(id)
    # Now format the custom fields
    custom_metadata = mi.get_all_user_metadata(make_copy=False)
    for key in custom_metadata:
        if key in format_args:
            cm = custom_metadata[key]
            if cm['datatype'] == 'series':
                format_args[key] = title_sort(format_args[key], order=tsorder)
                if key+'_index' in format_args:
                    format_args[key+'_index'] = fmt_sidx(format_args[key+'_index'])
            elif cm['datatype'] == 'datetime':
                format_args[key] = strftime(timefmt, as_local_time(format_args[key]).timetuple())
            elif cm['datatype'] == 'bool':
                format_args[key] = _('yes') if format_args[key] else _('no')
            elif cm['datatype'] == 'rating':
                format_args[key] = mi.format_rating(format_args[key],
                        divide_by=2.0)
            elif cm['datatype'] in ['int', 'float']:
                if format_args[key] != 0:
                    format_args[key] = str(format_args[key])
                else:
                    format_args[key] = ''
    if safe_format:
        components = Formatter().safe_format(template, format_args,
                                            'G_C-EXCEPTION!', mi)
    else:
        components = Formatter().unsafe_format(template, format_args, mi)
    components = [x.strip() for x in components.split('/')]
    components = [sanitize_func(x) for x in components if x]
    if not components:
        components = [str(id)]
    if to_lowercase:
        components = [x.lower() for x in components]
    if replace_whitespace:
        components = [re.sub(r'\s', '_', x) for x in components]

    if single_dir:
        components = components[-1:]
    return shorten_components_to(length, components, last_has_extension=last_has_extension)


def get_formats(available_formats, formats):
    available_formats = {x.lower().strip() for x in available_formats}
    if formats == 'all':
        asked_formats = available_formats
    else:
        asked_formats = {x.lower().strip() for x in formats.split(',')}
    return available_formats & asked_formats


def save_book_to_disk(book_id, db, root, opts, length):
    db = db.new_api
    mi = db.get_metadata(book_id, index_is_id=True)
    plugboards = db.pref('plugboards', {})
    formats = get_formats(db.formats(book_id), opts.formats)
    return do_save_book_to_disk(db, book_id, mi, plugboards,
        formats, root, opts, length)


def get_path_components(opts, mi, book_id, path_length):
    try:
        components = get_components(opts.template, mi, book_id, opts.timefmt, path_length,
            ascii_filename if opts.asciiize else sanitize_file_name,
            to_lowercase=opts.to_lowercase,
            replace_whitespace=opts.replace_whitespace, safe_format=False,
            last_has_extension=False, single_dir=opts.single_dir)
    except Exception as e:
        raise ValueError(_('Failed to calculate path for '
            'save to disk. Template: %(templ)s\n'
            'Error: %(err)s')%dict(templ=opts.template, err=e))
    if not components:
        raise ValueError(_('Template evaluation resulted in no'
            ' path components. Template: %s')%opts.template)
    return components


def update_metadata(mi, fmt, stream, plugboards, cdata, error_report=None, plugboard_cache=None):
    from calibre.ebooks.metadata.meta import set_metadata
    if error_report is not None:
        def report_error(mi, fmt, tb):
            error_report(fmt, tb)

    try:
        if plugboard_cache is not None:
            cpb = plugboard_cache[fmt]
        else:
            cpb = find_plugboard(plugboard_save_to_disk_value, fmt, plugboards)
        if cpb:
            newmi = mi.deepcopy_metadata()
            newmi.template_to_attribute(mi, cpb)
        else:
            newmi = mi
        if cdata:
            newmi.cover_data = ('jpg', cdata)
        set_metadata(stream, newmi, fmt, report_error=None if error_report is None else report_error)
    except:
        if error_report is None:
            prints('Failed to set metadata for the', fmt, 'format of', mi.title)
            traceback.print_exc()
        else:
            error_report(fmt, traceback.format_exc())


def do_save_book_to_disk(db, book_id, mi, plugboards,
        formats, root, opts, length):
    originals = mi.cover, mi.pubdate, mi.timestamp
    formats_written = False
    try:
        if mi.pubdate:
            mi.pubdate = as_local_time(mi.pubdate)
        if mi.timestamp:
            mi.timestamp = as_local_time(mi.timestamp)

        components = get_path_components(opts, mi, book_id, length)
        base_path = os.path.join(root, *components)
        base_name = os.path.basename(base_path)
        dirpath = os.path.dirname(base_path)
        try:
            os.makedirs(dirpath)
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise

        cdata = None
        if opts.save_cover:
            cdata = db.cover(book_id)
            if cdata:
                cpath = base_path + '.jpg'
                with lopen(cpath, 'wb') as f:
                    f.write(cdata)
                mi.cover = base_name+'.jpg'
        if opts.write_opf:
            from calibre.ebooks.metadata.opf2 import metadata_to_opf
            opf = metadata_to_opf(mi)
            with lopen(base_path+'.opf', 'wb') as f:
                f.write(opf)
    finally:
        mi.cover, mi.pubdate, mi.timestamp = originals

    if not formats:
        return not formats_written, book_id, mi.title

    for fmt in formats:
        fmt_path = base_path+'.'+str(fmt)
        try:
            db.copy_format_to(book_id, fmt, fmt_path)
            formats_written = True
        except NoSuchFormat:
            continue
        if opts.update_metadata:
            with lopen(fmt_path, 'r+b') as stream:
                update_metadata(mi, fmt, stream, plugboards, cdata)

    return not formats_written, book_id, mi.title


def sanitize_args(root, opts):
    if opts is None:
        opts = config().parse()
    root = os.path.abspath(root)

    opts.template = preprocess_template(opts.template)
    length = 240
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
    root, opts, length = sanitize_args(root, opts)
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


def read_serialized_metadata(data):
    from calibre.ebooks.metadata.opf2 import OPF
    from calibre.utils.date import parse_date
    mi = OPF(data['opf'], try_to_guess_cover=False, populate_spine=False, basedir=os.path.dirname(data['opf'])).to_book_metadata()
    try:
        mi.last_modified = parse_date(data['last_modified'])
    except:
        pass
    mi.cover, mi.cover_data = None, (None, None)
    cdata = None
    if 'cover' in data:
        with lopen(data['cover'], 'rb') as f:
            cdata = f.read()
    return mi, cdata


def update_serialized_metadata(book, common_data=None):
    result = []
    plugboard_cache = common_data
    from calibre.customize.ui import apply_null_metadata
    with apply_null_metadata:
        fmts = [fp.rpartition(os.extsep)[-1] for fp in book['fmts']]
        mi, cdata = read_serialized_metadata(book)

        def report_error(fmt, tb):
            result.append((fmt, tb))

        for fmt, fmtpath in zip(fmts, book['fmts']):
            try:
                with lopen(fmtpath, 'r+b') as stream:
                    update_metadata(mi, fmt, stream, (), cdata, error_report=report_error, plugboard_cache=plugboard_cache)
            except Exception:
                report_error(fmt, traceback.format_exc())

    return result
