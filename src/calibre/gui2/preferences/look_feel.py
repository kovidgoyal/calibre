#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import (QApplication, QFont, QFontInfo, QFontDialog,
        QAbstractListModel, Qt, QIcon, QKeySequence)

from calibre.gui2.preferences import ConfigWidgetBase, test_widget, CommaSeparatedList
from calibre.gui2.preferences.look_feel_ui import Ui_Form
from calibre.gui2 import config, gprefs, qt_app, NONE
from calibre.utils.localization import (available_translations,
    get_language, get_lang)
from calibre.utils.config import prefs
from calibre.utils.icu import sort_key
from calibre.gui2.book_details import get_field_list
from calibre.gui2.preferences.coloring import EditRules

class DisplayedFields(QAbstractListModel): # {{{

    def __init__(self, db, parent=None):
        QAbstractListModel.__init__(self, parent)

        self.fields = []
        self.db = db
        self.changed = False

    def initialize(self, use_defaults=False):
        self.fields = [[x[0], x[1]] for x in
                get_field_list(self.db.field_metadata,
                    use_defaults=use_defaults)]
        self.reset()
        self.changed = True

    def rowCount(self, *args):
        return len(self.fields)

    def data(self, index, role):
        try:
            field, visible = self.fields[index.row()]
        except:
            return NONE
        if role == Qt.DisplayRole:
            name = field
            try:
                name = self.db.field_metadata[field]['name']
            except:
                pass
            if not name:
                name = field
            return name
        if role == Qt.CheckStateRole:
            return Qt.Checked if visible else Qt.Unchecked
        return NONE

    def flags(self, index):
        ans = QAbstractListModel.flags(self, index)
        return ans | Qt.ItemIsUserCheckable

    def setData(self, index, val, role):
        ret = False
        if role == Qt.CheckStateRole:
            val, ok = val.toInt()
            if ok:
                self.fields[index.row()][1] = bool(val)
                self.changed = True
                ret = True
                self.dataChanged.emit(index, index)
        return ret

    def restore_defaults(self):
        self.initialize(use_defaults=True)

    def commit(self):
        if self.changed:
            gprefs['book_display_fields'] = self.fields

    def move(self, idx, delta):
        row = idx.row() + delta
        if row >= 0 and row < len(self.fields):
            t = self.fields[row]
            self.fields[row] = self.fields[row-delta]
            self.fields[row-delta] = t
            self.dataChanged.emit(idx, idx)
            idx = self.index(row)
            self.dataChanged.emit(idx, idx)
            self.changed = True
            return idx

# }}}

