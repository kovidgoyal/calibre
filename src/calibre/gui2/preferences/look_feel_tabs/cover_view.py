#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from qt.core import QKeySequence

from calibre.gui2 import config, gprefs
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.preferences import ConfigTabWidget, ConfigWidgetBase, set_help_tips
from calibre.gui2.preferences.look_feel_tabs.cover_view_ui import Ui_Form


class CoverView(ConfigTabWidget, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        db = gui.library_view.model().db
        r = self.register

        r('books_autoscroll_time', gprefs)
        r('cover_flow_queue_length', config, restart_required=True)
        r('cover_browser_reflections', gprefs)
        r('cover_browser_narrow_view_position', gprefs,
                            choices=[(_('Automatic'), 'automatic'), # Automatic must be first
                                     (_('On top'), 'on_top'),
                                     (_('On right'), 'on_right')])
        r('cover_browser_title_template', db.prefs)
        fm = db.field_metadata
        r('cover_browser_subtitle_field', db.prefs, choices=[(_('No subtitle'), 'none')] + sorted(
            (fm[k].get('name'), k) for k in fm.all_field_keys() if fm[k].get('name')
        ))
        self.cover_browser_title_template_button.clicked.connect(self.edit_cb_title_template)
        r('separate_cover_flow', config, restart_required=True)
        r('cb_fullscreen', gprefs)
        r('cb_preserve_aspect_ratio', gprefs)
        r('cb_double_click_to_activate', gprefs)
        self.fs_help_msg.setText(self.fs_help_msg.text()%(
            QKeySequence(QKeySequence.StandardKey.FullScreen).toString(QKeySequence.SequenceFormat.NativeText)))

    def initialize(self):
        ConfigWidgetBase.initialize(self)
        set_help_tips(self.opt_cover_browser_narrow_view_position, _(
            'This option controls the position of the cover browser when using the Narrow user '
            'interface layout.  "Automatic" will place the cover browser on top or on the right '
            'of the book list depending on the aspect ratio of the calibre window. "On top" '
            'places it over the book list, and "On right" places it to the right of the book '
            'list. This option has no effect when using the Wide user interface layout.'))

    def edit_cb_title_template(self):
        t = TemplateDialog(self, self.opt_cover_browser_title_template.text(), fm=self.gui.current_db.field_metadata)
        t.setWindowTitle(_('Edit template for caption'))
        if t.exec():
            self.opt_cover_browser_title_template.setText(t.rule[1])

    def refresh_gui(self, gui):
        gui.cover_flow.setShowReflections(gprefs['cover_browser_reflections'])
        gui.cover_flow.setPreserveAspectRatio(gprefs['cb_preserve_aspect_ratio'])
        gui.cover_flow.setActivateOnDoubleClick(gprefs['cb_double_click_to_activate'])
        gui.update_cover_flow_subtitle_font()
        gui.cover_flow.template_inited = False
