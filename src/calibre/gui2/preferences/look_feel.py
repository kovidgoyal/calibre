#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import (QApplication, QFont, QFontInfo, QFontDialog,
        QAbstractListModel, Qt, QColor)

from calibre.gui2.preferences import ConfigWidgetBase, test_widget, CommaSeparatedList
from calibre.gui2.preferences.look_feel_ui import Ui_Form
from calibre.gui2 import config, gprefs, qt_app
from calibre.utils.localization import (available_translations,
    get_language, get_lang)
from calibre.utils.config import prefs
from calibre.utils.icu import sort_key
from calibre.gui2 import NONE
from calibre.gui2.book_details import get_field_list

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

        r('cover_flow_queue_length', config, restart_required=True)

        lang = get_lang()
        if lang is None or lang not in available_translations():
            lang = 'en'
        items = [(l, get_language(l)) for l in available_translations() \
                 if l != lang]
        if lang != 'en':
            items.append(('en', get_language('en')))
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

        choices = [(_('Off'), 'off'), (_('Small'), 'small'),
            (_('Medium'), 'medium'), (_('Large'), 'large')]
        r('toolbar_icon_size', gprefs, choices=choices)

        choices = [(_('Automatic'), 'auto'), (_('Always'), 'always'),
            (_('Never'), 'never')]
        r('toolbar_text', gprefs, choices=choices)

        choices = [(_('Disabled'), 'disable'), (_('By first letter'), 'first letter'),
                   (_('Partitioned'), 'partition')]
        r('tags_browser_partition_method', gprefs, choices=choices)
        r('tags_browser_collapse_at', gprefs)

        choices = set([k for k in db.field_metadata.all_field_keys()
                if db.field_metadata[k]['is_category'] and
                   (db.field_metadata[k]['datatype'] in ['text', 'series', 'enumeration']) and
                   not db.field_metadata[k]['display'].get('is_names', False)])
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

        self.color_help_text.setText('<p>' +
                _('Here you can specify coloring rules for columns shown in the '
                  'library view. Choose the column you wish to color, then '
                  'supply a template that specifies the color to use based on '
                  'the values in the column. There is a '
                  '<a href="http://calibre-ebook.com/user_manual/template_lang.html">'
                  'tutorial</a> on using templates.') +
                 '</p><p>' +
                _('The template must evaluate to one of the color names shown '
                  'below. You can use any legal template expression. '
                  'For example, you can set the title to always display in '
                  'green using the template "green" (without the quotes). '
                  'To show the title in the color named in the custom column '
                  '#column, use "{#column}". To show the title in blue if the '
                  'custom column #column contains the value "foo", in red if the '
                  'column contains the value "bar", otherwise in black, use '
                  '<pre>{#column:switch(foo,blue,bar,red,black)}</pre>'
                  'To show the title in blue if the book has the exact tag '
                  '"Science Fiction", red if the book has the exact tag '
                  '"Mystery", or black if the book has neither tag, use'
                  "<pre>program: \n"
                  "    t = field('tags'); \n"
                  "    first_non_empty(\n"
                  "        in_list(t, ',', '^Science Fiction$', 'blue', ''), \n"
                  "        in_list(t, ',', '^Mystery$', 'red', 'black'))</pre>"
                  'To show the title in green if it has one format, blue if it '
                  'two formats, and red if more, use'
                  "<pre>program:cmp(count(field('formats'),','), 2, 'green', 'blue', 'red')</pre>") +
                               '</p><p>' +
                _('You can access a multi-line template editor from the '
                  'context menu (right-click).') + '</p><p>' +
                _('<b>Note:</b> if you want to color a "custom column with a fixed set '
                  'of values", it is often easier to specify the '
                  'colors in the column definition dialog. There you can '
                  'provide a color for each value without using a template.')+ '</p>')
        choices = db.field_metadata.displayable_field_keys()
        choices.sort(key=sort_key)
        choices.insert(0, '')
        self.column_color_count = db.column_color_count+1
        tags = db.all_tags()
        for i in range(1, self.column_color_count):
            r('column_color_name_'+str(i), db.prefs, choices=choices)
            r('column_color_template_'+str(i), db.prefs)
            temp = getattr(self, 'opt_column_color_template_'+str(i))
            temp.set_tags(tags)
        all_colors = [unicode(s) for s in list(QColor.colorNames())]
        self.colors_box.setText(', '.join(all_colors))

    def initialize(self):
        ConfigWidgetBase.initialize(self)
        font = gprefs['font']
        if font is not None:
            font = list(font)
            font.append(gprefs.get('font_stretch', QFont.Unstretched))
        self.current_font = self.initial_font = font
        self.update_font_display()
        self.display_model.initialize()

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        ofont = self.current_font
        self.current_font = None
        if ofont is not None:
            self.changed_signal.emit()
            self.update_font_display()
        self.display_model.restore_defaults()
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
        for i in range(1, self.column_color_count):
            col = getattr(self, 'opt_column_color_name_'+str(i))
            tpl = getattr(self, 'opt_column_color_template_'+str(i))
            if not col.currentIndex() or not unicode(tpl.text()).strip():
                col.setCurrentIndex(0)
                tpl.setText('')
        rr = ConfigWidgetBase.commit(self, *args)
        if self.current_font != self.initial_font:
            gprefs['font'] = (self.current_font[:4] if self.current_font else
                    None)
            gprefs['font_stretch'] = (self.current_font[4] if self.current_font
                    is not None else QFont.Unstretched)
            QApplication.setFont(self.font_display.font())
            rr = True
        self.display_model.commit()
        return rr

    def refresh_gui(self, gui):
        gui.library_view.model().set_color_templates()
        self.update_font_display()
        gui.tags_view.reread_collapse_parameters()
        gui.library_view.refresh_book_details()

if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    test_widget('Interface', 'Look & Feel')

