#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os, textwrap, unicodedata
from itertools import izip
from collections import OrderedDict

from PyQt5.Qt import (
    QGridLayout, QLabel, QLineEdit, QVBoxLayout, QFormLayout, QHBoxLayout,
    QToolButton, QIcon, QApplication, Qt, QWidget, QPoint, QSizePolicy,
    QPainter, QStaticText, pyqtSignal, QTextOption, QAbstractListModel,
    QModelIndex, QStyledItemDelegate, QStyle, QCheckBox, QListView,
    QTextDocument, QSize, QComboBox, QFrame, QCursor, QGroupBox, QSplitter,
    QPixmap, QRect, QPlainTextEdit, QMimeData)

from calibre import prepare_string_for_xml, human_readable
from calibre.constants import iswindows
from calibre.ebooks.oeb.polish.utils import lead_text, guess_type
from calibre.gui2 import error_dialog, choose_files, choose_save_file, info_dialog, choose_images
from calibre.gui2.tweak_book import tprefs, current_container
from calibre.gui2.widgets2 import Dialog as BaseDialog
from calibre.utils.icu import primary_sort_key, sort_key, primary_contains
from calibre.utils.matcher import get_char, Matcher
from calibre.gui2.complete2 import EditWithComplete

ROOT = QModelIndex()
PARAGRAPH_SEPARATOR = '\u2029'


class BusyCursor(object):

    def __enter__(self):
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

    def __exit__(self, *args):
        QApplication.restoreOverrideCursor()


class Dialog(BaseDialog):

    def __init__(self, title, name, parent=None):
        BaseDialog.__init__(self, title, name, parent=parent, prefs=tprefs)


class InsertTag(Dialog):  # {{{

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Choose tag name'), 'insert-tag', parent=parent)

    def setup_ui(self):
        from calibre.ebooks.constants import html5_tags
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)

        self.la = la = QLabel(_('Specify the name of the &tag to insert:'))
        l.addWidget(la)

        self.tag_input = ti = EditWithComplete(self)
        ti.set_separator(None)
        ti.all_items = html5_tags | frozenset(tprefs['insert_tag_mru'])
        la.setBuddy(ti)
        l.addWidget(ti)
        l.addWidget(self.bb)
        ti.setFocus(Qt.OtherFocusReason)

    @property
    def tag(self):
        return unicode(self.tag_input.text()).strip()

    @classmethod
    def test(cls):
        d = cls()
        if d.exec_() == d.Accepted:
            print (d.tag)

# }}}


class RationalizeFolders(Dialog):  # {{{

    TYPE_MAP = (
                ('text', _('Text (HTML) files')),
                ('style', _('Style (CSS) files')),
                ('image', _('Images')),
                ('font', _('Fonts')),
                ('audio', _('Audio')),
                ('video', _('Video')),
                ('opf', _('OPF file (metadata)')),
                ('toc', _('Table of contents file (NCX)')),
    )

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Arrange in folders'), 'rationalize-folders', parent=parent)

    def setup_ui(self):
        self.l = l = QGridLayout()
        self.setLayout(l)

        self.la = la = QLabel(_(
            'Arrange the files in this book into sub-folders based on their types.'
            ' If you leave a folder blank, the files will be placed in the root.'))
        la.setWordWrap(True)
        l.addWidget(la, 0, 0, 1, -1)

        folders = tprefs['folders_for_types']
        for i, (typ, text) in enumerate(self.TYPE_MAP):
            la = QLabel('&' + text)
            setattr(self, '%s_label' % typ, la)
            le = QLineEdit(self)
            setattr(self, '%s_folder' % typ, le)
            val = folders.get(typ, '')
            if val and not val.endswith('/'):
                val += '/'
            le.setText(val)
            la.setBuddy(le)
            l.addWidget(la, i + 1, 0)
            l.addWidget(le, i + 1, 1)
        self.la2 = la = QLabel(_(
            'Note that this will only arrange files inside the book,'
            ' it will not affect how they are displayed in the File browser'))
        la.setWordWrap(True)
        l.addWidget(la, i + 2, 0, 1, -1)
        l.addWidget(self.bb, i + 3, 0, 1, -1)

    @property
    def folder_map(self):
        ans = {}
        for typ, x in self.TYPE_MAP:
            val = unicode(getattr(self, '%s_folder' % typ).text()).strip().strip('/')
            ans[typ] = val
        return ans

    def accept(self):
        tprefs['folders_for_types'] = self.folder_map
        return Dialog.accept(self)
# }}}


class MultiSplit(Dialog):  # {{{

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Specify locations to split at'), 'multisplit-xpath', parent=parent)

    def setup_ui(self):
        from calibre.gui2.convert.xpath_wizard import XPathEdit
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)

        self.la = la = QLabel(_(
            'Specify the locations to split at, using an XPath expression (click'
            ' the wizard button for help with generating XPath expressions).'))
        la.setWordWrap(True)
        l.addWidget(la)

        self._xpath = xp = XPathEdit(self)
        xp.set_msg(_('&XPath expression:'))
        xp.setObjectName('editor-multisplit-xpath-edit')
        l.addWidget(xp)
        l.addWidget(self.bb)

    def accept(self):
        if not self._xpath.check():
            return error_dialog(self, _('Invalid XPath expression'), _(
                'The XPath expression %s is invalid.') % self.xpath)
        return Dialog.accept(self)

    @property
    def xpath(self):
        return self._xpath.xpath

