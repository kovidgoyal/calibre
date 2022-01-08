#!/usr/bin/env python
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>

import os
import importlib


def form_to_compiled_form(form):
    return form.rpartition('.')[0]+'_ui.py'


def find_forms(srcdir):
    base = os.path.join(srcdir, 'calibre', 'gui2')
    forms = []
    for root, _, files in os.walk(base):
        for name in files:
            if name.endswith('.ui'):
                forms.append(os.path.abspath(os.path.join(root, name)))

    return forms


def build_forms(srcdir, info=None, summary=False, check_for_migration=False):
    import re
    from qt.core import QT_VERSION_STR
    qt_major = QT_VERSION_STR.split('.')[0]
    m = importlib.import_module(f'PyQt{qt_major}.uic')

    from polyglot.io import PolyglotStringIO
    forms = find_forms(srcdir)
    if info is None:
        info = print

    num = 0
    transdef_pat = re.compile(r'^\s+_translate\s+=\s+QtCore.QCoreApplication.translate$', flags=re.M)
    transpat = re.compile(r'_translate\s*\(.+?,\s+"(.+?)(?<!\\)"\)', re.DOTALL)

    # Ensure that people running from source have all their forms rebuilt for
    # the qt5 migration
    force_compile = os.environ.get('CALIBRE_FORCE_BUILD_UI_FORMS', '') in ('1', 'yes', 'true')
    if check_for_migration:
        from calibre.gui2 import gprefs
        force_compile |= not gprefs.get(f'migrated_forms_to_qt{qt_major}', False)

    icon_constructor_pat = re.compile(r'\s*\S+\s+=\s+QtGui.QIcon\(\)')
    icon_pixmap_adder_pat = re.compile(r'''(\S+?)\.addPixmap\(.+?(['"]):/images/([^'"]+)\2.+''')

    def icon_pixmap_sub(match):
        ans = match.group(1) + ' = QtGui.QIcon.ic(' + match.group(2) + match.group(3) + match.group(2) + ')'
        return ans

    for form in forms:
        compiled_form = form_to_compiled_form(form)
        if force_compile or not os.path.exists(compiled_form) or os.stat(form).st_mtime > os.stat(compiled_form).st_mtime:
            if not summary:
                info('\tCompiling form', form)
            buf = PolyglotStringIO()
            m.compileUi(form, buf)
            dat = buf.getvalue()
            dat = dat.replace('import images_rc', '')
            dat = transdef_pat.sub('', dat)
            dat = transpat.sub(r'_("\1")', dat)
            dat = dat.replace('_("MMM yyyy")', '"MMM yyyy"')
            dat = dat.replace('_("d MMM yyyy")', '"d MMM yyyy"')
            dat = icon_constructor_pat.sub('', dat)
            dat = icon_pixmap_adder_pat.sub(icon_pixmap_sub, dat)
            if not isinstance(dat, bytes):
                dat = dat.encode('utf-8')
            open(compiled_form, 'wb').write(dat)
            num += 1
    if num:
        info('Compiled %d forms' % num)
    if check_for_migration and force_compile:
        gprefs.set(f'migrated_forms_to_qt{qt_major}', True)
