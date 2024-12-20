#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re
from threading import Thread

from qt.core import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QIcon,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPalette,
    QPen,
    QPixmap,
    QProgressBar,
    QSize,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    Qt,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre import fit_image, force_unicode, human_readable
from calibre.ebooks.oeb.polish.main import CUSTOMIZATION
from calibre.gui2 import empty_index, question_dialog
from calibre.gui2.tweak_book import current_container, set_current_container, tprefs
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.startup import connect_lambda
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
    d.m = m = QCheckBox(_('Merge CSS rules with identical &selectors'))
    m.setChecked(tprefs['merge_identical_selectors'])
    l.addWidget(m)
    d.la3 = label('<span style="font-size:small; font-style: italic">' + _(
        'Merge CSS rules in the same stylesheet that have identical selectors.'
    ' Note that in rare cases merging can result in a change to the effective styling'
    ' of the book, so use with care.'))
    d.p = p = QCheckBox(_('Merge CSS rules with identical &properties'))
    p.setChecked(tprefs['merge_rules_with_identical_properties'])
    l.addWidget(p)
    d.la4 = label('<span style="font-size:small; font-style: italic">' + _(
        'Merge CSS rules in the same stylesheet that have identical properties.'
    ' Note that in rare cases merging can result in a change to the effective styling'
    ' of the book, so use with care.'))
    d.u = u = QCheckBox(_('Remove &unreferenced style sheets'))
    u.setChecked(tprefs['remove_unreferenced_sheets'])
    l.addWidget(u)
    d.la5 = label('<span style="font-size:small; font-style: italic">' + _(
        'Remove stylesheets that are not referenced by any content.'
    ))

    d.bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    d.l.addWidget(d.bb)
    d.bb.rejected.connect(d.reject)
    d.bb.accepted.connect(d.accept)
    ret = d.exec()
    ans['remove_unused_classes'] = tprefs['remove_unused_classes'] = c.isChecked()
    ans['merge_identical_selectors'] = tprefs['merge_identical_selectors'] = m.isChecked()
    ans['merge_rules_with_identical_properties'] = tprefs['merge_rules_with_identical_properties'] = p.isChecked()
    ans['remove_unreferenced_sheets'] = tprefs['remove_unreferenced_sheets'] = u.isChecked()
    if ret != QDialog.DialogCode.Accepted:
        raise Abort()


def get_customization(action, name, parent):
    ans = CUSTOMIZATION.copy()
    try:
        if action == 'remove_unused_css':
            customize_remove_unused_css(name, parent, ans)
        elif action == 'upgrade_book':
            ans['remove_ncx'] = tprefs['remove_ncx'] = question_dialog(
                parent, _('Remove NCX ToC file'),
                _('Remove the legacy Table of Contents in NCX form?'),
                _('This form of Table of Contents is superseded by the new HTML based Table of Contents.'
                  ' Leaving it behind is useful only if you expect this book to be read on very'
                  ' old devices that lack proper support for EPUB 3'),
                skip_dialog_name='edit-book-remove-ncx',
                skip_dialog_msg=_('Ask this question again in the future'),
                skip_dialog_skipped_value=tprefs['remove_ncx'],
                yes_text=_('Remove NCX'), no_text=_('Keep NCX')
            )
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
    d.bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    d.show_changes = False
    if changed:
        b = d.b = d.bb.addButton(_('See what &changed'), QDialogButtonBox.ButtonRole.AcceptRole)
        b.setIcon(QIcon.ic('diff.png')), b.setAutoDefault(False)
        connect_lambda(b.clicked, d, lambda d: setattr(d, 'show_changes', True))
    b = d.bb.addButton(_('&Copy to clipboard'), QDialogButtonBox.ButtonRole.ActionRole)
    b.setIcon(QIcon.ic('edit-copy.png')), b.setAutoDefault(False)

    def copy_report():
        text = re.sub(r'</.+?>', '\n', report)
        text = re.sub(r'<.+?>', '', text)
        cp = QApplication.instance().clipboard()
        cp.setText(text)

    b.clicked.connect(copy_report)
    d.bb.button(QDialogButtonBox.StandardButton.Close).setDefault(True)
    d.l.addWidget(d.bb)
    d.bb.rejected.connect(d.reject)
    d.bb.accepted.connect(d.accept)
    d.resize(600, 400)
    d.exec()
    b.clicked.disconnect()
    if d.show_changes:
        show_current_diff(allow_revert=True)

