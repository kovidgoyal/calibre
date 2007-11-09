##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
'''
Manage translation of user visible strings.
'''

import sys, os, cStringIO, tempfile, subprocess, functools
check_call = functools.partial(subprocess.check_call, shell=True)

from libprs500.translations.pygettext import main as pygettext
from libprs500.translations.msgfmt import main as msgfmt

TRANSLATIONS = [
                'sl',
                'de'
                ]

def source_files():
    ans = []
    for root, dirs, files in os.walk(os.getcwdu()):
        for name in files:
            if name.endswith('.py'):
                ans.append(os.path.abspath(os.path.join(root, name)))
    return ans
                

def main(args=sys.argv):
    tdir = os.path.dirname(__file__)
    files = source_files()
    buf = cStringIO.StringIO()
    pygettext(buf, ['-p', tdir]+files)
    src = buf.getvalue()
    template = tempfile.NamedTemporaryFile(suffix='.pot')
    template.write(src)
    translations = {}
    for tr in TRANSLATIONS:
        po = os.path.join(tdir, tr+'.po')
        if not os.path.exists(po):
            open(po, 'wb').write(src.replace('LANGUAGE', tr))
        buf = cStringIO.StringIO()
        msgfmt(buf, [po])
        translations[tr] = buf.getvalue()
    open(os.path.join(tdir, 'data.py'), 'wb').write('translations = '+repr(translations))
    return 0

if __name__ == '__main__':
    sys.exit(main())