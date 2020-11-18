#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>


class Client:

    def __init__(self):
        from calibre.utils.windows.winsapi import ISpVoice
        self.sp_voice = ISpVoice()

    def __del__(self):
        self.sp_voice = None

    def speak_simple_text(self, text):
        from calibre_extensions.winsapi import SPF_ASYNC, SPF_PURGEBEFORESPEAK, SPF_IS_NOT_XML
        self.sp_voice.speak(text, SPF_ASYNC | SPF_PURGEBEFORESPEAK | SPF_IS_NOT_XML)
