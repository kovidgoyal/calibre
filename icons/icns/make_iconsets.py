#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from copy import deepcopy

d, j, a = (getattr(os.path, x) for x in ('dirname', 'join', 'abspath'))
base = d(a(__file__))

# To generate this template create an icon using Icon Composer on macOS and in
# the saved .icon (which is a folder) look for icon.js
icon_settings = {
  'fill-specializations' : [
    {
      'value' : {
        'automatic-gradient' : 'extended-gray:1.00000,1.00000'
      }
    },
    {
      'appearance' : 'dark',
      'value' : {
        'automatic-gradient' : 'display-p3:0.20500,0.20500,0.20500,1.00000'
      }
    }
  ],
  'groups' : [
    {
      'layers' : [
        {
          'blend-mode' : 'normal',
          'glass' : False,
          'hidden' : False,
          'image-name' : 'icon.svg',
          'name' : 'icon',
          'opacity' : 1,
          'position' : {
            'scale' : 0.9,
            'translation-in-points' : [
              0,
              0
            ]
          }
        }
      ],
      'shadow' : {
        'kind' : 'neutral',
        'opacity' : 0.5
      },
      'translucency' : {
        'enabled' : True,
        'value' : 0.5
      }
    }
  ],
  'supported-platforms' : {
    'circles' : [
      'watchOS'
    ],
    'squares' : 'shared'
  }
}

imgsrc = j(d(d(base)), 'imgsrc')
sources = {
    'calibre':j(imgsrc, 'calibre.svg'),
    'ebook-edit':j(imgsrc, 'tweak.svg'),
    'ebook-viewer':j(imgsrc, 'viewer.svg'),
    'book':j(imgsrc, 'book.svg')
}

frames = {
    'light': j(imgsrc, 'frame.svg'),
    'dark': j(imgsrc, 'frame-dark.svg'),
}


def get_svg_viewbox(file_path: str) -> tuple[float, ...]:
    tree = ET.parse(file_path)
    root = tree.getroot()
    viewbox = root.get('viewBox')
    if viewbox:
        return tuple(float(x) for x in viewbox.split())
    width = root.get('width')
    height = root.get('height')
    return [0.0, 0.0, float(width or 0), float(height or 0)]


def create_icon(name: str, svg_path: str, output_path: str) -> str:
    view_box = get_svg_viewbox(svg_path)
    sz = view_box[-1]
    scale = 0.9 * 1024 / sz
    icon_dir = os.path.join(output_path, f'{name}.icon')
    if os.path.exists(icon_dir):
        shutil.rmtree(icon_dir)
    os.mkdir(icon_dir)
    s = deepcopy(icon_settings)
    for group in s['groups']:
        for layer in group['layers']:
            layer['image-name'] = os.path.basename(svg_path)
            layer['name'] = name
            layer['position']['scale'] = scale
    with open(os.path.join(icon_dir, 'icon.json'), 'w') as f:
        json.dump(s, f, indent=2)
    assets_dir = os.path.join(icon_dir, 'Assets')
    os.mkdir(assets_dir)
    shutil.copy(svg_path, assets_dir)
    return icon_dir


def create_assets():
    os.chdir(base)
    actool = [
        'xcrun', 'actool', '--warnings', '--platform', 'macosx', '--compile', '.',
        '--minimum-deployment-target', '15.0', '--output-partial-info-plist', '/dev/stdout',
    ]
    primary = ''
    icons = []
    alternates = []
    for name, svg in sources.items():
        if not primary:
            primary = name
        icons.append(create_icon(name, svg, os.getcwd()))
        if name != primary:
            alternates.extend(('--alternate-app-icon', name))
            # Generate .icns for backwards compat
            subprocess.check_call(actool + ['--app-icon', name, icons[-1]])
            os.remove('Assets.car')
    subprocess.check_call([
        'xcrun', 'actool', '--warnings', '--platform', 'macosx', '--compile', '.',
        '--minimum-deployment-target', '15.0', '--output-partial-info-plist', '/dev/stdout',
        '--app-icon', primary] + alternates + icons)
    for x in icons:
        shutil.rmtree(x)


def main():
    if 'darwin' in sys.platform.lower():
        create_assets()
    else:
        subprocess.check_call(['ssh', 'ox', 'sh', '-c', '~/bin/update-calibre && python3 ~/calibre-src/icons/icns/make_iconsets.py'])
        subprocess.check_call(['rsync', '-avz', '--include=*.icns', '--include=*.car', '--exclude=*', 'ox:~/calibre-src/icons/icns/', base + '/'])


if __name__ == '__main__':
    main()
