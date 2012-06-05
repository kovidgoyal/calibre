#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from collections import namedtuple

from PyQt4.Qt import (QDialog, Qt, QLabel, QGridLayout, QPixmap,
        QDialogButtonBox, QApplication, QSize, pyqtSignal, QIcon,
        QPlainTextEdit)

from calibre.constants import __version__
from calibre.gui2.dialogs.message_box import ViewLog

Question = namedtuple('Question', 'payload callback cancel_callback '
        'title msg html_log log_viewer_title log_is_file det_msg '
        'show_copy_button')

class ProceedQuestion(QDialog):

    ask_question = pyqtSignal(object, object)

    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setWindowIcon(QIcon(I('dialog_question.png')))

        self.questions = []

        self._l = l = QGridLayout(self)
        self.setLayout(l)

        self.icon_label = ic = QLabel(self)
        ic.setPixmap(QPixmap(I('dialog_question.png')))
        self.msg_label = msg = QLabel('some random filler text')
        msg.setWordWrap(True)
        ic.setMaximumWidth(110)
        ic.setMaximumHeight(100)
        ic.setScaledContents(True)
        ic.setStyleSheet('QLabel { margin-right: 10px }')
        self.bb = QDialogButtonBox()
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        self.log_button = self.bb.addButton(_('View log'), self.bb.ActionRole)
        self.log_button.setIcon(QIcon(I('debug.png')))
        self.log_button.clicked.connect(self.show_log)
        self.copy_button = self.bb.addButton(_('&Copy to clipboard'),
                self.bb.ActionRole)
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        self.show_det_msg = _('Show &details')
        self.hide_det_msg = _('Hide &details')
        self.det_msg_toggle = self.bb.addButton(self.show_det_msg, self.bb.ActionRole)
        self.det_msg_toggle.clicked.connect(self.toggle_det_msg)
        self.det_msg_toggle.setToolTip(
                _('Show detailed information about this error'))
        self.det_msg = QPlainTextEdit(self)
        self.det_msg.setReadOnly(True)
        self.bb.setStandardButtons(self.bb.Yes|self.bb.No)
        self.bb.button(self.bb.Yes).setDefault(True)

        l.addWidget(ic, 0, 0, 1, 1)
        l.addWidget(msg, 0, 1, 1, 1)
        l.addWidget(self.det_msg, 1, 0, 1, 2)
        l.addWidget(self.bb, 2, 0, 1, 2)

        self.ask_question.connect(self.do_ask_question,
                type=Qt.QueuedConnection)

    def copy_to_clipboard(self, *args):
        QApplication.clipboard().setText(
                'calibre, version %s\n%s: %s\n\n%s' %
                (__version__, unicode(self.windowTitle()),
                    unicode(self.msg_label.text()),
                    unicode(self.det_msg.toPlainText())))
        self.copy_button.setText(_('Copied'))

    def accept(self):
        if self.questions:
            payload, callback, cancel_callback = self.questions[0][:3]
            self.questions = self.questions[1:]
            self.ask_question.emit(callback, payload)
        self.hide()

    def reject(self):
        if self.questions:
            payload, callback, cancel_callback = self.questions[0][:3]
            self.questions = self.questions[1:]
            self.ask_question.emit(cancel_callback, payload)
        self.hide()

    def do_ask_question(self, callback, payload):
        if callable(callback):
            callback(payload)
        self.show_question()

    def toggle_det_msg(self, *args):
        vis = unicode(self.det_msg_toggle.text()) == self.hide_det_msg
        self.det_msg_toggle.setText(self.show_det_msg if vis else
                self.hide_det_msg)
        self.det_msg.setVisible(not vis)
        self.do_resize()

    def do_resize(self):
        sz = self.sizeHint() + QSize(100, 0)
        sz.setWidth(min(500, sz.width()))
        sz.setHeight(min(500, sz.height()))
        self.resize(sz)

    def show_question(self):
        if self.isVisible(): return
        if self.questions:
            question = self.questions[0]
            self.msg_label.setText(question.msg)
            self.setWindowTitle(question.title)
            self.log_button.setVisible(bool(question.html_log))
            self.copy_button.setVisible(bool(question.show_copy_button))
            self.det_msg.setPlainText(question.det_msg or '')
            self.det_msg.setVisible(False)
            self.det_msg_toggle.setVisible(bool(question.det_msg))
            self.det_msg_toggle.setText(self.show_det_msg)
            self.bb.button(self.bb.Yes).setDefault(True)
            self.do_resize()
            self.bb.button(self.bb.Yes).setFocus(Qt.OtherFocusReason)
            self.show()

    def __call__(self, callback, payload, html_log, log_viewer_title, title,
            msg, det_msg='', show_copy_button=False, cancel_callback=None,
            log_is_file=False):
        '''
        A non modal popup that notifies the user that a background task has
        been completed. This class guarantees that onlya single popup is
        visible at any one time. Other requests are queued and displayed after
        the user dismisses the current popup.

        :param callback: A callable that is called with payload if the user
        asks to proceed. Note that this is always called in the GUI thread.
        :param cancel_callback: A callable that is called with the payload if
        the users asks not to proceed.
        :param payload: Arbitrary object, passed to callback
        :param html_log: An HTML or plain text log
        :param log_viewer_title: The title for the log viewer window
        :param title: The title for this popup
        :param msg: The msg to display
        :param det_msg: Detailed message
        :param log_is_file: If True the html_log parameter is interpreted as
        the path to a file on disk containing the log encoded with utf-8
        '''
        question = Question(payload, callback, cancel_callback, title, msg,
                html_log, log_viewer_title, log_is_file, det_msg,
                show_copy_button)
        self.questions.append(question)
        self.show_question()

    def show_log(self):
        if self.questions:
            q = self.questions[0]
            log = q.html_log
            if q.log_is_file:
                with open(log, 'rb') as f:
                    log = f.read().decode('utf-8')
            self.log_viewer = ViewLog(q.log_viewer_title, log,
                        parent=self)

if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    ProceedQuestion(None).exec_()

