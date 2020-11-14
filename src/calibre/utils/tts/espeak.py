#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

def info():
    from calibre_extensions.espeak import info
    return info()


def create_recording_wav(text, seekable_file_object_or_path, buflength=0, ssml=False, phonemes=False, endpause=False):
    import struct

    from calibre_extensions.espeak import (
        ENDPAUSE, PHONEMES, SSML, create_recording_wav as doit
    )
    flags = 0
    if ssml:
        flags |= SSML
    if phonemes:
        flags |= PHONEMES
    if endpause:
        flags |= ENDPAUSE
    if isinstance(seekable_file_object_or_path, str):
        seekable_file_object = open(seekable_file_object_or_path, 'w+b')
    else:
        seekable_file_object = seekable_file_object_or_path

    w = seekable_file_object.write

    def write(data):
        w(data)
        return False

    doit(text, write, buflength, flags)
    sz = seekable_file_object.tell()
    seekable_file_object.seek(4)
    seekable_file_object.write(struct.pack('<I', sz - 8))
    seekable_file_object.seek(40)
    seekable_file_object.write(struct.pack('<I', sz - 44))
