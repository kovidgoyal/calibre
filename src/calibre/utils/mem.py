#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Measure memory usage of the current process.

The key function is memory() which returns the current memory usage in MB.
You can pass a number to memory and it will be subtracted from the returned
value.
'''

import gc, os


def get_memory():
    'Return memory usage in bytes'
    # See https://pythonhosted.org/psutil/#psutil.Process.memory_info
    import psutil
    return psutil.Process(os.getpid()).memory_info().rss


def memory(since=0.0):
    'Return memory used in MB. The value of since is subtracted from the used memory'
    ans = get_memory()
    ans /= float(1024**2)
    return ans - since


def gc_histogram():
    """Returns per-class counts of existing objects."""
    result = {}
    for o in gc.get_objects():
        t = type(o)
        count = result.get(t, 0)
        result[t] = count + 1
    return result


def diff_hists(h1, h2):
    """Prints differences between two results of gc_histogram()."""
    for k in h1:
        if k not in h2:
            h2[k] = 0
        if h1[k] != h2[k]:
            print("%s: %d -> %d (%s%d)" % (
                k, h1[k], h2[k], h2[k] > h1[k] and "+" or "", h2[k] - h1[k]))
