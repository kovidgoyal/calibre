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
import re, glob
from pkg_resources import resource_filename

from trac.core import Component, implements
from trac.web.chrome import INavigationContributor, ITemplateProvider, add_stylesheet
from trac.web.main import IRequestHandler
from trac.util import Markup


__appname__ = 'libprs500'
DOWNLOAD_DIR = '/var/www/vhosts/kovidgoyal.net/subdomains/libprs500/httpdocs/downloads'



class OS(dict):
    """Dictionary with a default value for unknown keys."""
    def __init__(self, dict):
        self.update(dict)
        if not dict.has_key('img'):
            self['img'] = self['name']

class Distribution(object):
    
    DEPENDENCIES = [
        #(Generic, version, gentoo, ubuntu, fedora)
        ('python', '2.5', None, None, None),
        ('setuptools', '0.6c5', 'setuptools', 'python-setuptools', 'python-setuptools-devel'),
        ('Python Imaging Library', '1.1.6', 'imaging', 'python-imaging', 'python-imaging'),
        ('libusb', '0.1.12', None, None, None),
        ('Qt', '4.3.1', 'qt', 'libqt4-core libqt4-gui', 'qt4'),
        ('PyQt', '4.3.1', 'PyQt4', 'python-qt4', 'PyQt4'),
        ('fonttools', '2.0-beta1', 'fonttools', 'fonttools', 'fonttools'),
        ('unrtf', '0.20.1', 'unrtf', 'unrtf', 'unrtf'),
        ('mechanize for python', '0.1.7b', 'dev-python/mechanize', 'python-mechanize', 'python-mechanize'),
        ('ImageMagick', '6.3.5', 'imagemagick', 'imagemagick', 'ImageMagick'),
        ('xdg-utils', '1.0.2', 'xdg-utils', 'xdg-utils', 'xdg-utils'),
        ('dbus-python', '0.82.2', 'dbus-python', 'python-dbus', 'dbus-python'),
        ('convertlit', '1.8', 'convertlit', None, None),
        ('lxml', '1.3.3', 'lxml', 'python-lxml', 'python-lxml'),
        ('librsvg', '2.0.0', 'librsvg', 'librsvg2-bin', 'librsvg2')
        ]
    
    DISTRO_MAP = {'gentoo':2, 'ubuntu':3, 'fedora':4, 'debian':3}
    
    INSTALLERS = ('emerge -av', 'apt-get install', 'yum install')
    AS_ROOT    = (True, False, True)
    
    TITLEMAP = {'gentoo':'Gentoo', 'ubuntu':'Ubuntu Gutsy Gibbon',
                'fedora':'Fedora 8', 'debian':'Debian Sid', 'generic': 'Generic Unix'}
    
    MANUAL_MAP = {
                  'ubuntu' : '<li>You will have to install <a href="">convertlit</a> manually to be able to convert LIT files.</li>',
                  'fedora' : '''<li>You have to upgrade Qt to at least 4.3.1 and PyQt to at least 4.3.1</li>'''\
                             '''<li>You will have to install <a href="">convertlit</a> manually to be able to convert LIT files.</li>''',
                  'debian' : '<li>Add the following to /etc/apt/sources.list<pre class="wiki">deb http://www.debian-multimedia.org sid main</pre>Then<pre class="wiki">apt-get install clit</pre></li>', 
                  }
    
    def __init__(self, os):
        self.os = os
        self.img = os
        self.title = self.TITLEMAP[os]
        self.app = __appname__
        self.is_generic = os == 'generic'
        offset = 0
        if not self.is_generic:
            index = self.DISTRO_MAP[self.os]
            if os == 'debian':
                self.as_root = True  
            else: self.as_root = self.AS_ROOT[index-2]
            prefix = '' 
            if not self.as_root: prefix =  'sudo '
            cmd = prefix + self.INSTALLERS[index-2]
            pre = ' \\\n '.ljust(len(cmd)+4)
            for dep in self.DEPENDENCIES:
                if len(cmd) > 70+offset:
                    offset += 70
                    cmd += pre 
                cmd += ' ' 
                if dep[index]: cmd += dep[index]
            self.command = cmd.strip()
            easy_install = 'easy_install'
            if os == 'debian':
                self.command += '\n'+prefix + 'cp -R /usr/share/pycentral/fonttools/site-packages/FontTools* /usr/lib/python2.5/site-packages/'
                easy_install = 'easy_install-2.5'
            self.command += '\n'+prefix+easy_install+' -U TTFQuery libprs500 \n'+prefix+'libprs500_postinstall'
            try:
                self.manual = Markup(self.MANUAL_MAP[os])
            except KeyError:
                self.manual = None
        else:
            self.img = 'linux'
            
    
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
            OS({'name' : 'windows', 'title' : 'Windows'}),
            OS({'name' : 'osx', 'title' : 'OS X'}),
            OS({'name' : 'linux', 'title' : 'Linux'}),
        ]
        data = dict(title='Get ' + __appname__, 
                    operating_systems=operating_systems, width=200,
                    font_size='xx-large')
        return 'download.html', data, None
    
    def version_from_filename(self):
        try:
            file = glob.glob(DOWNLOAD_DIR+'/*.exe')[0]
            return re.search(r'\S+-(\d+\.\d+\.\d+)\.', file).group(1)
        except:
            return '0.0.0'
    
    def windows(self, req):
        version = self.version_from_filename()
        file = 'libprs500-%s.exe'%(version,)         
        data = dict(version = version, name='windows',
            installer_name='Windows installer', 
            title='Download %s for windows'%(__appname__),
            compatibility='%s works on Windows XP and Windows Vista.'%(__appname__,),
            path='/downloads/'+file, app=__appname__,
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
        version = self.version_from_filename()
        file = 'libprs500-%s.dmg'%(version,) 
        data = dict(version = version, name='osx',
            installer_name='OS X universal dmg', 
            title='Download %s for OS X'%(__appname__),
            compatibility='%s works on OS X Tiger and above.'%(__appname__,),
            path='/downloads/'+file, app=__appname__,
            note=Markup(\
'''
<ol>
<li>Before trying to use the command line tools, you must run the app at least once. This will ask you for you password and then setup the symbolic links for the command line tools.</li>
<li>The app cannot be run from within the dmg. You must drag it to a folder on your filesystem (The Desktop, Applications, wherever).</li> 
<li>In order for the conversion of RTF to LRF to support WMF images (common in older RTF files) you need to install ImageMagick.</li>
<li>In order for localization of the user interface in your language you must create the file <code>~/.MacOSX/environment.plist</code> as shown below:
<pre class="wiki">
&lt;?xml version="1.0" encoding="UTF-8"?&gt;
&lt;!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"&gt;
&lt;plist version="1.0"&gt;
&lt;dict&gt;
        &lt;key&gt;LANG&lt;/key&gt;
        &lt;string&gt;de_DE&lt;/string&gt;
&lt;/dict&gt;
&lt;/plist&gt;
</pre>
The example above is for the German language. Substitute the language code you need. 
After creating the file you need to log out and log in again for the changes to become
active. Of course, this will only work if libprs500 has been translated for your language.
If not, head over to <a href="https://libprs500.kovidgoyal.net/wiki/Development#Translations">Translations</a> to see how you can translate it.
</li>
</ol>
'''))
        return 'binary.html', data, None
    
    def linux(self, req):
        operating_systems = [
            OS({'name' : 'gentoo', 'title': 'Gentoo'}),
            OS({'name' : 'ubuntu', 'title': 'Ubuntu'}),
            OS({'name' : 'fedora', 'title': 'Fedora'}),
            OS({'name' : 'debian', 'title': 'Debian'}),
            OS({'name' : 'generic','title': 'Generic', 'img':'linux'}),
                             ]
        data = dict(title='Choose linux distribution', width=100,
                    operating_systems=operating_systems, font_size='x-large')
        return 'download.html', data, None
                            