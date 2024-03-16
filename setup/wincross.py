#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

# See https://github.com/mstorsjo/msvc-wine/blob/master/vsdownload.py and
# https://github.com/Jake-Shadle/xwin/blob/main/src/lib.rs for the basic logic
# used to download and install the needed VisualStudio packages

import argparse
import concurrent.futures
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from functools import partial
from pprint import pprint
from tempfile import TemporaryDirectory
from urllib.parse import unquote
from urllib.request import urlopen
from zipfile import ZipFile


@dataclass
class File:
    filename: str
    url: str
    size: int
    sha256: str

    def __init__(self, pf, filename=''):
        self.filename=filename or pf['fileName']
        self.url=pf['url']
        self.size=pf['size']
        self.sha256=pf['sha256'].lower()


def package_sort_key(p):
    chip = 0 if p.get('chip', '').lower() == 'x64' else 1
    language = 0 if p.get('language', '').lower().startswith('en-') else 1
    return chip, language


def llvm_arch_to_ms_arch(arch):
    return {'x86_64': 'x64', 'aarch64': 'arm64', 'x64': 'x64', 'arm64': 'arm64'}[arch]


class Packages:

    def __init__(self, manifest_raw, crt_variant, arch):
        arch = llvm_arch_to_ms_arch(arch)
        self.manifest = json.loads(manifest_raw)
        self.packages = defaultdict(list)
        self.cabinet_entries = {}
        for p in self.manifest['packages']:
            pid = p['id'].lower()
            self.packages[pid].append(p)
        for v in self.packages.values():
            v.sort(key=package_sort_key)

        build_tools = self.packages[
            'Microsoft.VisualStudio.Product.BuildTools'.lower()][0]
        pat = re.compile(r'Microsoft\.VisualStudio\.Component\.VC\.(.+)\.x86\.x64')
        latest = (0, 0, 0, 0)
        self.crt_version = ''
        for dep in build_tools['dependencies']:
            m = pat.match(dep)
            if m is not None:
                parts = m.group(1).split('.')
                if len(parts) > 1:
                    q = tuple(map(int, parts))
                    if q > latest:
                        self.crt_version = m.group(1)
                        latest = q
        if not self.crt_version:
            raise KeyError('Failed to find CRT version from build tools deps')
        self.files_to_download = []

        def add_package(key):
            p = self.packages.get(key.lower())
            if not p:
                raise KeyError(f'No package named {key} found')
            for pf in p[0]['payloads']:
                self.files_to_download.append(File(pf))

        # CRT headers
        add_package(f"Microsoft.VC.{self.crt_version}.CRT.Headers.base")
        # CRT libs
        prefix = f'Microsoft.VC.{self.crt_version}.CRT.{arch}.'.lower()
        variants = {}
        for pid in self.packages:
            if pid.startswith(prefix):
                parts = pid[len(prefix):].split('.')
                if parts[-1] == 'base':
                    variant = parts[0]
                    if variant not in variants or 'spectre' in parts:
                        # spectre variant contains both spectre and regular libs
                        variants[variant] = pid
        add_package(variants[crt_variant])
        # ATL headers
        add_package(f"Microsoft.VC.{self.crt_version}.ATL.Headers.base")
        # ATL libs
        add_package(f'Microsoft.VC.{self.crt_version}.ATL.{arch}.Spectre.base')
        add_package(f'Microsoft.VC.{self.crt_version}.ATL.{arch}.base')
        # WinSDK
        pat = re.compile(r'Win(\d+)SDK_(\d.+)', re.IGNORECASE)
        latest_sdk = (0, 0, 0)
        self.sdk_version = ''
        sdk_pid = ''
        for pid in self.packages:
            m = pat.match(pid)
            if m is not None:
                ver = tuple(map(int, m.group(2).split('.')))
                if ver > latest_sdk:
                    self.sdk_version = m.group(2)
                    latest_sdk = ver
                    sdk_pid = pid
        if not self.sdk_version:
            raise KeyError('Failed to find SDK package')
        # headers are in x86 package and arch specific package
        for pf in self.packages[sdk_pid][0]['payloads']:
            fname = pf['fileName'].split('\\')[-1]
            if fname.startswith('Windows SDK Desktop Headers '):
                q = fname[len('Windows SDK Desktop Headers '):]
                if q.lower() == 'x86-x86_en-us.msi':
                    self.files_to_download.append(File(
                        pf, filename=f'{sdk_pid}_headers.msi'))
                elif q.lower() == f'{arch}-x86_en-us.msi':
                    self.files_to_download.append(File(
                        pf, filename=f'{sdk_pid}_{arch}_headers.msi'))
            elif fname == 'Windows SDK for Windows Store Apps Headers-x86_en-us.msi':
                self.files_to_download.append(File(
                    pf, filename=f'{sdk_pid}_store_headers.msi'))
            elif fname.startswith('Windows SDK Desktop Libs '):
                q = fname[len('Windows SDK Desktop Libs '):]
                if q == f'{arch}-x86_en-us.msi':
                    self.files_to_download.append(File(
                        pf, filename=f'{sdk_pid}_libs_x64.msi'))
            elif fname == 'Windows SDK for Windows Store Apps Libs-x86_en-us.msi':
                self.files_to_download.append(File(
                    pf, filename=f'{sdk_pid}_store_libs.msi'))
            elif (fl := fname.lower()).endswith('.cab'):
                self.cabinet_entries[fl] = File(pf, filename=fl)
        # UCRT
        for pf in self.packages[
                'Microsoft.Windows.UniversalCRT.HeadersLibsSources.Msi'.lower()][0]['payloads']:
            fname = pf['fileName'].split('\\')[-1]
            if fname == 'Universal CRT Headers Libraries and Sources-x86_en-us.msi':
                self.files_to_download.append(File(pf))
                self.files_to_download[-1].filename = 'ucrt.msi'
            elif (fl := fname.lower()).endswith('.cab'):
                self.cabinet_entries[fl] = File(pf, filename=fl)


