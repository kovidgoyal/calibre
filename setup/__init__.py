#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, re, os, platform, subprocess, time, errno, tempfile, shutil
from contextlib import contextmanager

is64bit = platform.architecture()[0] == '64bit'
iswindows = re.search('win(32|64)', sys.platform)
ismacos = 'darwin' in sys.platform
isfreebsd = 'freebsd' in sys.platform
isnetbsd = 'netbsd' in sys.platform
isdragonflybsd = 'dragonfly' in sys.platform
isbsd = isnetbsd or isfreebsd or isdragonflybsd
ishaiku = 'haiku1' in sys.platform
islinux = not ismacos and not iswindows and not isbsd and not ishaiku
sys.setup_dir = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(os.path.dirname(sys.setup_dir), 'src'))
sys.path.insert(0, SRC)
sys.resources_location = os.path.join(os.path.dirname(SRC), 'resources')
sys.extensions_location = os.path.abspath(os.environ.get('CALIBRE_SETUP_EXTENSIONS_PATH', os.path.join(SRC, 'calibre', 'plugins')))
sys.running_from_setup = True

__version__ = __appname__ = modules = functions = basenames = scripts = None

_cache_dir_built = False


def newer(targets, sources):
    if hasattr(targets, 'rjust'):
        targets = [targets]
    if hasattr(sources, 'rjust'):
        sources = [sources]
    for f in targets:
        if not os.path.exists(f):
            return True
    ttimes = map(lambda x: os.stat(x).st_mtime, targets)
    stimes = map(lambda x: os.stat(x).st_mtime, sources)
    newest_source, oldest_target = max(stimes), min(ttimes)
    return newest_source > oldest_target


def dump_json(obj, path, indent=4):
    import json
    with open(path, 'wb') as f:
        data = json.dumps(obj, indent=indent)
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        f.write(data)


def download_securely(url):
    # We use curl here as on some OSes (OS X) when bootstrapping calibre,
    # python will be unable to validate certificates until after cacerts is
    # installed
    return subprocess.check_output(['curl', '-fsSL', url])


def build_cache_dir():
    global _cache_dir_built
    ans = os.path.join(os.path.dirname(SRC), '.build-cache')
    if not _cache_dir_built:
        _cache_dir_built = True
        try:
            os.mkdir(ans)
        except EnvironmentError as err:
            if err.errno != errno.EEXIST:
                raise
    return ans


def require_git_master(branch='master'):
    if subprocess.check_output(['git', 'symbolic-ref', '--short', 'HEAD']).decode('utf-8').strip() != branch:
        raise SystemExit('You must be in the {} git branch'.format(branch))


def require_clean_git():
    c = subprocess.check_call
    p = subprocess.Popen
    c('git rev-parse --verify HEAD'.split(), stdout=subprocess.DEVNULL)
    c('git update-index -q --ignore-submodules --refresh'.split())
    if p('git diff-files --quiet --ignore-submodules'.split()).wait() != 0:
        raise SystemExit('You have unstaged changes in your working tree')
    if p('git diff-index --cached --quiet --ignore-submodules HEAD --'.split()).wait() != 0:
        raise SystemExit('Your git index contains uncommitted changes')


def initialize_constants():
    global __version__, __appname__, modules, functions, basenames, scripts

    with open(os.path.join(SRC, 'calibre/constants.py'), 'rb') as f:
        src = f.read().decode('utf-8')
    nv = re.search(r'numeric_version\s+=\s+\((\d+), (\d+), (\d+)\)', src)
    __version__ = '%s.%s.%s'%(nv.group(1), nv.group(2), nv.group(3))
    __appname__ = re.search(r'__appname__\s+=\s+(u{0,1})[\'"]([^\'"]+)[\'"]',
            src).group(2)
    epsrc = re.compile(r'entry_points = (\{.*?\})', re.DOTALL).\
            search(open(os.path.join(SRC, 'calibre/linux.py'), 'rb').read().decode('utf-8')).group(1)
    entry_points = eval(epsrc, {'__appname__': __appname__})

    def e2b(ep):
        return re.search(r'\s*(.*?)\s*=', ep).group(1).strip()

    def e2s(ep, base='src'):
        return (base+os.path.sep+re.search(r'.*=\s*(.*?):', ep).group(1).replace('.', '/')+'.py').strip()

    def e2m(ep):
        return re.search(r'.*=\s*(.*?)\s*:', ep).group(1).strip()

    def e2f(ep):
        return ep[ep.rindex(':')+1:].strip()

    basenames, functions, modules, scripts = {}, {}, {}, {}
    for x in ('console', 'gui'):
        y = x + '_scripts'
        basenames[x] = list(map(e2b, entry_points[y]))
        functions[x] = list(map(e2f, entry_points[y]))
        modules[x] = list(map(e2m, entry_points[y]))
        scripts[x] = list(map(e2s, entry_points[y]))


