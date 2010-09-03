#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.preferences import ConfigWidgetBase, test_widget, \
    CommaSeparatedList
from calibre.gui2.preferences.behavior_ui import Ui_Form
from calibre.gui2 import config, info_dialog, dynamic
from calibre.utils.config import prefs
from calibre.customize.ui import available_output_formats
from calibre.utils.search_query_parser import saved_searches

class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        db = gui.library_view.model().db

        r = self.register

        r('worker_process_priority', prefs, choices=
                [(_('Low'), 'low'), (_('Normal'), 'normal'), (_('High'), 'high')])

        r('network_timeout', prefs)


        r('overwrite_author_title_metadata', config)
        r('get_social_metadata', config)
        r('new_version_notification', config)
        r('upload_news_to_device', config)
        r('delete_news_from_library_on_upload', config)

        output_formats = list(sorted(available_output_formats()))
        output_formats.remove('oeb')
        choices = [(x.upper(), x) for x in output_formats]
        r('output_format', prefs, choices=choices)

        restrictions = sorted(saved_searches().names(),
                              cmp=lambda x,y: cmp(x.lower(), y.lower()))
        choices = [('', '')] + [(x, x) for x in restrictions]
        r('gui_restriction', db.prefs, choices=choices)
        r('new_book_tags', prefs, setting=CommaSeparatedList)
        self.reset_confirmation_button.clicked.connect(self.reset_confirmation_dialogs)

    def reset_confirmation_dialogs(self, *args):
        for key in dynamic.keys():
            if key.endswith('_again') and dynamic[key] is False:
                dynamic[key] = True
        info_dialog(self, _('Done'),
                _('Confirmation dialogs have all been reset'), show=True)

if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    test_widget('Interface', 'Behavior')

