#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from threading import Thread

from PyQt5.Qt import (
    pyqtSignal, QWidget, QListWidget, QListWidgetItem, QLabel, Qt,
    QVBoxLayout, QScrollArea, QProgressBar, QGridLayout, QSize, QIcon)

from calibre.gui2 import error_dialog, info_dialog, warning_dialog
from calibre.gui2.tweak_book import current_container
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.gui2.progress_indicator import WaitStack
from calibre.ebooks.oeb.polish.download import get_external_resources, download_external_resources, replace_resources


class ChooseResources(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(_('Choose the external resources to download'))
        la.setWordWrap(True)
        l.addWidget(la)
        self.items = i = QListWidget(self)
        l.addWidget(i)

    def __iter__(self):
        for i in xrange(self.items.count()):
            yield self.items.item(i)

    def select_none(self):
        for item in self:
            item.setCheckState(Qt.Unchecked)

    def select_all(self):
        for item in self:
            item.setCheckState(Qt.Checked)

    @property
    def resources(self):
        return {i.data(Qt.UserRole):self.original_resources[i.data(Qt.UserRole)] for i in self if i.checkState() == Qt.Checked}

    @resources.setter
    def resources(self, resources):
        self.items.clear()
        self.original_resources = resources
        dc = 0
        for url, matches in resources.iteritems():
            text = url
            num = len(matches)
            if text.startswith('data:'):
                dc += 1
                text = _('Data URL #{}').format(dc)
            text += ' ({})'.format(ngettext('one instance', '{} instances', num).format(num))
            i = QListWidgetItem(text, self.items)
            i.setData(Qt.UserRole, url)
            i.setCheckState(Qt.Checked)
            i.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)


class DownloadStatus(QScrollArea):

    def __init__(self, parent=None):
        QScrollArea.__init__(self, parent)
        self.setWidgetResizable(True)
        self.w = QWidget(self)
        self.l = QGridLayout(self.w)
        self.setWidget(self.w)

    def __call__(self, resources):
        self.url_map = {}
        self.labels = []
        for url in resources:
            p = self.url_map[url] = QProgressBar(self.w)
            p.setRange(0, 0)
            self.l.addWidget(p, self.l.rowCount(), 0)
            la = QLabel('\xa0' + url)
            self.labels.append(la)
            self.l.addWidget(la, self.l.rowCount()-1, 1)
        self.l.addWidget(QLabel(''))
        self.l.setRowStretch(self.l.rowCount()-1, 10)

    def progress(self, url, done, total):
        p = self.url_map.get(url)
        if p is not None:
            if total > 0:
                p.setRange(0, total)
                p.setValue(done)
            else:
                p.setRange(0, 0)


