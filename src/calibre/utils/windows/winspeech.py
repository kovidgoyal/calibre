#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>


import json
import struct
import sys
from contextlib import closing
from queue import Queue
from threading import Thread

from calibre.utils.shm import SharedMemory
from calibre.utils.ipc.simple_worker import start_pipe_worker

SSML_SAMPLE = '''
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
    <voice name="en-US-AriaNeural">
        We are selling <bookmark mark='flower_1'/>roses and <bookmark mark='flower_2'/>daisies.
    </voice>
</speak>
'''

def decode_msg(line: bytes) -> dict:
    parts = line.strip().split(b' ', 2)
    msg_id, msg_type, ans = int(parts[0]), parts[1].decode(), json.loads(parts[2])
    ans['related_to'] = msg_id
    ans['payload_type'] = msg_type
    return ans


def start_worker():
    return start_pipe_worker('from calibre_extensions.winspeech import run_main_loop; raise SystemExit(run_main_loop())')


def max_buffer_size(text) -> int:
    if isinstance(text, str):
        text = [text]
    ans = 0
    for x in text:
        if isinstance(x, int):
            ans += 5
        else:
            ans += 4 * len(x)
    return ans


def encode_to_file_object(text, output) -> int:
    if isinstance(text, str):
        text = [text]
    p = struct.pack
    sz = 0
    for x in text:
        if isinstance(x, int):
            output.write(b'\0')
            output.write(p('=I', x))
            sz += 5
        else:
            b = x.encode('utf-8')
            output.write(b)
            sz += len(b)
    return sz


def develop_speech(text='Lucca Brazzi sleeps with the fishes.'):
    p = start_worker()
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
    exit_code = 0
    with closing(p.stdin), closing(p.stdout), SharedMemory(size=max_buffer_size(text)) as shm:
        st = 'ssml' if '<speak' in text else 'text'
        sz = encode_to_file_object(text, shm)
        try:
            send('1 echo Synthesizer started')
            send('1 volume 0.1')
            send(f'2 speak {st} shm {sz} {shm.name}')
            while True:
                m = q.get()
                if m['related_to'] != 2:
                    continue
                if m['payload_type'] == 'media_state_changed' and m['state'] == 'ended':
                    break
                if m['payload_type'] == 'error':
                    exit_code = 1
                    break
            send(f'3 echo Synthesizer exiting with exit code: {exit_code}')
            send(f'4 exit {exit_code}')
            raise SystemExit(p.wait(1))
        finally:
            if p.poll() is None:
                p.kill()
                raise SystemExit(1)
