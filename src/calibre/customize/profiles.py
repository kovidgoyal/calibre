from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from itertools import izip

from calibre.customize import Plugin as _Plugin

FONT_SIZES = [('xx-small', 1),
              ('x-small',  None),
              ('small',    2),
              ('medium',   3),
              ('large',    4),
              ('x-large',  5),
              ('xx-large', 6),
              (None,       7)]


class Plugin(_Plugin):

    fbase  = 12
    fsizes = [5, 7, 9, 12, 13.5, 17, 20, 22, 24]
    screen_size = (1600, 1200)
    dpi = 100

    def __init__(self, *args, **kwargs):
        _Plugin.__init__(self, *args, **kwargs)
        self.width, self.height = self.screen_size
        fsizes = list(self.fsizes)
        self.fkey = list(self.fsizes)
        self.fsizes = []
        for (name, num), size in izip(FONT_SIZES, fsizes):
            self.fsizes.append((name, num, float(size)))
        self.fnames = dict((name, sz) for name, _, sz in self.fsizes if name)
        self.fnums = dict((num, sz) for _, num, sz in self.fsizes if num)


class InputProfile(Plugin):

    author = 'Kovid Goyal'
    supported_platforms = set(['windows', 'osx', 'linux'])
    can_be_disabled = False
    type = _('Input profile')

    name        = 'Default Input Profile'
    short_name  = 'default' # Used in the CLI so dont use spaces etc. in it
    description = _('This profile tries to provide sane defaults and is useful '
                    'if you know nothing about the input document.')


class SonyReaderInput(InputProfile):

    name        = 'Sony Reader'
    short_name  = 'sony'
    description = _('This profile is intended for the SONY PRS line. '
                    'The 500/505/700 etc.')

    screen_size               = (584, 754)
    dpi                       = 168.451
    fbase                     = 12
    fsizes                    = [7.5, 9, 10, 12, 15.5, 20, 22, 24]

class SonyReader900Input(InputProfile):

    author      = 'John Schember'
    name        = 'Sony Reader 900'
    short_name  = 'sony'
    description = _('This profile is intended for the SONY PRS-900.')

    screen_size               = (600, 1024)
    dpi                       = 167
    fbase                     = 12
    fsizes                    = [7.5, 9, 10, 12, 15.5, 20, 22, 24]

class MSReaderInput(InputProfile):

    name        = 'Microsoft Reader'
    short_name  = 'msreader'
    description = _('This profile is intended for the Microsoft Reader.')

    screen_size               = (480, 652)
    dpi                       = 96
    fbase                     = 13
    fsizes                    = [10, 11, 13, 16, 18, 20, 22, 26]

class MobipocketInput(InputProfile):

    name        = 'Mobipocket Books'
    short_name  = 'mobipocket'
    description = _('This profile is intended for the Mobipocket books.')

    # Unfortunately MOBI books are not narrowly targeted, so this information is
    # quite likely to be spurious
    screen_size               = (600, 800)
    dpi                       = 96
    fbase                     = 18
    fsizes                    = [14, 14, 16, 18, 20, 22, 24, 26]

class HanlinV3Input(InputProfile):

    name        = 'Hanlin V3/V5'
    short_name  = 'hanlinv3'
    description = _('This profile is intended for the Hanlin V3/V5 and its clones.')

    # Screen size is a best guess
    screen_size               = (584, 754)
    dpi                       = 168.451
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

class CybookG3Input(InputProfile):

    name        = 'Cybook G3'
    short_name  = 'cybookg3'
    description = _('This profile is intended for the Cybook G3.')

    # Screen size is a best guess
    screen_size               = (600, 800)
    dpi                       = 168.451
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

class CybookOpusInput(InputProfile):

    author      = 'John Schember'
    name        = 'Cybook Opus'
    short_name  = 'cybook_opus'
    description = _('This profile is intended for the Cybook Opus.')

    # Screen size is a best guess
    screen_size               = (600, 800)
    dpi                       = 200
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

