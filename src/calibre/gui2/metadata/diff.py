#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os
from collections import OrderedDict, namedtuple
from functools import partial
from future_builtins import zip

from PyQt4.Qt import (
    QDialog, QWidget, QGridLayout, QLineEdit, QLabel, QToolButton, QIcon,
    QVBoxLayout, QDialogButtonBox, QApplication, pyqtSignal, QFont, QPixmap,
    QSize, QPainter, Qt, QColor, QPen, QSizePolicy, QScrollArea, QFrame)

from calibre import fit_image
from calibre.ebooks.metadata import title_sort, authors_to_sort_string
from calibre.gui2 import pixmap_to_data, gprefs
from calibre.gui2.comments_editor import Editor
from calibre.gui2.languages import LanguagesEdit as LE
from calibre.gui2.metadata.basic_widgets import PubdateEdit, RatingEdit
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.date import UNDEFINED_DATE

Widgets = namedtuple('Widgets', 'new old label button')

# Widgets {{{

class LineEdit(QLineEdit):

    changed = pyqtSignal()

    def __init__(self, field, is_new, parent, metadata, extra):
        QLineEdit.__init__(self, parent)
        self.is_new = is_new
        self.field = field
        self.metadata = metadata
        if not is_new:
            self.setReadOnly(True)
        self.textChanged.connect(self.changed)

    def from_mi(self, mi):
        val = mi.get(self.field, default='') or ''
        ism = self.metadata['is_multiple']
        if ism:
            if not val:
                val = ''
            else:
                val = ism['list_to_ui'].join(val)
        self.setText(val)
        self.setCursorPosition(0)

    def to_mi(self, mi):
        val = unicode(self.text()).strip()
        ism = self.metadata['is_multiple']
        if ism:
            if not val:
                val = []
            else:
                val = [x.strip() for x in val.split(ism['list_to_ui']) if x.strip()]
        mi.set(self.field, val)
        if self.field == 'title':
            mi.set('title_sort', title_sort(val, lang=mi.language))
        elif self.field == 'authors':
            mi.set('author_sort', authors_to_sort_string(val))

    @dynamic_property
    def current_val(self):
        def fget(self):
            return unicode(self.text())
        def fset(self, val):
            self.setText(val)
            self.setCursorPosition(0)
        return property(fget=fget, fset=fset)

    @property
    def is_blank(self):
        val = self.current_val.strip()
        if self.field in {'title', 'authors'}:
            return val in {'', _('Unknown')}
        return not val

    def same_as(self, other):
        return self.current_val == other.current_val

class LanguagesEdit(LE):

    changed = pyqtSignal()

    def __init__(self, field, is_new, parent, metadata, extra):
        LE.__init__(self, parent=parent)
        self.is_new = is_new
        self.field = field
        self.metadata = metadata
        self.textChanged.connect(self.changed)
        if not is_new:
            self.lineEdit().setReadOnly(True)

    @dynamic_property
    def current_val(self):
        def fget(self):
            return self.lang_codes
        def fset(self, val):
            self.lang_codes = val
        return property(fget=fget, fset=fset)

    def from_mi(self, mi):
        self.lang_codes = mi.languages

    def to_mi(self, mi):
        mi.languages = self.lang_codes

    @property
    def is_blank(self):
        return not self.current_val

    def same_as(self, other):
        return self.current_val == other.current_val

class RatingsEdit(RatingEdit):

    changed = pyqtSignal()

    def __init__(self, field, is_new, parent, metadata, extra):
        RatingEdit.__init__(self, parent)
        self.is_new = is_new
        self.field = field
        self.metadata = metadata
        self.valueChanged.connect(self.changed)
        if not is_new:
            self.setReadOnly(True)

    def from_mi(self, mi):
        val = (mi.get(self.field, default=0) or 0)/2
        self.setValue(val)

    def to_mi(self, mi):
        mi.set(self.field, self.value() * 2)

    @property
    def is_blank(self):
        return self.value() == 0

    def same_as(self, other):
        return self.current_val == other.current_val

class DateEdit(PubdateEdit):

    changed = pyqtSignal()

    def __init__(self, field, is_new, parent, metadata, extra):
        PubdateEdit.__init__(self, parent, create_clear_button=False)
        self.is_new = is_new
        self.field = field
        self.metadata = metadata
        self.setDisplayFormat(extra)
        self.dateTimeChanged.connect(self.changed)
        if not is_new:
            self.setReadOnly(True)

    def from_mi(self, mi):
        self.current_val = mi.get(self.field, default=None)

    def to_mi(self, mi):
        mi.set(self.field, self.current_val)

    @property
    def is_blank(self):
        return self.current_val.year <= UNDEFINED_DATE.year

    def same_as(self, other):
        return self.text() == other.text()

