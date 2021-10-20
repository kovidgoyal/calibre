__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from qt.core import QDialog

from calibre.gui2.dialogs.conversion_error_ui import Ui_ConversionErrorDialog


class ConversionErrorDialog(QDialog, Ui_ConversionErrorDialog):

    def __init__(self, window, title, html, show=False):
        QDialog.__init__(self, window)
        Ui_ConversionErrorDialog.__init__(self)
        self.setupUi(self)
        self.setWindowTitle(title)
        self.set_message(html)
        if show:
            self.show()

    def set_message(self, html):
        self.text.setHtml('<html><body>%s</body></html'%(html,))