# CompressImages {{{


class ImageItemDelegate(QStyledItemDelegate):

    def sizeHint(self, option, index):
        return QSize(300, 100)

    def paint(self, painter, option, index):
        name = index.data(Qt.ItemDataRole.DisplayRole)
        sz = human_readable(index.data(Qt.ItemDataRole.UserRole))
        pmap = index.data(Qt.ItemDataRole.UserRole+1)
        irect = option.rect.adjusted(0, 5, 0, -5)
        irect.setRight(irect.left() + 70)
        if pmap is None:
            pmap = QPixmap(current_container().get_file_path_for_processing(name))
            scaled, nwidth, nheight = fit_image(pmap.width(), pmap.height(), irect.width(), irect.height())
            if scaled:
                pmap = pmap.scaled(nwidth, nheight, transformMode=Qt.TransformationMode.SmoothTransformation)
            index.model().setData(index, pmap, Qt.ItemDataRole.UserRole+1)
        x, y = (irect.width() - pmap.width())//2, (irect.height() - pmap.height())//2
        r = irect.adjusted(x, y, -x, -y)
        QStyledItemDelegate.paint(self, painter, option, empty_index)
        painter.drawPixmap(r, pmap)
        trect = irect.adjusted(irect.width() + 10, 0, 0, 0)
        trect.setRight(option.rect.right())
        painter.save()
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(QPen(option.palette.color(QPalette.ColorRole.HighlightedText)))
        painter.drawText(trect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name + '\n' + sz)
        painter.restore()


class LossyCompression(QWidget):

    def __init__(self, image_type, default_compression=80, parent=None):
        super().__init__(parent)
        l = QVBoxLayout(self)
        image_type = image_type.upper()
        self.enable_lossy = el = QCheckBox(_('Enable &lossy compression of {} images').format(image_type))
        el.setToolTip(_('This allows you to change the quality factor used for {} images.\nBy lowering'
                        ' the quality you can greatly reduce file size, at the expense of the image looking blurred.').format(image_type))
        l.addWidget(el)
        self.h2 = h = QHBoxLayout()
        l.addLayout(h)
        self.jq = jq = QSpinBox(self)
        image_type = image_type.lower()
        self.image_type = image_type
        self.quality_pref_name = f'{image_type}_compression_quality_for_lossless_compression'
        jq.setMinimum(1), jq.setMaximum(100), jq.setValue(tprefs.get(self.quality_pref_name, default_compression))
        jq.setEnabled(False)
        jq.setToolTip(_('The image quality, 1 is high compression with low image quality, 100 is low compression with high image quality'))
        jq.valueChanged.connect(self.save_compression_quality)
        el.toggled.connect(jq.setEnabled)
        self.jql = la = QLabel(_('Image &quality:'))
        la.setBuddy(jq)
        h.addWidget(la), h.addWidget(jq)

    def save_compression_quality(self):
        tprefs.set(self.quality_pref_name, self.jq.value())


