#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation

class RecipeInput(InputFormatPlugin):

    name        = 'Recipe Input'
    author      = 'Kovid Goyal'
    description = _('Download periodical content from the internet')
    file_types  = set(['recipe'])

    recommendations = set([
        ('chapter_mark', 'none', OptionRecommendation.HIGH),
        ('dont_split_on_page_breaks', True, OptionRecommendation.HIGH),
        ('use_auto_toc', False, OptionRecommendation.HIGH),
        ])

    options = set([
        OptionRecommendation(name='test', recommended_value=False,
            help=_('Useful for recipe development. Forces '
            'max_articles_per_feed to 2 and downloads at most 2 feeds.')),
        OptionRecommendation(name='username', recommended_value=None,
            help=_('Username for sites that require a login to access '
                'content.')),
        OptionRecommendation(name='password', recommended_value=None,
            help=_('Password for sites that require a login to access '
                'content.')),
        OptionRecommendation(name='lrf', recommended_value=False,
            help='Optimize fetching for subsequent conversion to LRF.'),
        ])

    def convert(self, recipe_or_file, opts, file_ext, log,
            accelerators, progress=lambda x, y: x):
        from calibre.web.feeds.recipes import \
                get_builtin_recipe, compile_recipe
        if os.access(recipe_or_file, os.R_OK):
            recipe = compile_recipe(open(recipe_or_file, 'rb').read())
        else:
            title = os.path.basename(recipe_or_file).rpartition('.')[0]
            recipe = get_builtin_recipe(title)

        if recipe is None:
            raise ValueError('%s is not a valid recipe file or builtin recipe' %
                    recipe_or_file)

        ro = recipe(opts, log, progress)
        ro.download()

        opts.output_profile.flow_size = 0

        for f in os.listdir('.'):
            if f.endswith('.opf'):
                return os.path.abspath(f)




