#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import posixpath
from copy import deepcopy

from lxml import etree
from qt.core import (
    QAbstractItemView,
    QBuffer,
    QByteArray,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QIcon,
    QImageReader,
    QIODevice,
    QLabel,
    QLineEdit,
    QPixmap,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSize,
    QSplitter,
    Qt,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from calibre import fit_image, prepare_string_for_xml
from calibre.ebooks.oeb.base import SVG, XLINK
from calibre.ebooks.oeb.polish.accessibility import (
    ABSENT,
    ACCESS_MODE,
    ACCESS_MODE_SUFFICIENT,
    ACCESS_MODES,
    CERTIFIED_BY,
    CONFORMANCE,
    CONFORMS_TO,
    FEATURE,
    FEATURES,
    HAZARD,
    HAZARDS,
    HTML_LANGUAGE_ALL,
    HTML_LANGUAGE_MISSING,
    PRESENT,
    SUFFICIENT_ACCESS_MODES,
    SUMMARY,
    UNKNOWN,
    AccessibilityChanges,
    ImageUse,
    book_languages,
    hazard_states,
    hazard_values,
    html_files_without_language,
    html_names,
    image_elements,
    image_uses,
    read_accessibility_metadata,
    svg_alt_text,
)
from calibre.ebooks.oeb.polish.container import Container
from calibre.gui2 import error_dialog
from calibre.gui2.languages import LanguagesEdit
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.utils.localization import _, ngettext

# Language {{{


class LanguagePanel(QWidget):
    def __init__(self, container: Container, parent: QWidget | None = None):
        QWidget.__init__(self, parent)
        self.original_languages = book_languages(container)
        self.num_html = len(html_names(container))
        self.num_missing = len(html_files_without_language(container))
        self.l = l = QVBoxLayout(self)
        la = QLabel(
            _(
                'The language of the book is used by reading systems, screen readers and text-to-speech engines to'
                ' pronounce the text correctly. Each HTML file should also specify the language of its text.'
            )
        )
        la.setWordWrap(True)
        l.addWidget(la)

        f = QFormLayout()
        f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.languages = le = LanguagesEdit(self)
        le.lang_codes = self.original_languages
        le.setToolTip(_('The languages of the book, separated by commas. The first language is the main language of the book.'))
        f.addRow(_('Book &languages:'), le)
        self.html_language = hl = QComboBox(self)
        hl.addItem(_('Leave unchanged'), None)
        if self.num_missing:
            hl.addItem(
                ngettext('Set for the one HTML file without a language', 'Set for the {} HTML files without a language', self.num_missing).format(
                    self.num_missing
                ),
                HTML_LANGUAGE_MISSING,
            )
        hl.addItem(ngettext('Set for the one HTML file', 'Set for all {} HTML files', self.num_html).format(self.num_html), HTML_LANGUAGE_ALL)
        hl.setToolTip(
            _(
                'Set the language of HTML files to the main language of the book. Text in other languages'
                ' inside the files that is marked with its own language is not changed.'
            )
        )
        f.addRow(_('Language of &HTML files:'), hl)
        l.addLayout(f)
        if self.num_missing:
            la = QLabel(
                ngettext('One HTML file does not specify its language.', '{} HTML files do not specify their language.', self.num_missing).format(
                    self.num_missing
                )
            )
            la.setWordWrap(True)
            l.addWidget(la)
        l.addStretch(10)

    def validate(self) -> list[str]:
        return self.languages.validate()

    @property
    def languages_changed(self) -> list[str] | None:
        langs = self.languages.lang_codes
        return None if langs == self.original_languages else langs

    @property
    def html_language_mode(self) -> str | None:
        return self.html_language.currentData()

    def commit(self) -> None:
        self.languages.update_recently_used()


# }}}

# Image descriptions {{{

THUMBNAIL_SIZE = 64
PREVIEW_SIZE = 300
IMAGE, LOCATION, DECORATIVE, ALT = range(4)


def load_pixmap(path: str | bytes, size: int, dpr: float) -> QPixmap:
    if isinstance(path, bytes):
        buf = QBuffer()
        buf.setData(QByteArray(path))
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        reader = QImageReader(buf, b'svg')
    else:
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


class ImagesPanel(QWidget):
    def __init__(self, container: Container, parent: QWidget | None = None):
        QWidget.__init__(self, parent)
        self.container = container
        self.uses = image_uses(container)
        self.thumbnails: dict[str | bytes | None, QIcon] = {}
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
        if not self.uses:
            la = QLabel('<b>' + _('This book does not contain any images.'))
            l.addWidget(la)
            l.addStretch(10)
            return

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

        self.update_summary()
        t.setCurrentCell(0, ALT)

    def image_element(self, use: ImageUse):
        root = self.container.parsed(use.html_name)
        return next(elem for i, elem in enumerate(image_elements(root)) if i == use.index)

    def image_source(self, use: ImageUse) -> str | bytes | None:
        if use.is_svg:
            svg = deepcopy(self.image_element(use))
            # The preview is read from memory, so image links need absolute paths
            for img in svg.iter(SVG('image')):
                for attr in ('href', XLINK('href')):
                    href = img.get(attr)
                    if href and not href.startswith('data:'):
                        name = self.container.href_to_name(href, use.html_name)
                        if name is not None and self.container.has_name(name):
                            img.set(attr, self.container.name_to_abspath(name))
                        else:
                            img.attrib.pop(attr, None)
            return etree.tostring(svg, with_tail=False)
        if use.image_name is not None:
            return self.container.name_to_abspath(use.image_name)
        return None

    def thumbnail(self, source: str | bytes | None) -> QIcon:
        if source not in self.thumbnails:
            pmap = QPixmap()
            if source is not None:
                pmap = load_pixmap(source, THUMBNAIL_SIZE, self.devicePixelRatioF())
            self.thumbnails[source] = QIcon(pmap) if not pmap.isNull() else QIcon()
        return self.thumbnails[source]

    def populate(self) -> None:
        t = self.table
        ro = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        for row, use in enumerate(self.uses):
            name = _('Inline SVG') if use.is_svg else posixpath.basename(use.image_name) if use.image_name else _('Missing image')
            i = QTableWidgetItem(self.thumbnail(self.image_source(use)), name)
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

    def item(self, row: int, col: int) -> QTableWidgetItem:
        ans = self.table.item(row, col)
        assert ans is not None
        return ans

    def is_decorative(self, row: int) -> bool:
        return self.item(row, DECORATIVE).checkState() == Qt.CheckState.Checked

    def alt_for_row(self, row: int) -> str | None:
        if self.is_decorative(row):
            return ''
        return ' '.join(self.item(row, ALT).text().split()) or None

    def set_row(self, row: int, decorative: bool, text: str) -> None:
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

    def item_changed(self, item: QTableWidgetItem) -> None:
        row, col = item.row(), item.column()
        if col == DECORATIVE:
            decorative, text = self.row_state(row)
            use = self.uses[row]
            if use.is_svg and not decorative and not text:
                text = svg_alt_text(self.image_element(use), ignore_decorative=True) or ''
            self.set_row(row, decorative, text)
        self.update_summary()

    def update_summary(self) -> None:
        missing = sum(1 for row in range(len(self.uses)) if self.alt_for_row(row) is None)
        total = ngettext('One image', '{} images', len(self.uses)).format(len(self.uses))
        self.summary.setText(ngettext('{0}, one without a description', '{0}, {1} without a description', missing).format(total, missing))

    def apply_filter(self) -> None:
        only_missing = self.only_missing.isChecked()
        for row, use in enumerate(self.uses):
            self.table.setRowHidden(row, only_missing and use.alt is not None)

    def current_changed(self, row: int, *a: int) -> None:
        use = self.uses[row] if 0 <= row < len(self.uses) else None
        self.apply_to_all_button.setEnabled(use is not None and use.image_name is not None)
        if use is None:
            self.preview.clear()
            self.image_name_label.clear()
            self.context_label.clear()
            return
        pmap = QPixmap()
        if (source := self.image_source(use)) is not None:
            pmap = load_pixmap(source, PREVIEW_SIZE, self.devicePixelRatioF())
        if pmap.isNull():
            self.preview.setText(_('No preview available'))
        else:
            self.preview.setPixmap(pmap)
        self.image_name_label.setText(_('Inline SVG') if use.is_svg else use.image_name or _('The image file is missing'))
        if use.context:
            self.context_label.setText('<p><b>{}</b></p><p>{}</p>'.format(_('Text near the image:'), prepare_string_for_xml(use.context)))
        else:
            self.context_label.setText('')

    def apply_to_all_uses(self) -> None:
        row = self.table.currentRow()
        if not 0 <= row < len(self.uses):
            return
        image_name = self.uses[row].image_name
        if image_name is None:
            return
        decorative, text = self.row_state(row)
        for other, use in enumerate(self.uses):
            if other != row and use.image_name == image_name:
                self.set_row(other, decorative, text)
        self.update_summary()

    def row_state(self, row: int) -> tuple[bool, str]:
        return self.is_decorative(row), self.item(row, ALT).text()

    @property
    def changes(self) -> dict[tuple[str, int], str | None]:
        # Only rows the user changed, so that existing alternative text is left as is
        ans: dict[tuple[str, int], str | None] = {}
        for row, use in enumerate(self.uses):
            if self.row_state(row) != self.initial_states[row]:
                alt = self.alt_for_row(row)
                if alt != use.alt:
                    ans[(use.html_name, use.index)] = alt
        return ans


# }}}

# Accessibility metadata {{{


def labels() -> dict[str, dict[str, str]]:
    return {
        ACCESS_MODE: {
            'textual': _('Text'),
            'visual': _('Images'),
            'auditory': _('Audio'),
            'tactile': _('Tactile content, such as braille'),
            'chartOnVisual': _('Charts in images'),
            'diagramOnVisual': _('Diagrams in images'),
            'mathOnVisual': _('Math in images'),
            'textOnVisual': _('Text in images'),
            'colorDependent': _('Information conveyed by color'),
        },
        ACCESS_MODE_SUFFICIENT: {
            'textual': _('Text alone'),
            'visual': _('Images alone'),
            'auditory': _('Audio alone'),
            'tactile': _('Tactile content alone'),
            'textual,visual': _('Text and images'),
            'textual,auditory': _('Text and audio'),
            'auditory,visual': _('Audio and images'),
        },
        FEATURE: {
            'alternativeText': _('All images have alternative text'),
            'longDescription': _('Complex images have long descriptions'),
            'tableOfContents': _('Table of Contents'),
            'structuralNavigation': _('Headings for navigation'),
            'readingOrder': _('Logical reading order'),
            'index': _('Index'),
            'pageNavigation': _('Page list'),
            'pageBreakMarkers': _('Page break markers'),
            'printPageNumbers': _('Page numbers of the print edition'),
            'displayTransformability': _('Display can be changed, such as font and colors'),
            'ARIA': _('ARIA roles'),
            'MathML': _('Math as MathML'),
            'describedMath': _('Math images have text descriptions'),
            'synchronizedAudioText': _('Text synchronized with audio (Media Overlays)'),
            'ttsMarkup': _('Pronunciation markup for text-to-speech'),
            'captions': _('Captions for video'),
            'transcript': _('Transcripts for audio'),
            'annotations': _('Annotations'),
            'none': _('None of these'),
        },
    }


def hazard_labels() -> dict[str, str]:
    return {
        'flashing': _('&Flashing content:'),
        'motionSimulation': _('&Motion simulation:'),
        'sound': _('&Sound:'),
    }


class CheckList(QGroupBox):
    # Check boxes for the known values of a property, along with any other
    # values the book already has, so that they are kept

    def __init__(self, title: str, prop: str, known: tuple[str, ...], values: list[str], columns: int = 2, parent: QWidget | None = None):
        QGroupBox.__init__(self, title, parent)
        self.prop = prop
        names = labels()[prop]
        self.l = l = QGridLayout(self)
        self.boxes: dict[str, QCheckBox] = {}
        all_values = list(known) + [v for v in values if v not in known]
        for i, val in enumerate(all_values):
            cb = QCheckBox(names.get(val, val), self)
            cb.setToolTip(val)
            cb.setChecked(val in values)
            l.addWidget(cb, i // columns, i % columns)
            self.boxes[val] = cb

    @property
    def values(self) -> list[str]:
        return [val for val, cb in self.boxes.items() if cb.isChecked()]


class MetadataPanel(QScrollArea):
    def __init__(self, container: Container, parent: QWidget | None = None):
        QScrollArea.__init__(self, parent)
        self.original = read_accessibility_metadata(container)
        self.setWidgetResizable(True)
        w = QWidget(self)
        self.setWidget(w)
        wl = QVBoxLayout(w)
        la = QLabel(
            _(
                'Accessibility metadata tells readers, reading systems and online stores how accessible the book is.'
                ' It is required by the <a href="{}">EPUB Accessibility</a> specification. Only claim what is actually'
                ' true of the book, for example, only say that all images have alternative text after checking that they do.'
            ).format('https://www.w3.org/TR/epub-a11y-11/')
        )
        la.setWordWrap(True)
        la.setOpenExternalLinks(True)
        wl.addWidget(la)
        md = self.original

        g = QGroupBox(_('Accessibility summary'), w)
        gl = QVBoxLayout(g)
        self.summary = s = QPlainTextEdit(g)
        s.setPlaceholderText(
            _(
                'A short description of the accessibility of the book, for example: This publication'
                ' has a table of contents and all images have alternative text.'
            )
        )
        s.setPlainText('\n'.join(md[SUMMARY]))
        s.setMaximumHeight(100)
        gl.addWidget(s)
        wl.addWidget(g)

        self.access_modes = CheckList(_('Ways the content is presented (access modes)'), ACCESS_MODE, ACCESS_MODES, md[ACCESS_MODE], 3, w)
        wl.addWidget(self.access_modes)
        self.sufficient = CheckList(
            _('Ways that are enough to understand all the content (sufficient access modes)'),
            ACCESS_MODE_SUFFICIENT,
            SUFFICIENT_ACCESS_MODES,
            md[ACCESS_MODE_SUFFICIENT],
            3,
            w,
        )
        wl.addWidget(self.sufficient)
        self.features = CheckList(_('Accessibility features'), FEATURE, FEATURES, md[FEATURE], 2, w)
        wl.addWidget(self.features)

        g = QGroupBox(_('Hazards'), w)
        gl = QFormLayout(g)
        states = hazard_states(md[HAZARD])
        self.hazards: dict[str, QComboBox] = {}
        names = hazard_labels()
        for hazard in HAZARDS:
            cb = QComboBox(g)
            for state, text in ((UNKNOWN, _('Unknown')), (ABSENT, _('Not present')), (PRESENT, _('Present'))):
                cb.addItem(text, state)
            cb.setCurrentIndex(cb.findData(states[hazard]))
            gl.addRow(names[hazard], cb)
            self.hazards[hazard] = cb
        wl.addWidget(g)

        g = QGroupBox(_('Conformance'), w)
        gl = QFormLayout(g)
        gl.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.conforms_to = c = QComboBox(g)
        c.setEditable(True)
        c.addItem('')
        c.addItems(CONFORMANCE)
        c.setEditText(md[CONFORMS_TO][0] if md[CONFORMS_TO] else '')
        c.setToolTip(_('The accessibility standard the book has been checked against and meets'))
        gl.addRow(_('&Conforms to:'), c)
        self.certified_by = cb = QLineEdit(g)
        cb.setText(md[CERTIFIED_BY][0] if md[CERTIFIED_BY] else '')
        cb.setPlaceholderText(_('The person or organization that checked the conformance'))
        gl.addRow(_('Ce&rtified by:'), cb)
        wl.addWidget(g)
        wl.addStretch(10)

    @property
    def metadata(self) -> dict[str, list[str]]:
        conforms_to = self.conforms_to.currentText().strip()
        certified_by = self.certified_by.text().strip()
        return {
            SUMMARY: [self.summary.toPlainText()],
            ACCESS_MODE: self.access_modes.values,
            ACCESS_MODE_SUFFICIENT: self.sufficient.values,
            FEATURE: self.features.values,
            HAZARD: hazard_values({h: cb.currentData() for h, cb in self.hazards.items()}),
            CONFORMS_TO: [conforms_to] if conforms_to else [],
            CERTIFIED_BY: [certified_by] if certified_by else [],
        }

    @property
    def changes(self) -> dict[str, list[str]]:
        # Only the properties the user changed, so that the book is not
        # modified just by opening and accepting this dialog
        ans = {}
        for prop, values in self.metadata.items():
            values = [val for val in (' '.join(v.split()) for v in values) if val]
            original = self.original[prop]
            if prop == HAZARD:
                if hazard_states(values) == hazard_states(original):
                    continue
            elif prop == SUMMARY:
                if values == [' '.join(original)] or (not values and not original):
                    continue
            elif values == original:
                continue
            ans[prop] = values
        return ans


# }}}


class Accessibility(Dialog):
    def __init__(self, container: Container, parent: QWidget | None = None):
        self.container = container
        Dialog.__init__(self, _('Accessibility'), 'accessibility-tool', parent=parent)

    def sizeHint(self) -> QSize:
        return QSize(1000, 750)

    def setup_ui(self) -> None:
        self.l = l = QVBoxLayout(self)
        self.tabs = t = QTabWidget(self)
        l.addWidget(t, stretch=10)
        c = self.container
        self.language_panel = LanguagePanel(c, t)
        t.addTab(self.language_panel, QIcon.ic('languages.png'), _('&Language'))
        self.images_panel = ImagesPanel(c, t)
        t.addTab(self.images_panel, QIcon.ic('view-image.png'), _('&Image descriptions'))
        self.metadata_panel: MetadataPanel | None = None
        if c.book_type == 'epub' and c.opf_version_parsed.major > 2:
            self.metadata_panel = MetadataPanel(c, t)
            t.addTab(self.metadata_panel, QIcon.ic('metadata.png'), _('Accessibility &metadata'))
        else:
            la = QLabel(
                _('Accessibility metadata is only supported for EPUB 3 books. You can convert this book to EPUB 3 using Tools->Upgrade book internals.'),
                t,
            )
            la.setWordWrap(True)
            la.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            la.setContentsMargins(10, 10, 10, 10)
            t.addTab(la, QIcon.ic('metadata.png'), _('Accessibility &metadata'))
        l.addWidget(self.bb)

    def accept(self) -> None:
        bad = self.language_panel.validate()
        if bad:
            self.tabs.setCurrentWidget(self.language_panel)
            msg = ngettext('The language {} is not recognized', 'The languages {} are not recognized', len(bad)).format(', '.join(bad))
            error_dialog(self, _('Unknown language'), msg, show=True)
            return
        self.language_panel.commit()
        Dialog.accept(self)

    @property
    def changes(self) -> AccessibilityChanges:
        return AccessibilityChanges(
            languages=self.language_panel.languages_changed,
            html_language=self.language_panel.html_language_mode,
            alt_text=self.images_panel.changes if self.images_panel.uses else {},
            metadata=self.metadata_panel.changes if self.metadata_panel is not None else {},
        )


if __name__ == '__main__':
    import sys

    from calibre.ebooks.oeb.polish.container import get_container
    from calibre.gui2 import Application

    app = Application([])
    d = Accessibility(get_container(sys.argv[-1], tweak_mode=True))
    d.exec()
    print(d.changes)
    del app
