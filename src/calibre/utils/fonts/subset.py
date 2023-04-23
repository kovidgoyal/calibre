#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import sys, os
from fontTools.subset import Subsetter, load_font, save_font


def subset(input_file_object_or_path, output_file_object_or_path, container_type, chars_or_text=''):
    s = Subsetter()
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


if __name__ == '__main__':
    import tempfile
    src = sys.argv[-1]
    with open(os.path.join(tempfile.gettempdir(), os.path.basename(src)), 'wb') as output:
        subset(src, output, os.path.splitext(sys.argv[-1])[1][1:], 'abcdefghijk')
    a, b = os.path.getsize(src), os.path.getsize(output.name)
    print(f'Input: {a} Output: {b}')
    print('Written to:', output.name)
