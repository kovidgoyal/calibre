#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2 import gprefs
from calibre.gui2.catalog.catalog_csv_xml_ui import Ui_Form
from PyQt4.Qt import QDialog, QWidget, SIGNAL

class PluginWidget(QWidget,Ui_Form):

    TITLE = _('CSV/XML Output')
    HELP  = _('Options specific to')+' CSV/XML '+_('output')
    sync_enabled = False
    
    def initialize(self, name):
        QWidget.__init__(self)
        self.setupUi(self)
        self.name = name
        # Restore the activated fields from last use
        for x in range(self.db_fields.count()):        
            pref = '%s_db_fields_%s' % (self.name, self.db_fields.item(x).text())
            activated = gprefs[pref] if pref in gprefs else False
            self.db_fields.item(x).setSelected(activated)

    def options(self):
        # Save the currently activated fields
        for x in range(self.db_fields.count()):
            pref = '%s_db_fields_%s' % (self.name, self.db_fields.item(x).text())
            gprefs[pref] =  self.db_fields.item(x).isSelected()           
        
        # Return a dictionary with current options for this widget 
        if len(self.db_fields.selectedItems()):
            return {'fields':[str(item.text()) for item in self.db_fields.selectedItems()]}
        else:
            return {'fields':['all']}