def download_item(dest_dir: str, file: File):
    dest = os.path.join(dest_dir, file.filename)
    m = hashlib.sha256()
    with urlopen(file.url) as src, open(dest, 'wb') as d:
        with memoryview(bytearray(shutil.COPY_BUFSIZE)) as buf:
            while True:
                n = src.readinto(buf)
                if not n:
                    break
                elif n < shutil.COPY_BUFSIZE:
                    with buf[:n] as smv:
                        d.write(smv)
                        m.update(smv)
                else:
                    d.write(buf)
                    m.update(buf)
    if m.hexdigest() != file.sha256:
        raise SystemExit(f'The hash for {file.filename} does not match.'
                         f' {m.hexdigest()} != {file.sha256}')

def cabinets_in_msi(path):
    raw = subprocess.check_output(['msiinfo', 'export', path, 'Media']).decode('utf-8')
    return re.findall(r'\S+\.cab', raw)


def download(dest_dir, manifest_version=17, manifest_type='release', manifest_path='', crt_variant='desktop', arch='x86_64'):
    if manifest_path:
        manifest = open(manifest_path, 'rb').read()
    else:
        url = f'https://aka.ms/vs/{manifest_version}/{manifest_type}/channel'
        print('Downloading top-level manifest from', url)
        tm = json.loads(urlopen(url).read())
        print("Got toplevel manifest for", (tm["info"]["productDisplayVersion"]))
        for item in tm["channelItems"]:
            if item.get('type') == "Manifest":
                url = item["payloads"][0]["url"]
                print('Downloading actual manifest...')
                manifest = urlopen(url).read()

    pkgs = Packages(manifest, crt_variant, arch)
    os.makedirs(dest_dir, exist_ok=True)
    total = sum(x.size for x in pkgs.files_to_download)
    print('Downloading', int(total/(1024*1024)), 'MB in', len(pkgs.files_to_download),
          'files...')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for _ in executor.map(partial(download_item, dest_dir), pkgs.files_to_download):
            pass
    cabs = []
    for x in os.listdir(dest_dir):
        if x.lower().endswith('.msi'):
            for cab in cabinets_in_msi(os.path.join(dest_dir, x)):
                cabs.append(pkgs.cabinet_entries[cab])
    total = sum(x.size for x in cabs)
    print('Downloading', int(total/(1024*1024)), 'MB in', len(cabs), 'files...')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for _ in executor.map(partial(download_item, dest_dir), cabs):
            pass


def merge_trees(src, dest):
    if not os.path.isdir(src):
        return
    if not os.path.isdir(dest):
        shutil.move(src, dest)
        return
    destnames = {n.lower():n for n in os.listdir(dest)}
    for d in os.scandir(src):
        n = d.name
        srcname = os.path.join(src, n)
        destname = os.path.join(dest, n)
        if d.is_dir():
            if os.path.isdir(destname):
                merge_trees(srcname, destname)
            elif n.lower() in destnames:
                merge_trees(srcname, os.path.join(dest, destnames[n.lower()]))
            else:
                shutil.move(srcname, destname)
        else:
            shutil.move(srcname, destname)


def extract_msi(path, dest_dir):
    print('Extracting', os.path.basename(path), '...')
    with open(os.path.join(dest_dir, os.path.basename(path) + '.listing'), 'w') as log:
        subprocess.check_call(['msiextract', '-C', dest_dir, path], stdout=log)


