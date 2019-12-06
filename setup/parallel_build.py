#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import subprocess, os, itertools, json, sys
from multiprocessing.dummy import Pool
from threading import Thread
from functools import partial
from contextlib import closing

from polyglot.builtins import unicode_type, as_bytes

cpu_count = min(16, max(1, os.cpu_count()))


def run_worker(job, decorate=True):
    cmd, human_text = job
    human_text = human_text or ' '.join(cmd)
    cwd = None
    if cmd[0].lower().endswith('cl.exe'):
        cwd = os.environ.get('COMPILER_CWD')
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd)
    except Exception as err:
        return False, human_text, unicode_type(err)
    stdout, stderr = p.communicate()
    if stdout:
        stdout = stdout.decode('utf-8')
    if stderr:
        stderr = stderr.decode('utf-8')
    if decorate:
        stdout = human_text + '\n' + (stdout or '')
    ok = p.returncode == 0
    return ok, stdout, (stderr or '')


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


def get_tasks(it, size):
    it = iter(it)
    while 1:
        x = tuple(itertools.islice(it, size))
        if not x:
            return
        yield x


def batched_parallel_jobs(cmd, jobs, cwd=None):
    chunksize, extra = divmod(len(jobs), cpu_count)
    if extra:
        chunksize += 1
    workers = []

    def get_output(p):
        p.output = p.communicate(as_bytes(json.dumps(p.jobs_batch)))

    for batch in get_tasks(jobs, chunksize):
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
        p.jobs_batch = batch
        p.output_thread = t = Thread(target=get_output, args=(p,))
        t.daemon = True
        t.start()
        workers.append(p)

    failed = False
    ans = []
    for p in workers:
        p.output_thread.join()
        if p.wait() != 0:
            sys.stderr.buffer.write(p.output[1])
            sys.stderr.buffer.flush()
            failed = True
        else:
            ans.extend(json.loads(p.output[0]))
    if failed:
        raise SystemExit('Worker process failed')
    return ans
