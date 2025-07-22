#!/usr/bin/env python
# License: GPLv3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os
from contextlib import suppress

from setup.revendor import ReVendor


class PiperVoices(ReVendor):

    description = 'Download the list of Piper voices'
    NAME = 'piper_voices'
    TAR_NAME = 'piper voice list'
    VERSION = 'main'
    DOWNLOAD_URL = f'https://huggingface.co/rhasspy/piper-voices/raw/{VERSION}/voices.json'
    CAN_USE_SYSTEM_VERSION = False

    @property
    def output_file_path(self) -> str:
        return os.path.join(self.RESOURCES, 'piper-voices.json')

    def run(self, opts):
        url = opts.path_to_piper_voices
        if url:
            with open(opts.path_to_piper_voices) as f:
                src = f.read()
        else:
            url = opts.piper_voices_url
            src = self.download_securely(url).decode('utf-8')
        data = json.loads(src)
        lang_map = {}
        for voice in data.values():
            language_code = voice['language']['code']
            lang_entry = lang_map.setdefault(language_code, {})
            voice_entry = lang_entry.setdefault(voice['name'], {})
            quality_entry = voice_entry.setdefault(voice['quality'], {})
            for f, metadata in voice['files'].items():
                if f.endswith('.json'):
                    key = 'config'
                elif f.endswith('.onnx'):
                    key = 'model'
                else:
                    key = 'card'
                quality_entry[key] = 'https://huggingface.co/rhasspy/piper-voices/resolve/main/' + f
        if not lang_map:
            raise SystemExit(f'Failed to read any piper voices from: {url}')
        if 'en_US' not in lang_map:
            raise SystemExit(f'Failed to read en_US piper voices from: {url}')
        with open(self.output_file_path, 'w') as f:
            json.dump({'version': 1, 'lang_map': lang_map}, f, indent=2, sort_keys=False)

    def clean(self):
        with suppress(FileNotFoundError):
            os.remove(self.output_file_path)
