#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from itertools import count
import os
import shutil

from bypy.constants import is64bit
from bypy.utils import run

WIXP = r'C:\Program Files (x86)\WiX Toolset v3.14'
if is64bit:
    UPGRADE_CODE = '5DD881FF-756B-4097-9D82-8C0F11D521EA'
else:
    UPGRADE_CODE = 'BEB2A80D-E902-4DAD-ADF9-8BD2DA42CFE1'
calibre_constants = globals()['calibre_constants']

CANDLE = WIXP + r'\bin\candle.exe'
LIGHT = WIXP + r'\bin\light.exe'
j, d, a, b = os.path.join, os.path.dirname, os.path.abspath, os.path.basename


def create_installer(env):
    if os.path.exists(env.installer_dir):
        shutil.rmtree(env.installer_dir)
    os.makedirs(env.installer_dir)

    with open(j(d(__file__), 'wix-template.xml'), 'rb') as f:
        template = f.read().decode('utf-8')

    components, smap = get_components_from_files(env)
    wxs = template.format(
        app=calibre_constants['appname'],
        appfolder='Calibre2' if is64bit else 'Calibre',
        version=calibre_constants['version'],
        upgrade_code=UPGRADE_CODE,
        ProgramFilesFolder='ProgramFiles64Folder' if is64bit else 'ProgramFilesFolder',
        x64=' 64bit' if is64bit else '',
        fix_wix='<Custom Action="OverwriteWixSetDefaultPerMachineFolder" After="WixSetDefaultPerMachineFolder" />' if is64bit else '',
        compression='high',
        app_components=components,
        exe_map=smap,
        main_icon=j(env.src_root, 'icons', 'library.ico'),
        viewer_icon=j(env.src_root, 'icons', 'viewer.ico'),
        editor_icon=j(env.src_root, 'icons', 'ebook-edit.ico'),
        web_icon=j(env.src_root, 'icons', 'web.ico'),
    )
    with open(j(d(__file__), 'en-us.xml'), 'rb') as f:
        template = f.read().decode('utf-8')
    enus = template.format(app=calibre_constants['appname'])

    enusf = j(env.installer_dir, 'en-us.wxl')
    wxsf = j(env.installer_dir, calibre_constants['appname'] + '.wxs')
    with open(wxsf, 'wb') as f:
        f.write(wxs.encode('utf-8'))
    with open(enusf, 'wb') as f:
        f.write(enus.encode('utf-8'))
    wixobj = j(env.installer_dir, calibre_constants['appname'] + '.wixobj')
    arch = 'x64' if is64bit else 'x86'
    cmd = [CANDLE, '-nologo', '-arch', arch, '-ext', 'WiXUtilExtension', '-o', wixobj, wxsf]
    run(*cmd)
    installer = j(env.dist, '%s%s-%s.msi' % (
        calibre_constants['appname'], ('-64bit' if is64bit else ''), calibre_constants['version']))
    license = j(env.src_root, 'LICENSE.rtf')
    banner = j(env.src_root, 'icons', 'wix-banner.bmp')
    dialog = j(env.src_root, 'icons', 'wix-dialog.bmp')
    cmd = [LIGHT, '-nologo', '-ext', 'WixUIExtension',
           '-cultures:en-us', '-loc', enusf, wixobj,
           '-ext', 'WixUtilExtension',
           '-o', installer,
           '-dWixUILicenseRtf=' + license,
           '-dWixUIBannerBmp=' + banner,
           '-dWixUIDialogBmp=' + dialog]
    cmd.extend([
        '-sice:ICE60',  # No language in dlls warning
        '-sice:ICE61',  # Allow upgrading with same version number
        '-sice:ICE40',  # Re-install mode overridden
        '-sice:ICE69',  # Shortcut components are part of a different feature than the files they point to
    ])
    cmd.append('-sval')  # Disable all checks since they fail when running under ssh
    run(*cmd)


def get_components_from_files(env):

    file_idc = count()
    file_id_map = {}

    def process_dir(path):
        components = []
        for x in os.listdir(path):
            f = os.path.join(path, x)
            file_id_map[f] = fid = next(file_idc)

            if os.path.isdir(f):
                components.append(
                    '<Directory Id="file_%s" FileSource="%s" Name="%s">' %
                    (file_id_map[f], f, x))
                c = process_dir(f)
                components.extend(c)
                components.append('</Directory>')
            else:
                checksum = 'Checksum="yes"' if x.endswith('.exe') else ''
                c = [
                    ('<Component Id="component_%s" Feature="MainApplication" '
                        'Guid="*">') % (fid,),
                    ('<File Id="file_%s" Source="%s" Name="%s" ReadOnly="yes" '
                        'KeyPath="yes" %s/>') %
                    (fid, f, x, checksum),
                    '</Component>'
                ]
                if x.endswith('.exe') and not x.startswith('pdf'):
                    # Add the executable to app paths so that users can
                    # launch it from the run dialog even if it is not on
                    # the path. See http://msdn.microsoft.com/en-us/library/windows/desktop/ee872121(v=vs.85).aspx
                    c[-1:-1] = [
                        ('<RegistryValue Root="HKLM" '
                            r'Key="SOFTWARE\Microsoft\Windows\CurrentVersion\App '
                            r'Paths\%s" Value="[#file_%d]" Type="string" />' % (x, fid)),
                        ('<RegistryValue Root="HKLM" '
                            r'Key="SOFTWARE\Microsoft\Windows\CurrentVersion\App '
                            r'Paths\{0}" Name="Path" Value="[APPLICATIONFOLDER]" '
                            'Type="string" />'.format(x)),
                    ]
                components.append('\n'.join(c))
        return components

    components = process_dir(a(env.base))
    smap = {}
    for x in calibre_constants['basenames']['gui']:
        smap[x] = 'file_%d' % file_id_map[a(j(env.base, x + '.exe'))]

    return '\t\t\t\t' + '\n\t\t\t\t'.join(components), smap
