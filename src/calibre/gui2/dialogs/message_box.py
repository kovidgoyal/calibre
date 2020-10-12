#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys

from PyQt5.Qt import (
    QPainter, QDialog, QIcon, QApplication, QSize, QKeySequence,
    QAction, Qt, QTextBrowser, QDialogButtonBox, QVBoxLayout, QGridLayout,
    QLabel, QPlainTextEdit, QTextDocument, QCheckBox, pyqtSignal, QWidget,
    QSizePolicy)

from calibre.constants import __version__, isfrozen
from calibre.gui2 import gprefs
from polyglot.builtins import unicode_type


class Icon(QWidget):

    def __init__(self, parent=None, size=None):
        QWidget.__init__(self, parent)
        self.pixmap = None
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.size = size or 64

    def set_icon(self, qicon):
        self.pixmap = qicon.pixmap(self.size, self.size)
        self.update()

    def sizeHint(self):
        return QSize(self.size, self.size)

    def paintEvent(self, ev):
        if self.pixmap is not None:
            x = (self.width() - self.size) // 2
            y = (self.height() - self.size) // 2
            p = QPainter(self)
            p.drawPixmap(x, y, self.size, self.size, self.pixmap)


class MessageBox(QDialog):  # {{{

    ERROR = 0
    WARNING = 1
    INFO = 2
    QUESTION = 3

    resize_needed = pyqtSignal()

    def setup_ui(self):
        self.setObjectName("Dialog")
        self.resize(497, 235)
        self.gridLayout = l = QGridLayout(self)
        l.setObjectName("gridLayout")
        self.icon_widget = Icon(self)
        l.addWidget(self.icon_widget)
        self.msg = la = QLabel(self)
        la.setWordWrap(True), la.setMinimumWidth(400)
        la.setOpenExternalLinks(True)
        la.setObjectName("msg")
        l.addWidget(la, 0, 1, 1, 1)
        self.det_msg = dm = QPlainTextEdit(self)
        dm.setReadOnly(True)
        dm.setObjectName("det_msg")
        l.addWidget(dm, 1, 0, 1, 2)
        self.bb = bb = QDialogButtonBox(self)
        bb.setStandardButtons(QDialogButtonBox.Ok)
        bb.setObjectName("bb")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb, 3, 0, 1, 2)
        self.toggle_checkbox = tc = QCheckBox(self)
        tc.setObjectName("toggle_checkbox")
        l.addWidget(tc, 2, 0, 1, 2)

    def __init__(self, type_, title, msg,
                 det_msg='',
                 q_icon=None,
                 show_copy_button=True,
                 parent=None, default_yes=True,
                 yes_text=None, no_text=None, yes_icon=None, no_icon=None):
        QDialog.__init__(self, parent)
        if q_icon is None:
            icon = {
                    self.ERROR : 'error',
                    self.WARNING: 'warning',
                    self.INFO:    'information',
                    self.QUESTION: 'question',
            }[type_]
            icon = 'dialog_%s.png'%icon
            self.icon = QIcon(I(icon))
        else:
            self.icon = q_icon if isinstance(q_icon, QIcon) else QIcon(I(q_icon))
        self.setup_ui()

        self.setWindowTitle(title)
        self.setWindowIcon(self.icon)
        self.icon_widget.set_icon(self.icon)
        self.msg.setText(msg)
        self.det_msg.setPlainText(det_msg)
        self.det_msg.setVisible(False)
        self.toggle_checkbox.setVisible(False)

        if show_copy_button:
            self.ctc_button = self.bb.addButton(_('&Copy to clipboard'),
                    self.bb.ActionRole)
            self.ctc_button.clicked.connect(self.copy_to_clipboard)

        self.show_det_msg = _('Show &details')
        self.hide_det_msg = _('Hide &details')
        self.det_msg_toggle = self.bb.addButton(self.show_det_msg, self.bb.ActionRole)
        self.det_msg_toggle.clicked.connect(self.toggle_det_msg)
        self.det_msg_toggle.setToolTip(
                _('Show detailed information about this error'))

        self.copy_action = QAction(self)
        self.addAction(self.copy_action)
        self.copy_action.setShortcuts(QKeySequence.Copy)
        self.copy_action.triggered.connect(self.copy_to_clipboard)

        self.is_question = type_ == self.QUESTION
        if self.is_question:
            self.bb.setStandardButtons(self.bb.Yes|self.bb.No)
            self.bb.button(self.bb.Yes if default_yes else self.bb.No
                    ).setDefault(True)
            self.default_yes = default_yes
            if yes_text is not None:
                self.bb.button(self.bb.Yes).setText(yes_text)
            if no_text is not None:
                self.bb.button(self.bb.No).setText(no_text)
            if yes_icon is not None:
                self.bb.button(self.bb.Yes).setIcon(yes_icon if isinstance(yes_icon, QIcon) else QIcon(I(yes_icon)))
            if no_icon is not None:
                self.bb.button(self.bb.No).setIcon(no_icon if isinstance(no_icon, QIcon) else QIcon(I(no_icon)))
        else:
            self.bb.button(self.bb.Ok).setDefault(True)

        if not det_msg:
            self.det_msg_toggle.setVisible(False)

        self.resize_needed.connect(self.do_resize, type=Qt.QueuedConnection)
        self.do_resize()

    def sizeHint(self):
        ans = QDialog.sizeHint(self)
        ans.setWidth(max(min(ans.width(), 500), self.bb.sizeHint().width() + 100))
        ans.setHeight(min(ans.height(), 500))
        return ans

    def toggle_det_msg(self, *args):
        vis = self.det_msg.isVisible()
        self.det_msg.setVisible(not vis)
        self.det_msg_toggle.setText(self.show_det_msg if vis else self.hide_det_msg)
        self.resize_needed.emit()

    def do_resize(self):
        self.resize(self.sizeHint())

    def copy_to_clipboard(self, *args):
        QApplication.clipboard().setText(
                'calibre, version %s\n%s: %s\n\n%s' %
                (__version__, unicode_type(self.windowTitle()),
                    unicode_type(self.msg.text()),
                    unicode_type(self.det_msg.toPlainText())))
        if hasattr(self, 'ctc_button'):
            self.ctc_button.setText(_('Copied'))

    def showEvent(self, ev):
        ret = QDialog.showEvent(self, ev)
        if self.is_question:
            try:
                self.bb.button(self.bb.Yes if self.default_yes else self.bb.No
                        ).setFocus(Qt.OtherFocusReason)
            except:
                pass  # Buttons were changed
        else:
            self.bb.button(self.bb.Ok).setFocus(Qt.OtherFocusReason)
        return ret

    def set_details(self, msg):
        if not msg:
            msg = ''
        self.det_msg.setPlainText(msg)
        self.det_msg_toggle.setText(self.show_det_msg)
        self.det_msg_toggle.setVisible(bool(msg))
        self.det_msg.setVisible(False)
        self.resize_needed.emit()
