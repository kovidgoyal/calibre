#!/usr/bin/env python
# License: GPLv3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os
import re
from contextlib import suppress

from setup.revendor import ReVendor


class PiperVoices(ReVendor):

    description = 'Download the list of Piper voices'
    NAME = 'piper_voices'
    TAR_NAME = 'piper voice list'
    VERSION = 'master'
    DOWNLOAD_URL = f'https://raw.githubusercontent.com/rhasspy/piper/{VERSION}/VOICES.md'
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
        lang_map = {}
        current_lang = current_voice = ''
        lang_pat = re.compile(r'\((.+?)\)')
        model_pat = re.compile(r'\[model\]\((.+?)\)')
        config_pat = re.compile(r'\[config\]\((.+?)\)')
        for line in src.splitlines():
            if line.startswith('* '):
                if m := lang_pat.search(line):
                    current_lang = m.group(1).partition(',')[0].replace('`', '')
                    lang_map[current_lang] = {}
                    current_voice = ''
            else:
                line = line.strip()
                if not line.startswith('*'):
                    continue
                if '[model]' in line:
                    if current_lang and current_voice:
                        qual_map = lang_map[current_lang][current_voice]
                        quality = line.partition('-')[0].strip().lstrip('*').strip()
                        model = config = ''
                        if m := model_pat.search(line):
                            model = m.group(1)
                        if m := config_pat.search(line):
                            config = m.group(1)
                        if not quality or not model or not config:
                            raise SystemExit('Failed to parse piper voice model definition from:\n' + line)
                        qual_map[quality] = {'model': model, 'config': config}
                else:
                    current_voice = line.partition(' ')[-1].strip()
                    lang_map[current_lang][current_voice] = {}
        if not lang_map:
            raise SystemExit(f'Failed to read any piper voices from: {url}')
        if 'en_US' not in lang_map:
            raise SystemExit(f'Failed to read en_US piper voices from: {url}')
        with open(self.output_file_path, 'w') as f:
            json.dump({'version': 1, 'lang_map': lang_map}, f, indent=2, sort_keys=False)

    def clean(self):
        with suppress(FileNotFoundError):
            os.remove(self.output_file_path)