# }}}


class ImportForeign(Dialog):  # {{{

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Choose file to import'), 'import-foreign')

    def sizeHint(self):
        ans = Dialog.sizeHint(self)
        ans.setWidth(ans.width() + 200)
        return ans

    def setup_ui(self):
        self.l = l = QFormLayout(self)
        self.setLayout(l)

        la = self.la = QLabel(_(
            'You can import an HTML or DOCX file directly as an EPUB and edit it. The EPUB'
            ' will be generated with minimal changes from the source, unlike doing a full'
            ' conversion in calibre.'))
        la.setWordWrap(True)
        l.addRow(la)

        self.h1 = h1 = QHBoxLayout()
        self.src = src = QLineEdit(self)
        src.setPlaceholderText(_('Choose the file to import'))
        h1.addWidget(src)
        self.b1 = b = QToolButton(self)
        b.setIcon(QIcon(I('document_open.png')))
        b.setText(_('Choose file'))
        h1.addWidget(b)
        l.addRow(_('Source file'), h1)
        b.clicked.connect(self.choose_source)
        b.setFocus(Qt.OtherFocusReason)

        self.h2 = h1 = QHBoxLayout()
        self.dest = src = QLineEdit(self)
        src.setPlaceholderText(_('Choose the location for the newly created EPUB'))
        h1.addWidget(src)
        self.b2 = b = QToolButton(self)
        b.setIcon(QIcon(I('document_open.png')))
        b.setText(_('Choose file'))
        h1.addWidget(b)
        l.addRow(_('Destination file'), h1)
        b.clicked.connect(self.choose_destination)

        l.addRow(self.bb)

    def choose_source(self):
        from calibre.ebooks.oeb.polish.import_book import IMPORTABLE
        path = choose_files(self, 'edit-book-choose-file-to-import', _('Choose file'), filters=[
            (_('Importable files'), list(IMPORTABLE))], select_only_single_file=True)
        if path:
            self.set_src(path[0])

    def set_src(self, path):
        self.src.setText(path)
        self.dest.setText(self.data[1])

    def choose_destination(self):
        path = choose_save_file(self, 'edit-book-destination-for-generated-epub', _('Choose destination'), filters=[
            (_('EPUB files'), ['epub'])], all_files=False)
        if path:
            if not path.lower().endswith('.epub'):
                path += '.epub'
            self.dest.setText(path)

    def accept(self):
        if not unicode(self.src.text()):
            return error_dialog(self, _('Need document'), _(
                'You must specify the source file that will be imported.'), show=True)
        Dialog.accept(self)

    @property
    def data(self):
        src = unicode(self.src.text()).strip()
        dest = unicode(self.dest.text()).strip()
        if not dest:
            dest = src.rpartition('.')[0] + '.epub'
        return src, dest
# }}}

# Quick Open {{{


def make_highlighted_text(emph, text, positions):
    positions = sorted(set(positions) - {-1})
    if positions:
        parts = []
        pos = 0
        for p in positions:
            ch = get_char(text, p)
            parts.append(prepare_string_for_xml(text[pos:p]))
            parts.append('<span style="%s">%s</span>' % (emph, prepare_string_for_xml(ch)))
            pos = p + len(ch)
        parts.append(prepare_string_for_xml(text[pos:]))
        return ''.join(parts)
    return text


