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
import re
from pkg_resources import resource_filename

from trac.core import Component, implements
from trac.web.chrome import INavigationContributor, ITemplateProvider, add_stylesheet
from trac.web.main import IRequestHandler
from trac.util import Markup


__appname__ = 'libprs500'

class Distribution(object):
    
    DEPENDENCIES = [
        #(Generic, version, gentoo, ubuntu, fedora)
        ('python', '2.5', None, None, None),
        ('setuptools', '0.6c5', 'setuptools', 'python-setuptools', 'python-setuptools'),
        ('Python Imaging Library', '1.1.6', 'imaging', 'python-imaging', 'python-imaging'),
        ('libusb', '0.1.12', None, None, None),
        ('Qt', '4.3.1', 'qt', 'libqt4-core libqt4-gui', 'qt4'),
        ('PyQt', '4.3.1', 'PyQt4', 'python-qt4', 'PyQt4'),
        ('fonttools', '2.0-beta1', 'fonttools', 'fonttools', 'fonttools'),
        ('unrtf', '0.20.1', 'unrtf', 'unrtf', 'unrtf'),
        ('mechanize for python', '0.1.7b', 'dev-python/mechanize', 'python-mechanize', 'python-mechanize'),
        ('ImageMagick', '6.3.5', 'imagemagick', 'imagemagick', 'imagemagick'),
        ('xdg-utils', '1.0.2', 'xdg-utils', 'xdg-utils', 'xdg-utils'),
        ('dbus-python', '0.82.2', 'dbus-python', 'python-dbus', 'dbus-python'),
        ('convertlit', '1.8', 'convertlit', None, None)
        ]
    
    DISTRO_MAP = {'gentoo':2, 'ubuntu':3, 'fedora':4, 'debian':3}
    
    INSTALLERS = ('emerge -av', 'apt-get install', 'yum install')
    AS_ROOT    = (True, False, True)
    
    TITLEMAP = {'gentoo':'Gentoo', 'ubuntu':'Ubuntu Gutsy Gibbon',
                'fedora':'Fedora 7', 'debian':'Debian Sid', 'generic': 'Generic Unix'}
    
    MANUAL_MAP = {
                  'ubuntu' : '<li>You will have to install <a href="">convertlit</a> manually to be able to convert LIT files.</li>',
                  'fedora' : '''<li>You have to upgrade Qt to at least 4.3.1 and PyQt to at least 4.3.1</li>'''\
                             '''<li>You will have to install <a href="">convertlit</a> manually to be able to convert LIT files.</li>''',
                  'debian' : '<li>Add the following to /etc/apt/sources.list<pre class="wiki">deb http://www.debian-multimedia.org sid main</pre>Then<pre class="wiki">apt-get install clit</pre></li>', 
                  }
    
    def __init__(self, os):
        self.os = os
        self.title = self.TITLEMAP[os]
        self.is_generic = os == 'generic'
        offset = 0
        if not self.is_generic:
            index = self.DISTRO_MAP[self.os]
            if os == 'debian':
                self.as_root = True  
            else: self.AS_ROOT[index-2]
            prefix = '' 
            if not self.as_root: prefix =  'sudo '
            cmd = prefix + self.INSTALLERS[index-2]
            pre = ' \\\n '.ljust(len(cmd)+3)
            for dep in self.DEPENDENCIES:
                if len(cmd) > 70+offset:
                    offset += 70
                    cmd += pre 
                cmd += ' ' 
                if dep[index]: cmd += dep[index]
            self.command = cmd.strip()
            if os == 'debian':
                self.command += '\n'+prefix + 'cp -R /usr/share/pycentral/fonttools/site-packages/FontTools* /usr/lib/python2.5/site-packages/'
            self.command += '\n'+prefix+'easy_install -U TTFQuery libprs500 \nlibprs500_postinstall'
            try:
                self.manual = Markup(self.MANUAL_MAP[os])
            except KeyError:
                self.manual = None
            
    
