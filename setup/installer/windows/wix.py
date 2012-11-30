#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, subprocess, sys

from setup import __appname__, __version__, basenames
from setup.build_environment import is64bit

if is64bit:
    WIXP = r'C:\Program Files (x86)\WiX Toolset v3.6'
    UPGRADE_CODE = '5DD881FF-756B-4097-9D82-8C0F11D521EA'
    MINVERHUMAN = 'Windows Vista'
else:
    WIXP = r'C:\Program Files\Windows Installer XML v3.5'
    UPGRADE_CODE = 'BEB2A80D-E902-4DAD-ADF9-8BD2DA42CFE1'
    MINVERHUMAN = 'Windows XP SP3'

CANDLE = WIXP+r'\bin\candle.exe'
LIGHT = WIXP+r'\bin\light.exe'

class WixMixIn:

    def create_installer(self):
        self.installer_dir = self.j(self.src_root, 'build', 'wix')
        if os.path.exists(self.installer_dir):
            shutil.rmtree(self.installer_dir)
        os.makedirs(self.installer_dir)

        template = open(self.j(self.d(__file__), 'wix-template.xml'),
                'rb').read()

        components = self.get_components_from_files()
        wxs = template.format(
            app                = __appname__,
            version            = __version__,
            upgrade_code       = UPGRADE_CODE,
            ProgramFilesFolder = 'ProgramFiles64Folder' if is64bit else 'ProgramFilesFolder',
            x64                = ' 64bit' if is64bit else '',
            minverhuman        = MINVERHUMAN,
            minver             = '600' if is64bit else '501',
            fix_wix = '<Custom Action="OverwriteWixSetDefaultPerMachineFolder" After="WixSetDefaultPerMachineFolder" />' if is64bit else '',
            compression        = self.opts.msi_compression,
            app_components     = components,
            exe_map            = self.smap,
            main_icon          = self.j(self.src_root, 'icons', 'library.ico'),
            web_icon           = self.j(self.src_root, 'icons', 'web.ico'),
        )
        template = open(self.j(self.d(__file__), 'en-us.xml'),
                'rb').read()
        enus = template.format(app=__appname__)


        enusf = self.j(self.installer_dir, 'en-us.wxl')
        wxsf = self.j(self.installer_dir, __appname__+'.wxs')
        with open(wxsf, 'wb') as f:
            f.write(wxs)
        with open(enusf, 'wb') as f:
            f.write(enus)
        wixobj = self.j(self.installer_dir, __appname__+'.wixobj')
        arch = 'x64' if is64bit else 'x86'
        cmd = [CANDLE, '-nologo', '-arch', arch, '-ext', 'WiXUtilExtension', '-o', wixobj, wxsf]
        self.info(*cmd)
        subprocess.check_call(cmd)
        self.installer = self.j(self.src_root, 'dist')
        if not os.path.exists(self.installer):
            os.makedirs(self.installer)
        self.installer = self.j(self.installer, '%s%s-%s.msi' % (__appname__,
            ('-64bit' if is64bit else ''), __version__))
        license = self.j(self.src_root, 'LICENSE.rtf')
        banner  = self.j(self.src_root, 'icons', 'wix-banner.bmp')
        dialog  = self.j(self.src_root, 'icons', 'wix-dialog.bmp')
        cmd = [LIGHT, '-nologo', '-ext', 'WixUIExtension',
                '-cultures:en-us', '-loc', enusf, wixobj,
                '-ext', 'WixUtilExtension',
                '-o', self.installer,
                '-dWixUILicenseRtf='+license,
                '-dWixUIBannerBmp='+banner,
                '-dWixUIDialogBmp='+dialog]
        cmd.append('-sice:ICE60') # No language in dlls warning
        if self.opts.no_ice:
            cmd.append('-sval')
        if self.opts.verbose:
            cmd.append('-v')
        self.info(*cmd)
        subprocess.check_call(cmd)

    def get_components_from_files(self):

        self._file_idc = 0
        self.file_id_map = {}

        def process_dir(path):
            components = []
            for x in os.listdir(path):
                self._file_idc += 1
                f = os.path.join(path, x)
                self.file_id_map[f] = fid = self._file_idc

                if os.path.isdir(f):
                    components.append(
                        '<Directory Id="file_%s" FileSource="%s" Name="%s">' %
                        (self.file_id_map[f], f, x))
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
                    components.append(''.join(c))
            return components

        components = process_dir(os.path.abspath(self.base))
        self.smap = {}
        for x in basenames['gui']:
            self.smap[x] = 'file_%d'%self.file_id_map[self.a(self.j(self.base, x+'.exe'))]

        return '\t\t\t\t'+'\n\t\t\t\t'.join(components)



