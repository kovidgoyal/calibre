#!/usr/bin/env python
# License: GPLv3 Copyright: 2019, Eli Schwartz <eschwartz@archlinux.org>


import re
import subprocess

from setup import Command


class GitVersion(Command):

    description = 'Update the version from git metadata'

    def run(self, opts):
        constants_file = self.j(self.SRC, 'calibre', 'constants.py')

        with open(constants_file, 'rb') as f:
            src = f.read().decode('utf-8')

        try:
            nv = subprocess.check_output(['git', 'describe'])
            nv = re.sub(r'([^-]*-g)', r'r\1', nv.decode('utf-8').strip().lstrip('v'))
            nv = nv.replace('-', '.')
        except subprocess.CalledProcessError:
            raise SystemExit('Error: not a git checkout')
        newsrc = re.sub(r'(git_version   = ).*', r'\1%s' % repr(nv), src)
        self.info('new version is:', nv)

        with open(constants_file, 'wb') as f:
            f.write(newsrc.encode('utf-8'))
