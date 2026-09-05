#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os

from calibre.utils.localization import _

readonly = True
version = 0
needs_srv_ctx = False
no_remote = True


def option_parser(get_parser, args):
    parser = get_parser(_('export [options] output_file.calibre-palette\n\nExport current palette colors to a .calibre-palette file'))
    return parser


def main(opts, args, dbctx):
    if not args:
        raise SystemExit(_('No output file specified. Usage: calibredb export-palette output.calibre-palette'))
    
    output_file = os.path.expanduser(args[0])
    
    from calibre.gui2 import gprefs
    from calibre.gui2.palette import dark_palette, light_palette
    
    # Mevcut palettleri al
    dp = dark_palette()
    lp = light_palette()
    
    # Serialize et
    from calibre.gui2.palette import serialize_palette_as_python
    
    data = {
        'dark': {
            'use_custom': bool(gprefs.get('dark_palette_name')),
            'palette': gprefs.get('dark_palettes', {}).get('__current__', {})
        },
        'light': {
            'use_custom': bool(gprefs.get('light_palette_name')),
            'palette': gprefs.get('light_palettes', {}).get('__current__', {})
        }
    }
    
    with open(output_file, 'wb') as f:
        f.write(json.dumps(data, indent=2, sort_keys=True).encode('utf-8'))
    
    print(f"Successfully exported palette to {output_file}")