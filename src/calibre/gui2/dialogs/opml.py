#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import defaultdict, namedtuple
from operator import itemgetter

from qt.core import (
    QDialog, QFormLayout, QHBoxLayout, QLineEdit, QToolButton, QIcon,
    QDialogButtonBox, Qt, QSpinBox, QCheckBox)

from lxml import etree

from calibre.gui2 import choose_files, error_dialog
from calibre.utils.xml_parse import safe_xml_fromstring
from calibre.utils.icu import sort_key

Group = namedtuple('Group', 'title feeds')


def uniq(vals, kmap=lambda x:x):
    ''' Remove all duplicates from vals, while preserving order. kmap must be a
    callable that returns a hashable value for every item in vals '''
    vals = vals or ()
    lvals = (kmap(x) for x in vals)
    seen = set()
    seen_add = seen.add
    return tuple(x for x, k in zip(vals, lvals) if k not in seen and not seen_add(k))


def import_opml(raw, preserve_groups=True):
    root = safe_xml_fromstring(raw)
    groups = defaultdict(list)
    ax = etree.XPath('ancestor::outline[@title or @text]')
    for outline in root.xpath('//outline[@type="rss" and @xmlUrl]'):
        url = outline.get('xmlUrl')
        parent = outline.get('title', '') or url
        title = parent if ('title' in outline.attrib and parent) else None
        if preserve_groups:
            for ancestor in ax(outline):
                if ancestor.get('type', None) != 'rss':
                    text = ancestor.get('title') or ancestor.get('text')
                    if text:
                        parent = text
                        break
        groups[parent].append((title, url))

    for title in sorted(groups, key=sort_key):
        yield Group(title, uniq(groups[title], kmap=itemgetter(1)))


class ImportOPML(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent=parent)
        self.l = l = QFormLayout(self)
        self.setLayout(l)
        self.setWindowTitle(_('Import OPML file'))
        self.setWindowIcon(QIcon.ic('opml.png'))

        self.h = h = QHBoxLayout()
        self.path = p = QLineEdit(self)
        p.setMinimumWidth(300)
        p.setPlaceholderText(_('Path to OPML file'))
        h.addWidget(p)
        self.cfb = b = QToolButton(self)
        b.setIcon(QIcon.ic('document_open.png'))
        b.setToolTip(_('Browse for OPML file'))
        b.clicked.connect(self.choose_file)
        h.addWidget(b)
        l.addRow(_('&OPML file:'), h)
        l.labelForField(h).setBuddy(p)
        b.setFocus(Qt.FocusReason.OtherFocusReason)

        self._articles_per_feed = a = QSpinBox(self)
        a.setMinimum(1), a.setMaximum(1000), a.setValue(100)
        a.setToolTip(_('Maximum number of articles to download per RSS feed'))
        l.addRow(_('&Maximum articles per feed:'), a)

        self._oldest_article = o = QSpinBox(self)
        o.setMinimum(1), o.setMaximum(3650), o.setValue(7)
        o.setSuffix(_(' days'))
        o.setToolTip(_('Articles in the RSS feeds older than this will be ignored'))
        l.addRow(_('&Oldest article:'), o)

        self.preserve_groups = g = QCheckBox(_('Preserve groups in the OPML file'))
        g.setToolTip('<p>' + _(
            'If enabled, every group of feeds in the OPML file will be converted into a single recipe. Otherwise every feed becomes its own recipe'))
        g.setChecked(True)
        l.addRow(g)

        self._replace_existing = r = QCheckBox(_('Replace existing recipes'))
        r.setToolTip('<p>' + _(
            'If enabled, any existing recipes with the same titles as entries in the OPML file will be replaced.'
            ' Otherwise, new entries with modified titles will be created'))
        r.setChecked(True)
        l.addRow(r)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept), bb.rejected.connect(self.reject)
        l.addRow(bb)

        self.recipes = ()

    @property
    def articles_per_feed(self):
        return self._articles_per_feed.value()

    @property
    def oldest_article(self):
        return self._oldest_article.value()

    @property
    def replace_existing(self):
        return self._replace_existing.isChecked()

    def choose_file(self):
        opml_files = choose_files(
            self, 'opml-select-dialog', _('Select OPML file'), filters=[(_('OPML files'), ['opml'])],
            all_files=False, select_only_single_file=True)
        if opml_files:
            self.path.setText(opml_files[0])

    def accept(self):
        path = str(self.path.text())
        if not path:
            return error_dialog(self, _('Path not specified'), _(
                'You must specify the path to the OPML file to import'), show=True)
        with open(path, 'rb') as f:
            raw = f.read()
        self.recipes = tuple(import_opml(raw, self.preserve_groups.isChecked()))
        if len(self.recipes) == 0:
            return error_dialog(self, _('No feeds found'), _(
                'No importable RSS feeds found in the OPML file'), show=True)

        QDialog.accept(self)


if __name__ == '__main__':
    import sys
    for group in import_opml(open(sys.argv[-1], 'rb').read()):
        print(group.title)
        for title, url in group.feeds:
            print(f'\t{title} - {url}')
        print()
