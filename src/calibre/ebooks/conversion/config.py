#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, ast, json

from calibre.utils.config import config_dir, prefs, tweaks
from calibre.utils.lock import ExclusiveFile
from calibre import sanitize_file_name
from calibre.customize.conversion import OptionRecommendation
from calibre.customize.ui import available_output_formats


config_dir = os.path.join(config_dir, 'conversion')
if not os.path.exists(config_dir):
    os.makedirs(config_dir)


def name_to_path(name):
    return os.path.join(config_dir, sanitize_file_name(name)+'.py')


def save_defaults(name, recs):
    path = name_to_path(name)
    raw = recs.serialize()
    with lopen(path, 'wb'):
        pass
    with ExclusiveFile(path) as f:
        f.write(raw)


def load_defaults(name):
    path = name_to_path(name)
    if not os.path.exists(path):
        open(path, 'wb').close()
    with ExclusiveFile(path) as f:
        raw = f.read()
    r = GuiRecommendations()
    if raw:
        r.deserialize(raw)
    return r


def save_specifics(db, book_id, recs):
    raw = recs.serialize()
    db.new_api.set_conversion_options({book_id: raw}, fmt='PIPE')


def load_specifics(db, book_id):
    raw = db.conversion_options(book_id, 'PIPE')
    r = GuiRecommendations()
    if raw:
        r.deserialize(raw)
    return r


def delete_specifics(db, book_id):
    db.delete_conversion_options(book_id, 'PIPE')


class GuiRecommendations(dict):

    def __new__(cls, *args):
        dict.__new__(cls)
        obj = super(GuiRecommendations, cls).__new__(cls, *args)
        obj.disabled_options = set()
        return obj

    def to_recommendations(self, level=OptionRecommendation.LOW):
        ans = []
        for key, val in self.items():
            ans.append((key, val, level))
        return ans

    def __str__(self):
        ans = ['{']
        for key, val in self.items():
            ans.append('\t'+repr(key)+' : '+repr(val)+',')
        ans.append('}')
        return '\n'.join(ans)

    def serialize(self):
        ans = json.dumps(self, indent=2, ensure_ascii=False)
        if isinstance(ans, unicode):
            ans = ans.encode('utf-8')
        return b'json:' + ans

    def deserialize(self, raw):
        try:
            if raw.startswith(b'json:'):
                d = json.loads(raw[len(b'json:'):])
            else:
                d = ast.literal_eval(raw)
        except Exception:
            pass
        else:
            if d:
                self.update(d)
    from_string = deserialize

    def merge_recommendations(self, get_option, level, options,
            only_existing=False):
        for name in options:
            if only_existing and name not in self:
                continue
            opt = get_option(name)
            if opt is None:
                continue
            if opt.level == OptionRecommendation.HIGH:
                self[name] = opt.recommended_value
                self.disabled_options.add(name)
            elif opt.level > level or name not in self:
                self[name] = opt.recommended_value

    def as_dict(self):
        return {
            'options': self.copy(),
            'disabled': tuple(self.disabled_options)
        }


def get_available_formats_for_book(db, book_id):
    available_formats = db.new_api.formats(book_id)
    return {x.lower() for x in available_formats}


class NoSupportedInputFormats(Exception):

    def __init__(self, available_formats):
        Exception.__init__(self)
        self.available_formats = available_formats


def get_supported_input_formats_for_book(db, book_id):
    from calibre.ebooks.conversion.plumber import supported_input_formats
    available_formats = get_available_formats_for_book(db, book_id)
    input_formats = {x.lower() for x in supported_input_formats()}
    input_formats = sorted(available_formats.intersection(input_formats))
    if not input_formats:
        raise NoSupportedInputFormats(tuple(x for x in available_formats if x))
    return input_formats


def get_preferred_input_format_for_book(db, book_id):
    recs = load_specifics(db, book_id)
    if recs:
        return recs.get('gui_preferred_input_format', None)


def sort_formats_by_preference(formats, prefs):
    uprefs = {x.upper():i for i, x in enumerate(prefs)}

    def key(x):
        return uprefs.get(x.upper(), len(prefs))

    return sorted(formats, key=key)


