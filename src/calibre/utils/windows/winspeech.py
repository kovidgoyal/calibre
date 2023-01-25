#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>


import json
import sys
from contextlib import closing
from queue import Queue
from threading import Thread

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


def develop_speech(text=SSML_SAMPLE):
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
    with closing(p.stdin), closing(p.stdout):
        text = text.replace('\n', ' ')
        st = 'ssml' if '<speak' in text else 'text'
        try:
            send('1 echo Synthesizer started')
            send('1 volume 0.1')
            send(f'2 speak {st} inline', text)
            while True:
                m = q.get()
                if m['payload_type'] == 'media_state_changed' and m['state'] == 'ended':
                    break
                if m['payload_type'] == 'error' and m['related_to'] == 2:
                    exit_code = 1
                    break
            send(f'3 echo Synthesizer exiting with exit code: {exit_code}')
            send(f'4 exit {exit_code}')
            raise SystemExit(p.wait(1))
        finally:
            if p.poll() is None:
                p.kill()
                raise SystemExit(1)