def extract_zipfile(zf, dest_dir):
    tmp = os.path.join(dest_dir, "extract")
    os.mkdir(tmp)
    for f in zf.infolist():
        name = unquote(f.filename)
        dest = os.path.join(dest_dir, name)
        extracted = zf.extract(f, tmp)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(extracted, dest)
    shutil.rmtree(tmp)


def extract_vsix(path, dest_dir):
    print('Extracting', os.path.basename(path), '...')
    with TemporaryDirectory(dir=dest_dir) as tdir, ZipFile(path, 'r') as zf:
        extract_zipfile(zf, tdir)
        contents = os.path.join(tdir, "Contents")
        merge_trees(contents, dest_dir)
        names = zf.namelist()
    with open(os.path.join(dest_dir, os.path.basename(path) + '.listing'), 'w') as ls:
        ls.write('\n'.join(names))


def move_unpacked_trees(src_dir, dest_dir):
    # CRT
    crt_src = os.path.dirname(glob.glob(
        os.path.join(src_dir, 'VC/Tools/MSVC/*/include'))[0])
    crt_dest = os.path.join(dest_dir, 'crt')
    os.makedirs(crt_dest)
    merge_trees(os.path.join(crt_src, 'include'), os.path.join(crt_dest, 'include'))
    merge_trees(os.path.join(crt_src, 'lib'), os.path.join(crt_dest, 'lib'))
    merge_trees(os.path.join(crt_src, 'atlmfc', 'include'),
                os.path.join(crt_dest, 'include'))
    merge_trees(os.path.join(crt_src, 'atlmfc', 'lib'),
                os.path.join(crt_dest, 'lib'))

    # SDK
    sdk_ver = glob.glob(os.path.join(src_dir, 'win11sdk_*_headers.msi.listing'))[0]
    sdk_ver = sdk_ver.split('_')[1]
    for x in glob.glob(os.path.join(src_dir, 'Program Files/Windows Kits/*/Include/*')):
        if os.path.basename(x).startswith(sdk_ver):
            sdk_ver = os.path.basename(x)
            break
    else:
        raise SystemExit(f'Failed to find sdk_ver: {sdk_ver}')
    sdk_include_src = glob.glob(os.path.join(
        src_dir, f'Program Files/Windows Kits/*/Include/{sdk_ver}'))[0]
    sdk_dest = os.path.join(dest_dir, 'sdk')
    os.makedirs(sdk_dest)
    merge_trees(sdk_include_src, os.path.join(sdk_dest, 'include'))
    sdk_lib_src = glob.glob(os.path.join(
        src_dir, f'Program Files/Windows Kits/*/Lib/{sdk_ver}'))[0]
    merge_trees(sdk_lib_src, os.path.join(sdk_dest, 'lib'))

    # UCRT
    if os.path.exists(os.path.join(sdk_include_src, 'ucrt')):
        return
    ucrt_include_src = glob.glob(os.path.join(
        src_dir, 'Program Files/Windows Kits/*/Include/*/ucrt'))[0]
    merge_trees(ucrt_include_src, os.path.join(sdk_dest, 'include', 'ucrt'))
    ucrt_lib_src = glob.glob(os.path.join(
        src_dir, 'Program Files/Windows Kits/*/Lib/*/ucrt'))[0]
    merge_trees(ucrt_lib_src, os.path.join(sdk_dest, 'lib', 'ucrt'))


def unpack(src_dir, dest_dir):
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    extract_dir = os.path.join(dest_dir, 'extract')
    os.makedirs(extract_dir)
    for x in os.listdir(src_dir):
        path = os.path.join(src_dir, x)
        ext = os.path.splitext(x)[1].lower()
        if ext =='.msi':
            extract_msi(path, extract_dir)
        elif ext == '.vsix':
            extract_vsix(path, extract_dir)
        elif ext == '.cab':
            continue
        else:
            raise SystemExit(f'Unknown downloaded file type: {x}')
    move_unpacked_trees(extract_dir, dest_dir)
    shutil.rmtree(extract_dir)


def symlink_transformed(path, transform=str.lower):
    base, name = os.path.split(path)
    lname = transform(name)
    if lname != name:
        npath = os.path.join(base, lname)
        if not os.path.lexists(npath):
            os.symlink(name, npath)


