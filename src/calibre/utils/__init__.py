#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Miscelleaneous utilities.
'''

from time import time

def join_with_timeout(q, timeout=2):
    ''' Join the queue q with a specified timeout. Blocks until all tasks on
    the queue are done or times out with a runtime error. '''
    q.all_tasks_done.acquire()
    try:
        endtime = time() + timeout
        while q.unfinished_tasks:
            remaining = endtime - time()
            if remaining <= 0.0:
                raise RuntimeError('Waiting for queue to clear timed out')
            q.all_tasks_done.wait(remaining)
    finally:
        q.all_tasks_done.release()