def get_input_format_for_book(db, book_id, pref=None):
    '''
    Return (preferred input format, list of available formats) for the book
    identified by book_id. Raises an error if the book has no input formats.

    :param pref: If None, the format used as input for the last conversion, if
    any, on this book is used. If not None, should be a lowercase format like
    'epub' or 'mobi'. If you do not want the last converted format to be used,
    set pref=False.
    '''
    if pref is None:
        pref = get_preferred_input_format_for_book(db, book_id)
    if hasattr(pref, 'lower'):
        pref = pref.lower()
    input_formats = get_supported_input_formats_for_book(db, book_id)
    input_format = pref if pref in input_formats else \
        sort_formats_by_preference(
            input_formats, prefs['input_format_order'])[0]
    return input_format, input_formats


def get_output_formats(preferred_output_format):
    all_formats = {x.upper() for x in available_output_formats()}
    all_formats.discard('OEB')
    pfo = preferred_output_format.upper() if preferred_output_format else ''
    restrict = tweaks['restrict_output_formats']
    if restrict:
        fmts = [x.upper() for x in restrict]
        if pfo and pfo not in fmts and pfo in all_formats:
            fmts.append(pfo)
    else:
        fmts = list(sorted(all_formats,
            key=lambda x:{'EPUB':'!A', 'AZW3':'!B', 'MOBI':'!C'}.get(x.upper(), x)))
    return fmts


def get_sorted_output_formats(preferred_fmt=None):
    preferred_output_format = (preferred_fmt or prefs['output_format']).upper()
    fmts = get_output_formats(preferred_output_format)
    try:
        fmts.remove(preferred_output_format)
    except Exception:
        pass
    fmts.insert(0, preferred_output_format)
    return fmts


