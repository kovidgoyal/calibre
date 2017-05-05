#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from threading import Thread

from PyQt5.Qt import (
    QTextBrowser, QVBoxLayout, QDialog, QDialogButtonBox, QIcon, QLabel,
    QCheckBox, Qt, QListWidgetItem, QHBoxLayout, QListWidget, QPixmap,
    QSpinBox, QStyledItemDelegate, QSize, QStyle, QPen,
    QProgressBar, pyqtSignal
)

from calibre import human_readable, fit_image, force_unicode
from calibre.ebooks.oeb.polish.main import CUSTOMIZATION
from calibre.gui2 import empty_index
from calibre.gui2.tweak_book import tprefs, current_container, set_current_container
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.utils.icu import numeric_sort_key


class Abort(Exception):
    pass


def customize_remove_unused_css(name, parent, ans):
    d = QDialog(parent)
    d.l = l = QVBoxLayout()
    d.setLayout(d.l)
    d.setWindowTitle(_('Remove unused CSS'))

    def label(text):
        la = QLabel(text)
        la.setWordWrap(True), l.addWidget(la), la.setMinimumWidth(450)
        l.addWidget(la)
        return la

    d.la = label(_(
        'This will remove all CSS rules that do not match any actual content.'
        ' There are a couple of additional cleanups you can enable, below:'))
    d.c = c = QCheckBox(_('Remove unused &class attributes'))
    c.setChecked(tprefs['remove_unused_classes'])
    l.addWidget(c)
    d.la2 = label('<span style="font-size:small; font-style: italic">' + _(
        'Remove all class attributes from the HTML that do not match any existing CSS rules'))
    d.m = m = QCheckBox(_('Merge identical CSS rules'))
    m.setChecked(tprefs['merge_identical_selectors'])
    l.addWidget(m)
    d.la3 = label('<span style="font-size:small; font-style: italic">' + _(
        'Merge CSS rules in the same stylesheet that have identical selectors.'
    ' Note that in rare cases merging can result in a change to the effective styling'
    ' of the book, so use with care.'))
    d.bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    d.l.addWidget(d.bb)
    d.bb.rejected.connect(d.reject)
    d.bb.accepted.connect(d.accept)
    if d.exec_() != d.Accepted:
        raise Abort()
    ans['remove_unused_classes'] = tprefs['remove_unused_classes'] = c.isChecked()
    ans['merge_identical_selectors'] = tprefs['merge_identical_selectors'] = m.isChecked()


def get_customization(action, name, parent):
    ans = CUSTOMIZATION.copy()
    try:
        if action == 'remove_unused_css':
            customize_remove_unused_css(name, parent, ans)
    except Abort:
        return None
    return ans


def format_report(title, report):
    from calibre.ebooks.markdown import markdown
    report = [force_unicode(line) for line in report]
    return markdown('# %s\n\n'%force_unicode(title) + '\n\n'.join(report), output_format='html4')


def show_report(changed, title, report, parent, show_current_diff):
    report = format_report(title, report)
    d = QDialog(parent)
    d.setWindowTitle(_('Action report'))
    d.l = QVBoxLayout()
    d.setLayout(d.l)
    d.e = QTextBrowser(d)
    d.l.addWidget(d.e)
    d.e.setHtml(report)
    d.bb = QDialogButtonBox(QDialogButtonBox.Close)
    if changed:
        b = d.b = d.bb.addButton(_('See what &changed'), d.bb.AcceptRole)
        b.setIcon(QIcon(I('diff.png'))), b.setAutoDefault(False)
        b.clicked.connect(lambda : show_current_diff(allow_revert=True), type=Qt.QueuedConnection)
    d.bb.button(d.bb.Close).setDefault(True)
    d.l.addWidget(d.bb)
    d.bb.rejected.connect(d.reject)
    d.bb.accepted.connect(d.accept)
    d.resize(600, 400)
    d.exec_()

# CompressImages {{{


class ImageItemDelegate(QStyledItemDelegate):

    def sizeHint(self, option, index):
        return QSize(300, 100)

    def paint(self, painter, option, index):
        name = index.data(Qt.DisplayRole)
        sz = human_readable(index.data(Qt.UserRole))
        pmap = index.data(Qt.UserRole+1)
        irect = option.rect.adjusted(0, 5, 0, -5)
        irect.setRight(irect.left() + 70)
        if pmap is None:
            pmap = QPixmap(current_container().get_file_path_for_processing(name))
            scaled, nwidth, nheight = fit_image(pmap.width(), pmap.height(), irect.width(), irect.height())
            if scaled:
                pmap = pmap.scaled(nwidth, nheight, transformMode=Qt.SmoothTransformation)
            index.model().setData(index, pmap, Qt.UserRole+1)
        x, y = (irect.width() - pmap.width())//2, (irect.height() - pmap.height())//2
        r = irect.adjusted(x, y, -x, -y)
        QStyledItemDelegate.paint(self, painter, option, empty_index)
        painter.drawPixmap(r, pmap)
        trect = irect.adjusted(irect.width() + 10, 0, 0, 0)
        trect.setRight(option.rect.right())
        painter.save()
        if option.state & QStyle.State_Selected:
            painter.setPen(QPen(option.palette.color(option.palette.HighlightedText)))
        painter.drawText(trect, Qt.AlignVCenter | Qt.AlignLeft, name + '\n' + sz)
        painter.restore()


