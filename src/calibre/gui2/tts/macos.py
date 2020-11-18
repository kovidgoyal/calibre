#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>


class Client:

    def __init__(self):
        from calibre_extensions.cocoa import NSSpeechSynthesizer
        self.nsss = NSSpeechSynthesizer()

    def __del__(self):
        self.nsss = None

    def speak_simple_text(self, text):
        self.nsss.speak(text)
