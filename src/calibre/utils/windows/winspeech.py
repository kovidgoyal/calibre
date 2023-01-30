#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>


import json
import os
import struct
import sys
from contextlib import closing
from enum import Enum, auto
from itertools import count
from queue import Queue
from threading import Thread
from typing import NamedTuple, Tuple

from calibre.utils.ipc.simple_worker import start_pipe_worker
from calibre.utils.shm import SharedMemory

SSML_SAMPLE = '''
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
    <voice name="en-US-AriaNeural">
        We are selling <bookmark mark='flower_1'/>roses and <bookmark mark='flower_2'/>daisies.
    </voice>
</speak>
'''

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


# message decoding {{{
class Saving(NamedTuple):
    related_to: int
    ssml: bool
    output_path: str


class Saved(NamedTuple):
    related_to: int
    size: int


class CueEntered(NamedTuple):
    related_to: int
    start_pos_in_text: int
    end_pos_in_text: int
    start_time: int
    type: str
    text: str


class CueExited(CueEntered):
    related_to: int
    start_pos_in_text: int
    end_pos_in_text: int
    start_time: int
    type: str


class MarkReached(NamedTuple):
    related_to: int
    id: int


class Error(NamedTuple):
    msg: str
    error: str = ''
    line: int = 0
    file: str = 'winspeech.py'
    hr: str = ''
    related_to: int = 0


class Synthesizing(NamedTuple):
    related_to: int
    ssml: bool
    num_marks: int
    text_length: int


class TrackFailed(NamedTuple):
    related_to: int
    code: str
    hr: str


class PlaybackState(Enum):
    none = auto()
    opening = auto()
    buffering = auto()
    playing = auto()
    paused = auto()


class PlaybackStateChanged(NamedTuple):
    related_to: int
    state: PlaybackState


class MediaState(Enum):
    opened = auto()
    ended = auto()
    failed = auto()


class MediaPlayerError(Enum):
    unknown = auto()
    aborted = auto()
    network_error = auto()
    decoding_error = auto()
    source_not_supported = auto()


class MediaStateChanged(NamedTuple):
    related_to: int
    state: MediaState
    error: str = ""
    code: MediaPlayerError = MediaPlayerError.unknown
    hr: str = ""


class Echo(NamedTuple):
    related_to: int
    msg: str


class Play(NamedTuple):
    related_to: int
    playback_state: PlaybackState


class Pause(NamedTuple):
    related_to: int
    playback_state: PlaybackState


class State(NamedTuple):
    related_to: int
    playback_state: PlaybackState


class VoiceInformation(NamedTuple):
    display_name: str
    description: str
    id: str
    language: str
    gender: str


class DefaultVoice(NamedTuple):
    related_to: int
    voice: VoiceInformation


class Voice(NamedTuple):
    related_to: int
    voice: VoiceInformation
    found: bool = True


class DeviceInformation(NamedTuple):
    id: str
    name: str
    kind: str
    is_default: bool
    is_enabled: bool


class AudioDevice(NamedTuple):
    related_to: int
    device: DeviceInformation
    found: bool = True


class AllVoices(NamedTuple):
    related_to: int
    voices: Tuple[VoiceInformation, ...]


class Volume(NamedTuple):
    related_to: int
    value: float


class Rate(NamedTuple):
    related_to: int
    value: float


class Pitch(NamedTuple):
    related_to: int
    value: float