class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        db = gui.library_view.model().db

        r = self.register

        r('gui_layout', config, restart_required=True, choices=
                [(_('Wide'), 'wide'), (_('Narrow'), 'narrow')])
        r('widget_style', gprefs, restart_required=True, choices=
                [(_('System default'), 'system'), (_('Calibre style'),
                    'calibre')])

        r('cover_flow_queue_length', config, restart_required=True)

        def get_esc_lang(l):
            if l == 'en':
                return 'English'
            return get_language(l)

        lang = get_lang()
        if lang is None or lang not in available_translations():
            lang = 'en'
        items = [(l, get_esc_lang(l)) for l in available_translations() \
                 if l != lang]
        if lang != 'en':
            items.append(('en', get_esc_lang('en')))
        items.sort(cmp=lambda x, y: cmp(x[1].lower(), y[1].lower()))
        choices = [(y, x) for x, y in items]
        # Default language is the autodetected one
        choices = [(get_language(lang), lang)] + choices
        r('language', prefs, choices=choices, restart_required=True)

        r('show_avg_rating', config)
        r('disable_animations', config)
        r('systray_icon', config, restart_required=True)
        r('show_splash_screen', gprefs)
        r('disable_tray_notification', config)
        r('use_roman_numerals_for_series_number', config)
        r('separate_cover_flow', config, restart_required=True)
        r('cb_fullscreen', gprefs)

        choices = [(_('Off'), 'off'), (_('Small'), 'small'),
            (_('Medium'), 'medium'), (_('Large'), 'large')]
        r('toolbar_icon_size', gprefs, choices=choices)

        choices = [(_('If there is enough room'), 'auto'), (_('Always'), 'always'),
            (_('Never'), 'never')]
        r('toolbar_text', gprefs, choices=choices)

        choices = [(_('Disabled'), 'disable'), (_('By first letter'), 'first letter'),
                   (_('Partitioned'), 'partition')]
        r('tags_browser_partition_method', gprefs, choices=choices)
        r('tags_browser_collapse_at', gprefs)
        r('default_author_link', gprefs)
        r('tag_browser_dont_collapse', gprefs, setting=CommaSeparatedList)

        choices = set([k for k in db.field_metadata.all_field_keys()
                if (db.field_metadata[k]['is_category'] and
                   (db.field_metadata[k]['datatype'] in ['text', 'series', 'enumeration']) and
                    not db.field_metadata[k]['display'].get('is_names', False))
                  or
                   (db.field_metadata[k]['datatype'] in ['composite'] and
                    db.field_metadata[k]['display'].get('make_category', False))])
        choices -= set(['authors', 'publisher', 'formats', 'news', 'identifiers'])
        choices |= set(['search'])
        self.opt_categories_using_hierarchy.update_items_cache(choices)
        r('categories_using_hierarchy', db.prefs, setting=CommaSeparatedList,
          choices=sorted(list(choices), key=sort_key))


        self.current_font = self.initial_font = None
        self.change_font_button.clicked.connect(self.change_font)

        self.display_model = DisplayedFields(self.gui.current_db,
                self.field_display_order)
        self.display_model.dataChanged.connect(self.changed_signal)
        self.field_display_order.setModel(self.display_model)
        self.df_up_button.clicked.connect(self.move_df_up)
        self.df_down_button.clicked.connect(self.move_df_down)

        self.edit_rules = EditRules(self.tabWidget)
        self.edit_rules.changed.connect(self.changed_signal)
        self.tabWidget.addTab(self.edit_rules,
                QIcon(I('format-fill-color.png')), _('Column coloring'))
        self.tabWidget.setCurrentIndex(0)
        keys = [QKeySequence('F11', QKeySequence.PortableText), QKeySequence(
            'Ctrl+Shift+F', QKeySequence.PortableText)]
        keys = [unicode(x.toString(QKeySequence.NativeText)) for x in keys]
        self.fs_help_msg.setText(unicode(self.fs_help_msg.text())%(
            _(' or ').join(keys)))

    def initialize(self):
        ConfigWidgetBase.initialize(self)
        font = gprefs['font']
        if font is not None:
            font = list(font)
            font.append(gprefs.get('font_stretch', QFont.Unstretched))
        self.current_font = self.initial_font = font
        self.update_font_display()
        self.display_model.initialize()
        db = self.gui.current_db
        try:
            idx = self.gui.library_view.currentIndex().row()
            mi = db.get_metadata(idx, index_is_id=False)
        except:
            mi=None
        self.edit_rules.initialize(db.field_metadata, db.prefs, mi)

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        ofont = self.current_font
        self.current_font = None
        if ofont is not None:
            self.changed_signal.emit()
            self.update_font_display()
        self.display_model.restore_defaults()
        self.edit_rules.clear()
        self.changed_signal.emit()

    def build_font_obj(self):
        font_info = self.current_font
        if font_info is not None:
            font = QFont(*(font_info[:4]))
            font.setStretch(font_info[4])
        else:
            font = qt_app.original_font
        return font

    def update_font_display(self):
        font = self.build_font_obj()
        fi = QFontInfo(font)
        name = unicode(fi.family())

        self.font_display.setFont(font)
        self.font_display.setText(name +
                ' [%dpt]'%fi.pointSize())

    def move_df_up(self):
        idx = self.field_display_order.currentIndex()
        if idx.isValid():
            idx = self.display_model.move(idx, -1)
            if idx is not None:
                sm = self.field_display_order.selectionModel()
                sm.select(idx, sm.ClearAndSelect)
                self.field_display_order.setCurrentIndex(idx)

    def move_df_down(self):
        idx = self.field_display_order.currentIndex()
        if idx.isValid():
            idx = self.display_model.move(idx, 1)
            if idx is not None:
                sm = self.field_display_order.selectionModel()
                sm.select(idx, sm.ClearAndSelect)
                self.field_display_order.setCurrentIndex(idx)

    def change_font(self, *args):
        fd = QFontDialog(self.build_font_obj(), self)
        if fd.exec_() == fd.Accepted:
            font = fd.selectedFont()
            fi = QFontInfo(font)
            self.current_font = [unicode(fi.family()), fi.pointSize(),
                    fi.weight(), fi.italic(), font.stretch()]
            self.update_font_display()
            self.changed_signal.emit()

    def commit(self, *args):
        rr = ConfigWidgetBase.commit(self, *args)
        if self.current_font != self.initial_font:
            gprefs['font'] = (self.current_font[:4] if self.current_font else
                    None)
            gprefs['font_stretch'] = (self.current_font[4] if self.current_font
                    is not None else QFont.Unstretched)
            QApplication.setFont(self.font_display.font())
            rr = True
        self.display_model.commit()
        self.edit_rules.commit(self.gui.current_db.prefs)
        return rr

    def refresh_gui(self, gui):
        gui.library_view.model().reset()
        self.update_font_display()
        gui.tags_view.reread_collapse_parameters()
        gui.library_view.refresh_book_details()

if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    test_widget('Interface', 'Look & Feel')

