#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Download and install the linux binary.
'''
import sys, os, shutil, tarfile, subprocess, tempfile, urllib2, re, stat

MOBILEREAD='https://dev.mobileread.com/dist/kovid/calibre/'

class TerminalController:
    """
    A class that can be used to portably generate formatted output to
    a terminal.  
    
    `TerminalController` defines a set of instance variables whose
    values are initialized to the control sequence necessary to
    perform a given action.  These can be simply included in normal
    output to the terminal:
    
    >>> term = TerminalController()
    >>> print 'This is '+term.GREEN+'green'+term.NORMAL
    
    Alternatively, the `render()` method can used, which replaces
    '${action}' with the string required to perform 'action':
    
    >>> term = TerminalController()
    >>> print term.render('This is ${GREEN}green${NORMAL}')
    
    If the terminal doesn't support a given action, then the value of
    the corresponding instance variable will be set to ''.  As a
    result, the above code will still work on terminals that do not
    support color, except that their output will not be colored.
    Also, this means that you can test whether the terminal supports a
    given action by simply testing the truth value of the
    corresponding instance variable:
    
    >>> term = TerminalController()
    >>> if term.CLEAR_SCREEN:
    ...     print 'This terminal supports clearning the screen.'
    
    Finally, if the width and height of the terminal are known, then
    they will be stored in the `COLS` and `LINES` attributes.
    """
    # Cursor movement:
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
        """
        Create a `TerminalController` and initialize its attributes
        with appropriate values for the current terminal.
        `term_stream` is the stream that will be used for terminal
        output; if this stream is not a tty, then the terminal is
        assumed to be a dumb terminal (i.e., have no capabilities).
        """
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
        """
        Replace each $-substitutions in the given template string with
        the corresponding terminal control string (if it's defined) or
        '' (if it's not).
        """
        return re.sub(r'\$\$|\${\w+}', self._render_sub, template)
    
    def _render_sub(self, match):
        s = match.group()
        if s == '$$': return s
        else: return getattr(self, s[2:-1])

#######################################################################
# Example use case: progress bar
#######################################################################

class ProgressBar:
    """
    A 3-line progress bar, which looks like::
    
    Header
    20% [===========----------------------------------]
    progress message
    
    The progress bar is colored, if the terminal supports color
    output; and adjusts to the width of the terminal.
    """
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


LAUNCHER='''\
#!/bin/bash
frozen_path=%s
export ORIGWD=`pwd`
export LD_LIBRARY_PATH=$frozen_path:$LD_LIBRARY_PATH
cd $frozen_path
./%s "$@"
'''

def extract_tarball(tar, destdir):
    if hasattr(tar, 'read'):
        tarfile.open(fileobj=tar, mode='r').extractall(destdir)
    else:
        tarfile.open(tar, 'r').extractall(destdir)

def create_launchers(destdir, bindir='/usr/bin'):
    for launcher in open(os.path.join(destdir, 'manifest')).readlines():
        if 'postinstall' in launcher:
            continue
        launcher = launcher.strip()
        lp = os.path.join(bindir, launcher)
        print 'Creating', lp
        open(lp, 'wb').write(LAUNCHER%(destdir, launcher))
        os.chmod(lp, stat.S_IXUSR|stat.S_IXOTH|stat.S_IXGRP|stat.S_IREAD|stat.S_IWRITE|stat.S_IRGRP|stat.S_IROTH)
        
def do_postinstall(destdir):
    cwd = os.getcwd()
    try:
        os.chdir(destdir)
        os.environ['LD_LIBRARY_PATH'] = destdir+':'+os.environ.get('LD_LIBRARY_PATH', '')
        subprocess.call((os.path.join(destdir, 'calibre_postinstall'),))
    finally:
        os.chdir(cwd)

def download_tarball():
    try:
        pb  = ProgressBar(TerminalController(sys.stdout), 'Downloading calibre...')
    except ValueError:
        print 'Downloading calibre...'
        pb = None
    src = urllib2.urlopen(MOBILEREAD+'calibre-%version-i686.tar.bz2')
    size = int(src.info()['content-length'])
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

def main(args=sys.argv):
    defdir = '/opt/calibre'
    destdir = raw_input('Enter the installation directory for calibre [%s]: '%defdir)
    if not destdir:
        destdir = defdir
    if os.path.exists(destdir):
        shutil.rmtree(destdir)
    os.makedirs(destdir)
    
    f = download_tarball()
    
    print 'Extracting...'
    extract_tarball(f, destdir)
    create_launchers(destdir)
    do_postinstall(destdir)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