OPTIONS = {
    'input': {
        'comic': (
            'colors', 'dont_normalize', 'keep_aspect_ratio', 'right2left', 'despeckle', 'no_sort', 'no_process', 'landscape',
            'dont_sharpen', 'disable_trim', 'wide', 'output_format', 'dont_grayscale', 'comic_image_size', 'dont_add_comic_pages_to_toc'),

        'docx': ('docx_no_cover', 'docx_no_pagebreaks_between_notes', 'docx_inline_subsup'),

        'fb2': ('no_inline_fb2_toc',),

        'pdf': ('no_images', 'unwrap_factor'),

        'rtf': ('ignore_wmf',),

        'txt': ('paragraph_type', 'formatting_type', 'markdown_extensions', 'preserve_spaces', 'txt_in_remove_indents'),
    },

    'pipe': {
        'debug': ('debug_pipeline',),

        'heuristics': (
            'enable_heuristics', 'markup_chapter_headings',
            'italicize_common_cases', 'fix_indents', 'html_unwrap_factor',
            'unwrap_lines', 'delete_blank_paragraphs', 'format_scene_breaks',
            'replace_scene_breaks', 'dehyphenate', 'renumber_headings'),

        'look_and_feel': (
            'change_justification', 'extra_css', 'base_font_size',
            'font_size_mapping', 'line_height', 'minimum_line_height',
            'embed_font_family', 'embed_all_fonts', 'subset_embedded_fonts',
            'smarten_punctuation', 'unsmarten_punctuation',
            'disable_font_rescaling', 'insert_blank_line',
            'remove_paragraph_spacing', 'remove_paragraph_spacing_indent_size',
            'insert_blank_line_size', 'input_encoding', 'filter_css',
            'expand_css', 'asciiize', 'keep_ligatures', 'linearize_tables',
            'transform_css_rules'),

        'metadata': ('prefer_metadata_cover',),

        'page_setup': (
            'margin_top', 'margin_left', 'margin_right', 'margin_bottom',
            'input_profile', 'output_profile'),

        'search_and_replace': (
            'search_replace', 'sr1_search', 'sr1_replace', 'sr2_search', 'sr2_replace', 'sr3_search', 'sr3_replace'),

        'structure_detection': (
            'chapter', 'chapter_mark', 'start_reading_at',
            'remove_first_image', 'remove_fake_margins', 'insert_metadata',
            'page_breaks_before'),

        'toc': (
            'level1_toc', 'level2_toc', 'level3_toc',
            'toc_threshold', 'max_toc_links', 'no_chapters_in_toc',
            'use_auto_toc', 'toc_filter', 'duplicate_links_in_toc',),
    },

    'output': {
        'azw3': ('prefer_author_sort', 'toc_title', 'mobi_toc_at_start', 'dont_compress', 'no_inline_toc', 'share_not_sync',),

        'docx': (
            'docx_page_size', 'docx_custom_page_size', 'docx_no_cover', 'docx_no_toc',
            'docx_page_margin_left', 'docx_page_margin_top', 'docx_page_margin_right',
            'docx_page_margin_bottom', 'preserve_cover_aspect_ratio',),

        'epub': (
            'dont_split_on_page_breaks', 'flow_size', 'no_default_epub_cover',
            'no_svg_cover', 'epub_inline_toc', 'epub_toc_at_end', 'toc_title',
            'preserve_cover_aspect_ratio', 'epub_flatten', 'epub_version'),

        'fb2': ('sectionize', 'fb2_genre'),

        'htmlz': ('htmlz_css_type', 'htmlz_class_style', 'htmlz_title_filename'),

        'lrf': (
            'wordspace', 'header', 'header_format', 'minimum_indent',
            'serif_family', 'render_tables_as_images', 'sans_family',
            'mono_family', 'text_size_multiplier_for_rendered_tables',
            'autorotation', 'header_separation', 'minimum_indent'),

        'mobi': (
            'prefer_author_sort', 'toc_title', 'mobi_keep_original_images',
            'mobi_ignore_margins', 'mobi_toc_at_start', 'dont_compress',
            'no_inline_toc', 'share_not_sync', 'personal_doc',
            'mobi_file_type'),

        'pdb': ('format', 'inline_toc', 'pdb_output_encoding'),

        'pdf': (
            'use_profile_size', 'paper_size', 'custom_size', 'pdf_hyphenate',
            'preserve_cover_aspect_ratio', 'pdf_serif_family', 'unit',
            'pdf_sans_family', 'pdf_mono_family', 'pdf_standard_font',
            'pdf_default_font_size', 'pdf_mono_font_size', 'pdf_page_numbers',
            'pdf_footer_template', 'pdf_header_template', 'pdf_add_toc',
            'toc_title', 'pdf_page_margin_left', 'pdf_page_margin_top',
            'pdf_page_margin_right', 'pdf_page_margin_bottom',
            'pdf_use_document_margins',),

        'pmlz': ('inline_toc', 'full_image_depth', 'pml_output_encoding'),

        'rb': ('inline_toc',),

        'snb': (
            'snb_insert_empty_line', 'snb_dont_indent_first_line',
            'snb_hide_chapter_name','snb_full_screen'),

        'txt': (
            'newline', 'max_line_length', 'force_max_line_length',
            'inline_toc', 'txt_output_formatting', 'keep_links', 'keep_image_references',
            'keep_color', 'txt_output_encoding'),
    },
}
OPTIONS['output']['txtz'] = OPTIONS['output']['txt']


def options_for_input_fmt(fmt):
    from calibre.customize.ui import plugin_for_input_format
    fmt = fmt.lower()
    plugin = plugin_for_input_format(fmt)
    if plugin is None:
        return None, ()
    full_name = plugin.name.lower().replace(' ', '_')
    name = full_name.rpartition('_')[0]
    return full_name, OPTIONS['input'].get(name, ())


def options_for_output_fmt(fmt):
    from calibre.customize.ui import plugin_for_output_format
    fmt = fmt.lower()
    plugin = plugin_for_output_format(fmt)
    if plugin is None:
        return None, ()
    full_name = plugin.name.lower().replace(' ', '_')
    name = full_name.rpartition('_')[0]
    return full_name, OPTIONS['output'].get(name, ())
