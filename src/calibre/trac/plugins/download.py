__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import re
from pkg_resources import resource_filename

from trac.core import Component, implements
from trac.web.chrome import INavigationContributor, ITemplateProvider, add_stylesheet
from trac.web.main import IRequestHandler
from trac.util import Markup


__appname__ = 'calibre'
DOWNLOAD_DIR = '/var/www/calibre.kovidgoyal.net/htdocs/downloads'
MOBILEREAD = 'https://dev.mobileread.com/dist/kovid/calibre/'

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
        ('Qt', '4.4.0', 'qt', 'libqt4-core libqt4-gui', 'qt4'),
        ('PyQt', '4.4.2', 'PyQt4', 'python-qt4', 'PyQt4'),
        ('mechanize for python', '0.1.8', 'dev-python/mechanize', 'python-mechanize', 'python-mechanize'),
        ('ImageMagick', '6.3.5', 'imagemagick', 'imagemagick', 'ImageMagick'),
        ('xdg-utils', '1.0.2', 'xdg-utils', 'xdg-utils', 'xdg-utils'),
        ('dbus-python', '0.82.2', 'dbus-python', 'python-dbus', 'dbus-python'),
        ('lxml', '2.0.5', 'lxml', 'python-lxml', 'python-lxml'),
        ('BeautifulSoup', '3.0.5', 'beautifulsoup', 'python-beautifulsoup', 'python-BeautifulSoup'),
        ('help2man', '1.36.4', 'help2man', 'help2man', 'help2man'),
        ]
    
    DISTRO_MAP = {'gentoo':2, 'ubuntu':3, 'fedora':4, 'debian':3}
    
    INSTALLERS = ('emerge -avn', 'apt-get install', 'yum install')
    AS_ROOT    = (True, False, True)
    
    TITLEMAP = {'gentoo':'Gentoo', 'ubuntu':'Ubuntu Intrepid Ibex',
                'fedora':'Fedora 10', 'debian':'Debian sid', 'generic': 'Install from source'}
    
    MANUAL_MAP = {
                  'fedora' : '''<li>You have to upgrade Qt to at least 4.4.0 and PyQt to at least 4.4.2</li>''',
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
                easy_install = 'easy_install-2.5'
            self.command += '\n'+prefix+easy_install+' -U calibre \n'+prefix+'calibre_postinstall'
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
        elif req.path_info == '/download_linux_binary_installer':
            req.send(LINUX_INSTALLER.replace('%version', self.version_from_filename()), 'text/x-python')
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
                elif 'binary' in os:
                    return self.linux_binary(req)
                else:
                    return self.linux_distro(req, os)       
    
    def linux_distro(self, req, os):
        version = self.version_from_filename()
        distro = Distribution(os)
        data = dict(distro=distro,title=distro.title, version=version)
        return 'distro.html', data, None
    
    def top_level(self, req):
        operating_systems = [
            OS({'name' : 'windows', 'title' : 'Windows'}),
            OS({'name' : 'osx', 'title' : 'OS X'}),
            OS({'name' : 'linux', 'title' : 'Linux'}),
        ]
        data = dict(title='Get ' + __appname__, 
                    operating_systems=operating_systems, width=200,
                    font_size='xx-large', top_level=True)
        return 'download.html', data, None
    
    def version_from_filename(self):
        try:
            return open(DOWNLOAD_DIR+'/latest_version', 'rb').read().strip()
        except:
            return '0.0.0'
    
    def windows(self, req):
        version = self.version_from_filename()
        file = '%s-%s.exe'%(__appname__, version,)         
        data = dict(version = version, name='windows',
            installer_name='Windows installer', 
            title='Download %s for windows'%(__appname__),
            compatibility='%s works on Windows XP and Windows Vista.'%(__appname__,),
            path=MOBILEREAD+file, app=__appname__,
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
<li>Once the drivers have been uninstalled, find the file prs500.inf (it will be in the 
driver folder in the folder in which you installed %(appname)s. Right click on it and
select Install.</li>
</ol>
</p>
</blockquote>
'''%dict(appname=__appname__)))
        return 'binary.html', data, None
    
    def linux_binary(self, req):
        version = self.version_from_filename()
        return 'pyinstaller.html', {'app':__appname__, 'version':version}, None
    
    def osx(self, req):
        version = self.version_from_filename()
        file = 'calibre-%s.dmg'%(version,) 
        data = dict(version = version, name='osx',
            installer_name='OS X universal dmg', 
            title='Download %s for OS X'%(__appname__),
            compatibility='%s works on OS X Tiger and above.'%(__appname__,),
            path=MOBILEREAD+file, app=__appname__,
            note=Markup(\
'''
<ol>
<li>Before trying to use the command line tools, you must run the app at least once. This will ask you for you password and then setup the symbolic links for the command line tools.</li>
<li>The app cannot be run from within the dmg. You must drag it to a folder on your filesystem (The Desktop, Applications, wherever).</li> 
<li>In order for localization of the user interface in your language, select your language in the configuration dialog (by clicking the hammer icon next to the search bar) and select your language.</li>
</ol>
'''))
        return 'binary.html', data, None
    
    def linux(self, req):
        operating_systems = [
            OS({'name' : 'binary', 'title': 'Binary Installer'}),
            OS({'name' : 'gentoo', 'title': 'Gentoo'}),
            OS({'name' : 'ubuntu', 'title': 'Ubuntu'}),
            OS({'name' : 'fedora', 'title': 'Fedora'}),
            OS({'name' : 'debian', 'title': 'Debian'}),
            OS({'name' : 'generic','title': 'Install from source', 'img':'linux'}),
                             ]
        data = dict(title='Choose linux distribution', width=100,
                    operating_systems=operating_systems, font_size='x-large', top_level=False)
        return 'download.html', data, None
                            

LINUX_INSTALLER = r'''
import sys, os, shutil, tarfile, subprocess, tempfile, urllib2, re, stat

MOBILEREAD='https://dev.mobileread.com/dist/kovid/calibre/'

class TerminalController:
    BOL = ''             #: Move the cursor to the beginning of the line
    UP = ''              #: Move the cursor up one line
    DOWN = ''            #: Move the cursor down one line
    LEFT = ''            #: Move the cursor left one char
    RIGHT = ''           #: Move the cursor right one char
    
    # Deletion:
    CLEAR_SCREEN = ''    #: Clear the screen and move to home position
    CLEAR_EOL = ''       #: Clear to the end of the line.
    CLEAR_BOL = ''       #: Clear to the beginning of the line.
    CLEAR_EOS = ''       #: Clear to the end of the screen
    
    # Output modes:
    BOLD = ''            #: Turn on bold mode
    BLINK = ''           #: Turn on blink mode
    DIM = ''             #: Turn on half-bright mode
    REVERSE = ''         #: Turn on reverse-video mode
    NORMAL = ''          #: Turn off all modes
    
    # Cursor display:
    HIDE_CURSOR = ''     #: Make the cursor invisible
    SHOW_CURSOR = ''     #: Make the cursor visible
    
    # Terminal size:
    COLS = None          #: Width of the terminal (None for unknown)
    LINES = None         #: Height of the terminal (None for unknown)
    
    # Foreground colors:
    BLACK = BLUE = GREEN = CYAN = RED = MAGENTA = YELLOW = WHITE = ''
    
    # Background colors:
    BG_BLACK = BG_BLUE = BG_GREEN = BG_CYAN = ''
    BG_RED = BG_MAGENTA = BG_YELLOW = BG_WHITE = ''
    
    _STRING_CAPABILITIES = """
    BOL=cr UP=cuu1 DOWN=cud1 LEFT=cub1 RIGHT=cuf1
    CLEAR_SCREEN=clear CLEAR_EOL=el CLEAR_BOL=el1 CLEAR_EOS=ed BOLD=bold
    BLINK=blink DIM=dim REVERSE=rev UNDERLINE=smul NORMAL=sgr0
    HIDE_CURSOR=cinvis SHOW_CURSOR=cnorm""".split()
    _COLORS = """BLACK BLUE GREEN CYAN RED MAGENTA YELLOW WHITE""".split()
    _ANSICOLORS = "BLACK RED GREEN YELLOW BLUE MAGENTA CYAN WHITE".split()
    
    def __init__(self, term_stream=sys.stdout):
        # Curses isn't available on all platforms
        try: import curses
        except: return
        
        # If the stream isn't a tty, then assume it has no capabilities.
        if not hasattr(term_stream, 'isatty') or not term_stream.isatty(): return
        
        # Check the terminal type.  If we fail, then assume that the
        # terminal has no capabilities.
        try: curses.setupterm()
        except: return
        
        # Look up numeric capabilities.
        self.COLS = curses.tigetnum('cols')
        self.LINES = curses.tigetnum('lines')
        
        # Look up string capabilities.
        for capability in self._STRING_CAPABILITIES:
            (attrib, cap_name) = capability.split('=')
            setattr(self, attrib, self._tigetstr(cap_name) or '')
        
        # Colors
        set_fg = self._tigetstr('setf')
        if set_fg:
            for i,color in zip(range(len(self._COLORS)), self._COLORS):
                setattr(self, color, curses.tparm(set_fg, i) or '')
        set_fg_ansi = self._tigetstr('setaf')
        if set_fg_ansi:
            for i,color in zip(range(len(self._ANSICOLORS)), self._ANSICOLORS):
                setattr(self, color, curses.tparm(set_fg_ansi, i) or '')
        set_bg = self._tigetstr('setb')
        if set_bg:
            for i,color in zip(range(len(self._COLORS)), self._COLORS):
                setattr(self, 'BG_'+color, curses.tparm(set_bg, i) or '')
        set_bg_ansi = self._tigetstr('setab')
        if set_bg_ansi:
            for i,color in zip(range(len(self._ANSICOLORS)), self._ANSICOLORS):
                setattr(self, 'BG_'+color, curses.tparm(set_bg_ansi, i) or '')
    
    def _tigetstr(self, cap_name):
        # String capabilities can include "delays" of the form "$<2>".
        # For any modern terminal, we should be able to just ignore
        # these, so strip them out.
        import curses
        cap = curses.tigetstr(cap_name) or ''
        return re.sub(r'\$<\d+>[/*]?', '', cap)
    
    def render(self, template):
        return re.sub(r'\$\$|\${\w+}', self._render_sub, template)
    
    def _render_sub(self, match):
        s = match.group()
        if s == '$$': return s
        else: return getattr(self, s[2:-1])

class ProgressBar:
    BAR = '%3d%% ${GREEN}[${BOLD}%s%s${NORMAL}${GREEN}]${NORMAL}\n'
    HEADER = '${BOLD}${CYAN}%s${NORMAL}\n\n'
    
    def __init__(self, term, header):
        self.term = term
        if not (self.term.CLEAR_EOL and self.term.UP and self.term.BOL):
            raise ValueError("Terminal isn't capable enough -- you "
            "should use a simpler progress dispaly.")
        self.width = self.term.COLS or 75
        self.bar = term.render(self.BAR)
        self.header = self.term.render(self.HEADER % header.center(self.width))
        self.cleared = 1 #: true if we haven't drawn the bar yet.
        
    def update(self, percent, message=''):
        if isinstance(message, unicode):
            message = message.encode('utf-8', 'ignore')
        if self.cleared:
            sys.stdout.write(self.header)
            self.cleared = 0
        n = int((self.width-10)*percent)
        msg = message.center(self.width)
        sys.stdout.write(
        self.term.BOL + self.term.UP + self.term.CLEAR_EOL +
        (self.bar % (100*percent, '='*n, '-'*(self.width-10-n))) +
        self.term.CLEAR_EOL + msg)
        sys.stdout.flush()
    
    def clear(self):
        if not self.cleared:
            sys.stdout.write(self.term.BOL + self.term.CLEAR_EOL +
            self.term.UP + self.term.CLEAR_EOL +
            self.term.UP + self.term.CLEAR_EOL)
            self.cleared = 1

def download_tarball():
    try:
        pb  = ProgressBar(TerminalController(sys.stdout), 'Downloading calibre...')
    except ValueError:
        print 'Downloading calibre...'
        pb = None
    local = 'calibre-test.tar.bz2'
    src = open(local) if os.access(local, os.R_OK) else urllib2.urlopen(MOBILEREAD+'calibre-%version-i686.tar.bz2')
    if hasattr(src, 'info'):
            size = int(src.info()['content-length'])
    else:
        src.seek(0, 2)
        size = src.tell()
        src.seek(0)
    f = tempfile.NamedTemporaryFile()
    while f.tell() < size:
        f.write(src.read(4*1024))
        percent = f.tell()/float(size)
        if pb is not None:
            pb.update(percent)
        else:
            print '%d%%, '%int(percent*100),
    f.seek(0)
    return f

def extract_tarball(tar, destdir):
    print 'Extracting application files...'
    if hasattr(tar, 'read'):
        try:
            tarfile.open(fileobj=tar, mode='r').extractall(destdir)
        except: # tarfile.py on Fedora 9 is buggy
            subprocess.check_call(['tar', 'xjf', tar.name, '-C', destdir])
    else:
        tarfile.open(tar, 'r').extractall(destdir)

def main():
    defdir = '/opt/calibre'
    destdir = raw_input('Enter the installation directory for calibre (Its contents will be deleted!)[%s]: '%defdir).strip()
    if not destdir:
        destdir = defdir
    destdir = os.path.abspath(destdir)
    if os.path.exists(destdir):
        shutil.rmtree(destdir)
    os.makedirs(destdir)
    
    f = download_tarball()
    
    print 'Extracting files to %s ...'%destdir
    extract_tarball(f, destdir)
    pi = os.path.join(destdir, 'calibre_postinstall')
    subprocess.call(pi, shell=True)
    return 0
'''
