#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

from qt.core import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QSize,
    QVBoxLayout,
    QWidget,
)

from calibre.ebooks.oeb.polish.accessibility_metadata import (
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
    PRESENT,
    SUFFICIENT_ACCESS_MODES,
    SUMMARY,
    UNKNOWN,
    hazard_states,
    hazard_values,
    read_accessibility_metadata,
)
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.utils.localization import _


def labels():
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


def hazard_labels():
    return {
        'flashing': _('&Flashing content:'),
        'motionSimulation': _('&Motion simulation:'),
        'sound': _('&Sound:'),
    }


class CheckList(QGroupBox):
    # Check boxes for the known values of a property, along with any other
    # values the book already has, so that they are kept

    def __init__(self, title, prop, known, values, columns=2, parent=None):
        QGroupBox.__init__(self, title, parent)
        self.prop = prop
        names = labels()[prop]
        self.l = l = QGridLayout(self)
        self.boxes = {}
        all_values = list(known) + [v for v in values if v not in known]
        for i, val in enumerate(all_values):
            cb = QCheckBox(names.get(val, val), self)
            cb.setToolTip(val)
            cb.setChecked(val in values)
            l.addWidget(cb, i // columns, i % columns)
            self.boxes[val] = cb

    @property
    def values(self):
        return [val for val, cb in self.boxes.items() if cb.isChecked()]


class AccessibilityMetadata(Dialog):
    def __init__(self, container, parent=None):
        self.original = read_accessibility_metadata(container)
        Dialog.__init__(self, _('Accessibility metadata'), 'accessibility-metadata', parent=parent)

    def sizeHint(self):
        return QSize(850, 750)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        la = QLabel(
            _(
                'Accessibility metadata tells readers, reading systems and online stores how accessible the book is.'
                ' It is required by the <a href="{}">EPUB Accessibility</a> specification. Only claim what is actually'
                ' true of the book, for example, only say that all images have alternative text after checking that they do.'
            ).format('https://www.w3.org/TR/epub-a11y-11/')
        )
        la.setWordWrap(True)
        la.setOpenExternalLinks(True)
        l.addWidget(la)

        self.scroll_area = sa = QScrollArea(self)
        sa.setWidgetResizable(True)
        l.addWidget(sa, stretch=10)
        w = QWidget(sa)
        sa.setWidget(w)
        wl = QVBoxLayout(w)
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
        self.hazards = {}
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

        h = QHBoxLayout()
        h.addStretch(10)
        h.addWidget(self.bb)
        l.addLayout(h)

    @property
    def metadata(self):
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
    def changes(self):
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


if __name__ == '__main__':
    import sys

    from calibre.ebooks.oeb.polish.container import get_container
    from calibre.gui2 import Application

    app = Application([])
    d = AccessibilityMetadata(get_container(sys.argv[-1], tweak_mode=True))
    d.exec()
    print(d.changes)
    del app
