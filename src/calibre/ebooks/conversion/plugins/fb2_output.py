# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import OutputFormatPlugin, OptionRecommendation


class FB2Output(OutputFormatPlugin):

    name = 'FB2 Output'
    author = 'John Schember'
    file_type = 'fb2'

    FB2_GENRES = [
        # Science Fiction & Fantasy
        'sf_history',  # Alternative history
        'sf_action',  # Action
        'sf_epic',  # Epic
        'sf_heroic',  # Heroic
        'sf_detective',  # Detective
        'sf_cyberpunk',  # Cyberpunk
        'sf_space',  # Space
        'sf_social',  # Social#philosophical
        'sf_horror',  # Horror & mystic
        'sf_humor',  # Humor
        'sf_fantasy',  # Fantasy
        'sf',  # Science Fiction
        # Detectives & Thrillers
        'det_classic',  # Classical detectives
        'det_police',  # Police Stories
        'det_action',  # Action
        'det_irony',  # Ironical detectives
        'det_history',  # Historical detectives
        'det_espionage',  # Espionage detectives
        'det_crime',  # Crime detectives
        'det_political',  # Political detectives
        'det_maniac',  # Maniacs
        'det_hard',  # Hard#boiled
        'thriller',  # Thrillers
        'detective',  # Detectives
        # Prose
        'prose_classic',  # Classics prose
        'prose_history',  # Historical prose
        'prose_contemporary',  # Contemporary prose
        'prose_counter',  # Counterculture
        'prose_rus_classic',  # Russial classics prose
        'prose_su_classics',  # Soviet classics prose
        # Romance
        'love_contemporary',  # Contemporary Romance
        'love_history',  # Historical Romance
        'love_detective',  # Detective Romance
        'love_short',  # Short Romance
        'love_erotica',  # Erotica
        # Adventure
        'adv_western',  # Western
        'adv_history',  # History
        'adv_indian',  # Indians
        'adv_maritime',  # Maritime Fiction
        'adv_geo',  # Travel & geography
        'adv_animal',  # Nature & animals
        'adventure',  # Other
        # Children's
        'child_tale',  # Fairy Tales
        'child_verse',  # Verses
    'child_prose',  # Prose
    'child_sf',  # Science Fiction
    'child_det',  # Detectives & Thrillers
    'child_adv',  # Adventures
    'child_education',  # Educational
    'children',  # Other
    # Poetry & Dramaturgy
    'poetry',  # Poetry
    'dramaturgy',  # Dramaturgy
    # Antique literature
    'antique_ant',  # Antique
    'antique_european',  # European
    'antique_russian',  # Old russian
    'antique_east',  # Old east
    'antique_myths',  # Myths. Legends. Epos
    'antique',  # Other
    # Scientific#educational
    'sci_history',  # History
    'sci_psychology',  # Psychology
    'sci_culture',  # Cultural science
    'sci_religion',  # Religious studies
    'sci_philosophy',  # Philosophy
    'sci_politics',  # Politics
    'sci_business',  # Business literature
    'sci_juris',  # Jurisprudence
    'sci_linguistic',  # Linguistics
    'sci_medicine',  # Medicine
    'sci_phys',  # Physics
    'sci_math',  # Mathematics
    'sci_chem',  # Chemistry
    'sci_biology',  # Biology
    'sci_tech',  # Technical
    'science',  # Other
    # Computers & Internet
    'comp_www',  # Internet
    'comp_programming',  # Programming
    'comp_hard',  # Hardware
    'comp_soft',  # Software
    'comp_db',  # Databases
    'comp_osnet',  # OS & Networking
    'computers',  # Other
    # Reference
    'ref_encyc',  # Encyclopedias
    'ref_dict',  # Dictionaries
    'ref_ref',  # Reference
    'ref_guide',  # Guidebooks
    'reference',  # Other
    # Nonfiction
    'nonf_biography',  # Biography & Memoirs
    'nonf_publicism',  # Publicism
    'nonf_criticism',  # Criticism
    'design',  # Art & design
    'nonfiction',  # Other
    # Religion & Inspiration
    'religion_rel',  # Religion
    'religion_esoterics',  # Esoterics
    'religion_self',  # Self#improvement
    'religion',  # Other
    # Humor
    'humor_anecdote',  # Anecdote (funny stories)
    'humor_prose',  # Prose
    'humor_verse',  # Verses
    'humor',  # Other
    # Home & Family
    'home_cooking',  # Cooking
    'home_pets',  # Pets
    'home_crafts',  # Hobbies & Crafts
    'home_entertain',  # Entertaining
    'home_health',  # Health
    'home_garden',  # Garden
    'home_diy',  # Do it yourself
    'home_sport',  # Sports
    'home_sex',  # Erotica & sex
    'home',  # Other
    ]

    options = set([
        OptionRecommendation(name='sectionize',
            recommended_value='files', level=OptionRecommendation.LOW,
            choices=['toc', 'files', 'nothing'],
            help=_('Specify the sectionization of elements. '
                'A value of "nothing" turns the book into a single section. '
                'A value of "files" turns each file into a separate section; use this if your device is having trouble. '
                'A value of "Table of Contents" turns the entries in the Table of Contents into titles and creates sections; '
                'if it fails, adjust the "Structure detection" and/or "Table of Contents" settings '
                '(turn on "Force use of auto-generated Table of Contents").')),
        OptionRecommendation(name='fb2_genre',
            recommended_value='antique', level=OptionRecommendation.LOW,
            choices=FB2_GENRES,
            help=(_('Genre for the book. Choices: %s\n\n See: ') % ', '.join(FB2_GENRES)) + 'http://www.fictionbook.org/index.php/Eng:FictionBook_2.1_genres ' +
                             _('for a complete list with descriptions.')),
    ])

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        from calibre.ebooks.oeb.transforms.jacket import linearize_jacket
        from calibre.ebooks.oeb.transforms.rasterize import SVGRasterizer, Unavailable
        from calibre.ebooks.fb2.fb2ml import FB2MLizer

        try:
            rasterizer = SVGRasterizer()
            rasterizer(oeb_book, opts)
        except Unavailable:
            log.warn('SVG rasterizer unavailable, SVG will not be converted')

        linearize_jacket(oeb_book)

        fb2mlizer = FB2MLizer(log)
        fb2_content = fb2mlizer.extract_content(oeb_book, opts)

        close = False
        if not hasattr(output_path, 'write'):
            close = True
            if not os.path.exists(os.path.dirname(output_path)) and os.path.dirname(output_path) != '':
                os.makedirs(os.path.dirname(output_path))
            out_stream = open(output_path, 'wb')
        else:
            out_stream = output_path

        out_stream.seek(0)
        out_stream.truncate()
        out_stream.write(fb2_content.encode('utf-8', 'replace'))

        if close:
            out_stream.close()