initialize_constants()
preferred_encoding = 'utf-8'
prints = print
warnings = []


def get_warnings():
    return list(warnings)


def edit_file(path):
    return subprocess.Popen([
        'vim', '-c', 'SyntasticCheck', '-c', 'll', '-S', os.path.join(SRC, '../session.vim'), '-f', path
    ]).wait() == 0


class Command(object):

    SRC = SRC
    RESOURCES = os.path.join(os.path.dirname(SRC), 'resources')
    description = ''

    sub_commands = []

    def __init__(self):
        self.d = os.path.dirname
        self.j = os.path.join
        self.a = os.path.abspath
        self.b = os.path.basename
        self.s = os.path.splitext
        self.e = os.path.exists
        self.orig_euid = os.geteuid() if hasattr(os, 'geteuid') else None
        self.real_uid = os.environ.get('SUDO_UID', None)
        self.real_gid = os.environ.get('SUDO_GID', None)
        self.real_user = os.environ.get('SUDO_USER', None)

    def drop_privileges(self):
        if not islinux or ismacos or isfreebsd:
            return
        if self.real_user is not None:
            self.info('Dropping privileges to those of', self.real_user+':',
                    self.real_uid)
        if self.real_gid is not None:
            os.setegid(int(self.real_gid))
        if self.real_uid is not None:
            os.seteuid(int(self.real_uid))

    def regain_privileges(self):
        if not islinux or ismacos or isfreebsd:
            return
        if os.geteuid() != 0 and self.orig_euid == 0:
            self.info('Trying to get root privileges')
            os.seteuid(0)
            if os.getegid() != 0:
                os.setegid(0)

    def pre_sub_commands(self, opts):
        pass

    def running(self, cmd):
        from setup.commands import command_names
        self.info('\n*')
        self.info('* Running', command_names[cmd])
        self.info('*\n')

    def run_cmd(self, cmd, opts):
        from setup.commands import command_names
        cmd.pre_sub_commands(opts)
        for scmd in cmd.sub_commands:
            self.run_cmd(scmd, opts)

        st = time.time()
        self.running(cmd)
        cmd.run(opts)
        self.info('* %s took %.1f seconds' % (command_names[cmd], time.time() - st))

    def run_all(self, opts):
        self.run_cmd(self, opts)

    def add_command_options(self, command, parser):
        import setup.commands as commands
        command.sub_commands = [getattr(commands, cmd) for cmd in
                command.sub_commands]
        for cmd in command.sub_commands:
            self.add_command_options(cmd, parser)

        command.add_options(parser)

    def add_all_options(self, parser):
        self.add_command_options(self, parser)

    def run(self, opts):
        pass

    def add_options(self, parser):
        pass

    def clean(self):
        pass

    @classmethod
    def newer(cls, targets, sources):
        '''
        Return True if sources is newer that targets or if targets
        does not exist.
        '''
        return newer(targets, sources)

    def info(self, *args, **kwargs):
        prints(*args, **kwargs)
        sys.stdout.flush()

    def warn(self, *args, **kwargs):
        print('\n'+'_'*20, 'WARNING','_'*20)
        prints(*args, **kwargs)
        print('_'*50)
        warnings.append((args, kwargs))
        sys.stdout.flush()

    @contextmanager
    def temp_dir(self, **kw):
        ans = tempfile.mkdtemp(**kw)
        try:
            yield ans
        finally:
            shutil.rmtree(ans)


def installer_name(ext, is64bit=False):
    if is64bit and ext == 'msi':
        return 'dist/%s-64bit-%s.msi'%(__appname__, __version__)
    if ext in ('exe', 'msi'):
        return 'dist/%s-%s.%s'%(__appname__, __version__, ext)
    if ext == 'dmg':
        if is64bit:
            return 'dist/%s-%s-x86_64.%s'%(__appname__, __version__, ext)
        return 'dist/%s-%s.%s'%(__appname__, __version__, ext)

    ans = 'dist/%s-%s-i686.%s'%(__appname__, __version__, ext)
    if is64bit:
        ans = ans.replace('i686', 'x86_64')
    return ans
