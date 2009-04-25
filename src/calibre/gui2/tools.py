#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Logic for setting up conversion jobs
'''
import os
from PyQt4.Qt import QDialog

from calibre.customize.ui import available_input_formats
from calibre.utils.config import prefs
from calibre.gui2 import warning_dialog
from calibre.ptempfile import PersistentTemporaryFile

# Ordered list of source formats. Items closer to the beginning are
# preferred for conversion over those toward the end.
PREFERRED_SOURCE_FORMATS = ['epub', 'lit', 'mobi', 'prc', 'azw', 'fb2', 'odt', 'rtf',
                  'txt', 'pdf', 'oebzip', 'htm', 'html']

def get_dialog(fmt):
    return {
              'epub':EPUBConvert,
              'mobi':MOBIConvert,
              }[fmt]

def get_config(fmt):
    return {
              'epub':epubconfig,
              'mobi':mobiconfig,
           }[fmt]

def auto_convert(fmt, parent, db, rows):
    changed = False
    jobs = []

    total = len(rows)
    if total == 0:
        return None, None, None
    parent.status_bar.showMessage(_('Starting auto conversion of %d books')%total, 2000)

    i = 0
    bad_rows = []

    for i, row in enumerate(rows):
        row_id = db.id(row)

        temp_files = []

        data = None
        in_formats = [f.lower() for f in db.formats(row).split(',')]
        in_formats = list(set(in_formats).intersection(available_input_formats()))
        for _fmt in PREFERRED_SOURCE_FORMATS:
            if _fmt in in_formats:
                data = _fmt
                break
        if data is None:
            if in_formats != []:
                data = list(in_formats)[0]
            else:
                bad_rows.append(row)
                continue

        mi = db.get_metadata(row)
        in_file = db.format_abspath(row, data)
        out_file = PersistentTemporaryFile('.'+fmt.lower())
        out_file.write(data)
        out_file.close()
        desc = _('Auto convert book %d of %d (%s)')%(i+1, total, repr(mi.title))
        args = [['', in_file, out_file.name]]
        temp_files = [out_file]
        jobs.append(('ebook-convert', args, desc, fmt.upper(), row_id, temp_files))

        changed = True

    if bad_rows:
        res = []
        for row in bad_rows:
            title = db.title(row)
            res.append('<li>%s</li>'%title)

        msg = _('<p>Could not convert %d of %d books, because no suitable source format was found.<ul>%s</ul>')%(len(res), total, '\n'.join(res))
        warning_dialog(parent, _('Could not convert some books'), msg).exec_()

    return jobs, changed, bad_rows

def convert_single(fmt, parent, db, comics, others):
    changed = False
    jobs = []
    others_ids = [db.id(row) for row in others]
    comics_ids = [db.id(row) for row in comics]
    for row, row_id in zip(others, others_ids):
        temp_files = []
        d = get_dialog(fmt)(parent, db, row)
        if d.source_format is not None:
            d.exec_()
            if d.result() == QDialog.Accepted:
                opts = d.opts
                data = db.format(row, d.source_format)
                pt = PersistentTemporaryFile('.'+d.source_format.lower())
                pt.write(data)
                pt.close()
                of = PersistentTemporaryFile('.'+fmt)
                of.close()
                opts.output = of.name
                opts.from_opf = d.opf_file.name
                opts.verbose = 2
                args = [opts, pt.name]
                if d.cover_file:
                    temp_files.append(d.cover_file)
                    opts.cover = d.cover_file.name
                temp_files.extend([d.opf_file, pt, of])
                jobs.append(('any2'+fmt, args, _('Convert book: ')+d.mi.title,
                             fmt.upper(), row_id, temp_files))
                changed = True

    for row, row_id in zip(comics, comics_ids):
        mi = db.get_metadata(row)
        title = author = _('Unknown')
        if mi.title:
            title = mi.title
        if mi.authors:
            author =  ','.join(mi.authors)
        defaults = db.conversion_options(db.id(row), 'comic')
        opts, defaults = ComicConf.get_conversion_options(parent, defaults, title, author)
        if defaults is not None:
            db.set_conversion_options(db.id(row), 'comic', defaults)
        if opts is None: continue
        for _fmt in ['cbz', 'cbr']:
            try:
                data = db.format(row, _fmt.upper())
                if data is not None:
                    break
            except:
                continue
        pt = PersistentTemporaryFile('.'+_fmt)
        pt.write(data)
        pt.close()
        of = PersistentTemporaryFile('.'+fmt)
        of.close()
        opts.output = of.name
        opts.verbose = 2
        args = [pt.name, opts]
        changed = True
        jobs.append(('comic2'+fmt, args, _('Convert comic: ')+opts.title,
                     fmt.upper(), row_id, [pt, of]))

    return jobs, changed



def convert_single_lrf(parent, db, comics, others):
    changed = False
    jobs = []
    others_ids = [db.id(row) for row in others]
    comics_ids = [db.id(row) for row in comics]
    for row, row_id in zip(others, others_ids):
        temp_files = []
        d = LRFSingleDialog(parent, db, row)
        if d.selected_format:
            d.exec_()
            if d.result() == QDialog.Accepted:
                cmdline = d.cmdline
                data = db.format(row, d.selected_format)
                pt = PersistentTemporaryFile('.'+d.selected_format.lower())
                pt.write(data)
                pt.close()
                of = PersistentTemporaryFile('.lrf')
                of.close()
                cmdline.extend(['-o', of.name])
                cmdline.append(pt.name)
                if d.cover_file:
                    temp_files.append(d.cover_file)
                temp_files.extend([pt, of])
                jobs.append(('any2lrf', [cmdline], _('Convert book: ')+d.title(),
                             'LRF', row_id, temp_files))
                changed = True

    for row, row_id in zip(comics, comics_ids):
        mi = db.get_metadata(row)
        title = author = _('Unknown')
        if mi.title:
            title = mi.title
        if mi.authors:
            author =  ','.join(mi.authors)
        defaults = db.conversion_options(db.id(row), 'comic')
        opts, defaults = ComicConf.get_conversion_options(parent, defaults, title, author)
        if defaults is not None:
            db.set_conversion_options(db.id(row), 'comic', defaults)
        if opts is None: continue
        for fmt in ['cbz', 'cbr']:
            try:
                data = db.format(row, fmt.upper())
                if data is not None:
                    break
            except:
                continue
        if data is None:
            continue
        pt = PersistentTemporaryFile('.'+fmt)
        pt.write(data)
        pt.close()
        of = PersistentTemporaryFile('.lrf')
        of.close()
        opts.output = of.name
        opts.verbose = 1
        args = [pt.name, opts]
        changed = True
        jobs.append(('comic2lrf', args, _('Convert comic: ')+opts.title,
                     'LRF', row_id, [pt, of]))

    return jobs, changed

def convert_bulk(fmt, parent, db, comics, others):
    if others:
        d = get_dialog(fmt)(parent, db)
        if d.exec_() != QDialog.Accepted:
            others, user_mi = [], None
        else:
            opts = d.opts
            opts.verbose = 2
            user_mi = d.user_mi
    if comics:
        comic_opts = ComicConf.get_bulk_conversion_options(parent)
        if not comic_opts:
            comics = []
    bad_rows = []
    jobs = []
    total = sum(map(len, (others, comics)))
    if total == 0:
        return
    parent.status_bar.showMessage(_('Starting Bulk conversion of %d books')%total, 2000)

    for i, row in enumerate(others+comics):
        row_id = db.id(row)
        if row in others:
            data = None
            for _fmt in EPUB_PREFERRED_SOURCE_FORMATS:
                try:
                    data = db.format(row, _fmt.upper())
                    if data is not None:
                        break
                except:
                    continue
            if data is None:
                bad_rows.append(row)
                continue
            options = opts.copy()
            mi = db.get_metadata(row)
            if user_mi is not None:
                if user_mi.series_index == 1:
                    user_mi.series_index = None
                mi.smart_update(user_mi)
            db.set_metadata(db.id(row), mi)
            opf = OPFCreator(os.getcwdu(), mi)
            opf_file = PersistentTemporaryFile('.opf')
            opf.render(opf_file)
            opf_file.close()
            pt = PersistentTemporaryFile('.'+_fmt.lower())
            pt.write(data)
            pt.close()
            of = PersistentTemporaryFile('.'+fmt)
            of.close()
            cover = db.cover(row)
            cf = None
            if cover:
                cf = PersistentTemporaryFile('.jpeg')
                cf.write(cover)
                cf.close()
                options.cover = cf.name
            options.output = of.name
            options.from_opf = opf_file.name
            args = [options, pt.name]
            desc = _('Convert book %d of %d (%s)')%(i+1, total, repr(mi.title))
            temp_files = [cf] if cf is not None else []
            temp_files.extend([opf_file, pt, of])
            jobs.append(('any2'+fmt, args, desc, fmt.upper(), row_id, temp_files))
        else:
            options = comic_opts.copy()
            mi = db.get_metadata(row)
            if mi.title:
                options.title = mi.title
            if mi.authors:
                options.author =  ','.join(mi.authors)
            data = None
            for _fmt in ['cbz', 'cbr']:
                try:
                    data = db.format(row, _fmt.upper())
                    if data is not None:
                        break
                except:
                    continue

            pt = PersistentTemporaryFile('.'+_fmt.lower())
            pt.write(data)
            pt.close()
            of = PersistentTemporaryFile('.'+fmt)
            of.close()
            setattr(options, 'output', of.name)
            options.verbose = 1
            args = [pt.name, options]
            desc = _('Convert book %d of %d (%s)')%(i+1, total, repr(mi.title))
            jobs.append(('comic2'+fmt, args, desc, fmt.upper(), row_id, [pt, of]))

    if bad_rows:
        res = []
        for row in bad_rows:
            title = db.title(row)
            res.append('<li>%s</li>'%title)

        msg = _('<p>Could not convert %d of %d books, because no suitable source format was found.<ul>%s</ul>')%(len(res), total, '\n'.join(res))
        warning_dialog(parent, _('Could not convert some books'), msg).exec_()

    return jobs, False


def convert_bulk_lrf(parent, db, comics, others):
    if others:
        d = LRFBulkDialog(parent)
        if d.exec_() != QDialog.Accepted:
            others = []
    if comics:
        comic_opts = ComicConf.get_bulk_conversion_options(parent)
        if not comic_opts:
            comics = []
    bad_rows = []
    jobs = []
    total = sum(map(len, (others, comics)))
    if total == 0:
        return
    parent.status_bar.showMessage(_('Starting Bulk conversion of %d books')%total, 2000)

    for i, row in enumerate(others+comics):
        row_id = db.id(row)
        if row in others:
            cmdline = list(d.cmdline)
            mi = db.get_metadata(row)
            if mi.title:
                cmdline.extend(['--title', mi.title])
            if mi.authors:
                cmdline.extend(['--author', ','.join(mi.authors)])
            if mi.publisher:
                cmdline.extend(['--publisher', mi.publisher])
            if mi.comments:
                cmdline.extend(['--comment', mi.comments])
            data = None
            for fmt in LRF_PREFERRED_SOURCE_FORMATS:
                try:
                    data = db.format(row, fmt.upper())
                    if data is not None:
                        break
                except:
                    continue
            if data is None:
                bad_rows.append(row)
                continue
            pt = PersistentTemporaryFile('.'+fmt.lower())
            pt.write(data)
            pt.close()
            of = PersistentTemporaryFile('.lrf')
            of.close()
            cover = db.cover(row)
            cf = None
            if cover:
                cf = PersistentTemporaryFile('.jpeg')
                cf.write(cover)
                cf.close()
                cmdline.extend(['--cover', cf.name])
            cmdline.extend(['-o', of.name])
            cmdline.append(pt.name)
            desc = _('Convert book %d of %d (%s)')%(i+1, total, repr(mi.title))
            temp_files = [cf] if cf is not None else []
            temp_files.extend([pt, of])
            jobs.append(('any2lrf', [cmdline], desc, 'LRF', row_id, temp_files))
        else:
            options = comic_opts.copy()
            mi = db.get_metadata(row)
            if mi.title:
                options.title = mi.title
            if mi.authors:
                options.author =  ','.join(mi.authors)
            data = None
            for fmt in ['cbz', 'cbr']:
                try:
                    data = db.format(row, fmt.upper())
                    if data is not None:
                        break
                except:
                    continue

            pt = PersistentTemporaryFile('.'+fmt.lower())
            pt.write(data)
            pt.close()
            of = PersistentTemporaryFile('.lrf')
            of.close()
            setattr(options, 'output', of.name)
            options.verbose = 1
            args = [pt.name, options]
            desc = _('Convert book %d of %d (%s)')%(i+1, total, repr(mi.title))
            jobs.append(('comic2lrf', args, desc, 'LRF', row_id, [pt, of]))

    if bad_rows:
        res = []
        for row in bad_rows:
            title = db.title(row)
            res.append('<li>%s</li>'%title)

        msg = _('<p>Could not convert %d of %d books, because no suitable source format was found.<ul>%s</ul>')%(len(res), total, '\n'.join(res))
        warning_dialog(parent, _('Could not convert some books'), msg).exec_()

    return jobs, False

def set_conversion_defaults_lrf(comic, parent, db):
    if comic:
        ComicConf.set_conversion_defaults(parent)
    else:
        LRFSingleDialog(parent, None, None).exec_()

def _set_conversion_defaults(dialog, comic, parent, db):
    if comic:
        ComicConf.set_conversion_defaults(parent)
    else:
        d = dialog(parent, db)
        d.setWindowTitle(_('Set conversion defaults'))
        d.exec_()

def _fetch_news(data, fmt):
    pt = PersistentTemporaryFile(suffix='_feeds2%s.%s'%(fmt.lower(), fmt.lower()))
    pt.close()
    args = ['feeds2%s'%fmt.lower(), '--output', pt.name, '--debug']
    if data['username']:
        args.extend(['--username', data['username']])
    if data['password']:
        args.extend(['--password', data['password']])
    args.append(data['script'] if data['script'] else data['title'])
    return 'feeds2'+fmt.lower(), [args], _('Fetch news from ')+data['title'], fmt.upper(), [pt]


def fetch_scheduled_recipe(recipe, script):
    from calibre.gui2.dialogs.scheduler import config
    fmt = prefs['output_format'].lower()
    pt = PersistentTemporaryFile(suffix='_feeds2%s.%s'%(fmt.lower(), fmt.lower()))
    pt.close()
    args = ['feeds2%s'%fmt.lower(), '--output', pt.name, '--debug']
    if recipe.needs_subscription:
        x = config.get('recipe_account_info_%s'%recipe.id, False)
        if not x:
            raise ValueError(_('You must set a username and password for %s')%recipe.title)
        args.extend(['--username', x[0], '--password', x[1]])
    args.append(script)
    return 'feeds2'+fmt, [args], _('Fetch news from ')+recipe.title, fmt.upper(), [pt]

def auto_convert_ebook(*args):
    return auto_convert(*args)

def convert_single_ebook(*args):
    fmt = prefs['output_format'].lower()
    if fmt == 'lrf':
        return convert_single_lrf(*args)
    elif fmt in ('epub', 'mobi'):
        return convert_single(fmt, *args)

def convert_bulk_ebooks(*args):
    fmt = prefs['output_format'].lower()
    if fmt == 'lrf':
        return convert_bulk_lrf(*args)
    elif fmt in ('epub', 'mobi'):
        return convert_bulk(fmt, *args)

def set_conversion_defaults(comic, parent, db):
    fmt = prefs['output_format'].lower()
    if fmt == 'lrf':
        return set_conversion_defaults_lrf(comic, parent, db)
    elif fmt in ('epub', 'mobi'):
        return _set_conversion_defaults(get_dialog(fmt), comic, parent, db)

def fetch_news(data):
    fmt = prefs['output_format'].lower()
    return _fetch_news(data, fmt)