# }}}


class ViewLog(QDialog):  # {{{

    def __init__(self, title, html, parent=None, unique_name=None):
        QDialog.__init__(self, parent)
        self.l = l = QVBoxLayout()
        self.setLayout(l)

        self.tb = QTextBrowser(self)
        self.tb.setHtml('<pre style="font-family: monospace">%s</pre>' % html)
        l.addWidget(self.tb)

        self.bb = QDialogButtonBox(QDialogButtonBox.Ok)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        self.copy_button = self.bb.addButton(_('Copy to clipboard'),
                self.bb.ActionRole)
        self.copy_button.setIcon(QIcon(I('edit-copy.png')))
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        l.addWidget(self.bb)

        self.unique_name = unique_name or 'view-log-dialog'
        self.finished.connect(self.dialog_closing)
        self.resize(QSize(700, 500))
        geom = gprefs.get(self.unique_name, None)
        if geom is not None:
            QApplication.instance().safe_restore_geometry(self, geom)

        self.setModal(False)
        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(I('debug.png')))
        self.show()

    def copy_to_clipboard(self):
        txt = self.tb.toPlainText()
        QApplication.clipboard().setText(txt)

    def dialog_closing(self, result):
        gprefs[self.unique_name] = bytearray(self.saveGeometry())
# }}}


_proceed_memory = []


