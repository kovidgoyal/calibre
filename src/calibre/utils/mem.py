#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Measure memory usage of the current process.

The key function is memory() which returns the current memory usage in MB.
You can pass a number to memory and it will be subtracted from the returned
value.
'''

import gc, os, re

from calibre.constants import iswindows, islinux

if islinux:
    # Taken, with thanks, from:
    # http://wingolog.org/archives/2007/11/27/reducing-the-footprint-of-python-applications

    def permute(args):
        ret = []
        if args:
            first = args.pop(0)
            for y in permute(args):
                for x in first:
                    ret.append(x + y)
        else:
            ret.append('')
        return ret

    def parsed_groups(match, *types):
        groups = match.groups()
        assert len(groups) == len(types)
        return tuple([type(group) for group, type in zip(groups, types)])

    class VMA(dict):
        def __init__(self, *args):
            (self.start, self.end, self.perms, self.offset,
            self.major, self.minor, self.inode, self.filename) = args

    def parse_smaps(pid):
        with open('/proc/%s/smaps'%pid, 'r') as maps:
            hex = lambda s: int(s, 16)

            ret = []
            header = re.compile(r'^([0-9a-f]+)-([0-9a-f]+) (....) ([0-9a-f]+) '
                                r'(..):(..) (\d+) *(.*)$')
            detail = re.compile(r'^(.*): +(\d+) kB')
            for line in maps:
                m = header.match(line)
                if m:
                    vma = VMA(*parsed_groups(m, hex, hex, str, hex, str, str, int, str))
                    ret.append(vma)
                else:
                    m = detail.match(line)
                    if m:
                        k, v = parsed_groups(m, str, int)
                        assert k not in vma
                        vma[k] = v
                    else:
                        print 'unparseable line:', line
            return ret

    perms = permute(['r-', 'w-', 'x-', 'ps'])

    def make_summary_dicts(vmas):
        mapped = {}
        anon = {}
        for d in mapped, anon:
            # per-perm
            for k in perms:
                d[k] = {}
                d[k]['Size'] = 0
                for y in 'Shared', 'Private':
                    d[k][y] = {}
                    for z in 'Clean', 'Dirty':
                        d[k][y][z] = 0
            # totals
            for y in 'Shared', 'Private':
                d[y] = {}
                for z in 'Clean', 'Dirty':
                    d[y][z] = 0

        for vma in vmas:
            if vma.major == '00' and vma.minor == '00':
                d = anon
            else:
                d = mapped
            for y in 'Shared', 'Private':
                for z in 'Clean', 'Dirty':
                    d[vma.perms][y][z] += vma.get(y + '_' + z, 0)
                    d[y][z] += vma.get(y + '_' + z, 0)
            d[vma.perms]['Size'] += vma.get('Size', 0)
        return mapped, anon

    def values(d, args):
        if args:
            ret = ()
            first = args[0]
            for k in first:
                ret += values(d[k], args[1:])
            return ret
        else:
            return (d,)

    def print_summary(dicts_and_titles):
        def desc(title, perms):
            ret = {('Anonymous', 'rw-p'): 'Data (malloc, mmap)',
                ('Anonymous', 'rwxp'): 'Writable code (stack)',
                ('Mapped', 'r-xp'): 'Code',
                ('Mapped', 'rwxp'): 'Writable code (jump tables)',
                ('Mapped', 'r--p'): 'Read-only data',
                ('Mapped', 'rw-p'): 'Data'}.get((title, perms), None)
            if ret:
                return '  -- ' + ret
            else:
                return ''

        for d, title in dicts_and_titles:
            print title, 'memory:'
            print '               Shared            Private'
            print '           Clean    Dirty    Clean    Dirty'
            for k in perms:
                if d[k]['Size']:
                    print ('    %s %7d  %7d  %7d  %7d%s'
                        % ((k,)
                            + values(d[k], (('Shared', 'Private'),
                                            ('Clean', 'Dirty')))
                            + (desc(title, k),)))
            print ('   total %7d  %7d  %7d  %7d'
                % values(d, (('Shared', 'Private'),
                                ('Clean', 'Dirty'))))

        print '   ' + '-' * 40
        print ('   total %7d  %7d  %7d  %7d'
            % tuple(map(sum, zip(*[values(d, (('Shared', 'Private'),
                                                ('Clean', 'Dirty')))
                                    for d, title in dicts_and_titles]))))

    def print_stats(pid=None):
        if pid is None:
            pid = os.getpid()
        vmas = parse_smaps(pid)
        mapped, anon = make_summary_dicts(vmas)
        print_summary(((mapped, "Mapped"), (anon, "Anonymous")))

    def linux_memory(since=0.0):
        vmas = parse_smaps(os.getpid())
        mapped, anon = make_summary_dicts(vmas)
        dicts_and_titles = ((mapped, "Mapped"), (anon, "Anonymous"))
        totals = tuple(map(sum, zip(*[values(d, (('Shared', 'Private'),
                                                ('Clean', 'Dirty')))
                                    for d, title in dicts_and_titles])))
        return (totals[-1]/1024.) - since

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
        return (info['WorkingSetSize']/1024.**2) - since

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
        if k not in h2:
            h2[k] = 0
        if h1[k] != h2[k]:
            print "%s: %d -> %d (%s%d)" % (
                k, h1[k], h2[k], h2[k] > h1[k] and "+" or "", h2[k] - h1[k])

