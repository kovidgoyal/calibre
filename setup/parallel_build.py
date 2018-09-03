#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import six

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import subprocess
from multiprocessing.dummy import Pool
from functools import partial
from contextlib import closing

from setup import iswindows

if iswindows:
    from ctypes import windll, Structure, POINTER, c_size_t
    from ctypes.wintypes import WORD, DWORD, LPVOID
    class SYSTEM_INFO(Structure):
        _fields_ = [
            ("wProcessorArchitecture",      WORD),
            ("wReserved",                   WORD),
            ("dwPageSize",                  DWORD),
            ("lpMinimumApplicationAddress", LPVOID),
            ("lpMaximumApplicationAddress", LPVOID),
            ("dwActiveProcessorMask",       c_size_t),
            ("dwNumberOfProcessors",        DWORD),
            ("dwProcessorType",             DWORD),
            ("dwAllocationGranularity",     DWORD),
            ("wProcessorLevel",             WORD),
            ("wProcessorRevision",          WORD)]
    gsi = windll.kernel32.GetSystemInfo
    gsi.argtypes = [POINTER(SYSTEM_INFO)]
    gsi.restype = None
    si = SYSTEM_INFO()
    gsi(si)
    cpu_count = si.dwNumberOfProcessors
else:
    from multiprocessing import cpu_count
    try:
        cpu_count = cpu_count()
    except NotImplementedError:
        cpu_count = 1

cpu_count = min(16, max(1, cpu_count))

def run_worker(job, decorate=True):
    cmd, human_text = job
    cmd = [param.encode('utf-8') for param in cmd]
    human_text = human_text or b' '.join(cmd)
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except Exception as err:
        return False, human_text, six.text_type(err)
    stdout, stderr = p.communicate()
    if decorate:
        stdout = bytes(human_text) + b'\n' + (stdout or b'')
    ok = p.returncode == 0
    return ok, stdout, (stderr or b'')

def create_job(cmd, human_text=None):
    return (cmd, human_text)

def parallel_build(jobs, log, verbose=True):
    p = Pool(cpu_count)
    with closing(p):
        for ok, stdout, stderr in p.imap(run_worker, jobs):
            if verbose or not ok:
                log(stdout.decode('utf-8'))
                if stderr:
                    log(stderr.decode('utf-8'))
            if not ok:
                return False
        return True

def parallel_check_output(jobs, log):
    p = Pool(cpu_count)
    with closing(p):
        for ok, stdout, stderr in p.imap(
                partial(run_worker, decorate=False), ((j, '') for j in jobs)):
            if not ok:
                log(stdout.decode())
                if stderr:
                    log(stderr.decode())
                raise SystemExit(1)
            yield stdout.decode()