def parse_message(line):
    parts = line.strip().split(b' ', 2)
    msg_id, msg_type, ans = int(parts[0]), parts[1].decode(), json.loads(parts[2])
    ans['related_to'] = msg_id
    if msg_type == 'cue_entered':
        return CueEntered(**ans)
    if msg_type == 'cue_exited':
        return CueExited(**ans)
    if msg_type == 'mark_reached':
        return MarkReached(**ans)
    if msg_type == 'playback_state_changed':
        ans['state'] = getattr(PlaybackState, ans['state'])
        return PlaybackStateChanged(**ans)
    if msg_type == 'media_state_changed':
        ans['state'] = getattr(MediaState, ans['state'])
        if 'code' in ans:
            ans['code'] = MediaPlayerError(ans['code'])
        return MediaStateChanged(**ans)
    if msg_type == 'error':
        return Error(**ans)
    if msg_type == 'synthesizing':
        return Synthesizing(**ans)
    if msg_type == 'track_failed':
        return TrackFailed(**ans)
    if msg_type == 'saving':
        return Saving(**ans)
    if msg_type == 'saved':
        return Saved(**ans)
    if msg_type == 'echo':
        return Echo(**ans)
    if msg_type == 'play':
        ans['playback_state'] = getattr(PlaybackState, ans['playback_state'])
        return Play(**ans)
    if msg_type == 'pause':
        ans['playback_state'] = getattr(PlaybackState, ans['playback_state'])
        return Pause(**ans)
    if msg_type == 'state':
        ans['playback_state'] = getattr(PlaybackState, ans['playback_state'])
        return State(**ans)
    if msg_type == 'default_voice':
        ans['voice'] = VoiceInformation(**ans['voice'])
        return DefaultVoice(**ans)
    if msg_type == 'all_voices':
        ans['voices'] = tuple(VoiceInformation(**x) for x in ans['voices'])
        return AllVoices(**ans)
    if msg_type == 'all_audio_devices':
        ans['devices'] = tuple(DeviceInformation(**x) for x in ans['devices'])
        return AudioDevice(**ans)
    if msg_type == 'audio_device':
        return AudioDevice(**ans)
    if msg_type == 'voice':
        ans['voice'] = VoiceInformation(**ans['voice'])
        return Voice(**ans)
    if msg_type == 'volume':
        return Volume(**ans)
    if msg_type == 'rate':
        return Rate(**ans)
    if msg_type == 'Pitch':
        return Pitch(**ans)
    return Error(f'Unknown message type: {msg_type}')
# }}}


class WinSpeech:

    def __init__(self):
        self._worker = None
        self.queue = Queue()
        self.msg_id_counter = count()
        next(self.msg_id_counter)

    @property
    def worker(self):
        if self._worker is None:
            self._worker = start_worker()
            Thread(name='WinspeechQueue', target=self._get_messages, args=(self._worker, self.queue), daemon=True).start()
        return self._worker

    def _get_messages(self, worker, queue):
        try:
            for line in worker.stdout:
                queue.put(line.decode('utf-8'))
        except OSError as e:
            line = ('0 error ' + json.dumps({"msg": "Failed to read from worker", "error": str(e), "file": "winspeech.py", "line": 0}))
            queue.put(line)


def develop_loop(*commands):
    p = start_worker()
    q = Queue()

    def echo_output(p):
        for line in p.stdout:
            sys.stdout.buffer.write(b'\x1b[33m' + line + b'\x1b[39m]]'[:-2])
            sys.stdout.buffer.flush()
            q.put(parse_message(line))

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
                        if m.related_to != command:
                            continue
                        if isinstance(m, MediaStateChanged) and m.state in (MediaState.ended, MediaState.failed):
                            break
                        if isinstance(m, Saved):
                            break
                        if isinstance(m, Error):
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


def develop_interactive():
    import subprocess

    from calibre.debug import run_calibre_debug
    print('\x1b[32mInteractive winspeech', '\x1b[39m]]'[:-2], flush=True)
    p = run_calibre_debug('-c', 'from calibre_extensions.winspeech import run_main_loop; raise SystemExit(run_main_loop())',
                          stdin=subprocess.PIPE)
    try:
        while True:
            line = input()
            if p.poll() is not None:
                raise SystemExit(p.returncode)
            p.stdin.write((line + '\n').encode())
            p.stdin.flush()
    except KeyboardInterrupt:
        print('Exiting on interrupt', flush=True)
    finally:
        if p.poll() is None:
            p.kill()
