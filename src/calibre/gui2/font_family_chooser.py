#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil

from PyQt4.Qt import (QFontInfo, QFontMetrics, Qt, QFont, QFontDatabase, QPen,
        QStyledItemDelegate, QSize, QStyle, QStringListModel, pyqtSignal,
        QDialog, QVBoxLayout, QApplication, QFontComboBox, QPushButton,
        QToolButton, QGridLayout, QListView, QWidget, QDialogButtonBox, QIcon,
        QHBoxLayout, QLabel, QModelIndex)

from calibre.constants import config_dir
from calibre.gui2 import choose_files, error_dialog, info_dialog

def writing_system_for_font(font):
    has_latin = True
    systems = QFontDatabase().writingSystems(font.family())

    # this just confuses the algorithm below. Vietnamese is Latin with lots of
    # special chars
    try:
        systems.remove(QFontDatabase.Vietnamese)
    except ValueError:
        pass

    system = QFontDatabase.Any

    if (QFontDatabase.Latin not in systems):
        has_latin = False
        # we need to show something
        if systems:
            system = systems[-1]
    else:
        systems.remove(QFontDatabase.Latin)

    if not systems:
        return system, has_latin

    if (len(systems) == 1 and systems[0] > QFontDatabase.Cyrillic):
        return systems[0], has_latin

    if (len(systems) <= 2 and
        systems[-1] > QFontDatabase.Armenian and
        systems[-1] < QFontDatabase.Vietnamese):
        return systems[-1], has_latin

    if (len(systems) <= 5 and
        systems[-1] >= QFontDatabase.SimplifiedChinese and
        systems[-1] <= QFontDatabase.Korean):
        system = systems[-1]

    return system, has_latin

class FontFamilyDelegate(QStyledItemDelegate):

    def sizeHint(self, option, index):
        try:
            return self.do_size_hint(option, index)
        except:
            return QSize(300, 50)

    def do_size_hint(self, option, index):
        text = index.data(Qt.DisplayRole).toString()
        font = QFont(option.font)
        font.setPointSize(QFontInfo(font).pointSize() * 1.5)
        m = QFontMetrics(font)
        return QSize(m.width(text), m.height())

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, QModelIndex())
        painter.save()
        try:
            self.do_paint(painter, option, index)
        except:
            pass
        painter.restore()

    def do_paint(self, painter, option, index):
        text = unicode(index.data(Qt.DisplayRole).toString())
        font = QFont(option.font)
        font.setPointSize(QFontInfo(font).pointSize() * 1.5)
        font2 = QFont(font)
        font2.setFamily(text)

        system, has_latin = writing_system_for_font(font2)
        if has_latin:
            font = font2

        r = option.rect

        if option.state & QStyle.State_Selected:
            painter.setPen(QPen(option.palette.highlightedText(), 0))

        if (option.direction == Qt.RightToLeft):
            r.setRight(r.right() - 4)
        else:
            r.setLeft(r.left() + 4)

        painter.setFont(font)
        painter.drawText(r, Qt.AlignVCenter|Qt.AlignLeading|Qt.TextSingleLine, text)

        if (system != QFontDatabase.Any):
            w = painter.fontMetrics().width(text + "  ")
            painter.setFont(font2)
            sample = QFontDatabase().writingSystemSample(system)
            if (option.direction == Qt.RightToLeft):
                r.setRight(r.right() - w)
            else:
                r.setLeft(r.left() + w)
            painter.drawText(r, Qt.AlignVCenter|Qt.AlignLeading|Qt.TextSingleLine, sample)

class Typefaces(QLabel):

    def __init__(self, parent=None):
        QLabel.__init__(self, parent)
        self.setMinimumWidth(400)
        self.base_msg = '<h3>'+_('Choose a font family')+'</h3>'
        self.setText(self.base_msg)
        self.setWordWrap(True)

    def show_family(self, family, faces):
        if not family:
            self.setText(self.base_msg)
            return
        msg = '''
        <h3>%s</h3>
        <dl style="font-size: smaller">
        {0}
        </dl>
        '''%(_('Available faces for %s')%family)
        entries = []
        for font in faces:
            sf = (font['wws_subfamily_name'] or font['preferred_subfamily_name']
                or font['subfamily_name'])
            entries.append('''
            <dt><b>{sf}</b></dt>
            <dd>font-stretch: <i>{width}</i> font-weight: <i>{weight}</i> font-style:
            <i>{style}</i></dd>

            '''.format(sf=sf, width=font['font-stretch'],
                    weight=font['font-weight'], style=font['font-style']))
        msg = msg.format('\n\n'.join(entries))
        self.setText(msg)

class FontsView(QListView):

    changed = pyqtSignal()

    def __init__(self, parent):
        QListView.__init__(self, parent)
        self.setSelectionMode(self.SingleSelection)
        self.setAlternatingRowColors(True)
        self.d = FontFamilyDelegate(self)
        self.setItemDelegate(self.d)

    def currentChanged(self, current, previous):
        self.changed.emit()
        QListView.currentChanged(self, current, previous)


