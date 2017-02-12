#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import, print_function)
import os, sys, subprocess

from setup import Command


def build_single(which, bitness, shutdown=True):
    d = os.path.dirname
    base = d(d(os.path.abspath(__file__)))
    build_calibre = os.path.join(d(base), 'build-calibre')
    build_calibre = os.environ.get('BUILD_CALIBRE_LOCATION', build_calibre)
    if not os.path.isdir(build_calibre):
        raise SystemExit(
            'Cannot find the build-calibre code. Set the environment variable BUILD_CALIBRE_LOCATION to point to it'
        )
    cmd = [sys.executable, os.path.join(build_calibre, which)]
    if bitness:
        cmd.append(bitness)
    cmd.append('calibre')
    cmd.append('--sign-installers')
    env = os.environ.copy()
    env['CALIBRE_SRC_DIR'] = base
    ret = subprocess.Popen(cmd, env=env, cwd=build_calibre).wait()
    if ret != 0:
        raise SystemExit(ret)
    dist = os.path.join(build_calibre, 'build', which)
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
        cmd = [sys.executable, os.path.join(build_calibre, which), 'shutdown']
        subprocess.Popen(cmd, env=env, cwd=build_calibre).wait()


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
    OS = 'win'
    BITNESS = '32'
    description = 'Build the 32-bit windows calibre installers'


class Win64(BuildInstaller):
    OS = 'win'
    BITNESS = '64'
    description = 'Build the 64-bit windows calibre installer'


class OSX(BuildInstaller):
    OS = 'osx'


class Linux(BuildInstallers):
    OS = 'linux'


class Win(BuildInstallers):
    OS = 'win'