class Results(QWidget):

    EMPH = "color:magenta; font-weight:bold"
    MARGIN = 4

    item_selected = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.results = ()
        self.current_result = -1
        self.max_result = -1
        self.mouse_hover_result = -1
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.text_option = to = QTextOption()
        to.setWrapMode(to.NoWrap)
        self.divider = QStaticText('\xa0→ \xa0')
        self.divider.setTextFormat(Qt.PlainText)

    def item_from_y(self, y):
        if not self.results:
            return
        delta = self.results[0][0].size().height() + self.MARGIN
        maxy = self.height()
        pos = 0
        for i, r in enumerate(self.results):
            bottom = pos + delta
            if pos <= y < bottom:
                return i
                break
            pos = bottom
            if pos > min(y, maxy):
                break
        return -1

    def mouseMoveEvent(self, ev):
        y = ev.pos().y()
        prev = self.mouse_hover_result
        self.mouse_hover_result = self.item_from_y(y)
        if prev != self.mouse_hover_result:
            self.update()

    def mousePressEvent(self, ev):
        if ev.button() == 1:
            i = self.item_from_y(ev.pos().y())
            if i != -1:
                ev.accept()
                self.current_result = i
                self.update()
                self.item_selected.emit()
                return
        return QWidget.mousePressEvent(self, ev)

    def change_current(self, delta=1):
        if not self.results:
            return
        nc = self.current_result + delta
        if 0 <= nc <= self.max_result:
            self.current_result = nc
            self.update()

    def __call__(self, results):
        if results:
            self.current_result = 0
            prefixes = [QStaticText('<b>%s</b>' % os.path.basename(x)) for x in results]
            [(p.setTextFormat(Qt.RichText), p.setTextOption(self.text_option)) for p in prefixes]
            self.maxwidth = max([x.size().width() for x in prefixes])
            self.results = tuple((prefix, self.make_text(text, positions), text)
                for prefix, (text, positions) in izip(prefixes, results.iteritems()))
        else:
            self.results = ()
            self.current_result = -1
        self.max_result = min(10, len(self.results) - 1)
        self.mouse_hover_result = -1
        self.update()

    def make_text(self, text, positions):
        text = QStaticText(make_highlighted_text(self.EMPH, text, positions))
        text.setTextOption(self.text_option)
        text.setTextFormat(Qt.RichText)
        return text

    def paintEvent(self, ev):
        offset = QPoint(0, 0)
        p = QPainter(self)
        p.setClipRect(ev.rect())
        bottom = self.rect().bottom()

        if self.results:
            for i, (prefix, full, text) in enumerate(self.results):
                size = prefix.size()
                if offset.y() + size.height() > bottom:
                    break
                self.max_result = i
                offset.setX(0)
                if i in (self.current_result, self.mouse_hover_result):
                    p.save()
                    if i != self.current_result:
                        p.setPen(Qt.DotLine)
                    p.drawLine(offset, QPoint(self.width(), offset.y()))
                    p.restore()
                offset.setY(offset.y() + self.MARGIN // 2)
                p.drawStaticText(offset, prefix)
                offset.setX(self.maxwidth + 5)
                p.drawStaticText(offset, self.divider)
                offset.setX(offset.x() + self.divider.size().width())
                p.drawStaticText(offset, full)
                offset.setY(offset.y() + size.height() + self.MARGIN // 2)
                if i in (self.current_result, self.mouse_hover_result):
                    offset.setX(0)
                    p.save()
                    if i != self.current_result:
                        p.setPen(Qt.DotLine)
                    p.drawLine(offset, QPoint(self.width(), offset.y()))
                    p.restore()
        else:
            p.drawText(self.rect(), Qt.AlignCenter, _('No results found'))

        p.end()

    @property
    def selected_result(self):
        try:
            return self.results[self.current_result][-1]
        except IndexError:
            pass


class QuickOpen(Dialog):

    def __init__(self, items, parent=None):
        self.matcher = Matcher(items)
        self.matches = ()
        self.selected_result = None
        Dialog.__init__(self, _('Choose file to edit'), 'quick-open', parent=parent)

    def sizeHint(self):
        ans = Dialog.sizeHint(self)
        ans.setWidth(800)
        ans.setHeight(max(600, ans.height()))
        return ans

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)

        self.text = t = QLineEdit(self)
        t.textEdited.connect(self.update_matches)
        l.addWidget(t, alignment=Qt.AlignTop)

        example = '<pre>{0}i{1}mages/{0}c{1}hapter1/{0}s{1}cene{0}3{1}.jpg</pre>'.format(
            '<span style="%s">' % Results.EMPH, '</span>')
        chars = '<pre style="%s">ics3</pre>' % Results.EMPH

        self.help_label = hl = QLabel(_(
            '''<p>Quickly choose a file by typing in just a few characters from the file name into the field above.
        For example, if want to choose the file:
        {example}
        Simply type in the characters:
        {chars}
        and press Enter.''').format(example=example, chars=chars))
        hl.setContentsMargins(50, 50, 50, 50), hl.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        l.addWidget(hl)
        self.results = Results(self)
        self.results.setVisible(False)
        self.results.item_selected.connect(self.accept)
        l.addWidget(self.results)

        l.addWidget(self.bb, alignment=Qt.AlignBottom)

    def update_matches(self, text):
        text = unicode(text).strip()
        self.help_label.setVisible(False)
        self.results.setVisible(True)
        matches = self.matcher(text, limit=100)
        self.results(matches)
        self.matches = tuple(matches)

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Up, Qt.Key_Down):
            ev.accept()
            self.results.change_current(delta=-1 if ev.key() == Qt.Key_Up else 1)
            return
        return Dialog.keyPressEvent(self, ev)

    def accept(self):
        self.selected_result = self.results.selected_result
        return Dialog.accept(self)

    @classmethod
    def test(cls):
        import os
        from calibre.utils.matcher import get_items_from_dir
        items = get_items_from_dir(os.getcwdu(), lambda x:not x.endswith('.pyc'))
        d = cls(items)
        d.exec_()
        print (d.selected_result)

# }}}

# Filterable names list {{{