class FontFamilyDialog(QDialog):

    def __init__(self, current_family, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('Choose font family'))
        self.setWindowIcon(QIcon(I('font.png')))
        from calibre.utils.fonts.scanner import font_scanner
        self.font_scanner = font_scanner

        self.m = QStringListModel(self)
        self.build_font_list()
        self.l = l = QGridLayout()
        self.setLayout(l)
        self.view = FontsView(self)
        self.view.setModel(self.m)
        self.view.setCurrentIndex(self.m.index(0))
        if current_family:
            for i, val in enumerate(self.families):
                if icu_lower(val) == icu_lower(current_family):
                    self.view.setCurrentIndex(self.m.index(i))
                    break
        self.view.doubleClicked.connect(self.accept, type=Qt.QueuedConnection)
        self.view.changed.connect(self.current_changed,
                type=Qt.QueuedConnection)
        self.faces = Typefaces(self)
        self.bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        self.add_fonts_button = afb = self.bb.addButton(_('Add &fonts'),
                self.bb.ActionRole)
        afb.setIcon(QIcon(I('plus.png')))
        afb.clicked.connect(self.add_fonts)
        self.ml = QLabel(_('Choose a font family from the list below:'))

        l.addWidget(self.ml, 0, 0, 1, 2)
        l.addWidget(self.view, 1, 0, 1, 1)
        l.addWidget(self.faces, 1, 1, 1, 1)
        l.addWidget(self.bb, 2, 0, 1, 2)
        l.setAlignment(self.faces, Qt.AlignTop)

        self.resize(800, 600)

    def build_font_list(self):
        try:
            self.families = list(self.font_scanner.find_font_families())
        except:
            self.families = []
            print ('WARNING: Could not load fonts')
            import traceback
            traceback.print_exc()
        self.families.insert(0, _('None'))
        self.m.setStringList(self.families)

    def add_fonts(self):
        from calibre.utils.fonts.metadata import FontMetadata
        files = choose_files(self, 'add fonts to calibre',
                _('Select font files'), filters=[(_('TrueType/OpenType Fonts'),
                    ['ttf', 'otf'])], all_files=False)
        if not files: return
        families = set()
        for f in files:
            try:
                with open(f, 'rb') as stream:
                    fm = FontMetadata(stream)
            except:
                import traceback
                error_dialog(self, _('Corrupt font'),
                        _('Failed to read metadata from the font file: %s')%
                        f, det_msg=traceback.format_exc(), show=True)
                return
            families.add(fm.font_family)
        families = sorted(families)

        dest = os.path.join(config_dir, 'fonts')
        for f in files:
            shutil.copyfile(f, os.path.join(dest, os.path.basename(f)))
        self.font_scanner.do_scan()
        self.build_font_list()
        self.m.reset()
        self.view.setCurrentIndex(self.m.index(0))
        if families:
            for i, val in enumerate(self.families):
                if icu_lower(val) == icu_lower(families[0]):
                    self.view.setCurrentIndex(self.m.index(i))
                    break

        info_dialog(self, _('Added fonts'),
                _('Added font families: %s')%(
                    ', '.join(families)), show=True)

    @property
    def font_family(self):
        idx = self.view.currentIndex().row()
        if idx == 0: return None
        return self.families[idx]

    def current_changed(self):
        fam = self.font_family
        self.faces.show_family(fam, self.font_scanner.fonts_for_family(fam)
                if fam else None)

class FontFamilyChooser(QWidget):

    family_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QHBoxLayout()
        self.setLayout(l)
        self.button = QPushButton(self)
        self.button.setIcon(QIcon(I('font.png')))
        l.addWidget(self.button)
        self.default_text = _('Choose &font family')
        self.font_family = None
        self.button.clicked.connect(self.show_chooser)
        self.clear_button = QToolButton(self)
        self.clear_button.setIcon(QIcon(I('clear_left.png')))
        self.clear_button.clicked.connect(self.clear_family)
        l.addWidget(self.clear_button)
        self.setToolTip = self.button.setToolTip
        self.toolTip = self.button.toolTip
        self.clear_button.setToolTip(_('Clear the font family'))

    def clear_family(self):
        self.font_family = None

    @dynamic_property
    def font_family(self):
        def fget(self):
            return self._current_family
        def fset(self, val):
            if not val:
                val = None
            self._current_family = val
            self.button.setText(val or self.default_text)
            self.family_changed.emit(val)
        return property(fget=fget, fset=fset)

    def show_chooser(self):
        d = FontFamilyDialog(self.font_family, self)
        if d.exec_() == d.Accepted:
            self.font_family = d.font_family

def test():
    app = QApplication([])
    app
    d = QDialog()
    d.setLayout(QVBoxLayout())
    d.layout().addWidget(FontFamilyChooser(d))
    d.layout().addWidget(QFontComboBox(d))
    d.exec_()

if __name__ == '__main__':
    test()

