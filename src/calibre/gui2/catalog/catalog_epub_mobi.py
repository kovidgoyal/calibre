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

    TITLE = _('EPUB/MOBI Options')
    HELP  = _('Options specific to')+' EPUB/MOBI '+_('output')
    OPTION_FIELDS = [('exclude_genre','\[[\w ]*\]'),
                     ('exclude_tags','~'),
                     ('read_tag','+'),
                     ('note_tag','*')]

    # Output synced to the connected device?
    sync_enabled = True
    
    # Formats supported by this plugin
    formats = set(['epub','mobi'])
    
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)

    def initialize(self, name):
        self.name = name
        # Restore options from last use here
        print "gui2.catalog.catalog_epub_mobi:initialize(): Retrieving options"
        for opt in self.OPTION_FIELDS:
            opt_value = gprefs[self.name + '_' + opt[0]]
            print "Restoring %s: %s" % (self.name + '_' + opt[0], opt_value)
            setattr(self,opt[0], unicode(opt_value))

    def options(self):

        # Save/return the current options
        # getattr() returns text value of QLineEdit control
        print "gui2.catalog.catalog_epub_mobi:options(): Saving options"
        opts_dict = {}
        for opt in self.OPTION_FIELDS:
            opt_value = unicode(getattr(self,opt[0]))
            print "writing %s to gprefs" % opt_value
            gprefs.set(self.name + '_' + opt[0], opt_value)
            opts_dict[opt[0]] = opt_value.split(',')

        opts_dict['output_profile'] = [load_defaults('page_setup')['output_profile']]


        return opts_dict
