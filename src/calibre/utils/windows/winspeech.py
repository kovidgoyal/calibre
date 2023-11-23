#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>


import json
import os
import struct
import sys
from contextlib import closing, suppress
from enum import Enum, auto
from itertools import count
from queue import Empty, Queue
from threading import Thread
from time import monotonic
from typing import NamedTuple, Tuple, Optional

from calibre.constants import DEBUG
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


class SpeechError(OSError):

    def __init__(self, err, msg=''):
        val = 'There was an error in the Windows Speech subsystem. '
        if msg:
            val += f'{msg}. '
        val += err.msg + ': ' + err.error + f'\nFile: {err.file} Line: {err.line}'
        if err.hr:
            # List of mediaserver errors is here: https://www.hresult.info/FACILITY_MEDIASERVER
            val += f' HRESULT: 0x{err.hr:x}'
        super().__init__(val)


class NoAudioDevices(OSError):
    display_to_user = True
    def __init__(self):
        super().__init__(_('No active audio output devices found.'
                           ' Connect headphones or speakers. If you are using Remote Desktop then enable Remote Audio for it.'))


class NoMediaPack(OSError):
    display_to_user = True

    def __init__(self):
        super().__init__(_('This computer is missing the Windows MediaPack, or the DLLs are corrupted. This is needed for Read aloud. Instructions'
                           ' for installing it are available at {}').format(

            'https://support.medal.tv/support/solutions/articles/48001157311-windows-is-missing-media-pack'))


class Error(NamedTuple):
    msg: str
    error: str = ''
    line: int = 0
    file: str = 'winspeech.py'
    hr: str = 0
    related_to: int = 0

    def as_exception(self, msg='', check_for_no_audio_devices=False):
        from calibre_extensions.winspeech import INITIALIZE_FAILURE_MESSAGE
        if check_for_no_audio_devices and self.hr == 0xc00d36fa:
            return NoAudioDevices()
        if check_for_no_audio_devices and self.hr == 0x80070002 and self.msg == INITIALIZE_FAILURE_MESSAGE:
            return NoMediaPack()
        return SpeechError(self, msg)


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
    hr: int = 0

    def as_exception(self):
        err = Error("Playback of speech stream failed", self.error + f' ({self.code})', hr=self.hr)
        return err.as_exception(check_for_no_audio_devices=True)


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
    voice: Optional[VoiceInformation]
    found: bool = True


class DeviceInformation(NamedTuple):
    id: str
    name: str
    kind: str
    is_default: bool
    is_enabled: bool

    def spec(self) -> Tuple[str, str]:
        return self.kind, self.id


class AudioDevice(NamedTuple):
    related_to: int
    device: Optional[DeviceInformation]
    found: bool = True


