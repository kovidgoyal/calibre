#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QApplication

from calibre.gui2.preferences import ConfigWidgetBase, test_widget, \
        CommaSeparatedList
from calibre.gui2.preferences.search_ui import Ui_Form
from calibre.gui2 import config
from calibre.utils.config import prefs

class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui

        r = self.register

        r('search_as_you_type', config)
        r('highlight_search_matches', config)
        r('limit_search_columns', prefs)
        r('limit_search_columns_to', prefs, setting=CommaSeparatedList)
        fl = gui.library_view.model().db.field_metadata.get_search_terms()
        self.opt_limit_search_columns_to.update_items_cache(fl)
        self.clear_history_button.clicked.connect(self.clear_histories)

    def refresh_gui(self, gui):
        gui.search.search_as_you_type(config['search_as_you_type'])
        gui.library_view.model().set_highlight_only(config['highlight_search_matches'])
        gui.search.do_search()

    def clear_histories(self, *args):
        for key, val in config.defaults.iteritems():
            if key.endswith('_search_history') and isinstance(val, list):
                config[key] = []
        self.gui.search.clear_history()

if __name__ == '__main__':
    app = QApplication([])
    test_widget('Interface', 'Search')