class SeriesEdit(LineEdit):

    def from_mi(self, mi):
        series = mi.get(self.field, default='')
        series_index = mi.get(self.field + '_index', default=1.0)
        val = ''
        if series:
            val = '%s [%s]' % (series, mi.format_series_index(series_index))
        self.setText(val)
        self.setCursorPosition(0)

    def to_mi(self, mi):
        val = unicode(self.text()).strip()
        try:
            series_index = float(val.rpartition('[')[-1].rstrip(']').strip())
        except:
            series_index = 1.0
        series = val.rpartition('[')[0].strip() or None
        mi.set(self.field, series)
        mi.set(self.field + '_index', series_index)

class IdentifiersEdit(LineEdit):

    def from_mi(self, mi):
        val = ('%s:%s' % (k, v) for k, v in mi.identifiers.iteritems())
        self.setText(', '.join(val))
        self.setCursorPosition(0)

    def to_mi(self, mi):
        parts = (x.strip() for x in self.current_val.split(',') if x.strip())
        val = {x.partition(':')[0].strip():x.partition(':')[-1].strip() for x in parts}
        mi.set_identifiers({k:v for k, v in val.iteritems() if k and v})

class CommentsEdit(Editor):

    changed = pyqtSignal()

    def __init__(self, field, is_new, parent, metadata, extra):
        Editor.__init__(self, parent, one_line_toolbar=False)
        self.is_new = is_new
        self.field = field
        self.metadata = metadata
        self.hide_tabs()
        if not is_new:
            self.hide_toolbars()
            self.set_readonly(True)

    @dynamic_property
    def current_val(self):
        def fget(self):
            return self.html
        def fset(self, val):
            self.html = val or ''
            self.changed.emit()
        return property(fget=fget, fset=fset)

    def from_mi(self, mi):
        val = mi.get(self.field, default='')
        self.current_val = val

    def to_mi(self, mi):
        mi.set(self.field, self.current_val)

    def sizeHint(self):
        return QSize(450, 200)

    @property
    def is_blank(self):
        return not self.current_val.strip()

    def same_as(self, other):
        return self.current_val == other.current_val

class CoverView(QWidget):

    changed = pyqtSignal()

    def __init__(self, field, is_new, parent, metadata, extra):
        QWidget.__init__(self, parent)
        self.is_new = is_new
        self.field = field
        self.metadata = metadata
        self.pixmap = None
        self.blank = QPixmap(I('blank.png'))
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.GrowFlag|QSizePolicy.ExpandFlag)
        self.sizePolicy().setHeightForWidth(True)

    @property
    def is_blank(self):
        return self.pixmap is None

    @dynamic_property
    def current_val(self):
        def fget(self):
            return self.pixmap
        def fset(self, val):
            self.pixmap = val
            self.changed.emit()
            self.update()
        return property(fget=fget, fset=fset)

    def from_mi(self, mi):
        p = getattr(mi, 'cover', None)
        if p and os.path.exists(p):
            pmap = QPixmap()
            with open(p, 'rb') as f:
                pmap.loadFromData(f.read())
            if not pmap.isNull():
                self.pixmap = pmap
                self.update()
                self.changed.emit()
                return
        cd = getattr(mi, 'cover_data', (None, None))
        if cd and cd[1]:
            pmap = QPixmap()
            pmap.loadFromData(cd[1])
            if not pmap.isNull():
                self.pixmap = pmap
                self.update()
                self.changed.emit()
                return
        self.pixmap = None
        self.update()
        self.changed.emit()

    def to_mi(self, mi):
        mi.cover, mi.cover_data = None, (None, None)
        if self.pixmap is not None and not self.pixmap.isNull():
            with PersistentTemporaryFile('.jpg') as pt:
                pt.write(pixmap_to_data(self.pixmap))
                mi.cover = pt.name

    def same_as(self, other):
        return self.current_val == other.current_val

    def sizeHint(self):
        return QSize(225, 300)

    def paintEvent(self, event):
        pmap = self.blank if self.pixmap is None or self.pixmap.isNull() else self.pixmap
        target = self.rect()
        scaled, width, height = fit_image(pmap.width(), pmap.height(), target.width(), target.height())
        target.setRect(target.x(), target.y(), width, height)
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        p.drawPixmap(target, pmap)

        if self.pixmap is not None and not self.pixmap.isNull():
            sztgt = target.adjusted(0, 0, 0, -4)
            f = p.font()
            f.setBold(True)
            p.setFont(f)
            sz = u'\u00a0%d x %d\u00a0'%(self.pixmap.width(), self.pixmap.height())
            flags = Qt.AlignBottom|Qt.AlignRight|Qt.TextSingleLine
            szrect = p.boundingRect(sztgt, flags, sz)
            p.fillRect(szrect.adjusted(0, 0, 0, 4), QColor(0, 0, 0, 200))
            p.setPen(QPen(QColor(255,255,255)))
            p.drawText(sztgt, flags, sz)
        p.end()
