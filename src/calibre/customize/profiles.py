# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
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
        self.width_pts = self.width * 72./self.dpi
        self.height_pts = self.height * 72./self.dpi

# Input profiles {{{
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
                    'The 500/505/600/700 etc.')

    screen_size               = (584, 754)
    dpi                       = 168.451
    fbase                     = 12
    fsizes                    = [7.5, 9, 10, 12, 15.5, 20, 22, 24]

class SonyReader300Input(SonyReaderInput):

    name        = 'Sony Reader 300'
    short_name  = 'sony300'
    description = _('This profile is intended for the SONY PRS 300.')

    dpi                       = 200

class SonyReader900Input(SonyReaderInput):

    author      = 'John Schember'
    name        = 'Sony Reader 900'
    short_name  = 'sony900'
    description = _('This profile is intended for the SONY PRS-900.')

    screen_size               = (584, 978)

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

    name        = 'Hanlin V3'
    short_name  = 'hanlinv3'
    description = _('This profile is intended for the Hanlin V3 and its clones.')

    # Screen size is a best guess
    screen_size               = (584, 754)
    dpi                       = 168.451
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

class HanlinV5Input(HanlinV3Input):

    name        = 'Hanlin V5'
    short_name  = 'hanlinv5'
    description = _('This profile is intended for the Hanlin V5 and its clones.')

    # Screen size is a best guess
    screen_size               = (584, 754)
    dpi                       = 200

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

class IRexDR800Input(InputProfile):

    author      = 'Eric Cronin'
    name        = 'IRex Digital Reader 800'
    short_name  = 'irexdr800'
    description = _('This profile is intended for the IRex Digital Reader 800.')

    screen_size               = (768, 1024)
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

input_profiles = [InputProfile, SonyReaderInput, SonyReader300Input,
        SonyReader900Input, MSReaderInput, MobipocketInput, HanlinV3Input,
        HanlinV5Input, CybookG3Input, CybookOpusInput, KindleInput, IlliadInput,
        IRexDR1000Input, IRexDR800Input, NookInput]

input_profiles.sort(cmp=lambda x,y:cmp(x.name.lower(), y.name.lower()))

# }}}

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

    #: The image size for comics
    comic_screen_size = (584, 754)

    #: If True the MOBI renderer on the device supports MOBI indexing
    supports_mobi_indexing = False

    #: If True output should be optimized for a touchscreen interface
    touchscreen = False
    touchscreen_news_css = ''
    #: A list of extra (beyond CSS 2.1) modules supported by the device
    #: Format is a cssutils profile dictionary (see iPad for example)
    extra_css_modules = []
    #: If True, the date is appended to the title of downloaded news
    periodical_date_in_title = True

    #: Characters used in jackets and catalogs
    ratings_char = u'*'
    empty_ratings_char = u' '

    #: Unsupported unicode characters to be replaced during preprocessing
    unsupported_unicode_chars = []

    #: Number of ems that the left margin of a blockquote is rendered as
    mobi_ems_per_blockquote = 1.0

    #: Special periodical formatting needed in EPUB
    epub_periodical_format = None

    @classmethod
    def tags_to_string(cls, tags):
        from xml.sax.saxutils import escape
        return escape(', '.join(tags))

class iPadOutput(OutputProfile):

    name = 'iPad'
    short_name = 'ipad'
    description = _('Intended for the iPad and similar devices with a '
            'resolution of 768x1024')
    screen_size = (768, 1024)
    comic_screen_size = (768, 1024)
    dpi = 132.0
    extra_css_modules = [
        {
            'name':'webkit',
            'props': { '-webkit-border-bottom-left-radius':'{length}',
                '-webkit-border-bottom-right-radius':'{length}',
                '-webkit-border-top-left-radius':'{length}',
                '-webkit-border-top-right-radius':'{length}',
                '-webkit-border-radius': r'{border-width}(\s+{border-width}){0,3}|inherit',
            },
            'macros': {'border-width': '{length}|medium|thick|thin'}
        }
    ]

    ratings_char = u'\u2605'            # filled star
    empty_ratings_char = u'\u2606'      # hollow star

    touchscreen = True
    # touchscreen_news_css {{{
    touchscreen_news_css = u'''
            /* hr used in articles */
            .article_articles_list {
                width:18%;
                }
            .article_link {
                color: #593f29;
                font-style: italic;
                }
            .article_next {
                -webkit-border-top-right-radius:4px;
                -webkit-border-bottom-right-radius:4px;
                font-style: italic;
                width:32%;
                }

            .article_prev {
                -webkit-border-top-left-radius:4px;
                -webkit-border-bottom-left-radius:4px;
                font-style: italic;
                width:32%;
                }
            .article_sections_list {
                width:18%;
                }
            .articles_link {
                font-weight: bold;
                }
            .sections_link {
                font-weight: bold;
                }


            .caption_divider {
                border:#ccc 1px solid;
                }

            .touchscreen_navbar {
                background:#c3bab2;
                border:#ccc 0px solid;
                border-collapse:separate;
                border-spacing:1px;
                margin-left: 5%;
                margin-right: 5%;
                page-break-inside:avoid;
                width: 90%;
                -webkit-border-radius:4px;
                }
            .touchscreen_navbar td {
                background:#fff;
                font-family:Helvetica;
                font-size:80%;
                /* UI touchboxes use 8px padding */
                padding: 6px;
                text-align:center;
                }

            .touchscreen_navbar td a:link {
                color: #593f29;
                text-decoration: none;
                }

            /* Index formatting */
            .publish_date {
                text-align:center;
                }
            .divider {
                border-bottom:1em solid white;
                border-top:1px solid gray;
                }

            hr.caption_divider {
                border-color:black;
                border-style:solid;
                border-width:1px;
                }

            /* Feed summary formatting */
            .article_summary {
                display:inline-block;
                padding-bottom:0.5em;
                }
            .feed {
                font-family:sans-serif;
                font-weight:bold;
                font-size:larger;
                }

            .feed_link {
                font-style: italic;
                }

            .feed_next {
                -webkit-border-top-right-radius:4px;
                -webkit-border-bottom-right-radius:4px;
                font-style: italic;
                width:40%;
                }

            .feed_prev {
                -webkit-border-top-left-radius:4px;
                -webkit-border-bottom-left-radius:4px;
                font-style: italic;
                width:40%;
                }

            .feed_title {
                text-align: center;
                font-size: 160%;
                }

            .feed_up {
                font-weight: bold;
                width:20%;
                }

            .summary_headline {
                font-weight:bold;
                text-align:left;
                }

            .summary_byline {
                text-align:left;
                font-family:monospace;
                }

            .summary_text {
                text-align:left;
                }

        '''
        # }}}

