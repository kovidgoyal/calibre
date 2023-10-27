#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import ctypes.wintypes
import os
import re
import subprocess
import sys
from functools import lru_cache
from glob import glob

CSIDL_PROGRAM_FILES = 38
CSIDL_PROGRAM_FILESX86 = 42


@lru_cache()
def get_program_files_location(which=CSIDL_PROGRAM_FILESX86):
    SHGFP_TYPE_CURRENT = 0
    buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(
        0, which, 0, SHGFP_TYPE_CURRENT, buf)
    return buf.value


@lru_cache()
def find_vswhere():
    for which in (CSIDL_PROGRAM_FILESX86, CSIDL_PROGRAM_FILES):
        root = get_program_files_location(which)
        vswhere = os.path.join(root, "Microsoft Visual Studio", "Installer",
                               "vswhere.exe")
        if os.path.exists(vswhere):
            return vswhere
    raise SystemExit('Could not find vswhere.exe')


def get_output(*cmd):
    return subprocess.check_output(cmd, encoding='mbcs', errors='strict')


@lru_cache()
def find_visual_studio():
    path = get_output(
        find_vswhere(),
        "-latest",
        "-requires",
        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
        "-property",
        "installationPath",
        "-products",
        "*"
    ).strip()
    return os.path.join(path, "VC", "Auxiliary", "Build")


@lru_cache()
def find_msbuild():
    base_path = get_output(
        find_vswhere(),
        "-latest",
        "-requires", "Microsoft.Component.MSBuild",
        "-property", 'installationPath'
    ).strip()
    return glob(os.path.join(
        base_path, 'MSBuild', '*', 'Bin', 'MSBuild.exe'))[0]


def find_vcvarsall():
    productdir = find_visual_studio()
    vcvarsall = os.path.join(productdir, "vcvarsall.bat")
    if os.path.isfile(vcvarsall):
        return vcvarsall
    raise SystemExit("Unable to find vcvarsall.bat in productdir: " +
                     productdir)


def remove_dups(variable):
    old_list = variable.split(os.pathsep)
    new_list = []
    for i in old_list:
        if i not in new_list:
            new_list.append(i)
    return os.pathsep.join(new_list)


def query_process(cmd, is64bit):
    if is64bit and 'PROGRAMFILES(x86)' not in os.environ:
        os.environ['PROGRAMFILES(x86)'] = get_program_files_location()
    result = {}
    popen = subprocess.Popen(cmd,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    try:
        stdout, stderr = popen.communicate()
        if popen.wait() != 0:
            raise RuntimeError(stderr.decode("mbcs"))

        stdout = stdout.decode("mbcs")
        for line in stdout.splitlines():
            if '=' not in line:
                continue
            line = line.strip()
            key, value = line.split('=', 1)
            key = key.lower()
            if key == 'path':
                if value.endswith(os.pathsep):
                    value = value[:-1]
                value = remove_dups(value)
            result[key] = value

    finally:
        popen.stdout.close()
        popen.stderr.close()
    return result


@lru_cache()
def query_vcvarsall(is64bit=True):
    plat = 'amd64' if is64bit else 'amd64_x86'
    vcvarsall = find_vcvarsall()
    env = query_process(f'"{vcvarsall}" {plat} & set', is64bit)
    pat = re.compile('vs(\d+)comntools', re.I)

    comn_tools = {}

    for k in env:
        m = pat.match(k)
        if m is not None:
            comn_tools[k] = int(m.group(1))
    comntools = sorted(comn_tools, key=comn_tools.__getitem__)[-1]


    def g(k):
        try:
            return env[k]
        except KeyError:
            try:
                return env[k.lower()]
            except KeyError:
                for k, v in env.items():
                    print(f'{k}={v}', file=sys.stderr)
                raise

    return {
        k: g(k)
        for k in (
            'PATH LIB INCLUDE LIBPATH WINDOWSSDKDIR'
            f' {comntools} PLATFORM'
            ' UCRTVERSION UNIVERSALCRTSDKDIR VCTOOLSVERSION WINDOWSSDKDIR'
            ' WINDOWSSDKVERSION WINDOWSSDKVERBINPATH WINDOWSSDKBINPATH'
            ' VISUALSTUDIOVERSION VSCMD_ARG_HOST_ARCH VSCMD_ARG_TGT_ARCH'
        ).split()
    }