# }}}

class CompareSingle(QWidget):

    def __init__(
            self, field_metadata, parent=None, revert_tooltip=None,
            datetime_fmt='MMMM yyyy', blank_as_equal=True,
            fields=('title', 'authors', 'series', 'tags', 'rating', 'publisher', 'pubdate', 'identifiers', 'languages', 'comments', 'cover')):
        QWidget.__init__(self, parent)
        self.l = l = QGridLayout()
        l.setContentsMargins(0, 0, 0, 0)
        self.setLayout(l)
        revert_tooltip = revert_tooltip or _('Revert %s')
        self.current_mi = None
        self.changed_font = QFont(QApplication.font())
        self.changed_font.setBold(True)
        self.changed_font.setItalic(True)
        self.blank_as_equal = blank_as_equal

        self.widgets = OrderedDict()
        row = 0

        for field in fields:
            m = field_metadata[field]
            dt = m['datatype']
            extra = None
            if 'series' in {field, dt}:
                cls = SeriesEdit
            elif field == 'identifiers':
                cls = IdentifiersEdit
            elif field == 'languages':
                cls = LanguagesEdit
            elif 'comments' in {field, dt}:
                cls = CommentsEdit
            elif 'rating' in {field, dt}:
                cls = RatingsEdit
            elif dt == 'datetime':
                extra = datetime_fmt
                cls = DateEdit
            elif field == 'cover':
                cls = CoverView
            elif dt in {'text', 'enum'}:
                cls = LineEdit
            else:
                continue
            neww = cls(field, True, self, m, extra)
            neww.changed.connect(partial(self.changed, field))
            oldw = cls(field, False, self, m, extra)
            newl = QLabel('&%s:' % m['name'])
            newl.setBuddy(neww)
            button = QToolButton(self)
            button.setIcon(QIcon(I('back.png')))
            button.clicked.connect(partial(self.revert, field))
            button.setToolTip(revert_tooltip % m['name'])
            self.widgets[field] = Widgets(neww, oldw, newl, button)
            for i, w in enumerate((newl, neww, button, oldw)):
                c = i if i < 2 else i + 1
                if w is oldw:
                    c += 1
                l.addWidget(w, row, c)
            row += 1

        self.sep = f = QFrame(self)
        f.setFrameShape(f.VLine)
        l.addWidget(f, 0, 2, row, 1)
        self.sep2 = f = QFrame(self)
        f.setFrameShape(f.VLine)
        l.addWidget(f, 0, 4, row, 1)

    def changed(self, field):
        w = self.widgets[field]
        if not w.new.same_as(w.old) and (not self.blank_as_equal or not w.new.is_blank):
            w.label.setFont(self.changed_font)
        else:
            w.label.setFont(QApplication.font())

    def revert(self, field):
        widgets = self.widgets[field]
        neww, oldw = widgets[:2]
        neww.current_val = oldw.current_val

    def __call__(self, oldmi, newmi):
        self.current_mi = newmi
        self.initial_vals = {}
        for field, widgets in self.widgets.iteritems():
            widgets.old.from_mi(oldmi)
            widgets.new.from_mi(newmi)
            self.initial_vals[field] = widgets.new.current_val

    def apply_changes(self):
        changed = False
        for field, widgets in self.widgets.iteritems():
            val = widgets.new.current_val
            if val != self.initial_vals[field]:
                widgets.new.to_mi(self.current_mi)
                changed = True
        return changed