def clone_tree(src_dir, dest_dir):
    os.makedirs(dest_dir)
    for dirpath, dirnames, filenames in os.walk(src_dir):
        for d in dirnames:
            path = os.path.join(dirpath, d)
            rpath = os.path.relpath(path, src_dir)
            dpath = os.path.join(dest_dir, rpath)
            os.makedirs(dpath)
            symlink_transformed(dpath)
        for f in filenames:
            if f.lower().endswith('.pdb'):
                continue
            path = os.path.join(dirpath, f)
            rpath = os.path.relpath(path, src_dir)
            dpath = os.path.join(dest_dir, rpath)
            os.link(path, dpath)
            symlink_transformed(dpath)


def files_in(path):
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            yield os.path.relpath(os.path.join(dirpath, f), path)


def create_include_symlinks(path, include_root, include_files):
    ' Create symlinks for include entries in header files whose case does not match '
    with open(path, 'rb') as f:
        src = f.read()
    for m in re.finditer(rb'^#include\s+([<"])(.+?)[>"]', src, flags=re.M):
        spec = m.group(2).decode().replace('\\', '/')
        lspec = spec.lower()
        if spec == lspec:
            continue
        is_local = m.group(1).decode() == '"'
        found = ''
        lmatches = []
        for ir, specs in include_files.items():
            if spec in specs:
                found = ir
                break
            if lspec in specs:
                lmatches.append(ir)

        if found and (not is_local or found == include_root):
            continue
        if lmatches:
            if is_local and include_root in lmatches:
                fr = include_root
            else:
                fr = lmatches[0]
            symlink_transformed(os.path.join(fr, lspec), lambda n: os.path.basename(spec))


def setup(splat_dir, root_dir, arch):
    print('Creating symlinks...')
    msarch = llvm_arch_to_ms_arch(arch)
    if os.path.exists(root_dir):
        shutil.rmtree(root_dir)
    os.makedirs(root_dir)
    # CRT
    clone_tree(os.path.join(splat_dir, 'crt', 'include'), os.path.join(root_dir, 'crt', 'include'))
    clone_tree(os.path.join(splat_dir, 'crt', 'lib', 'spectre', msarch), os.path.join(root_dir, 'crt', 'lib'))
    # SDK
    clone_tree(os.path.join(splat_dir, 'sdk', 'include'), os.path.join(root_dir, 'sdk', 'include'))
    for x in glob.glob(os.path.join(splat_dir, 'sdk', 'lib', '*', msarch)):
        clone_tree(x, os.path.join(root_dir, 'sdk', 'lib', os.path.basename(os.path.dirname(x))))
    include_roots = [x for x in glob.glob(os.path.join(root_dir, 'sdk', 'include', '*')) if os.path.isdir(x)]
    include_roots.append(os.path.join(root_dir, 'crt', 'include'))
    include_files = {x:set(files_in(x)) for x in include_roots}
    for ir, files in include_files.items():
        files_to_check = []
        for relpath in files:
            path = os.path.join(ir, relpath)
            if not os.path.islink(path):
                files_to_check.append(path)
        for path in files_to_check:
            create_include_symlinks(path, ir, include_files)


def main(args=sys.argv[1:]):
    stages = ('download', 'unpack', 'setup')
    p = argparse.ArgumentParser(
        description='Setup the headers and libraries for cross-compilation of windows binaries')
    p.add_argument(
        'stages', metavar='STAGES', nargs='*', help=(
            f'The stages to run by default all stages are run. Stages are: {" ".join(stages)}'))
    p.add_argument(
        '--manifest-version', default=17, type=int, help='The manifest version to use to find the packages to install')
    p.add_argument(
        '--manifest-path', default='', help='Path to a local manifest file to use. Causes --manifest-version to be ignored.')
    p.add_argument(
        '--crt-variant', default='desktop', choices=('desktop', 'store', 'onecore'), help='The type of CRT to download')
    p.add_argument(
        '--arch', default='x86_64', choices=('x86_64', 'aarch64'), help='The architecture to install')
    p.add_argument('--dest', default='.', help='The directory to install into')
    args = p.parse_args(args)
    if args.dest == '.':
        args.dest = os.getcwd()
    stages = args.stages or stages
    dl_dir = os.path.join(args.dest, 'dl')
    splat_dir = os.path.join(args.dest, 'splat')
    root_dir = os.path.join(args.dest, 'root')
    for stage in stages:
        if stage == 'download':
            download(dl_dir, manifest_version=args.manifest_version, manifest_path=args.manifest_path, crt_variant=args.crt_variant, arch=args.arch)
        elif stage == 'unpack':
            unpack(dl_dir, splat_dir)
        elif stage == 'setup':
            setup(splat_dir, root_dir, args.arch)
        else:
            raise SystemExit(f'Unknown stage: {stage}')


if __name__ == '__main__':
    pprint
    main()
