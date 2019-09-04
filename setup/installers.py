#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

import os, sys, subprocess

from setup import Command


def build_single(which, bitness, shutdown=True):
    d = os.path.dirname
    base = d(d(os.path.abspath(__file__)))
    bypy = os.path.join(d(base), 'bypy')
    bypy = os.environ.get('BYPY_LOCATION', bypy)
    if not os.path.isdir(bypy):
        raise SystemExit(
            'Cannot find the bypy code. Set the environment variable BYPY_LOCATION to point to it'
        )
    exe = 'python3' if sys.version_info.major == 2 else sys.executable
    cmd = [exe, bypy, which]
    if bitness and bitness == '32':
        cmd.append(bitness)
    cmd.append('program')
    if not sys.stdout.isatty():
        cmd.append('--no-tty')
    cmd.append('--sign-installers')
    ret = subprocess.Popen(cmd).wait()
    if ret != 0:
        raise SystemExit(ret)
    dist = os.path.join(base, 'bypy', 'b', which)
    if bitness:
        dist = os.path.join(dist, bitness)
    for q in 'dist sw/dist'.split():
        if os.path.exists(os.path.join(dist, q)):
            dist = os.path.join(dist, q)
            break
    for x in os.listdir(dist):
        print(x)
        dest = os.path.join(base, 'dist', x)
        try:
            os.remove(dest)
        except EnvironmentError:
            pass
        os.link(os.path.join(dist, x), dest)
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