class CompareMany(QDialog):

    def __init__(self, ids, get_metadata, field_metadata, parent=None,
                 window_title=None,
                 reject_button_tooltip=None,
                 accept_all_tooltip=None,
                 reject_all_tooltip=None,
                 revert_tooltip=None,
                 intro_msg=None,
                 **kwargs):
        QDialog.__init__(self, parent)
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        self.setWindowIcon(QIcon(I('auto_author_sort.png')))
        self.get_metadata = get_metadata
        self.ids = list(ids)
        self.total = len(self.ids)
        self.accepted = OrderedDict()
        self.window_title = window_title or _('Compare metadata')

        if intro_msg:
            self.la = la = QLabel(intro_msg)
            la.setWordWrap(True)
            l.addWidget(la)

        self.compare_widget = CompareSingle(field_metadata, parent=parent, revert_tooltip=revert_tooltip, **kwargs)
        self.sa = sa = QScrollArea()
        l.addWidget(sa)
        sa.setWidget(self.compare_widget)
        sa.setWidgetResizable(True)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        bb.rejected.connect(self.reject)
        if self.total > 1:
            self.aarb = b = bb.addButton(_('&Accept all remaining'), bb.YesRole)
            b.setIcon(QIcon(I('ok.png')))
            if accept_all_tooltip:
                b.setToolTip(accept_all_tooltip)
            b.clicked.connect(self.accept_all_remaining)
            self.rarb = b = bb.addButton(_('Re&ject all remaining'), bb.NoRole)
            b.setIcon(QIcon(I('minus.png')))
            if reject_all_tooltip:
                b.setToolTip(reject_all_tooltip)
            b.clicked.connect(self.reject_all_remaining)
            self.sb = b = bb.addButton(_('&Reject'), bb.ActionRole)
            b.clicked.connect(partial(self.next_item, False))
            b.setIcon(QIcon(I('minus.png')))
            if reject_button_tooltip:
                b.setToolTip(reject_button_tooltip)
        self.nb = b = bb.addButton(_('&Next') if self.total > 1 else _('&OK'), bb.ActionRole)
        b.setIcon(QIcon(I('forward.png' if self.total > 1 else 'ok.png')))
        b.clicked.connect(partial(self.next_item, True))
        b.setDefault(True)
        l.addWidget(bb)

        self.next_item(True)

        desktop = QApplication.instance().desktop()
        geom = desktop.availableGeometry(parent or self)
        width = max(700, min(950, geom.width()-50))
        height = max(650, min(1000, geom.height()-100))
        self.resize(QSize(width, height))
        geom = gprefs.get('diff_dialog_geom', None)
        if geom is not None:
            self.restoreGeometry(geom)
        b.setFocus(Qt.OtherFocusReason)

    def accept(self):
        gprefs.set('diff_dialog_geom', bytearray(self.saveGeometry()))
        super(CompareMany, self).accept()

    def reject(self):
        gprefs.set('diff_dialog_geom', bytearray(self.saveGeometry()))
        super(CompareMany, self).reject()

    @property
    def current_mi(self):
        return self.compare_widget.current_mi

    def next_item(self, accept):
        if not self.ids:
            return self.accept()
        if self.current_mi is not None:
            changed = self.compare_widget.apply_changes()
        if self.current_mi is not None:
            old_id = self.ids.pop(0)
            self.accepted[old_id] = (changed, self.current_mi) if accept else (False, None)
        if not self.ids:
            return self.accept()
        self.setWindowTitle(self.window_title + _(' [%(num)d of %(tot)d]') % dict(
            num=(self.total - len(self.ids) + 1), tot=self.total))
        oldmi, newmi = self.get_metadata(self.ids[0])
        self.compare_widget(oldmi, newmi)

    def accept_all_remaining(self):
        self.next_item(True)
        for id_ in self.ids:
            oldmi, newmi = self.get_metadata(id_)
            self.accepted[id_] = (False, newmi)
        self.ids = []
        self.accept()

    def reject_all_remaining(self):
        self.next_item(False)
        for id_ in self.ids:
            oldmi, newmi = self.get_metadata(id_)
            self.accepted[id_] = (False, None)
        self.ids = []
        self.accept()

if __name__ == '__main__':
    app = QApplication([])
    from calibre.library import db
    db = db()
    ids = sorted(db.all_ids(), reverse=True)
    ids = tuple(zip(ids[0::2], ids[1::2]))
    gm = partial(db.get_metadata, index_is_id=True, get_cover=True, cover_as_data=True)
    get_metadata = lambda x:map(gm, ids[x])
    d = CompareMany(list(xrange(len(ids))), get_metadata, db.field_metadata)
    if d.exec_() == d.Accepted:
        for changed, mi in d.accepted.itervalues():
            if changed and mi is not None:
                print (mi)

