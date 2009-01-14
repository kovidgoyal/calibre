'''
Device profiles.
'''

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

from itertools import izip

FONT_SIZES = [('xx-small', 1),
              ('x-small',  None),
              ('small',    2),
              ('medium',   3),
              ('large',    4),
              ('x-large',  5),
              ('xx-large', 6),
              (None,       7)]


class Profile(object):
    def __init__(self, width, height, dpi, fbase, fsizes):
        self.width = (float(width) / dpi) * 72.
        self.height = (float(height) / dpi) * 72.
        self.dpi = float(dpi)
        self.fbase = float(fbase)
        self.fsizes = []
        for (name, num), size in izip(FONT_SIZES, fsizes):
            self.fsizes.append((name, num, float(size)))
        self.fnames = dict((name, sz) for name, _, sz in self.fsizes if name)
        self.fnums = dict((num, sz) for _, num, sz in self.fsizes if num)


PROFILES = {
    'PRS505':
        Profile(width=584, height=754, dpi=168.451, fbase=12,
                fsizes=[7.5, 9, 10, 12, 15.5, 20, 22, 24]),

    'MSReader':
        Profile(width=480, height=652, dpi=96, fbase=13,
                fsizes=[10, 11, 13, 16, 18, 20, 22, 26]),

    # Not really, but let's pretend
    'Mobipocket':
        Profile(width=600, height=800, dpi=96, fbase=18,
                fsizes=[14, 14, 16, 18, 20, 22, 24, 26]),
    
    # No clue on usable screen size; DPI should be good
    'HanlinV3':
        Profile(width=584, height=754, dpi=168.451, fbase=16,
                fsizes=[12, 12, 14, 16, 18, 21, 24, 28]),

    'CybookG3':
        Profile(width=600, height=800, dpi=168.451, fbase=16,
                fsizes=[12, 12, 14, 16, 18, 21, 24, 28]),

    'Kindle':
        Profile(width=525, height=640, dpi=168.451, fbase=16,
                fsizes=[12, 12, 14, 16, 18, 21, 24, 28]),
    
    'Browser':
        Profile(width=800, height=600, dpi=100.0, fbase=12,
                fsizes=[5, 7, 9, 12, 13.5, 17, 20, 22, 24])
    }


class Context(object):
    PROFILES = PROFILES
    
    def __init__(self, source, dest):
        if source in PROFILES:
            source = PROFILES[source]
        if dest in PROFILES:
            dest = PROFILES[dest]
        self.source = source
        self.dest = dest
