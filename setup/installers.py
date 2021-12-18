#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import os, sys, subprocess, binascii, json

from setup import Command


d = os.path.dirname


def get_paths():
    base = d(d(os.path.abspath(__file__)))
    bypy = os.path.join(d(base), 'bypy')
    bypy = os.environ.get('BYPY_LOCATION', bypy)
    if not os.path.isdir(bypy):
        raise SystemExit(
            'Cannot find the bypy code. Set the environment variable BYPY_LOCATION to point to it'
        )
    return base, bypy


def get_exe():
    return 'python3' if sys.version_info.major == 2 else sys.executable


def get_cmd(exe, bypy, which, bitness, sign_installers=False, notarize=True, compression_level='9', action='program'):
    cmd = [exe, bypy, which]
    if bitness and bitness != '64':
        cmd += ['--arch', bitness]
    cmd.append(action)
    if action == 'program':
        if sign_installers or notarize:
            cmd.append('--sign-installers')
        if notarize:
            cmd.append('--notarize')
        cmd.append('--compression-level=' + compression_level)
    return cmd


def get_dist(base, which, bitness):
    dist = os.path.join(base, 'bypy', 'b', which)
    if bitness:
        dist = os.path.join(dist, bitness)
    for q in 'dist sw/dist'.split():
        if os.path.exists(os.path.join(dist, q)):
            dist = os.path.join(dist, q)
            break
    return dist


def build_only(which, bitness, spec, shutdown=False):
    base, bypy = get_paths()
    exe = get_exe()
    cmd = get_cmd(exe, bypy, which, bitness, False)
    cmd.extend(['--build-only', spec])
    ret = subprocess.Popen(cmd).wait()
    if ret != 0:
        raise SystemExit(ret)
    dist = get_dist(base, which, bitness)
    dist = os.path.join(dist, 'c-extensions')
    if shutdown:
        cmd = get_cmd(exe, bypy, which, bitness, action='shutdown')
        subprocess.Popen(cmd).wait()
    return dist


def build_single(which='windows', bitness='64', shutdown=True, sign_installers=True, notarize=True, compression_level='9'):
    base, bypy = get_paths()
    exe = get_exe()
    cmd = get_cmd(exe, bypy, which, bitness, sign_installers, notarize, compression_level=compression_level)
    ret = subprocess.Popen(cmd).wait()
    if ret != 0:
        raise SystemExit(ret)
    dist = get_dist(base, which, bitness)
    for x in os.listdir(dist):
        src = os.path.join(dist, x)
        if os.path.isdir(src):
            continue
        print(x)
        dest = os.path.join(base, 'dist', x)
        try:
            os.remove(dest)
        except OSError:
            pass
        os.link(src, dest)
    if shutdown:
        cmd = get_cmd(exe, bypy, which, bitness, action='shutdown')
        subprocess.Popen(cmd).wait()


def build_dep(args):
    base, bypy = get_paths()
    exe = get_exe()
    cmd = [exe, bypy] + list(args)
    ret = subprocess.Popen(cmd).wait()
    if ret != 0:
        raise SystemExit(ret)


class BuildInstaller(Command):

    OS = BITNESS = ''

    def add_options(self, parser):
        parser.add_option(
            '--dont-shutdown',
            default=False,
            action='store_true',
            help='Do not shutdown the VM after building'
        )
        parser.add_option(
            '--dont-sign',
            default=False,
            action='store_true',
            help='Do not sign the installers'
        )
        parser.add_option(
            '--dont-notarize',
            default=False,
            action='store_true',
            help='Do not notarize the installers'
        )
        parser.add_option(
            '--compression-level',
            default='9',
            choices=list('123456789'),
            help='Do not notarize the installers'
        )

    def run(self, opts):
        build_single(
            self.OS, self.BITNESS, not opts.dont_shutdown,
            not opts.dont_sign, not opts.dont_notarize,
            compression_level=opts.compression_level
        )


class BuildInstallers(BuildInstaller):

    OS = ''
    ALL_ARCHES = '64', '32'

    def run(self, opts):
        for bitness in self.ALL_ARCHES:
            shutdown = bitness is self.ALL_ARCHES[-1] and not opts.dont_shutdown
            build_single(self.OS, bitness, shutdown)


class Linux32(BuildInstaller):
    OS = 'linux'
    BITNESS = '32'
    description = 'Build the 32-bit Linux calibre installer'


class Linux64(BuildInstaller):
    OS = 'linux'
    BITNESS = '64'
    description = 'Build the 64-bit Linux calibre installer'


class LinuxArm64(BuildInstaller):
    OS = 'linux'
    BITNESS = 'arm64'
    description = 'Build the 64-bit ARM Linux calibre installer'


