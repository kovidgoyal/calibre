#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import OrderedDict

from PyQt5.Qt import (
    QWidget, QHBoxLayout, QTabWidget, QLabel, QSizePolicy, QSize, QFormLayout,
    QSpinBox, pyqtSignal, QPixmap, QDialog, QVBoxLayout, QDialogButtonBox,
    QListWidget, QListWidgetItem, Qt, QGridLayout, QPushButton, QIcon, QApplication,
    QColorDialog, QToolButton, QLineEdit, QColor, QFrame, QTimer, QCheckBox)

from calibre.ebooks.covers import all_styles, cprefs, generate_cover, override_prefs, default_color_themes
from calibre.gui2 import gprefs, error_dialog
from calibre.gui2.font_family_chooser import FontFamilyChooser
from calibre.utils.date import now
from calibre.utils.icu import sort_key
from polyglot.builtins import iteritems, itervalues


class Preview(QLabel):

    def __init__(self, parent=None):
        QLabel.__init__(self, parent)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)

    def sizeHint(self):
        return QSize(300, 400)


class ColorButton(QToolButton):

    def __init__(self, color, parent=None):
        QToolButton.__init__(self, parent)
        self.setIconSize(QSize(50, 25))
        self.pix = QPixmap(self.iconSize())
        self._color = QColor('#' + color)
        self.pix.fill(self._color)
        self.setIcon(QIcon(self.pix))
        self.clicked.connect(self.choose_color)

    @property
    def color(self):
        return self._color.name(QColor.HexRgb)[1:]

    @color.setter
    def color(self, val):
        self._color = QColor('#' + val)

    def update_display(self):
        self.pix.fill(self._color)
        self.setIcon(QIcon(self.pix))

    def choose_color(self):
        c = QColorDialog.getColor(self._color, self, _('Choose color'))
        if c.isValid():
            self._color = c
            self.update_display()


class CreateColorScheme(QDialog):

    def __init__(self, scheme_name, scheme, existing_names, edit_scheme=False, parent=None):
        QDialog.__init__(self, parent)
        self.existing_names, self.is_editing, self.scheme_name = existing_names, edit_scheme, scheme_name
        self.l = l = QFormLayout(self)
        self.setLayout(l)
        self.setWindowTitle(scheme_name)
        self.name = n = QLineEdit(self)
        n.setText(scheme_name if edit_scheme else '#' +('My Color Scheme'))
        l.addRow(_('&Name:'), self.name)
        for x in 'color1 color2 contrast_color1 contrast_color2'.split():
            setattr(self, x, ColorButton(scheme[x], self))
        l.addRow(_('Color &1:'), self.color1)
        l.addRow(_('Color &2:'), self.color2)
        l.addRow(_('Contrast color &1 (mainly for text):'), self.contrast_color1)
        l.addRow(_('Contrast color &2 (mainly for text):'), self.contrast_color2)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addRow(bb)

    @property
    def data(self):
        return self.name.text(), {x:getattr(self, x).color for x in 'color1 color2 contrast_color1 contrast_color2'.split()}

    def accept(self):
        name = self.name.text()
        if not name or len(name) < 2 or not name.startswith('#'):
            return error_dialog(self, _('Invalid name'), _(
                'The color scheme name "%s" is invalid. It must start with a # and be at least two characters long.') % name, show=True)
        if name in self.existing_names:
            if not self.is_editing or name != self.scheme_name:
                return error_dialog(self, _('Invalid name'), _(
                    'A color scheme with the name "%s" already exists.') % name, show=True)
        QDialog.accept(self)


