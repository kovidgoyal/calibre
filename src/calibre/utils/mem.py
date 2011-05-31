#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Measure memory usage of the current process.

The key function is memory() which returns the current memory usage in bytes.
You can pass a number to memory and it will be subtracted from the returned
value.
'''

import gc, os

from calibre.constants import iswindows, islinux

if islinux:
    ## {{{ http://code.activestate.com/recipes/286222/ (r1)

    _proc_status = '/proc/%d/status' % os.getpid()

    _scale = {'kB': 1024.0, 'mB': 1024.0*1024.0,
            'KB': 1024.0, 'MB': 1024.0*1024.0}

    def _VmB(VmKey):
        '''Private.
        '''
        global _proc_status, _scale
        # get pseudo file  /proc/<pid>/status
        try:
            t = open(_proc_status)
            v = t.read()
            t.close()
        except:
            return 0.0  # non-Linux?
        # get VmKey line e.g. 'VmRSS:  9999  kB\n ...'
        i = v.index(VmKey)
        v = v[i:].split(None, 3)  # whitespace
        if len(v) < 3:
            return 0.0  # invalid format?
        # convert Vm value to bytes
        return float(v[1]) * _scale[v[2]]


    def linux_memory(since=0.0):
        '''Return memory usage in bytes.
        '''
        return _VmB('VmSize:') - since


    def resident(since=0.0):
        '''Return resident memory usage in bytes.
        '''
        return _VmB('VmRSS:') - since


    def stacksize(since=0.0):
        '''Return stack size in bytes.
        '''
        return _VmB('VmStk:') - since
    ## end of http://code.activestate.com/recipes/286222/ }}}
    memory = linux_memory
elif iswindows:
    import win32process
    import win32con
    import win32api

    # See http://msdn.microsoft.com/en-us/library/ms684877.aspx
    # for details on the info returned by get_meminfo

    def get_handle(pid):
        return win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, 0,
                pid)

    def listprocesses(self):
        for process in win32process.EnumProcesses():
            try:
                han = get_handle(process)
                procmeminfo = meminfo(han)
                procmemusage = procmeminfo["WorkingSetSize"]
                yield process, procmemusage
            except:
                pass

    def get_meminfo(pid):
        han = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, 0,
                pid)
        return meminfo(han)

    def meminfo(handle):
        return win32process.GetProcessMemoryInfo(handle)

    def win_memory(since=0.0):
        info = meminfo(get_handle(os.getpid()))
        return info['WorkingSetSize'] - since

    memory = win_memory


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
        if h1[k] != h2[k]:
            print "%s: %d -> %d (%s%d)" % (
                k, h1[k], h2[k], h2[k] > h1[k] and "+" or "", h2[k] - h1[k])