class iPad3Output(iPadOutput):

    screen_size = comic_screen_size = (2048, 1536)
    dpi = 264.0
    name = 'iPad 3'
    short_name = 'ipad3'
    description = _('Intended for the iPad 3 and similar devices with a '
            'resolution of 1536x2048')

class TabletOutput(iPadOutput):
    name = 'Tablet'
    short_name = 'tablet'
    description = _('Intended for generic tablet devices, does no resizing of images')

    screen_size = (10000, 10000)
    comic_screen_size = (10000, 10000)

class SamsungGalaxy(TabletOutput):
    name = 'Samsung Galaxy'
    short_name = 'galaxy'
    description = _('Intended for the Samsung Galaxy and similar tablet devices with '
            'a resolution of 600x1280')
    screen_size = comic_screen_size = (600, 1280)

class NookHD(TabletOutput):
    name = 'Nook HD+'
    short_name = 'nook_hd_plus'
    description = _('Intended for the Nook HD+ and similar tablet devices with '
            'a resolution of 1080x1920')
    screen_size = comic_screen_size = (1280, 1920)

class SonyReaderOutput(OutputProfile):

    name        = 'Sony Reader'
    short_name  = 'sony'
    description = _('This profile is intended for the SONY PRS line. '
                    'The 500/505/600/700 etc.')

    screen_size               = (590, 775)
    dpi                       = 168.451
    fbase                     = 12
    fsizes                    = [7.5, 9, 10, 12, 15.5, 20, 22, 24]
    unsupported_unicode_chars = [u'\u201f', u'\u201b']

    epub_periodical_format = 'sony'
    #periodical_date_in_title = False


class KoboReaderOutput(OutputProfile):

    name = 'Kobo Reader'
    short_name = 'kobo'

    description = _('This profile is intended for the Kobo Reader.')

    screen_size               = (536, 710)
    comic_screen_size         = (536, 710)
    dpi                       = 168.451
    fbase                     = 12
    fsizes                    = [7.5, 9, 10, 12, 15.5, 20, 22, 24]

class SonyReader300Output(SonyReaderOutput):

    author      = 'John Schember'
    name        = 'Sony Reader 300'
    short_name  = 'sony300'
    description = _('This profile is intended for the SONY PRS-300.')

    dpi                       = 200

class SonyReader900Output(SonyReaderOutput):

    author      = 'John Schember'
    name        = 'Sony Reader 900'
    short_name  = 'sony900'
    description = _('This profile is intended for the SONY PRS-900.')

    screen_size               = (600, 999)
    comic_screen_size = screen_size

class GenericEink(SonyReaderOutput):

    name = 'Generic e-ink'
    short_name = 'generic_eink'
    description = _('Suitable for use with any e-ink device')
    epub_periodical_format = None

class GenericEinkLarge(GenericEink):

    name = 'Generic e-ink large'
    short_name = 'generic_eink_large'
    description = _('Suitable for use with any large screen e-ink device')

    screen_size               = (600, 999)
    comic_screen_size = screen_size

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

    name        = 'Hanlin V3'
    short_name  = 'hanlinv3'
    description = _('This profile is intended for the Hanlin V3 and its clones.')

    # Screen size is a best guess
    screen_size               = (584, 754)
    dpi                       = 168.451
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

class HanlinV5Output(HanlinV3Output):

    name        = 'Hanlin V5'
    short_name  = 'hanlinv5'
    description = _('This profile is intended for the Hanlin V5 and its clones.')

    dpi                       = 200

