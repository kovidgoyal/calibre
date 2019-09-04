#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

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


def get_cmd(exe, bypy, which, bitness):
    cmd = [exe, bypy, which]
    if bitness and bitness == '32':
        cmd.append(bitness)
    cmd.append('program')
    if not sys.stdout.isatty():
        cmd.append('--no-tty')
    cmd.append('--sign-installers')
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
    cmd = get_cmd(exe, bypy, which, bitness)
    cmd.extend(['--build-only', spec])
    ret = subprocess.Popen(cmd).wait()
    if ret != 0:
        raise SystemExit(ret)
    dist = get_dist(base, which, bitness)
    dist = os.path.join(dist, 'c-extensions')
    if shutdown:
        cmd = [exe, bypy, which, 'shutdown']
        subprocess.Popen(cmd).wait()
    return dist


def build_single(which='windows', bitness='64', shutdown=True):
    base, bypy = get_paths()
    exe = get_exe()
    cmd = get_cmd(exe, bypy, which, bitness)
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
        except EnvironmentError:
            pass
        os.link(src, dest)
    if shutdown:
        cmd = [exe, bypy, which, 'shutdown']
        subprocess.Popen(cmd).wait()


class BuildInstaller(Command):

    OS = BITNESS = ''

    def add_options(self, parser):
        parser.add_option(
            '--dont-shutdown',
            default=False,
            action='store_true',
            help='Do not shutdown the VM after building'
        )

    def run(self, opts):
        build_single(self.OS, self.BITNESS, not opts.dont_shutdown)


class BuildInstallers(BuildInstaller):

    OS = ''

    def run(self, opts):
        bits = '64 32'.split()
        for bitness in bits:
            shutdown = bitness is bits[-1] and not opts.dont_shutdown
            build_single(self.OS, bitness, shutdown)


class Linux32(BuildInstaller):
    OS = 'linux'
    BITNESS = '32'
    description = 'Build the 32-bit linux calibre installer'


class Linux64(BuildInstaller):
    OS = 'linux'
    BITNESS = '64'
    description = 'Build the 64-bit linux calibre installer'


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


class Win(BuildInstallers):
    OS = 'win'


class ExtDev(Command):

    description = 'Develop a single native extension conveniently'

    def run(self, opts):
        which, ext = opts.cli_args[:2]
        cmd = opts.cli_args[2:]
        bitness = '64' if which == 'windows' else ''
        ext_dir = build_only(which, bitness, ext)
        if which == 'windows':
            host = 'win'
            path = '/cygdrive/c/Program Files/Calibre2/app/bin/{}.pyd'
            bin_dir = '/cygdrive/c/Program Files/Calibre2'
        elif which == 'macos':
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
            subprocess.check_call(['ssh', '-S', control_path, host, 'chmod', '+w', '"{}"'.format(path)])
            with open(src, 'rb') as f:
                p = subprocess.Popen(['ssh', '-S', control_path, host, 'cat - > "{}"'.format(path)], stdin=subprocess.PIPE)
                p.communicate(f.read())
            if p.wait() != 0:
                raise SystemExit(1)
            subprocess.check_call(['ssh', '-S', control_path, host, './update-calibre'])
            enc = json.dumps(cmd)
            if not isinstance(enc, bytes):
                enc = enc.encode('utf-8')
            enc = binascii.hexlify(enc).decode('ascii')
            cmd = ['"{}"'.format(os.path.join(bin_dir, 'calibre-debug')), '-c', '"'
                    'import sys, json, binascii, os; cmd = json.loads(binascii.unhexlify(sys.argv[-1]));'
                    '''os.environ['CALIBRE_DEVELOP_FROM'] = os.path.expanduser('~/calibre-src/src');'''
                    'from calibre.debug import get_debug_executable; exe_dir = os.path.dirname(get_debug_executable());'
                    'os.execv(os.path.join(exe_dir, cmd[0]), cmd)'
                    '"', enc]
            subprocess.check_call(['ssh', '-S', control_path, host] + cmd)
        finally:
            subprocess.Popen(['ssh', '-O', 'exit', '-S', control_path, host])