class DownloadResources(Dialog):

    get_done = pyqtSignal(object, object)
    progress = pyqtSignal(object, object, object)
    download_done = pyqtSignal(object, object)
    replace_done = pyqtSignal(object, object)

    def __init__(self, parent=None):
        self.resources_replaced = False
        self.show_diff = False
        Dialog.__init__(self, _('Download external resources'), 'download-external-resources', parent)
        self.state = 0
        self.get_done.connect(self._get_done)
        self.download_done.connect(self._download_done)
        self.replace_done.connect(self._replace_done)
        self.progress.connect(self.download_status.progress, type=Qt.QueuedConnection)

    def setup_ui(self):
        self.setWindowIcon(QIcon(I('download-metadata.png')))
        self.choose_resources = cr = ChooseResources(self)
        self.download_status = ds = DownloadStatus(self)
        self.success = s = QLabel('')
        s.setWordWrap(True)
        self.l = l = QVBoxLayout(self)
        self.wait = WaitStack(_('Searching for external resources...'), cr, self)
        self.wait.addWidget(ds), self.wait.addWidget(s)
        self.wait.start()
        for t, f in ((_('Select &none'), cr.select_none), (_('Select &all'), cr.select_all)):
            b = self.bb.addButton(t, self.bb.ActionRole)
            b.clicked.connect(f), b.setAutoDefault(False)
        self.bb.setVisible(False)
        l.addWidget(self.wait), l.addWidget(self.bb)
        t = Thread(name='GetResources', target=self.get_resources)
        t.daemon = True
        t.start()

    def get_resources(self):
        tb = None
        try:
            ret = get_external_resources(current_container())
        except Exception as err:
            import traceback
            ret, tb = err, traceback.format_exc()
        self.get_done.emit(ret, tb)

    def _get_done(self, x, tb):
        if not self.isVisible():
            return self.reject()
        if tb is not None:
            error_dialog(self, _('Scan failed'), _(
                'Failed to scan for external resources, click "Show Details" for more information.'),
                         det_msg=tb, show=True)
            self.reject()
        else:
            self.wait.stop()
            self.state = 1
            resources = x
            if not resources:
                info_dialog(self, _('No external resources found'), _(
                    'No external resources were found in this book.'), show=True)
                self.reject()
                return
            self.choose_resources.resources = resources
            self.bb.setVisible(True)

    def download_resources(self, resources):
        tb = None
        try:
            ret = download_external_resources(current_container(), resources, progress_report=self.progress.emit)
        except Exception as err:
            import traceback
            ret, tb = err, traceback.format_exc()
        self.download_done.emit(ret, tb)

    def _download_done(self, ret, tb):
        if not self.isVisible():
            return self.reject()
        if tb is not None:
            error_dialog(self, _('Download failed'), _(
                'Failed to download external resources, click "Show Details" for more information.'),
                         det_msg=tb, show=True)
            self.reject()
        else:
            replacements, failures = ret
            if failures:
                tb = ['{}\n\t{}\n'.format(url, err) for url, err in failures.iteritems()]
                if not replacements:
                    error_dialog(self, _('Download failed'), _(
                        'Failed to download external resources, click "Show Details" for more information.'),
                                det_msg='\n'.join(tb), show=True)
                    self.reject()
                    return
                else:
                    warning_dialog(self, _('Some downloads failed'), _(
                        'Failed to download some external resources, click "Show Details" for more information.'),
                                det_msg='\n'.join(tb), show=True)
            self.state = 2
            self.wait.msg = _('Updating resources in book...')
            self.wait.start()
            t = ngettext(
                'Successfully processed the external resource', 'Successfully processed {} external resources', len(replacements)).format(len(replacements))
            if failures:
                t += '<br>' + ngettext('Could not download one image', 'Could not download {} images', len(failures)).format(len(failures))
            self.success.setText('<p style="text-align:center">' + t)
            resources = self.choose_resources.resources
            t = Thread(name='ReplaceResources', target=self.replace_resources, args=(resources, replacements))
            t.daemon = True
            t.start()

    def replace_resources(self, resources, replacements):
        tb = None
        try:
            ret = replace_resources(current_container(), resources, replacements)
        except Exception as err:
            import traceback
            ret, tb = err, traceback.format_exc()
        self.replace_done.emit(ret, tb)

    def _replace_done(self, ret, tb):
        if tb is not None:
            error_dialog(self, _('Replace failed'), _(
                'Failed to replace external resources, click "Show Details" for more information.'),
                         det_msg=tb, show=True)
            Dialog.reject(self)
        else:
            self.wait.setCurrentIndex(3)
            self.state = 3
            self.bb.clear()
            self.resources_replaced = True
            self.bb.setStandardButtons(self.bb.Ok | self.bb.Close)
            b = self.bb.button(self.bb.Ok)
            b.setText(_('See what &changed'))
            b.setIcon(QIcon(I('diff.png')))
            b.clicked.connect(lambda : setattr(self, 'show_diff', True))
            self.bb.setVisible(True)

    def accept(self):
        if self.state == 0:
            return self.reject()
        if self.state == 1:
            resources = self.choose_resources.resources
            self.download_status(resources)
            self.wait.setCurrentIndex(2)
            self.bb.setVisible(False)
            t = Thread(name='DownloadResources', target=self.download_resources, args=(resources,))
            t.daemon = True
            t.start()
            return
        if self.state == 2:
            return
        self.wait.stop()
        Dialog.accept(self)

    def reject(self):
        if self.state == 2:
            return
        self.wait.stop()
        return Dialog.reject(self)

    def sizeHint(self):
        return QSize(800, 500)


if __name__ == '__main__':
    from calibre.gui2 import Application
    import sys
    app = Application([])
    from calibre.gui2.tweak_book import set_current_container
    from calibre.gui2.tweak_book.boss import get_container
    set_current_container(get_container(sys.argv[-1]))
    d = DownloadResources()
    d.exec_()
    print(d.show_diff)
    del d, app
