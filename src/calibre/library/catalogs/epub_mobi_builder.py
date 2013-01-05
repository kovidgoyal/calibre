# -*- coding: utf-8 -*-

__license__ = 'GPL v3'
__copyright__ = '2010, Greg Riker'

import datetime, htmlentitydefs, os, platform, re, shutil, unicodedata, zlib
from copy import deepcopy
from xml.sax.saxutils import escape

from calibre import (prepare_string_for_xml, strftime, force_unicode,
        isbytestring)
from calibre.constants import isosx
from calibre.customize.conversion import DummyReporter
from calibre.customize.ui import output_profiles
from calibre.ebooks.BeautifulSoup import BeautifulSoup, BeautifulStoneSoup, Tag, NavigableString
from calibre.ebooks.chardet import substitute_entites
from calibre.ebooks.metadata import author_to_author_sort
from calibre.library.catalogs import AuthorSortMismatchException, EmptyCatalogException, \
                                     InvalidGenresSourceFieldException
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.config import config_dir
from calibre.utils.date import format_date, is_date_undefined, now as nowf
from calibre.utils.filenames import ascii_text, shorten_components_to
from calibre.utils.icu import capitalize, collation_order, sort_key
from calibre.utils.magick.draw import thumbnail
from calibre.utils.zipfile import ZipFile


