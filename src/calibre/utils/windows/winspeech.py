#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>


import json
import os
import struct
import sys
from contextlib import closing
from queue import Queue
from threading import Thread

from calibre.utils.ipc.simple_worker import start_pipe_worker
from calibre.utils.shm import SharedMemory

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


def develop_loop(*commands):
    p = start_worker()
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
    with closing(p.stdin), closing(p.stdout):
        try:
            send('1 echo Synthesizer started')
            send('1 volume 0.1')
            for command in commands:
                if isinstance(command, str):
                    send(command)
                else:
                    while True:
                        m = q.get()
                        if m['related_to'] != command:
                            continue
                        if m['payload_type'] == 'media_state_changed' and m['state'] == 'ended':
                            break
                        if m['payload_type'] == 'saved':
                            break
                        if m['payload_type'] == 'error':
                            exit_code = 1
                            break
            send(f'333 echo Synthesizer exiting with exit code: {exit_code}')
            send(f'334 exit {exit_code}')
            ec = p.wait(1)
            print(f'Worker exited with code: {os.waitstatus_to_exitcode(p.wait(1))}', file=sys.stderr, flush=True)
            raise SystemExit(ec)
        finally:
            if p.poll() is None:
                p.kill()
                raise SystemExit(1)


def develop_speech(text='Lucca Brazzi sleeps with the fishes.', mark_words=True):
    print('\x1b[32mSpeaking', text, '\x1b[39m]]'[:-2], flush=True)
    st = 'ssml' if '<speak' in text else 'text'
    if mark_words:
        st = 'cued'
        words = text.split()
        text = []
        for i, w in enumerate(words):
            text.append(i+1)
            text.append(w)
            if w is not words[-1]:
                text.append(' ')

    with SharedMemory(size=max_buffer_size(text)) as shm:
        sz = encode_to_file_object(text, shm)
        develop_loop(f'2 speak {st} shm {sz} {shm.name}', 2)


def develop_save(text='Lucca Brazzi sleeps with the fishes.', filename="speech.wav"):
    print('\x1b[32mSaving', text, '\x1b[39m]]'[:-2], flush=True)
    st = 'ssml' if '<speak' in text else 'text'
    with SharedMemory(size=max_buffer_size(text)) as shm:
        sz = encode_to_file_object(text, shm)
        develop_loop(f'2 save {st} {sz} {shm.name} {filename}', 2)
