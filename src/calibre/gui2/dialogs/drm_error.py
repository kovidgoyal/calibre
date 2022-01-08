#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from qt.core import QDialog

from calibre.gui2.dialogs.drm_error_ui import Ui_Dialog
from calibre.utils.localization import localize_website_link


class DRMErrorMessage(QDialog, Ui_Dialog):

    def __init__(self, parent=None, title=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        msg = _('<p>This book is locked by <b>DRM</b>. To learn more about DRM'
                ' and why you cannot read or convert this book in calibre,'
                ' <a href="{0}">click here</a>.'
                ' </p>').format(localize_website_link('https://manual.calibre-ebook.com/drm.html'))
        if title is not None:
            msg = '<h2>%s</h2>%s'%(title, msg)
        self.msg.setText(msg)
        self.resize(self.sizeHint())


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = DRMErrorMessage(title='testing title')
    d.exec()
    del d
