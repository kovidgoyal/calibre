#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json

from collections import defaultdict
from threading import Thread
from functools import partial

from PyQt5.Qt import (
    QApplication, QFont, QFontInfo, QFontDialog, QColorDialog, QPainter,
    QAbstractListModel, Qt, QIcon, QKeySequence, QColor, pyqtSignal, QCursor,
    QWidget, QSizePolicy, QBrush, QPixmap, QSize, QPushButton, QVBoxLayout,
    QTableWidget, QTableWidgetItem, QLabel, QFormLayout, QLineEdit
)

from calibre import human_readable
from calibre.ebooks.metadata.sources.prefs import msprefs
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.preferences import ConfigWidgetBase, test_widget, CommaSeparatedList
from calibre.gui2.preferences.look_feel_ui import Ui_Form
from calibre.gui2 import config, gprefs, qt_app, open_local_file, question_dialog, error_dialog
from calibre.utils.localization import (available_translations,
    get_language, get_lang)
from calibre.utils.config import prefs
from calibre.utils.icu import sort_key
from calibre.gui2.book_details import get_field_list
from calibre.gui2.preferences.coloring import EditRules
from calibre.gui2.library.alternate_views import auto_height, CM_TO_INCH
from calibre.gui2.widgets2 import Dialog


class BusyCursor(object):

    def __enter__(self):
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

    def __exit__(self, *args):
        QApplication.restoreOverrideCursor()

# IdLinksEditor {{{


class IdLinksRuleEdit(Dialog):

    def __init__(self, key='', name='', template='', parent=None):
        title = _('Edit rule') if key else _('Create a new rule')
        Dialog.__init__(self, title=title, name='id-links-rule-editor', parent=parent)
        self.key.setText(key), self.nw.setText(name), self.template.setText(template or 'http://example.com/{id}')

    @property
    def rule(self):
        return self.key.text().lower(), self.nw.text(), self.template.text()

    def setup_ui(self):
        self.l = l = QFormLayout(self)
        l.setFieldGrowthPolicy(l.AllNonFixedFieldsGrow)
        l.addRow(QLabel(_(
            'The key of the identifier, for example, in isbn:XXX, the key is isbn')))
        self.key = k = QLineEdit(self)
        l.addRow(_('&Key:'), k)
        l.addRow(QLabel(_(
            'The name that will appear in the book details panel')))
        self.nw = n = QLineEdit(self)
        l.addRow(_('&Name:'), n)
        la = QLabel(_(
            'The template used to create the link. The placeholder {id} in the template will be replaced with the actual identifier value.'))
        la.setWordWrap(True)
        l.addRow(la)
        self.template = t = QLineEdit(self)
        l.addRow(_('&Template:'), t)
        t.selectAll()
        t.setFocus(Qt.OtherFocusReason)
        l.addWidget(self.bb)

    def accept(self):
        r = self.rule
        for i, which in enumerate([_('Key'), _('Name'), _('Template')]):
            if not r[i]:
                return error_dialog(self, _('Value needed'), _(
                    'The %s field cannot be empty') % which, show=True)
        Dialog.accept(self)


