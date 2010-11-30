#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


import os

from calibre.ebooks.conversion.config import load_defaults
from calibre.gui2 import gprefs
from calibre.library.database2 import LibraryDatabase2
from calibre.utils.config import prefs

from catalog_epub_mobi_ui import Ui_Form
from PyQt4 import QtGui
from PyQt4.Qt import QWidget

class PluginWidget(QWidget,Ui_Form):

    TITLE = _('E-book options')
    HELP  = _('Options specific to')+' EPUB/MOBI '+_('output')
    OPTION_FIELDS = [('exclude_genre','\[.+\]'),
                     ('exclude_tags','~,'+_('Catalog')),
                     ('generate_titles', True),
                     ('generate_series', True),
                     ('generate_recently_added', True),
                     ('note_tag','*'),
                     ('numbers_as_text', False),
                     ('read_pattern','+'),
                     ('read_source_field_cb','Tag'),
                     ('wishlist_tag','Wishlist'),
                     ]


    # Output synced to the connected device?
    sync_enabled = True

    # Formats supported by this plugin
    formats = set(['epub','mobi'])

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)

    def initialize(self, name):
        self.name = name

        # Populate the 'Read book' source fields
        dbpath = os.path.abspath(prefs['library_path'])
        db =  LibraryDatabase2(dbpath)
        all_custom_fields = db.custom_field_keys()
        custom_fields = {}
        custom_fields['Tag'] = {'field':'tag', 'datatype':u'text'}
        for custom_field in all_custom_fields:
            field_md = db.metadata_for_field(custom_field)
            if field_md['datatype'] in ['bool','composite','datetime','text']:
                custom_fields[field_md['name']] = {'field':custom_field,
                                                   'datatype':field_md['datatype']}

        # Add the sorted eligible fields to the combo box
        for cf in sorted(custom_fields):
            self.read_source_field_cb.addItem(cf)

        self.read_source_fields = custom_fields
        self.read_source_field_cb.currentIndexChanged.connect(self.read_source_field_changed)

        # Update dialog fields from stored options
        for opt in self.OPTION_FIELDS:
            opt_value = gprefs.get(self.name + '_' + opt[0], opt[1])
            if opt[0] in [
                          'generate_recently_added',
                          'generate_series',
                          'generate_titles',
                          'numbers_as_text',
                          ]:
                getattr(self, opt[0]).setChecked(opt_value)

            # Combo box
            elif opt[0] in ['read_source_field_cb']:
                # Look for last-stored combo box value
                index = self.read_source_field_cb.findText(opt_value)
                if index == -1:
                    index = self.read_source_field_cb.findText('Tag')
                self.read_source_field_cb.setCurrentIndex(index)

            # Text fields
            else:
                getattr(self, opt[0]).setText(opt_value)

        # Init self.read_source_field
        cs = str(self.read_source_field_cb.currentText())
        read_source_spec = self.read_source_fields[str(cs)]
        self.read_source_field = read_source_spec['field']

    def options(self):
        # Save/return the current options
        # exclude_genre stores literally
        # generate_titles, generate_recently_added, numbers_as_text stores as True/False
        # others store as lists
        opts_dict = {}
        for opt in self.OPTION_FIELDS:
            # Save values to gprefs
            if opt[0] in [
                          'generate_recently_added',
                          'generate_series',
                          'generate_titles',
                          'numbers_as_text',
                          ]:
                opt_value = getattr(self,opt[0]).isChecked()

            # Combo box uses .currentText()
            elif opt[0] in ['read_source_field_cb']:
                opt_value = unicode(getattr(self, opt[0]).currentText())

            # text fields use .text()
            else:
                opt_value = unicode(getattr(self, opt[0]).text())
            gprefs.set(self.name + '_' + opt[0], opt_value)

            # Construct opts
            if opt[0] in [
                          'exclude_genre',
                          'generate_recently_added',
                          'generate_series',
                          'generate_titles',
                          'numbers_as_text',
                          ]:
                opts_dict[opt[0]] = opt_value
            else:
                opts_dict[opt[0]] = opt_value.split(',')

        # Generate read_book_marker
        opts_dict['read_book_marker'] = "%s:%s" % (self.read_source_field, self.read_pattern.text())

        # Append the output profile
        opts_dict['output_profile'] = [load_defaults('page_setup')['output_profile']]
        return opts_dict

    def read_source_field_changed(self,new_index):
        '''
        Process changes in the read_source_field combo box
        Currently using QLineEdit for all field types
        Possible to modify to switch QWidget type
        '''
        new_source = str(self.read_source_field_cb.currentText())
        read_source_spec = self.read_source_fields[str(new_source)]
        self.read_source_field = read_source_spec['field']

        # Change pattern input widget to match the source field datatype
        if read_source_spec['datatype'] in ['bool','composite','datetime','text']:
            if  type(self.read_pattern) != type(QtGui.QLineEdit()):
                self.read_spec_hl.removeWidget(self.read_pattern)
                dw = QtGui.QLineEdit()
                dw.setObjectName('read_pattern')
                dw.setToolTip('Pattern for read book')
                self.read_pattern = dw
                self.read_spec_hl.addWidget(dw)

