#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from collections import defaultdict
from threading import Thread

from PyQt5.Qt import (
    QCheckBox, QHBoxLayout, QIcon, QInputDialog, QLabel, QProgressBar, QSizePolicy,
    QStackedWidget, Qt, QTextBrowser, QVBoxLayout, QWidget, pyqtSignal
)

from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book import current_container, editors, set_current_container, tprefs
from calibre.gui2.tweak_book.boss import get_boss
from calibre.gui2.tweak_book.widgets import Dialog


def get_data(name):
    'Get the data for name. Returns a unicode string if name is a text document/stylesheet'
    if name in editors:
        return editors[name].get_raw_data()
    return current_container().raw_data(name)


def set_data(name, val):
    if name in editors:
        editors[name].replace_data(val, only_if_different=False)
    else:
        with current_container().open(name, 'wb') as f:
            f.write(val)
    get_boss().set_modified()


class CheckExternalLinks(Dialog):

    progress_made = pyqtSignal(object, object)

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Check external links'), 'check-external-links-dialog', parent)
        self.progress_made.connect(self.on_progress_made, type=Qt.QueuedConnection)

    def show(self):
        if self.rb.isEnabled():
            self.refresh()
        return Dialog.show(self)

    def refresh(self):
        self.stack.setCurrentIndex(0)
        self.rb.setEnabled(False)
        t = Thread(name='CheckLinksMaster', target=self.run)
        t.daemon = True
        t.start()

    def setup_ui(self):
        self.pb = pb = QProgressBar(self)
        pb.setTextVisible(True)
        pb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        pb.setRange(0, 0)
        self.w = w = QWidget(self)
        self.w.l = l = QVBoxLayout(w)
        l.addStretch(), l.addWidget(pb)
        self.w.la = la = QLabel(_('Checking external links, please wait...'))
        la.setStyleSheet('QLabel { font-size: 20px; font-weight: bold }')
        l.addWidget(la, 0, Qt.AlignCenter), l.addStretch()

        self.l = l = QVBoxLayout(self)
        self.results = QTextBrowser(self)
        self.results.setOpenLinks(False)
        self.results.anchorClicked.connect(self.anchor_clicked)
        self.stack = s = QStackedWidget(self)
        s.addWidget(w), s.addWidget(self.results)
        l.addWidget(s)
        self.bh = h = QHBoxLayout()
        self.check_anchors = ca = QCheckBox(_('Check &anchors'))
        ca.setToolTip(_('Check HTML anchors in links (the part after the #).\n'
            ' This can be a little slow, since it requires downloading and parsing all the HTML pages.'))
        ca.setChecked(tprefs.get('check_external_link_anchors', True))
        ca.stateChanged.connect(self.anchors_changed)
        h.addWidget(ca), h.addStretch(100), h.addWidget(self.bb)
        l.addLayout(h)
        self.bb.setStandardButtons(self.bb.Close)
        self.rb = b = self.bb.addButton(_('&Refresh'), self.bb.ActionRole)
        b.setIcon(QIcon(I('view-refresh.png')))
        b.clicked.connect(self.refresh)

    def anchors_changed(self):
        tprefs.set('check_external_link_anchors', self.check_anchors.isChecked())

    def sizeHint(self):
        ans = Dialog.sizeHint(self)
        ans.setHeight(600)
        ans.setWidth(max(ans.width(), 800))
        return ans

    def run(self):
        from calibre.ebooks.oeb.polish.check.links import check_external_links
        self.tb = None
        self.errors = []
        try:
            self.errors = check_external_links(current_container(), self.progress_made.emit, check_anchors=self.check_anchors.isChecked())
        except Exception:
            import traceback
            self.tb = traceback.format_exc()
        self.progress_made.emit(None, None)

    def on_progress_made(self, curr, total):
        if curr is None:
            self.results.setText('')
            self.stack.setCurrentIndex(1)
            self.fixed_errors = set()
            self.rb.setEnabled(True)
            if self.tb is not None:
                return error_dialog(self, _('Checking failed'), _(
                    'There was an error while checking links, click "Show details" for more information'),
                             det_msg=self.tb, show=True)
            if not self.errors:
                self.results.setText(_('No broken links found'))
            else:
                self.populate_results()
        else:
            self.pb.setMaximum(total), self.pb.setValue(curr)

    def populate_results(self, preserve_pos=False):
        num = len(self.errors) - len(self.fixed_errors)
        text = '<h3>%s</h3><ol>' % (ngettext(
            'Found a broken link', 'Found {} broken links', num).format(num))
        for i, (locations, err, url) in enumerate(self.errors):
            if i in self.fixed_errors:
                continue
            text += '<li><b>%s</b> \xa0<a href="err:%d">[%s]</a><br>%s<br><ul>' % (url, i, _('Fix this link'), err)
            for name, href, lnum, col in locations:
                text += '<li>{name} \xa0<a href="loc:{lnum},{name}">[{line}: {lnum}]</a></li>'.format(
                    name=name, lnum=lnum, line=_('line number'))
            text += '</ul></li><hr>'
        self.results.setHtml(text)

    def anchor_clicked(self, qurl):
        url = qurl.toString()
        if url.startswith('err:'):
            errnum = int(url[4:])
            err = self.errors[errnum]
            newurl, ok = QInputDialog.getText(self, _('Fix URL'), _('Enter the corrected URL:') + '\xa0'*40, text=err[2])
            if not ok:
                return
            nmap = defaultdict(set)
            for name, href in {(l[0], l[1]) for l in err[0]}:
                nmap[name].add(href)

            for name, hrefs in nmap.iteritems():
                raw = oraw = get_data(name)
                for href in hrefs:
                    raw = raw.replace(href, newurl)
                if raw != oraw:
                    set_data(name, raw)
            self.fixed_errors.add(errnum)
            self.populate_results()
        elif url.startswith('loc:'):
            lnum, name = url[4:].partition(',')[::2]
            lnum = int(lnum or 1)
            editor = get_boss().edit_file(name)
            if lnum and editor is not None and editor.has_line_numbers:
                editor.current_line = lnum


if __name__ == '__main__':
    import sys
    from calibre.gui2 import Application
    from calibre.gui2.tweak_book.boss import get_container
    app = Application([])
    set_current_container(get_container(sys.argv[-1]))
    d = CheckExternalLinks()
    d.refresh()
    d.exec_()
    del app
