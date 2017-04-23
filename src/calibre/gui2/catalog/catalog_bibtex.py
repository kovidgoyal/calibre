#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2 import gprefs
from calibre.gui2.catalog.catalog_bibtex_ui import Ui_Form
from PyQt5.Qt import QWidget, QListWidgetItem


class PluginWidget(QWidget, Ui_Form):

    TITLE = _('BibTeX options')
    HELP  = _('Options specific to')+' BibTeX '+_('output')
    OPTION_FIELDS = [('bib_cit','{authors}{id}'),
                     ('bib_entry', 0),  # mixed
                     ('bibfile_enc', 0),  # utf-8
                     ('bibfile_enctag', 0),  # strict
                     ('impcit', True),
                     ('addfiles', False),
                     ]

    sync_enabled = False
    formats = set(['bib'])

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)

    def initialize(self, name, db):  # not working properly to update
        from calibre.library.catalogs import FIELDS

        self.all_fields = [x for x in FIELDS if x != 'all']
        # add custom columns
        for x in sorted(db.custom_field_keys()):
            self.all_fields.append(x)
            if db.field_metadata[x]['datatype'] == 'series':
                self.all_fields.append(x+'_index')
        # populate
        for x in self.all_fields:
            QListWidgetItem(x, self.db_fields)

        self.name = name
        fields = gprefs.get(name+'_db_fields', self.all_fields)
        # Restore the activated db_fields from last use
        for x in xrange(self.db_fields.count()):
            item = self.db_fields.item(x)
            item.setSelected(unicode(item.text()) in fields)
        self.bibfile_enc.clear()
        self.bibfile_enc.addItems(['utf-8', 'cp1252', 'ascii/LaTeX'])
        self.bibfile_enctag.clear()
        self.bibfile_enctag.addItems(['strict', 'replace', 'ignore',
            'backslashreplace'])
        self.bib_entry.clear()
        self.bib_entry.addItems(['mixed', 'misc', 'book'])
        # Update dialog fields from stored options
        for opt in self.OPTION_FIELDS:
            opt_value = gprefs.get(self.name + '_' + opt[0], opt[1])
            if opt[0] in ['bibfile_enc', 'bibfile_enctag', 'bib_entry']:
                getattr(self, opt[0]).setCurrentIndex(opt_value)
            elif opt[0] in ['impcit', 'addfiles'] :
                getattr(self, opt[0]).setChecked(opt_value)
            else:
                getattr(self, opt[0]).setText(opt_value)

    def options(self):

        # Save the currently activated fields
        fields = []
        for x in xrange(self.db_fields.count()):
            item = self.db_fields.item(x)
            if item.isSelected():
                fields.append(unicode(item.text()))
        gprefs.set(self.name+'_db_fields', fields)

        # Dictionary currently activated fields
        if len(self.db_fields.selectedItems()):
            opts_dict = {'fields':[unicode(i.text()) for i in self.db_fields.selectedItems()]}
        else:
            opts_dict = {'fields':['all']}

        # Save/return the current options
        # bib_cit stores as text
        # 'bibfile_enc','bibfile_enctag' stores as int (Indexes)
        for opt in self.OPTION_FIELDS:
            if opt[0] in ['bibfile_enc', 'bibfile_enctag', 'bib_entry']:
                opt_value = getattr(self,opt[0]).currentIndex()
            elif opt[0] in ['impcit', 'addfiles'] :
                opt_value = getattr(self, opt[0]).isChecked()
            else :
                opt_value = unicode(getattr(self, opt[0]).text())
            gprefs.set(self.name + '_' + opt[0], opt_value)

            opts_dict[opt[0]] = opt_value

        return opts_dict
