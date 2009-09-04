#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

def _disable_linecache():
    import linecache
    def fake_getline(*args, **kwargs):
        return ''
    linecache.orig_getline = linecache.getline
    linecache.getline = fake_getline
_disable_linecache()

def _recipes_pil_prescript(plugins):
    from PIL import Image
    import sys
    def init():
        if Image._initialized >= 2:
            return
        for plugin in plugins:
            try:
                __import__(plugin, globals(), locals(), [])
            except ImportError:
                if Image.DEBUG:
                    print 'Image: failed to import'
                    print plugin, ':', sys.exc_info()[1]
        if Image.OPEN or Image.SAVE:
            Image._initialized = 2
    Image.init = init


_recipes_pil_prescript(['Hdf5StubImagePlugin', 'FitsStubImagePlugin', 'SunImagePlugin', 'GbrImagePlugin', 'PngImagePlugin', 'MicImagePlugin', 'FpxImagePlugin', 'PcxImagePlugin', 'ImImagePlugin', 'SpiderImagePlugin', 'PsdImagePlugin', 'BufrStubImagePlugin', 'SgiImagePlugin', 'McIdasImagePlugin', 'XpmImagePlugin', 'BmpImagePlugin', 'TgaImagePlugin', 'PalmImagePlugin', 'XVThumbImagePlugin', 'GribStubImagePlugin', 'ArgImagePlugin', 'PdfImagePlugin', 'ImtImagePlugin', 'GifImagePlugin', 'CurImagePlugin', 'WmfImagePlugin', 'MpegImagePlugin', 'IcoImagePlugin', 'TiffImagePlugin', 'PpmImagePlugin', 'MspImagePlugin', 'EpsImagePlugin', 'JpegImagePlugin', 'PixarImagePlugin', 'PcdImagePlugin', 'IptcImagePlugin', 'XbmImagePlugin', 'DcxImagePlugin', 'IcnsImagePlugin', 'FliImagePlugin'])

def _run():
    global __file__
    import os, sys
    base = os.environ['RESOURCEPATH']

    sys.frozen = 'macosx_app'
    sys.frameworks_dir = os.path.join(os.path.dirname(base), 'Frameworks')
    sys.new_app_bundle = True
    sys.site_packages = os.path.join(base, 'Python', 'site-packages')
    sys.binaries_path = os.path.join(os.path.dirname(base), 'MacOS')
    sys.console_binaries_path = os.path.join(os.path.dirname(base),
        'console.app', 'Contents', 'MacOS')

    exe = os.environ.get('CALIBRE_LAUNCH_MODULE', 'calibre.gui2.main')
    exe = os.path.join(base, 'Python', 'site-packages', *exe.split('.'))
    exe += '.py'
    sys.argv[0] = __file__ = exe
    for arg in list(sys.argv[1:]):
        if arg.startswith('-psn'):
            sys.argv.remove(arg)
    execfile(exe, globals(), globals())

_run()