class CatalogBuilder(object):
    '''
    Generates catalog source files from calibre database

    Flow of control:
        gui2.actions.catalog:generate_catalog()
        gui2.tools:generate_catalog() or library.cli:command_catalog()
        called from gui2.convert.gui_conversion:gui_catalog()
        catalog = Catalog(notification=Reporter())
        catalog.build_sources()
    Options managed in gui2.catalog.catalog_epub_mobi.py

    Turned off fetch_bookmarks as of 0.8.70
    self.generate_recently_read = True if (_opts.generate_recently_added and
                                           _opts.connected_kindle and
                                           self.generate_for_kindle_mobi) else False
    Does not work with AZW3, interferes with new prefix handling
    '''

    DEBUG = False

    # A single number creates 'Last x days' only.
    # Multiple numbers create 'Last x days', 'x to y days ago' ...
    # e.g, [7,15,30,60] or [30]
    # [] = No date ranges added
    DATE_RANGE = [30]

    # Text used in generated catalog for title section with other-than-ASCII leading letter
    SYMBOLS = _('Symbols')

    # basename              output file basename
    # creator               dc:creator in OPF metadata
    # description_clip       limits size of NCX descriptions (Kindle only)
    # includeSources        Used in filter_excluded_genres to skip tags like '[SPL]'
    # notification          Used to check for cancel, report progress
    # stylesheet            CSS stylesheet
    # title                 dc:title in OPF metadata, NCX periodical
    # verbosity             level of diagnostic printout

    ''' device-specific symbol (default empty star) '''
    @property
    def SYMBOL_EMPTY_RATING(self):
        return self.output_profile.empty_ratings_char

    ''' device-specific symbol (default filled star) '''
    @property
    def SYMBOL_FULL_RATING(self):
        return self.output_profile.ratings_char

    ''' device-specific symbol for reading progress '''
    @property
    def SYMBOL_PROGRESS_READ(self):
        psr = '+'
        if self.generate_for_kindle_mobi:
            psr = '&#9642;'
        return psr

    ''' device-specific symbol for reading progress '''
    @property
    def SYMBOL_PROGRESS_UNREAD(self):
        psu = '-'
        if self.generate_for_kindle_mobi:
            psu = '&#9643;'
        return psu

    ''' device-specific symbol for reading progress '''
    @property
    def SYMBOL_READING(self):
        if self.generate_for_kindle_mobi:
            return '&#x25b7;'
        else:
            return '&nbsp;'

    def __init__(self, db, _opts, plugin,
                    report_progress=DummyReporter(),
                    stylesheet="content/stylesheet.css",
                    init_resources=True):

        self.db = db
        self.opts = _opts
        self.plugin = plugin
        self.reporter = report_progress
        self.stylesheet = stylesheet
        self.cache_dir = os.path.join(config_dir, 'caches', 'catalog')
        self.catalog_path = PersistentTemporaryDirectory("_epub_mobi_catalog", prefix='')
        self.content_dir = os.path.join(self.catalog_path, "content")
        self.excluded_tags = self.get_excluded_tags()
        self.generate_for_kindle_azw3 = True if (_opts.fmt == 'azw3' and
                                              _opts.output_profile and
                                              _opts.output_profile.startswith("kindle")) else False
        self.generate_for_kindle_mobi = True if (_opts.fmt == 'mobi' and
                                              _opts.output_profile and
                                              _opts.output_profile.startswith("kindle")) else False

        self.all_series = set()
        self.authors = None
        self.bookmarked_books = None
        self.bookmarked_books_by_date_read = None
        self.books_by_author = None
        self.books_by_date_range = None
        self.books_by_description = []
        self.books_by_month = None
        self.books_by_series = None
        self.books_by_title = None
        self.books_by_title_no_series_prefix = None
        self.books_to_catalog = None
        self.current_step = 0.0
        self.error = []
        self.generate_recently_read = False
        self.genres = []
        self.genre_tags_dict = \
            self.filter_genre_tags(max_len=245 - len("%s/Genre_.html" % self.content_dir)) \
            if self.opts.generate_genres else None
        self.html_filelist_1 = []
        self.html_filelist_2 = []
        self.individual_authors = None
        self.merge_comments_rule = dict(zip(['field', 'position', 'hr'],
                                            _opts.merge_comments_rule.split(':')))
        self.ncx_soup = None
        self.output_profile = self.get_output_profile(_opts)
        self.play_order = 1
        self.prefix_rules = self.get_prefix_rules()
        self.progress_int = 0.0
        self.progress_string = ''
        self.thumb_height = 0
        self.thumb_width = 0
        self.thumbs = None
        self.thumbs_path = os.path.join(self.cache_dir, "thumbs.zip")
        self.total_steps = 6.0
        self.use_series_prefix_in_titles_section = False

        self.dump_custom_fields()
        self.books_to_catalog = self.fetch_books_to_catalog()
        self.compute_total_steps()
        self.calculate_thumbnail_dimensions()
        self.confirm_thumbs_archive()
        self.load_section_templates()
        if init_resources:
            self.copy_catalog_resources()

    """ key() functions """

    def _kf_author_to_author_sort(self, author):
        """ Compute author_sort value from author

        Tokenize author string, return capitalized string with last token first

        Args:
         author (str): author, e.g. 'John Smith'

        Return:
         (str): 'Smith, john'
        """
        tokens = author.split()
        tokens = tokens[-1:] + tokens[:-1]
        if len(tokens) > 1:
            tokens[0] += ','
        return ' '.join(tokens).capitalize()

    def _kf_books_by_author_sorter_author(self, book):
        """ Generate book sort key with computed author_sort.

        Generate a sort key of computed author_sort, title. Used to look for
        author_sort mismatches.
        Twiddle included to force series to sort after non-series books.
         'Smith, john Star Wars'
         'Smith, john ~Star Wars 0001.0000'

        Args:
         book (dict): book metadata

        Return:
         (str): sort key
        """
        if not book['series']:
            key = '%s %s' % (self._kf_author_to_author_sort(book['author']),
                                capitalize(book['title_sort']))
        else:
            index = book['series_index']
            integer = int(index)
            fraction = index - integer
            series_index = '%04d%s' % (integer, str('%0.4f' % fraction).lstrip('0'))
            key = '%s ~%s %s' % (self._kf_author_to_author_sort(book['author']),
                                    self.generate_sort_title(book['series']),
                                    series_index)
        return key

    def _kf_books_by_author_sorter_author_sort(self, book, longest_author_sort=60):
        """ Generate book sort key with supplied author_sort.

        Generate a sort key of author_sort, title.
        Bang, tilde included to force series to sort after non-series books.

        Args:
         book (dict): book metadata

        Return:
         (str): sort key
        """
        if not book['series']:
            fs = u'{:<%d}!{!s}' % longest_author_sort
            key = fs.format(capitalize(book['author_sort']),
                            capitalize(book['title_sort']))
        else:
            index = book['series_index']
            integer = int(index)
            fraction = index - integer
            series_index = u'%04d%s' % (integer, str(u'%0.4f' % fraction).lstrip(u'0'))
            fs = u'{:<%d}~{!s}{!s}' % longest_author_sort
            key = fs.format(capitalize(book['author_sort']),
                            self.generate_sort_title(book['series']),
                            series_index)
        return key

    def _kf_books_by_series_sorter(self, book):
        index = book['series_index']
        integer = int(index)
        fraction = index - integer
        series_index = '%04d%s' % (integer, str('%0.4f' % fraction).lstrip('0'))
        key = '%s %s' % (self.generate_sort_title(book['series']),
                         series_index)
        return key

    """ Methods """

    def build_sources(self):
        """ Generate catalog source files.

        Assemble OPF, HTML and NCX files reflecting catalog options.
        Generated source is OEB compliant.
        Called from gui2.convert.gui_conversion:gui_catalog()

        Args:

        Exceptions:
            AuthorSortMismatchException
            EmptyCatalogException

        Results:
         error: problems reported during build

        """

        self.fetch_books_by_title()
        self.fetch_books_by_author()
        self.fetch_bookmarks()
        if self.opts.generate_descriptions:
            self.generate_thumbnails()
            self.generate_html_descriptions()
        if self.opts.generate_authors:
            self.generate_html_by_author()
        if self.opts.generate_titles:
            self.generate_html_by_title()
        if self.opts.generate_series:
            self.generate_html_by_series()
        if self.opts.generate_genres:
            self.generate_html_by_genres()
            # If this is the only Section, and there are no genres, bail
            if self.opts.section_list == ['Genres'] and not self.genres:
                error_msg = _("No genres to catalog.\n")
                if not self.opts.cli_environment:
                    error_msg += _("Check 'Excluded genres' regex in E-book options.\n")
                self.opts.log.error(error_msg)
                self.error.append(_('No books available to catalog'))
                self.error.append(error_msg)
                raise EmptyCatalogException, "No genres to catalog"
        if self.opts.generate_recently_added:
            self.generate_html_by_date_added()
            if self.generate_recently_read:
                self.generate_html_by_date_read()

        self.generate_opf()
        self.generate_ncx_header()
        if self.opts.generate_authors:
            self.generate_ncx_by_author(_("Authors"))
        if self.opts.generate_titles:
            self.generate_ncx_by_title(_("Titles"))
        if self.opts.generate_series:
            self.generate_ncx_by_series(_("Series"))
        if self.opts.generate_genres:
            self.generate_ncx_by_genre(_("Genres"))
        if self.opts.generate_recently_added:
            self.generate_ncx_by_date_added(_("Recently Added"))
            if self.generate_recently_read:
                self.generate_ncx_by_date_read(_("Recently Read"))
        if self.opts.generate_descriptions:
            self.generate_ncx_descriptions(_("Descriptions"))
        self.write_ncx()

    def calculate_thumbnail_dimensions(self):
        """ Calculate thumb dimensions based on device DPI.

        Using the specified output profile, calculate thumb_width
        in pixels, then set height to width * 1.33. Special-case for
        Kindle/MOBI, as rendering off by 2.
        *** dead code? ***

        Inputs:
         opts.thumb_width (str|float): specified thumb_width
         opts.output_profile.dpi (int): device DPI

        Outputs:
         thumb_width (float): calculated thumb_width
         thumb_height (float): calculated thumb_height
        """

        for x in output_profiles():
            if x.short_name == self.opts.output_profile:
                # aspect ratio: 3:4
                self.thumb_width = x.dpi * float(self.opts.thumb_width)
                self.thumb_height = self.thumb_width * 1.33
                if 'kindle' in x.short_name and self.opts.fmt == 'mobi':
                    # Kindle DPI appears to be off by a factor of 2
                    self.thumb_width = self.thumb_width / 2
                    self.thumb_height = self.thumb_height / 2
                break
        if self.opts.verbose:
            self.opts.log(" Thumbnails:")
            self.opts.log("  DPI = %d; thumbnail dimensions: %d x %d" % \
                            (x.dpi, self.thumb_width, self.thumb_height))

    def compute_total_steps(self):
        """ Calculate number of build steps to generate catalog.

        Calculate total number of build steps based on enabled sections.

        Inputs:
         opts.generate_* (bool): enabled sections

        Outputs:
         total_steps (int): updated
        """
        # Tweak build steps based on optional sections:  1 call for HTML, 1 for NCX
        incremental_jobs = 0
        if self.opts.generate_authors:
            incremental_jobs += 2
        if self.opts.generate_titles:
            incremental_jobs += 2
        if self.opts.generate_recently_added:
            incremental_jobs += 2
            if self.generate_recently_read:
                incremental_jobs += 2
        if self.opts.generate_series:
            incremental_jobs += 2
        if self.opts.generate_descriptions:
            # +1 thumbs
            incremental_jobs += 3
        self.total_steps += incremental_jobs

    def confirm_thumbs_archive(self):
        """ Validate thumbs archive.

        Confirm existence of thumbs archive, or create if absent.
        Confirm stored thumb_width matches current opts.thumb_width,
        or invalidate archive.
        generate_thumbnails() writes current thumb_width to archive.

        Inputs:
         opts.thumb_width (float): requested thumb_width
         thumbs_path (file): existing thumbs archive

        Outputs:
         thumbs_path (file): new (non_existent or invalidated), or
                                  validated existing thumbs archive
        """
        if self.opts.generate_descriptions:
            if not os.path.exists(self.cache_dir):
                self.opts.log.info("  creating new thumb cache '%s'" % self.cache_dir)
                os.makedirs(self.cache_dir)
            if not os.path.exists(self.thumbs_path):
                self.opts.log.info('  creating thumbnail archive, thumb_width: %1.2f"' %
                                        float(self.opts.thumb_width))
                with ZipFile(self.thumbs_path, mode='w') as zfw:
                    zfw.writestr("Catalog Thumbs Archive", '')
            else:
                try:
                    with ZipFile(self.thumbs_path, mode='r') as zfr:
                        try:
                            cached_thumb_width = zfr.read('thumb_width')
                        except:
                            cached_thumb_width = "-1"
                except:
                    os.remove(self.thumbs_path)
                    cached_thumb_width = '-1'

                if float(cached_thumb_width) != float(self.opts.thumb_width):
                    self.opts.log.warning("  invalidating cache at '%s'" % self.thumbs_path)
                    self.opts.log.warning('  thumb_width changed: %1.2f" => %1.2f"' %
                                        (float(cached_thumb_width), float(self.opts.thumb_width)))
                    with ZipFile(self.thumbs_path, mode='w') as zfw:
                        zfw.writestr("Catalog Thumbs Archive", '')
                else:
                    self.opts.log.info('  existing thumb cache at %s, cached_thumb_width: %1.2f"' %
                                            (self.thumbs_path, float(cached_thumb_width)))

    def convert_html_entities(self, s):
        """ Convert string containing HTML entities to its unicode equivalent.

        Convert a string containing HTML entities of the form '&amp;' or '&97;'
        to a normalized unicode string. E.g., 'AT&amp;T' converted to 'AT&T'.

        Args:
         s (str): str containing one or more HTML entities.

        Return:
         s (str): converted string
        """
        matches = re.findall("&#\d+;", s)
        if len(matches) > 0:
            hits = set(matches)
            for hit in hits:
                name = hit[2:-1]
                try:
                    entnum = int(name)
                    s = s.replace(hit, unichr(entnum))
                except ValueError:
                    pass

        matches = re.findall("&\w+;", s)
        hits = set(matches)
        amp = "&amp;"
        if amp in hits:
            hits.remove(amp)
        for hit in hits:
            name = hit[1:-1]
            if htmlentitydefs.name2codepoint in name:
                    s = s.replace(hit, unichr(htmlentitydefs.name2codepoint[name]))
        s = s.replace(amp, "&")
        return s

    def copy_catalog_resources(self):
        """ Copy resources from calibre source to self.catalog_path.

        Copy basic resources - default cover, stylesheet, and masthead (Kindle only)
        from calibre resource directory to self.catalog_path, a temporary directory
        for constructing the catalog. Files stored to specified destination dirs.

        Inputs:
         files_to_copy (files): resource files from calibre resources, which may be overridden locally

        Output:
         resource files copied to self.catalog_path/*
        """
        self.create_catalog_directory_structure()
        catalog_resources = P("catalog")

        files_to_copy = [('', 'DefaultCover.jpg'),
                            ('content', 'stylesheet.css')]
        if self.generate_for_kindle_mobi:
            files_to_copy.extend([('images', 'mastheadImage.gif')])

        for file in files_to_copy:
            if file[0] == '':
                shutil.copy(os.path.join(catalog_resources, file[1]),
                                self.catalog_path)
            else:
                shutil.copy(os.path.join(catalog_resources, file[1]),
                                os.path.join(self.catalog_path, file[0]))

        if self.generate_for_kindle_mobi:
            try:
                self.generate_masthead_image(os.path.join(self.catalog_path,
                                                'images/mastheadImage.gif'))
            except:
                pass

    def create_catalog_directory_structure(self):
        """ Create subdirs in catalog output dir.

        Create /content and /images in self.catalog_path

        Inputs:
         catalog_path (path): path to catalog output dir

        Output:
         /content, /images created
        """
        if not os.path.isdir(self.catalog_path):
            os.makedirs(self.catalog_path)

        content_path = self.catalog_path + "/content"
        if not os.path.isdir(content_path):
            os.makedirs(content_path)
        images_path = self.catalog_path + "/images"
        if not os.path.isdir(images_path):
            os.makedirs(images_path)

    def detect_author_sort_mismatches(self, books_to_test):
        """ Detect author_sort mismatches.

        Sort by author, look for inconsistencies in author_sort among
        similarly-named authors. Fatal for MOBI generation, a mere
        annoyance for EPUB.

        Inputs:
         books_by_author (list): list of books to test, possibly unsorted

        Output:
         (none)

        Exceptions:
         AuthorSortMismatchException: author_sort mismatch detected
        """

        books_by_author = sorted(list(books_to_test), key=self._kf_books_by_author_sorter_author)

        authors = [(record['author'], record['author_sort']) for record in books_by_author]
        current_author = authors[0]
        for (i, author) in enumerate(authors):
            if author != current_author and i:
                if author[0] == current_author[0]:
                    if self.opts.fmt == 'mobi':
                        # Exit if building MOBI
                        error_msg = _("<p>Inconsistent Author Sort values for Author<br/>" +
                                      "'{!s}':</p>".format(author[0]) +
                                      "<p><center><b>{!s}</b> != <b>{!s}</b></center></p>".format(author[1], current_author[1]) +
                                      "<p>Unable to build MOBI catalog.<br/>" +
                                      "Select all books by '{!s}', apply correct Author Sort value in Edit Metadata dialog, then rebuild the catalog.\n<p>".format(author[0]))

                        self.opts.log.warn('\n*** Metadata error ***')
                        self.opts.log.warn(error_msg)

                        self.error.append('Author Sort mismatch')
                        self.error.append(error_msg)
                        raise AuthorSortMismatchException, "author_sort mismatch while building MOBI"
                    else:
                        # Warning if building non-MOBI
                        if not self.error:
                            self.error.append('Author Sort mismatch')

                        error_msg = _("Warning: Inconsistent Author Sort values for Author '{!s}':\n".format(author[0]) +
                                      " {!s} != {!s}\n".format(author[1], current_author[1]))
                        self.opts.log.warn('\n*** Metadata warning ***')
                        self.opts.log.warn(error_msg)
                        self.error.append(error_msg)
                        continue

                current_author = author

    def discover_prefix(self, record):
        """ Return a prefix for record.

        Evaluate record against self.prefix_rules. Return assigned prefix
        if matched.

        Args:
         record (dict): book metadata

        Return:
         prefix (str): matched a prefix_rule
         None: no match
        """
        def _log_prefix_rule_match_info(rule, record, matched):
            self.opts.log.info("  %s '%s' by %s (%s: '%s' contains '%s')" %
                               (rule['prefix'], record['title'],
                                record['authors'][0], rule['name'],
                                self.db.metadata_for_field(rule['field'])['name'],
                                matched))

        # Compare the record to each rule looking for a match
        for rule in self.prefix_rules:
            # Literal comparison for Tags field
            if rule['field'].lower() == 'tags':
                if rule['pattern'].lower() in map(unicode.lower, record['tags']):
                    if self.DEBUG and self.opts.verbose:
                        self.opts.log.info("  %s '%s' by %s (%s: Tags includes '%s')" %
                               (rule['prefix'], record['title'],
                                record['authors'][0], rule['name'],
                                rule['pattern']))
                    return rule['prefix']

            # Regex match for custom field
            elif rule['field'].startswith('#'):
                field_contents = self.db.get_field(record['id'],
                                    rule['field'],
                                    index_is_id=True)

                if field_contents == '':
                    field_contents = None

                if (self.db.metadata_for_field(rule['field'])['datatype'] == 'bool' and
                    field_contents is None):
                    # Handle condition where field is a bool and contents is None,
                    # which is displayed as No
                    field_contents = _('False')

                if field_contents is not None:
                    if self.db.metadata_for_field(rule['field'])['datatype'] == 'bool':
                        # For Yes/No fields, need to translate field_contents to
                        # locale version
                        field_contents = _(repr(field_contents))
                    try:
                        if re.search(rule['pattern'], unicode(field_contents),
                                re.IGNORECASE) is not None:
                            if self.DEBUG:
                                _log_prefix_rule_match_info(rule, record, field_contents)
                            return rule['prefix']
                    except:
                        if self.opts.verbose:
                            self.opts.log.error("pattern failed to compile: %s" % rule['pattern'])
                        pass
                elif field_contents is None and rule['pattern'] == 'None':
                    if self.DEBUG:
                        _log_prefix_rule_match_info(rule, record, field_contents)
                    return rule['prefix']

        return None

    def dump_custom_fields(self):
        """
        Dump custom field mappings for debugging
        """
        if self.opts.verbose:
            self.opts.log.info(" Custom fields:")
            all_custom_fields = self.db.custom_field_keys()
            for cf in all_custom_fields:
                self.opts.log.info("  %-20s %-20s %s" %
                    (cf, "'%s'" % self.db.metadata_for_field(cf)['name'],
                     self.db.metadata_for_field(cf)['datatype']))

    def establish_equivalencies(self, item_list, key=None):
        """ Return icu equivalent sort letter.

        Returns base sort letter for accented characters. Code provided by
        chaley, modified to force unaccented base letters for A, O & U when
        an accented version would otherwise be returned.

        Args:
         item_list (list): list of items, sorted by icu_sort

        Return:
         cl_list (list): list of equivalent leading chars, 1:1 correspondence to item_list
        """

        # Hack to force the cataloged leading letter to be
        # an unadorned character if the accented version sorts before the unaccented
        exceptions = {
                        u'Ä':   u'A',
                        u'Ö':   u'O',
                        u'Ü':   u'U'
                     }

        if key is not None:
            sort_field = key

        cl_list = [None] * len(item_list)
        last_ordnum = 0

        for idx, item in enumerate(item_list):
            if key:
                c = item[sort_field]
            else:
                c = item

            ordnum, ordlen = collation_order(c)
            if isosx and platform.mac_ver()[0] < '10.8':
                # Hackhackhackhackhack
                # icu returns bogus results with curly apostrophes, maybe others under OS X 10.6.x
                # When we see the magic combo of 0/-1 for ordnum/ordlen, special case the logic
                last_c = u''
                if ordnum == 0 and ordlen == -1:
                    if icu_upper(c[0]) != last_c:
                        last_c = icu_upper(c[0])
                        if last_c in exceptions.keys():
                            last_c = exceptions[unicode(last_c)]
                        last_ordnum = ordnum
                    cl_list[idx] = last_c
                else:
                    if last_ordnum != ordnum:
                        last_c = icu_upper(c[0:ordlen])
                        if last_c in exceptions.keys():
                            last_c = exceptions[unicode(last_c)]
                        last_ordnum = ordnum
                    cl_list[idx] = last_c

            else:
                if last_ordnum != ordnum:
                    last_c = icu_upper(c[0:ordlen])
                    if last_c in exceptions.keys():
                        last_c = exceptions[unicode(last_c)]
                    last_ordnum = ordnum
                cl_list[idx] = last_c

        if self.DEBUG and self.opts.verbose:
            print("     establish_equivalencies():")
            if key:
                for idx, item in enumerate(item_list):
                    print("      %s %s" % (cl_list[idx], item[sort_field]))
            else:
                    print("      %s %s" % (cl_list[idx], item))

        return cl_list

    def fetch_books_by_author(self):
        """ Generate a list of books sorted by author.

        For books with multiple authors, relist book with additional authors.
        Sort the database by author. Report author_sort inconsistencies as warning when
        building EPUB or MOBI, error when building MOBI. Collect a list of unique authors
        to self.authors.

        Inputs:
         self.books_to_catalog (list): database, sorted by title

        Outputs:
         books_by_author: database, sorted by author
         authors: list of book authors. Two credited authors are considered an
          individual entity
         error: author_sort mismatches

        Return:
         True: no errors
         False: author_sort mismatch detected while building MOBI
        """

        self.update_progress_full_step(_("Sorting database"))

        books_by_author = list(self.books_to_catalog)
        self.detect_author_sort_mismatches(books_by_author)

        # Assumes books_by_title already populated
        # init books_by_description before relisting multiple authors
        if self.opts.generate_descriptions:
            books_by_description = list(books_by_author) if self.opts.sort_descriptions_by_author \
                else list(self.books_by_title)

        if self.opts.cross_reference_authors:
            books_by_author = self.relist_multiple_authors(books_by_author)

        #books_by_author = sorted(list(books_by_author), key=self._kf_books_by_author_sorter_author)

        # Determine the longest author_sort length before sorting
        asl = [i['author_sort'] for i in books_by_author]
        las = max(asl, key=len)

        if self.opts.generate_descriptions:
            self.books_by_description = sorted(books_by_description,
                key=lambda x: sort_key(self._kf_books_by_author_sorter_author_sort(x, len(las))))

        books_by_author = sorted(books_by_author,
            key=lambda x: sort_key(self._kf_books_by_author_sorter_author_sort(x, len(las))))

        if self.DEBUG and self.opts.verbose:
            tl = [i['title'] for i in books_by_author]
            lt = max(tl, key=len)
            fs = '{:<6}{:<%d} {:<%d} {!s}' % (len(lt), len(las))
            print(fs.format('', 'Title', 'Author', 'Series'))
            for i in books_by_author:
                print(fs.format('', i['title'], i['author_sort'], i['series']))

        # Build the unique_authors set from existing data
        authors = [(record['author'], capitalize(record['author_sort'])) for record in books_by_author]

        # authors[] contains a list of all book authors, with multiple entries for multiple books by author
        #        authors[]: (([0]:friendly  [1]:sort))
        # unique_authors[]: (([0]:friendly  [1]:sort  [2]:book_count))
        books_by_current_author = 0
        current_author = authors[0]
        multiple_authors = False
        unique_authors = []
        individual_authors = set()
        for (i, author) in enumerate(authors):
            if author != current_author:
                # Note that current_author and author are tuples: (friendly, sort)
                multiple_authors = True

                # New author, save the previous author/sort/count
                unique_authors.append((current_author[0], icu_title(current_author[1]),
                                        books_by_current_author))
                current_author = author
                books_by_current_author = 1
            elif i == 0 and len(authors) == 1:
                # Allow for single-book lists
                unique_authors.append((current_author[0], icu_title(current_author[1]),
                                        books_by_current_author))
            else:
                books_by_current_author += 1
        else:
            # Add final author to list or single-author dataset
            if (current_author == author and len(authors) > 1) or not multiple_authors:
                unique_authors.append((current_author[0], icu_title(current_author[1]),
                                        books_by_current_author))

        self.authors = list(unique_authors)
        self.books_by_author = books_by_author

        for ua in unique_authors:
            for ia in ua[0].replace(' &amp; ', ' & ').split(' & '):
                individual_authors.add(ia)
        self.individual_authors = list(individual_authors)

        if self.DEBUG and self.opts.verbose:
            self.opts.log.info("\nfetch_books_by_author(): %d unique authors" % len(unique_authors))
            for author in unique_authors:
                self.opts.log.info((u" %-50s %-25s %2d" % (author[0][0:45], author[1][0:20],
                    author[2])).encode('utf-8'))
            self.opts.log.info("\nfetch_books_by_author(): %d individual authors" % len(individual_authors))
            for author in sorted(individual_authors):
                self.opts.log.info("%s" % author)

        return True

    def fetch_books_by_title(self):
        """ Generate a list of books sorted by title.

        Sort the database by title.

        Inputs:
         self.books_to_catalog (list): database

        Outputs:
         books_by_title: database, sorted by title

        Return:
         True: no errors
         False: author_sort mismatch detected while building MOBI
        """
        self.update_progress_full_step(_("Sorting titles"))
        # Re-sort based on title_sort
        if len(self.books_to_catalog):
            self.books_by_title = sorted(self.books_to_catalog, key=lambda x: sort_key(x['title_sort'].upper()))

            if self.DEBUG and self.opts.verbose:
                self.opts.log.info("fetch_books_by_title(): %d books" % len(self.books_by_title))
                self.opts.log.info(" %-40s %-40s" % ('title', 'title_sort'))
                for title in self.books_by_title:
                    self.opts.log.info((u" %-40s %-40s" % (title['title'][0:40],
                                                            title['title_sort'][0:40])).encode('utf-8'))
        else:
            error_msg = _("No books to catalog.\nCheck 'Excluded books' rules in E-book options.\n")
            self.opts.log.error('*** ' + error_msg + ' ***')
            self.error.append(_('No books available to include in catalog'))
            self.error.append(error_msg)
            raise EmptyCatalogException, error_msg

    def fetch_books_to_catalog(self):
        """ Populate self.books_to_catalog from database

        Create self.books_to_catalog from filtered database.
        Keys:
         authors            massaged
         author_sort        record['author_sort'] or computed
         cover              massaged record['cover']
         date               massaged record['pubdate']
         description        massaged record['comments'] + merge_comments
         id                 record['id']
         formats            massaged record['formats']
         notes              from opts.header_note_source_field
         prefix             from self.discover_prefix()
         publisher          massaged record['publisher']
         rating             record['rating'] (0 if None)
         series             record['series'] or None
         series_index       record['series_index'] or 0.0
         short_description  truncated description
         tags               filtered record['tags']
         timestamp          record['timestamp']
         title              massaged record['title']
         title_sort         computed from record['title']
         uuid               record['uuid']

        Inputs:
         data (list): filtered list of book metadata dicts

        Outputs:
         (list) books_to_catalog

        Returns:
         True: Successful
         False: Empty data, (check filter restrictions)
        """

        def _populate_title(record):
            ''' populate this_title with massaged metadata '''
            this_title = {}

            this_title['id'] = record['id']
            this_title['uuid'] = record['uuid']

            this_title['title'] = self.convert_html_entities(record['title'])
            if record['series']:
                this_title['series'] = record['series']
                self.all_series.add(this_title['series'])
                this_title['series_index'] = record['series_index']
            else:
                this_title['series'] = None
                this_title['series_index'] = 0.0

            this_title['title_sort'] = self.generate_sort_title(this_title['title'])

            if 'authors' in record:
                this_title['authors'] = record['authors']
                # Synthesize author attribution from authors list
                if record['authors']:
                    this_title['author'] = " &amp; ".join(record['authors'])
                else:
                    this_title['author'] = _('Unknown')
                    this_title['authors'] = [this_title['author']]

            if 'author_sort' in record and record['author_sort'].strip():
                this_title['author_sort'] = record['author_sort']
            else:
                this_title['author_sort'] = self._kf_author_to_author_sort(this_title['author'])

            if record['publisher']:
                this_title['publisher'] = re.sub('&', '&amp;', record['publisher'])

            this_title['rating'] = record['rating'] if record['rating'] else 0

            if is_date_undefined(record['pubdate']):
                this_title['date'] = None
            else:
                this_title['date'] = strftime(u'%B %Y', record['pubdate'].timetuple())

            this_title['timestamp'] = record['timestamp']

            if record['comments']:
                # Strip annotations
                a_offset = record['comments'].find('<div class="user_annotations">')
                ad_offset = record['comments'].find('<hr class="annotations_divider" />')
                if a_offset >= 0:
                    record['comments'] = record['comments'][:a_offset]
                if ad_offset >= 0:
                    record['comments'] = record['comments'][:ad_offset]

                this_title['description'] = self.massage_comments(record['comments'])

                # Create short description
                paras = BeautifulSoup(this_title['description']).findAll('p')
                tokens = []
                for p in paras:
                    for token in p.contents:
                        if token.string is not None:
                            tokens.append(token.string)
                this_title['short_description'] = self.generate_short_description(' '.join(tokens), dest="description")
            else:
                this_title['description'] = None
                this_title['short_description'] = None

            # Merge with custom field/value
            if self.merge_comments_rule['field']:
                this_title['description'] = self.merge_comments(this_title)

            if record['cover']:
                this_title['cover'] = re.sub('&amp;', '&', record['cover'])

            this_title['prefix'] = self.discover_prefix(record)

            this_title['tags'] = []
            if record['tags']:
                this_title['tags'] = self.filter_excluded_genres(record['tags'],
                                        self.opts.exclude_genre)

            this_title['genres'] = []
            if self.opts.genre_source_field == _('Tags'):
                this_title['genres'] = this_title['tags']
            else:
                record_genres = self.db.get_field(record['id'],
                                    self.opts.genre_source_field,
                                    index_is_id=True)

                if record_genres:
                    if type(record_genres) is not list:
                        record_genres = [record_genres]

                    this_title['genres'] = self.filter_excluded_genres(record_genres,
                                            self.opts.exclude_genre)

            if record['formats']:
                formats = []
                for format in record['formats']:
                    formats.append(self.convert_html_entities(format))
                this_title['formats'] = formats

            # Add user notes to be displayed in header
            # Special case handling for datetime fields and lists
            if self.opts.header_note_source_field:
                field_md = self.db.metadata_for_field(self.opts.header_note_source_field)
                notes = self.db.get_field(record['id'],
                                    self.opts.header_note_source_field,
                                    index_is_id=True)
                if notes:
                    if field_md['datatype'] == 'text':
                        if isinstance(notes, list):
                            notes = ' &middot; '.join(notes)
                    elif field_md['datatype'] == 'datetime':
                        notes = format_date(notes, 'dd MMM yyyy')
                    this_title['notes'] = {'source': field_md['name'], 'content': notes}

            return this_title

        # Entry point

        self.opts.sort_by = 'title'
        search_phrase = ''
        if self.excluded_tags:
            search_terms = []
            for tag in self.excluded_tags:
                search_terms.append("tag:=%s" % tag)
            search_phrase = "not (%s)" % " or ".join(search_terms)

        # If a list of ids are provided, don't use search_text
        if self.opts.ids:
            self.opts.search_text = search_phrase
        else:
            if self.opts.search_text:
                self.opts.search_text += " " + search_phrase
            else:
                self.opts.search_text = search_phrase

        # Fetch the database as a dictionary
        data = self.plugin.search_sort_db(self.db, self.opts)
        data = self.process_exclusions(data)

        if self.prefix_rules and self.DEBUG:
            self.opts.log.info(" Added prefixes:")

        # Populate this_title{} from data[{},{}]
        titles = []
        for record in data:
            this_title = _populate_title(record)
            titles.append(this_title)
        return titles

    def fetch_bookmarks(self):
        """ Interrogate connected Kindle for bookmarks.

        Discover bookmarks associated with books on Kindle downloaded by calibre.
        Used in Descriptions to show reading progress, Last Read section showing date
        last read. Kindle-specific, for AZW, MOBI, TAN and TXT formats.
        Uses the system default save_template specified in
        Preferences|Add/Save|Sending to device, not a customized one specified in
        the Kindle plugin.

        Inputs:
         (): bookmarks from connected Kindle

        Output:
         bookmarked_books (dict): dict of Bookmarks
        """

        from calibre.devices.usbms.device import Device
        from calibre.devices.kindle.bookmark import Bookmark
        from calibre.ebooks.metadata import MetaInformation

        MBP_FORMATS = [u'azw', u'mobi', u'prc', u'txt']
        mbp_formats = set(MBP_FORMATS)
        PDR_FORMATS = [u'pdf']
        pdr_formats = set(PDR_FORMATS)
        TAN_FORMATS = [u'tpz', u'azw1']
        tan_formats = set(TAN_FORMATS)

        class BookmarkDevice(Device):
            def initialize(self, save_template):
                self._save_template = save_template
                self.SUPPORTS_SUB_DIRS = True

            def save_template(self):
                return self._save_template

        def _resolve_bookmark_paths(storage, path_map):
            pop_list = []
            book_ext = {}
            for id in path_map:
                file_fmts = set()
                for fmt in path_map[id]['fmts']:
                    file_fmts.add(fmt)

                bookmark_extension = None
                if file_fmts.intersection(tan_formats):
                    book_extension = list(file_fmts.intersection(tan_formats))[0]
                    bookmark_extension = 'han'
                elif file_fmts.intersection(mbp_formats):
                    book_extension = list(file_fmts.intersection(mbp_formats))[0]
                    bookmark_extension = 'mbp'
                elif file_fmts.intersection(tan_formats):
                    book_extension = list(file_fmts.intersection(tan_formats))[0]
                    bookmark_extension = 'tan'
                elif file_fmts.intersection(pdr_formats):
                    book_extension = list(file_fmts.intersection(pdr_formats))[0]
                    bookmark_extension = 'pdr'

                if bookmark_extension:
                    for vol in storage:
                        bkmk_path = path_map[id]['path'].replace(os.path.abspath('/<storage>'), vol)
                        bkmk_path = bkmk_path.replace('bookmark', bookmark_extension)
                        if os.path.exists(bkmk_path):
                            path_map[id] = bkmk_path
                            book_ext[id] = book_extension
                            break
                    else:
                        pop_list.append(id)
                else:
                    pop_list.append(id)
            # Remove non-existent bookmark templates
            for id in pop_list:
                path_map.pop(id)
            return path_map, book_ext

        self.bookmarked_books = {}
        if self.generate_recently_read:
            self.opts.log.info("     Collecting Kindle bookmarks matching catalog entries")

            d = BookmarkDevice(None)
            d.initialize(self.opts.connected_device['save_template'])

            bookmarks = {}
            for book in self.books_to_catalog:
                if 'formats' in book:
                    path_map = {}
                    id = book['id']
                    original_title = book['title'][book['title'].find(':') + 2:] if book['series'] \
                                else book['title']
                    myMeta = MetaInformation(original_title,
                                                authors=book['authors'])
                    myMeta.author_sort = book['author_sort']
                    a_path = d.create_upload_path('/<storage>', myMeta, 'x.bookmark', create_dirs=False)
                    path_map[id] = dict(path=a_path, fmts=[x.rpartition('.')[2] for x in book['formats']])

                    path_map, book_ext = _resolve_bookmark_paths(self.opts.connected_device['storage'], path_map)
                    if path_map:
                        bookmark_ext = path_map[id].rpartition('.')[2]
                        myBookmark = Bookmark(path_map[id], id, book_ext[id], bookmark_ext)
                        try:
                            book['percent_read'] = min(float(100 * myBookmark.last_read / myBookmark.book_length), 100)
                        except:
                            book['percent_read'] = 0
                        dots = int((book['percent_read'] + 5) / 10)
                        dot_string = self.SYMBOL_PROGRESS_READ * dots
                        empty_dots = self.SYMBOL_PROGRESS_UNREAD * (10 - dots)
                        book['reading_progress'] = '%s%s' % (dot_string, empty_dots)
                        bookmarks[id] = ((myBookmark, book))

            self.bookmarked_books = bookmarks

    def filter_genre_tags(self, max_len):
        """ Remove excluded tags from data set, return normalized genre list.

        Filter all db tags, removing excluded tags supplied in opts.
        Test for multiple tags resolving to same normalized form. Normalized
        tags are flattened to alphanumeric ascii_text.

        Args:
         max_len: maximum length of normalized tag to fit within OS constraints

        Return:
         genre_tags_dict (dict): dict of filtered, normalized tags in data set
        """

        def _format_tag_list(tags, indent=1, line_break=70, header='Tag list'):
            def _next_tag(sorted_tags):
                for (i, tag) in enumerate(sorted_tags):
                    if i < len(tags) - 1:
                        yield tag + ", "
                    else:
                        yield tag

            ans = '%s%d %s:\n' % (' ' * indent, len(tags), header)
            ans += ' ' * (indent + 1)
            out_str = ''
            sorted_tags = sorted(tags, key=sort_key)
            for tag in _next_tag(sorted_tags):
                out_str += tag
                if len(out_str) >= line_break:
                    ans += out_str + '\n'
                    out_str = ' ' * (indent + 1)
            return ans + out_str

        def _normalize_tag(tag, max_len):
            """ Generate an XHTML-legal anchor string from tag.

            Parse tag for non-ascii, convert to unicode name.

            Args:
             tags (str): tag name possible containing symbols
             max_len (int): maximum length of tag

            Return:
             normalized (str): unicode names substituted for non-ascii chars,
              clipped to max_len
            """

            normalized = massaged = re.sub('\s', '', ascii_text(tag).lower())
            if re.search('\W', normalized):
                normalized = ''
                for c in massaged:
                    if re.search('\W', c):
                        normalized += self.generate_unicode_name(c)
                    else:
                        normalized += c
            shortened = shorten_components_to(max_len, [normalized])[0]
            return shortened

        # Entry point
        normalized_tags = []
        friendly_tags = []
        excluded_tags = []

        # Fetch all possible genres from source field
        all_genre_tags = []
        if self.opts.genre_source_field == _('Tags'):
            all_genre_tags = self.db.all_tags()
        else:
            # Validate custom field is usable as a genre source
            field_md = self.db.metadata_for_field(self.opts.genre_source_field)
            if not field_md['datatype'] in ['enumeration', 'text']:
                all_custom_fields = self.db.custom_field_keys()
                eligible_custom_fields = []
                for cf in all_custom_fields:
                    if self.db.metadata_for_field(cf)['datatype'] in ['enumeration', 'text']:
                        eligible_custom_fields.append(cf)
                self.opts.log.error("Custom genre_source_field must be either:\n"
                                    " 'Comma separated text, like tags, shown in the browser',\n"
                                    " 'Text, column shown in the tag browser', or\n"
                                    " 'Text, but with a fixed set of permitted values'.")
                self.opts.log.error("Eligible custom fields: %s" % ', '.join(eligible_custom_fields))
                raise InvalidGenresSourceFieldException, "invalid custom field specified for genre_source_field"

            all_genre_tags = list(self.db.all_custom(self.db.field_metadata.key_to_label(self.opts.genre_source_field)))

        all_genre_tags.sort()

        for tag in all_genre_tags:
            if tag in self.excluded_tags:
                excluded_tags.append(tag)
                continue
            try:
                if re.search(self.opts.exclude_genre, tag):
                    excluded_tags.append(tag)
                    continue
            except:
                self.opts.log.error("\tfilterDbTags(): malformed --exclude-genre regex pattern: %s" % self.opts.exclude_genre)

            if tag == ' ':
                continue

            normalized_tags.append(_normalize_tag(tag, max_len))
            friendly_tags.append(tag)

        genre_tags_dict = dict(zip(friendly_tags, normalized_tags))

        # Test for multiple genres resolving to same normalized form
        normalized_set = set(normalized_tags)
        for normalized in normalized_set:
            if normalized_tags.count(normalized) > 1:
                self.opts.log.warn("      Warning: multiple tags resolving to genre '%s':" % normalized)
                for key in genre_tags_dict:
                    if genre_tags_dict[key] == normalized:
                        self.opts.log.warn("       %s" % key)
        if self.opts.verbose:
            self.opts.log.info('%s' % _format_tag_list(genre_tags_dict, header="enabled genres"))
            self.opts.log.info('%s' % _format_tag_list(excluded_tags, header="excluded genres"))

        print("genre_tags_dict: %s" % genre_tags_dict)
        return genre_tags_dict

    def filter_excluded_genres(self, tags, regex):
        """ Remove excluded tags from a tag list

        Run regex against list of tags, remove matching tags. Return filtered list.

        Args:
         tags (list): list of tags

        Return:
         tag_list(list): filtered list of tags
        """

        tag_list = []

        try:
            for tag in tags:
                tag = self.convert_html_entities(tag)
                if re.search(regex, tag):
                    continue
                else:
                    tag_list.append(tag)
        except:
            self.opts.log.error("\tfilter_excluded_genres(): malformed --exclude-genre regex pattern: %s" % regex)
            return tags

        return tag_list

    def format_ncx_text(self, description, dest=None):
        """ Massage NCX text for Kindle.

        Convert HTML entities for proper display on Kindle, convert
        '&amp;' to '&#38;' (Kindle fails).

        Args:
         description (str): string, possibly with HTM entities
         dest (kwarg): author, title or description

        Return:
         (str): massaged, possibly truncated description
        """
        # Kindle TOC descriptions won't render certain characters
        # Fix up
        massaged = unicode(BeautifulStoneSoup(description, convertEntities=BeautifulStoneSoup.HTML_ENTITIES))

        # Replace '&' with '&#38;'
        massaged = re.sub("&", "&#38;", massaged)

        if massaged.strip() and dest:
            #print traceback.print_stack(limit=3)
            return self.generate_short_description(massaged.strip(), dest=dest)
        else:
            return None

    def format_prefix(self, prefix_char):
        """ Generate HTML snippet with prefix character.

        Return a <code> snippet for Kindle, <span> snippet for EPUB.
        Optimized to preserve first-column alignment for MOBI, EPUB.

        Args:
         prefix_char (str): prefix character or None

        Return:
         (str): BeautifulSoup HTML snippet to be inserted into <p> line item entry.
        """

        soup = BeautifulSoup('')
        if self.opts.fmt == 'mobi':
            codeTag = Tag(soup, "code")
            if prefix_char is None:
                codeTag.insert(0, NavigableString('&nbsp;'))
            else:
                codeTag.insert(0, NavigableString(prefix_char))
            return codeTag
        else:
            spanTag = Tag(soup, "span")
            spanTag['class'] = "prefix"
            if prefix_char is None:
                prefix_char = "&nbsp;"
            spanTag.insert(0, NavigableString(prefix_char))
            return spanTag

    def generate_author_anchor(self, author):
        """ Generate legal XHTML anchor.

        Convert author to legal XHTML (may contain unicode chars), stripping
        non-alphanumeric chars.

        Args:
         author (str): author name

        Return:
         (str): asciized version of author
        """
        return re.sub("\W", "", ascii_text(author))

    def generate_format_args(self, book):
        """ Generate the format args for template substitution.

        self.load_section_templates imports string formatting templates of the form
        'by_*_template.py' for use in the various sections. The templates are designed to use
        format args, supplied by this method.

        Args:
         book (dict): book metadata

        Return:
         (dict): formatted args for templating
        """
        series_index = str(book['series_index'])
        if series_index.endswith('.0'):
            series_index = series_index[:-2]
        args = dict(
                title = book['title'],
                series = book['series'],
                series_index = series_index,
                rating = self.generate_rating_string(book),
                rating_parens = '(%s)' % self.generate_rating_string(book) if 'rating' in book else '',
                pubyear = book['date'].split()[1] if book['date'] else '',
                pubyear_parens = "(%s)" % book['date'].split()[1] if book['date'] else '')
        return args

    def generate_html_by_author(self):
        """ Generate content/ByAlphaAuthor.html.

        Loop through self.books_by_author, generate HTML
        with anchors for author and index letters.

        Input:
         books_by_author (list): books, sorted by author

        Output:
         content/ByAlphaAuthor.html (file)
        """

        friendly_name = _("Authors")
        self.update_progress_full_step("%s HTML" % friendly_name)

        soup = self.generate_html_empty_header(friendly_name)
        body = soup.find('body')

        btc = 0

        divTag = Tag(soup, "div")
        dtc = 0
        divOpeningTag = None
        dotc = 0
        divRunningTag = None
        drtc = 0

        # Loop through books_by_author
        # Each author/books group goes in an openingTag div (first) or
        # a runningTag div (subsequent)
        book_count = 0
        current_author = ''
        current_letter = ''
        current_series = None
        # Establish initial letter equivalencies
        sort_equivalents = self.establish_equivalencies(self.books_by_author, key='author_sort')

        for idx, book in enumerate(self.books_by_author):
            book_count += 1
            if self.letter_or_symbol(sort_equivalents[idx]) != current_letter:
                # Start a new letter with Index letter
                if divOpeningTag is not None:
                    divTag.insert(dtc, divOpeningTag)
                    dtc += 1
                    dotc = 0
                if divRunningTag is not None:
                    divTag.insert(dtc, divRunningTag)
                    dtc += 1
                    drtc = 0
                    divRunningTag = None

                author_count = 0
                divOpeningTag = Tag(soup, 'div')
                if dtc > 0:
                    divOpeningTag['class'] = "initial_letter"
                dotc = 0
                pIndexTag = Tag(soup, "p")
                pIndexTag['class'] = "author_title_letter_index"
                aTag = Tag(soup, "a")
                #current_letter = self.letter_or_symbol(book['author_sort'][0].upper())
                current_letter = self.letter_or_symbol(sort_equivalents[idx])
                if current_letter == self.SYMBOLS:
                    aTag['id'] = self.SYMBOLS + '_authors'
                    pIndexTag.insert(0, aTag)
                    pIndexTag.insert(1, NavigableString(self.SYMBOLS))
                else:
                    aTag['id'] = self.generate_unicode_name(current_letter) + '_authors'
                    pIndexTag.insert(0, aTag)
                    pIndexTag.insert(1, NavigableString(sort_equivalents[idx]))
                divOpeningTag.insert(dotc, pIndexTag)
                dotc += 1

            if book['author'] != current_author:
                # Start a new authorl
                current_author = book['author']
                author_count += 1
                if author_count >= 2:
                    # Add divOpeningTag to divTag, kill divOpeningTag
                    if divOpeningTag:
                        divTag.insert(dtc, divOpeningTag)
                        dtc += 1
                        divOpeningTag = None
                        dotc = 0

                    # Create a divRunningTag for the next author
                    if author_count > 2:
                        divTag.insert(dtc, divRunningTag)
                        dtc += 1

                    divRunningTag = Tag(soup, 'div')
                    divRunningTag['class'] = "author_logical_group"
                    drtc = 0

                non_series_books = 0
                current_series = None
                pAuthorTag = Tag(soup, "p")
                pAuthorTag['class'] = "author_index"
                aTag = Tag(soup, "a")
                aTag['id'] = "%s" % self.generate_author_anchor(current_author)
                aTag.insert(0, NavigableString(current_author))
                pAuthorTag.insert(0, aTag)
                if author_count == 1:
                    divOpeningTag.insert(dotc, pAuthorTag)
                    dotc += 1
                else:
                    divRunningTag.insert(drtc, pAuthorTag)
                    drtc += 1

            # Check for series
            if book['series'] and book['series'] != current_series:
                # Start a new series
                current_series = book['series']
                pSeriesTag = Tag(soup, 'p')
                pSeriesTag['class'] = "series"
                if self.opts.fmt == 'mobi':
                    pSeriesTag['class'] = "series_mobi"
                if self.opts.generate_series:
                    aTag = Tag(soup, 'a')
                    aTag['href'] = "%s.html#%s" % ('BySeries', self.generate_series_anchor(book['series']))
                    aTag.insert(0, book['series'])
                    pSeriesTag.insert(0, aTag)
                else:
                    pSeriesTag.insert(0, NavigableString('%s' % book['series']))

                if author_count == 1:
                    divOpeningTag.insert(dotc, pSeriesTag)
                    dotc += 1
                elif divRunningTag is not None:
                    divRunningTag.insert(drtc, pSeriesTag)
                    drtc += 1
            if current_series and not book['series']:
                current_series = None

            # Add books
            pBookTag = Tag(soup, "p")
            pBookTag['class'] = "line_item"
            ptc = 0

            pBookTag.insert(ptc, self.format_prefix(book['prefix']))
            ptc += 1

            spanTag = Tag(soup, "span")
            spanTag['class'] = "entry"
            stc = 0

            aTag = Tag(soup, "a")
            if self.opts.generate_descriptions:
                aTag['href'] = "book_%d.html" % (int(float(book['id'])))

            # Generate the title from the template
            args = self.generate_format_args(book)
            if current_series:
                #aTag.insert(0,'%s%s' % (escape(book['title'][len(book['series'])+1:]),pubyear))
                formatted_title = self.by_authors_series_title_template.format(**args).rstrip()
            else:
                #aTag.insert(0,'%s%s' % (escape(book['title']), pubyear))
                formatted_title = self.by_authors_normal_title_template.format(**args).rstrip()
                non_series_books += 1
            aTag.insert(0, NavigableString(escape(formatted_title)))

            spanTag.insert(ptc, aTag)
            stc += 1
            pBookTag.insert(ptc, spanTag)
            ptc += 1

            if author_count == 1:
                divOpeningTag.insert(dotc, pBookTag)
                dotc += 1
            elif divRunningTag:
                divRunningTag.insert(drtc, pBookTag)
                drtc += 1

        # loop ends here

        pTag = Tag(soup, "p")
        pTag['class'] = 'title'
        ptc = 0
        aTag = Tag(soup, 'a')
        aTag['id'] = 'section_start'
        pTag.insert(ptc, aTag)
        ptc += 1

        if not self.generate_for_kindle_mobi:
            # Kindle don't need this because it shows section titles in Periodical format
            aTag = Tag(soup, "a")
            anchor_name = friendly_name.lower()
            aTag['id'] = anchor_name.replace(" ", "")
            pTag.insert(ptc, aTag)
            ptc += 1
            pTag.insert(ptc, NavigableString('%s' % (friendly_name)))

        body.insert(btc, pTag)
        btc += 1

        if author_count == 1:
            divTag.insert(dtc, divOpeningTag)
            dtc += 1
        elif divRunningTag is not None:
            divTag.insert(dtc, divRunningTag)
            dtc += 1

        # Add the divTag to the body
        body.insert(btc, divTag)

        # Write the generated file to content_dir
        outfile_spec = "%s/ByAlphaAuthor.html" % (self.content_dir)
        outfile = open(outfile_spec, 'w')
        outfile.write(soup.prettify())
        outfile.close()
        self.html_filelist_1.append("content/ByAlphaAuthor.html")

    def generate_html_by_date_added(self):
        """ Generate content/ByDateAdded.html.

        Loop through self.books_to_catalog sorted by reverse date, generate HTML.

        Input:
         books_by_title (list): books, sorted by title

        Output:
         content/ByDateAdded.html (file)
        """

        def _add_books_to_html_by_month(this_months_list, dtc):
            if len(this_months_list):
                # Determine the longest author_sort_length before sorting
                asl = [i['author_sort'] for i in this_months_list]
                las = max(asl, key=len)
                this_months_list = sorted(this_months_list,
                    key=lambda x: sort_key(self._kf_books_by_author_sorter_author_sort(x, len(las))))

                # Create a new month anchor
                date_string = strftime(u'%B %Y', current_date.timetuple())
                pIndexTag = Tag(soup, "p")
                pIndexTag['class'] = "date_index"
                aTag = Tag(soup, "a")
                aTag['id'] = "bda_%s-%s" % (current_date.year, current_date.month)
                pIndexTag.insert(0, aTag)
                pIndexTag.insert(1, NavigableString(date_string))
                divTag.insert(dtc, pIndexTag)
                dtc += 1
                current_author = None
                current_series = None

                for new_entry in this_months_list:
                    if new_entry['author'] != current_author:
                        # Start a new author
                        current_author = new_entry['author']
                        non_series_books = 0
                        current_series = None
                        pAuthorTag = Tag(soup, "p")
                        pAuthorTag['class'] = "author_index"
                        aTag = Tag(soup, "a")
                        if self.opts.generate_authors:
                            aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generate_author_anchor(current_author))
                        aTag.insert(0, NavigableString(current_author))
                        pAuthorTag.insert(0, aTag)
                        divTag.insert(dtc, pAuthorTag)
                        dtc += 1

                    # Check for series
                    if new_entry['series'] and new_entry['series'] != current_series:
                        # Start a new series
                        current_series = new_entry['series']
                        pSeriesTag = Tag(soup, 'p')
                        pSeriesTag['class'] = "series"
                        if self.opts.fmt == 'mobi':
                            pSeriesTag['class'] = "series_mobi"
                        if self.opts.generate_series:
                            aTag = Tag(soup, 'a')
                            aTag['href'] = "%s.html#%s" % ('BySeries', self.generate_series_anchor(new_entry['series']))
                            aTag.insert(0, new_entry['series'])
                            pSeriesTag.insert(0, aTag)
                        else:
                            pSeriesTag.insert(0, NavigableString('%s' % new_entry['series']))
                        divTag.insert(dtc, pSeriesTag)
                        dtc += 1
                    if current_series and not new_entry['series']:
                        current_series = None

                    # Add books
                    pBookTag = Tag(soup, "p")
                    pBookTag['class'] = "line_item"
                    ptc = 0

                    pBookTag.insert(ptc, self.format_prefix(new_entry['prefix']))
                    ptc += 1

                    spanTag = Tag(soup, "span")
                    spanTag['class'] = "entry"
                    stc = 0

                    aTag = Tag(soup, "a")
                    if self.opts.generate_descriptions:
                        aTag['href'] = "book_%d.html" % (int(float(new_entry['id'])))

                    # Generate the title from the template
                    args = self.generate_format_args(new_entry)
                    if current_series:
                        formatted_title = self.by_month_added_series_title_template.format(**args).rstrip()
                    else:
                        formatted_title = self.by_month_added_normal_title_template.format(**args).rstrip()
                        non_series_books += 1
                    aTag.insert(0, NavigableString(escape(formatted_title)))
                    spanTag.insert(stc, aTag)
                    stc += 1

                    pBookTag.insert(ptc, spanTag)
                    ptc += 1

                    divTag.insert(dtc, pBookTag)
                    dtc += 1
            return dtc

        def _add_books_to_html_by_date_range(date_range_list, date_range, dtc):
            if len(date_range_list):
                pIndexTag = Tag(soup, "p")
                pIndexTag['class'] = "date_index"
                aTag = Tag(soup, "a")
                aTag['id'] = "bda_%s" % date_range.replace(' ', '')
                pIndexTag.insert(0, aTag)
                pIndexTag.insert(1, NavigableString(date_range))
                divTag.insert(dtc, pIndexTag)
                dtc += 1

                for new_entry in date_range_list:
                    # Add books
                    pBookTag = Tag(soup, "p")
                    pBookTag['class'] = "line_item"
                    ptc = 0

                    pBookTag.insert(ptc, self.format_prefix(new_entry['prefix']))
                    ptc += 1

                    spanTag = Tag(soup, "span")
                    spanTag['class'] = "entry"
                    stc = 0

                    aTag = Tag(soup, "a")
                    if self.opts.generate_descriptions:
                        aTag['href'] = "book_%d.html" % (int(float(new_entry['id'])))

                    # Generate the title from the template
                    args = self.generate_format_args(new_entry)
                    if new_entry['series']:
                        formatted_title = self.by_recently_added_series_title_template.format(**args).rstrip()
                    else:
                        formatted_title = self.by_recently_added_normal_title_template.format(**args).rstrip()
                    aTag.insert(0, NavigableString(escape(formatted_title)))
                    spanTag.insert(stc, aTag)
                    stc += 1

                    # Dot
                    spanTag.insert(stc, NavigableString(" &middot; "))
                    stc += 1

                    # Link to author
                    emTag = Tag(soup, "em")
                    aTag = Tag(soup, "a")
                    if self.opts.generate_authors:
                        aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generate_author_anchor(new_entry['author']))
                    aTag.insert(0, NavigableString(new_entry['author']))
                    emTag.insert(0, aTag)
                    spanTag.insert(stc, emTag)
                    stc += 1

                    pBookTag.insert(ptc, spanTag)
                    ptc += 1

                    divTag.insert(dtc, pBookTag)
                    dtc += 1
            return dtc

        friendly_name = _("Recently Added")
        self.update_progress_full_step("%s HTML" % friendly_name)

        soup = self.generate_html_empty_header(friendly_name)
        body = soup.find('body')

        btc = 0

        pTag = Tag(soup, "p")
        pTag['class'] = 'title'
        ptc = 0

        aTag = Tag(soup, 'a')
        aTag['id'] = 'section_start'
        pTag.insert(ptc, aTag)
        ptc += 1

        if not self.generate_for_kindle_mobi:
            # Kindle don't need this because it shows section titles in Periodical format
            aTag = Tag(soup, "a")
            anchor_name = friendly_name.lower()
            aTag['id'] = anchor_name.replace(" ", "")

            pTag.insert(ptc, aTag)
            ptc += 1
            pTag.insert(ptc, NavigableString('%s' % friendly_name))

        body.insert(btc, pTag)
        btc += 1

        divTag = Tag(soup, "div")
        dtc = 0

        # >>> Books by date range <<<
        if self.use_series_prefix_in_titles_section:
            self.books_by_date_range = sorted(self.books_to_catalog,
                                key=lambda x: (x['timestamp'], x['timestamp']), reverse=True)
        else:
            nspt = deepcopy(self.books_to_catalog)
            self.books_by_date_range = sorted(nspt, key=lambda x: (x['timestamp'], x['timestamp']), reverse=True)

        date_range_list = []
        today_time = nowf().replace(hour=23, minute=59, second=59)
        for (i, date) in enumerate(self.DATE_RANGE):
            date_range_limit = self.DATE_RANGE[i]
            if i:
                date_range = '%d to %d days ago' % (self.DATE_RANGE[i - 1], self.DATE_RANGE[i])
            else:
                date_range = 'Last %d days' % (self.DATE_RANGE[i])

            for book in self.books_by_date_range:
                book_time = book['timestamp']
                delta = today_time - book_time
                if delta.days <= date_range_limit:
                    date_range_list.append(book)
                else:
                    break

            dtc = _add_books_to_html_by_date_range(date_range_list, date_range, dtc)
            date_range_list = [book]

        # >>>> Books by month <<<<
        # Sort titles case-insensitive for by month using series prefix
        self.books_by_month = sorted(self.books_to_catalog,
                                key=lambda x: (x['timestamp'], x['timestamp']), reverse=True)

        # Loop through books by date
        current_date = datetime.date.fromordinal(1)
        this_months_list = []
        for book in self.books_by_month:
            if book['timestamp'].month != current_date.month or \
                book['timestamp'].year != current_date.year:
                dtc = _add_books_to_html_by_month(this_months_list, dtc)
                this_months_list = []
                current_date = book['timestamp'].date()
            this_months_list.append(book)

        # Add the last month's list
        _add_books_to_html_by_month(this_months_list, dtc)

        # Add the divTag to the body
        body.insert(btc, divTag)

        # Write the generated file to content_dir
        outfile_spec = "%s/ByDateAdded.html" % (self.content_dir)
        outfile = open(outfile_spec, 'w')
        outfile.write(soup.prettify())
        outfile.close()
        self.html_filelist_2.append("content/ByDateAdded.html")

    def generate_html_by_date_read(self):
        """ Generate content/ByDateRead.html.

        Create self.bookmarked_books_by_date_read from self.bookmarked_books.
        Loop through self.bookmarked_books_by_date_read, generate HTML.

        Input:
         bookmarked_books_by_date_read (list)

        Output:
         content/ByDateRead.html (file)
        """

        def _add_books_to_html_by_day(todays_list, dtc):
            if len(todays_list):
                # Create a new day anchor
                date_string = strftime(u'%A, %B %d', current_date.timetuple())
                pIndexTag = Tag(soup, "p")
                pIndexTag['class'] = "date_index"
                aTag = Tag(soup, "a")
                aTag['name'] = "bdr_%s-%s-%s" % (current_date.year, current_date.month, current_date.day)
                pIndexTag.insert(0, aTag)
                pIndexTag.insert(1, NavigableString(date_string))
                divTag.insert(dtc, pIndexTag)
                dtc += 1

                for new_entry in todays_list:
                    pBookTag = Tag(soup, "p")
                    pBookTag['class'] = "date_read"
                    ptc = 0

                    # Percent read
                    pBookTag.insert(ptc, NavigableString(new_entry['reading_progress']))
                    ptc += 1

                    aTag = Tag(soup, "a")
                    if self.opts.generate_descriptions:
                        aTag['href'] = "book_%d.html" % (int(float(new_entry['id'])))
                    aTag.insert(0, escape(new_entry['title']))
                    pBookTag.insert(ptc, aTag)
                    ptc += 1

                    # Dot
                    pBookTag.insert(ptc, NavigableString(" &middot; "))
                    ptc += 1

                    # Link to author
                    emTag = Tag(soup, "em")
                    aTag = Tag(soup, "a")
                    if self.opts.generate_authors:
                        aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generate_author_anchor(new_entry['author']))
                    aTag.insert(0, NavigableString(new_entry['author']))
                    emTag.insert(0, aTag)
                    pBookTag.insert(ptc, emTag)
                    ptc += 1

                    divTag.insert(dtc, pBookTag)
                    dtc += 1
            return dtc

        def _add_books_to_html_by_date_range(date_range_list, date_range, dtc):
            if len(date_range_list):
                pIndexTag = Tag(soup, "p")
                pIndexTag['class'] = "date_index"
                aTag = Tag(soup, "a")
                aTag['name'] = "bdr_%s" % date_range.replace(' ', '')
                pIndexTag.insert(0, aTag)
                pIndexTag.insert(1, NavigableString(date_range))
                divTag.insert(dtc, pIndexTag)
                dtc += 1

                for new_entry in date_range_list:
                    # Add books
                    pBookTag = Tag(soup, "p")
                    pBookTag['class'] = "date_read"
                    ptc = 0

                    # Percent read
                    dots = int((new_entry['percent_read'] + 5) / 10)
                    dot_string = self.SYMBOL_PROGRESS_READ * dots
                    empty_dots = self.SYMBOL_PROGRESS_UNREAD * (10 - dots)
                    pBookTag.insert(ptc, NavigableString('%s%s' % (dot_string, empty_dots)))
                    ptc += 1

                    aTag = Tag(soup, "a")
                    if self.opts.generate_descriptions:
                        aTag['href'] = "book_%d.html" % (int(float(new_entry['id'])))
                    aTag.insert(0, escape(new_entry['title']))
                    pBookTag.insert(ptc, aTag)
                    ptc += 1

                    # Dot
                    pBookTag.insert(ptc, NavigableString(" &middot; "))
                    ptc += 1

                    # Link to author
                    emTag = Tag(soup, "em")
                    aTag = Tag(soup, "a")
                    if self.opts.generate_authors:
                        aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generate_author_anchor(new_entry['author']))
                    aTag.insert(0, NavigableString(new_entry['author']))
                    emTag.insert(0, aTag)
                    pBookTag.insert(ptc, emTag)
                    ptc += 1

                    divTag.insert(dtc, pBookTag)
                    dtc += 1
            return dtc

        friendly_name = _('Recently Read')
        self.update_progress_full_step("%s HTML" % friendly_name)

        if not self.bookmarked_books:
            return

        soup = self.generate_html_empty_header(friendly_name)
        body = soup.find('body')

        btc = 0

        # Insert section tag
        aTag = Tag(soup, 'a')
        aTag['name'] = 'section_start'
        body.insert(btc, aTag)
        btc += 1

        # Insert the anchor
        aTag = Tag(soup, "a")
        anchor_name = friendly_name.lower()
        aTag['name'] = anchor_name.replace(" ", "")
        body.insert(btc, aTag)
        btc += 1

        divTag = Tag(soup, "div")
        dtc = 0

        # self.bookmarked_books: (Bookmark, book)
        bookmarked_books = []
        for bm_book in self.bookmarked_books:
            book = self.bookmarked_books[bm_book]
            #print "bm_book: %s" % bm_book
            book[1]['bookmark_timestamp'] = book[0].timestamp
            try:
                book[1]['percent_read'] = min(float(100 * book[0].last_read / book[0].book_length), 100)
            except:
                book[1]['percent_read'] = 0
            bookmarked_books.append(book[1])

        self.bookmarked_books_by_date_read = sorted(bookmarked_books,
                            key=lambda x: (x['bookmark_timestamp'], x['bookmark_timestamp']), reverse=True)

        # >>>> Recently read by day <<<<
        current_date = datetime.date.fromordinal(1)
        todays_list = []
        for book in self.bookmarked_books_by_date_read:
            bookmark_time = datetime.datetime.utcfromtimestamp(book['bookmark_timestamp'])
            if bookmark_time.day != current_date.day or \
                bookmark_time.month != current_date.month or \
                bookmark_time.year != current_date.year:
                dtc = _add_books_to_html_by_day(todays_list, dtc)
                todays_list = []
                current_date = datetime.datetime.utcfromtimestamp(book['bookmark_timestamp']).date()
            todays_list.append(book)

        # Add the last day's list
        _add_books_to_html_by_day(todays_list, dtc)

        # Add the divTag to the body
        body.insert(btc, divTag)

        # Write the generated file to content_dir
        outfile_spec = "%s/ByDateRead.html" % (self.content_dir)
        outfile = open(outfile_spec, 'w')
        outfile.write(soup.prettify())
        outfile.close()
        self.html_filelist_2.append("content/ByDateRead.html")

    def generate_html_by_genres(self):
        """ Generate individual HTML files per tag.

        Filter out excluded tags. For each tag qualifying as a genre,
        create a separate HTML file. Normalize tags to flatten synonymous tags.

        Inputs:
         self.genre_tags_dict (list): all genre tags

        Output:
         (files): HTML file per genre
        """

        self.update_progress_full_step(_("Genres HTML"))

        # Extract books matching filtered_tags
        genre_list = []
        for friendly_tag in sorted(self.genre_tags_dict, key=sort_key):
            #print("\ngenerate_html_by_genres(): looking for books with friendly_tag '%s'" % friendly_tag)
            # tag_list => { normalized_genre_tag : [{book},{},{}],
            #               normalized_genre_tag : [{book},{},{}] }

            tag_list = {}
            for book in self.books_by_author:
                # Scan each book for tag matching friendly_tag
                if 'genres' in book and friendly_tag in book['genres']:
                    this_book = {}
                    this_book['author'] = book['author']
                    this_book['title'] = book['title']
                    this_book['author_sort'] = capitalize(book['author_sort'])
                    this_book['prefix'] = book['prefix']
                    this_book['tags'] = book['tags']
                    this_book['id'] = book['id']
                    this_book['series'] = book['series']
                    this_book['series_index'] = book['series_index']
                    this_book['date'] = book['date']
                    normalized_tag = self.genre_tags_dict[friendly_tag]
                    genre_tag_list = [key for genre in genre_list for key in genre]
                    if normalized_tag in genre_tag_list:
                        for existing_genre in genre_list:
                            for key in existing_genre:
                                new_book = None
                                if key == normalized_tag:
                                    for book in existing_genre[key]:
                                        if book['title'] == this_book['title']:
                                            new_book = False
                                            break
                                    else:
                                        new_book = True
                                if new_book:
                                    existing_genre[key].append(this_book)
                    else:
                        tag_list[normalized_tag] = [this_book]
                        genre_list.append(tag_list)

        if self.opts.verbose:
            if len(genre_list):
                self.opts.log.info("  Genre summary: %d active genre tags used in generating catalog with %d titles" %
                                (len(genre_list), len(self.books_to_catalog)))

                for genre in genre_list:
                    for key in genre:
                        self.opts.log.info("   %s: %d %s" % (self.get_friendly_genre_tag(key),
                                            len(genre[key]),
                                            'titles' if len(genre[key]) > 1 else 'title'))

        # Write the results
        # genre_list = [ {friendly_tag:[{book},{book}]}, {friendly_tag:[{book},{book}]}, ...]
        master_genre_list = []
        for genre_tag_set in genre_list:
            for (index, genre) in enumerate(genre_tag_set):
                #print "genre: %s  \t  genre_tag_set[genre]: %s" % (genre, genre_tag_set[genre])

                # Create sorted_authors[0] = friendly, [1] = author_sort for NCX creation
                authors = []
                for book in genre_tag_set[genre]:
                    authors.append((book['author'], book['author_sort']))

                # authors[] contains a list of all book authors, with multiple entries for multiple books by author
                # Create unique_authors with a count of books per author as the third tuple element
                books_by_current_author = 1
                current_author = authors[0]
                unique_authors = []
                for (i, author) in enumerate(authors):
                    if author != current_author and i:
                        unique_authors.append((current_author[0], current_author[1], books_by_current_author))
                        current_author = author
                        books_by_current_author = 1
                    elif i == 0 and len(authors) == 1:
                        # Allow for single-book lists
                        unique_authors.append((current_author[0], current_author[1], books_by_current_author))
                    else:
                        books_by_current_author += 1

                # Write the genre book list as an article
                outfile = "%s/Genre_%s.html" % (self.content_dir, genre)
                titles_spanned = self.generate_html_by_genre(genre,
                                                             True if index == 0 else False,
                                                             genre_tag_set[genre],
                                                             outfile)

                tag_file = "content/Genre_%s.html" % genre
                master_genre_list.append({
                                            'tag': genre,
                                            'file': tag_file,
                                            'authors': unique_authors,
                                            'books': genre_tag_set[genre],
                                            'titles_spanned': titles_spanned})

        self.genres = master_genre_list

    def generate_html_by_genre(self, genre, section_head, books, outfile):
        """ Generate individual genre HTML file.

        Generate an individual genre HTML file. Called from generate_html_by_genres()

        Args:
         genre (str): genre name
         section_head (bool): True if starting section
         books (dict): list of books in genre
         outfile (str): full pathname to output file

        Results:
         (file): Genre HTML file written

        Returns:
         titles_spanned (list): [(first_author, first_book), (last_author, last_book)]
        """

        soup = self.generate_html_genre_header(genre)
        body = soup.find('body')

        btc = 0
        divTag = Tag(soup, 'div')
        dtc = 0

        # Insert section tag if this is the section start - first article only
        if section_head:
            aTag = Tag(soup, 'a')
            aTag['id'] = 'section_start'
            divTag.insert(dtc, aTag)
            dtc += 1
            #body.insert(btc, aTag)
            #btc += 1

        # Create an anchor from the tag
        aTag = Tag(soup, 'a')
        aTag['id'] = "Genre_%s" % genre
        divTag.insert(dtc, aTag)
        body.insert(btc, divTag)
        btc += 1

        titleTag = body.find(attrs={'class': 'title'})
        titleTag.insert(0, NavigableString('%s' % escape(self.get_friendly_genre_tag(genre))))

        # Insert the books by author list
        divTag = body.find(attrs={'class': 'authors'})
        dtc = 0

        current_author = ''
        current_series = None
        for book in books:
            if book['author'] != current_author:
                # Start a new author with link
                current_author = book['author']
                non_series_books = 0
                current_series = None
                pAuthorTag = Tag(soup, "p")
                pAuthorTag['class'] = "author_index"
                aTag = Tag(soup, "a")
                if self.opts.generate_authors:
                    aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generate_author_anchor(book['author']))
                aTag.insert(0, book['author'])
                pAuthorTag.insert(0, aTag)
                divTag.insert(dtc, pAuthorTag)
                dtc += 1

            # Check for series
            if book['series'] and book['series'] != current_series:
                # Start a new series
                current_series = book['series']
                pSeriesTag = Tag(soup, 'p')
                pSeriesTag['class'] = "series"
                if self.opts.fmt == 'mobi':
                    pSeriesTag['class'] = "series_mobi"
                if self.opts.generate_series:
                    aTag = Tag(soup, 'a')
                    aTag['href'] = "%s.html#%s" % ('BySeries', self.generate_series_anchor(book['series']))
                    aTag.insert(0, book['series'])
                    pSeriesTag.insert(0, aTag)
                else:
                    pSeriesTag.insert(0, NavigableString('%s' % book['series']))
                divTag.insert(dtc, pSeriesTag)
                dtc += 1

            if current_series and not book['series']:
                current_series = None

            # Add books
            pBookTag = Tag(soup, "p")
            pBookTag['class'] = "line_item"
            ptc = 0

            pBookTag.insert(ptc, self.format_prefix(book['prefix']))
            ptc += 1

            spanTag = Tag(soup, "span")
            spanTag['class'] = "entry"
            stc = 0

            # Add the book title
            aTag = Tag(soup, "a")
            if self.opts.generate_descriptions:
                aTag['href'] = "book_%d.html" % (int(float(book['id'])))

            # Generate the title from the template
            args = self.generate_format_args(book)
            if current_series:
                #aTag.insert(0,escape(book['title'][len(book['series'])+1:]))
                formatted_title = self.by_genres_series_title_template.format(**args).rstrip()
            else:
                #aTag.insert(0,escape(book['title']))
                formatted_title = self.by_genres_normal_title_template.format(**args).rstrip()
                non_series_books += 1
            aTag.insert(0, NavigableString(escape(formatted_title)))

            spanTag.insert(stc, aTag)
            stc += 1

            pBookTag.insert(ptc, spanTag)
            ptc += 1

            divTag.insert(dtc, pBookTag)
            dtc += 1

        # Write the generated file to content_dir
        outfile = open(outfile, 'w')
        outfile.write(soup.prettify())
        outfile.close()

        if len(books) > 1:
            titles_spanned = [(books[0]['author'], books[0]['title']), (books[-1]['author'], books[-1]['title'])]
        else:
            titles_spanned = [(books[0]['author'], books[0]['title'])]

        return titles_spanned

    def generate_html_by_series(self):
        """ Generate content/BySeries.html.

        Search database for books in series.

        Input:
         database

        Output:
         content/BySeries.html (file)

        """
        friendly_name = _("Series")
        self.update_progress_full_step("%s HTML" % friendly_name)

        self.opts.sort_by = 'series'

        # *** Convert the existing database, resort by series/index ***
        self.books_by_series = [i for i in self.books_to_catalog if i['series']]
        self.books_by_series = sorted(self.books_by_series, key=lambda x: sort_key(self._kf_books_by_series_sorter(x)))

        if not self.books_by_series:
            self.opts.generate_series = False
            self.opts.log("  no series found in selected books, skipping Series section")
            return

        # Generate series_sort
        for book in self.books_by_series:
            book['series_sort'] = self.generate_sort_title(book['series'])

        # Establish initial letter equivalencies
        sort_equivalents = self.establish_equivalencies(self.books_by_series, key='series_sort')

        soup = self.generate_html_empty_header(friendly_name)
        body = soup.find('body')

        btc = 0
        divTag = Tag(soup, "div")
        dtc = 0
        current_letter = ""
        current_series = None

        # Loop through books_by_series
        series_count = 0
        for idx, book in enumerate(self.books_by_series):
            # Check for initial letter change
            if self.letter_or_symbol(sort_equivalents[idx]) != current_letter:
                # Start a new letter with Index letter
                current_letter = self.letter_or_symbol(sort_equivalents[idx])
                pIndexTag = Tag(soup, "p")
                pIndexTag['class'] = "series_letter_index"
                aTag = Tag(soup, "a")
                if current_letter == self.SYMBOLS:
                    aTag['id'] = self.SYMBOLS + "_series"
                    pIndexTag.insert(0, aTag)
                    pIndexTag.insert(1, NavigableString(self.SYMBOLS))
                else:
                    aTag['id'] = self.generate_unicode_name(current_letter) + "_series"
                    pIndexTag.insert(0, aTag)
                    pIndexTag.insert(1, NavigableString(sort_equivalents[idx]))
                divTag.insert(dtc, pIndexTag)
                dtc += 1
            # Check for series change
            if book['series'] != current_series:
                # Start a new series
                series_count += 1
                current_series = book['series']
                pSeriesTag = Tag(soup, 'p')
                pSeriesTag['class'] = "series"
                if self.opts.fmt == 'mobi':
                    pSeriesTag['class'] = "series_mobi"
                aTag = Tag(soup, 'a')
                aTag['id'] = self.generate_series_anchor(book['series'])
                pSeriesTag.insert(0, aTag)
                pSeriesTag.insert(1, NavigableString('%s' % book['series']))
                divTag.insert(dtc, pSeriesTag)
                dtc += 1

            # Add books
            pBookTag = Tag(soup, "p")
            pBookTag['class'] = "line_item"
            ptc = 0

            book['prefix'] = self.discover_prefix(book)
            pBookTag.insert(ptc, self.format_prefix(book['prefix']))
            ptc += 1

            spanTag = Tag(soup, "span")
            spanTag['class'] = "entry"
            stc = 0

            aTag = Tag(soup, "a")
            if self.opts.generate_descriptions:
                aTag['href'] = "book_%d.html" % (int(float(book['id'])))
            # Use series, series index if avail else just title
            #aTag.insert(0,'%d. %s &middot; %s' % (book['series_index'],escape(book['title']), ' & '.join(book['authors'])))

            args = self.generate_format_args(book)
            formatted_title = self.by_series_title_template.format(**args).rstrip()
            aTag.insert(0, NavigableString(escape(formatted_title)))

            spanTag.insert(stc, aTag)
            stc += 1

            # &middot;
            spanTag.insert(stc, NavigableString(' &middot; '))
            stc += 1

            # Link to author
            aTag = Tag(soup, "a")
            if self.opts.generate_authors:
                aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor",
                                            self.generate_author_anchor(escape(' & '.join(book['authors']))))
            aTag.insert(0, NavigableString(' &amp; '.join(book['authors'])))
            spanTag.insert(stc, aTag)
            stc += 1

            pBookTag.insert(ptc, spanTag)
            ptc += 1

            divTag.insert(dtc, pBookTag)
            dtc += 1

        pTag = Tag(soup, "p")
        pTag['class'] = 'title'
        ptc = 0
        aTag = Tag(soup, 'a')
        aTag['id'] = 'section_start'
        pTag.insert(ptc, aTag)
        ptc += 1

        if not self.generate_for_kindle_mobi:
            # Insert the <h2> tag with book_count at the head
            aTag = Tag(soup, "a")
            anchor_name = friendly_name.lower()
            aTag['id'] = anchor_name.replace(" ", "")
            pTag.insert(0, aTag)
            pTag.insert(1, NavigableString('%s' % friendly_name))
        body.insert(btc, pTag)
        btc += 1

        # Add the divTag to the body
        body.insert(btc, divTag)

        # Write the generated file to content_dir
        outfile_spec = "%s/BySeries.html" % (self.content_dir)
        outfile = open(outfile_spec, 'w')
        outfile.write(soup.prettify())
        outfile.close()
        self.html_filelist_1.append("content/BySeries.html")

    def generate_html_by_title(self):
        """ Generate content/ByAlphaTitle.html.

        Generate HTML of books sorted by title.

        Input:
         books_by_title

        Output:
         content/ByAlphaTitle.html (file)
        """

        self.update_progress_full_step(_("Titles HTML"))

        soup = self.generate_html_empty_header("Books By Alpha Title")
        body = soup.find('body')
        btc = 0

        pTag = Tag(soup, "p")
        pTag['class'] = 'title'
        ptc = 0
        aTag = Tag(soup, 'a')
        aTag['id'] = 'section_start'
        pTag.insert(ptc, aTag)
        ptc += 1

        if not self.generate_for_kindle_mobi:
            # Kindle don't need this because it shows section titles in Periodical format
            aTag = Tag(soup, "a")
            aTag['id'] = "bytitle"
            pTag.insert(ptc, aTag)
            ptc += 1
            pTag.insert(ptc, NavigableString(_('Titles')))

        body.insert(btc, pTag)
        btc += 1

        divTag = Tag(soup, "div")
        dtc = 0
        current_letter = ""

        # Re-sort title list without leading series/series_index
        # Incoming title <series> <series_index>: <title>
        if not self.use_series_prefix_in_titles_section:
            nspt = deepcopy(self.books_to_catalog)
            nspt = sorted(nspt, key=lambda x: sort_key(x['title_sort'].upper()))
            self.books_by_title_no_series_prefix = nspt

        # Establish initial letter equivalencies
        sort_equivalents = self.establish_equivalencies(self.books_by_title, key='title_sort')

        # Loop through the books by title
        # Generate one divRunningTag per initial letter for the purposes of
        # minimizing widows and orphans on readers that can handle large
        # <divs> styled as inline-block
        title_list = self.books_by_title
        if not self.use_series_prefix_in_titles_section:
            title_list = self.books_by_title_no_series_prefix
        drtc = 0
        divRunningTag = None
        for idx, book in enumerate(title_list):
            if self.letter_or_symbol(sort_equivalents[idx]) != current_letter:
                # Start a new letter
                if drtc and divRunningTag is not None:
                    divTag.insert(dtc, divRunningTag)
                    dtc += 1
                divRunningTag = Tag(soup, 'div')
                if dtc > 0:
                    divRunningTag['class'] = "initial_letter"
                drtc = 0
                pIndexTag = Tag(soup, "p")
                pIndexTag['class'] = "author_title_letter_index"
                aTag = Tag(soup, "a")
                current_letter = self.letter_or_symbol(sort_equivalents[idx])
                if current_letter == self.SYMBOLS:
                    aTag['id'] = self.SYMBOLS + "_titles"
                    pIndexTag.insert(0, aTag)
                    pIndexTag.insert(1, NavigableString(self.SYMBOLS))
                else:
                    aTag['id'] = self.generate_unicode_name(current_letter) + "_titles"
                    pIndexTag.insert(0, aTag)
                    pIndexTag.insert(1, NavigableString(sort_equivalents[idx]))
                divRunningTag.insert(dtc, pIndexTag)
                drtc += 1

            # Add books
            pBookTag = Tag(soup, "p")
            pBookTag['class'] = "line_item"
            ptc = 0

            pBookTag.insert(ptc, self.format_prefix(book['prefix']))
            ptc += 1

            spanTag = Tag(soup, "span")
            spanTag['class'] = "entry"
            stc = 0

            # Link to book
            aTag = Tag(soup, "a")
            if self.opts.generate_descriptions:
                aTag['href'] = "book_%d.html" % (int(float(book['id'])))

            # Generate the title from the template
            args = self.generate_format_args(book)
            if book['series']:
                formatted_title = self.by_titles_series_title_template.format(**args).rstrip()
            else:
                formatted_title = self.by_titles_normal_title_template.format(**args).rstrip()
            aTag.insert(0, NavigableString(escape(formatted_title)))
            spanTag.insert(stc, aTag)
            stc += 1

            # Dot
            spanTag.insert(stc, NavigableString(" &middot; "))
            stc += 1

            # Link to author
            emTag = Tag(soup, "em")
            aTag = Tag(soup, "a")
            if self.opts.generate_authors:
                aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generate_author_anchor(book['author']))
            aTag.insert(0, NavigableString(book['author']))
            emTag.insert(0, aTag)
            spanTag.insert(stc, emTag)
            stc += 1

            pBookTag.insert(ptc, spanTag)
            ptc += 1

            if divRunningTag is not None:
                divRunningTag.insert(drtc, pBookTag)
            drtc += 1

        # Add the last divRunningTag to divTag
        if divRunningTag is not None:
            divTag.insert(dtc, divRunningTag)
            dtc += 1

        # Add the divTag to the body
        body.insert(btc, divTag)
        btc += 1

        # Write the volume to content_dir
        outfile_spec = "%s/ByAlphaTitle.html" % (self.content_dir)
        outfile = open(outfile_spec, 'w')
        outfile.write(soup.prettify())
        outfile.close()
        self.html_filelist_1.append("content/ByAlphaTitle.html")

    def generate_html_description_header(self, book):
        """ Generate the HTML Description header from template.

        Create HTML Description from book metadata and template.
        Called by generate_html_descriptions()

        Args:
         book (dict): book metadata

        Return:
         soup (BeautifulSoup): HTML Description for book
        """

        from calibre.ebooks.oeb.base import XHTML_NS

        def _generate_html():
            args = dict(
                        author=author,
                        author_prefix=author_prefix,
                        comments=comments,
                        css=css,
                        formats=formats,
                        genres=genres,
                        note_content=note_content,
                        note_source=note_source,
                        pubdate=pubdate,
                        publisher=publisher,
                        pubmonth=pubmonth,
                        pubyear=pubyear,
                        rating=rating,
                        series=series,
                        series_index=series_index,
                        thumb=thumb,
                        title=title,
                        title_str=title_str,
                        xmlns=XHTML_NS,
                        )
            for k, v in args.iteritems():
                if isbytestring(v):
                    args[k] = v.decode('utf-8')
            generated_html = P('catalog/template.xhtml',
                    data=True).decode('utf-8').format(**args)
            generated_html = substitute_entites(generated_html)
            return BeautifulSoup(generated_html)

        # Generate the template arguments
        css = P('catalog/stylesheet.css', data=True).decode('utf-8')
        title_str = title = escape(book['title'])
        series = ''
        series_index = ''
        if book['series']:
            series = escape(book['series'])
            series_index = str(book['series_index'])
            if series_index.endswith('.0'):
                series_index = series_index[:-2]

        # Author, author_prefix (read|reading|none symbol or missing symbol)
        author = book['author']

        if book['prefix']:
            author_prefix = book['prefix'] + ' ' + _("by ")
        elif self.opts.connected_kindle and book['id'] in self.bookmarked_books:
            author_prefix = self.SYMBOL_READING + ' ' + _("by ")
        else:
            author_prefix = _("by ")

        # Genres
        genres = ''
        if 'genres' in book:
            _soup = BeautifulSoup('')
            genresTag = Tag(_soup, 'p')
            gtc = 0
            for (i, tag) in enumerate(sorted(book.get('genres', []))):
                aTag = Tag(_soup, 'a')
                if self.opts.generate_genres:
                    aTag['href'] = "Genre_%s.html" % self.genre_tags_dict[tag]
                aTag.insert(0, escape(NavigableString(tag)))
                genresTag.insert(gtc, aTag)
                gtc += 1
                if i < len(book['genres']) - 1:
                    genresTag.insert(gtc, NavigableString(' &middot; '))
                    gtc += 1
            genres = genresTag.renderContents()

        # Formats
        formats = []
        if 'formats' in book:
            for format in sorted(book['formats']):
                formats.append(format.rpartition('.')[2].upper())
            formats = ' &middot; '.join(formats)

        # Date of publication
        if book['date']:
            pubdate = book['date']
            pubmonth, pubyear = pubdate.split()
        else:
            pubdate = pubyear = pubmonth = ''

        # Thumb
        _soup = BeautifulSoup('<html>', selfClosingTags=['img'])
        thumb = Tag(_soup, "img")
        if 'cover' in book and book['cover']:
            thumb['src'] = "../images/thumbnail_%d.jpg" % int(book['id'])
        else:
            thumb['src'] = "../images/thumbnail_default.jpg"
        thumb['alt'] = "cover thumbnail"

        # Publisher
        publisher = ' '
        if 'publisher' in book:
            publisher = book['publisher']

        # Rating
        stars = int(book['rating']) / 2
        rating = ''
        if stars:
            star_string = self.SYMBOL_FULL_RATING * stars
            empty_stars = self.SYMBOL_EMPTY_RATING * (5 - stars)
            rating = '%s%s <br/>' % (star_string, empty_stars)

        # Notes
        note_source = ''
        note_content = ''
        if 'notes' in book:
            note_source = book['notes']['source']
            note_content = book['notes']['content']

        # Comments
        comments = ''
        if 'description' in book and book['description'] > '':
            comments = book['description']

        # >>>> Populate the template <<<<
        soup = _generate_html()

        # >>>> Post-process the template <<<<
        body = soup.find('body')
        btc = 0
        # Insert the title anchor for inbound links
        aTag = Tag(soup, "a")
        aTag['id'] = "book%d" % int(book['id'])
        divTag = Tag(soup, 'div')
        divTag.insert(0, aTag)
        body.insert(btc, divTag)
        btc += 1

        # Insert the link to the series or remove <a class="series">
        aTag = body.find('a', attrs={'class': 'series_id'})
        if aTag:
            if book['series']:
                if self.opts.generate_series:
                    aTag['href'] = "%s.html#%s" % ('BySeries', self.generate_series_anchor(book['series']))
            else:
                aTag.extract()

        # Insert the author link
        aTag = body.find('a', attrs={'class': 'author'})
        if self.opts.generate_authors and aTag:
            aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor",
                                        self.generate_author_anchor(book['author']))

        if publisher == ' ':
            publisherTag = body.find('td', attrs={'class': 'publisher'})
            if publisherTag:
                publisherTag.contents[0].replaceWith('&nbsp;')

        if not genres:
            genresTag = body.find('p', attrs={'class': 'genres'})
            if genresTag:
                genresTag.extract()

        if not formats:
            formatsTag = body.find('p', attrs={'class': 'formats'})
            if formatsTag:
                formatsTag.extract()

        if note_content == '':
            tdTag = body.find('td', attrs={'class': 'notes'})
            if tdTag:
                tdTag.contents[0].replaceWith('&nbsp;')

        emptyTags = body.findAll('td', attrs={'class': 'empty'})
        for mt in emptyTags:
            newEmptyTag = Tag(BeautifulSoup(), 'td')
            newEmptyTag.insert(0, NavigableString('&nbsp;'))
            mt.replaceWith(newEmptyTag)

        return soup

    def generate_html_descriptions(self):
        """ Generate Description HTML for each book.

        Loop though books, write Description HTML for each book.

        Inputs:
         books_by_title (list)

        Output:
         (files): Description HTML for each book
        """

        self.update_progress_full_step(_("Descriptions HTML"))

        for (title_num, title) in enumerate(self.books_by_title):
            self.update_progress_micro_step("%s %d of %d" %
                                            (_("Description HTML"),
                                            title_num, len(self.books_by_title)),
                                            float(title_num * 100 / len(self.books_by_title)) / 100)

            # Generate the header from user-customizable template
            soup = self.generate_html_description_header(title)

            # Write the book entry to content_dir
            outfile = open("%s/book_%d.html" % (self.content_dir, int(title['id'])), 'w')
            outfile.write(soup.prettify())
            outfile.close()

    def generate_html_empty_header(self, title):
        """ Return a boilerplate HTML header.

        Generate an HTML header with document title.

        Args:
         title (str): document title

        Return:
         soup (BeautifulSoup): HTML header with document title inserted
        """

        header = '''
            <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
            <html xmlns="http://www.w3.org/1999/xhtml" xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata">
            <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
                <link rel="stylesheet" type="text/css" href="stylesheet.css" media="screen" />
            <title></title>
            </head>
            <body>
            </body>
            </html>
            '''
        # Insert the supplied title
        soup = BeautifulSoup(header)
        titleTag = soup.find('title')
        titleTag.insert(0, NavigableString(title))
        return soup

    def generate_html_genre_header(self, title):
        """ Generate HTML header with initial body content

        Start with a generic HTML header, add <p> and <div>

        Args:
         title (str): document title

        Return:
         soup (BeautifulSoup): HTML with initial <p> and <div> tags
        """

        soup = self.generate_html_empty_header(title)
        bodyTag = soup.find('body')
        pTag = Tag(soup, 'p')
        pTag['class'] = 'title'
        bodyTag.insert(0, pTag)
        divTag = Tag(soup, 'div')
        divTag['class'] = 'authors'
        bodyTag.insert(1, divTag)
        return soup

    def generate_masthead_image(self, out_path):
        """ Generate a Kindle masthead image.

        Generate a Kindle masthead image, used with Kindle periodical format.

        Args:
         out_path (str): path to write generated masthead image

        Input:
         opts.catalog_title (str): Title to render
         masthead_font: User-specified font preference (MOBI output option)

        Output:
         out_path (file): masthead image (GIF)
        """

        from calibre.ebooks.conversion.config import load_defaults

        MI_WIDTH = 600
        MI_HEIGHT = 60

        font_path = default_font = P('fonts/liberation/LiberationSerif-Bold.ttf')
        recs = load_defaults('mobi_output')
        masthead_font_family = recs.get('masthead_font', 'Default')

        if masthead_font_family != 'Default':
            from calibre.utils.fonts.scanner import font_scanner
            faces = font_scanner.fonts_for_family(masthead_font_family)
            if faces:
                font_path = faces[0]['path']

        if not font_path or not os.access(font_path, os.R_OK):
            font_path = default_font

        try:
            from PIL import Image, ImageDraw, ImageFont
            Image, ImageDraw, ImageFont
        except ImportError:
            import Image, ImageDraw, ImageFont

        img = Image.new('RGB', (MI_WIDTH, MI_HEIGHT), 'white')
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(font_path, 48)
        except:
            self.opts.log.error("     Failed to load user-specifed font '%s'" % font_path)
            font = ImageFont.truetype(default_font, 48)
        text = self.opts.catalog_title.encode('utf-8')
        width, height = draw.textsize(text, font=font)
        left = max(int((MI_WIDTH - width) / 2.), 0)
        top = max(int((MI_HEIGHT - height) / 2.), 0)
        draw.text((left, top), text, fill=(0, 0, 0), font=font)
        img.save(open(out_path, 'wb'), 'GIF')

    def generate_ncx_header(self):
        """ Generate the basic NCX file.

        Generate the initial NCX, which is added to depending on included Sections.

        Inputs:
         None

        Updated:
         play_order (int)

        Outputs:
         ncx_soup (file): NCX foundation
        """

        self.update_progress_full_step(_("NCX header"))

        header = '''
            <?xml version="1.0" encoding="utf-8"?>
            <ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata" version="2005-1" xml:lang="en">
            </ncx>
        '''
        soup = BeautifulStoneSoup(header, selfClosingTags=['content', 'calibre:meta-img'])

        ncx = soup.find('ncx')
        navMapTag = Tag(soup, 'navMap')

        if self.generate_for_kindle_mobi:
            # Build a top-level navPoint for Kindle periodicals
            navPointTag = Tag(soup, 'navPoint')
            navPointTag['class'] = "periodical"
            navPointTag['id'] = "title"
            navPointTag['playOrder'] = self.play_order
            self.play_order += 1
            navLabelTag = Tag(soup, 'navLabel')
            textTag = Tag(soup, 'text')
            textTag.insert(0, NavigableString(self.opts.catalog_title))
            navLabelTag.insert(0, textTag)
            navPointTag.insert(0, navLabelTag)

            if self.opts.generate_authors:
                contentTag = Tag(soup, 'content')
                contentTag['src'] = "content/ByAlphaAuthor.html"
                navPointTag.insert(1, contentTag)
            elif self.opts.generate_titles:
                contentTag = Tag(soup, 'content')
                contentTag['src'] = "content/ByAlphaTitle.html"
                navPointTag.insert(1, contentTag)
            elif self.opts.generate_series:
                contentTag = Tag(soup, 'content')
                contentTag['src'] = "content/BySeries.html"
                navPointTag.insert(1, contentTag)
            elif self.opts.generate_genres:
                contentTag = Tag(soup, 'content')
                #contentTag['src'] = "content/ByGenres.html"
                contentTag['src'] = "%s" % self.genres[0]['file']
                navPointTag.insert(1, contentTag)
            elif self.opts.generate_recently_added:
                contentTag = Tag(soup, 'content')
                contentTag['src'] = "content/ByDateAdded.html"
                navPointTag.insert(1, contentTag)
            elif self.opts.generate_descriptions:
                # Descriptions only
                contentTag = Tag(soup, 'content')
                contentTag['src'] = "content/book_%d.html" % int(self.books_by_description[0]['id'])
                navPointTag.insert(1, contentTag)

            if self.generate_for_kindle_mobi:
                cmiTag = Tag(soup, '%s' % 'calibre:meta-img')
                cmiTag['id'] = "mastheadImage"
                cmiTag['src'] = "images/mastheadImage.gif"
                navPointTag.insert(2, cmiTag)
            navMapTag.insert(0, navPointTag)

        ncx.insert(0, navMapTag)
        self.ncx_soup = soup

    def generate_ncx_descriptions(self, tocTitle):
        """ Add Descriptions to the basic NCX file.

        Generate the Descriptions NCX content, add to self.ncx_soup.

        Inputs:
         books_by_author (list)

        Updated:
         play_order (int)

        Outputs:
         ncx_soup (file): updated
        """

        self.update_progress_full_step(_("NCX for Descriptions"))

        # --- Construct the 'Descriptions' section ---
        ncx_soup = self.ncx_soup
        if self.generate_for_kindle_mobi:
            body = ncx_soup.find("navPoint")
        else:
            body = ncx_soup.find('navMap')
        btc = len(body.contents)

        # Add the section navPoint
        navPointTag = Tag(ncx_soup, 'navPoint')
        if self.generate_for_kindle_mobi:
            navPointTag['class'] = "section"
        navPointTag['id'] = "bydescription-ID"
        navPointTag['playOrder'] = self.play_order
        self.play_order += 1
        navLabelTag = Tag(ncx_soup, 'navLabel')
        textTag = Tag(ncx_soup, 'text')
        section_header = '%s [%d]' % (tocTitle, len(self.books_by_description))
        if self.generate_for_kindle_mobi:
            section_header = tocTitle
        textTag.insert(0, NavigableString(section_header))
        navLabelTag.insert(0, textTag)
        nptc = 0
        navPointTag.insert(nptc, navLabelTag)
        nptc += 1
        contentTag = Tag(ncx_soup, "content")
        contentTag['src'] = "content/book_%d.html" % int(self.books_by_description[0]['id'])
        navPointTag.insert(nptc, contentTag)
        nptc += 1

        # Loop over the titles

        for book in self.books_by_description:
            navPointVolumeTag = Tag(ncx_soup, 'navPoint')
            if self.generate_for_kindle_mobi:
                navPointVolumeTag['class'] = "article"
            navPointVolumeTag['id'] = "book%dID" % int(book['id'])
            navPointVolumeTag['playOrder'] = self.play_order
            self.play_order += 1
            navLabelTag = Tag(ncx_soup, "navLabel")
            textTag = Tag(ncx_soup, "text")
            if book['series']:
                series_index = str(book['series_index'])
                if series_index.endswith('.0'):
                    series_index = series_index[:-2]
                if self.generate_for_kindle_mobi:
                    # Don't include Author for Kindle
                    textTag.insert(0, NavigableString(self.format_ncx_text('%s (%s [%s])' %
                                    (book['title'], book['series'], series_index), dest='title')))
                else:
                    # Include Author for non-Kindle
                    textTag.insert(0, NavigableString(self.format_ncx_text('%s (%s [%s]) &middot; %s ' %
                                    (book['title'], book['series'], series_index, book['author']), dest='title')))
            else:
                if self.generate_for_kindle_mobi:
                    # Don't include Author for Kindle
                    title_str = self.format_ncx_text('%s' % (book['title']), dest='title')
                    if self.opts.connected_kindle and book['id'] in self.bookmarked_books:
                        '''
                        dots = int((book['percent_read'] + 5)/10)
                        dot_string = '+' * dots
                        empty_dots = '-' * (10 - dots)
                        title_str += ' %s%s' % (dot_string,empty_dots)
                        '''
                        title_str += '*'
                    textTag.insert(0, NavigableString(title_str))
                else:
                    # Include Author for non-Kindle
                    textTag.insert(0, NavigableString(self.format_ncx_text('%s &middot; %s' % \
                                                    (book['title'], book['author']), dest='title')))
            navLabelTag.insert(0, textTag)
            navPointVolumeTag.insert(0, navLabelTag)

            contentTag = Tag(ncx_soup, "content")
            contentTag['src'] = "content/book_%d.html#book%d" % (int(book['id']), int(book['id']))
            navPointVolumeTag.insert(1, contentTag)

            if self.generate_for_kindle_mobi:
                # Add the author tag
                cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                cmTag['name'] = "author"

                if book['date']:
                    navStr = '%s | %s' % (self.format_ncx_text(book['author'], dest='author'),
                            book['date'].split()[1])
                else:
                    navStr = '%s' % (self.format_ncx_text(book['author'], dest='author'))

                if 'tags' in book and len(book['tags']):
                    navStr = self.format_ncx_text(navStr + ' | ' + ' &middot; '.join(sorted(book['tags'])), dest='author')
                cmTag.insert(0, NavigableString(navStr))
                navPointVolumeTag.insert(2, cmTag)

                # Add the description tag
                if book['short_description']:
                    cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                    cmTag['name'] = "description"
                    cmTag.insert(0, NavigableString(self.format_ncx_text(book['short_description'], dest='description')))
                    navPointVolumeTag.insert(3, cmTag)

            # Add this volume to the section tag
            navPointTag.insert(nptc, navPointVolumeTag)
            nptc += 1

        # Add this section to the body
        body.insert(btc, navPointTag)
        btc += 1

        self.ncx_soup = ncx_soup

    def generate_ncx_by_series(self, tocTitle):
        """ Add Series to the basic NCX file.

        Generate the Series NCX content, add to self.ncx_soup.

        Inputs:
         books_by_series (list)

        Updated:
         play_order (int)

        Outputs:
         ncx_soup (file): updated
        """

        self.update_progress_full_step(_("NCX for Series"))

        def _add_to_series_by_letter(current_series_list):
            current_series_list = " &bull; ".join(current_series_list)
            current_series_list = self.format_ncx_text(current_series_list, dest="description")
            series_by_letter.append(current_series_list)

        ncx_soup = self.ncx_soup
        output = "BySeries"
        if self.generate_for_kindle_mobi:
            body = ncx_soup.find("navPoint")
        else:
            body = ncx_soup.find('navMap')
        btc = len(body.contents)

        # --- Construct the 'Books By Series' section ---
        navPointTag = Tag(ncx_soup, 'navPoint')
        if self.generate_for_kindle_mobi:
            navPointTag['class'] = "section"
        navPointTag['id'] = "byseries-ID"
        navPointTag['playOrder'] = self.play_order
        self.play_order += 1
        navLabelTag = Tag(ncx_soup, 'navLabel')
        textTag = Tag(ncx_soup, 'text')
        section_header = '%s [%d]' % (tocTitle, len(self.all_series))
        if self.generate_for_kindle_mobi:
            section_header = tocTitle
        textTag.insert(0, NavigableString(section_header))
        navLabelTag.insert(0, textTag)
        nptc = 0
        navPointTag.insert(nptc, navLabelTag)
        nptc += 1
        contentTag = Tag(ncx_soup, "content")
        contentTag['src'] = "content/%s.html#section_start" % (output)
        navPointTag.insert(nptc, contentTag)
        nptc += 1

        series_by_letter = []
        # Establish initial letter equivalencies
        sort_equivalents = self.establish_equivalencies(self.books_by_series, key='series_sort')

        # Loop over the series titles, find start of each letter, add description_preview_count books
        # Special switch for using different title list

        title_list = self.books_by_series

        # Prime the pump
        current_letter = self.letter_or_symbol(sort_equivalents[0])

        title_letters = [current_letter]
        current_series_list = []
        current_series = ""
        for idx, book in enumerate(title_list):
            sort_title = self.generate_sort_title(book['series'])
            self.establish_equivalencies([sort_title])[0]
            if self.letter_or_symbol(sort_equivalents[idx]) != current_letter:

                # Save the old list
                _add_to_series_by_letter(current_series_list)

                # Start the new list
                current_letter = self.letter_or_symbol(sort_equivalents[idx])
                title_letters.append(current_letter)
                current_series = book['series']
                current_series_list = [book['series']]
            else:
                if len(current_series_list) < self.opts.description_clip and \
                    book['series'] != current_series:
                    current_series = book['series']
                    current_series_list.append(book['series'])

        # Add the last book list
        _add_to_series_by_letter(current_series_list)

        # Add *article* entries for each populated series title letter
        for (i, books) in enumerate(series_by_letter):
            navPointByLetterTag = Tag(ncx_soup, 'navPoint')
            if self.generate_for_kindle_mobi:
                navPointByLetterTag['class'] = "article"
            navPointByLetterTag['id'] = "%sSeries-ID" % (title_letters[i].upper())
            navPointTag['playOrder'] = self.play_order
            self.play_order += 1
            navLabelTag = Tag(ncx_soup, 'navLabel')
            textTag = Tag(ncx_soup, 'text')
            if len(title_letters[i]) > 1:
                fmt_string = _(u"Series beginning with %s")
            else:
                fmt_string = _(u"Series beginning with '%s'")
            textTag.insert(0, NavigableString(fmt_string %
                (title_letters[i] if len(title_letters[i]) > 1 else title_letters[i])))
            navLabelTag.insert(0, textTag)
            navPointByLetterTag.insert(0, navLabelTag)
            contentTag = Tag(ncx_soup, 'content')
            #contentTag['src'] = "content/%s.html#%s_series" % (output, title_letters[i])
            if title_letters[i] == self.SYMBOLS:
                contentTag['src'] = "content/%s.html#%s_series" % (output, self.SYMBOLS)
            else:
                contentTag['src'] = "content/%s.html#%s_series" % (output, self.generate_unicode_name(title_letters[i]))

            navPointByLetterTag.insert(1, contentTag)

            if self.generate_for_kindle_mobi:
                cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                cmTag['name'] = "description"
                cmTag.insert(0, NavigableString(self.format_ncx_text(books, dest='description')))
                navPointByLetterTag.insert(2, cmTag)

            navPointTag.insert(nptc, navPointByLetterTag)
            nptc += 1

        # Add this section to the body
        body.insert(btc, navPointTag)
        btc += 1

        self.ncx_soup = ncx_soup

    def generate_ncx_by_title(self, tocTitle):
        """ Add Titles to the basic NCX file.

        Generate the Titles NCX content, add to self.ncx_soup.

        Inputs:
         books_by_title (list)

        Updated:
         play_order (int)

        Outputs:
         ncx_soup (file): updated
        """

        self.update_progress_full_step(_("NCX for Titles"))

        def _add_to_books_by_letter(current_book_list):
            current_book_list = " &bull; ".join(current_book_list)
            current_book_list = self.format_ncx_text(current_book_list, dest="description")
            books_by_letter.append(current_book_list)

        ncx_soup = self.ncx_soup
        output = "ByAlphaTitle"
        if self.generate_for_kindle_mobi:
            body = ncx_soup.find("navPoint")
        else:
            body = ncx_soup.find('navMap')
        btc = len(body.contents)

        # --- Construct the 'Books By Title' section ---
        navPointTag = Tag(ncx_soup, 'navPoint')
        if self.generate_for_kindle_mobi:
            navPointTag['class'] = "section"
        navPointTag['id'] = "byalphatitle-ID"
        navPointTag['playOrder'] = self.play_order
        self.play_order += 1
        navLabelTag = Tag(ncx_soup, 'navLabel')
        textTag = Tag(ncx_soup, 'text')
        section_header = '%s [%d]' % (tocTitle, len(self.books_by_title))
        if self.generate_for_kindle_mobi:
            section_header = tocTitle
        textTag.insert(0, NavigableString(section_header))
        navLabelTag.insert(0, textTag)
        nptc = 0
        navPointTag.insert(nptc, navLabelTag)
        nptc += 1
        contentTag = Tag(ncx_soup, "content")
        contentTag['src'] = "content/%s.html#section_start" % (output)
        navPointTag.insert(nptc, contentTag)
        nptc += 1

        books_by_letter = []

        # Establish initial letter equivalencies
        sort_equivalents = self.establish_equivalencies(self.books_by_title, key='title_sort')

        # Loop over the titles, find start of each letter, add description_preview_count books
        # Special switch for using different title list
        if self.use_series_prefix_in_titles_section:
            title_list = self.books_by_title
        else:
            title_list = self.books_by_title_no_series_prefix

        # Prime the list
        current_letter = self.letter_or_symbol(sort_equivalents[0])
        title_letters = [current_letter]
        current_book_list = []
        current_book = ""
        for idx, book in enumerate(title_list):
            #if self.letter_or_symbol(book['title_sort'][0]) != current_letter:
            if self.letter_or_symbol(sort_equivalents[idx]) != current_letter:

                # Save the old list
                _add_to_books_by_letter(current_book_list)

                # Start the new list
                #current_letter = self.letter_or_symbol(book['title_sort'][0])
                current_letter = self.letter_or_symbol(sort_equivalents[idx])
                title_letters.append(current_letter)
                current_book = book['title']
                current_book_list = [book['title']]
            else:
                if len(current_book_list) < self.opts.description_clip and \
                    book['title'] != current_book:
                    current_book = book['title']
                    current_book_list.append(book['title'])

        # Add the last book list
        _add_to_books_by_letter(current_book_list)

        # Add *article* entries for each populated title letter
        for (i, books) in enumerate(books_by_letter):
            navPointByLetterTag = Tag(ncx_soup, 'navPoint')
            if self.generate_for_kindle_mobi:
                navPointByLetterTag['class'] = "article"
            navPointByLetterTag['id'] = "%sTitles-ID" % (title_letters[i].upper())
            navPointTag['playOrder'] = self.play_order
            self.play_order += 1
            navLabelTag = Tag(ncx_soup, 'navLabel')
            textTag = Tag(ncx_soup, 'text')
            if len(title_letters[i]) > 1:
                fmt_string = _(u"Titles beginning with %s")
            else:
                fmt_string = _(u"Titles beginning with '%s'")
            textTag.insert(0, NavigableString(fmt_string %
                (title_letters[i] if len(title_letters[i]) > 1 else title_letters[i])))
            navLabelTag.insert(0, textTag)
            navPointByLetterTag.insert(0, navLabelTag)
            contentTag = Tag(ncx_soup, 'content')
            if title_letters[i] == self.SYMBOLS:
                contentTag['src'] = "content/%s.html#%s_titles" % (output, self.SYMBOLS)
            else:
                contentTag['src'] = "content/%s.html#%s_titles" % (output, self.generate_unicode_name(title_letters[i]))
            navPointByLetterTag.insert(1, contentTag)

            if self.generate_for_kindle_mobi:
                cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                cmTag['name'] = "description"
                cmTag.insert(0, NavigableString(self.format_ncx_text(books, dest='description')))
                navPointByLetterTag.insert(2, cmTag)

            navPointTag.insert(nptc, navPointByLetterTag)
            nptc += 1

        # Add this section to the body
        body.insert(btc, navPointTag)
        btc += 1

        self.ncx_soup = ncx_soup

    def generate_ncx_by_author(self, tocTitle):
        """ Add Authors to the basic NCX file.

        Generate the Authors NCX content, add to self.ncx_soup.

        Inputs:
         authors (list)

        Updated:
         play_order (int)

        Outputs:
         ncx_soup (file): updated
        """

        self.update_progress_full_step(_("NCX for Authors"))

        def _add_to_author_list(current_author_list, current_letter):
            current_author_list = " &bull; ".join(current_author_list)
            current_author_list = self.format_ncx_text(current_author_list, dest="description")
            master_author_list.append((current_author_list, current_letter))

        ncx_soup = self.ncx_soup
        HTML_file = "content/ByAlphaAuthor.html"
        if self.generate_for_kindle_mobi:
            body = ncx_soup.find("navPoint")
        else:
            body = ncx_soup.find('navMap')
        btc = len(body.contents)

        # --- Construct the 'Books By Author' *section* ---
        navPointTag = Tag(ncx_soup, 'navPoint')
        if self.generate_for_kindle_mobi:
            navPointTag['class'] = "section"
        file_ID = "%s" % tocTitle.lower()
        file_ID = file_ID.replace(" ", "")
        navPointTag['id'] = "%s-ID" % file_ID
        navPointTag['playOrder'] = self.play_order
        self.play_order += 1
        navLabelTag = Tag(ncx_soup, 'navLabel')
        textTag = Tag(ncx_soup, 'text')
        section_header = '%s [%d]' % (tocTitle, len(self.individual_authors))
        if self.generate_for_kindle_mobi:
            section_header = tocTitle
        textTag.insert(0, NavigableString(section_header))
        navLabelTag.insert(0, textTag)
        nptc = 0
        navPointTag.insert(nptc, navLabelTag)
        nptc += 1
        contentTag = Tag(ncx_soup, "content")
        contentTag['src'] = "%s#section_start" % HTML_file
        navPointTag.insert(nptc, contentTag)
        nptc += 1

        # Create an NCX article entry for each populated author index letter
        # Loop over the sorted_authors list, find start of each letter,
        # add description_preview_count artists
        # self.authors[0]:friendly [1]:author_sort [2]:book_count
        # (<friendly name>, author_sort, book_count)

        # Need to extract a list of author_sort, generate sort_equivalents from that
        sort_equivalents = self.establish_equivalencies([x[1] for x in self.authors])

        master_author_list = []
        # Prime the pump
        current_letter = self.letter_or_symbol(sort_equivalents[0])
        current_author_list = []
        for idx, author in enumerate(self.authors):
            if self.letter_or_symbol(sort_equivalents[idx]) != current_letter:
                # Save the old list
                _add_to_author_list(current_author_list, current_letter)

                # Start the new list
                current_letter = self.letter_or_symbol(sort_equivalents[idx])
                current_author_list = [author[0]]
            else:
                if len(current_author_list) < self.opts.description_clip:
                    current_author_list.append(author[0])

        # Add the last author list
        _add_to_author_list(current_author_list, current_letter)

        # Add *article* entries for each populated author initial letter
        # master_author_list{}: [0]:author list [1]:Initial letter
        for authors_by_letter in master_author_list:
            navPointByLetterTag = Tag(ncx_soup, 'navPoint')
            if self.generate_for_kindle_mobi:
                navPointByLetterTag['class'] = "article"
            navPointByLetterTag['id'] = "%sauthors-ID" % (authors_by_letter[1])
            navPointTag['playOrder'] = self.play_order
            self.play_order += 1
            navLabelTag = Tag(ncx_soup, 'navLabel')
            textTag = Tag(ncx_soup, 'text')
            if authors_by_letter[1] == self.SYMBOLS:
                fmt_string = _(u"Authors beginning with %s")
            else:
                fmt_string = _(u"Authors beginning with '%s'")
            textTag.insert(0, NavigableString(fmt_string % authors_by_letter[1]))
            navLabelTag.insert(0, textTag)
            navPointByLetterTag.insert(0, navLabelTag)
            contentTag = Tag(ncx_soup, 'content')
            if authors_by_letter[1] == self.SYMBOLS:
                contentTag['src'] = "%s#%s_authors" % (HTML_file, authors_by_letter[1])
            else:
                contentTag['src'] = "%s#%s_authors" % (HTML_file, self.generate_unicode_name(authors_by_letter[1]))
            navPointByLetterTag.insert(1, contentTag)

            if self.generate_for_kindle_mobi:
                cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                cmTag['name'] = "description"
                cmTag.insert(0, NavigableString(authors_by_letter[0]))
                navPointByLetterTag.insert(2, cmTag)

            navPointTag.insert(nptc, navPointByLetterTag)
            nptc += 1

        # Add this section to the body
        body.insert(btc, navPointTag)
        btc += 1

        self.ncx_soup = ncx_soup

    def generate_ncx_by_date_added(self, tocTitle):
        """ Add Recently Added to the basic NCX file.

        Generate the Recently Added NCX content, add to self.ncx_soup.

        Inputs:
         books_by_date_range (list)

        Updated:
         play_order (int)

        Outputs:
         ncx_soup (file): updated
        """

        self.update_progress_full_step(_("NCX for Recently Added"))

        def _add_to_master_month_list(current_titles_list):
            book_count = len(current_titles_list)
            current_titles_list = " &bull; ".join(current_titles_list)
            current_titles_list = self.format_ncx_text(current_titles_list, dest='description')
            master_month_list.append((current_titles_list, current_date, book_count))

        def _add_to_master_date_range_list(current_titles_list):
            book_count = len(current_titles_list)
            current_titles_list = " &bull; ".join(current_titles_list)
            current_titles_list = self.format_ncx_text(current_titles_list, dest='description')
            master_date_range_list.append((current_titles_list, date_range, book_count))

        ncx_soup = self.ncx_soup
        HTML_file = "content/ByDateAdded.html"
        if self.generate_for_kindle_mobi:
            body = ncx_soup.find("navPoint")
        else:
            body = ncx_soup.find('navMap')
        btc = len(body.contents)

        # --- Construct the 'Recently Added' *section* ---
        navPointTag = Tag(ncx_soup, 'navPoint')
        if self.generate_for_kindle_mobi:
            navPointTag['class'] = "section"
        file_ID = "%s" % tocTitle.lower()
        file_ID = file_ID.replace(" ", "")
        navPointTag['id'] = "%s-ID" % file_ID
        navPointTag['playOrder'] = self.play_order
        self.play_order += 1
        navLabelTag = Tag(ncx_soup, 'navLabel')
        textTag = Tag(ncx_soup, 'text')
        textTag.insert(0, NavigableString('%s' % tocTitle))
        navLabelTag.insert(0, textTag)
        nptc = 0
        navPointTag.insert(nptc, navLabelTag)
        nptc += 1
        contentTag = Tag(ncx_soup, "content")
        contentTag['src'] = "%s#section_start" % HTML_file
        navPointTag.insert(nptc, contentTag)
        nptc += 1

        # Create an NCX article entry for each date range
        current_titles_list = []
        master_date_range_list = []
        today = datetime.datetime.now()
        today_time = datetime.datetime(today.year, today.month, today.day)
        for (i, date) in enumerate(self.DATE_RANGE):
            if i:
                date_range = '%d to %d days ago' % (self.DATE_RANGE[i - 1], self.DATE_RANGE[i])
            else:
                date_range = 'Last %d days' % (self.DATE_RANGE[i])
            date_range_limit = self.DATE_RANGE[i]
            for book in self.books_by_date_range:
                book_time = datetime.datetime(book['timestamp'].year, book['timestamp'].month, book['timestamp'].day)
                if (today_time - book_time).days <= date_range_limit:
                    #print "generate_ncx_by_date_added: %s added %d days ago" % (book['title'], (today_time-book_time).days)
                    current_titles_list.append(book['title'])
                else:
                    break
            if current_titles_list:
                _add_to_master_date_range_list(current_titles_list)
            current_titles_list = [book['title']]

        # Add *article* entries for each populated date range
        # master_date_range_list{}: [0]:titles list [1]:datestr
        for books_by_date_range in master_date_range_list:
            navPointByDateRangeTag = Tag(ncx_soup, 'navPoint')
            if self.generate_for_kindle_mobi:
                navPointByDateRangeTag['class'] = "article"
            navPointByDateRangeTag['id'] = "%s-ID" % books_by_date_range[1].replace(' ', '')
            navPointTag['playOrder'] = self.play_order
            self.play_order += 1
            navLabelTag = Tag(ncx_soup, 'navLabel')
            textTag = Tag(ncx_soup, 'text')
            textTag.insert(0, NavigableString(books_by_date_range[1]))
            navLabelTag.insert(0, textTag)
            navPointByDateRangeTag.insert(0, navLabelTag)
            contentTag = Tag(ncx_soup, 'content')
            contentTag['src'] = "%s#bda_%s" % (HTML_file,
                books_by_date_range[1].replace(' ', ''))

            navPointByDateRangeTag.insert(1, contentTag)

            if self.generate_for_kindle_mobi:
                cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                cmTag['name'] = "description"
                cmTag.insert(0, NavigableString(books_by_date_range[0]))
                navPointByDateRangeTag.insert(2, cmTag)

                cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                cmTag['name'] = "author"
                navStr = '%d titles' % books_by_date_range[2] if books_by_date_range[2] > 1 else \
                            '%d title' % books_by_date_range[2]
                cmTag.insert(0, NavigableString(navStr))
                navPointByDateRangeTag.insert(3, cmTag)

            navPointTag.insert(nptc, navPointByDateRangeTag)
            nptc += 1

        # Create an NCX article entry for each populated month
        # Loop over the booksByDate list, find start of each month,
        # add description_preview_count titles
        # master_month_list(list,date,count)
        current_titles_list = []
        master_month_list = []
        current_date = self.books_by_month[0]['timestamp']

        for book in self.books_by_month:
            if book['timestamp'].month != current_date.month or \
                book['timestamp'].year != current_date.year:
                # Save the old lists
                _add_to_master_month_list(current_titles_list)

                # Start the new list
                current_date = book['timestamp'].date()
                current_titles_list = [book['title']]
            else:
                current_titles_list.append(book['title'])

        # Add the last month list
        _add_to_master_month_list(current_titles_list)

        # Add *article* entries for each populated month
        # master_months_list{}: [0]:titles list [1]:date
        for books_by_month in master_month_list:
            datestr = strftime(u'%B %Y', books_by_month[1].timetuple())
            navPointByMonthTag = Tag(ncx_soup, 'navPoint')
            if self.generate_for_kindle_mobi:
                navPointByMonthTag['class'] = "article"
            navPointByMonthTag['id'] = "bda_%s-%s-ID" % (books_by_month[1].year, books_by_month[1].month)
            navPointTag['playOrder'] = self.play_order
            self.play_order += 1
            navLabelTag = Tag(ncx_soup, 'navLabel')
            textTag = Tag(ncx_soup, 'text')
            textTag.insert(0, NavigableString(datestr))
            navLabelTag.insert(0, textTag)
            navPointByMonthTag.insert(0, navLabelTag)
            contentTag = Tag(ncx_soup, 'content')
            contentTag['src'] = "%s#bda_%s-%s" % (HTML_file,
                books_by_month[1].year, books_by_month[1].month)

            navPointByMonthTag.insert(1, contentTag)

            if self.generate_for_kindle_mobi:
                cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                cmTag['name'] = "description"
                cmTag.insert(0, NavigableString(books_by_month[0]))
                navPointByMonthTag.insert(2, cmTag)

                cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                cmTag['name'] = "author"
                navStr = '%d titles' % books_by_month[2] if books_by_month[2] > 1 else \
                            '%d title' % books_by_month[2]
                cmTag.insert(0, NavigableString(navStr))
                navPointByMonthTag.insert(3, cmTag)

            navPointTag.insert(nptc, navPointByMonthTag)
            nptc += 1

        # Add this section to the body
        body.insert(btc, navPointTag)
        btc += 1
        self.ncx_soup = ncx_soup

    def generate_ncx_by_date_read(self, tocTitle):
        """ Add By Date Read to the basic NCX file.

        Generate the By Date Read NCX content (Kindle only), add to self.ncx_soup.

        Inputs:
         bookmarked_books_by_date_read (list)

        Updated:
         play_order (int)

        Outputs:
         ncx_soup (file): updated
        """

        def _add_to_master_day_list(current_titles_list):
            book_count = len(current_titles_list)
            current_titles_list = " &bull; ".join(current_titles_list)
            current_titles_list = self.format_ncx_text(current_titles_list, dest='description')
            master_day_list.append((current_titles_list, current_date, book_count))

        def _add_to_master_date_range_list(current_titles_list):
            book_count = len(current_titles_list)
            current_titles_list = " &bull; ".join(current_titles_list)
            current_titles_list = self.format_ncx_text(current_titles_list, dest='description')
            master_date_range_list.append((current_titles_list, date_range, book_count))

        self.update_progress_full_step(_("NCX for Recently Read"))

        if not self.bookmarked_books_by_date_read:
            return

        ncx_soup = self.ncx_soup
        HTML_file = "content/ByDateRead.html"
        if self.generate_for_kindle_mobi:
            body = ncx_soup.find("navPoint")
        else:
            body = ncx_soup.find('navMap')
        btc = len(body.contents)

        # --- Construct the 'Recently Read' *section* ---
        navPointTag = Tag(ncx_soup, 'navPoint')
        if self.generate_for_kindle_mobi:
            navPointTag['class'] = "section"
        file_ID = "%s" % tocTitle.lower()
        file_ID = file_ID.replace(" ", "")
        navPointTag['id'] = "%s-ID" % file_ID
        navPointTag['playOrder'] = self.play_order
        self.play_order += 1
        navLabelTag = Tag(ncx_soup, 'navLabel')
        textTag = Tag(ncx_soup, 'text')
        textTag.insert(0, NavigableString('%s' % tocTitle))
        navLabelTag.insert(0, textTag)
        nptc = 0
        navPointTag.insert(nptc, navLabelTag)
        nptc += 1
        contentTag = Tag(ncx_soup, "content")
        contentTag['src'] = "%s#section_start" % HTML_file
        navPointTag.insert(nptc, contentTag)
        nptc += 1

        # Create an NCX article entry for each date range
        current_titles_list = []
        master_date_range_list = []
        today = datetime.datetime.now()
        today_time = datetime.datetime(today.year, today.month, today.day)
        for (i, date) in enumerate(self.DATE_RANGE):
            if i:
                date_range = '%d to %d days ago' % (self.DATE_RANGE[i - 1], self.DATE_RANGE[i])
            else:
                date_range = 'Last %d days' % (self.DATE_RANGE[i])
            date_range_limit = self.DATE_RANGE[i]
            for book in self.bookmarked_books_by_date_read:
                bookmark_time = datetime.datetime.utcfromtimestamp(book['bookmark_timestamp'])
                if (today_time - bookmark_time).days <= date_range_limit:
                    #print "generate_ncx_by_date_added: %s added %d days ago" % (book['title'], (today_time-book_time).days)
                    current_titles_list.append(book['title'])
                else:
                    break
            if current_titles_list:
                _add_to_master_date_range_list(current_titles_list)
            current_titles_list = [book['title']]

        # Create an NCX article entry for each populated day
        # Loop over the booksByDate list, find start of each month,
        # add description_preview_count titles
        # master_month_list(list,date,count)
        current_titles_list = []
        master_day_list = []
        current_date = datetime.datetime.utcfromtimestamp(self.bookmarked_books_by_date_read[0]['bookmark_timestamp'])

        for book in self.bookmarked_books_by_date_read:
            bookmark_time = datetime.datetime.utcfromtimestamp(book['bookmark_timestamp'])
            if bookmark_time.day != current_date.day or \
                bookmark_time.month != current_date.month or \
                bookmark_time.year != current_date.year:
                # Save the old lists
                _add_to_master_day_list(current_titles_list)

                # Start the new list
                current_date = datetime.datetime.utcfromtimestamp(book['bookmark_timestamp']).date()
                current_titles_list = [book['title']]
            else:
                current_titles_list.append(book['title'])

        # Add the last day list
        _add_to_master_day_list(current_titles_list)

        # Add *article* entries for each populated day
        # master_day_list{}: [0]:titles list [1]:date
        for books_by_day in master_day_list:
            datestr = strftime(u'%A, %B %d', books_by_day[1].timetuple())
            navPointByDayTag = Tag(ncx_soup, 'navPoint')
            if self.generate_for_kindle_mobi:
                navPointByDayTag['class'] = "article"
            navPointByDayTag['id'] = "bdr_%s-%s-%sID" % (books_by_day[1].year,
                                                            books_by_day[1].month,
                                                            books_by_day[1].day)
            navPointTag['playOrder'] = self.play_order
            self.play_order += 1
            navLabelTag = Tag(ncx_soup, 'navLabel')
            textTag = Tag(ncx_soup, 'text')
            textTag.insert(0, NavigableString(datestr))
            navLabelTag.insert(0, textTag)
            navPointByDayTag.insert(0, navLabelTag)
            contentTag = Tag(ncx_soup, 'content')
            contentTag['src'] = "%s#bdr_%s-%s-%s" % (HTML_file,
                                                        books_by_day[1].year,
                                                        books_by_day[1].month,
                                                        books_by_day[1].day)

            navPointByDayTag.insert(1, contentTag)

            if self.generate_for_kindle_mobi:
                cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                cmTag['name'] = "description"
                cmTag.insert(0, NavigableString(books_by_day[0]))
                navPointByDayTag.insert(2, cmTag)

                cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                cmTag['name'] = "author"
                navStr = '%d titles' % books_by_day[2] if books_by_day[2] > 1 else \
                            '%d title' % books_by_day[2]
                cmTag.insert(0, NavigableString(navStr))
                navPointByDayTag.insert(3, cmTag)

            navPointTag.insert(nptc, navPointByDayTag)
            nptc += 1

        # Add this section to the body
        body.insert(btc, navPointTag)
        btc += 1
        self.ncx_soup = ncx_soup

    def generate_ncx_by_genre(self, tocTitle):
        """ Add Genres to the basic NCX file.

        Generate the Genre NCX content, add to self.ncx_soup.

        Inputs:
         genres (list)

        Updated:
         play_order (int)

        Outputs:
         ncx_soup (file): updated
        """

        self.update_progress_full_step(_("NCX for Genres"))

        if not len(self.genres):
            self.opts.log.warn(" No genres found\n"
                                " No Genre section added to Catalog")
            return

        ncx_soup = self.ncx_soup
        if self.generate_for_kindle_mobi:
            body = ncx_soup.find("navPoint")
        else:
            body = ncx_soup.find('navMap')
        btc = len(body.contents)

        # --- Construct the 'Books By Genre' *section* ---
        navPointTag = Tag(ncx_soup, 'navPoint')
        if self.generate_for_kindle_mobi:
            navPointTag['class'] = "section"
        file_ID = "%s" % tocTitle.lower()
        file_ID = file_ID.replace(" ", "")
        navPointTag['id'] = "%s-ID" % file_ID
        navPointTag['playOrder'] = self.play_order
        self.play_order += 1
        navLabelTag = Tag(ncx_soup, 'navLabel')
        textTag = Tag(ncx_soup, 'text')
        section_header = '%s [%d]' % (tocTitle, len(self.genres))
        if self.generate_for_kindle_mobi:
            section_header = tocTitle
        textTag.insert(0, NavigableString(section_header))
        navLabelTag.insert(0, textTag)
        nptc = 0
        navPointTag.insert(nptc, navLabelTag)
        nptc += 1
        contentTag = Tag(ncx_soup, "content")
        contentTag['src'] = "content/Genre_%s.html#section_start" % self.genres[0]['tag']
        navPointTag.insert(nptc, contentTag)
        nptc += 1

        for genre in self.genres:
            # Add an article for each genre
            navPointVolumeTag = Tag(ncx_soup, 'navPoint')
            if self.generate_for_kindle_mobi:
                navPointVolumeTag['class'] = "article"
            navPointVolumeTag['id'] = "genre-%s-ID" % genre['tag']
            navPointVolumeTag['playOrder'] = self.play_order
            self.play_order += 1
            navLabelTag = Tag(ncx_soup, "navLabel")
            textTag = Tag(ncx_soup, "text")

            # GwR *** Can this be optimized?
            normalized_tag = None
            for friendly_tag in self.genre_tags_dict:
                if self.genre_tags_dict[friendly_tag] == genre['tag']:
                    normalized_tag = self.genre_tags_dict[friendly_tag]
                    break
            textTag.insert(0, self.format_ncx_text(NavigableString(friendly_tag), dest='description'))
            navLabelTag.insert(0, textTag)
            navPointVolumeTag.insert(0, navLabelTag)
            contentTag = Tag(ncx_soup, "content")
            contentTag['src'] = "content/Genre_%s.html#Genre_%s" % (normalized_tag, normalized_tag)
            navPointVolumeTag.insert(1, contentTag)

            if self.generate_for_kindle_mobi:
                # Build the author tag
                cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                cmTag['name'] = "author"
                # First - Last author

                if len(genre['titles_spanned']) > 1:
                    author_range = "%s - %s" % (genre['titles_spanned'][0][0], genre['titles_spanned'][1][0])
                else:
                    author_range = "%s" % (genre['titles_spanned'][0][0])

                cmTag.insert(0, NavigableString(author_range))
                navPointVolumeTag.insert(2, cmTag)

                # Build the description tag
                cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                cmTag['name'] = "description"

                if False:
                    # Form 1: Titles spanned
                    if len(genre['titles_spanned']) > 1:
                        title_range = "%s -\n%s" % (genre['titles_spanned'][0][1], genre['titles_spanned'][1][1])
                    else:
                        title_range = "%s" % (genre['titles_spanned'][0][1])
                    cmTag.insert(0, NavigableString(self.format_ncx_text(title_range, dest='description')))
                else:
                    # Form 2: title &bull; title &bull; title ...
                    titles = []
                    for title in genre['books']:
                        titles.append(title['title'])
                    titles = sorted(titles, key=lambda x: (self.generate_sort_title(x), self.generate_sort_title(x)))
                    titles_list = self.generate_short_description(u" &bull; ".join(titles), dest="description")
                    cmTag.insert(0, NavigableString(self.format_ncx_text(titles_list, dest='description')))

                navPointVolumeTag.insert(3, cmTag)

            # Add this volume to the section tag
            navPointTag.insert(nptc, navPointVolumeTag)
            nptc += 1

        # Add this section to the body
        body.insert(btc, navPointTag)
        btc += 1
        self.ncx_soup = ncx_soup

    def generate_opf(self):
        """ Generate the OPF file.

        Start with header template, construct manifest, spine and guide.

        Inputs:
         genres (list)
         html_filelist_1 (list)
         html_filelist_2 (list)
         thumbs (list)

        Updated:
         play_order (int)

        Outputs:
         opts.basename + '.opf' (file): written
        """

        self.update_progress_full_step(_("Generating OPF"))

        header = '''
            <?xml version="1.0" encoding="UTF-8"?>
            <package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="calibre_id">
                <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf" xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
                    <dc:language>en-US</dc:language>
                </metadata>
                <manifest></manifest>
                <spine toc="ncx"></spine>
                <guide></guide>
            </package>
            '''
        # Add the supplied metadata tags
        soup = BeautifulStoneSoup(header, selfClosingTags=['item', 'itemref', 'meta', 'reference'])
        metadata = soup.find('metadata')
        mtc = 0

        titleTag = Tag(soup, "dc:title")
        titleTag.insert(0, escape(self.opts.catalog_title))
        metadata.insert(mtc, titleTag)
        mtc += 1

        creatorTag = Tag(soup, "dc:creator")
        creatorTag.insert(0, self.opts.creator)
        metadata.insert(mtc, creatorTag)
        mtc += 1

        if self.generate_for_kindle_mobi:
            periodicalTag = Tag(soup, "meta")
            periodicalTag['name'] = "calibre:publication_type"
            periodicalTag['content'] = "periodical:default"
            metadata.insert(mtc, periodicalTag)
            mtc += 1

        # Create the OPF tags
        manifest = soup.find('manifest')
        mtc = 0
        spine = soup.find('spine')
        stc = 0
        guide = soup.find('guide')

        itemTag = Tag(soup, "item")
        itemTag['id'] = "ncx"
        itemTag['href'] = '%s.ncx' % self.opts.basename
        itemTag['media-type'] = "application/x-dtbncx+xml"
        manifest.insert(mtc, itemTag)
        mtc += 1

        itemTag = Tag(soup, "item")
        itemTag['id'] = 'stylesheet'
        itemTag['href'] = self.stylesheet
        itemTag['media-type'] = 'text/css'
        manifest.insert(mtc, itemTag)
        mtc += 1

        if self.generate_for_kindle_mobi:
            itemTag = Tag(soup, "item")
            itemTag['id'] = 'mastheadimage-image'
            itemTag['href'] = "images/mastheadImage.gif"
            itemTag['media-type'] = 'image/gif'
            manifest.insert(mtc, itemTag)
            mtc += 1

        # Write the thumbnail images, descriptions to the manifest
        if self.opts.generate_descriptions:
            for thumb in self.thumbs:
                itemTag = Tag(soup, "item")
                itemTag['href'] = "images/%s" % (thumb)
                end = thumb.find('.jpg')
                itemTag['id'] = "%s-image" % thumb[:end]
                itemTag['media-type'] = 'image/jpeg'
                manifest.insert(mtc, itemTag)
                mtc += 1

        # Add html_files to manifest and spine

        for file in self.html_filelist_1:
            # By Author, By Title, By Series,
            itemTag = Tag(soup, "item")
            start = file.find('/') + 1
            end = file.find('.')
            itemTag['href'] = file
            itemTag['id'] = file[start:end].lower()
            itemTag['media-type'] = "application/xhtml+xml"
            manifest.insert(mtc, itemTag)
            mtc += 1

            # spine
            itemrefTag = Tag(soup, "itemref")
            itemrefTag['idref'] = file[start:end].lower()
            spine.insert(stc, itemrefTag)
            stc += 1

        # Add genre files to manifest and spine
        for genre in self.genres:
            itemTag = Tag(soup, "item")
            start = genre['file'].find('/') + 1
            end = genre['file'].find('.')
            itemTag['href'] = genre['file']
            itemTag['id'] = genre['file'][start:end].lower()
            itemTag['media-type'] = "application/xhtml+xml"
            manifest.insert(mtc, itemTag)
            mtc += 1

            # spine
            itemrefTag = Tag(soup, "itemref")
            itemrefTag['idref'] = genre['file'][start:end].lower()
            spine.insert(stc, itemrefTag)
            stc += 1

        for file in self.html_filelist_2:
            # By Date Added, By Date Read
            itemTag = Tag(soup, "item")
            start = file.find('/') + 1
            end = file.find('.')
            itemTag['href'] = file
            itemTag['id'] = file[start:end].lower()
            itemTag['media-type'] = "application/xhtml+xml"
            manifest.insert(mtc, itemTag)
            mtc += 1

            # spine
            itemrefTag = Tag(soup, "itemref")
            itemrefTag['idref'] = file[start:end].lower()
            spine.insert(stc, itemrefTag)
            stc += 1

        for book in self.books_by_description:
            # manifest
            itemTag = Tag(soup, "item")
            itemTag['href'] = "content/book_%d.html" % int(book['id'])
            itemTag['id'] = "book%d" % int(book['id'])
            itemTag['media-type'] = "application/xhtml+xml"
            manifest.insert(mtc, itemTag)
            mtc += 1

            # spine
            itemrefTag = Tag(soup, "itemref")
            itemrefTag['idref'] = "book%d" % int(book['id'])
            spine.insert(stc, itemrefTag)
            stc += 1

        # Guide
        if self.generate_for_kindle_mobi:
            referenceTag = Tag(soup, "reference")
            referenceTag['type'] = 'masthead'
            referenceTag['title'] = 'mastheadimage-image'
            referenceTag['href'] = 'images/mastheadImage.gif'
            guide.insert(0, referenceTag)

        # Write the OPF file
        outfile = open("%s/%s.opf" % (self.catalog_path, self.opts.basename), 'w')
        outfile.write(soup.prettify())

    def generate_rating_string(self, book):
        """ Generate rating string for Descriptions.

        Starting with database rating (0-10), return 5 stars, with 0-5 filled,
        balance empty.

        Args:
         book (dict): book metadata

        Return:
         rating (str): 5 stars, 1-5 solid, balance empty. Empty str for no rating.
        """

        rating = ''
        try:
            if 'rating' in book:
                stars = int(book['rating']) / 2
                if stars:
                    star_string = self.SYMBOL_FULL_RATING * stars
                    empty_stars = self.SYMBOL_EMPTY_RATING * (5 - stars)
                    rating = '%s%s' % (star_string, empty_stars)
        except:
            # Rating could be None
            pass
        return rating

    def generate_series_anchor(self, series):
        """ Generate legal XHTML anchor for series names.

        Flatten series name to ascii_legal text.

        Args:
         series (str): series name

        Return:
         (str): asciized version of series name
        """

        # Generate a legal XHTML id/href string
        if self.letter_or_symbol(series) == self.SYMBOLS:
            return "symbol_%s_series" % re.sub('\W', '', series).lower()
        else:
            return "%s_series" % re.sub('\W', '', ascii_text(series)).lower()

    def generate_short_description(self, description, dest=None):
        """ Generate a truncated version of the supplied string.

        Given a string and NCX destination, truncate string to length specified
        in self.opts.

        Args:
         description (str): string to truncate
         dest (str): NCX destination
           description  NCX summary
           title        NCX title
           author       NCX author

        Return:
         (str): truncated description
        """

        def _short_description(description, limit):
            short_description = ""
            words = description.split()
            for word in words:
                short_description += word + " "
                if len(short_description) > limit:
                    short_description += "..."
                    return short_description

        if not description:
            return None

        if dest == 'title':
            # No truncation for titles, let the device deal with it
            return description
        elif dest == 'author':
            if self.opts.author_clip and len(description) < self.opts.author_clip:
                return description
            else:
                return _short_description(description, self.opts.author_clip)
        elif dest == 'description':
            if self.opts.description_clip and len(description) < self.opts.description_clip:
                return description
            else:
                return _short_description(description, self.opts.description_clip)
        else:
            print " returning description with unspecified destination '%s'" % description
            raise RuntimeError

    def generate_sort_title(self, title):
        """ Generates a sort string from title.

        Based on trunk title_sort algorithm, but also accommodates series
        numbers by padding with leading zeroes to force proper numeric
        sorting. Option to sort numbers alphabetically, e.g. '1942' sorts
        as 'Nineteen forty two'.

        Args:
         title (str):

        Return:
         (str): sort string
        """

        from calibre.ebooks.metadata import title_sort
        from calibre.library.catalogs.utils import NumberToText

        # Strip stop words
        title_words = title_sort(title).split()
        translated = []

        for (i, word) in enumerate(title_words):
            # Leading numbers optionally translated to text equivalent
            # Capitalize leading sort word
            if i == 0:
                # *** Keep this code in case we need to restore numbers_as_text ***
                if False:
                #if self.opts.numbers_as_text and re.match('[0-9]+',word[0]):
                    translated.append(NumberToText(word).text.capitalize())
                else:
                    if re.match('[0-9]+', word[0]):
                        word = word.replace(',', '')
                        suffix = re.search('[\D]', word)
                        if suffix:
                            word = '%10.0f%s' % (float(word[:suffix.start()]), word[suffix.start():])
                        else:
                            word = '%10.0f' % (float(word))

                    # If leading char > 'A', insert symbol as leading forcing lower sort
                    # '/' sorts below numbers, g
                    if self.letter_or_symbol(word[0]) != word[0]:
                        if word[0] > 'A' or (ord('9') < ord(word[0]) < ord('A')):
                            translated.append('/')
                    translated.append(capitalize(word))

            else:
                if re.search('[0-9]+', word[0]):
                    word = word.replace(',', '')
                    suffix = re.search('[\D]', word)
                    if suffix:
                        word = '%10.0f%s' % (float(word[:suffix.start()]), word[suffix.start():])
                    else:
                        word = '%10.0f' % (float(word))
                translated.append(word)
        return ' '.join(translated)

    def generate_thumbnail(self, title, image_dir, thumb_file):
        """ Create thumbnail of cover or return previously cached thumb.

        Test thumb archive for currently cached cover. Return cached version, or create
        and cache new version. Uses calibre.utils.magick.draw to generate thumbnail from
        cover.

        Args:
         title (dict): book metadata
         image_dir (str): directory to write thumb data to
         thumb_file (str): filename to save thumb as

        Output:
         (file): thumb written to /images
         (archive): current thumb archived under cover crc
        """

        def _open_archive(mode='r'):
            try:
                return ZipFile(self.thumbs_path, mode=mode, allowZip64=True)
            except:
                # occurs under windows if the file is opened by another
                # process
                pass

        # Generate crc for current cover
        with open(title['cover'], 'rb') as f:
            data = f.read()
        cover_crc = hex(zlib.crc32(data))

        # Test cache for uuid
        zf = _open_archive()
        if zf is not None:
            with zf:
                try:
                    zf.getinfo(title['uuid'] + cover_crc)
                except:
                    pass
                else:
                    # uuid found in cache with matching crc
                    thumb_data = zf.read(title['uuid'] + cover_crc)
                    with open(os.path.join(image_dir, thumb_file), 'wb') as f:
                        f.write(thumb_data)
                    return

        # Save thumb for catalog. If invalid data, error returns to generate_thumbnails()
        thumb_data = thumbnail(data,
                width=self.thumb_width, height=self.thumb_height)[-1]
        with open(os.path.join(image_dir, thumb_file), 'wb') as f:
            f.write(thumb_data)

        # Save thumb to archive
        if zf is not None:
            # Ensure that the read succeeded
            # If we failed to open the zip file for reading,
            # we dont know if it contained the thumb or not
            zf = _open_archive('a')
            if zf is not None:
                with zf:
                    zf.writestr(title['uuid'] + cover_crc, thumb_data)

    def generate_thumbnails(self):
        """ Generate a thumbnail cover for each book.

        Generate or retrieve a thumbnail for each cover. If nonexistent or faulty
        cover data, substitute default cover. Checks for updated default cover.
        At completion, writes self.opts.thumb_width to archive.

        Inputs:
         books_by_title (list): books to catalog

        Output:
         thumbs (list): list of referenced thumbnails
        """

        self.update_progress_full_step(_("Thumbnails"))
        thumbs = ['thumbnail_default.jpg']
        image_dir = "%s/images" % self.catalog_path
        for (i, title) in enumerate(self.books_by_title):
            # Update status
            self.update_progress_micro_step("%s %d of %d" %
                (_("Thumbnail"), i, len(self.books_by_title)),
                 i / float(len(self.books_by_title)))

            thumb_file = 'thumbnail_%d.jpg' % int(title['id'])
            thumb_generated = True
            valid_cover = True
            try:
                self.generate_thumbnail(title, image_dir, thumb_file)
                thumbs.append("thumbnail_%d.jpg" % int(title['id']))
            except:
                if 'cover' in title and os.path.exists(title['cover']):
                    valid_cover = False
                    self.opts.log.warn(" *** Invalid cover file for '%s'***" %
                                            (title['title']))
                    if not self.error:
                        self.error.append('Invalid cover files')
                    self.error.append("Warning: invalid cover file for '%s', default cover substituted.\n" % (title['title']))

                thumb_generated = False

            if not thumb_generated:
                self.opts.log.warn("     using default cover for '%s' (%d)" % (title['title'], title['id']))
                # Confirm thumb exists, default is current
                default_thumb_fp = os.path.join(image_dir, "thumbnail_default.jpg")
                cover = os.path.join(self.catalog_path, "DefaultCover.png")
                title['cover'] = cover

                if not os.path.exists(cover):
                    shutil.copyfile(I('book.png'), cover)

                if os.path.isfile(default_thumb_fp):
                    # Check to see if default cover is newer than thumbnail
                    # os.path.getmtime() = modified time
                    # os.path.ctime() = creation time
                    cover_timestamp = os.path.getmtime(cover)
                    thumb_timestamp = os.path.getmtime(default_thumb_fp)
                    if thumb_timestamp < cover_timestamp:
                        if self.DEBUG and self.opts.verbose:
                            self.opts.log.warn("updating thumbnail_default for %s" % title['title'])
                        self.generate_thumbnail(title, image_dir,
                                            "thumbnail_default.jpg" if valid_cover else thumb_file)
                else:
                    if self.DEBUG and self.opts.verbose:
                        self.opts.log.warn("     generating new thumbnail_default.jpg")
                    self.generate_thumbnail(title, image_dir,
                                            "thumbnail_default.jpg" if valid_cover else thumb_file)
                # Clear the book's cover property
                title['cover'] = None

        # Write thumb_width to the file, validating cache contents
        # Allows detection of aborted catalog builds
        with ZipFile(self.thumbs_path, mode='a') as zfw:
            zfw.writestr('thumb_width', self.opts.thumb_width)

        self.thumbs = thumbs

    def generate_unicode_name(self, c):
        """ Generate a legal XHTML anchor from unicode character.

        Generate a legal XHTML anchor from unicode character.

        Args:
         c (unicode): character

        Return:
         (str): legal XHTML anchor string of unicode character name
        """
        fullname = ''
        for cc in c:
            fullname += unicodedata.name(unicode(cc))
        terms = fullname.split()
        return "_".join(terms)

    def get_excluded_tags(self):
        """ Get excluded_tags from opts.exclusion_rules.

        Parse opts.exclusion_rules for tags to be excluded, return list.
        Log books that will be excluded by excluded_tags.

        Inputs:
         opts.excluded_tags (tuples): exclusion rules

        Return:
         excluded_tags (list): excluded tags
        """
        excluded_tags = []
        for rule in self.opts.exclusion_rules:
            if rule[1].lower() == 'tags':
                excluded_tags.extend(rule[2].split(','))

        # Remove dups
        excluded_tags = list(set(excluded_tags))

        # Report excluded books
        if self.opts.verbose and excluded_tags:
            self.opts.log.info(" Books excluded by tag:")
            data = self.db.get_data_as_dict(ids=self.opts.ids)
            for record in data:
                matched = list(set(record['tags']) & set(excluded_tags))
                if matched:
                    for rule in self.opts.exclusion_rules:
                        if rule[1] == 'Tags' and rule[2] == str(matched[0]):
                            self.opts.log.info("  - '%s' by %s (Exclusion rule '%s')" %
                                (record['title'], record['authors'][0], rule[0]))

        return excluded_tags

    def get_friendly_genre_tag(self, genre):
        """ Return the first friendly_tag matching genre.

        Scan self.genre_tags_dict[] for first friendly_tag matching genre.
        genre_tags_dict[] populated in filter_genre_tags().

        Args:
         genre (str): genre to match

        Return:
         friendly_tag (str): friendly_tag matching genre
        """
        # Find the first instance of friendly_tag matching genre
        for friendly_tag in self.genre_tags_dict:
            if self.genre_tags_dict[friendly_tag] == genre:
                return friendly_tag

    def get_output_profile(self, _opts):
        """ Return profile matching opts.output_profile

        Input:
         _opts (object): build options object

        Return:
         (profile): output profile matching name
        """
        for profile in output_profiles():
            if profile.short_name == _opts.output_profile:
                return profile

    def get_prefix_rules(self):
        """ Convert opts.prefix_rules to dict.

        Convert opts.prefix_rules to dict format. The model for a prefix rule is
        ('<rule name>','<#source_field_lookup>','<pattern>','<prefix>')

        Input:
         opts.prefix_rules (tuples): (name, field, pattern, prefix)

        Return:
         (list): list of prefix_rules dicts
        """
        pr = []
        if self.opts.prefix_rules:
            try:
                for rule in self.opts.prefix_rules:
                    prefix_rule = {}
                    prefix_rule['name'] = rule[0]
                    prefix_rule['field'] = rule[1]
                    prefix_rule['pattern'] = rule[2]
                    prefix_rule['prefix'] = rule[3]
                    pr.append(prefix_rule)
            except:
                self.opts.log.error("malformed prefix_rules: %s" % repr(self.opts.prefix_rules))
                raise
        return pr

    def letter_or_symbol(self, char):
        """ Test asciized char for A-z.

        Convert char to ascii, test for A-z.

        Args:
         char (chr): character to test

        Return:
         (str): char if A-z, else SYMBOLS
        """
        if not re.search('[a-zA-Z]', ascii_text(char)):
            return self.SYMBOLS
        else:
            return char

    def load_section_templates(self):
        """ Add section templates to local namespace.

        Load section templates from resource directory. If user has made local copies,
        these will be used for individual section generation.
        generate_format_args() builds args that populate templates.
        Templates referenced in individual section builders, e.g.
        generate_html_by_title().

        Inputs:
         (files): section template files from resource dir

        Results:
         (strs): section templates added to local namespace
        """

        templates = {}
        execfile(P('catalog/section_list_templates.py'), templates)
        for name, template in templates.iteritems():
            if name.startswith('by_') and name.endswith('_template'):
                setattr(self, name, force_unicode(template, 'utf-8'))

    def massage_comments(self, comments):
        """ Massage comments to somewhat consistent format.

        Convert random comment text to normalized, xml-legal block of <p>s
        'plain text' returns as
        <p>plain text</p>

        'plain text with <i>minimal</i> <b>markup</b>' returns as
        <p>plain text with <i>minimal</i> <b>markup</b></p>

        '<p>pre-formatted text</p> returns untouched

        'A line of text\n\nFollowed by a line of text' returns as
        <p>A line of text</p>
        <p>Followed by a line of text</p>

        'A line of text.\nA second line of text.\rA third line of text' returns as
        <p>A line of text.<br />A second line of text.<br />A third line of text.</p>

        '...end of a paragraph.Somehow the break was lost...' returns as
        <p>...end of a paragraph.</p>
        <p>Somehow the break was lost...</p>

        Deprecated HTML returns as HTML via BeautifulSoup()

        Args:
         comments (str): comments from metadata, possibly HTML

        Return:
         result (BeautifulSoup): massaged comments in HTML form
        """

        # Hackish - ignoring sentences ending or beginning in numbers to avoid
        # confusion with decimal points.

        # Explode lost CRs to \n\n
        for lost_cr in re.finditer('([a-z])([\.\?!])([A-Z])', comments):
            comments = comments.replace(lost_cr.group(),
                                        '%s%s\n\n%s' % (lost_cr.group(1),
                                                        lost_cr.group(2),
                                                        lost_cr.group(3)))
        # Extract pre-built elements - annotations, etc.
        if not isinstance(comments, unicode):
            comments = comments.decode('utf-8', 'replace')
        soup = BeautifulSoup(comments)
        elems = soup.findAll('div')
        for elem in elems:
            elem.extract()

        # Reconstruct comments w/o <div>s
        comments = soup.renderContents(None)

        # Convert \n\n to <p>s
        if re.search('\n\n', comments):
            soup = BeautifulSoup()
            split_ps = comments.split(u'\n\n')
            tsc = 0
            for p in split_ps:
                pTag = Tag(soup, 'p')
                pTag.insert(0, p)
                soup.insert(tsc, pTag)
                tsc += 1
            comments = soup.renderContents(None)

        # Convert solo returns to <br />
        comments = re.sub('[\r\n]', '<br />', comments)

        # Convert two hypens to emdash
        comments = re.sub('--', '&mdash;', comments)
        soup = BeautifulSoup(comments)
        result = BeautifulSoup()
        rtc = 0
        open_pTag = False

        all_tokens = list(soup.contents)
        for token in all_tokens:
            if type(token) is NavigableString:
                if not open_pTag:
                    pTag = Tag(result, 'p')
                    open_pTag = True
                    ptc = 0
                pTag.insert(ptc, prepare_string_for_xml(token))
                ptc += 1

            elif token.name in ['br', 'b', 'i', 'em']:
                if not open_pTag:
                    pTag = Tag(result, 'p')
                    open_pTag = True
                    ptc = 0
                pTag.insert(ptc, token)
                ptc += 1

            else:
                if open_pTag:
                    result.insert(rtc, pTag)
                    rtc += 1
                    open_pTag = False
                    ptc = 0
                # Clean up NavigableStrings for xml
                sub_tokens = list(token.contents)
                for sub_token in sub_tokens:
                    if type(sub_token) is NavigableString:
                        sub_token.replaceWith(prepare_string_for_xml(sub_token))
                result.insert(rtc, token)
                rtc += 1

        if open_pTag:
            result.insert(rtc, pTag)
            rtc += 1

        paras = result.findAll('p')
        for p in paras:
            p['class'] = 'description'

        # Add back <div> elems initially removed
        for elem in elems:
            result.insert(rtc, elem)
            rtc += 1

        return result.renderContents(encoding=None)

    def merge_comments(self, record):
        """ Merge comments with custom column content.

        Merge comments from book metadata with user-specified custom column
         content, optionally before or after. Optionally insert <hr> between
         fields.

        Args:
         record (dict): book metadata

        Return:
         merged (str): comments merged with addendum
        """

        merged = ''
        if record['description']:
            addendum = self.db.get_field(record['id'],
                                        self.merge_comments_rule['field'],
                                        index_is_id=True)
            if addendum is None:
                addendum = ''
            elif type(addendum) is list:
                addendum = (', '.join(addendum))
            include_hr = eval(self.merge_comments_rule['hr'])
            if self.merge_comments_rule['position'] == 'before':
                merged = addendum
                if include_hr:
                    merged += '<hr class="merged_comments_divider"/>'
                else:
                    merged += '\n'
                merged += record['description']
            else:
                merged = record['description']
                if include_hr:
                    merged += '<hr class="merged_comments_divider"/>'
                else:
                    merged += '\n'
                merged += addendum
        else:
            # Return only the custom field contents
            merged = self.db.get_field(record['id'],
                                        self.merge_comments_rule['field'],
                                        index_is_id=True)
            if type(merged) is list:
                merged = (', '.join(merged))

        return merged

    def process_exclusions(self, data_set):
        """ Filter data_set based on exclusion_rules.

        Compare each book in data_set to each exclusion_rule. Remove
         books matching exclusion criteria.

        Args:
         data_set (list): all candidate books

        Return:
         (list): filtered data_set
        """

        filtered_data_set = []
        exclusion_pairs = []
        exclusion_set = []
        for rule in self.opts.exclusion_rules:
            if rule[1].startswith('#') and rule[2] != '':
                field = rule[1]
                pat = rule[2]
                exclusion_pairs.append((field, pat))
            else:
                continue
        if exclusion_pairs:
            if self.opts.verbose:
                self.opts.log.info(" Books excluded by custom field contents:")

            for record in data_set:
                for exclusion_pair in exclusion_pairs:
                    field, pat = exclusion_pair
                    field_contents = self.db.get_field(record['id'],
                                                field,
                                                index_is_id=True)

                    if (self.db.metadata_for_field(field)['datatype'] == 'bool' and
                        field_contents is None):
                        # Handle condition where field is a bool and contents is None,
                        # which is displayed as No
                        field_contents = _('False')

                    if field_contents is not None:
                        if self.db.metadata_for_field(field)['datatype'] == 'bool':
                            # For Yes/No fields, need to translate field_contents to
                            # locale version
                            field_contents = _(repr(field_contents))

                        matched = re.search(pat, unicode(field_contents),
                                re.IGNORECASE)
                        if matched is not None:
                            if self.opts.verbose:
                                field_md = self.db.metadata_for_field(field)
                                for rule in self.opts.exclusion_rules:
                                    if rule[1] == '#%s' % field_md['label']:
                                        self.opts.log.info("  - '%s' by %s (%s: '%s' contains '%s')" %
                                            (record['title'], record['authors'][0],
                                             rule[0],
                                             self.db.metadata_for_field(field)['name'],
                                             field_contents))
                            exclusion_set.append(record)
                            if record in filtered_data_set:
                                filtered_data_set.remove(record)
                            break
                        else:
                            filtered_data_set.append(record)
                    else:
                        if (record not in filtered_data_set and
                            record not in exclusion_set):
                            filtered_data_set.append(record)
            return filtered_data_set
        else:
            return data_set

    def relist_multiple_authors(self, books_by_author):
        """ Create multiple entries for books with multiple authors

        Given a list of books by author, scan list for books with multiple
        authors. Add a cloned copy of the book per additional author.

        Args:
         books_by_author (list): book list possibly containing books
         with multiple authors

        Return:
         (list): books_by_author with additional cloned entries for books with
         multiple authors
        """

        multiple_author_books = []

        # Find the multiple author books
        for book in books_by_author:
            if len(book['authors']) > 1:
                multiple_author_books.append(book)

        for book in multiple_author_books:
            cloned_authors = list(book['authors'])
            for x, author in enumerate(book['authors']):
                if x:
                    first_author = cloned_authors.pop(0)
                    cloned_authors.append(first_author)
                    new_book = deepcopy(book)
                    new_book['author'] = ' & '.join(cloned_authors)
                    new_book['authors'] = list(cloned_authors)
                    asl = [author_to_author_sort(auth) for auth in cloned_authors]
                    new_book['author_sort'] = ' & '.join(asl)
                    books_by_author.append(new_book)

        return books_by_author

    def update_progress_full_step(self, description):
        """ Update calibre's job status UI.

        Call ProgessReporter() with updates.

        Args:
         description (str): text describing current step

        Result:
         (UI): Jobs UI updated
        """

        self.current_step += 1
        self.progress_string = description
        self.progress_int = float((self.current_step - 1) / self.total_steps)
        if not self.progress_int:
            self.progress_int = 0.01
        self.reporter(self.progress_int, self.progress_string)
        if self.opts.cli_environment:
            self.opts.log(u"%3.0f%% %s" % (self.progress_int * 100, self.progress_string))

    def update_progress_micro_step(self, description, micro_step_pct):
        """ Update calibre's job status UI.

        Called from steps requiring more time:
         generate_html_descriptions()
         generate_thumbnails()

        Args:
         description (str): text describing microstep
         micro_step_pct (float): percentage of full step

        Results:
         (UI): Jobs UI updated
        """

        step_range = 100 / self.total_steps
        self.progress_string = description
        coarse_progress = float((self.current_step - 1) / self.total_steps)
        fine_progress = float((micro_step_pct * step_range) / 100)
        self.progress_int = coarse_progress + fine_progress
        self.reporter(self.progress_int, self.progress_string)

    def write_ncx(self):
        """ Write accumulated ncx_soup to file.

        Expanded description

        Inputs:
         catalog_path (str): path to generated catalog
         opts.basename (str): catalog basename

        Output:
         (file): basename.NCX written
        """

        self.update_progress_full_step(_("Saving NCX"))

        outfile = open("%s/%s.ncx" % (self.catalog_path, self.opts.basename), 'w')
        outfile.write(self.ncx_soup.prettify())