class AllAudioDevices(NamedTuple):
    related_to: int
    devices: Tuple[DeviceInformation, ...]


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
            ans['code'] = getattr(MediaPlayerError, ans['code'])
        if 'hr' in ans:
            ans['hr'] = int(ans['hr'], 16)
        return MediaStateChanged(**ans)
    if msg_type == 'error':
        if 'hr' in ans:
            ans['hr'] = int(ans['hr'], 16)
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
        return AllAudioDevices(**ans)
    if msg_type == 'audio_device':
        if ans['device']:
            ans['device'] = DeviceInformation(**ans['device'])
        else:
            ans['device'] = None
        return AudioDevice(**ans)
    if msg_type == 'voice':
        if ans['voice']:
            ans['voice'] = VoiceInformation(**ans['voice'])
        else:
            ans['voice'] = None
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

    def __init__(self, event_dispatcher=print):
        self._worker = None
        self.queue = Queue()
        self.msg_id_counter = count()
        next(self.msg_id_counter)
        self.pending_messages = []
        self.current_speak_cmd_id = 0
        self.waiting_for = -1
        self.event_dispatcher = event_dispatcher

    @property
    def worker(self):
        if self._worker is None:
            self._worker = start_worker()
            Thread(name='WinspeechQueue', target=self._get_messages, args=(self._worker, self.queue), daemon=True).start()
        return self._worker

    def __del__(self):
        if self._worker is not None:
            self.send_command('exit')
            with suppress(Exception):
                self._worker.wait(0.3)
            if self._worker.poll() is None:
                self._worker.kill()
            self._worker = None
    shutdown = __del__

    def _get_messages(self, worker, queue):
        def send_msg(msg):
            if self.waiting_for == msg.related_to:
                self.queue.put(msg)
            else:
                self.dispatch_message(msg)
        try:
            for line in worker.stdout:
                line = line.strip()
                if DEBUG:
                    with suppress(Exception):
                        print('winspeech:\x1b[32m<-\x1b[39m', line.decode('utf-8', 'replace'), flush=True)
                send_msg(parse_message(line))
        except OSError as e:
            send_msg(Error('Failed to read from worker', str(e)))
        except Exception as e:
            send_msg(Error('Failed to parse message from worker', str(e)))

    def send_command(self, cmd):
        cmd_id = next(self.msg_id_counter)
        w = self.worker
        cmd = f'{cmd_id} {cmd}'
        if DEBUG:
            with suppress(Exception):
                print('winspeech:\x1b[31m->\x1b[39m', cmd, flush=True)
        w.stdin.write(f'{cmd}\n'.encode())
        w.stdin.flush()
        return cmd_id

    def wait_for(self, error_msg, *classes, related_to=-1, timeout=4):
        orig, self.waiting_for = self.waiting_for, related_to
        try:
            limit = monotonic() + timeout
            while True:
                left = limit - monotonic()
                if left <= 0:
                    break
                try:
                    x = self.queue.get(True, left)
                except Empty:
                    break
                if (not classes or isinstance(x, *classes)) and (not related_to or x.related_to == related_to):
                    return x
                if isinstance(x, Error) and (not related_to or x.related_to == related_to):
                    raise x.as_exception(error_msg)
            raise TimeoutError('Timed out waiting for: ' + error_msg)
        finally:
            self.waiting_for = orig

    def speak(self, text, is_cued=False, is_xml=False):
        with SharedMemory(size=max_buffer_size(text)) as shm:
            st = 'cued' if is_cued else ('ssml' if is_xml else 'text')
            sz = encode_to_file_object(text, shm)
            self.current_speak_cmd_id = self.send_command(f'speak {st} shm {sz} {shm.name}')
            self.wait_for('speech synthesis to start', Synthesizing, related_to=self.current_speak_cmd_id, timeout=8)
        return self.current_speak_cmd_id

    def dispatch_message(self, x):
        if x.related_to == self.current_speak_cmd_id:
            if isinstance(x, (Error, MediaStateChanged, MarkReached)):
                self.event_dispatcher(x)

    def pause(self):
        self.wait_for('pause', Pause, related_to=self.send_command('pause'))

    def play(self):
        self.wait_for('play', Play, related_to=self.send_command('play'))

    def set_rate(self, val):
        val = float(val)
        self.wait_for('Setting the rate', Rate, related_to=self.send_command(f'rate {val}'))

    def set_voice(self, spec, default_system_voice):
        val = spec or getattr(default_system_voice, 'id', '__default__')
        x = self.wait_for('Setting the voice', Voice, related_to=self.send_command(f'voice {val}'))
        if not x.found:
            raise SpeechError(f'Failed to find the voice: {val}')

    def set_audio_device(self, spec, default_system_audio_device):
        if not spec and not default_system_audio_device:
            return
        if not spec:
            spec = default_system_audio_device.spec()
        x = self.wait_for('Setting the audio device', AudioDevice, related_to=self.send_command(f'audio_device {spec[0]} {spec[1]}'))
        if not x.found:
            raise SpeechError(f'Failed to find the audio device: {spec}')

    def get_audio_device(self):
        return self.wait_for('Audio device', AudioDevice, related_to=self.send_command('audio_device'))

    def default_voice(self):
        return self.wait_for('Default voice', DefaultVoice, related_to=self.send_command('default_voice'))

    def all_voices(self):
        return self.wait_for('All voices', AllVoices, related_to=self.send_command('all_voices'))

    def all_audio_devices(self):
        return self.wait_for('All audio devices', AllAudioDevices, related_to=self.send_command('all_audio_devices'))



# develop {{{
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
# }}}
