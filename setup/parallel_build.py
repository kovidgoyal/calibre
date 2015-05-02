#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import subprocess
from multiprocessing.dummy import Pool
from functools import partial
from contextlib import closing

from setup.build_environment import cpu_count

def run_worker(job, decorate=True):
    cmd, human_text = job
    human_text = human_text or b' '.join(cmd)
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except Exception as err:
        return False, human_text, unicode(err)
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
                log(stdout)
                if stderr:
                    log(stderr)
            if not ok:
                return False
        return True

def parallel_check_output(jobs, log):
    p = Pool(cpu_count)
    with closing(p):
        for ok, stdout, stderr in p.imap(
                partial(run_worker, decorate=False), ((j, '') for j in jobs)):
            if not ok:
                log(stdout)
                if stderr:
                    log(stderr)
                raise SystemExit(1)
            yield stdout