class CybookG3Output(OutputProfile):

    name        = 'Cybook G3'
    short_name  = 'cybookg3'
    description = _('This profile is intended for the Cybook G3.')

    # Screen size is a best guess
    screen_size               = (600, 800)
    comic_screen_size         = (600, 757)
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

    epub_periodical_format = None

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
    periodical_date_in_title = False

    empty_ratings_char = u'\u2606'
    ratings_char = u'\u2605'

    mobi_ems_per_blockquote = 2.0

    @classmethod
    def tags_to_string(cls, tags):
        return u'%s <br/><span style="color:white">%s</span>' % (', '.join(tags),
                'ttt '.join(tags)+'ttt ')

class KindleDXOutput(OutputProfile):

    name        = 'Kindle DX'
    short_name  = 'kindle_dx'
    description = _('This profile is intended for the Amazon Kindle DX.')

    # Screen size is a best guess
    screen_size               = (744, 1022)
    dpi                       = 150.0
    comic_screen_size = (771, 1116)
    #comic_screen_size         = (741, 1022)
    supports_mobi_indexing = True
    periodical_date_in_title = False
    empty_ratings_char = u'\u2606'
    ratings_char = u'\u2605'
    mobi_ems_per_blockquote = 2.0

    @classmethod
    def tags_to_string(cls, tags):
        return u'%s <br/><span style="color: white">%s</span>' % (', '.join(tags),
                'ttt '.join(tags)+'ttt ')

class KindlePaperWhiteOutput(KindleOutput):

    name = 'Kindle PaperWhite'
    short_name = 'kindle_pw'
    description = _('This profile is intended for the Amazon Kindle PaperWhite')

    # Screen size is a best guess
    screen_size               = (658, 940)
    dpi                       = 212.0
    comic_screen_size = screen_size

class KindleFireOutput(KindleDXOutput):

    name = 'Kindle Fire'
    short_name = 'kindle_fire'
    description = _('This profile is intended for the Amazon Kindle Fire.')

    screen_size               = (570, 1016)
    dpi                       = 169.0
    comic_screen_size = (570, 1016)

    @classmethod
    def tags_to_string(cls, tags):
        # The idiotic fire doesn't obey the color:white directive
        from xml.sax.saxutils import escape
        return escape(', '.join(tags))

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

class IRexDR800Output(OutputProfile):

    author      = 'Eric Cronin'
    name        = 'IRex Digital Reader 800'
    short_name  = 'irexdr800'
    description = _('This profile is intended for the IRex Digital Reader 800.')

    # Screen size is a best guess
    screen_size               = (768, 1024)
    comic_screen_size         = (768, 1024)
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
    comic_screen_size         = (584, 730)
    dpi                       = 167
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

class NookColorOutput(NookOutput):
    name = 'Nook Color'
    short_name = 'nook_color'
    description = _('This profile is intended for the B&N Nook Color.')

    screen_size               = (600, 900)
    comic_screen_size         = (594, 900)
    dpi                       = 169

class BambookOutput(OutputProfile):

    author      = 'Li Fanxi'
    name        = 'Sanda Bambook'
    short_name  = 'bambook'
    description = _('This profile is intended for the Sanda Bambook.')

    # Screen size is for full screen display
    screen_size               = (580, 780)
    # Comic size is for normal display
    comic_screen_size         = (540, 700)
    dpi                       = 168.451
    fbase                     = 12
    fsizes                    = [10, 12, 14, 16]

class PocketBook900Output(OutputProfile):

    author = 'Chris Lockfort'
    name = 'PocketBook Pro 900'
    short_name = 'pocketbook_900'
    description = _('This profile is intended for the PocketBook Pro 900 series of devices.')

    screen_size               = (810, 1180)
    dpi                       = 150.0
    comic_screen_size         = screen_size

class PocketBookPro912Output(OutputProfile):

    author = 'Daniele Pizzolli'
    name = 'PocketBook Pro 912'
    short_name = 'pocketbook_pro_912'
    description = _('This profile is intended for the PocketBook Pro 912 series of devices.')

    # According to http://download.pocketbook-int.com/user-guides/E_Ink/912/User_Guide_PocketBook_912(EN).pdf
    screen_size               = (825, 1200)
    dpi                       = 155.0
    comic_screen_size         = screen_size

output_profiles = [OutputProfile, SonyReaderOutput, SonyReader300Output,
        SonyReader900Output, MSReaderOutput, MobipocketOutput, HanlinV3Output,
        HanlinV5Output, CybookG3Output, CybookOpusOutput, KindleOutput,
        iPadOutput, iPad3Output, KoboReaderOutput, TabletOutput, SamsungGalaxy,
        SonyReaderLandscapeOutput, KindleDXOutput, IlliadOutput, NookHD,
        IRexDR1000Output, IRexDR800Output, JetBook5Output, NookOutput,
        BambookOutput, NookColorOutput, PocketBook900Output, PocketBookPro912Output,
        GenericEink, GenericEinkLarge, KindleFireOutput, KindlePaperWhiteOutput]

output_profiles.sort(cmp=lambda x,y:cmp(x.name.lower(), y.name.lower()))
