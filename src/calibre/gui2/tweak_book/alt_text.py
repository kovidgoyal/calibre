#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import posixpath

from qt.core import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QIcon,
    QImageReader,
    QLabel,
    QPixmap,
    QPushButton,
    QSize,
    QSplitter,
    Qt,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from calibre import fit_image, prepare_string_for_xml
from calibre.ebooks.oeb.polish.alt_text import image_uses
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.utils.localization import _, ngettext

THUMBNAIL_SIZE = 64
PREVIEW_SIZE = 300
IMAGE, LOCATION, DECORATIVE, ALT = range(4)


def load_pixmap(path, size, dpr):
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    sz = reader.size()
    if sz.isValid():
        scaled, width, height = fit_image(sz.width(), sz.height(), int(size * dpr), int(size * dpr))
        if scaled:
            reader.setScaledSize(QSize(width, height))
    img = reader.read()
    if img.isNull():
        return QPixmap()
    ans = QPixmap.fromImage(img)
    ans.setDevicePixelRatio(dpr)
    return ans


class AltTextDialog(Dialog):
    def __init__(self, container, parent=None):
        self.container = container
        self.uses = image_uses(container)
        self.thumbnails = {}
        Dialog.__init__(self, _('Image descriptions'), 'image-alt-text', parent=parent)

    def sizeHint(self):
        return QSize(1000, 650)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(
            _(
                'Describe the images in the book for readers who cannot see them, such as people using screen'
                ' readers. Good descriptions are short and convey what the image shows in the context of the text.'
                ' Mark images that are purely decorative, such as ornaments and separators, as decorative, so'
                ' that screen readers skip them.'
            )
        )
        la.setWordWrap(True)
        l.addWidget(la)

        h = QHBoxLayout()
        self.only_missing = om = QCheckBox(_('Show only images &without a description'))
        om.toggled.connect(self.apply_filter)
        h.addWidget(om)
        h.addStretch(10)
        self.summary = QLabel(self)
        h.addWidget(self.summary)
        l.addLayout(h)

        self.splitter = s = QSplitter(self)
        l.addWidget(s, stretch=10)
        self.table = t = QTableWidget(len(self.uses), 4, self)
        t.setHorizontalHeaderLabels([_('Image'), _('Location'), _('Decorative'), _('Description (alternative text)')])
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        t.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        t.setIconSize(QSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE))
        t.setWordWrap(True)
        vh = t.verticalHeader()
        assert vh is not None
        vh.setVisible(False)
        vh.setDefaultSectionSize(THUMBNAIL_SIZE + 8)
        hh = t.horizontalHeader()
        assert hh is not None
        hh.setSectionResizeMode(ALT, QHeaderView.ResizeMode.Stretch)
        self.populate()
        self.initial_states = [self.row_state(row) for row in range(len(self.uses))]
        t.resizeColumnsToContents()
        t.setColumnWidth(IMAGE, min(t.columnWidth(IMAGE), 250))
        t.setColumnWidth(LOCATION, min(t.columnWidth(LOCATION), 200))
        t.itemChanged.connect(self.item_changed)
        t.currentCellChanged.connect(self.current_changed)
        s.addWidget(t)

        self.preview_panel = p = QWidget(self)
        pl = QVBoxLayout(p)
        pl.setContentsMargins(0, 0, 0, 0)
        self.preview = pv = QLabel(p)
        pv.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pv.setMinimumSize(PREVIEW_SIZE // 2, PREVIEW_SIZE // 2)
        pl.addWidget(pv)
        self.image_name_label = la = QLabel(p)
        la.setWordWrap(True)
        la.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        pl.addWidget(la)
        self.context_label = la = QLabel(p)
        la.setWordWrap(True)
        la.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        la.setAlignment(Qt.AlignmentFlag.AlignTop)
        pl.addWidget(la, stretch=10)
        self.apply_to_all_button = b = QPushButton(_('&Use for all uses of this image'), p)
        b.setToolTip(_('Use the description of the current image for every other place in the book where the same image is used'))
        b.clicked.connect(self.apply_to_all_uses)
        pl.addWidget(b)
        s.addWidget(p)
        s.setStretchFactor(0, 10)
        s.setStretchFactor(1, 1)
        s.setChildrenCollapsible(False)

        l.addWidget(self.bb)
        self.update_summary()
        if self.uses:
            t.setCurrentCell(0, ALT)
        else:
            self.current_changed(-1)

    def thumbnail(self, image_name):
        if image_name not in self.thumbnails:
            pmap = QPixmap()
            if image_name is not None:
                pmap = load_pixmap(self.container.name_to_abspath(image_name), THUMBNAIL_SIZE, self.devicePixelRatioF())
            self.thumbnails[image_name] = QIcon(pmap) if not pmap.isNull() else QIcon()
        return self.thumbnails[image_name]

    def populate(self):
        t = self.table
        ro = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        for row, use in enumerate(self.uses):
            i = QTableWidgetItem(self.thumbnail(use.image_name), posixpath.basename(use.image_name) if use.image_name else _('Missing image'))
            i.setFlags(ro)
            i.setToolTip(use.image_name or '')
            t.setItem(row, IMAGE, i)
            i = QTableWidgetItem(use.html_name)
            i.setFlags(ro)
            if use.sourceline:
                i.setToolTip(_('{0}, line {1}').format(use.html_name, use.sourceline))
            t.setItem(row, LOCATION, i)
            i = QTableWidgetItem()
            i.setFlags(ro | Qt.ItemFlag.ItemIsUserCheckable)
            i.setCheckState(Qt.CheckState.Checked if use.alt == '' else Qt.CheckState.Unchecked)
            i.setToolTip(_('Decorative images are skipped by screen readers'))
            t.setItem(row, DECORATIVE, i)
            i = QTableWidgetItem(use.alt or '')
            i.setFlags(ro if use.alt == '' else ro | Qt.ItemFlag.ItemIsEditable)
            t.setItem(row, ALT, i)

    def item(self, row, col) -> QTableWidgetItem:
        ans = self.table.item(row, col)
        assert ans is not None
        return ans

    def is_decorative(self, row):
        return self.item(row, DECORATIVE).checkState() == Qt.CheckState.Checked

    def alt_for_row(self, row):
        if self.is_decorative(row):
            return ''
        return ' '.join(self.item(row, ALT).text().split()) or None

    def set_row(self, row, decorative, text):
        t = self.table
        t.blockSignals(True)
        try:
            self.item(row, DECORATIVE).setCheckState(Qt.CheckState.Checked if decorative else Qt.CheckState.Unchecked)
            ai = self.item(row, ALT)
            ai.setText('' if decorative else text)
            flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            ai.setFlags(flags if decorative else flags | Qt.ItemFlag.ItemIsEditable)
        finally:
            t.blockSignals(False)

    def item_changed(self, item):
        row, col = item.row(), item.column()
        if col == DECORATIVE:
            self.set_row(row, self.is_decorative(row), self.item(row, ALT).text())
        self.update_summary()

    def update_summary(self):
        missing = sum(1 for row in range(len(self.uses)) if self.alt_for_row(row) is None)
        total = ngettext('One image', '{} images', len(self.uses)).format(len(self.uses))
        self.summary.setText(ngettext('{0}, one without a description', '{0}, {1} without a description', missing).format(total, missing))

    def apply_filter(self):
        only_missing = self.only_missing.isChecked()
        for row, use in enumerate(self.uses):
            self.table.setRowHidden(row, only_missing and use.alt is not None)

    def current_changed(self, row, *a):
        use = self.uses[row] if 0 <= row < len(self.uses) else None
        self.apply_to_all_button.setEnabled(use is not None and use.image_name is not None)
        if use is None:
            self.preview.clear()
            self.image_name_label.clear()
            self.context_label.clear()
            return
        pmap = QPixmap()
        if use.image_name is not None:
            pmap = load_pixmap(self.container.name_to_abspath(use.image_name), PREVIEW_SIZE, self.devicePixelRatioF())
        if pmap.isNull():
            self.preview.setText(_('No preview available'))
        else:
            self.preview.setPixmap(pmap)
        self.image_name_label.setText(use.image_name or _('The image file is missing'))
        if use.context:
            self.context_label.setText('<p><b>{}</b></p><p>{}</p>'.format(_('Text near the image:'), prepare_string_for_xml(use.context)))
        else:
            self.context_label.setText('')

    def apply_to_all_uses(self):
        row = self.table.currentRow()
        if not 0 <= row < len(self.uses):
            return
        image_name = self.uses[row].image_name
        decorative, text = self.row_state(row)
        for other, use in enumerate(self.uses):
            if other != row and use.image_name == image_name:
                self.set_row(other, decorative, text)
        self.update_summary()

    def row_state(self, row):
        return self.is_decorative(row), self.item(row, ALT).text()

    @property
    def changes(self):
        # Only rows the user changed, so that existing alternative text is left as is
        ans = {}
        for row, use in enumerate(self.uses):
            if self.row_state(row) != self.initial_states[row]:
                alt = self.alt_for_row(row)
                if alt != use.alt:
                    ans[(use.html_name, use.index)] = alt
        return ans


if __name__ == '__main__':
    import sys

    from calibre.ebooks.oeb.polish.container import get_container
    from calibre.gui2 import Application

    app = Application([])
    d = AltTextDialog(get_container(sys.argv[-1], tweak_mode=True))
    d.exec()
    print(d.changes)
    del app
