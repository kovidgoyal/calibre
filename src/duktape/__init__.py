#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


__all__ = ['dukpy', 'Context', 'undefined']

import errno, os
from functools import partial

from calibre.constants import plugins
dukpy, err = plugins['dukpy']
if err:
    raise RuntimeError('Failed to load dukpy with error: %s' % err)
del err
Context_, undefined = dukpy.Context, dukpy.undefined

def load_file(base_dirs, name):
    for b in base_dirs:
        try:
            return open(os.path.join(b, name), 'rb').read().decode('utf-8')
        except EnvironmentError as e:
            if e.errno != errno.ENOENT:
                raise
    raise EnvironmentError('No module named: %s found in the base directories: %s' % (name, os.pathsep.join(base_dirs)))

def Context(base_dirs=()):
    ans = Context_()
    if not base_dirs:
        base_dirs = (os.getcwdu(),)
    ans.g.Duktape.load_file = partial(load_file, base_dirs or (os.getcwdu(),))
    ans.eval('''
console = { log: function() { print(Array.prototype.join.call(arguments, ' ')); } };
Duktape.modSearch = function (id, require, exports, module) {
   return Duktape.load_file(id);
}
''')
    return ans
