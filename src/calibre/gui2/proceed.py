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
        QPlainTextEdit, QCheckBox)

from calibre.constants import __version__
from calibre.gui2.dialogs.message_box import ViewLog

Question = namedtuple('Question', 'payload callback cancel_callback '
        'title msg html_log log_viewer_title log_is_file det_msg '
        'show_copy_button checkbox_msg checkbox_checked action_callback '
        'action_label action_icon')

class ProceedQuestion(QDialog):

    ask_question = pyqtSignal(object, object, object)

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
        self.action_button = self.bb.addButton('', self.bb.ActionRole)
        self.action_button.clicked.connect(self.action_clicked)
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

        self.checkbox = QCheckBox('', self)

        l.addWidget(ic, 0, 0, 1, 1)
        l.addWidget(msg, 0, 1, 1, 1)
        l.addWidget(self.checkbox, 1, 0, 1, 2)
        l.addWidget(self.det_msg, 2, 0, 1, 2)
        l.addWidget(self.bb, 3, 0, 1, 2)

        self.ask_question.connect(self.do_ask_question,
                type=Qt.QueuedConnection)

    def copy_to_clipboard(self, *args):
        QApplication.clipboard().setText(
                'calibre, version %s\n%s: %s\n\n%s' %
                (__version__, unicode(self.windowTitle()),
                    unicode(self.msg_label.text()),
                    unicode(self.det_msg.toPlainText())))
        self.copy_button.setText(_('Copied'))

    def action_clicked(self):
        if self.questions:
            q = self.questions[0]
            self.questions[0] = q._replace(callback=q.action_callback)
        self.accept()

    def accept(self):
        if self.questions:
            payload, callback, cancel_callback = self.questions[0][:3]
            self.questions = self.questions[1:]
            cb = None
            if self.checkbox.isVisible():
                cb = bool(self.checkbox.isChecked())
            self.ask_question.emit(callback, payload, cb)
        self.hide()

    def reject(self):
        if self.questions:
            payload, callback, cancel_callback = self.questions[0][:3]
            self.questions = self.questions[1:]
            cb = None
            if self.checkbox.isVisible():
                cb = bool(self.checkbox.isChecked())
            self.ask_question.emit(cancel_callback, payload, cb)
        self.hide()

    def do_ask_question(self, callback, payload, checkbox_checked):
        if callable(callback):
            args = [payload]
            if checkbox_checked is not None:
                args.append(checkbox_checked)
            callback(*args)
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
        if self.isVisible():
            return
        if self.questions:
            question = self.questions[0]
            self.msg_label.setText(question.msg)
            self.setWindowTitle(question.title)
            self.log_button.setVisible(bool(question.html_log))
            self.copy_button.setVisible(bool(question.show_copy_button))
            self.action_button.setVisible(question.action_callback is not None)
            if question.action_callback is not None:
                self.action_button.setText(question.action_label or '')
                self.action_button.setIcon(
                    QIcon() if question.action_icon is None else question.action_icon)
            self.det_msg.setPlainText(question.det_msg or '')
            self.det_msg.setVisible(False)
            self.det_msg_toggle.setVisible(bool(question.det_msg))
            self.det_msg_toggle.setText(self.show_det_msg)
            self.checkbox.setVisible(question.checkbox_msg is not None)
            if question.checkbox_msg is not None:
                self.checkbox.setText(question.checkbox_msg)
                self.checkbox.setChecked(question.checkbox_checked)
            self.do_resize()
            self.show()
            self.bb.button(self.bb.Yes).setDefault(True)
            self.bb.button(self.bb.Yes).setFocus(Qt.OtherFocusReason)

    def __call__(self, callback, payload, html_log, log_viewer_title, title,
            msg, det_msg='', show_copy_button=False, cancel_callback=None,
            log_is_file=False, checkbox_msg=None, checkbox_checked=False,
            action_callback=None, action_label=None, action_icon=None):
        '''
        A non modal popup that notifies the user that a background task has
        been completed. This class guarantees that only a single popup is
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
                            the path to a file on disk containing the log
                            encoded with utf-8
        :param checkbox_msg: If not None, a checkbox is displayed in the
                             dialog, showing this message. The callback is
                             called with both the payload and the state of the
                             checkbox as arguments.
        :param checkbox_checked: If True the checkbox is checked by default.
        :param action_callback: If not None, an extra button is added, which
                                when clicked will cause action_callback to be called
                                instead of callback. action_callback is called in
                                exactly the same way as callback.
        :param action_label: The text on the action button
        :param action_icon: The icon for the action button, must be a QIcon object or None

        '''
        question = Question(
            payload, callback, cancel_callback, title, msg, html_log,
            log_viewer_title, log_is_file, det_msg, show_copy_button,
            checkbox_msg, checkbox_checked, action_callback, action_label,
            action_icon)
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

def main():
    from calibre.gui2 import Application
    app = Application([])
    p = ProceedQuestion(None)
    p(lambda p:None, None, 'ass', 'ass', 'testing', 'testing',
            checkbox_msg='testing the ruddy checkbox', det_msg='details')
    p.exec_()
    app

if __name__ == '__main__':
    main()