class CoverSettingsWidget(QWidget):

    changed = pyqtSignal()

    def __init__(self, mi=None, prefs=None, parent=None, for_global_prefs=False):
        QWidget.__init__(self, parent)
        self.ignore_changed = False
        self.for_global_prefs = for_global_prefs

        self.l = l = QHBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.setLayout(l)
        self.settings_tabs = st = QTabWidget(self)
        l.addWidget(st)
        self.preview_label = la = Preview(self)
        l.addWidget(la)

        if prefs is None:
            prefs = cprefs
        self.original_prefs = prefs
        self.mi = mi or self.default_mi()

        self.colors_page = cp = QWidget(st)
        st.addTab(cp, _('&Colors'))
        cp.l = l = QGridLayout()
        cp.setLayout(l)
        if for_global_prefs:
            msg = _('When generating covers, a color scheme for the cover is chosen at random from the'
                    ' color schemes below. You can prevent an individual scheme from being selected by'
                    ' unchecking it. The preview on the right shows the currently selected color scheme.')
        else:
            msg = _('Choose a color scheme to be used for this generated cover.') + '<p>' + _(
                'In normal cover generation, the color scheme is chosen at random from the list of color schemes below. You'
                ' can prevent an individual color scheme from being chosen by unchecking it here.')
        cp.la = la = QLabel('<p>' + msg)
        la.setWordWrap(True)
        l.addWidget(la, 0, 0, 1, -1)
        self.colors_list = cl = QListWidget(cp)
        l.addWidget(cl, 1, 0, 1, -1)
        self.colors_map = OrderedDict()
        self.ncs = ncs = QPushButton(QIcon(I('plus.png')), _('&New color scheme'), cp)
        ncs.clicked.connect(self.create_color_scheme)
        l.addWidget(ncs)
        self.ecs = ecs = QPushButton(QIcon(I('format-fill-color.png')), _('&Edit color scheme'), cp)
        ecs.clicked.connect(self.edit_color_scheme)
        l.addWidget(ecs, l.rowCount()-1, 1)
        self.rcs = rcs = QPushButton(QIcon(I('minus.png')), _('&Remove color scheme'), cp)
        rcs.clicked.connect(self.remove_color_scheme)
        l.addWidget(rcs, l.rowCount()-1, 2)

        self.styles_page = sp = QWidget(st)
        st.addTab(sp, _('&Styles'))
        sp.l = l = QVBoxLayout()
        sp.setLayout(l)
        if for_global_prefs:
            msg = _('When generating covers, a style for the cover is chosen at random from the'
                    ' styles below. You can prevent an individual style from being selected by'
                    ' unchecking it. The preview on the right shows the currently selected style.')
        else:
            msg = _('Choose a style to be used for this generated cover.') + '<p>' + _(
                'In normal cover generation, the style is chosen at random from the list of styles below. You'
                ' can prevent an individual style from being chosen by unchecking it here.')
        sp.la = la = QLabel('<p>' + msg)
        la.setWordWrap(True)
        l.addWidget(la)
        self.styles_list = sl = QListWidget(sp)
        l.addWidget(sl)
        self.style_map = OrderedDict()

        self.font_page = fp = QWidget(st)
        st.addTab(fp, _('&Fonts and sizes'))
        fp.l = l = QFormLayout()
        fp.setLayout(l)
        fp.f = []

        def add_hline():
            f = QFrame()
            fp.f.append(f)
            f.setFrameShape(f.HLine)
            l.addRow(f)

        for x, label, size_label in (
                ('title', _('&Title font family:'), _('&Title font size:')),
                ('subtitle', _('&Subtitle font family'), _('&Subtitle font size:')),
                ('footer', _('&Footer font family'), _('&Footer font size')),
        ):
            attr = '%s_font_family' % x
            ff = FontFamilyChooser(fp)
            setattr(self, attr, ff)
            l.addRow(label, ff)
            ff.family_changed.connect(self.emit_changed)
            attr = '%s_font_size' % x
            fs = QSpinBox(fp)
            setattr(self, attr, fs)
            fs.setMinimum(8), fs.setMaximum(200), fs.setSuffix(' px')
            fs.setValue(prefs[attr])
            fs.valueChanged.connect(self.emit_changed)
            l.addRow(size_label, fs)
            add_hline()
        self.changed_timer = t = QTimer(self)
        t.setSingleShot(True), t.setInterval(500), t.timeout.connect(self.emit_changed)

        def create_sz(label):
            ans = QSpinBox(self)
            ans.setSuffix(' px'), ans.setMinimum(100), ans.setMaximum(10000)
            l.addRow(label, ans)
            ans.valueChanged.connect(self.changed_timer.start)
            return ans

        self.cover_width = create_sz(_('Cover &width:'))
        self.cover_height = create_sz(_('Cover &height:'))
        fp.cla = la = QLabel(_(
            'Note that the preview to the side is of fixed aspect ratio, so changing the cover'
            ' width above will not have any effect. If you change the height, you should also change the width nevertheless'
            ' as it will be used in actual cover generation.'))
        la.setWordWrap(True)
        l.addRow(la)

        self.templates_page = tp = QWidget(st)
        st.addTab(tp, _('&Text'))
        tp.l = l = QVBoxLayout()
        tp.setLayout(l)
        tp.la = la = QLabel(_(
            'The text on the generated cover is taken from the metadata of the book.'
            ' This is controlled via templates. You can use the <b>, <i> and <br> tags'
            ' in the templates for bold, italic and line breaks, respectively. The'
            ' default templates use the title, series and authors. You can change them to use'
            ' whatever metadata you like.'))
        la.setWordWrap(True), la.setTextFormat(Qt.PlainText)
        l.addWidget(la)

        def create_template_widget(title, which, button):
            attr = which + '_template'
            heading = QLabel('<h2>' + title)
            setattr(tp, attr + '_heading', heading)
            l.addWidget(heading)
            la = QLabel()
            setattr(self, attr, la)
            l.addWidget(la), la.setTextFormat(Qt.PlainText), la.setStyleSheet('QLabel {font-family: monospace}')
            la.setWordWrap(True)
            b = QPushButton(button)
            b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            connect_lambda(b.clicked, self, lambda self: self.change_template(which))
            setattr(self, attr + '_button', b)
            l.addWidget(b)
            if which != 'footer':
                f = QFrame(tp)
                setattr(tp, attr + '_sep', f), f.setFrameShape(QFrame.HLine)
                l.addWidget(f)
            l.addSpacing(10)

        create_template_widget(_('The title template'), 'title', _('Change the &title template'))
        create_template_widget(_('The sub-title template'), 'subtitle', _('Change the &sub-title template'))
        create_template_widget(_('The footer template'), 'footer', _('Change the &footer template'))
        l.addStretch(2)

        self.apply_prefs(prefs)
        self.changed.connect(self.update_preview)
        self.styles_list.itemSelectionChanged.connect(self.update_preview)
        self.colors_list.itemSelectionChanged.connect(self.update_preview)
        self.update_preview()

    def __enter__(self):
        self.ignore_changed = True

    def __exit__(self, *args):
        self.ignore_changed = False

    def emit_changed(self):
        if not self.ignore_changed:
            self.changed.emit()

    def apply_prefs(self, prefs):
        with self:
            self._apply_prefs(prefs)

    def _apply_prefs(self, prefs):
        for x in ('title', 'subtitle', 'footer'):
            attr = '%s_font_family' % x
            getattr(self, attr).font_family = prefs[attr]
            attr = '%s_font_size' % x
            getattr(self, attr).setValue(prefs[attr])

        for x in ('title', 'subtitle', 'footer'):
            x += '_template'
            getattr(self, x).setText(prefs[x])

        for x in ('width', 'height'):
            x = 'cover_' + x
            getattr(self, x).setValue(prefs[x])

        color_themes = prefs['color_themes'].copy()
        color_themes.update(default_color_themes)
        disabled = set(prefs['disabled_color_themes'])
        self.colors_list.clear()
        self.colors_map = {}
        for name in sorted(color_themes, key=sort_key):
            self.colors_map[name] = li = QListWidgetItem(name, self.colors_list)
            li.setFlags(li.flags() | Qt.ItemIsUserCheckable)
            li.setCheckState(Qt.Unchecked if name in disabled else Qt.Checked)
            li.setData(Qt.UserRole, color_themes[name])
        lu = prefs.get('last_used_colors')
        if not self.for_global_prefs and lu in self.colors_map and self.colors_map[lu].checkState() == Qt.Checked:
            self.colors_map[lu].setSelected(True)
        else:
            for name, li in iteritems(self.colors_map):
                if li.checkState() == Qt.Checked:
                    li.setSelected(True)
                    break
            else:
                next(itervalues(self.colors_map)).setSelected(True)

        disabled = set(prefs['disabled_styles'])
        self.styles_list.clear()
        self.style_map.clear()
        for name in sorted(all_styles(), key=sort_key):
            self.style_map[name] = li = QListWidgetItem(name, self.styles_list)
            li.setFlags(li.flags() | Qt.ItemIsUserCheckable)
            li.setCheckState(Qt.Unchecked if name in disabled else Qt.Checked)
        lu = prefs.get('last_used_style')
        if not self.for_global_prefs and lu in self.style_map and self.style_map[lu].checkState() == Qt.Checked:
            self.style_map[lu].setSelected(True)
        else:
            for name, li in iteritems(self.style_map):
                if li.checkState() == Qt.Checked:
                    li.setSelected(True)
                    break
            else:
                next(itervalues(self.style_map)).setSelected(True)

    @property
    def current_colors(self):
        for name, li in iteritems(self.colors_map):
            if li.isSelected():
                return name

    @property
    def disabled_colors(self):
        for name, li in iteritems(self.colors_map):
            if li.checkState() == Qt.Unchecked:
                yield name

    @property
    def custom_colors(self):
        ans = {}
        for name, li in iteritems(self.colors_map):
            if name.startswith('#'):
                ans[name] = li.data(Qt.UserRole)
        return ans

    @property
    def current_style(self):
        for name, li in iteritems(self.style_map):
            if li.isSelected():
                return name

    @property
    def disabled_styles(self):
        for name, li in iteritems(self.style_map):
            if li.checkState() == Qt.Unchecked:
                yield name

    @property
    def current_prefs(self):
        prefs = {k:self.original_prefs[k] for k in self.original_prefs.defaults}
        for x in ('title', 'subtitle', 'footer'):
            attr = '%s_font_family' % x
            prefs[attr] = getattr(self, attr).font_family
            attr = '%s_font_size' % x
            prefs[attr] = getattr(self, attr).value()
        prefs['color_themes'] = self.custom_colors
        prefs['disabled_styles'] = list(self.disabled_styles)
        prefs['disabled_color_themes'] = list(self.disabled_colors)
        for x in ('title', 'subtitle', 'footer'):
            x += '_template'
            prefs[x] = getattr(self, x).text()
        for x in ('width', 'height'):
            x = 'cover_' + x
            prefs[x] = getattr(self, x).value()
        return prefs

    def insert_scheme(self, name, li):
        with self:
            self.colors_list.insertItem(0, li)
            cm = OrderedDict()
            cm[name] = li
            for k, v in iteritems(self.colors_map):
                cm[k] = v
            self.colors_map = cm
            li.setSelected(True)
            for i in range(1, self.colors_list.count()):
                self.colors_list.item(i).setSelected(False)

    def create_color_scheme(self):
        scheme = self.colors_map[self.current_colors].data(Qt.UserRole)
        d = CreateColorScheme('#' + _('My Color Scheme'), scheme, set(self.colors_map), parent=self)
        if d.exec_() == d.Accepted:
            name, scheme = d.data
            li = QListWidgetItem(name)
            li.setData(Qt.UserRole, scheme), li.setFlags(li.flags() | Qt.ItemIsUserCheckable), li.setCheckState(Qt.Checked)
            self.insert_scheme(name, li)
            self.emit_changed()
            self.original_prefs['color_themes'] = self.current_prefs['color_themes']

    def edit_color_scheme(self):
        cs = self.current_colors
        if cs is None or not cs.startswith('#'):
            return error_dialog(self, _('Cannot edit'), _(
                'Cannot edit a builtin color scheme. Create a new'
                ' color scheme instead.'), show=True)
        li = self.colors_map[cs]
        d = CreateColorScheme(cs, li.data(Qt.UserRole), set(self.colors_map), edit_scheme=True, parent=self)
        if d.exec_() == d.Accepted:
            name, scheme = d.data
            li.setText(name)
            li.setData(Qt.UserRole, scheme)
            if name != cs:
                self.colors_map.pop(cs, None)
                self.insert_scheme(name, li)
            self.emit_changed()
            self.original_prefs['color_themes'] = self.current_prefs['color_themes']

    def remove_color_scheme(self):
        cs = self.current_colors
        if cs is None or not cs.startswith('#'):
            return error_dialog(self, _('Cannot remove'), _(
                'Cannot remove a builtin color scheme.'), show=True)
        for i in range(self.colors_list.count()):
            item = self.colors_list.item(i)
            if item.isSelected():
                with self:
                    del self.colors_map[item.text()]
                    self.colors_list.takeItem(i)
                    i = i % self.colors_list.count()
                    self.colors_list.item(i).setSelected(True)
                self.emit_changed()
                self.original_prefs['color_themes'] = self.current_prefs['color_themes']
                return

    def change_template(self, which):
        from calibre.gui2.dialogs.template_dialog import TemplateDialog
        from calibre.gui2.ui import get_gui
        gui = get_gui()
        if gui is None:
            from calibre.ebooks.metadata.book.base import field_metadata
        else:
            field_metadata = gui.current_db.new_api.field_metadata
        attr = which + '_template'
        templ = getattr(self, attr).text()
        d = TemplateDialog(self, templ, mi=self.mi, fm=field_metadata)
        if d.exec_() == d.Accepted:
            templ = d.rule[1]
            getattr(self, attr).setText(templ)
            self.emit_changed()

    @property
    def prefs_for_rendering(self):
        prefs = self.current_prefs
        prefs = override_prefs(prefs, override_style=self.current_style, override_color_theme=self.current_colors)
        return prefs

    def update_preview(self):
        if self.ignore_changed:
            return
        dpr = getattr(self, 'devicePixelRatioF', self.devicePixelRatio)()
        w, h = int(dpr * self.preview_label.sizeHint().width()), int(dpr * self.preview_label.sizeHint().height())
        prefs = self.prefs_for_rendering
        hr = h / prefs['cover_height']
        for x in ('title', 'subtitle', 'footer'):
            attr = '%s_font_size' % x
            prefs[attr] = int(prefs[attr] * hr)
        prefs['cover_width'], prefs['cover_height'] = w, h
        img = generate_cover(self.mi, prefs=prefs, as_qimage=True)
        img.setDevicePixelRatio(dpr)
        self.preview_label.setPixmap(QPixmap.fromImage(img))

    def default_mi(self):
        from calibre.ebooks.metadata.book.base import Metadata
        mi = Metadata(_('A sample book'), [_('Author One'), _('Author Two')])
        mi.series = _('A series of samples')
        mi.series_index = 4
        mi.tags = [_('Tag One'), _('Tag Two')]
        mi.publisher = _('Some publisher')
        mi.rating = 4
        mi.identifiers = {'isbn':'123456789', 'url': 'https://calibre-ebook.com'}
        mi.languages = ['eng', 'fra']
        mi.pubdate = mi.timestamp = now()
        return mi

    def restore_defaults(self):
        defaults = self.original_prefs.defaults.copy()
        # Dont delete custom color themes when restoring defaults
        defaults['color_themes'] = self.custom_colors
        self.apply_prefs(defaults)
        self.update_preview()

    def save_state(self):
        self.original_prefs.set('last_used_colors', self.current_colors)
        self.original_prefs.set('last_used_style', self.current_style)

    def save_as_prefs(self):
        with self.original_prefs:
            for k, v in iteritems(self.current_prefs):
                self.original_prefs[k] = v