class NamesDelegate(QStyledItemDelegate):

    def sizeHint(self, option, index):
        ans = QStyledItemDelegate.sizeHint(self, option, index)
        ans.setHeight(ans.height() + 10)
        return ans

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, index)
        text, positions = index.data(Qt.UserRole)
        self.initStyleOption(option, index)
        painter.save()
        painter.setFont(option.font)
        p = option.palette
        c = p.HighlightedText if option.state & QStyle.State_Selected else p.Text
        group = (p.Active if option.state & QStyle.State_Active else p.Inactive)
        c = p.color(group, c)
        painter.setClipRect(option.rect)
        if positions is None or -1 in positions:
            painter.setPen(c)
            painter.drawText(option.rect, Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine, text)
        else:
            to = QTextOption()
            to.setWrapMode(to.NoWrap)
            to.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            positions = sorted(set(positions) - {-1}, reverse=True)
            text = '<body>%s</body>' % make_highlighted_text(Results.EMPH, text, positions)
            doc = QTextDocument()
            c = 'rgb(%d, %d, %d)'%c.getRgb()[:3]
            doc.setDefaultStyleSheet(' body { color: %s }'%c)
            doc.setHtml(text)
            doc.setDefaultFont(option.font)
            doc.setDocumentMargin(0.0)
            doc.setDefaultTextOption(to)
            height = doc.size().height()
            painter.translate(option.rect.left(), option.rect.top() + (max(0, option.rect.height() - height) // 2))
            doc.drawContents(painter)
        painter.restore()


class NamesModel(QAbstractListModel):

    filtered = pyqtSignal(object)

    def __init__(self, names, parent=None):
        self.items = []
        QAbstractListModel.__init__(self, parent)
        self.set_names(names)

    def set_names(self, names):
        self.names = names
        self.matcher = Matcher(names)
        self.filter('')

    def rowCount(self, parent=ROOT):
        return len(self.items)

    def data(self, index, role):
        if role == Qt.UserRole:
            return self.items[index.row()]
        if role == Qt.DisplayRole:
            return '\xa0' * 20

    def filter(self, query):
        query = unicode(query or '')
        self.beginResetModel()
        if not query:
            self.items = tuple((text, None) for text in self.names)
        else:
            self.items = tuple(self.matcher(query).iteritems())
        self.endResetModel()
        self.filtered.emit(not bool(query))

    def find_name(self, name):
        for i, (text, positions) in enumerate(self.items):
            if text == name:
                return i

    def name_for_index(self, index):
        try:
            return self.items[index.row()][0]
        except IndexError:
            pass


def create_filterable_names_list(names, filter_text=None, parent=None, model=NamesModel):
    nl = QListView(parent)
    nl.m = m = model(names, parent=nl)
    m.filtered.connect(lambda all_items: nl.scrollTo(m.index(0)))
    nl.setModel(m)
    if model is NamesModel:
        nl.d = NamesDelegate(nl)
        nl.setItemDelegate(nl.d)
    f = QLineEdit(parent)
    f.setPlaceholderText(filter_text or '')
    f.textEdited.connect(m.filter)
    return nl, f

# }}}

# Insert Link {{{


class AnchorsModel(QAbstractListModel):

    filtered = pyqtSignal(object)

    def __init__(self, names, parent=None):
        self.items = []
        self.names = []
        QAbstractListModel.__init__(self, parent=parent)

    def rowCount(self, parent=ROOT):
        return len(self.items)

    def data(self, index, role):
        if role == Qt.UserRole:
            return self.items[index.row()]
        if role == Qt.DisplayRole:
            return '\n'.join(self.items[index.row()])
        if role == Qt.ToolTipRole:
            text, frag = self.items[index.row()]
            return _('Anchor: {0}\nLeading text: {1}').format(frag, text)

    def set_names(self, names):
        self.names = names
        self.filter('')

    def filter(self, query):
        query = unicode(query or '')
        self.beginResetModel()
        self.items = [x for x in self.names if primary_contains(query, x[0]) or primary_contains(query, x[1])]
        self.endResetModel()
        self.filtered.emit(not bool(query))


class InsertLink(Dialog):

    def __init__(self, container, source_name, initial_text=None, parent=None):
        self.container = container
        self.source_name = source_name
        self.initial_text = initial_text
        Dialog.__init__(self, _('Insert Hyperlink'), 'insert-hyperlink', parent=parent)
        self.anchor_cache = {}

    def sizeHint(self):
        return QSize(800, 600)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)

        self.h = h = QHBoxLayout()
        l.addLayout(h)

        names = [n for n, linear in self.container.spine_names]
        fn, f = create_filterable_names_list(names, filter_text=_('Filter files'), parent=self)
        self.file_names, self.file_names_filter = fn, f
        fn.selectionModel().selectionChanged.connect(self.selected_file_changed)
        self.fnl = fnl = QVBoxLayout()
        self.la1 = la = QLabel(_('Choose a &file to link to:'))
        la.setBuddy(fn)
        fnl.addWidget(la), fnl.addWidget(f), fnl.addWidget(fn)
        h.addLayout(fnl), h.setStretch(0, 2)

        fn, f = create_filterable_names_list([], filter_text=_('Filter locations'), parent=self, model=AnchorsModel)
        fn.setSpacing(5)
        self.anchor_names, self.anchor_names_filter = fn, f
        fn.selectionModel().selectionChanged.connect(self.update_target)
        fn.doubleClicked.connect(self.accept, type=Qt.QueuedConnection)
        self.anl = fnl = QVBoxLayout()
        self.la2 = la = QLabel(_('Choose a &location (anchor) in the file:'))
        la.setBuddy(fn)
        fnl.addWidget(la), fnl.addWidget(f), fnl.addWidget(fn)
        h.addLayout(fnl), h.setStretch(1, 1)

        self.tl = tl = QFormLayout()
        tl.setFieldGrowthPolicy(tl.AllNonFixedFieldsGrow)
        self.target = t = QLineEdit(self)
        t.setPlaceholderText(_('The destination (href) for the link'))
        tl.addRow(_('&Target:'), t)
        l.addLayout(tl)

        self.text_edit = t = QLineEdit(self)
        la.setBuddy(t)
        tl.addRow(_('Te&xt:'), t)
        t.setText(self.initial_text or '')
        t.setPlaceholderText(_('The (optional) text for the link'))

        l.addWidget(self.bb)

    def selected_file_changed(self, *args):
        rows = list(self.file_names.selectionModel().selectedRows())
        if not rows:
            self.anchor_names.model().set_names([])
        else:
            name, positions = self.file_names.model().data(rows[0], Qt.UserRole)
            self.populate_anchors(name)

    def populate_anchors(self, name):
        if name not in self.anchor_cache:
            from calibre.ebooks.oeb.base import XHTML_NS
            root = self.container.parsed(name)
            ac = self.anchor_cache[name] = []
            for item in set(root.xpath('//*[@id]')) | set(root.xpath('//h:a[@name]', namespaces={'h':XHTML_NS})):
                frag = item.get('id', None) or item.get('name')
                if not frag:
                    continue
                text = lead_text(item, num_words=4)
                ac.append((text, frag))
            ac.sort(key=lambda text_frag: primary_sort_key(text_frag[0]))
        self.anchor_names.model().set_names(self.anchor_cache[name])
        self.update_target()

    def update_target(self):
        rows = list(self.file_names.selectionModel().selectedRows())
        if not rows:
            return
        name = self.file_names.model().data(rows[0], Qt.UserRole)[0]
        if name == self.source_name:
            href = ''
        else:
            href = self.container.name_to_href(name, self.source_name)
        frag = ''
        rows = list(self.anchor_names.selectionModel().selectedRows())
        if rows:
            anchor = self.anchor_names.model().data(rows[0], Qt.UserRole)[1]
            if anchor:
                frag = '#' + anchor
        href += frag
        self.target.setText(href or '#')

    @property
    def href(self):
        return unicode(self.target.text()).strip()

    @property
    def text(self):
        return unicode(self.text_edit.text()).strip()

    @classmethod
    def test(cls):
        import sys
        from calibre.ebooks.oeb.polish.container import get_container
        c = get_container(sys.argv[-1], tweak_mode=True)
        d = cls(c, next(c.spine_names)[0])
        if d.exec_() == d.Accepted:
            print (d.href, d.text)

# }}}

# Insert Semantics {{{


class InsertSemantics(Dialog):

    def __init__(self, container, parent=None):
        self.container = container
        self.anchor_cache = {}
        self.original_type_map = {item.get('type', ''):(container.href_to_name(item.get('href'), container.opf_name), item.get('href', '').partition('#')[-1])
            for item in container.opf_xpath('//opf:guide/opf:reference[@href and @type]')}
        self.final_type_map = self.original_type_map.copy()
        self.create_known_type_map()
        Dialog.__init__(self, _('Set Semantics'), 'insert-semantics', parent=parent)

    def sizeHint(self):
        return QSize(800, 600)

    def create_known_type_map(self):
        _ = lambda x: x
        self.known_type_map = {
            'title-page': _('Title Page'),
            'toc': _('Table of Contents'),
            'index': _('Index'),
            'glossary': _('Glossary'),
            'acknowledgements': _('Acknowledgements'),
            'bibliography': _('Bibliography'),
            'colophon': _('Colophon'),
            'copyright-page': _('Copyright page'),
            'dedication': _('Dedication'),
            'epigraph': _('Epigraph'),
            'foreword': _('Foreword'),
            'loi': _('List of illustrations'),
            'lot': _('List of tables'),
            'notes': _('Notes'),
            'preface': _('Preface'),
            'text': _('Text'),
        }
        _ = __builtins__['_']
        type_map_help = {
            'title-page': _('Page with title, author, publisher, etc.'),
            'index': _('Back-of-book style index'),
            'text': _('First "real" page of content'),
        }
        t = _
        all_types = [(k, (('%s (%s)' % (t(v), type_map_help[k])) if k in type_map_help else t(v))) for k, v in self.known_type_map.iteritems()]
        all_types.sort(key=lambda x: sort_key(x[1]))
        self.all_types = OrderedDict(all_types)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)

        self.tl = tl = QFormLayout()
        self.semantic_type = QComboBox(self)
        for key, val in self.all_types.iteritems():
            self.semantic_type.addItem(val, key)
        tl.addRow(_('Type of &semantics:'), self.semantic_type)
        self.target = t = QLineEdit(self)
        t.setPlaceholderText(_('The destination (href) for the link'))
        tl.addRow(_('&Target:'), t)
        l.addLayout(tl)

        self.hline = hl = QFrame(self)
        hl.setFrameStyle(hl.HLine)
        l.addWidget(hl)

        self.h = h = QHBoxLayout()
        l.addLayout(h)

        names = [n for n, linear in self.container.spine_names]
        fn, f = create_filterable_names_list(names, filter_text=_('Filter files'), parent=self)
        self.file_names, self.file_names_filter = fn, f
        fn.selectionModel().selectionChanged.connect(self.selected_file_changed)
        self.fnl = fnl = QVBoxLayout()
        self.la1 = la = QLabel(_('Choose a &file:'))
        la.setBuddy(fn)
        fnl.addWidget(la), fnl.addWidget(f), fnl.addWidget(fn)
        h.addLayout(fnl), h.setStretch(0, 2)

        fn, f = create_filterable_names_list([], filter_text=_('Filter locations'), parent=self)
        self.anchor_names, self.anchor_names_filter = fn, f
        fn.selectionModel().selectionChanged.connect(self.update_target)
        fn.doubleClicked.connect(self.accept, type=Qt.QueuedConnection)
        self.anl = fnl = QVBoxLayout()
        self.la2 = la = QLabel(_('Choose a &location (anchor) in the file:'))
        la.setBuddy(fn)
        fnl.addWidget(la), fnl.addWidget(f), fnl.addWidget(fn)
        h.addLayout(fnl), h.setStretch(1, 1)

        self.bb.addButton(self.bb.Help)
        self.bb.helpRequested.connect(self.help_requested)
        l.addWidget(self.bb)
        self.semantic_type_changed()
        self.semantic_type.currentIndexChanged.connect(self.semantic_type_changed)
        self.target.textChanged.connect(self.target_text_changed)

    def help_requested(self):
        d = info_dialog(self, _('About semantics'), _(
            'Semantics refer to additional information about specific locations in the book.'
            ' For example, you can specify that a particular location is the dedication or the preface'
            ' or the table of contents and so on.\n\nFirst choose the type of semantic information, then'
            ' choose a file and optionally a location within the file to point to.\n\nThe'
            ' semantic information will be written in the <guide> section of the opf file.'))
        d.resize(d.sizeHint())
        d.exec_()

    def semantic_type_changed(self):
        item_type = unicode(self.semantic_type.itemData(self.semantic_type.currentIndex()) or '')
        name, frag = self.final_type_map.get(item_type, (None, None))
        self.show_type(name, frag)

    def show_type(self, name, frag):
        self.file_names_filter.clear(), self.anchor_names_filter.clear()
        self.file_names.clearSelection(), self.anchor_names.clearSelection()
        if name is not None:
            row = self.file_names.model().find_name(name)
            if row is not None:
                sm = self.file_names.selectionModel()
                sm.select(self.file_names.model().index(row), sm.ClearAndSelect)
                if frag:
                    row = self.anchor_names.model().find_name(frag)
                    if row is not None:
                        sm = self.anchor_names.selectionModel()
                        sm.select(self.anchor_names.model().index(row), sm.ClearAndSelect)
        self.target.blockSignals(True)
        if name is not None:
            self.target.setText(name + (('#' + frag) if frag else ''))
        else:
            self.target.setText('')
        self.target.blockSignals(False)

    def target_text_changed(self):
        name, frag = unicode(self.target.text()).partition('#')[::2]
        item_type = unicode(self.semantic_type.itemData(self.semantic_type.currentIndex()) or '')
        self.final_type_map[item_type] = (name, frag or None)

    def selected_file_changed(self, *args):
        rows = list(self.file_names.selectionModel().selectedRows())
        if not rows:
            self.anchor_names.model().set_names([])
        else:
            name, positions = self.file_names.model().data(rows[0], Qt.UserRole)
            self.populate_anchors(name)

    def populate_anchors(self, name):
        if name not in self.anchor_cache:
            from calibre.ebooks.oeb.base import XHTML_NS
            root = self.container.parsed(name)
            self.anchor_cache[name] = sorted(
                (set(root.xpath('//*/@id')) | set(root.xpath('//h:a/@name', namespaces={'h':XHTML_NS}))) - {''}, key=primary_sort_key)
        self.anchor_names.model().set_names(self.anchor_cache[name])
        self.update_target()

    def update_target(self):
        rows = list(self.file_names.selectionModel().selectedRows())
        if not rows:
            return
        name = self.file_names.model().data(rows[0], Qt.UserRole)[0]
        href = name
        frag = ''
        rows = list(self.anchor_names.selectionModel().selectedRows())
        if rows:
            anchor = self.anchor_names.model().data(rows[0], Qt.UserRole)[0]
            if anchor:
                frag = '#' + anchor
        href += frag
        self.target.setText(href or '#')

    @property
    def changed_type_map(self):
        return {k:v for k, v in self.final_type_map.iteritems() if v != self.original_type_map.get(k, None)}

    def apply_changes(self, container):
        from calibre.ebooks.oeb.polish.opf import set_guide_item, get_book_language
        from calibre.translations.dynamic import translate
        lang = get_book_language(container)
        for item_type, (name, frag) in self.changed_type_map.iteritems():
            title = self.known_type_map[item_type]
            if lang:
                title = translate(lang, title)
            set_guide_item(container, item_type, title, name, frag=frag)

    @classmethod
    def test(cls):
        import sys
        from calibre.ebooks.oeb.polish.container import get_container
        c = get_container(sys.argv[-1], tweak_mode=True)
        d = cls(c)
        if d.exec_() == d.Accepted:
            import pprint
            pprint.pprint(d.changed_type_map)
            d.apply_changes(d.container)

