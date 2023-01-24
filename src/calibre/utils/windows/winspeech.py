#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>


import sys
import time
from contextlib import closing
from threading import Thread

from calibre.utils.ipc.simple_worker import start_pipe_worker


def develop_speech(text='Lucca brazzi sleeps with the fishes'):
    p = start_pipe_worker('from calibre_extensions.winspeech import run_main_loop; run_main_loop()')
    print('\x1b[32mSpeaking', text, '\x1b[39m', flush=True)

    def echo_output(p):
        for line in p.stdout:
            sys.stdout.buffer.write(b'\x1b[33m' + line + b'\x1b[39m')
            sys.stdout.buffer.flush()

    def send(*a):
        cmd = ' '.join(map(str, a)) + '\n'
        p.stdin.write(cmd.encode())
        p.stdin.flush()

    Thread(name='Echo', target=echo_output, args=(p,), daemon=True).start()
    with closing(p.stdin), closing(p.stdout):
        try:
            send('1 echo Synthesizer started')
            send('2 speak text inline', text)
            time.sleep(6)
            send('3 echo Synthesizer exiting')
            send('exit')
            time.sleep(1)
        finally:
            if p.poll() is None:
                p.kill()
