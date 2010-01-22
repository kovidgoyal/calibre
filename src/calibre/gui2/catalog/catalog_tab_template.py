#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from <basename>  import Ui_Form
from PyQt4.Qt import QDialog, QWidget

class PluginWidget(QWidget,Ui_Form):

    TITLE = _('<formats> Output')
    HELP  = _('Options specific to')+' <formats> '+_('output')
    # Indicates whether this plugin wants its output synced to the connected device
    sync_enabled = False

    def initialize(self):
        QWidget.__init__(self)
        self.setupUi(self)

    def options(self):
        # Return a dictionary with options for this Widget
        return {}
