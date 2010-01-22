#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2 import gprefs
from catalog_epub_mobi_ui import Ui_Form
from PyQt4.Qt import QWidget

class PluginWidget(QWidget,Ui_Form):

    TITLE = _('EPUB/MOBI Options')
    HELP  = _('Options specific to')+' EPUB/MOBI '+_('output')
    # Indicates whether this plugin wants its output synced to the connected device
    sync_enabled = True
    formats = set(['epub','mobi'])
    
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)

    def initialize(self, name):
        self.name = name
        # Restore options from last use here
        print "gui2.catalog.catalog_epub_mobi:initialize(): need to restore options"
        
    def options(self):
        OPTION_FIELDS = ['exclude_genre','exclude_tags','read_tag','note_tag','output_profile']

        # Save the current options
        print "gui2.catalog.catalog_epub_mobi:options(): need to save options"
        
        # Return a dictionary with current options
        print "gui2.catalog.catalog_epub_mobi:options(): need to return options"
        print "gui2.catalog.catalog_epub_mobi:options(): using hard-coded options"
        
        opts_dict = {}
        for opt in OPTION_FIELDS:
            opts_dict[opt] = str(getattr(self,opt).text()).split(',')

        return opts_dict