class CompressImages(Dialog):

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Compress images'), 'compress-images', parent=parent)

    def setup_ui(self):
        from calibre.ebooks.oeb.polish.images import get_compressible_images
        self.setWindowIcon(QIcon.ic('compress-image.png'))
        self.h = h = QHBoxLayout(self)
        self.images = i = QListWidget(self)
        h.addWidget(i)
        self.l = l = QVBoxLayout()
        h.addLayout(l)
        c = current_container()
        for name in sorted(get_compressible_images(c), key=numeric_sort_key):
            x = QListWidgetItem(name, i)
            x.setData(Qt.ItemDataRole.UserRole, c.filesize(name))
        i.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        i.setMinimumHeight(350), i.setMinimumWidth(350)
        i.selectAll(), i.setSpacing(5)
        self.delegate = ImageItemDelegate(self)
        i.setItemDelegate(self.delegate)
        self.la = la = QLabel(_(
            'You can compress the images in this book losslessly, reducing the file size of the book,'
            ' without affecting image quality. Typically image size is reduced by 5 - 15%.'))
        la.setWordWrap(True)
        la.setMinimumWidth(250)
        l.addWidget(la)
        self.jpeg = LossyCompression('jpeg', parent=self)
        l.addSpacing(30), l.addWidget(self.jpeg)
        self.webp = LossyCompression('webp', default_compression=75, parent=self)
        l.addSpacing(30), l.addWidget(self.webp)
        l.addStretch(10)
        l.addWidget(self.bb)

    @property
    def names(self):
        return {item.text() for item in self.images.selectedItems()}

    @property
    def jpeg_quality(self):
        if not self.jpeg.enable_lossy.isChecked():
            return None
        return self.jpeg.jq.value()

    @property
    def webp_quality(self):
        if not self.webp.enable_lossy.isChecked():
            return None
        return self.webp.jq.value()



class CompressImagesProgress(Dialog):

    gui_loop = pyqtSignal(object, object, object)
    cidone = pyqtSignal()

    def __init__(self, names=None, jpeg_quality=None, webp_quality=None, parent=None):
        self.names, self.jpeg_quality = names, jpeg_quality
        self.webp_quality = webp_quality
        self.keep_going = True
        self.result = (None, '')
        Dialog.__init__(self, _('Compressing images...'), 'compress-images-progress', parent=parent)
        self.gui_loop.connect(self.update_progress, type=Qt.ConnectionType.QueuedConnection)
        self.cidone.connect(self.accept, type=Qt.ConnectionType.QueuedConnection)
        t = Thread(name='RunCompressImages', target=self.run_compress)
        t.daemon = True
        t.start()

    def run_compress(self):
        from calibre.ebooks.oeb.polish.images import compress_images
        from calibre.gui2.tweak_book import current_container
        report = []
        try:
            self.result = (compress_images(
                current_container(), report=report.append, names=self.names, jpeg_quality=self.jpeg_quality, webp_quality=self.webp_quality,
                progress_callback=self.progress_callback
            )[0], report)
        except Exception:
            import traceback
            self.result = (None, traceback.format_exc())
        self.cidone.emit()

    def setup_ui(self):
        self.setWindowIcon(QIcon.ic('compress-image.png'))
        self.setCursor(Qt.CursorShape.BusyCursor)
        self.setMinimumWidth(350)
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(_('Compressing images, please wait...'))
        la.setStyleSheet('QLabel { font-weight: bold }'), la.setAlignment(Qt.AlignmentFlag.AlignCenter), la.setTextFormat(Qt.TextFormat.PlainText)
        l.addWidget(la)
        self.progress = p = QProgressBar(self)
        p.setMinimum(0), p.setMaximum(0)
        l.addWidget(p)
        self.msg = la = QLabel('\xa0')
        la.setAlignment(Qt.AlignmentFlag.AlignCenter), la.setTextFormat(Qt.TextFormat.PlainText)
        l.addWidget(la)

        self.bb.setStandardButtons(QDialogButtonBox.StandardButton.Cancel)
        l.addWidget(self.bb)

    def reject(self):
        self.keep_going = False
        self.bb.button(QDialogButtonBox.StandardButton.Cancel).setEnabled(False)
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
    import sys

    import sip

    from calibre.ebooks.oeb.polish.container import get_container
    c = get_container(sys.argv[-1], tweak_mode=True)
    set_current_container(c)
    d = CompressImages()
    if d.exec() == QDialog.DialogCode.Accepted:
        pass
    sip.delete(app)
    del app
