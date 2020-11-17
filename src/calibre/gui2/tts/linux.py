#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from .errors import TTSSystemUnavailable


class Client:

    def __init__(self):
        self.create_ssip_client()

    def create_ssip_client(self):
        from speechd.client import SSIPClient, SpawnError
        try:
            self.ssip_client = SSIPClient('calibre')
        except SpawnError as err:
            raise TTSSystemUnavailable(_('Could not find speech-dispatcher on your system. Please install it.'), str(err))

    def __del__(self):
        self.ssip_client.close()
        del self.ssip_client

    def speak_simple_text(self, text):
        from speechd.client import SSIPCommunicationError
        try:
            self.ssip_client.speak(text)
        except SSIPCommunicationError:
            self.ssip_client.close()
            self.create_ssip_client()
            self.ssip_client.speak(text)
