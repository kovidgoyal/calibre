#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Logic for setting up conversion jobs
'''
import os
from PyQt4.Qt import QDialog

from calibre.utils.config import prefs
from calibre.gui2.dialogs.lrf_single import LRFSingleDialog, LRFBulkDialog
from calibre.gui2.dialogs.epub import Config as EPUBConvert
import calibre.gui2.dialogs.comicconf as ComicConf
from calibre.gui2 import warning_dialog, dynamic
from calibre.ptempfile import PersistentTemporaryFile
from calibre.ebooks.lrf import preferred_source_formats as LRF_PREFERRED_SOURCE_FORMATS
from calibre.ebooks.metadata.opf import OPFCreator
from calibre.ebooks.epub.from_any import SOURCE_FORMATS as EPUB_PREFERRED_SOURCE_FORMATS

def convert_single_epub(parent, db, comics, others):
    changed = False
    jobs = []
    for row in others:
        temp_files = []
        d = EPUBConvert(parent, db, row)
        if d.source_format is not None:
            d.exec_()
            if d.result() == QDialog.Accepted:
                opts = d.opts
                data = db.format(row, d.source_format)
                pt = PersistentTemporaryFile('.'+d.source_format.lower())
                pt.write(data)
                pt.close()
                of = PersistentTemporaryFile('.epub')
                of.close()
                opts.output = of.name
                opts.from_opf = d.opf_file.name
                opts.verbose = 2
                args = [opts, pt.name]
                if d.cover_file:
                    temp_files.append(d.cover_file)
                    opts.cover = d.cover_file.name
                temp_files.extend([d.opf_file, pt, of])
                jobs.append(('any2epub', args, _('Convert book: ')+d.mi.title, 
                             'EPUB', db.id(row), temp_files))
                changed = True
                
    for row in comics:
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
        pt = PersistentTemporaryFile('.'+fmt)
        pt.write(data)
        pt.close()
        of = PersistentTemporaryFile('.epub')
        of.close()
        opts.output = of.name
        opts.verbose = 2
        args = [pt.name, opts]
        changed = True
        jobs.append(('comic2epub', args, _('Convert comic: ')+opts.title, 
                     'EPUB', db.id(row), [pt, of]))
        
    return jobs, changed
    
    

def convert_single_lrf(parent, db, comics, others):
    changed = False
    jobs = []
    for row in others:
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
                             'LRF', db.id(row), temp_files))
                changed = True
                
    for row in comics:
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
                     'LRF', db.id(row), [pt, of]))
        
    return jobs, changed

def convert_bulk_epub(parent, db, comics, others):
    if others:
        d = EPUBConvert(parent, db)
        if d.exec_() != QDialog.Accepted:
            others = []
        else:
            opts = d.opts
            opts.verbose = 2
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
        if row in others:
            data = None
            for fmt in EPUB_PREFERRED_SOURCE_FORMATS:
                try:
                    data = db.format(row, fmt.upper())
                    if data is not None:
                        break
                except:
                    continue
            if data is None:
                bad_rows.append(row)
                continue
            options = opts.copy()
            mi = db.get_metadata(row)
            opf = OPFCreator(os.getcwdu(), mi)
            opf_file = PersistentTemporaryFile('.opf')
            opf.render(opf_file)
            opf_file.close()
            pt = PersistentTemporaryFile('.'+fmt.lower())
            pt.write(data)
            pt.close()
            of = PersistentTemporaryFile('.epub')
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
            jobs.append(('any2epub', args, desc, 'EPUB', db.id(row), temp_files))
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
            of = PersistentTemporaryFile('.epub')
            of.close()
            setattr(options, 'output', of.name)
            options.verbose = 1
            args = [pt.name, options]
            desc = _('Convert book %d of %d (%s)')%(i+1, total, repr(mi.title))
            jobs.append(('comic2epub', args, desc, 'EPUB', db.id(row), [pt, of]))        
        
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
            jobs.append(('any2lrf', [cmdline], desc, 'LRF', db.id(row), temp_files))
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
            jobs.append(('comic2lrf', args, desc, 'LRF', db.id(row), [pt, of]))        
        
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

def set_conversion_defaults_epub(comic, parent, db):
    if comic:
        ComicConf.set_conversion_defaults(parent)
    else:
        d = EPUBConvert(parent, db)
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
            

def convert_single_ebook(*args):
    fmt = prefs['output_format'].lower()
    if fmt == 'lrf':
        return convert_single_lrf(*args)
    elif fmt == 'epub':
        return convert_single_epub(*args)
    
def convert_bulk_ebooks(*args):
    fmt = prefs['output_format'].lower()
    if fmt == 'lrf':
        return convert_bulk_lrf(*args)
    elif fmt == 'epub':
        return convert_bulk_epub(*args)
    
def set_conversion_defaults(comic, parent, db):
    fmt = prefs['output_format'].lower()
    if fmt == 'lrf':
        return set_conversion_defaults_lrf(comic, parent, db)
    elif fmt == 'epub':
        return set_conversion_defaults_epub(comic, parent, db)

def fetch_news(data):
    fmt = prefs['output_format'].lower()
    return _fetch_news(data, fmt)