class Download(Component):
    implements(INavigationContributor, IRequestHandler, ITemplateProvider)
    
    request_pat = re.compile(r'\/download$|\/download_\S+')
    
    # INavigationContributor methods
    def get_active_navigation_item(self, req):
        return 'download'

    def get_navigation_items(self, req):
        yield 'mainnav', 'download', Markup('<a href="/download">Get %s</a>'%(__appname__,))
    
    def get_templates_dirs(self):
        return [resource_filename(__name__, 'templates')]
    
    def get_htdocs_dirs(self):
        return [('dl', resource_filename(__name__, 'htdocs'))]

    # IRequestHandler methods
    def match_request(self, req):
        return self.__class__.request_pat.match(req.path_info)

    def process_request(self, req):
        add_stylesheet(req, 'dl/css/download.css')
        if req.path_info == '/download':
            return self.top_level(req)
        else:
            match = re.match(r'\/download_(\S+)', req.path_info)
            if match:
                os = match.group(1)
                if os == 'windows':
                    return self.windows(req)
                elif os == 'osx':
                    return self.osx(req)
                elif os == 'linux':
                    return self.linux(req) 
                else:
                    return self.linux_distro(req, os)       
    
    def linux_distro(self, req, os):
        distro = Distribution(os)
        data = dict(distro=distro,title=distro.title)
        return 'distro.html', data, None
    
    def top_level(self, req):
        operating_systems = [
            {'name' : 'windows', 'title' : 'Windows'},
            {'name' : 'osx', 'title' : 'OS X'},
            {'name' : 'linux', 'title' : 'Linux'},
        ]
        data = dict(title='Get ' + __appname__, 
                    operating_systems=operating_systems, width=200,
                    font_size='xx-large')
        return 'download.html', data, None
    
    def version_from_filename(self, file):
        return re.search(r'\S+-(\d+\.\d+\.\d+)\.', file).group(1)
    
    def windows(self, req):
        file = 'libprs500-0.4.14.exe'
        version = self.version_from_filename(file) 
        data = dict(version = version, name='windows',
            installer_name='Windows installer', 
            title='Download %s for windows'%(__appname__),
            compatibility='%s works on Windows XP and Windows Vista.'%(__appname__,),
            path='downloads/'+file,
            note=Markup(\
'''
<p>If you are using the <b>SONY PRS-500</b> and %(appname)s does not detect your reader, read on:</p>
<blockquote>
<p>
If you are using 64-bit windows, you're out of luck. 
</p>
<p>
There may be a conflict with the USB driver from SONY. In windows, you cannot install two drivers
for one device. In order to resolve the conflict:
<ol>
<li>Start Device Manager by clicking Start->Run, typing devmgmt.msc and pressing enter.</li>
<li>Uninstall all PRS500 related drivers. You will find them in two locations:
<ul>
<li>Under "Libusb-Win32"</li>
<li>Under "Universal Serial ..." (... depends on the version of windows)</li>
</ul>
You can uninstall a driver by right clicking on it and selecting uninstall.
</li>
<li>Once the drivers have been uninstalled, uninstall %(appname)s. Reboot. Reinstall %(appname)s.</li>
</ol>
</p>
</blockquote>
'''%dict(appname=__appname__)))
        return 'binary.html', data, None
    
    def osx(self, req):
        file = 'libprs500-0.4.14.dmg'
        version = self.version_from_filename(file) 
        data = dict(version = version, name='osx',
            installer_name='OS X universal dmg', 
            title='Download %s for OS X'%(__appname__),
            compatibility='%s works on OS X Tiger and above.'%(__appname__,),
            path='downloads/'+file,
            note=Markup(\
'''
<ol>
<li>Before trying to use the command line tools, you must run the app at least once. This will ask you for you password and then setup the symbolic links for the command line tools.</li>
<li>The app cannot be run from within the dmg. You must drag it to a folder on your filesystem (The Desktop, Applications, wherever).</li> 
<li>In order for the conversion of RTF to LRF to support WMF images (common in older RTF files) you need to install ImageMagick.</li>
</ol>
'''))
        return 'binary.html', data, None
    
    def linux(self, req):
        operating_systems = [
            {'name' : 'gentoo', 'title': 'Gentoo'},
            {'name' : 'ubuntu', 'title': 'Ubuntu'},
            {'name' : 'fedora', 'title': 'Fedora'},
            {'name' : 'debian', 'title': 'Debian'},
            {'name' : 'generic','title': 'Generic', 'img':'linux'},
                             ]
        data = dict(title='Choose linux distribution', width=100,
                    operating_systems=operating_systems, font_size='x-large')
        return 'download.html', data, None
                            