class CoverSettingsDialog(QDialog):

    def __init__(self, mi=None, prefs=None, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('Cover generation settings'))
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)
        self.settings = CoverSettingsWidget(mi=mi, prefs=prefs, parent=self)
        l.addWidget(self.settings)
        self.save_settings = ss = QCheckBox(_('Save these settings as the &defaults for future use'))
        ss.setChecked(gprefs.get('cover_generation_save_settings_for_future', True))
        l.addWidget(ss)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        l.addWidget(bb)
        bb.accepted.connect(self.accept), bb.rejected.connect(self.reject)
        bb.b = b = bb.addButton(_('Restore &defaults'), bb.ActionRole)
        b.clicked.connect(self.restore_defaults)
        ss.setToolTip('<p>' + _(
            'Save the current settings as the settings to use always instead of just this time. Remember that'
            ' for styles and colors the actual style or color used is chosen at random from'
            ' the list of checked styles/colors.'))

        self.resize(self.sizeHint())
        geom = gprefs.get('cover_settings_dialog_geom', None)
        if geom is not None:
            QApplication.instance().safe_restore_geometry(self, geom)
        self.prefs_for_rendering = None

    def restore_defaults(self):
        self.settings.restore_defaults()
        self.settings.save_as_prefs()

    def _save_settings(self):
        gprefs.set('cover_generation_save_settings_for_future', self.save_settings.isChecked())
        gprefs.set('cover_settings_dialog_geom', bytearray(self.saveGeometry()))
        self.settings.save_state()

    def accept(self):
        self._save_settings()
        self.prefs_for_rendering = self.settings.prefs_for_rendering
        if self.save_settings.isChecked():
            self.settings.save_as_prefs()
        QDialog.accept(self)

    def reject(self):
        self._save_settings()
        QDialog.reject(self)


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = CoverSettingsDialog()
    d.show()
    app.exec_()
    del d
    del app
