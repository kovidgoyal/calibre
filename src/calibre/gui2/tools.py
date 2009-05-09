#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Logic for setting up conversion jobs
'''

import cPickle

from PyQt4.Qt import QDialog

from calibre.ptempfile import PersistentTemporaryFile
from calibre.gui2 import warning_dialog
from calibre.gui2.convert.single import NoSupportedInputFormats
from calibre.gui2.convert.single import Config as SingleConfig
from calibre.gui2.convert.bulk import BulkConfig
from calibre.utils.config import prefs

def convert_single_ebook(parent, db, book_ids, auto_conversion=False, out_format=None):
    changed = False
    jobs = []
    bad = []

    total = len(book_ids)
    if total == 0:
        return None, None, None
    parent.status_bar.showMessage(_('Starting conversion of %d books') % total, 2000)

    for i, book_id in enumerate(book_ids):
        temp_files = []

        try:
            d = SingleConfig(parent, db, book_id, None, out_format)

            if auto_conversion:
                d.accept()
                result = QDialog.Accepted
            else:
                result = d.exec_()

            if result == QDialog.Accepted:
                mi = db.get_metadata(book_id, True)
                in_file = db.format_abspath(book_id, d.input_format, True)

                out_file = PersistentTemporaryFile('.' + d.output_format)
                out_file.write(d.output_format)
                out_file.close()

                desc = _('Convert book %d of %d (%s)') % (i + 1, total, repr(mi.title))

                recs = cPickle.loads(d.recommendations)
                args = [in_file, out_file.name, recs]
                temp_files = [out_file]
                jobs.append(('gui_convert', args, desc, d.output_format.upper(), book_id, temp_files))

                changed = True
        except NoSupportedInputFormats:
            bad.append(book_id)

    if bad != []:
        res = []
        for id in bad:
            title = db.title(id, True)
            res.append('%s'%title)

        msg = '%s' % '\n'.join(res)
        warning_dialog(parent, _('Could not convert some books'),
            _('Could not convert %d of %d books, because no suitable source format was found.' % (len(res), total)),
            msg).exec_()

    return jobs, changed, bad

def convert_bulk_ebook(parent, db, book_ids, out_format=None):
    changed = False
    jobs = []
    bad = []

    total = len(book_ids)
    if total == 0:
        return None, None, None
    parent.status_bar.showMessage(_('Starting conversion of %d books') % total, 2000)

    d = BulkConfig(parent, db, out_format)
    if d.exec_() != QDialog.Accepted:
        return jobs, changed, bad

    output_format = d.output_format
    recs = cPickle.loads(d.recommendations)

    for i, book_id in enumerate(book_ids):
        temp_files = []

        try:
            d = SingleConfig(parent, db, book_id, None, output_format)
            d.accept()

            mi = db.get_metadata(book_id, True)
            in_file = db.format_abspath(book_id, d.input_format, True)

            out_file = PersistentTemporaryFile('.' + output_format)
            out_file.write(output_format)
            out_file.close()

            desc = _('Convert book %d of %d (%s)') % (i + 1, total, repr(mi.title))

            args = [in_file, out_file.name, recs]
            temp_files = [out_file]
            jobs.append(('gui_convert', args, desc, d.output_format.upper(), book_id, temp_files))

            changed = True
        except NoSupportedInputFormats:
            bad.append(book_id)

    if bad != []:
        res = []
        for id in bad:
            title = db.title(id, True)
            res.append('%s'%title)

        msg = '%s' % '\n'.join(res)
        warning_dialog(parent, _('Could not convert some books'),
            _('Could not convert %d of %d books, because no suitable source format was found.' % (len(res), total)),
            msg).exec_()

    return jobs, changed, bad

def fetch_scheduled_recipe(recipe, script):
    from calibre.gui2.dialogs.scheduler import config
    fmt = prefs['output_format'].lower()
    pt = PersistentTemporaryFile(suffix='_recipe_out.%s'%fmt.lower())
    pt.close()
    args = ['ebook-convert', script, pt.name, '-vv']
    if recipe.needs_subscription:
        x = config.get('recipe_account_info_%s'%recipe.id, False)
        if not x:
            raise ValueError(_('You must set a username and password for %s')%recipe.title)
        args.extend(['--username', x[0], '--password', x[1]])

    return 'ebook-convert', [args], _('Fetch news from ')+recipe.title, fmt.upper(), [pt]


