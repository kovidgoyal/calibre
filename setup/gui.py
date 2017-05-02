#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

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

    @classmethod
    def find_forms(cls):
        # We do not use the calibre function find_forms as
        # mporting calibre.gui2 may not work
        forms = []
        for root, _, files in os.walk(cls.PATH):
            for name in files:
                if name.endswith('.ui'):
                    forms.append(os.path.abspath(os.path.join(root, name)))

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
