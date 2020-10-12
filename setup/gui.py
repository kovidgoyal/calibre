#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from setup import Command, __appname__


class GUI(Command):
    description = 'Compile all GUI forms'
    PATH  = os.path.join(Command.SRC, __appname__, 'gui2')
    QRC = os.path.join(Command.RESOURCES, 'images.qrc')

    def add_options(self, parser):
        parser.add_option('--summary', default=False, action='store_true',
                help='Only display a summary about how many files were compiled')

    def find_forms(self):
        # We do not use the calibre function find_forms as
        # importing calibre.gui2 may not work
        forms = []
        for root, _, files in os.walk(self.PATH):
            for name in files:
                path = os.path.abspath(os.path.join(root, name))
                if name.endswith('.ui'):
                    forms.append(path)
                elif name.endswith('_ui.py') or name.endswith('_ui.pyc'):
                    fname = path.rpartition('_')[0] + '.ui'
                    if not os.path.exists(fname):
                        os.remove(path)
        return forms

    @classmethod
    def form_to_compiled_form(cls, form):
        # We do not use the calibre function form_to_compiled_form as
        # importing calibre.gui2 may not work
        return form.rpartition('.')[0]+'_ui.py'

    def run(self, opts):
        self.build_forms(summary=opts.summary)
        self.build_images()

    def build_images(self):
        cwd = os.getcwd()
        try:
            os.chdir(self.RESOURCES)
            sources, files = [], []
            for root, _, files2 in os.walk('images'):
                for name in files2:
                    sources.append(os.path.join(root, name))
            if self.newer(self.QRC, sources):
                self.info('Creating images.qrc')
                for s in sources:
                    files.append('<file>%s</file>'%s)
                manifest = '<RCC>\n<qresource prefix="/">\n%s\n</qresource>\n</RCC>'%'\n'.join(sorted(files))
                if not isinstance(manifest, bytes):
                    manifest = manifest.encode('utf-8')
                with open('images.qrc', 'wb') as f:
                    f.write(manifest)
        finally:
            os.chdir(cwd)

    def build_forms(self, summary=False):
        from calibre.gui2 import build_forms
        build_forms(self.SRC, info=self.info, summary=summary)

    def clean(self):
        forms = self.find_forms()
        for form in forms:
            c = self.form_to_compiled_form(form)
            if os.path.exists(c):
                os.remove(c)
        if os.path.exists(self.QRC):
            os.remove(self.QRC)
