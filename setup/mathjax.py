#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil

from setup import Command

def size_dir(d):
    file_walker = (
        os.path.join(root, f)
        for root, _, files in os.walk(d)
        for f in files
    )
    return sum(os.path.getsize(f) for f in file_walker)

class MathJax(Command):

    description = 'Rebuild the bundled copy of mathjax'

    MATHJAX_PATH = '../mathjax'

    def run(self, opts):
        base = self.a(self.j(self.d(self.SRC), self.MATHJAX_PATH))
        dest = self.j(self.RESOURCES, 'viewer', 'mathjax')
        if os.path.exists(dest):
            shutil.rmtree(dest)
        os.mkdir(dest)
        up = self.j(base, 'unpacked')
        for x in os.listdir(up):
            if x == 'config': continue
            if os.path.isdir(self.j(up, x)):
                shutil.copytree(self.j(up, x), self.j(dest, x))
            else:
                shutil.copy(self.j(up, x), dest)

        op = self.j(dest, 'jax', 'output')
        for x in os.listdir(op):
            if x != 'SVG':
                shutil.rmtree(self.j(op, x))

        shutil.rmtree(self.j(dest, 'extensions', 'HTML-CSS'))

        print ('MathJax bundle updated. Size: %g MB'%(size_dir(dest)/(1024**2)))

