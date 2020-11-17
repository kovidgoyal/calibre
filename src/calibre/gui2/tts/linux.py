#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

import atexit
from .errors import TTSSystemUnavailable


def get_client():
    client = getattr(get_client, 'ans', None)
    if client is not None:
        return client
    from speechd.client import SSIPClient, SpawnError
    try:
        client = get_client.ans = SSIPClient('calibre')
    except SpawnError as err:
        raise TTSSystemUnavailable(_('Could not find speech-dispatcher on your system. Please install it.'), str(err))
    atexit.register(client.close)
    return client


def speak_simple_text(text):
    client = get_client()
    from speechd.client import SSIPCommunicationError
    try:
        client.speak(text)
    except SSIPCommunicationError:
        get_client.ans = None
        client = get_client()
        client.speak(text)