class IdLinksEditor(Dialog):

    def __init__(self, parent=None):
        Dialog.__init__(self, title=_('Create rules for identifiers'), name='id-links-rules-editor', parent=parent)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(_(
            'Create rules to convert identifiers into links.'))
        la.setWordWrap(True)
        l.addWidget(la)
        items = []
        for k, lx in msprefs['id_link_rules'].iteritems():
            for n, t in lx:
                items.append((k, n, t))
        items.sort(key=lambda x:sort_key(x[1]))
        self.table = t = QTableWidget(len(items), 3, self)
        t.setHorizontalHeaderLabels([_('Key'), _('Name'), _('Template')])
        for r, (key, val, template) in enumerate(items):
            t.setItem(r, 0, QTableWidgetItem(key))
            t.setItem(r, 1, QTableWidgetItem(val))
            t.setItem(r, 2, QTableWidgetItem(template))
        l.addWidget(t)
        t.horizontalHeader().setSectionResizeMode(2, t.horizontalHeader().Stretch)
        self.cb = b = QPushButton(QIcon(I('plus.png')), _('&Add rule'), self)
        b.clicked.connect(lambda : self.edit_rule())
        self.bb.addButton(b, self.bb.ActionRole)
        self.rb = b = QPushButton(QIcon(I('minus.png')), _('&Remove rule'), self)
        b.clicked.connect(lambda : self.remove_rule())
        self.bb.addButton(b, self.bb.ActionRole)
        self.eb = b = QPushButton(QIcon(I('modified.png')), _('&Edit rule'), self)
        b.clicked.connect(lambda : self.edit_rule(self.table.currentRow()))
        self.bb.addButton(b, self.bb.ActionRole)
        l.addWidget(self.bb)

    def sizeHint(self):
        return QSize(700, 550)

    def accept(self):
        rules = defaultdict(list)
        for r in range(self.table.rowCount()):
            def item(c):
                return self.table.item(r, c).text()
            rules[item(0)].append([item(1), item(2)])
        msprefs['id_link_rules'] = dict(rules)
        Dialog.accept(self)

    def edit_rule(self, r=-1):
        key = name = template = ''
        if r > -1:
            key, name, template = map(lambda c: self.table.item(r, c).text(), range(3))
        d = IdLinksRuleEdit(key, name, template, self)
        if d.exec_() == d.Accepted:
            if r < 0:
                self.table.setRowCount(self.table.rowCount() + 1)
                r = self.table.rowCount() - 1
            rule = d.rule
            for c in range(3):
                self.table.setItem(r, c, QTableWidgetItem(rule[c]))
            self.table.scrollToItem(self.table.item(r, 0))

    def remove_rule(self):
        r = self.table.currentRow()
        if r > -1:
            self.table.removeRow(r)
# }}}


class DisplayedFields(QAbstractListModel):  # {{{

    def __init__(self, db, parent=None):
        QAbstractListModel.__init__(self, parent)

        self.fields = []
        self.db = db
        self.changed = False

    def initialize(self, use_defaults=False):
        self.beginResetModel()
        self.fields = [[x[0], x[1]] for x in
                get_field_list(self.db.field_metadata,
                    use_defaults=use_defaults)]
        self.endResetModel()
        self.changed = True

    def rowCount(self, *args):
        return len(self.fields)

    def data(self, index, role):
        try:
            field, visible = self.fields[index.row()]
        except:
            return None
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
        if role == Qt.DecorationRole and field.startswith('#'):
            return QIcon(I('column.png'))
        return None

    def flags(self, index):
        ans = QAbstractListModel.flags(self, index)
        return ans | Qt.ItemIsUserCheckable

    def setData(self, index, val, role):
        ret = False
        if role == Qt.CheckStateRole:
            self.fields[index.row()][1] = bool(val)
            self.changed = True
            ret = True
            self.dataChanged.emit(index, index)
        return ret

    def restore_defaults(self):
        self.initialize(use_defaults=True)

    def commit(self):
        if self.changed:
            self.db.new_api.set_pref('book_display_fields', self.fields)

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


class Background(QWidget):  # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.bcol = QColor(*gprefs['cover_grid_color'])
        self.btex = gprefs['cover_grid_texture']
        self.update_brush()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def update_brush(self):
        self.brush = QBrush(self.bcol)
        if self.btex:
            from calibre.gui2.preferences.texture_chooser import texture_path
            path = texture_path(self.btex)
            if path:
                p = QPixmap(path)
                try:
                    dpr = self.devicePixelRatioF()
                except AttributeError:
                    dpr = self.devicePixelRatio()
                p.setDevicePixelRatio(dpr)
                self.brush.setTexture(p)
        self.update()

    def sizeHint(self):
        return QSize(200, 120)

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.fillRect(ev.rect(), self.brush)
        painter.end()
