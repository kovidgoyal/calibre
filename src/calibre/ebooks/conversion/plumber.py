from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.customize.conversion import OptionRecommendation 
from calibre.customize.ui import input_profiles

pipeline_options = [

OptionRecommendation(name='verbose', 
            recommended_value=0, level=OptionRecommendation.LOW,
            short_switch='v', 
            help=_('Level of verbosity. Specify multiple times for greater '
                   'verbosity.')
        ),


OptionRecommendation(name='input_profile',
            recommended_value='default', level=OptionRecommendation.LOW,
            choices=[x.short_name for x in input_profiles()],
            help=_('Specify the input profile. The input profile gives the '
                   'conversion system information on how to interpret '
                   'various information in the input document. For '
                   'example resolution dependent lengths (i.e. lengths in '
                   'pixels).')
        ),

]