class CompressImages(Dialog):

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Compress images'), 'compress-images', parent=parent)

    def setup_ui(self):
        from calibre.ebooks.oeb.polish.images import get_compressible_images
        self.setWindowIcon(QIcon(I('compress-image.png')))
        self.h = h = QHBoxLayout(self)
        self.images = i = QListWidget(self)
        h.addWidget(i)
        self.l = l = QVBoxLayout()
        h.addLayout(l)
        c = current_container()
        for name in sorted(get_compressible_images(c), key=numeric_sort_key):
            x = QListWidgetItem(name, i)
            x.setData(Qt.UserRole, c.filesize(name))
        i.setSelectionMode(i.ExtendedSelection)
        i.setMinimumHeight(500), i.setMinimumWidth(350)
        i.selectAll(), i.setSpacing(5)
        self.delegate = ImageItemDelegate(self)
        i.setItemDelegate(self.delegate)
        self.la = la = QLabel(_(
            'You can compress the images in this book losslessly, reducing the file size of the book,'
            ' without affecting image quality. Typically image size is reduced by 5 - 15%.'))
        la.setWordWrap(True)
        la.setMinimumWidth(250)
        l.addWidget(la), l.addSpacing(30)

        self.enable_lossy = el = QCheckBox(_('Enable &lossy compression of JPEG images'))
        el.setToolTip(_('This allows you to change the quality factor used for JPEG images.\nBy lowering'
                        ' the quality you can greatly reduce file size, at the expense of the image looking blurred.'))
        l.addWidget(el)
        self.h2 = h = QHBoxLayout()
        l.addLayout(h)
        self.jq = jq = QSpinBox(self)
        jq.setMinimum(0), jq.setMaximum(100), jq.setValue(80), jq.setEnabled(False)
        jq.setToolTip(_('The compression quality, 1 is high compression, 100 is low compression.\nImage'
                        ' quality is inversely correlated with compression quality.'))
        el.toggled.connect(jq.setEnabled)
        self.jql = la = QLabel(_('Compression &quality:'))
        la.setBuddy(jq)
        h.addWidget(la), h.addWidget(jq)
        l.addStretch(10)
        l.addWidget(self.bb)

    @property
    def names(self):
        return {item.text() for item in self.images.selectedItems()}

    @property
    def jpeg_quality(self):
        if not self.enable_lossy.isChecked():
            return None
        return self.jq.value()


class CompressImagesProgress(Dialog):

    gui_loop = pyqtSignal(object, object, object)
    cidone = pyqtSignal()

    def __init__(self, names=None, jpeg_quality=None, parent=None):
        self.names, self.jpeg_quality = names, jpeg_quality
        self.keep_going = True
        self.result = (None, '')
        Dialog.__init__(self, _('Compressing images...'), 'compress-images-progress', parent=parent)
        self.gui_loop.connect(self.update_progress, type=Qt.QueuedConnection)
        self.cidone.connect(self.accept, type=Qt.QueuedConnection)
        t = Thread(name='RunCompressImages', target=self.run_compress)
        t.daemon = True
        t.start()

    def run_compress(self):
        from calibre.gui2.tweak_book import current_container
        from calibre.ebooks.oeb.polish.images import compress_images
        report = []
        try:
            self.result = (compress_images(
                current_container(), report=report.append, names=self.names, jpeg_quality=self.jpeg_quality,
                progress_callback=self.progress_callback
            )[0], report)
        except Exception:
            import traceback
            self.result = (None, traceback.format_exc())
        self.cidone.emit()

    def setup_ui(self):
        self.setWindowIcon(QIcon(I('compress-image.png')))
        self.setCursor(Qt.BusyCursor)
        self.setMinimumWidth(350)
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(_('Compressing images, please wait...'))
        la.setStyleSheet('QLabel { font-weight: bold }'), la.setAlignment(Qt.AlignCenter), la.setTextFormat(Qt.PlainText)
        l.addWidget(la)
        self.progress = p = QProgressBar(self)
        p.setMinimum(0), p.setMaximum(0)
        l.addWidget(p)
        self.msg = la = QLabel('\xa0')
        la.setAlignment(Qt.AlignCenter), la.setTextFormat(Qt.PlainText)
        l.addWidget(la)

        self.bb.setStandardButtons(self.bb.Cancel)
        l.addWidget(self.bb)

    def reject(self):
        self.keep_going = False
        self.bb.button(self.bb.Cancel).setEnabled(False)
        Dialog.reject(self)

    def progress_callback(self, num, total, name):
        self.gui_loop.emit(num, total, name)
        return self.keep_going

    def update_progress(self, num, total, name):
        self.progress.setMaximum(total), self.progress.setValue(num)
        self.msg.setText(name)

# }}}


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    import sys, sip
    from calibre.ebooks.oeb.polish.container import get_container
    c = get_container(sys.argv[-1], tweak_mode=True)
    set_current_container(c)
    d = CompressImages()
    if d.exec_() == d.Accepted:
        pass
    sip.delete(app)
    del app
