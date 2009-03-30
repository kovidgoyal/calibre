from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, re
from calibre.customize import Plugin

class InputProfile(Plugin):

    author = 'Kovid Goyal'
    supported_platforms = set(['windows', 'osx', 'linux'])
    can_be_disabled = False
    type = _('Input profile')

# TODO: Add some real information to this profile. All other profiles must
#       inherit from this profile and override as needed

    name        = 'Default Input Profile'
    short_name  = 'default' # Used in the CLI so dont use spaces etc. in it
    description = _('This profile tries to provide sane defaults and is useful '
                    'if you know nothing about the input document.')

input_profiles = [InputProfile]


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

    epub_flow_size            = sys.maxint
    screen_size               = None
    remove_special_chars      = None
    remove_object_tags        = False

class SonyReader(OutputProfile):

    name        = 'Sony Reader'
    short_name  = 'sony'
    description = _('This profile is intended for the SONY PRS line. '
                    'The 500/505/700 etc.')

    epub_flow_size            = 270000
    screen_size               = (590, 765)
    remove_special_chars      = re.compile(u'[\u200b\u00ad]')
    remove_object_tags        = True



output_profiles = [OutputProfile, SonyReader]
