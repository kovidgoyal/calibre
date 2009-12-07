#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.constants import numeric_version

class RecipeInput(InputFormatPlugin):

    name        = 'Recipe Input'
    author      = 'Kovid Goyal'
    description = _('Download periodical content from the internet')
    file_types  = set(['recipe'])

    recommendations = set([
        ('chapter', None, OptionRecommendation.HIGH),
        ('dont_split_on_page_breaks', True, OptionRecommendation.HIGH),
        ('use_auto_toc', False, OptionRecommendation.HIGH),
        ('input_encoding', None, OptionRecommendation.HIGH),
        ('input_profile', 'default', OptionRecommendation.HIGH),
        ('page_breaks_before', None, OptionRecommendation.HIGH),
        ('insert_metadata', False, OptionRecommendation.HIGH),
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
            accelerators):
        from calibre.web.feeds.recipes import compile_recipe
        from calibre.web.feeds.recipes.collection import \
                get_builtin_recipe_by_title
        if os.access(recipe_or_file, os.R_OK):
            recipe = compile_recipe(open(recipe_or_file, 'rb').read())
        else:
            title = getattr(opts, 'original_recipe_input_arg', recipe_or_file)
            title = os.path.basename(title).rpartition('.')[0]
            raw = get_builtin_recipe_by_title(title, log=log, download_recipe=True)
            builtin = False
            try:
                recipe = compile_recipe(raw)
                if recipe.requires_version > numeric_version:
                    log.warn(
                    'Downloaded recipe needs calibre version at least: %s' % \
                    recipe.requires_version)
                builtin = True
            except:
                log.exception('Failed to compile downloaded recipe. Falling '
                        'back to builtin one')
                builtin = True
            if builtin:
                raw = get_builtin_recipe_by_title(title, log=log,
                        download_recipe=False)
                recipe = compile_recipe(raw)



        if recipe is None:
            raise ValueError('%r is not a valid recipe file or builtin recipe' %
                    recipe_or_file)

        ro = recipe(opts, log, self.report_progress)
        ro.download()
        self.recipe_object = ro
        for key, val in recipe.conversion_options.items():
            setattr(opts, key, val)

        opts.output_profile.flow_size = 0

        for f in os.listdir('.'):
            if f.endswith('.opf'):
                return os.path.abspath(f)

    def postprocess_book(self, oeb, opts, log):
        self.recipe_object.postprocess_book(oeb, opts, log)

