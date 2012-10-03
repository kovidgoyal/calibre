#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.constants import numeric_version
from calibre import walk

class RecipeDisabled(Exception):
    pass

class RecipeInput(InputFormatPlugin):

    name        = 'Recipe Input'
    author      = 'Kovid Goyal'
    description = _('Download periodical content from the internet')
    file_types  = set(['recipe', 'downloaded_recipe'])

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
        OptionRecommendation(name='dont_download_recipe',
            recommended_value=False,
            help=_('Do not download latest version of builtin recipes from the calibre server')),
        OptionRecommendation(name='lrf', recommended_value=False,
            help='Optimize fetching for subsequent conversion to LRF.'),
        ])

    def convert(self, recipe_or_file, opts, file_ext, log,
            accelerators):
        from calibre.web.feeds.recipes import compile_recipe
        opts.output_profile.flow_size = 0
        if file_ext == 'downloaded_recipe':
            from calibre.utils.zipfile import ZipFile
            zf = ZipFile(recipe_or_file, 'r')
            zf.extractall()
            zf.close()
            self.recipe_source = open(u'download.recipe', 'rb').read()
            recipe = compile_recipe(self.recipe_source)
            recipe.needs_subscription = False
            self.recipe_object = recipe(opts, log, self.report_progress)
        else:
            if os.access(recipe_or_file, os.R_OK):
                self.recipe_source = open(recipe_or_file, 'rb').read()
                recipe = compile_recipe(self.recipe_source)
                log('Using custom recipe')
            else:
                from calibre.web.feeds.recipes.collection import \
                        get_builtin_recipe_by_title
                title = getattr(opts, 'original_recipe_input_arg', recipe_or_file)
                title = os.path.basename(title).rpartition('.')[0]
                raw = get_builtin_recipe_by_title(title, log=log,
                        download_recipe=not opts.dont_download_recipe)
                builtin = False
                try:
                    recipe = compile_recipe(raw)
                    self.recipe_source = raw
                    if recipe.requires_version > numeric_version:
                        log.warn(
                        'Downloaded recipe needs calibre version at least: %s' % \
                        ('.'.join(recipe.requires_version)))
                        builtin = True
                except:
                    log.exception('Failed to compile downloaded recipe. Falling '
                            'back to builtin one')
                    builtin = True
                if builtin:
                    log('Using bundled builtin recipe')
                    raw = get_builtin_recipe_by_title(title, log=log,
                            download_recipe=False)
                    if raw is None:
                        raise ValueError('Failed to find builtin recipe: '+title)
                    recipe = compile_recipe(raw)
                    self.recipe_source = raw
                else:
                    log('Using downloaded builtin recipe')

            if recipe is None:
                raise ValueError('%r is not a valid recipe file or builtin recipe' %
                        recipe_or_file)

            disabled = getattr(recipe, 'recipe_disabled', None)
            if disabled is not None:
                raise RecipeDisabled(disabled)
            ro = recipe(opts, log, self.report_progress)
            ro.download()
            self.recipe_object = ro

        for key, val in self.recipe_object.conversion_options.items():
            setattr(opts, key, val)

        for f in os.listdir(u'.'):
            if f.endswith('.opf'):
                return os.path.abspath(f)

        for f in walk(u'.'):
            if f.endswith('.opf'):
                return os.path.abspath(f)

    def postprocess_book(self, oeb, opts, log):
        if self.recipe_object is not None:
            self.recipe_object.postprocess_book(oeb, opts, log)

    def specialize(self, oeb, opts, log, output_fmt):
        if opts.no_inline_navbars:
            from calibre.ebooks.oeb.base import XPath
            for item in oeb.spine:
                for div in XPath('//h:div[contains(@class, "calibre_navbar")]')(item.data):
                    div.getparent().remove(div)

    def save_download(self, zf):
        raw = self.recipe_source
        if isinstance(raw, unicode):
            raw = raw.encode('utf-8')
        zf.writestr('download.recipe', raw)

