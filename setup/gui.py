#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, cStringIO, re

from setup import Command, __appname__

class GUI(Command):
    description = 'Compile all GUI forms'
    PATH  = os.path.join(Command.SRC, __appname__, 'gui2')
    QRC = os.path.join(Command.RESOURCES, 'images.qrc')

    @classmethod
    def find_forms(cls):
        forms = []
        for root, _, files in os.walk(cls.PATH):
            for name in files:
                if name.endswith('.ui'):
                    forms.append(os.path.abspath(os.path.join(root, name)))

        return forms

    @classmethod
    def form_to_compiled_form(cls, form):
        return form.rpartition('.')[0]+'_ui.py'

    def run(self, opts):
        self.build_forms()
        self.build_images()

    def build_images(self):
        cwd = os.getcwd()
        try:
            os.chdir(self.RESOURCES)
            sources, files = [], []
            for root, _, files in os.walk('images'):
                for name in files:
                    sources.append(os.path.join(root, name))
            if self.newer(self.QRC, sources):
                self.info('Creating images.qrc')
                for s in sources:
                    files.append('<file>%s</file>'%s)
                manifest = '<RCC>\n<qresource prefix="/">\n%s\n</qresource>\n</RCC>'%'\n'.join(files)
                with open('images.qrc', 'wb') as f:
                    f.write(manifest)
        finally:
            os.chdir(cwd)


    def build_forms(self):
        from PyQt4.uic import compileUi
        forms = self.find_forms()
        for form in forms:
            compiled_form = self.form_to_compiled_form(form)
            if not os.path.exists(compiled_form) or os.stat(form).st_mtime > os.stat(compiled_form).st_mtime:
                print 'Compiling form', form
                buf = cStringIO.StringIO()
                compileUi(form, buf)
                dat = buf.getvalue()
                dat = dat.replace('__appname__', __appname__)
                dat = dat.replace('import images_rc', 'from calibre.gui2 import images_rc')
                dat = dat.replace('from library import', 'from calibre.gui2.library import')
                dat = dat.replace('from widgets import', 'from calibre.gui2.widgets import')
                dat = dat.replace('from convert.xpath_wizard import',
                    'from calibre.gui2.convert.xpath_wizard import')
                dat = re.compile(r'QtGui.QApplication.translate\(.+?,\s+"(.+?)(?<!\\)",.+?\)', re.DOTALL).sub(r'_("\1")', dat)
                dat = dat.replace('_("MMM yyyy")', '"MMM yyyy"')

                # Workaround bug in Qt 4.4 on Windows
                if form.endswith('dialogs%sconfig.ui'%os.sep) or form.endswith('dialogs%slrf_single.ui'%os.sep):
                    print 'Implementing Workaround for buggy pyuic in form', form
                    dat = re.sub(r'= QtGui\.QTextEdit\(self\..*?\)', '= QtGui.QTextEdit()', dat)
                    dat = re.sub(r'= QtGui\.QListWidget\(self\..*?\)', '= QtGui.QListWidget()', dat)

                if form.endswith('viewer%smain.ui'%os.sep):
                    print 'Promoting WebView'
                    dat = dat.replace('self.view = QtWebKit.QWebView(', 'self.view = DocumentView(')
                    dat += '\n\nfrom calibre.gui2.viewer.documentview import DocumentView'

                open(compiled_form, 'wb').write(dat)


    def clean(self):
        forms = self.find_forms()
        for form in forms:
            c = self.form_to_compiled_form(form)
            if os.path.exists(c):
                os.remove(c)
        if os.path.exists(self.QRC):
            os.remove(self.QRC)


