#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import os
import sys
from logging.handlers import QueueHandler
from queue import Empty, SimpleQueue



def subset(input_file_object_or_path, output_file_object_or_path, container_type, chars_or_text=''):
    from fontTools.subset import Subsetter, load_font, log, save_font
    log_messages = SimpleQueue()
    log_handler = QueueHandler(log_messages)
    log.addHandler(log_handler)
    try:
        s = Subsetter()
        s.options.layout_features.append('*')
        s.options.recommended_glyphs = True
        container_type = container_type.lower()
        if 'woff' in container_type:
            s.options.flavor = 'woff2'
        font = load_font(input_file_object_or_path, s.options, dontLoadGlyphNames=False)
        unicodes = {ord(x) for x in chars_or_text}
        unicodes.add(ord(' '))
        s.populate(unicodes=unicodes)
        s.subset(font)
        save_font(font, output_file_object_or_path, s.options)
    finally:
        log.removeHandler(log_handler)
    msgs = []
    while True:
        try:
            msgs.append(log_messages.get_nowait().getMessage())
        except Empty:
            break
    return msgs


if __name__ == '__main__':
    import tempfile
    src = sys.argv[-1]
    with open(os.path.join(tempfile.gettempdir(), os.path.basename(src)), 'wb') as output:
        print('\n'.join(subset(src, output, os.path.splitext(sys.argv[-1])[1][1:], 'abcdefghijk')))
    a, b = os.path.getsize(src), os.path.getsize(output.name)
    print(f'Input: {a} Output: {b}')
    print('Written to:', output.name)
