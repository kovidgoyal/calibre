from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.customize import Plugin

class InputProfile(Plugin):
    
    author = 'Kovid Goyal'
    supported_platforms = set(['windows', 'osx', 'linux'])
    can_be_disabled = False
    type = _('Input profile')

# TODO: Add some real information to this profile. All other profiles must
#       inherit from this profile and override as needed

    name        = 'Default Input Profile'
    short_name  = 'default' # Used in the CLI so dont spaces etc. in it
    description = _('This profile tries to provide sane defaults and is useful '
                    'if you know nothing about the input document.')
                  
input_profiles = [InputProfile]
    


    
