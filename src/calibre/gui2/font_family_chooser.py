#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import (QFontInfo, QFontMetrics, Qt, QFont, QFontDatabase, QPen,
        QStyledItemDelegate, QSize, QStyle, QComboBox, QStringListModel,
        QDialog, QVBoxLayout, QApplication, QFontComboBox)

from calibre.utils.icu import sort_key

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
            painter.setBrush(option.palette.highlight())
            painter.setPen(Qt.NoPen)
            painter.drawRect(option.rect)
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

class FontFamilyChooser(QComboBox):

    def __init__(self, parent=None):
        QComboBox.__init__(self, parent)
        from calibre.utils.fonts import fontconfig
        try:
            ok, self.families = fontconfig.find_font_families_no_delay()
        except:
            self.families = []
            print ('WARNING: Could not load fonts')
            import traceback
            traceback.print_exc()
        # Restrict to Qt families as we need the font to be available in
        # QFontDatabase
        qt_families = set([unicode(x) for x in QFontDatabase().families()])
        self.families = list(qt_families.intersection(set(self.families)))
        self.families.sort(key=sort_key)
        self.families.insert(0, _('None'))

        self.m = QStringListModel(self.families)
        self.setModel(self.m)
        self.d = FontFamilyDelegate(self)
        self.setItemDelegate(self.d)
        self.setCurrentIndex(0)

    def event(self, e):
        if e.type() == e.Resize:
            view = self.view()
            view.window().setFixedWidth(self.width() * 5/3)
        return QComboBox.event(self, e)

    def sizeHint(self):
        ans = QComboBox.sizeHint(self)
        try:
            ans.setWidth(QFontMetrics(self.font()).width('m'*14))
        except:
            pass
        return ans

    @dynamic_property
    def font_family(self):
        def fget(self):
            idx=  self.currentIndex()
            if idx == 0: return None
            return self.families[idx]
        def fset(self, val):
            if not val:
                idx = 0
            try:
                idx = self.families.index(type(u'')(val))
            except ValueError:
                idx = 0
            self.setCurrentIndex(idx)
        return property(fget=fget, fset=fset)

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