class Win32(BuildInstaller):
    OS = 'windows'
    BITNESS = '32'
    description = 'Build the 32-bit windows calibre installers'


class Win64(BuildInstaller):
    OS = 'windows'
    BITNESS = '64'
    description = 'Build the 64-bit windows calibre installer'


class OSX(BuildInstaller):
    OS = 'macos'


class Linux(BuildInstallers):
    OS = 'linux'
    ALL_ARCHES = '64', '32', 'arm64'


class Win(BuildInstallers):
    OS = 'windows'


class BuildDep(Command):

    description = (
        'Build a calibre dependency. For example, build_dep windows expat.'
        ' Without arguments builds all deps for specified platform. Use windows 32 for 32bit.'
        ' Use build_dep all somedep to build a dep for all platforms.'
    )

    def run(self, opts):
        args = opts.cli_args
        if args and args[0] == 'all':
            for x in ('linux', 'linux 32', 'macos', 'windows', 'windows 32'):
                build_dep(x.split() + list(args)[1:])
        else:
            build_dep(args)


class ExportPackages(Command):

    description = 'Export built deps to a server for CI testing'

    def run(self, opts):
        base, bypy = get_paths()
        exe = get_exe()
        cmd = [exe, bypy, 'export'] + list(opts.cli_args) + ['download.calibre-ebook.com:/srv/download/ci/calibre3']
        ret = subprocess.Popen(cmd).wait()
        if ret != 0:
            raise SystemExit(ret)


class ExtDev(Command):

    description = 'Develop a single native extension conveniently'

    def run(self, opts):
        which, ext = opts.cli_args[:2]
        cmd = opts.cli_args[2:] or ['calibre-debug', '--test-build']
        bitness = '64' if which == 'windows' else ''
        ext_dir = build_only(which, bitness, ext)
        if which == 'windows':
            host = 'win'
            path = '/cygdrive/c/Program Files/Calibre2/app/bin/{}.pyd'
            bin_dir = '/cygdrive/c/Program Files/Calibre2'
        elif which == 'macos':
            print(
                "\n\n\x1b[33;1mWARNING: This does not work on macOS, unless you use un-signed builds with ",
                ' ./update-on-ox develop\x1b[m',
                file=sys.stderr, end='\n\n\n')
            host = 'ox'
            path = '/Applications/calibre.app/Contents/Frameworks/plugins/{}.so'
            bin_dir = '/Applications/calibre.app/Contents/MacOS'
        control_path = os.path.expanduser('~/.ssh/extdev-master-%C')
        if subprocess.Popen([
            'ssh', '-o', 'ControlMaster=auto', '-o', 'ControlPath=' + control_path, '-o', 'ControlPersist=yes', host,
            'echo', 'ssh master running'
        ]).wait() != 0:
            raise SystemExit(1)
        try:
            path = path.format(ext)
            src = os.path.join(ext_dir, os.path.basename(path))
            subprocess.check_call(['ssh', '-S', control_path, host, 'chmod', '+w', f'"{path}"'])
            with open(src, 'rb') as f:
                p = subprocess.Popen(['ssh', '-S', control_path, host, f'cat - > "{path}"'], stdin=subprocess.PIPE)
                p.communicate(f.read())
            if p.wait() != 0:
                raise SystemExit(1)
            subprocess.check_call(['ssh', '-S', control_path, host, './update-calibre'])
            enc = json.dumps(cmd)
            if not isinstance(enc, bytes):
                enc = enc.encode('utf-8')
            enc = binascii.hexlify(enc).decode('ascii')
            wcmd = ['"{}"'.format(os.path.join(bin_dir, 'calibre-debug')), '-c', '"'
                    'import sys, json, binascii, os, subprocess; cmd = json.loads(binascii.unhexlify(sys.argv[-1]));'
                    'env = os.environ.copy();'
                    '''env[str('CALIBRE_DEVELOP_FROM')] = str(os.path.abspath('calibre-src/src'));'''
                    'from calibre.debug import get_debug_executable; exe_dir = os.path.dirname(get_debug_executable()[0]);'
                    'cmd[0] = os.path.join(exe_dir, cmd[0]); ret = subprocess.Popen(cmd, env=env).wait();'
                    'sys.stdout.flush(); sys.stderr.flush(); sys.exit(ret)'
                    '"', enc]
            ret = subprocess.Popen(['ssh', '-S', control_path, host] + wcmd).wait()
            if ret != 0:
                raise SystemExit('The test command "{}" failed with exit code: {}'.format(' '.join(cmd), ret))
        finally:
            subprocess.Popen(['ssh', '-O', 'exit', '-S', control_path, host])
