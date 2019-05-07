#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2019, Eli Schwartz <eschwartz@archlinux.org>

from __future__ import absolute_import, division, print_function, unicode_literals

import re
import subprocess

from setup import Command

class GitVersion(Command):

    description = 'Update the version from git metadata'

    def run(self, opts):
        def try_int(i):
            try:
                return int(i)
            except:
                return i

        constants_file = self.j(self.SRC, 'calibre', 'constants.py')

        with open(constants_file, 'rb') as f:
            src = f.read().decode('utf-8')

        try:
            nv = subprocess.check_output(['git', 'describe'], stderr=subprocess.STDOUT)
            nv = re.sub(r'([^-]*-g)', r'r\1', nv.decode('utf-8')[1:].strip())
            nv = tuple(map(try_int, re.split(r'\.|-', nv)))
        except subprocess.CalledProcessError:
            print('Error: not a git checkout')
            raise SystemExit(1)
        newsrc = re.sub(r'(numeric_version = )(\(.*?\))', r'\1%s' % repr(nv), src)
        self.info('new version is:', nv)

        with open(constants_file, 'wb') as f:
            f.write(newsrc.encode('utf-8'))
