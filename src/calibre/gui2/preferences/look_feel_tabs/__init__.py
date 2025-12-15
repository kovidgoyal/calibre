#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json
from threading import Thread

from qt.core import (
    QAbstractListModel,
    QBrush,
    QColor,
    QColorDialog,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QIcon,
    QItemSelectionModel,
    QLabel,
    QLineEdit,
    QPainter,
    QPixmap,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    Qt,
    QToolButton,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre import human_readable
from calibre.db.constants import NO_SEARCH_LINK
from calibre.ebooks.metadata.book.render import DEFAULT_AUTHOR_LINK
from calibre.ebooks.metadata.search_internet import qquote
from calibre.gui2 import choose_files, choose_save_file, error_dialog, gprefs, open_local_file, question_dialog, resolve_custom_background
from calibre.gui2.book_details import get_field_list
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.preferences import LazyConfigWidgetBase, get_move_count
from calibre.gui2.preferences.coloring import EditRules
from calibre.gui2.ui import get_gui
from calibre.utils.formatter import EvalFormatter


class DefaultAuthorLink(QWidget):

    changed_signal = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        l = QVBoxLayout()
        l.addWidget(self)
        l.setContentsMargins(0, 0, 0, 0)
        l = QFormLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.choices = c = QComboBox()
        c.setMinimumContentsLength(30)
        for text, data in [
                (_('Search for the author on Goodreads'), 'search-goodreads'),
                (_('Search for the author on Amazon'), 'search-amzn'),
                (_('Search for the author in your calibre library'), 'search-calibre'),
                (_('Search for the author on Wikipedia'), 'search-wikipedia'),
                (_('Search for the author on Google Books'), 'search-google'),
                (_('Search for the book on Goodreads'), 'search-goodreads-book'),
                (_('Search for the book on Amazon'), 'search-amzn-book'),
                (_('Search for the book on Google Books'), 'search-google-book'),
                (_('No author search URL'), NO_SEARCH_LINK),
                (_('Use a custom search URL'), 'url'),
        ]:
            c.addItem(text, data)
        l.addRow(_('Clicking on &author names should:'), c)
        ul = QHBoxLayout()
        self.custom_url = u = QLineEdit(self)
        u.setToolTip(_(
            'Enter the URL to search. It should contain the string {0}'
            '\nwhich will be replaced by the author name. For example,'
            '\n{1}. Note: the author name is already URL-encoded.').format(
                        '{author}', 'https://en.wikipedia.org/w/index.php?search={author}'))
        u.textChanged.connect(self.changed_signal)
        u.setPlaceholderText(_('Enter the URL'))
        ul.addWidget(u)
        u = self.custom_url_button = QToolButton()
        u.setIcon(QIcon.ic('edit_input.png'))
        u.setToolTip(_('Click this button to open the template tester'))
        u.clicked.connect(self.open_template_tester)
        ul.addWidget(u)
        c.currentIndexChanged.connect(self.current_changed)
        l.addRow(ul)
        self.current_changed()
        c.currentIndexChanged.connect(self.changed_signal)

    @property
    def value(self):
        k = self.choices.currentData()
        if k == 'url':
            return self.custom_url.text()
        return k if k != DEFAULT_AUTHOR_LINK else None

    @value.setter
    def value(self, val):
        i = self.choices.findData(val)
        if i < 0:
            i = self.choices.findData('url')
            self.custom_url.setText(val)
        self.choices.setCurrentIndex(i)

    def open_template_tester(self):
        gui = get_gui()
        db = gui.current_db.new_api
        lv = gui.library_view
        rows = lv.selectionModel().selectedRows()
        if not rows:
            vals = [{'author': qquote(_('Author')), 'title': _('Title'), 'author_sort': _('Author sort')}]
        else:
            vals = []
            for row in rows:
                book_id = lv.model().id(row)
                mi = db.new_api.get_proxy_metadata(book_id)
                vals.append({'author': qquote(mi.authors[0]),
                             'title': qquote(mi.title),
                             'author_sort': qquote(mi.author_sort_map.get(mi.authors[0]))})
        d = TemplateDialog(parent=self, text=self.custom_url.text(), mi=vals, formatter=EvalFormatter)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.custom_url.setText(d.rule[1])

    def current_changed(self):
        k = self.choices.currentData()
        self.custom_url.setVisible(k == 'url')
        self.custom_url_button.setVisible(k == 'url')

    def restore_defaults(self):
        self.value = DEFAULT_AUTHOR_LINK


class DisplayedFields(QAbstractListModel):

    def __init__(self, db, parent=None, pref_name=None, category_icons=None):
        self.pref_name = pref_name or 'book_display_fields'
        QAbstractListModel.__init__(self, parent)

        self.fields = []
        self.db = db
        self.changed = False
        self.category_icons = category_icons

    def get_field_list(self, use_defaults=False):
        return get_field_list(self.db.field_metadata, use_defaults=use_defaults, pref_name=self.pref_name)

    def initialize(self, use_defaults=False):
        self.beginResetModel()
        self.fields = [[x[0], x[1]] for x in self.get_field_list(use_defaults=use_defaults)]
        self.endResetModel()
        self.changed = True

    def rowCount(self, *args):
        return len(self.fields)

    def data(self, index, role):
        try:
            field, visible = self.fields[index.row()]
        except Exception:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            name = field
            try:
                name = self.db.field_metadata[field]['name']
            except Exception:
                pass
            if field == 'path':
                name = _('Folders/path')
            name = field.partition('.')[0][1:] if field.startswith('@') else name
            if not name:
                return field
            return f'{name} ({field})'
        if role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked
        if role == Qt.ItemDataRole.DecorationRole:
            if self.category_icons:
                icon = self.category_icons.get(field, None)
                if icon is not None:
                    return icon
            if field.startswith('#'):
                return QIcon.ic('column.png')
        return None

    def toggle_all(self, show=True):
        for i in range(self.rowCount()):
            idx = self.index(i)
            if idx.isValid():
                self.setData(idx, Qt.CheckState.Checked if show else Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)

    def flags(self, index):
        ans = QAbstractListModel.flags(self, index)
        return ans | Qt.ItemFlag.ItemIsUserCheckable

    def setData(self, index, val, role):
        ret = False
        if role == Qt.ItemDataRole.CheckStateRole:
            self.fields[index.row()][1] = val in (Qt.CheckState.Checked, Qt.CheckState.Checked.value)
            self.changed = True
            ret = True
            self.dataChanged.emit(index, index)
        return ret

    def restore_defaults(self):
        self.initialize(use_defaults=True)

    def commit(self):
        if self.changed:
            self.db.new_api.set_pref(self.pref_name, self.fields)

    def move(self, idx, delta):
        row = idx.row()
        if delta > 0:
            delta = delta if row + delta < self.rowCount() else self.rowCount() - row - 1
        else:
            delta = -row if row + delta < 0 else delta
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


class LazyEditRulesBase(LazyConfigWidgetBase):

    rule_set_name = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules_editor = EditRules(parent)
        self.setLayout(self.rules_editor.layout())

    def genesis(self, gui):
        self.gui = gui

    def lazy_initialize(self):
        if not self.rule_set_name:
            raise NotImplementedError('You must define the attribute "rule_set_name" in LazyEditRulesBase subclasses')

        db = self.gui.current_db
        mi = selected_rows_metadatas()
        self.rules_editor.initialize(db.field_metadata, db.prefs, mi, self.rule_set_name)
        self.register(self.rule_set_name, db.prefs, 'rules_editor')


class ColumnColorRules(LazyEditRulesBase):
    rule_set_name = 'column_color_rules'


class ColumnIconRules(LazyEditRulesBase):
    rule_set_name = 'column_icon_rules'


class GridEmblemnRules(LazyEditRulesBase):
    rule_set_name = 'cover_grid_icon_rules'


class BookshelfColorRules(LazyEditRulesBase):
    rule_set_name = 'bookshelf_color_rules'


class BackgroundConfig(QGroupBox, LazyConfigWidgetBase):

    changed_signal = pyqtSignal()
    restart_now = pyqtSignal()

    class Container(LazyConfigWidgetBase):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.config_name = None
            self.bcol_dark = None
            self.bcol_light = None
            self.btex_dark = None
            self.btex_light = None

            self.light_label = QLabel(self)
            self.dark_label = QLabel(self)

            self.light_label.linkActivated.connect(self.light_link_activated)
            self.dark_label.linkActivated.connect(self.dark_link_activated)

            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.setMinimumSize(200, 120)
            self.setContentsMargins(0, 0, 0, 0)

            l = QHBoxLayout(self)
            self.setLayout(l)
            l.addWidget(self.light_label)
            l.addWidget(self.dark_label)

            self.changed_signal.connect(self.update_content)

        def genesis(self, gui):
            self.gui = gui

        def lazy_initialize(self):
            self.load_from_gprefs()

        def load_from_gprefs(self, use_defaults=False):
            rs = resolve_custom_background
            self.bcol_dark = QColor(*rs(self.config_name, for_dark=True, use_defaults=use_defaults))
            self.bcol_light = QColor(*rs(self.config_name, for_dark=False, use_defaults=use_defaults))
            self.btex_dark = rs(self.config_name, 'texture', for_dark=True, use_defaults=use_defaults)
            self.btex_light = rs(self.config_name, 'texture', for_dark=False, use_defaults=use_defaults)
            self.update_content()

        def light_link_activated(self, url):
            if 'texture' in url:
                self.change_texture(light=True)
            else:
                self.change_color(light=True)
            self.update_content()

        def dark_link_activated(self, url):
            if 'texture' in url:
                self.change_texture(light=False)
            else:
                self.change_color(light=False)

        def change_texture(self, light=False):
            from calibre.gui2.preferences.texture_chooser import TextureChooser
            btex = self.btex_light if light else self.btex_dark
            d = TextureChooser(parent=self, initial=btex)
            if d.exec() == QDialog.DialogCode.Accepted:
                if light:
                    self.btex_light = d.texture
                else:
                    self.btex_dark = d.texture
                self.changed_signal.emit()

        def change_color(self, light=False):
            which = _('light') if light else _('dark')
            col = QColorDialog.getColor(self.bcol_light if light else self.bcol_dark,
                    self, _('Choose {} background color').format(which))

            if col.isValid():
                if light:
                    self.bcol_light = col
                else:
                    self.bcol_dark = col
                btex = self.btex_light if light else self.btex_dark
                if btex:
                    if question_dialog(
                        self, _('Remove background image?'),
                        _('There is currently a background image set, so the color'
                          ' you have chosen will not be visible. Remove the background image?')):
                        if light:
                            self.btex_light = None
                        else:
                            self.btex_dark = None
                self.changed_signal.emit()

        def update_content(self):
            self.update_text()
            self.update_brush()
            self.update()

        def update_text(self):
            text = (
                '<p style="text-align: center; color: {}"><b>{}</b><br>'
                '<a style="text-decoration: none" href="la://color.me">{}</a><br>'
                '<a style="text-decoration: none" href="la://texture.me">{}</a></p>')
            self.light_label.setText(text.format('black', _('Light'), _('Change color'), _('Change texture')))
            self.dark_label.setText(text.format('white', _('Dark'), _('Change color'), _('Change texture')))

        def update_brush(self):
            self.light_brush = QBrush(self.bcol_light)
            self.dark_brush = QBrush(self.bcol_dark)
            def dotex(path, brush):
                if path:
                    from calibre.gui2.preferences.texture_chooser import texture_path
                    path = texture_path(path)
                    if path:
                        p = QPixmap(path)
                        try:
                            dpr = self.devicePixelRatioF()
                        except AttributeError:
                            dpr = self.devicePixelRatio()
                        p.setDevicePixelRatio(dpr)
                        brush.setTexture(p)
            dotex(self.btex_light, self.light_brush)
            dotex(self.btex_dark, self.dark_brush)

        def restore_defaults(self):
            self.load_from_gprefs(use_defaults=True)
            self.changed_signal.emit()

        def commit(self):
            s = gprefs[self.config_name].copy()
            s['light'] = tuple(self.bcol_light.getRgb())[:3]
            s['dark'] = tuple(self.bcol_dark.getRgb())[:3]
            s['light_texture'] = self.btex_light
            s['dark_texture'] = self.btex_dark
            gprefs[self.config_name] = s

        def paintEvent(self, ev):
            painter = QPainter(self)
            r = self.rect()
            light = r.adjusted(0, 0, -r.width()//2, 0)
            dark = r.adjusted(light.width(), 0, 0, 0)
            painter.fillRect(light, self.light_brush)
            painter.fillRect(dark, self.dark_brush)
            painter.end()
            super().paintEvent(ev)

    def __init__(self, parent=None):
        super().__init__(parent)

    def setupUi(self, form):
        # Simulate a ui file, else LazyConfigWidgetBase don't found the child
        grid = QGridLayout(self)
        self.setLayout(grid)

        self.container = BackgroundConfig.Container(self)
        self.reset_appearance_button = QPushButton(_('Restore default &appearance'), self)
        self.reset_appearance_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.reset_appearance_button.clicked.connect(self.container.restore_defaults)

        grid.addWidget(self.container, 0, 0, 2, 1)
        grid.addWidget(self.reset_appearance_button, 0, 1)

    def genesis(self, gui):
        self.gui = gui

    def link_config(self, name):
        self.container.config_name = name


class CoverCacheConfig(LazyConfigWidgetBase):

    size_calculated = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.name_disk_cache_size = None
        self.name_cache_size_multiple = None

        l = QVBoxLayout(self)
        self.setLayout(l)
        group_box = QGroupBox(_('Caching of covers for improved performance'), self)
        l.addWidget(group_box)

        grid = QGridLayout(group_box)
        group_box.setLayout(grid)

        description = QLabel(group_box)
        description.setWordWrap(True)
        description.setText(
            _("There are two kinds of caches that calibre uses to improve performance when rendering covers."
            " A disk cache that is kept on your hard disk and stores the cover thumbnails and an in memory cache"
            " used to ensure flicker free rendering of covers. For best results, keep the memory cache small and the disk cache large,"
            " unless you have a lot of extra RAM in your computer and don't mind it being used by the memory cache."))

        self.lbl_cache_size_multiple = QLabel(_('Number of screenfulls of covers to cache in &memory (keep this small):'), group_box)
        self.opt_cache_size_multiple = QSpinBox(group_box)
        self.opt_cache_size_multiple.setMinimum(2)
        self.opt_cache_size_multiple.setMaximum(100)
        self.opt_cache_size_multiple.setSingleStep(1)
        self.opt_cache_size_multiple.setToolTip(
            _('The maximum number of screenfulls of thumbnails to keep in memory.'
            ' Increasing this will make rendering faster, at the cost of more memory usage. Note that regardless of this setting,'
            ' a minimum of one hundred thumbnails are always kept in memory, to ensure flicker free rendering.'))
        self.lbl_cache_size_multiple.setBuddy(self.opt_cache_size_multiple)

        self.lbl_cache_size_disk = QLabel(_('Maximum amount of &disk space to use for caching thumbnails: '), group_box)
        self.opt_cache_size_disk = QSpinBox(group_box)
        self.opt_cache_size_disk.setSingleStep(100)
        self.lbl_cache_size_disk.setBuddy(self.opt_cache_size_disk)

        self.opt_cache_size_disk.setSpecialValueText(_('Disable'))
        self.opt_cache_size_disk.setSuffix(_(' MB'))

        self.lbl_current_disk_cache = QLabel(group_box)

        btn_empty_cache = QPushButton(_('&Empty disk cache'), group_box)
        btn_open_cache = QPushButton(_('&Open cache folder'), group_box)

        spacer1 = QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        spacer2 = QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        grid.addWidget(description, 0, 0, 1, 5)
        grid.addWidget(self.lbl_cache_size_multiple, 1, 0, 1, 2)
        grid.addWidget(self.opt_cache_size_multiple, 1, 2)
        grid.addWidget(self.lbl_cache_size_disk, 2, 0, 1, 2)
        grid.addWidget(self.opt_cache_size_disk, 2, 2)
        grid.addItem(spacer1, 2, 3)
        grid.addWidget(self.lbl_current_disk_cache, 3, 2)
        grid.addWidget(btn_empty_cache, 4, 0)
        grid.addWidget(btn_open_cache, 4, 1)
        grid.addItem(spacer2, 5, 1)

        btn_empty_cache.clicked.connect(self.empty_cache)
        btn_open_cache.clicked.connect(self.open_cache)
        self.size_calculated.connect(self.update_cache_size, type=Qt.ConnectionType.QueuedConnection)

    def genesis(self, gui):
        self.gui = gui

    def link(self, cover_cache, name_disk_cache_size, name_cache_size_multiple=None):
        from calibre.gui2.library.caches import ThumbnailRenderer
        self.cover_cache: ThumbnailRenderer = cover_cache.renderer
        self.name_disk_cache_size = name_disk_cache_size
        self.name_cache_size_multiple = name_cache_size_multiple
        self.opt_cache_size_disk.setMinimum(self.cover_cache.disk_cache.min_disk_cache)
        self.opt_cache_size_disk.setMaximum(self.cover_cache.disk_cache.min_disk_cache * 100)

        self.register(self.name_disk_cache_size, gprefs, 'opt_cache_size_disk')
        if self.name_cache_size_multiple:
            self.register(self.name_cache_size_multiple, gprefs, 'opt_cache_size_multiple')
        else:
            self.lbl_cache_size_multiple.setHidden(True)
            self.opt_cache_size_multiple.setHidden(True)

    def lazy_initialize(self):
        self.show_current_cache_usage()

    def update_cache_size(self, size):
        self.lbl_current_disk_cache.setText(_('Current space used: %s') % human_readable(size))

    def empty_cache(self):
        self.cover_cache.disk_cache.empty()
        self.calc_cache_size()

    def open_cache(self):
        open_local_file(self.cover_cache.disk_cache.location)

    def show_current_cache_usage(self):
        t = Thread(target=self.calc_cache_size)
        t.daemon = True
        t.start()

    def calc_cache_size(self):
        self.size_calculated.emit(self.cover_cache.disk_cache.current_size)


def export_layout(in_widget, model=None):
    filename = choose_save_file(in_widget, 'look_feel_prefs_import_export_field_list',
            _('Save column list to file'),
            filters=[(_('Column list'), ['json'])])
    if filename:
        try:
            with open(filename, 'w') as f:
                json.dump(model.fields, f, indent=1)
        except Exception as err:
            error_dialog(in_widget, _('Export field layout'),
                         _('<p>Could not write field list. Error:<br>%s')%err, show=True)


def import_layout(in_widget, model=None):
    filename = choose_files(in_widget, 'look_feel_prefs_import_export_field_list',
            _('Load column list from file'),
            filters=[(_('Column list'), ['json'])])
    if filename:
        try:
            with open(filename[0]) as f:
                fields = json.load(f)
            model.initialize(pref_data_override=fields)
            in_widget.changed_signal.emit()
        except Exception as err:
            error_dialog(in_widget, _('Import layout'),
                         _('<p>Could not read field list. Error:<br>%s')%err, show=True)


def reset_layout(in_widget, model=None):
    model.initialize(use_defaults=True)
    in_widget.changed_signal.emit()


def move_field_up(widget, model, *args, use_kbd_modifiers=True):
    count = get_move_count(model.rowCount()) if use_kbd_modifiers else 1
    idx = widget.currentIndex()
    if idx.isValid():
        idx = model.move(idx, -count)
        if idx is not None:
            sm = widget.selectionModel()
            sm.select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            widget.setCurrentIndex(idx)


def move_field_down(widget, model, *args, use_kbd_modifiers=True):
    count = get_move_count(model.rowCount()) if use_kbd_modifiers else 1
    idx = widget.currentIndex()
    if idx.isValid():
        idx = model.move(idx, count)
        if idx is not None:
            sm = widget.selectionModel()
            sm.select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            widget.setCurrentIndex(idx)


def selected_rows_metadatas():
    rslt = []
    try:
        db = get_gui().current_db
        rows = get_gui().current_view().selectionModel().selectedRows()
        for row in rows:
            if row.isValid():
                rslt.append(db.new_api.get_proxy_metadata(db.data.index_to_id(row.row())))
    except Exception:
        pass
    return rslt