class ProceedNotification(MessageBox):  # {{{

    '''
    WARNING: This class is deprecated. DO not use it as some users have
    reported crashes when closing the dialog box generated by this class.
    Instead use: gui.proceed_question(...) The arguments are the same as for
    this class.
    '''

    def __init__(self, callback, payload, html_log, log_viewer_title, title, msg,
            det_msg='', show_copy_button=False, parent=None,
            cancel_callback=None, log_is_file=False):
        '''
        A non modal popup that notifies the user that a background task has
        been completed.

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
        MessageBox.__init__(self, MessageBox.QUESTION, title, msg,
                det_msg=det_msg, show_copy_button=show_copy_button,
                parent=parent)
        self.payload = payload
        self.html_log = html_log
        self.log_is_file = log_is_file
        self.log_viewer_title = log_viewer_title

        self.vlb = self.bb.addButton(_('&View log'), self.bb.ActionRole)
        self.vlb.setIcon(QIcon(I('debug.png')))
        self.vlb.clicked.connect(self.show_log)
        self.det_msg_toggle.setVisible(bool(det_msg))
        self.setModal(False)
        self.callback, self.cancel_callback = callback, cancel_callback
        _proceed_memory.append(self)

    def show_log(self):
        log = self.html_log
        if self.log_is_file:
            with open(log, 'rb') as f:
                log = f.read().decode('utf-8')
        self.log_viewer = ViewLog(self.log_viewer_title, log,
                parent=self)

    def do_proceed(self, result):
        from calibre.gui2.ui import get_gui
        func = (self.callback if result == self.Accepted else
                self.cancel_callback)
        gui = get_gui()
        gui.proceed_requested.emit(func, self.payload)
        # Ensure this notification is garbage collected
        self.vlb.clicked.disconnect()
        self.callback = self.cancel_callback = self.payload = None
        self.setParent(None)
        _proceed_memory.remove(self)

    def done(self, r):
        self.do_proceed(r)
        return MessageBox.done(self, r)

# }}}


class ErrorNotification(MessageBox):  # {{{

    def __init__(self, html_log, log_viewer_title, title, msg,
            det_msg='', show_copy_button=False, parent=None):
        '''
        A non modal popup that notifies the user that a background task has
        errored.

        :param html_log: An HTML or plain text log
        :param log_viewer_title: The title for the log viewer window
        :param title: The title for this popup
        :param msg: The msg to display
        :param det_msg: Detailed message
        '''
        MessageBox.__init__(self, MessageBox.ERROR, title, msg,
                det_msg=det_msg, show_copy_button=show_copy_button,
                parent=parent)
        self.html_log = html_log
        self.log_viewer_title = log_viewer_title
        self.finished.connect(self.do_close, type=Qt.QueuedConnection)

        self.vlb = self.bb.addButton(_('&View log'), self.bb.ActionRole)
        self.vlb.setIcon(QIcon(I('debug.png')))
        self.vlb.clicked.connect(self.show_log)
        self.det_msg_toggle.setVisible(bool(det_msg))
        self.setModal(False)
        _proceed_memory.append(self)

    def show_log(self):
        self.log_viewer = ViewLog(self.log_viewer_title, self.html_log,
                parent=self)

    def do_close(self, result):
        # Ensure this notification is garbage collected
        self.setParent(None)
        self.finished.disconnect()
        self.vlb.clicked.disconnect()
        _proceed_memory.remove(self)
# }}}


class JobError(QDialog):  # {{{

    WIDTH = 600
    do_pop = pyqtSignal()

    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.queue = []
        self.do_pop.connect(self.pop, type=Qt.QueuedConnection)

        self._layout = l = QGridLayout()
        self.setLayout(l)
        self.icon = QIcon(I('dialog_error.png'))
        self.setWindowIcon(self.icon)
        self.icon_widget = Icon(self)
        self.icon_widget.set_icon(self.icon)
        self.msg_label = QLabel('<p>&nbsp;')
        self.msg_label.setStyleSheet('QLabel { margin-top: 1ex; }')
        self.msg_label.setWordWrap(True)
        self.msg_label.setTextFormat(Qt.RichText)
        self.det_msg = QPlainTextEdit(self)
        self.det_msg.setVisible(False)

        self.bb = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        self.ctc_button = self.bb.addButton(_('&Copy to clipboard'),
                self.bb.ActionRole)
        self.ctc_button.clicked.connect(self.copy_to_clipboard)
        self.retry_button = self.bb.addButton(_('&Retry'), self.bb.ActionRole)
        self.retry_button.clicked.connect(self.retry)
        self.retry_func = None
        self.show_det_msg = _('Show &details')
        self.hide_det_msg = _('Hide &details')
        self.det_msg_toggle = self.bb.addButton(self.show_det_msg, self.bb.ActionRole)
        self.det_msg_toggle.clicked.connect(self.toggle_det_msg)
        self.det_msg_toggle.setToolTip(
                _('Show detailed information about this error'))
        self.suppress = QCheckBox(self)

        l.addWidget(self.icon_widget, 0, 0, 1, 1)
        l.addWidget(self.msg_label,  0, 1, 1, 1)
        l.addWidget(self.det_msg,    1, 0, 1, 2)
        l.addWidget(self.suppress,   2, 0, 1, 2, Qt.AlignLeft|Qt.AlignBottom)
        l.addWidget(self.bb,         3, 0, 1, 2, Qt.AlignRight|Qt.AlignBottom)
        l.setColumnStretch(1, 100)

        self.setModal(False)
        self.suppress.setVisible(False)
        self.do_resize()

    def retry(self):
        if self.retry_func is not None:
            self.accept()
            self.retry_func()

    def update_suppress_state(self):
        self.suppress.setText(ngettext(
            'Hide the remaining error message',
            'Hide the {} remaining error messages', len(self.queue)).format(len(self.queue)))
        self.suppress.setVisible(len(self.queue) > 3)
        self.do_resize()

    def copy_to_clipboard(self, *args):
        d = QTextDocument()
        d.setHtml(self.msg_label.text())
        QApplication.clipboard().setText(
                'calibre, version %s (%s, embedded-python: %s)\n%s: %s\n\n%s' %
                (__version__, sys.platform, isfrozen,
                    unicode_type(self.windowTitle()), unicode_type(d.toPlainText()),
                    unicode_type(self.det_msg.toPlainText())))
        if hasattr(self, 'ctc_button'):
            self.ctc_button.setText(_('Copied'))

    def toggle_det_msg(self, *args):
        vis = unicode_type(self.det_msg_toggle.text()) == self.hide_det_msg
        self.det_msg_toggle.setText(self.show_det_msg if vis else
                self.hide_det_msg)
        self.det_msg.setVisible(not vis)
        self.do_resize()

    def do_resize(self):
        h = self.sizeHint().height()
        self.setMinimumHeight(0)  # Needed as this gets set if det_msg is shown
        # Needed otherwise re-showing the box after showing det_msg causes the box
        # to not reduce in height
        self.setMaximumHeight(h)
        self.resize(QSize(self.WIDTH, h))

    def showEvent(self, ev):
        ret = QDialog.showEvent(self, ev)
        self.bb.button(self.bb.Close).setFocus(Qt.OtherFocusReason)
        return ret

    def show_error(self, title, msg, det_msg='', retry_func=None):
        self.queue.append((title, msg, det_msg, retry_func))
        self.update_suppress_state()
        self.pop()

    def pop(self):
        if not self.queue or self.isVisible():
            return
        title, msg, det_msg, retry_func = self.queue.pop(0)
        self.setWindowTitle(title)
        self.msg_label.setText(msg)
        self.det_msg.setPlainText(det_msg)
        self.det_msg.setVisible(False)
        self.det_msg_toggle.setText(self.show_det_msg)
        self.det_msg_toggle.setVisible(True)
        self.suppress.setChecked(False)
        self.update_suppress_state()
        if not det_msg:
            self.det_msg_toggle.setVisible(False)
        self.retry_button.setVisible(retry_func is not None)
        self.retry_func = retry_func
        self.do_resize()
        self.show()

    def done(self, r):
        if self.suppress.isChecked():
            self.queue = []
        QDialog.done(self, r)
        self.do_pop.emit()

# }}}


if __name__ == '__main__':
    from calibre.gui2 import question_dialog, Application
    app = Application([])
    print(question_dialog(None, 'title', 'msg <a href="http://google.com">goog</a> ',
            det_msg='det '*1000,
            show_copy_button=True))
