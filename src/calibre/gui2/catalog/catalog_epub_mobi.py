#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2 import gprefs
from catalog_epub_mobi_ui import Ui_Form
from calibre.ebooks.conversion.config import load_defaults
from PyQt4.Qt import QWidget

class PluginWidget(QWidget,Ui_Form):

    TITLE = _('E-book options')
    HELP  = _('Options specific to')+' EPUB/MOBI '+_('output')
    OPTION_FIELDS = [('exclude_genre','\[[\w ]*\]'),
                     ('exclude_tags','~,'+_('Catalog')),
                     ('note_tag','*'),
                     ('numbers_as_text', False),
                     ('read_tag','+')]

    # Output synced to the connected device?
    sync_enabled = True

    # Formats supported by this plugin
    formats = set(['epub','mobi'])

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)

    def initialize(self, name):
        self.name = name
        # Update dialog fields from stored options
        for opt in self.OPTION_FIELDS:
            opt_value = gprefs.get(self.name + '_' + opt[0], opt[1])
            if opt[0] == 'numbers_as_text':
                getattr(self, opt[0]).setChecked(opt_value)
            else:
                getattr(self, opt[0]).setText(opt_value)

    def options(self):
        # Save/return the current options
        # exclude_genre stores literally
        # numbers_as_text stores as True/False
        # others store as lists
        opts_dict = {}
        for opt in self.OPTION_FIELDS:
            if opt[0] == 'numbers_as_text':
                opt_value = getattr(self,opt[0]).isChecked()
            else:
                opt_value = unicode(getattr(self, opt[0]).text())
            gprefs.set(self.name + '_' + opt[0], opt_value)
            if opt[0] == 'exclude_genre' or 'numbers_as_text':
                opts_dict[opt[0]] = opt_value
            else:
                opt_value = opt_value.split(',')
        opts_dict['output_profile'] = [load_defaults('page_setup')['output_profile']]


        return opts_dict