class KindleInput(InputProfile):

    name        = 'Kindle'
    short_name  = 'kindle'
    description = _('This profile is intended for the Amazon Kindle.')

    # Screen size is a best guess
    screen_size               = (525, 640)
    dpi                       = 168.451
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

class IlliadInput(InputProfile):

    name        = 'Illiad'
    short_name  = 'illiad'
    description = _('This profile is intended for the Irex Illiad.')

    screen_size               = (760, 925)
    dpi                       = 160.0
    fbase                     = 12
    fsizes                    = [7.5, 9, 10, 12, 15.5, 20, 22, 24]

class IRexDR1000Input(InputProfile):

    author      = 'John Schember'
    name        = 'IRex Digital Reader 1000'
    short_name  = 'irexdr1000'
    description = _('This profile is intended for the IRex Digital Reader 1000.')

    # Screen size is a best guess
    screen_size               = (1024, 1280)
    dpi                       = 160
    fbase                     = 16
    fsizes                    = [12, 14, 16, 18, 20, 22, 24]


class NookInput(InputProfile):

    author      = 'John Schember'
    name        = 'Nook'
    short_name  = 'nook'
    description = _('This profile is intended for the B&N Nook.')

    # Screen size is a best guess
    screen_size               = (600, 800)
    dpi                       = 167
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

input_profiles = [InputProfile, SonyReaderInput, SonyReader900Input,
        MSReaderInput, MobipocketInput, HanlinV3Input, CybookG3Input,
        CybookOpusInput, KindleInput, IlliadInput, IRexDR1000Input, NookInput]


class OutputProfile(Plugin):

    author = 'Kovid Goyal'
    supported_platforms = set(['windows', 'osx', 'linux'])
    can_be_disabled = False
    type = _('Output profile')

    name        = 'Default Output Profile'
    short_name  = 'default' # Used in the CLI so dont use spaces etc. in it
    description = _('This profile tries to provide sane defaults and is useful '
                    'if you want to produce a document intended to be read at a '
                    'computer or on a range of devices.')

    # The image size for comics
    comic_screen_size = (584, 754)

    # If True the MOBI renderer on the device supports MOBI indexing
    supports_mobi_indexing = False

    @classmethod
    def tags_to_string(cls, tags):
        return ', '.join(tags)

class SonyReaderOutput(OutputProfile):

    name        = 'Sony Reader'
    short_name  = 'sony'
    description = _('This profile is intended for the SONY PRS line. '
                    'The 500/505/700 etc.')

    screen_size               = (600, 775)
    dpi                       = 168.451
    fbase                     = 12
    fsizes                    = [7.5, 9, 10, 12, 15.5, 20, 22, 24]

class SonyReader900Output(OutputProfile):

    author      = 'John Schember'
    name        = 'Sony Reader 900'
    short_name  = 'sony'
    description = _('This profile is intended for the SONY PRS-900.')

    screen_size               = (600, 1024)
    dpi                       = 167
    fbase                     = 12
    fsizes                    = [7.5, 9, 10, 12, 15.5, 20, 22, 24]

class JetBook5Output(OutputProfile):

    name        = 'JetBook 5-inch'
    short_name  = 'jetbook5'
    description = _('This profile is intended for the 5-inch JetBook.')

    screen_size               = (480, 640)
    dpi                       = 168.451



class SonyReaderLandscapeOutput(SonyReaderOutput):

    name        = 'Sony Reader Landscape'
    short_name  = 'sony-landscape'
    description = _('This profile is intended for the SONY PRS line. '
                    'The 500/505/700 etc, in landscape mode. Mainly useful '
                    'for comics.')

    screen_size               = (784, 1012)
    comic_screen_size         = (784, 1012)


