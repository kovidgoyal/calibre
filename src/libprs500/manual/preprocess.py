#!/usr/bin/env  python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
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
''''''

import sys, glob, mechanize, time, subprocess
from tempfile import NamedTemporaryFile
from xml.etree.ElementTree import parse, tostring, fromstring
from BeautifulSoup import BeautifulSoup

def browser():
    opener = mechanize.Browser()
    opener.set_handle_refresh(True)
    opener.set_handle_robots(False)
    opener.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; i686 Linux; en_US; rv:1.8.0.4) Gecko/20060508 Firefox/1.5.0.4')]
    return opener

def update_manifest(src='libprs500.qhp'):
    root = parse(src).getroot()
    files = root.find('filterSection').find('files')
    files.clear()
    for f in glob.glob('*.html')+glob.glob('*.css')+glob.glob('images/*'):
        if f.startswith('preview'):
            continue
        files.append(fromstring('<file>%s</file>'%f))
    
    raw = tostring(root, 'UTF-8').replace('<file>', '\n            <file>')
    raw = raw.replace('</files>', '\n        </files>')
    raw = raw.replace('</filterSection>', '\n\n    </filterSection>')
    open(src, 'wb').write(raw+'\n')


def validate_html():
    br = browser()
    for f in glob.glob('*.html'):
        raw = open(f).read()
        br.open('http://validator.w3.org/#validate_by_input')
        br.form = tuple(br.forms())[2]
        br.form.set_value(raw, id='fragment')
        res = br.submit()
        soup = BeautifulSoup(res.read())
        if soup.find('div', id='result').find(id='congrats') is None:
            print 'Invalid HTML in', f
            t = NamedTemporaryFile()
            t.write(unicode(soup).encode('utf-8'))
            subprocess.call(('xdg-open', t.name))
            time.sleep(2)
            return
                        
    
    

def main(args=sys.argv):
    update_manifest()
    validate_html()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())