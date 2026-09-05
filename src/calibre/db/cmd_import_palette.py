#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os
import sys

from calibre.utils.localization import _

readonly = True  # Bu komut sadece okuma yapar
version = 0
needs_srv_ctx = False  # Sunucu bağlamı gerekli değil
no_remote = True  # Uzak kütüphaneler desteklenmez


def option_parser(get_parser, args):
    parser = get_parser(_('import [options] file.calibre-palette\n\nImport palette colors from a .calibre-palette file'))
    parser.add_option(
        '--force',
        action='store_true',
        default=False,
        help=_('Overwrite existing palette without confirmation')
    )
    return parser


def implementation(db, notify_changes, file_path, force=False):
    """Palette dosyasını içe aktar"""
    if not os.path.exists(file_path):
        raise ValueError(f'File not found: {file_path}')
    
    if not file_path.endswith('.calibre-palette'):
        raise ValueError('File must have .calibre-palette extension')
    
    try:
        with open(file_path, 'rb') as f:
            data = json.loads(f.read())
    except json.JSONDecodeError as e:
        raise ValueError(f'Invalid palette file format: {e}')
    
    # Validate palette data structure
    if not isinstance(data, dict) or 'dark' not in data or 'light' not in data:
        raise ValueError('Palette file must contain "dark" and "light" keys')
    
    from calibre.gui2 import gprefs
    
    # Palettleri kaydet
    dark_palettes = gprefs.get('dark_palettes', {})
    light_palettes = gprefs.get('light_palettes', {})
    
    dark_palettes['imported'] = data['dark']['palette']
    light_palettes['imported'] = data['light']['palette']
    
    with gprefs:
        gprefs['dark_palettes'] = dark_palettes
        gprefs['light_palettes'] = light_palettes
        # Aktif palette olarak ayarla
        gprefs['dark_palette_name'] = 'imported'
        gprefs['light_palette_name'] = 'imported'
    
    return f"Successfully imported palette from {file_path}"


def main(opts, args, dbctx):
    if not args:
        raise SystemExit(_('No palette file specified. Usage: calibredb import-palette file.calibre-palette'))
    
    file_path = os.path.expanduser(args[0])
    result = implementation(None, None, file_path, opts.force)
    print(result)