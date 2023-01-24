#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>


import json
import sys
from contextlib import closing
from queue import Queue
from threading import Thread

from calibre.utils.ipc.simple_worker import start_pipe_worker


def decode_msg(line: bytes) -> dict:
    parts = line.strip().split(b' ', 2)
    msg_id, msg_type, ans = int(parts[0]), parts[1].decode(), json.loads(parts[2])
    ans['related_to'] = msg_id
    ans['payload_type'] = msg_type
    return ans


def develop_speech(text='Lucca brazzi sleeps with the fishes'):
    p = start_pipe_worker('from calibre_extensions.winspeech import run_main_loop; run_main_loop()')
    print('\x1b[32mSpeaking', text, '\x1b[39m]]'[:-2], flush=True)
    q = Queue()

    def echo_output(p):
        for line in p.stdout:
            sys.stdout.buffer.write(b'\x1b[33m' + line + b'\x1b[39m]]'[:-2])
            sys.stdout.buffer.flush()
            q.put(decode_msg(line))

    def send(*a):
        cmd = ' '.join(map(str, a)) + '\n'
        p.stdin.write(cmd.encode())
        p.stdin.flush()

    Thread(name='Echo', target=echo_output, args=(p,), daemon=True).start()
    with closing(p.stdin), closing(p.stdout):
        try:
            send('1 echo Synthesizer started')
            send('2 speak text inline', text)
            while True:
                m = q.get()
                if m['payload_type'] == 'media_state_changed' and m['state'] == 'ended':
                    break
            send('3 echo Synthesizer exiting')
            send('exit')
            p.wait(1)
        finally:
            if p.poll() is None:
                p.kill()