# }}}


class FilterCSS(Dialog):  # {{{

    def __init__(self, current_name=None, parent=None):
        self.current_name = current_name
        Dialog.__init__(self, _('Filter style information'), 'filter-css', parent=parent)

    def setup_ui(self):
        from calibre.gui2.convert.look_and_feel_ui import Ui_Form
        f, w = Ui_Form(), QWidget()
        f.setupUi(w)
        self.l = l = QFormLayout(self)
        self.setLayout(l)

        l.addRow(QLabel(_('Select what style information you want completely removed:')))
        self.h = h = QHBoxLayout()

        for name, text in (
                ('fonts', _('&Fonts')), ('margins', _('&Margins')), ('padding', _('&Padding')), ('floats', _('Flo&ats')), ('colors', _('&Colors')),
            ):
            c = QCheckBox(text)
            setattr(self, 'opt_' + name, c)
            h.addWidget(c)
            c.setToolTip(getattr(f, 'filter_css_' + name).toolTip())
        l.addRow(h)

        self.others = o = QLineEdit(self)
        l.addRow(_('&Other CSS properties:'), o)
        o.setToolTip(f.filter_css_others.toolTip())

        if self.current_name is not None:
            self.filter_current = c = QCheckBox(_('Only filter CSS in the current file (%s)') % self.current_name)
            l.addRow(c)

        l.addRow(self.bb)

    @property
    def filter_names(self):
        if self.current_name is not None and self.filter_current.isChecked():
            return (self.current_name,)
        return ()

    @property
    def filtered_properties(self):
        ans = set()
        a = ans.add
        if self.opt_fonts.isChecked():
            a('font-family')
        if self.opt_margins.isChecked():
            a('margin')
        if self.opt_padding.isChecked():
            a('padding')
        if self.opt_floats.isChecked():
            a('float'), a('clear')
        if self.opt_colors.isChecked():
            a('color'), a('background-color')
        for x in unicode(self.others.text()).split(','):
            x = x.strip()
            if x:
                a(x)
        return ans

    @classmethod
    def test(cls):
        d = cls()
        if d.exec_() == d.Accepted:
            print (d.filtered_properties)

