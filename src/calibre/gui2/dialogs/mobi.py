#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

from calibre.gui2.dialogs.epub import Config as _Config
from calibre.ebooks.mobi.from_any import config as mobiconfig

class Config(_Config):
    
    OUTPUT = 'MOBI'
    
    def __init__(self, parent, db, row=None):
        _Config.__init__(self, parent, db, row=row, config=mobiconfig)
        
    def hide_controls(self):
        self.profile_label.setVisible(False)
        self.opt_profile.setVisible(False)
        self.opt_dont_split_on_page_breaks.setVisible(False)
        self.opt_preserve_tag_structure.setVisible(False)