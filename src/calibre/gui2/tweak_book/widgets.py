#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os
from itertools import izip

from PyQt4.Qt import (
    QDialog, QDialogButtonBox, QGridLayout, QLabel, QLineEdit, QVBoxLayout,
    QFormLayout, QHBoxLayout, QToolButton, QIcon, QApplication, Qt, QWidget,
    QPoint, QSizePolicy, QPainter, QStaticText, pyqtSignal, QTextOption)

from calibre import prepare_string_for_xml
from calibre.gui2 import error_dialog, choose_files, choose_save_file
from calibre.gui2.tweak_book import tprefs
from calibre.utils.matcher import get_char, Matcher

class Dialog(QDialog):

    def __init__(self, title, name, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(title)
        self.name = name
        self.bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)

        self.setup_ui()

        self.resize(self.sizeHint())
        geom = tprefs.get(name + '-geometry', None)
        if geom is not None:
            self.restoreGeometry(geom)
        if hasattr(self, 'splitter'):
            state = tprefs.get(name + '-splitter-state', None)
            if state is not None:
                self.splitter.restoreState(state)

    def accept(self):
        tprefs.set(self.name + '-geometry', bytearray(self.saveGeometry()))
        if hasattr(self, 'splitter'):
            tprefs.set(self.name + '-splitter-state', bytearray(self.splitter.saveState()))
        QDialog.accept(self)

    def reject(self):
        tprefs.set(self.name + '-geometry', bytearray(self.saveGeometry()))
        if hasattr(self, 'splitter'):
            tprefs.set(self.name + '-splitter-state', bytearray(self.splitter.saveState()))
        QDialog.reject(self)

    def setup_ui(self):
        raise NotImplementedError('You must implement this method in Dialog subclasses')

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
            ' it will not affect how they are displayed in the Files Browser'))
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
        positions = sorted(set(positions) - {-1}, reverse=True)
        text = prepare_string_for_xml(text)
        for p in positions:
            ch = get_char(text, p)
            text = '%s<span style="%s">%s</span>%s' % (text[:p], self.EMPH, ch, text[p+len(ch):])
        text = QStaticText(text)
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
        hl.setMargin(50), hl.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
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
        matches = self.matcher(text)
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

if __name__ == '__main__':
    app = QApplication([])
    QuickOpen.test()
