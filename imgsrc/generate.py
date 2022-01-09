#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import os, glob, subprocess, argparse, json, hashlib

duplicates = {
    'character-set': ['languages'],
    'calibre': ['library', 'lt'],
    'format-text-color': ['lookfeel'],
    'books_in_series': ['series'],
    'plugins.svg': ['plugins/plugin_upgrade_ok'],
}

sizes = {
    'lt': '256',
    'library': '1024',
    'default_cover': 'original',
    'viewer': '256',
    'tweak': '256',
}

skip = {'calibre'}

j = os.path.join
base = os.path.dirname(os.path.abspath(__file__))
output_base = j(os.path.dirname(base), 'resources', 'images')
dark_output_base = j(os.path.dirname(output_base), 'icon-themes', 'calibre-default-dark', 'base')
light_output_base = j(os.path.dirname(output_base), 'icon-themes', 'calibre-default-light', 'base')
hash_path = j(os.path.dirname(base), '.build-cache', 'imgsrc-gen.json')
if os.path.exists(hash_path):
    with open(hash_path, 'rb') as f:
        hashes = json.load(f)
else:
    hashes = {}
src_hashes = {}


def iterfiles(only=()):
    for src in glob.glob(j(base, '*.svg')) + glob.glob(j(base, 'plugins/*.svg')):
        name = os.path.relpath(src, base).rpartition('.')[0]
        if only and name not in only:
            continue
        src_hashes[name] = h = hashlib.sha1(open(src, 'rb').read()).hexdigest()
        if not only and h == hashes.get(name):
            continue
        output_names = [n for n in [name] + duplicates.get(name, []) if n not in skip]
        obase = output_base
        if name.endswith('-for-dark-theme'):
            obase = dark_output_base
        elif name.endswith('-for-light-theme'):
            obase = light_output_base
        output_files = [j(obase, n) + '.png' for n in output_names]
        if output_files:
            yield src, output_files


def rsvg(src, size, dest):
    cmd = ['rsvg-convert', '-d', '96', '-p', '96']
    if size != 'original':
        cmd += ['--width', size, '--height', size]
    subprocess.check_call(cmd + ['-o', dest, src])
    subprocess.check_call(['optipng', '-o7', '-quiet', '-strip', 'all', dest])


def render(src, output_files):
    for dest in output_files:
        oname = os.path.basename(dest).rpartition('.')[0]
        size = sizes.get(oname, '128')
        print('Rendering', oname, 'at size:', size)
        rsvg(src, size, dest)
        name = os.path.relpath(src, base).rpartition('.')[0]
        hashes[name] = src_hashes[name]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('only', nargs='*', default=[], help='Only render the specified icons')
    args = p.parse_args()
    for src, ofiles in iterfiles(args.only):
        render(src, ofiles)
    with open(hash_path, 'w') as f:
        json.dump(hashes, f, indent=2, sort_keys=True)


if __name__ == '__main__':
    main()