class MSReaderOutput(OutputProfile):

    name        = 'Microsoft Reader'
    short_name  = 'msreader'
    description = _('This profile is intended for the Microsoft Reader.')

    screen_size               = (480, 652)
    dpi                       = 96
    fbase                     = 13
    fsizes                    = [10, 11, 13, 16, 18, 20, 22, 26]

class MobipocketOutput(OutputProfile):

    name        = 'Mobipocket Books'
    short_name  = 'mobipocket'
    description = _('This profile is intended for the Mobipocket books.')

    # Unfortunately MOBI books are not narrowly targeted, so this information is
    # quite likely to be spurious
    screen_size               = (600, 800)
    dpi                       = 96
    fbase                     = 18
    fsizes                    = [14, 14, 16, 18, 20, 22, 24, 26]

class HanlinV3Output(OutputProfile):

    name        = 'Hanlin V3/V5'
    short_name  = 'hanlinv3'
    description = _('This profile is intended for the Hanlin V3/V5 and its clones.')

    # Screen size is a best guess
    screen_size               = (584, 754)
    dpi                       = 168.451
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

class CybookG3Output(OutputProfile):

    name        = 'Cybook G3'
    short_name  = 'cybookg3'
    description = _('This profile is intended for the Cybook G3.')

    # Screen size is a best guess
    screen_size               = (600, 800)
    dpi                       = 168.451
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

class CybookOpusOutput(SonyReaderOutput):

    author      = 'John Schember'
    name        = 'Cybook Opus'
    short_name  = 'cybook_opus'
    description = _('This profile is intended for the Cybook Opus.')

    # Screen size is a best guess
    dpi                       = 200
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

class KindleOutput(OutputProfile):

    name        = 'Kindle'
    short_name  = 'kindle'
    description = _('This profile is intended for the Amazon Kindle.')

    # Screen size is a best guess
    screen_size               = (525, 640)
    dpi                       = 168.451
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]
    supports_mobi_indexing = True

    @classmethod
    def tags_to_string(cls, tags):
        return 'ttt '.join(tags)+'ttt '

class KindleDXOutput(OutputProfile):

    name        = 'Kindle DX'
    short_name  = 'kindle_dx'
    description = _('This profile is intended for the Amazon Kindle DX.')

    # Screen size is a best guess
    screen_size               = (744, 1022)
    dpi                       = 150.0
    comic_screen_size         = (741, 1022)
    supports_mobi_indexing = True

    @classmethod
    def tags_to_string(cls, tags):
        return 'ttt '.join(tags)+'ttt '

class IlliadOutput(OutputProfile):

    name        = 'Illiad'
    short_name  = 'illiad'
    description = _('This profile is intended for the Irex Illiad.')

    screen_size               = (760, 925)
    comic_screen_size         = (760, 925)
    dpi                       = 160.0
    fbase                     = 12
    fsizes                    = [7.5, 9, 10, 12, 15.5, 20, 22, 24]

class IRexDR1000Output(OutputProfile):

    author      = 'John Schember'
    name        = 'IRex Digital Reader 1000'
    short_name  = 'irexdr1000'
    description = _('This profile is intended for the IRex Digital Reader 1000.')

    # Screen size is a best guess
    screen_size               = (1024, 1280)
    comic_screen_size         = (996, 1241)
    dpi                       = 160
    fbase                     = 16
    fsizes                    = [12, 14, 16, 18, 20, 22, 24]

class NookOutput(OutputProfile):

    author      = 'John Schember'
    name        = 'Nook'
    short_name  = 'nook'
    description = _('This profile is intended for the B&N Nook.')

    # Screen size is a best guess
    screen_size               = (600, 730)
    dpi                       = 167
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

output_profiles = [OutputProfile, SonyReaderOutput, SonyReader900Output,
        MSReaderOutput, MobipocketOutput, HanlinV3Output, CybookG3Output,
        CybookOpusOutput, KindleOutput, SonyReaderLandscapeOutput,
        KindleDXOutput, IlliadOutput, IRexDR1000Output, JetBook5Output,
        NookOutput]