# }}}

# Add Cover {{{


class CoverView(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.current_pixmap_size = QSize(0, 0)
        self.pixmap = QPixmap()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_pixmap(self, data):
        self.pixmap.loadFromData(data)
        self.current_pixmap_size = self.pixmap.size()
        self.update()

    def paintEvent(self, event):
        if self.pixmap.isNull():
            return
        canvas_size = self.rect()
        width = self.current_pixmap_size.width()
        extrax = canvas_size.width() - width
        if extrax < 0:
            extrax = 0
        x = int(extrax/2.)
        height = self.current_pixmap_size.height()
        extray = canvas_size.height() - height
        if extray < 0:
            extray = 0
        y = int(extray/2.)
        target = QRect(x, y, min(canvas_size.width(), width), min(canvas_size.height(), height))
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        p.drawPixmap(target, self.pixmap.scaled(target.size(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation))
        p.end()

    def sizeHint(self):
        return QSize(300, 400)


class AddCover(Dialog):

    import_requested = pyqtSignal(object, object)

    def __init__(self, container, parent=None):
        self.container = container
        Dialog.__init__(self, _('Add a cover'), 'add-cover-wizard', parent)

    @property
    def image_names(self):
        img_types = {guess_type('a.'+x) for x in ('png', 'jpeg', 'gif')}
        for name, mt in self.container.mime_map.iteritems():
            if mt.lower() in img_types:
                yield name

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)
        self.gb  = gb = QGroupBox(_('&Images in book'), self)
        self.v = v = QVBoxLayout(gb)
        gb.setLayout(v), gb.setFlat(True)
        self.names, self.names_filter = create_filterable_names_list(
            sorted(self.image_names, key=sort_key), filter_text=_('Filter the list of images'), parent=self)
        self.names.doubleClicked.connect(self.double_clicked, type=Qt.QueuedConnection)
        self.cover_view = CoverView(self)
        l.addWidget(self.names_filter)
        v.addWidget(self.names)

        self.splitter = s = QSplitter(self)
        l.addWidget(s)
        s.addWidget(gb)
        s.addWidget(self.cover_view)

        self.h = h = QHBoxLayout()
        self.preserve = p = QCheckBox(_('Preserve aspect ratio'))
        p.setToolTip(textwrap.fill(_('If enabled the cover image you select will be embedded'
                       ' into the book in such a way that when viewed, its aspect'
                       ' ratio (ratio of width to height) will be preserved.'
                       ' This will mean blank spaces around the image if the screen'
                       ' the book is being viewed on has an aspect ratio different'
                       ' to the image.')))
        p.setChecked(tprefs['add_cover_preserve_aspect_ratio'])
        p.setVisible(self.container.book_type != 'azw3')
        p.stateChanged.connect(lambda s:tprefs.set('add_cover_preserve_aspect_ratio', s == Qt.Checked))
        self.info_label = il = QLabel('\xa0')
        h.addWidget(p), h.addStretch(1), h.addWidget(il)
        l.addLayout(h)

        l.addWidget(self.bb)
        b = self.bb.addButton(_('Import &image'), self.bb.ActionRole)
        b.clicked.connect(self.import_image)
        b.setIcon(QIcon(I('document_open.png')))
        self.names.setFocus(Qt.OtherFocusReason)
        self.names.selectionModel().currentChanged.connect(self.current_image_changed)

    def double_clicked(self):
        self.accept()

    @property
    def file_name(self):
        return self.names.model().name_for_index(self.names.currentIndex())

    def current_image_changed(self):
        self.info_label.setText('')
        name = self.file_name
        if name is not None:
            data = self.container.raw_data(name, decode=False)
            self.cover_view.set_pixmap(data)
            self.info_label.setText('{0}x{1}px | {2}'.format(
                self.cover_view.pixmap.width(), self.cover_view.pixmap.height(), human_readable(len(data))))

    def import_image(self):
        ans = choose_images(self, 'add-cover-choose-image', _('Choose a cover image'), formats=(
            'jpg', 'jpeg', 'png', 'gif'))
        if ans:
            from calibre.gui2.tweak_book.file_list import NewFileDialog
            d = NewFileDialog(self)
            d.do_import_file(ans[0], hide_button=True)
            if d.exec_() == d.Accepted:
                self.import_requested.emit(d.file_name, d.file_data)
                self.container = current_container()
                self.names_filter.clear()
                self.names.model().set_names(sorted(self.image_names, key=sort_key))
                i = self.names.model().find_name(d.file_name)
                self.names.setCurrentIndex(self.names.model().index(i))
                self.current_image_changed()

    @classmethod
    def test(cls):
        import sys
        from calibre.ebooks.oeb.polish.container import get_container
        c = get_container(sys.argv[-1], tweak_mode=True)
        d = cls(c)
        if d.exec_() == d.Accepted:
            pass

# }}}


class PlainTextEdit(QPlainTextEdit):  # {{{

    ''' A class that overrides some methods from QPlainTextEdit to fix handling
    of the nbsp unicode character and AltGr input method on windows. '''

    def __init__(self, parent=None):
        QPlainTextEdit.__init__(self, parent)
        self.syntax = None

    def toPlainText(self):
        # QPlainTextEdit's toPlainText implementation replaces nbsp with normal
        # space, so we re-implement it using QTextCursor, which does not do
        # that
        c = self.textCursor()
        c.clearSelection()
        c.movePosition(c.Start)
        c.movePosition(c.End, c.KeepAnchor)
        ans = c.selectedText().replace(PARAGRAPH_SEPARATOR, '\n')
        # QTextCursor pads the return value of selectedText with null bytes if
        # non BMP characters such as 0x1f431 are present.
        return ans.rstrip('\0')

    def selected_text_from_cursor(self, cursor):
        return unicodedata.normalize('NFC', unicode(cursor.selectedText()).replace(PARAGRAPH_SEPARATOR, '\n').rstrip('\0'))

    @property
    def selected_text(self):
        return self.selected_text_from_cursor(self.textCursor())

    def createMimeDataFromSelection(self):
        ans = QMimeData()
        ans.setText(self.selected_text)
        return ans

    def show_tooltip(self, ev):
        pass

    def override_shortcut(self, ev):
        if iswindows and self.windows_ignore_altgr_shortcut(ev):
            ev.accept()
            return True

    def windows_ignore_altgr_shortcut(self, ev):
        import win32api, win32con
        s = win32api.GetAsyncKeyState(win32con.VK_RMENU) & 0xffff  # VK_RMENU == R_ALT
        return s & 0x8000

    def event(self, ev):
        et = ev.type()
        if et == ev.ToolTip:
            self.show_tooltip(ev)
            return True
        if et == ev.ShortcutOverride:
            ret = self.override_shortcut(ev)
            if ret:
                return True
        return QPlainTextEdit.event(self, ev)

# }}}


if __name__ == '__main__':
    app = QApplication([])
    AddCover.test()