# }}}


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    size_calculated = pyqtSignal(object)

    def genesis(self, gui):
        self.gui = gui
        db = gui.library_view.model().db

        r = self.register

        try:
            self.icon_theme_title = json.loads(I('icon-theme.json', data=True))['name']
        except Exception:
            self.icon_theme_title = _('Default icons')
        self.icon_theme.setText(_('Icon theme: <b>%s</b>') % self.icon_theme_title)
        self.commit_icon_theme = None
        self.icon_theme_button.clicked.connect(self.choose_icon_theme)
        r('gui_layout', config, restart_required=True, choices=[(_('Wide'), 'wide'), (_('Narrow'), 'narrow')])
        r('ui_style', gprefs, restart_required=True, choices=[(_('System default'), 'system'), (_('Calibre style'),
                    'calibre')])
        r('book_list_tooltips', gprefs)
        r('row_numbers_in_book_list', gprefs)
        r('tag_browser_old_look', gprefs, restart_required=True)
        r('tag_browser_hide_empty_categories', gprefs)
        r('bd_show_cover', gprefs)
        r('bd_overlay_cover_size', gprefs)
        r('cover_grid_width', gprefs)
        r('cover_grid_height', gprefs)
        r('cover_grid_cache_size_multiple', gprefs)
        r('cover_grid_disk_cache_size', gprefs)
        r('cover_grid_spacing', gprefs)
        r('cover_grid_show_title', gprefs)
        r('tag_browser_show_counts', gprefs)

        r('cover_flow_queue_length', config, restart_required=True)
        r('cover_browser_reflections', gprefs)
        r('cover_browser_title_template', db.prefs)
        fm = db.field_metadata
        r('cover_browser_subtitle_field', db.prefs, choices=[(_('No subtitle'), 'none')] + sorted(
            (fm[k].get('name'), k) for k in fm.all_field_keys() if fm[k].get('name')
        ))
        r('emblem_size', gprefs)
        r('emblem_position', gprefs, choices=[
            (_('Left'), 'left'), (_('Top'), 'top'), (_('Right'), 'right'), (_('Bottom'), 'bottom')])
        r('book_list_extra_row_spacing', gprefs)
        self.cover_browser_title_template_button.clicked.connect(self.edit_cb_title_template)
        self.id_links_button.clicked.connect(self.edit_id_link_rules)

        def get_esc_lang(l):
            if l == 'en':
                return 'English'
            return get_language(l)

        lang = get_lang()
        if lang is None or lang not in available_translations():
            lang = 'en'
        items = [(l, get_esc_lang(l)) for l in available_translations()
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
        r('cb_preserve_aspect_ratio', gprefs)

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

        self.search_library_for_author_button.clicked.connect(
            lambda : self.opt_default_author_link.setText('search-calibre'))

        choices = set([k for k in db.field_metadata.all_field_keys()
                if (db.field_metadata[k]['is_category'] and
                   (db.field_metadata[k]['datatype'] in ['text', 'series', 'enumeration']) and
                    not db.field_metadata[k]['display'].get('is_names', False)) or
                   (db.field_metadata[k]['datatype'] in ['composite'] and
                    db.field_metadata[k]['display'].get('make_category', False))])
        choices -= set(['authors', 'publisher', 'formats', 'news', 'identifiers'])
        choices |= set(['search'])
        self.opt_categories_using_hierarchy.update_items_cache(choices)
        r('categories_using_hierarchy', db.prefs, setting=CommaSeparatedList,
          choices=sorted(list(choices), key=sort_key))

        fm = db.field_metadata
        choices = sorted(((fm[k]['name'], k) for k in fm.displayable_field_keys() if fm[k]['name']),
                         key=lambda x:sort_key(x[0]))
        r('field_under_covers_in_grid', db.prefs, choices=choices)

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

        self.icon_rules = EditRules(self.tabWidget)
        self.icon_rules.changed.connect(self.changed_signal)
        self.tabWidget.addTab(self.icon_rules,
                QIcon(I('icon_choose.png')), _('Column icons'))

        self.grid_rules = EditRules(self.emblems_tab)
        self.grid_rules.changed.connect(self.changed_signal)
        self.emblems_tab.setLayout(QVBoxLayout())
        self.emblems_tab.layout().addWidget(self.grid_rules)

        self.tabWidget.setCurrentIndex(0)
        keys = [QKeySequence('F11', QKeySequence.PortableText), QKeySequence(
            'Ctrl+Shift+F', QKeySequence.PortableText)]
        keys = [unicode(x.toString(QKeySequence.NativeText)) for x in keys]
        self.fs_help_msg.setText(unicode(self.fs_help_msg.text())%(
            _(' or ').join(keys)))
        self.size_calculated.connect(self.update_cg_cache_size, type=Qt.QueuedConnection)
        self.tabWidget.currentChanged.connect(self.tab_changed)

        l = self.cg_background_box.layout()
        self.cg_bg_widget = w = Background(self)
        l.addWidget(w, 0, 0, 3, 1)
        self.cover_grid_color_button = b = QPushButton(_('Change &color'), self)
        b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        l.addWidget(b, 0, 1)
        b.clicked.connect(self.change_cover_grid_color)
        self.cover_grid_texture_button = b = QPushButton(_('Change &background image'), self)
        b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        l.addWidget(b, 1, 1)
        b.clicked.connect(self.change_cover_grid_texture)
        self.cover_grid_default_appearance_button = b = QPushButton(_('Restore &default appearance'), self)
        b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        l.addWidget(b, 2, 1)
        b.clicked.connect(self.restore_cover_grid_appearance)
        self.cover_grid_empty_cache.clicked.connect(self.empty_cache)
        self.cover_grid_open_cache.clicked.connect(self.open_cg_cache)
        self.cover_grid_smaller_cover.clicked.connect(partial(self.resize_cover, True))
        self.cover_grid_larger_cover.clicked.connect(partial(self.resize_cover, False))
        self.cover_grid_reset_size.clicked.connect(self.cg_reset_size)
        self.opt_cover_grid_disk_cache_size.setMinimum(self.gui.grid_view.thumbnail_cache.min_disk_cache)
        self.opt_cover_grid_disk_cache_size.setMaximum(self.gui.grid_view.thumbnail_cache.min_disk_cache * 100)
        self.opt_cover_grid_width.valueChanged.connect(self.update_aspect_ratio)
        self.opt_cover_grid_height.valueChanged.connect(self.update_aspect_ratio)

    def choose_icon_theme(self):
        from calibre.gui2.icon_theme import ChooseTheme
        d = ChooseTheme(self)
        if d.exec_() == d.Accepted:
            self.commit_icon_theme = d.commit_changes
            self.icon_theme_title = d.new_theme_title or _('Default icons')
            self.icon_theme.setText(_('Icon theme: <b>%s</b>') % self.icon_theme_title)
            self.changed_signal.emit()

    def edit_id_link_rules(self):
        if IdLinksEditor(self).exec_() == Dialog.Accepted:
            self.changed_signal.emit()

    @property
    def current_cover_size(self):
        cval = self.opt_cover_grid_height.value()
        wval = self.opt_cover_grid_width.value()
        if cval < 0.1:
            dpi = self.opt_cover_grid_height.logicalDpiY()
            cval = auto_height(self.opt_cover_grid_height) / dpi / CM_TO_INCH
        if wval < 0.1:
            wval = 0.75 * cval
        return wval, cval

    def update_aspect_ratio(self, *args):
        width, height = self.current_cover_size
        ar = width / height
        self.cover_grid_aspect_ratio.setText(_('Current aspect ratio (width/height): %.2g') % ar)

    def resize_cover(self, smaller):
        wval, cval = self.current_cover_size
        ar = wval / cval
        delta = 0.2 * (-1 if smaller else 1)
        cval += delta
        cval = max(0, cval)
        self.opt_cover_grid_height.setValue(cval)
        self.opt_cover_grid_width.setValue(cval * ar)

    def cg_reset_size(self):
        self.opt_cover_grid_width.setValue(0)
        self.opt_cover_grid_height.setValue(0)

    def edit_cb_title_template(self):
        t = TemplateDialog(self, self.opt_cover_browser_title_template.text(), fm=self.gui.current_db.field_metadata)
        t.setWindowTitle(_('Edit template for caption'))
        if t.exec_():
            self.opt_cover_browser_title_template.setText(t.rule[1])

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
        self.edit_rules.initialize(db.field_metadata, db.prefs, mi, 'column_color_rules')
        self.icon_rules.initialize(db.field_metadata, db.prefs, mi, 'column_icon_rules')
        self.grid_rules.initialize(db.field_metadata, db.prefs, mi, 'cover_grid_icon_rules')
        self.set_cg_color(gprefs['cover_grid_color'])
        self.set_cg_texture(gprefs['cover_grid_texture'])
        self.update_aspect_ratio()

    def open_cg_cache(self):
        open_local_file(self.gui.grid_view.thumbnail_cache.location)

    def update_cg_cache_size(self, size):
        self.cover_grid_current_disk_cache.setText(
            _('Current space used: %s') % human_readable(size))

    def tab_changed(self, index):
        if self.tabWidget.currentWidget() is self.cover_grid_tab:
            self.show_current_cache_usage()

    def show_current_cache_usage(self):
        t = Thread(target=self.calc_cache_size)
        t.daemon = True
        t.start()

    def calc_cache_size(self):
        self.size_calculated.emit(self.gui.grid_view.thumbnail_cache.current_size)

    def set_cg_color(self, val):
        self.cg_bg_widget.bcol = QColor(*val)
        self.cg_bg_widget.update_brush()

    def set_cg_texture(self, val):
        self.cg_bg_widget.btex = val
        self.cg_bg_widget.update_brush()

    def empty_cache(self):
        self.gui.grid_view.thumbnail_cache.empty()
        self.calc_cache_size()

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        ofont = self.current_font
        self.current_font = None
        if ofont is not None:
            self.changed_signal.emit()
            self.update_font_display()
        self.display_model.restore_defaults()
        self.edit_rules.clear()
        self.icon_rules.clear()
        self.grid_rules.clear()
        self.changed_signal.emit()
        self.set_cg_color(gprefs.defaults['cover_grid_color'])
        self.set_cg_texture(gprefs.defaults['cover_grid_texture'])

    def change_cover_grid_color(self):
        col = QColorDialog.getColor(self.cg_bg_widget.bcol,
                              self.gui, _('Choose background color for the cover grid'))
        if col.isValid():
            col = tuple(col.getRgb())[:3]
            self.set_cg_color(col)
            self.changed_signal.emit()
            if self.cg_bg_widget.btex:
                if question_dialog(
                    self, _('Remove background image?'),
                    _('There is currently a background image set, so the color'
                      ' you have chosen will not be visible. Remove the background image?')):
                    self.set_cg_texture(None)

    def change_cover_grid_texture(self):
        from calibre.gui2.preferences.texture_chooser import TextureChooser
        d = TextureChooser(parent=self, initial=self.cg_bg_widget.btex)
        if d.exec_() == d.Accepted:
            self.set_cg_texture(d.texture)
            self.changed_signal.emit()

    def restore_cover_grid_appearance(self):
        self.set_cg_color(gprefs.defaults['cover_grid_color'])
        self.set_cg_texture(gprefs.defaults['cover_grid_texture'])
        self.changed_signal.emit()

    def build_font_obj(self):
        font_info = qt_app.original_font if self.current_font is None else self.current_font
        font = QFont(*(font_info[:4]))
        font.setStretch(font_info[4])
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
        with BusyCursor():
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
            self.icon_rules.commit(self.gui.current_db.prefs)
            self.grid_rules.commit(self.gui.current_db.prefs)
            gprefs['cover_grid_color'] = tuple(self.cg_bg_widget.bcol.getRgb())[:3]
            gprefs['cover_grid_texture'] = self.cg_bg_widget.btex
            if self.commit_icon_theme is not None:
                self.commit_icon_theme()
                rr = True
        return rr

    def refresh_gui(self, gui):
        m = gui.library_view.model()
        m.beginResetModel(), m.endResetModel()
        self.update_font_display()
        gui.tags_view.reread_collapse_parameters()
        gui.library_view.refresh_book_details()
        gui.library_view.set_row_header_visibility()
        gui.cover_flow.setShowReflections(gprefs['cover_browser_reflections'])
        gui.cover_flow.setPreserveAspectRatio(gprefs['cb_preserve_aspect_ratio'])
        gui.update_cover_flow_subtitle_font()
        gui.cover_flow.template_inited = False
        for view in 'library memory card_a card_b'.split():
            getattr(gui, view + '_view').set_row_header_visibility()
        gui.library_view.refresh_row_sizing()
        gui.grid_view.refresh_settings()


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    test_widget('Interface', 'Look & Feel')
