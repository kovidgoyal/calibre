# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2010, Greg Riker'

import datetime, htmlentitydefs, os, re, shutil, unicodedata, zlib
from copy import deepcopy
from xml.sax.saxutils import escape

from calibre import (prepare_string_for_xml, strftime, force_unicode)
from calibre.customize.conversion import DummyReporter
from calibre.ebooks.BeautifulSoup import BeautifulSoup, BeautifulStoneSoup, Tag, NavigableString
from calibre.ebooks.chardet import substitute_entites
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.config import config_dir
from calibre.utils.date import format_date, is_date_undefined, now as nowf
from calibre.utils.filenames import ascii_text
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
        catalog.createDirectoryStructure()
        catalog.copyResources()
        catalog.buildSources()
    Options managed in gui2.catalog.catalog_epub_mobi.py
    '''

    # A single number creates 'Last x days' only.
    # Multiple numbers create 'Last x days', 'x to y days ago' ...
    # e.g, [7,15,30,60], [30]
    # [] = No date ranges added
    DATE_RANGE=[30]

    # Text used in generated catalog for title section with other-than-ASCII leading letter
    SYMBOLS = _('Symbols')

    # basename              output file basename
    # creator               dc:creator in OPF metadata
    # descriptionClip       limits size of NCX descriptions (Kindle only)
    # includeSources        Used in processSpecialTags to skip tags like '[SPL]'
    # notification          Used to check for cancel, report progress
    # stylesheet            CSS stylesheet
    # title                 dc:title in OPF metadata, NCX periodical
    # verbosity             level of diagnostic printout

    def __init__(self, db, opts, plugin,
                    report_progress=DummyReporter(),
                    stylesheet="content/stylesheet.css"):
        self.__opts = opts
        self.__authorClip = opts.authorClip
        self.__authors = None
        self.__basename = opts.basename
        self.__bookmarked_books = None
        self.__booksByAuthor = None
        self.__booksByDateRead = None
        self.__booksByTitle = None
        self.__booksByTitle_noSeriesPrefix = None
        self.__cache_dir = os.path.join(config_dir, 'caches', 'catalog')
        self.__archive_path = os.path.join(self.__cache_dir, "thumbs.zip")
        self.__catalogPath = PersistentTemporaryDirectory("_epub_mobi_catalog", prefix='')
        self.__contentDir = os.path.join(self.catalogPath, "content")
        self.__currentStep = 0.0
        self.__creator = opts.creator
        self.__db = db
        self.__defaultPrefix = None
        self.__descriptionClip = opts.descriptionClip
        self.__error = []
        self.__generateForKindle = True if (self.opts.fmt == 'mobi' and \
                                    self.opts.output_profile and \
                                    self.opts.output_profile.startswith("kindle")) else False
        self.__generateRecentlyRead = True if self.opts.generate_recently_added \
                                                and self.opts.connected_kindle \
                                                and self.generateForKindle \
                                            else False
        self.__genres = None
        self.genres = []
        self.__genre_tags_dict = None
        self.__htmlFileList_1 = []
        self.__htmlFileList_2 = []
        self.__markerTags = self.getMarkerTags()
        self.__ncxSoup = None
        self.__output_profile = None
        self.__playOrder = 1
        self.__plugin = plugin
        self.__prefixRules = []
        self.__progressInt = 0.0
        self.__progressString = ''
        f, p, hr = self.opts.merge_comments.split(':')
        self.__merge_comments = {'field':f, 'position':p, 'hr':hr}
        self.__reporter = report_progress
        self.__stylesheet = stylesheet
        self.__thumbs = None
        self.__thumbWidth = 0
        self.__thumbHeight = 0
        self.__title = opts.catalog_title
        self.__totalSteps = 6.0
        self.__useSeriesPrefixInTitlesSection = False
        self.__verbose = opts.verbose

        from calibre.customize.ui import output_profiles
        for profile in output_profiles():
            if profile.short_name == self.opts.output_profile:
                self.__output_profile = profile
                break

        # Process prefix rules
        self.processPrefixRules()

        # Confirm/create thumbs archive.
        if self.opts.generate_descriptions:
            if not os.path.exists(self.__cache_dir):
                self.opts.log.info(" creating new thumb cache '%s'" % self.__cache_dir)
                os.makedirs(self.__cache_dir)
            if not os.path.exists(self.__archive_path):
                self.opts.log.info(' creating thumbnail archive, thumb_width: %1.2f"' %
                                        float(self.opts.thumb_width))
                with ZipFile(self.__archive_path, mode='w') as zfw:
                    zfw.writestr("Catalog Thumbs Archive",'')
            else:
                try:
                    with ZipFile(self.__archive_path, mode='r') as zfr:
                        try:
                            cached_thumb_width = zfr.read('thumb_width')
                        except:
                            cached_thumb_width = "-1"
                except:
                    os.remove(self.__archive_path)
                    cached_thumb_width = '-1'

                if float(cached_thumb_width) != float(self.opts.thumb_width):
                    self.opts.log.warning(" invalidating cache at '%s'" % self.__archive_path)
                    self.opts.log.warning('  thumb_width changed: %1.2f" => %1.2f"' %
                                        (float(cached_thumb_width),float(self.opts.thumb_width)))
                    with ZipFile(self.__archive_path, mode='w') as zfw:
                        zfw.writestr("Catalog Thumbs Archive",'')
                else:
                    self.opts.log.info(' existing thumb cache at %s, cached_thumb_width: %1.2f"' %
                                            (self.__archive_path, float(cached_thumb_width)))

        # Tweak build steps based on optional sections:  1 call for HTML, 1 for NCX
        incremental_jobs = 0
        if self.opts.generate_authors:
            incremental_jobs += 2
        if self.opts.generate_titles:
            incremental_jobs += 2
        if self.opts.generate_recently_added:
            incremental_jobs += 2
            if self.generateRecentlyRead:
                incremental_jobs += 2
        if self.opts.generate_series:
            incremental_jobs += 2
        if self.opts.generate_descriptions:
            # +1 thumbs
            incremental_jobs += 3
        self.__totalSteps += incremental_jobs

        # Load section list templates
        templates = {}
        execfile(P('catalog/section_list_templates.py'), templates)
        for name, template in templates.iteritems():
            if name.startswith('by_') and name.endswith('_template'):
                setattr(self, name, force_unicode(template, 'utf-8'))

    # Accessors
    if True:
        '''
        @dynamic_property
        def xxxx(self):
            def fget(self):
                return self.__
            def fset(self, val):
                self.__ = val
            return property(fget=fget, fset=fset)
        '''
        @dynamic_property
        def authorClip(self):
            def fget(self):
                return self.__authorClip
            def fset(self, val):
                self.__authorClip = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def authors(self):
            def fget(self):
                return self.__authors
            def fset(self, val):
                self.__authors = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def basename(self):
            def fget(self):
                return self.__basename
            def fset(self, val):
                self.__basename = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def bookmarked_books(self):
            def fget(self):
                return self.__bookmarked_books
            def fset(self, val):
                self.__bookmarked_books = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def booksByAuthor(self):
            def fget(self):
                return self.__booksByAuthor
            def fset(self, val):
                self.__booksByAuthor = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def booksByDateRead(self):
            def fget(self):
                return self.__booksByDateRead
            def fset(self, val):
                self.__booksByDateRead = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def booksByTitle(self):
            def fget(self):
                return self.__booksByTitle
            def fset(self, val):
                self.__booksByTitle = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def booksByTitle_noSeriesPrefix(self):
            def fget(self):
                return self.__booksByTitle_noSeriesPrefix
            def fset(self, val):
                self.__booksByTitle_noSeriesPrefix = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def catalogPath(self):
            def fget(self):
                return self.__catalogPath
            def fset(self, val):
                self.__catalogPath = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def contentDir(self):
            def fget(self):
                return self.__contentDir
            def fset(self, val):
                self.__contentDir = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def currentStep(self):
            def fget(self):
                return self.__currentStep
            def fset(self, val):
                self.__currentStep = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def creator(self):
            def fget(self):
                return self.__creator
            def fset(self, val):
                self.__creator = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def db(self):
            def fget(self):
                return self.__db
            return property(fget=fget)
        @dynamic_property
        def defaultPrefix(self):
            def fget(self):
                return self.__defaultPrefix
            def fset(self, val):
                self.__defaultPrefix = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def descriptionClip(self):
            def fget(self):
                return self.__descriptionClip
            def fset(self, val):
                self.__descriptionClip = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def error(self):
            def fget(self):
                return self.__error
            def fset(self, val):
                self.__error = val
            return property(fget=fget,fset=fset)
        @dynamic_property
        def generateForKindle(self):
            def fget(self):
                return self.__generateForKindle
            def fset(self, val):
                self.__generateForKindle = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def generateRecentlyRead(self):
            def fget(self):
                return self.__generateRecentlyRead
            def fset(self, val):
                self.__generateRecentlyRead = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def genres(self):
            def fget(self):
                return self.__genres
            def fset(self, val):
                self.__genres = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def genre_tags_dict(self):
            def fget(self):
                return self.__genre_tags_dict
            def fset(self, val):
                self.__genre_tags_dict = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def htmlFileList_1(self):
            def fget(self):
                return self.__htmlFileList_1
            def fset(self, val):
                self.__htmlFileList_1 = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def htmlFileList_2(self):
            def fget(self):
                return self.__htmlFileList_2
            def fset(self, val):
                self.__htmlFileList_2 = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def libraryPath(self):
            def fget(self):
                return self.__libraryPath
            def fset(self, val):
                self.__libraryPath = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def markerTags(self):
            def fget(self):
                return self.__markerTags
            def fset(self, val):
                self.__markerTags = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def ncxSoup(self):
            def fget(self):
                return self.__ncxSoup
            def fset(self, val):
                self.__ncxSoup = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def opts(self):
            def fget(self):
                return self.__opts
            return property(fget=fget)
        @dynamic_property
        def playOrder(self):
            def fget(self):
                return self.__playOrder
            def fset(self,val):
                self.__playOrder = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def plugin(self):
            def fget(self):
                return self.__plugin
            return property(fget=fget)
        @dynamic_property
        def prefixRules(self):
            def fget(self):
                return self.__prefixRules
            def fset(self, val):
                self.__prefixRules = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def progressInt(self):
            def fget(self):
                return self.__progressInt
            def fset(self, val):
                self.__progressInt = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def progressString(self):
            def fget(self):
                return self.__progressString
            def fset(self, val):
                self.__progressString = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def reporter(self):
            def fget(self):
                return self.__reporter
            def fset(self, val):
                self.__reporter = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def stylesheet(self):
            def fget(self):
                return self.__stylesheet
            def fset(self, val):
                self.__stylesheet = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def thumbs(self):
            def fget(self):
                return self.__thumbs
            def fset(self, val):
                self.__thumbs = val
            return property(fget=fget, fset=fset)
        def thumbWidth(self):
            def fget(self):
                return self.__thumbWidth
            def fset(self, val):
                self.__thumbWidth = val
            return property(fget=fget, fset=fset)
        def thumbHeight(self):
            def fget(self):
                return self.__thumbHeight
            def fset(self, val):
                self.__thumbHeight = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def title(self):
            def fget(self):
                return self.__title
            def fset(self, val):
                self.__title = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def totalSteps(self):
            def fget(self):
                return self.__totalSteps
            return property(fget=fget)
        @dynamic_property
        def useSeriesPrefixInTitlesSection(self):
            def fget(self):
                return self.__useSeriesPrefixInTitlesSection
            def fset(self, val):
                self.__useSeriesPrefixInTitlesSection = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def verbose(self):
            def fget(self):
                return self.__verbose
            def fset(self, val):
                self.__verbose = val
            return property(fget=fget, fset=fset)

        @dynamic_property
        def READING_SYMBOL(self):
            def fget(self):
                return '<span style="color:black">&#x25b7;</span>' if self.generateForKindle else \
                        '<span style="color:white">+</span>'
            return property(fget=fget)
        @dynamic_property
        def FULL_RATING_SYMBOL(self):
            def fget(self):
                return self.__output_profile.ratings_char
            return property(fget=fget)
        @dynamic_property
        def EMPTY_RATING_SYMBOL(self):
            def fget(self):
                return self.__output_profile.empty_ratings_char
            return property(fget=fget)
        @dynamic_property

        def READ_PROGRESS_SYMBOL(self):
            def fget(self):
                return "&#9642;" if self.generateForKindle else '+'
            return property(fget=fget)
        @dynamic_property
        def UNREAD_PROGRESS_SYMBOL(self):
            def fget(self):
                return "&#9643;" if self.generateForKindle else '-'
            return property(fget=fget)

    # Methods
    def buildSources(self):
        if self.booksByTitle is None:
            if not self.fetchBooksByTitle():
                return False
        if not self.fetchBooksByAuthor():
            return False
        self.fetchBookmarks()
        if self.opts.generate_descriptions:
            self.generateThumbnails()
            self.generateHTMLDescriptions()
        if self.opts.generate_authors:
            self.generateHTMLByAuthor()
        if self.opts.generate_titles:
            self.generateHTMLByTitle()
        if self.opts.generate_series:
            self.generateHTMLBySeries()
        if self.opts.generate_genres:
            self.generateHTMLByTags()
            # If this is the only Section, and there are no genres, bail
            if self.opts.section_list == ['Genres'] and not self.genres:
                error_msg = _("No enabled genres found to catalog.\n")
                if not self.opts.cli_environment:
                    error_msg += "Check 'Excluded genres'\nin E-book options.\n"
                self.opts.log.error(error_msg)
                self.error.append(_('No books available to catalog'))
                self.error.append(error_msg)
                return False
        if self.opts.generate_recently_added:
            self.generateHTMLByDateAdded()
            if self.generateRecentlyRead:
                self.generateHTMLByDateRead()

        self.generateOPF()
        self.generateNCXHeader()
        if self.opts.generate_authors:
            self.generateNCXByAuthor(_("Authors"))
        if self.opts.generate_titles:
            self.generateNCXByTitle(_("Titles"))
        if self.opts.generate_series:
            self.generateNCXBySeries(_("Series"))
        if self.opts.generate_genres:
            self.generateNCXByGenre(_("Genres"))
        if self.opts.generate_recently_added:
            self.generateNCXByDateAdded(_("Recently Added"))
            if self.generateRecentlyRead:
                self.generateNCXByDateRead(_("Recently Read"))
        if self.opts.generate_descriptions:
            self.generateNCXDescriptions(_("Descriptions"))

        self.writeNCX()
        return True

    def cleanUp(self):
        pass

    def copyResources(self):
        '''Move resource files to self.catalogPath'''
        catalog_resources = P("catalog")

        files_to_copy = [('','DefaultCover.jpg'),
                            ('content','stylesheet.css'),
                            ('images','mastheadImage.gif')]

        for file in files_to_copy:
            if file[0] == '':
                shutil.copy(os.path.join(catalog_resources,file[1]),
                                self.catalogPath)
            else:
                shutil.copy(os.path.join(catalog_resources,file[1]),
                                os.path.join(self.catalogPath, file[0]))

        # Create the custom masthead image overwriting default
        # If failure, default mastheadImage.gif should still be in place
        if self.generateForKindle:
            try:
                self.generateMastheadImage(os.path.join(self.catalogPath,
                                                'images/mastheadImage.gif'))
            except:
                pass

    def fetchBooksByAuthor(self):
        '''
        Generate a list of titles sorted by author from the database
        return = Success
        '''

        self.updateProgressFullStep("Sorting database")
        self.booksByAuthor = list(self.booksByTitle)
        self.booksByAuthor = sorted(self.booksByAuthor, key=self.booksByAuthorSorter_author)

        # Build the unique_authors set from existing data, test for author_sort mismatches
        authors = [(record['author'], record['author_sort']) for record in self.booksByAuthor]
        current_author = authors[0]
        for (i,author) in enumerate(authors):
            if author != current_author and i:
                if author[0] == current_author[0]:
                    if self.opts.fmt == 'mobi':
                        # Exit if building MOBI
                        error_msg = _(
'''Inconsistent Author Sort values for
Author '{0}':
'{1}' <> '{2}'
Unable to build MOBI catalog.\n
Select all books by '{0}', apply correct Author Sort value in Edit Metadata dialog, then rebuild the catalog.\n''').format(author[0],author[1],current_author[1])
                        self.opts.log.warn('\n*** Metadata error ***')
                        self.opts.log.warn(error_msg)

                        self.error.append('Author Sort mismatch')
                        self.error.append(error_msg)
                        return False
                    else:
                        # Warning if building non-MOBI
                        if not self.error:
                            self.error.append('Author Sort mismatch')

                        error_msg = _(
'''Warning: inconsistent Author Sort values for
Author '{0}':
'{1}' <> '{2}'\n''').format(author[0],author[1],current_author[1])
                        self.opts.log.warn('\n*** Metadata warning ***')
                        self.opts.log.warn(error_msg)
                        self.error.append(error_msg)

                current_author = author

        self.booksByAuthor = sorted(self.booksByAuthor,
                                    key=lambda x: sort_key(self.booksByAuthorSorter_author_sort(x)))

        # Build the unique_authors set from existing data
        authors = [(record['author'], capitalize(record['author_sort'])) for record in self.booksByAuthor]

        # authors[] contains a list of all book authors, with multiple entries for multiple books by author
        #        authors[]: (([0]:friendly  [1]:sort))
        # unique_authors[]: (([0]:friendly  [1]:sort  [2]:book_count))
        books_by_current_author = 0
        current_author = authors[0]
        multiple_authors = False
        unique_authors = []
        for (i,author) in enumerate(authors):
            if author != current_author:
                # Note that current_author and author are tuples: (friendly, sort)
                multiple_authors = True

                # New author, save the previous author/sort/count
                unique_authors.append((current_author[0], icu_title(current_author[1]),
                                        books_by_current_author))
                current_author = author
                books_by_current_author = 1
            elif i==0 and len(authors) == 1:
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

        if False and self.verbose:
            self.opts.log.info("\nfetchBooksByauthor(): %d unique authors" % len(unique_authors))
            for author in unique_authors:
                self.opts.log.info((u" %-50s %-25s %2d" % (author[0][0:45], author[1][0:20],
                    author[2])).encode('utf-8'))

        self.authors = unique_authors
        return True

    def fetchBooksByTitle(self):
        self.updateProgressFullStep("Fetching database")

        self.opts.sort_by = 'title'

        # Merge opts.exclude_tags with opts.search_text
        # Updated to use exact match syntax

        exclude_tags = []
        for rule in self.opts.exclusion_rules:
            if rule[1].lower() == 'tags':
                exclude_tags.extend(rule[2].split(','))

        # Remove dups
        self.exclude_tags = exclude_tags = list(set(exclude_tags))

        # Report tag exclusions
        if self.opts.verbose and self.exclude_tags:
            data = self.db.get_data_as_dict(ids=self.opts.ids)
            for record in data:
                matched = list(set(record['tags']) & set(exclude_tags))
                if matched :
                    self.opts.log.info("     - %s by %s (Exclusion rule Tags: '%s')" %
                        (record['title'], record['authors'][0], str(matched[0])))

        search_phrase = ''
        if exclude_tags:
            search_terms = []
            for tag in exclude_tags:
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
        data = self.processExclusions(data)

        # Populate this_title{} from data[{},{}]
        titles = []
        for record in data:
            this_title = {}

            this_title['id'] = record['id']
            this_title['uuid'] = record['uuid']

            this_title['title'] = self.convertHTMLEntities(record['title'])
            if record['series']:
                this_title['series'] = record['series']
                this_title['series_index'] = record['series_index']
            else:
                this_title['series'] = None
                this_title['series_index'] = 0.0

            this_title['title_sort'] = self.generateSortTitle(this_title['title'])
            if 'authors' in record:
                # from calibre.ebooks.metadata import authors_to_string
                # return authors_to_string(self.authors)

                this_title['authors'] = record['authors']
                if record['authors']:
                    this_title['author'] = " &amp; ".join(record['authors'])
                else:
                    this_title['author'] = 'Unknown'

            if 'author_sort' in record and record['author_sort'].strip():
                this_title['author_sort'] = record['author_sort']
            else:
                this_title['author_sort'] = self.author_to_author_sort(this_title['author'])

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

                this_title['description'] = self.markdownComments(record['comments'])

                # Create short description
                paras = BeautifulSoup(this_title['description']).findAll('p')
                tokens = []
                for p in paras:
                    for token in p.contents:
                        if token.string is not None:
                            tokens.append(token.string)
                this_title['short_description'] = self.generateShortDescription(' '.join(tokens), dest="description")
            else:
                this_title['description'] = None
                this_title['short_description'] = None

            # Merge with custom field/value
            if self.__merge_comments['field']:
                this_title['description'] = self.mergeComments(this_title)

            if record['cover']:
                this_title['cover'] = re.sub('&amp;', '&', record['cover'])

            this_title['prefix'] = self.discoverPrefix(record)

            if record['tags']:
                this_title['tags'] = self.processSpecialTags(record['tags'],
                                        this_title, self.opts)
            if record['formats']:
                formats = []
                for format in record['formats']:
                    formats.append(self.convertHTMLEntities(format))
                this_title['formats'] = formats

            # Add user notes to be displayed in header
            # Special case handling for datetime fields and lists
            if self.opts.header_note_source_field:
                field_md = self.__db.metadata_for_field(self.opts.header_note_source_field)
                notes = self.__db.get_field(record['id'],
                                    self.opts.header_note_source_field,
                                    index_is_id=True)
                if notes:
                    if field_md['datatype'] == 'text':
                        if isinstance(notes,list):
                            notes = ' &middot; '.join(notes)
                    elif field_md['datatype'] == 'datetime':
                        notes = format_date(notes,'dd MMM yyyy')
                    this_title['notes'] = {'source':field_md['name'],
                                                'content':notes}

            titles.append(this_title)

        # Re-sort based on title_sort
        if len(titles):
            #self.booksByTitle = sorted(titles,
            #                        key=lambda x:(x['title_sort'].upper(), x['title_sort'].upper()))

            self.booksByTitle = sorted(titles, key=lambda x: sort_key(x['title_sort'].upper()))

            if False and self.verbose:
                self.opts.log.info("fetchBooksByTitle(): %d books" % len(self.booksByTitle))
                self.opts.log.info(" %-40s %-40s" % ('title', 'title_sort'))
                for title in self.booksByTitle:
                    self.opts.log.info((u" %-40s %-40s" % (title['title'][0:40],
                                                            title['title_sort'][0:40])).decode('mac-roman'))
            return True
        else:
            error_msg = _("No books found to catalog.\nCheck 'Excluded books' criteria in E-book options.\n")
            self.opts.log.error('*** ' + error_msg + ' ***')
            self.error.append(_('No books available to include in catalog'))
            self.error.append(error_msg)
            return False

    def fetchBookmarks(self):
        '''
        Collect bookmarks for catalog entries
        This will use the system default save_template specified in
        Preferences|Add/Save|Sending to device, not a customized one specified in
        the Kindle plugin
        '''
        from calibre.devices.usbms.device import Device
        from calibre.devices.kindle.driver import Bookmark
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

        def resolve_bookmark_paths(storage, path_map):
            pop_list = []
            book_ext = {}
            for id in path_map:
                file_fmts = set()
                for fmt in path_map[id]['fmts']:
                    file_fmts.add(fmt)

                bookmark_extension = None
                if file_fmts.intersection(mbp_formats):
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
                        bkmk_path = path_map[id]['path'].replace(os.path.abspath('/<storage>'),vol)
                        bkmk_path = bkmk_path.replace('bookmark',bookmark_extension)
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

        if self.generateRecentlyRead:
            self.opts.log.info("     Collecting Kindle bookmarks matching catalog entries")

            d = BookmarkDevice(None)
            d.initialize(self.opts.connected_device['save_template'])

            bookmarks = {}
            for book in self.booksByTitle:
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

                    path_map, book_ext = resolve_bookmark_paths(self.opts.connected_device['storage'], path_map)
                    if path_map:
                        bookmark_ext = path_map[id].rpartition('.')[2]
                        myBookmark = Bookmark(path_map[id], id, book_ext[id], bookmark_ext)
                        try:
                            book['percent_read'] = min(float(100*myBookmark.last_read / myBookmark.book_length),100)
                        except:
                            book['percent_read'] = 0
                        dots = int((book['percent_read'] + 5)/10)
                        dot_string = self.READ_PROGRESS_SYMBOL * dots
                        empty_dots = self.UNREAD_PROGRESS_SYMBOL * (10 - dots)
                        book['reading_progress'] = '%s%s' % (dot_string,empty_dots)
                        bookmarks[id] = ((myBookmark,book))

            self.bookmarked_books = bookmarks
        else:
            self.bookmarked_books = {}

    def generateHTMLDescriptions(self):
        '''
        Write each title to a separate HTML file in contentdir
        '''
        self.updateProgressFullStep("'Descriptions'")

        for (title_num, title) in enumerate(self.booksByTitle):
            self.updateProgressMicroStep("Description %d of %d" % \
                                            (title_num, len(self.booksByTitle)),
                                            float(title_num*100/len(self.booksByTitle))/100)

            # Generate the header from user-customizable template
            soup = self.generateHTMLDescriptionHeader(title)

            # Write the book entry to contentdir
            outfile = open("%s/book_%d.html" % (self.contentDir, int(title['id'])), 'w')
            outfile.write(soup.prettify())
            outfile.close()

    def generateHTMLByTitle(self):
        '''
        Write books by title A-Z to HTML file
        '''
        self.updateProgressFullStep("'Titles'")

        soup = self.generateHTMLEmptyHeader("Books By Alpha Title")
        body = soup.find('body')
        btc = 0

        pTag = Tag(soup, "p")
        pTag['class'] = 'title'
        ptc = 0
        aTag = Tag(soup,'a')
        aTag['id'] = 'section_start'
        pTag.insert(ptc, aTag)
        ptc += 1

        if not self.__generateForKindle:
            # Kindle don't need this because it shows section titles in Periodical format
            aTag = Tag(soup, "a")
            aTag['id'] = "bytitle"
            pTag.insert(ptc,aTag)
            ptc += 1
            pTag.insert(ptc,NavigableString(_('Titles')))

        body.insert(btc,pTag)
        btc += 1

        divTag = Tag(soup, "div")
        dtc = 0
        current_letter = ""

        # Re-sort title list without leading series/series_index
        # Incoming title <series> <series_index>: <title>
        if not self.useSeriesPrefixInTitlesSection:
            nspt = deepcopy(self.booksByTitle)
            nspt = sorted(nspt, key=lambda x: sort_key(x['title_sort'].upper()))
            self.booksByTitle_noSeriesPrefix = nspt

        # Establish initial letter equivalencies
        sort_equivalents = self.establish_equivalencies(self.booksByTitle, key='title_sort')

        # Loop through the books by title
        # Generate one divRunningTag per initial letter for the purposes of
        # minimizing widows and orphans on readers that can handle large
        # <divs> styled as inline-block
        title_list = self.booksByTitle
        if not self.useSeriesPrefixInTitlesSection:
            title_list = self.booksByTitle_noSeriesPrefix
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
                    pIndexTag.insert(0,aTag)
                    pIndexTag.insert(1,NavigableString(self.SYMBOLS))
                else:
                    aTag['id'] = self.generateUnicodeName(current_letter) + "_titles"
                    pIndexTag.insert(0,aTag)
                    pIndexTag.insert(1,NavigableString(sort_equivalents[idx]))
                divRunningTag.insert(dtc,pIndexTag)
                drtc += 1

            # Add books
            pBookTag = Tag(soup, "p")
            pBookTag['class'] = "line_item"
            ptc = 0

            pBookTag.insert(ptc, self.formatPrefix(book['prefix'],soup))
            ptc += 1

            spanTag = Tag(soup, "span")
            spanTag['class'] = "entry"
            stc = 0


            # Link to book
            aTag = Tag(soup, "a")
            if self.opts.generate_descriptions:
                aTag['href'] = "book_%d.html" % (int(float(book['id'])))

            # Generate the title from the template
            args = self.generateFormatArgs(book)
            if book['series']:
                formatted_title = self.by_titles_series_title_template.format(**args).rstrip()
            else:
                formatted_title = self.by_titles_normal_title_template.format(**args).rstrip()
            aTag.insert(0,NavigableString(escape(formatted_title)))
            spanTag.insert(stc, aTag)
            stc += 1

            # Dot
            spanTag.insert(stc, NavigableString(" &middot; "))
            stc += 1

            # Link to author
            emTag = Tag(soup, "em")
            aTag = Tag(soup, "a")
            if self.opts.generate_authors:
                aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generateAuthorAnchor(book['author']))
            aTag.insert(0, NavigableString(book['author']))
            emTag.insert(0,aTag)
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

        # Write the volume to contentdir
        outfile_spec = "%s/ByAlphaTitle.html" % (self.contentDir)
        outfile = open(outfile_spec, 'w')
        outfile.write(soup.prettify())
        outfile.close()
        self.htmlFileList_1.append("content/ByAlphaTitle.html")

    def generateHTMLByAuthor(self):
        '''
        Write books by author A-Z
        '''
        self.updateProgressFullStep("'Authors'")

        friendly_name = _("Authors")

        soup = self.generateHTMLEmptyHeader(friendly_name)
        body = soup.find('body')

        btc = 0

        divTag = Tag(soup, "div")
        dtc = 0
        divOpeningTag = None
        dotc = 0
        divRunningTag = None
        drtc = 0

        # Loop through booksByAuthor
        # Each author/books group goes in an openingTag div (first) or
        # a runningTag div (subsequent)
        book_count = 0
        current_author = ''
        current_letter = ''
        current_series = None
        # Establish initial letter equivalencies
        sort_equivalents = self.establish_equivalencies(self.booksByAuthor,key='author_sort')

        #for book in sorted(self.booksByAuthor, key = self.booksByAuthorSorter_author_sort):
        #for book in self.booksByAuthor:
        for idx, book in enumerate(self.booksByAuthor):
            book_count += 1
            if self.letter_or_symbol(sort_equivalents[idx]) != current_letter :
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
                    pIndexTag.insert(0,aTag)
                    pIndexTag.insert(1,NavigableString(self.SYMBOLS))
                else:
                    aTag['id'] = self.generateUnicodeName(current_letter) + '_authors'
                    pIndexTag.insert(0,aTag)
                    pIndexTag.insert(1,NavigableString(sort_equivalents[idx]))
                divOpeningTag.insert(dotc,pIndexTag)
                dotc += 1

            if book['author'] != current_author:
                # Start a new author
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
                aTag['id'] = "%s" % self.generateAuthorAnchor(current_author)
                aTag.insert(0,NavigableString(current_author))
                pAuthorTag.insert(0,aTag)
                if author_count == 1:
                    divOpeningTag.insert(dotc, pAuthorTag)
                    dotc += 1
                else:
                    divRunningTag.insert(drtc,pAuthorTag)
                    drtc += 1

            # Check for series
            if book['series'] and book['series'] != current_series:
                # Start a new series
                current_series = book['series']
                pSeriesTag = Tag(soup,'p')
                pSeriesTag['class'] = "series"
                if self.opts.fmt == 'mobi':
                    pSeriesTag['class'] = "series_mobi"
                if self.opts.generate_series:
                    aTag = Tag(soup,'a')
                    aTag['href'] = "%s.html#%s" % ('BySeries',self.generateSeriesAnchor(book['series']))
                    aTag.insert(0, book['series'])
                    pSeriesTag.insert(0, aTag)
                else:
                    pSeriesTag.insert(0,NavigableString('%s' % book['series']))

                if author_count == 1:
                    divOpeningTag.insert(dotc, pSeriesTag)
                    dotc += 1
                elif divRunningTag is not None:
                    divRunningTag.insert(drtc,pSeriesTag)
                    drtc += 1
            if current_series and not book['series']:
                current_series = None

            # Add books
            pBookTag = Tag(soup, "p")
            pBookTag['class'] = "line_item"
            ptc = 0

            pBookTag.insert(ptc, self.formatPrefix(book['prefix'],soup))
            ptc += 1

            spanTag = Tag(soup, "span")
            spanTag['class'] = "entry"
            stc = 0

            aTag = Tag(soup, "a")
            if self.opts.generate_descriptions:
                aTag['href'] = "book_%d.html" % (int(float(book['id'])))

            # Generate the title from the template
            args = self.generateFormatArgs(book)
            if current_series:
                #aTag.insert(0,'%s%s' % (escape(book['title'][len(book['series'])+1:]),pubyear))
                formatted_title = self.by_authors_series_title_template.format(**args).rstrip()
            else:
                #aTag.insert(0,'%s%s' % (escape(book['title']), pubyear))
                formatted_title = self.by_authors_normal_title_template.format(**args).rstrip()
                non_series_books += 1
            aTag.insert(0,NavigableString(escape(formatted_title)))

            spanTag.insert(ptc, aTag)
            stc += 1
            pBookTag.insert(ptc, spanTag)
            ptc += 1

            if author_count == 1:
                divOpeningTag.insert(dotc, pBookTag)
                dotc += 1
            elif divRunningTag:
                divRunningTag.insert(drtc,pBookTag)
                drtc += 1

        # Loop ends here

        pTag = Tag(soup, "p")
        pTag['class'] = 'title'
        ptc = 0
        aTag = Tag(soup,'a')
        aTag['id'] = 'section_start'
        pTag.insert(ptc, aTag)
        ptc += 1

        if not self.__generateForKindle:
            # Kindle don't need this because it shows section titles in Periodical format
            aTag = Tag(soup, "a")
            anchor_name = friendly_name.lower()
            aTag['id'] = anchor_name.replace(" ","")
            pTag.insert(ptc,aTag)
            ptc += 1
            pTag.insert(ptc,NavigableString('%s' % (friendly_name)))

        body.insert(btc,pTag)
        btc += 1

        if author_count == 1:
            divTag.insert(dtc, divOpeningTag)
            dtc += 1
        elif divRunningTag is not None:
            divTag.insert(dtc, divRunningTag)
            dtc += 1

        # Add the divTag to the body
        body.insert(btc, divTag)

        # Write the generated file to contentdir
        outfile_spec = "%s/ByAlphaAuthor.html" % (self.contentDir)
        outfile = open(outfile_spec, 'w')
        outfile.write(soup.prettify())
        outfile.close()
        self.htmlFileList_1.append("content/ByAlphaAuthor.html")

    def generateHTMLByDateAdded(self):
        '''
        Write books by reverse chronological order
        '''
        self.updateProgressFullStep("'Recently Added'")

        def add_books_to_HTML_by_month(this_months_list, dtc):
            if len(this_months_list):

                this_months_list = sorted(this_months_list, key=lambda x: sort_key(self.booksByAuthorSorter_author_sort(x)))

                # Create a new month anchor
                date_string = strftime(u'%B %Y', current_date.timetuple())
                pIndexTag = Tag(soup, "p")
                pIndexTag['class'] = "date_index"
                aTag = Tag(soup, "a")
                aTag['id'] = "bda_%s-%s" % (current_date.year, current_date.month)
                pIndexTag.insert(0,aTag)
                pIndexTag.insert(1,NavigableString(date_string))
                divTag.insert(dtc,pIndexTag)
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
                            aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generateAuthorAnchor(current_author))
                        aTag.insert(0,NavigableString(current_author))
                        pAuthorTag.insert(0,aTag)
                        divTag.insert(dtc,pAuthorTag)
                        dtc += 1

                    # Check for series
                    if new_entry['series'] and new_entry['series'] != current_series:
                        # Start a new series
                        current_series = new_entry['series']
                        pSeriesTag = Tag(soup,'p')
                        pSeriesTag['class'] = "series"
                        if self.opts.fmt == 'mobi':
                            pSeriesTag['class'] = "series_mobi"
                        if self.opts.generate_series:
                            aTag = Tag(soup,'a')

                            if self.letter_or_symbol(new_entry['series']) == self.SYMBOLS:
                                aTag['href'] = "%s.html#%s" % ('BySeries',self.generateSeriesAnchor(new_entry['series']))
                            aTag.insert(0, new_entry['series'])
                            pSeriesTag.insert(0, aTag)
                        else:
                            pSeriesTag.insert(0,NavigableString('%s' % new_entry['series']))
                        divTag.insert(dtc,pSeriesTag)
                        dtc += 1
                    if current_series and not new_entry['series']:
                        current_series = None

                    # Add books
                    pBookTag = Tag(soup, "p")
                    pBookTag['class'] = "line_item"
                    ptc = 0

                    pBookTag.insert(ptc, self.formatPrefix(new_entry['prefix'],soup))
                    ptc += 1

                    spanTag = Tag(soup, "span")
                    spanTag['class'] = "entry"
                    stc = 0

                    aTag = Tag(soup, "a")
                    if self.opts.generate_descriptions:
                        aTag['href'] = "book_%d.html" % (int(float(new_entry['id'])))

                    # Generate the title from the template
                    args = self.generateFormatArgs(new_entry)
                    if current_series:
                        formatted_title = self.by_month_added_series_title_template.format(**args).rstrip()
                    else:
                        formatted_title = self.by_month_added_normal_title_template.format(**args).rstrip()
                        non_series_books += 1
                    aTag.insert(0,NavigableString(escape(formatted_title)))
                    spanTag.insert(stc, aTag)
                    stc += 1

                    pBookTag.insert(ptc, spanTag)
                    ptc += 1

                    divTag.insert(dtc, pBookTag)
                    dtc += 1
            return dtc

        def add_books_to_HTML_by_date_range(date_range_list, date_range, dtc):
            if len(date_range_list):
                pIndexTag = Tag(soup, "p")
                pIndexTag['class'] = "date_index"
                aTag = Tag(soup, "a")
                aTag['id'] = "bda_%s" % date_range.replace(' ','')
                pIndexTag.insert(0,aTag)
                pIndexTag.insert(1,NavigableString(date_range))
                divTag.insert(dtc,pIndexTag)
                dtc += 1

                for new_entry in date_range_list:
                    # Add books
                    pBookTag = Tag(soup, "p")
                    pBookTag['class'] = "line_item"
                    ptc = 0

                    pBookTag.insert(ptc, self.formatPrefix(new_entry['prefix'],soup))
                    ptc += 1

                    spanTag = Tag(soup, "span")
                    spanTag['class'] = "entry"
                    stc = 0

                    aTag = Tag(soup, "a")
                    if self.opts.generate_descriptions:
                        aTag['href'] = "book_%d.html" % (int(float(new_entry['id'])))

                    # Generate the title from the template
                    args = self.generateFormatArgs(new_entry)
                    if new_entry['series']:
                        formatted_title = self.by_recently_added_series_title_template.format(**args).rstrip()
                    else:
                        formatted_title = self.by_recently_added_normal_title_template.format(**args).rstrip()
                    aTag.insert(0,NavigableString(escape(formatted_title)))
                    spanTag.insert(stc, aTag)
                    stc += 1

                    # Dot
                    spanTag.insert(stc, NavigableString(" &middot; "))
                    stc += 1

                    # Link to author
                    emTag = Tag(soup, "em")
                    aTag = Tag(soup, "a")
                    if self.opts.generate_authors:
                        aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generateAuthorAnchor(new_entry['author']))
                    aTag.insert(0, NavigableString(new_entry['author']))
                    emTag.insert(0,aTag)
                    spanTag.insert(stc, emTag)
                    stc += 1

                    pBookTag.insert(ptc, spanTag)
                    ptc += 1

                    divTag.insert(dtc, pBookTag)
                    dtc += 1
            return dtc

        friendly_name = _("Recently Added")

        soup = self.generateHTMLEmptyHeader(friendly_name)
        body = soup.find('body')

        btc = 0

        pTag = Tag(soup, "p")
        pTag['class'] = 'title'
        ptc = 0

        aTag = Tag(soup,'a')
        aTag['id'] = 'section_start'
        pTag.insert(ptc, aTag)
        ptc += 1

        if not self.__generateForKindle:
            # Kindle don't need this because it shows section titles in Periodical format
            aTag = Tag(soup, "a")
            anchor_name = friendly_name.lower()
            aTag['id'] = anchor_name.replace(" ","")

            pTag.insert(ptc,aTag)
            ptc += 1
            pTag.insert(ptc, NavigableString('%s' % friendly_name))

        body.insert(btc,pTag)
        btc += 1

        divTag = Tag(soup, "div")
        dtc = 0

        # >>> Books by date range <<<
        if self.useSeriesPrefixInTitlesSection:
            self.booksByDateRange = sorted(self.booksByTitle,
                                key=lambda x:(x['timestamp'], x['timestamp']),reverse=True)
        else:
            nspt = deepcopy(self.booksByTitle)
            self.booksByDateRange = sorted(nspt, key=lambda x:(x['timestamp'], x['timestamp']),reverse=True)

        date_range_list = []
        today_time = nowf().replace(hour=23, minute=59, second=59)
        for (i, date) in enumerate(self.DATE_RANGE):
            date_range_limit = self.DATE_RANGE[i]
            if i:
                date_range = '%d to %d days ago' % (self.DATE_RANGE[i-1], self.DATE_RANGE[i])
            else:
                date_range = 'Last %d days' % (self.DATE_RANGE[i])

            for book in self.booksByDateRange:
                book_time = book['timestamp']
                delta = today_time-book_time
                if delta.days <= date_range_limit:
                    date_range_list.append(book)
                else:
                    break

            dtc = add_books_to_HTML_by_date_range(date_range_list, date_range, dtc)
            date_range_list = [book]

        # >>>> Books by month <<<<
        # Sort titles case-insensitive for by month using series prefix
        self.booksByMonth = sorted(self.booksByTitle,
                                key=lambda x:(x['timestamp'], x['timestamp']),reverse=True)

        # Loop through books by date
        current_date = datetime.date.fromordinal(1)
        this_months_list = []
        for book in self.booksByMonth:
            if book['timestamp'].month != current_date.month or \
                book['timestamp'].year != current_date.year:
                dtc = add_books_to_HTML_by_month(this_months_list, dtc)
                this_months_list = []
                current_date = book['timestamp'].date()
            this_months_list.append(book)

        # Add the last month's list
        add_books_to_HTML_by_month(this_months_list, dtc)

        # Add the divTag to the body
        body.insert(btc, divTag)

        # Write the generated file to contentdir
        outfile_spec = "%s/ByDateAdded.html" % (self.contentDir)
        outfile = open(outfile_spec, 'w')
        outfile.write(soup.prettify())
        outfile.close()
        self.htmlFileList_2.append("content/ByDateAdded.html")

    def generateHTMLByDateRead(self):
        '''
        Write books by active bookmarks
        '''
        friendly_name = _('Recently Read')
        self.updateProgressFullStep("'%s'" % friendly_name)
        if not self.bookmarked_books:
            return

        def add_books_to_HTML_by_day(todays_list, dtc):
            if len(todays_list):
                # Create a new day anchor
                date_string = strftime(u'%A, %B %d', current_date.timetuple())
                pIndexTag = Tag(soup, "p")
                pIndexTag['class'] = "date_index"
                aTag = Tag(soup, "a")
                aTag['name'] = "bdr_%s-%s-%s" % (current_date.year, current_date.month, current_date.day)
                pIndexTag.insert(0,aTag)
                pIndexTag.insert(1,NavigableString(date_string))
                divTag.insert(dtc,pIndexTag)
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
                    aTag.insert(0,escape(new_entry['title']))
                    pBookTag.insert(ptc, aTag)
                    ptc += 1

                    # Dot
                    pBookTag.insert(ptc, NavigableString(" &middot; "))
                    ptc += 1

                    # Link to author
                    emTag = Tag(soup, "em")
                    aTag = Tag(soup, "a")
                    if self.opts.generate_authors:
                        aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generateAuthorAnchor(new_entry['author']))
                    aTag.insert(0, NavigableString(new_entry['author']))
                    emTag.insert(0,aTag)
                    pBookTag.insert(ptc, emTag)
                    ptc += 1

                    divTag.insert(dtc, pBookTag)
                    dtc += 1
            return dtc

        def add_books_to_HTML_by_date_range(date_range_list, date_range, dtc):
            if len(date_range_list):
                pIndexTag = Tag(soup, "p")
                pIndexTag['class'] = "date_index"
                aTag = Tag(soup, "a")
                aTag['name'] = "bdr_%s" % date_range.replace(' ','')
                pIndexTag.insert(0,aTag)
                pIndexTag.insert(1,NavigableString(date_range))
                divTag.insert(dtc,pIndexTag)
                dtc += 1

                for new_entry in date_range_list:
                    # Add books
                    pBookTag = Tag(soup, "p")
                    pBookTag['class'] = "date_read"
                    ptc = 0

                    # Percent read
                    dots = int((new_entry['percent_read'] + 5)/10)
                    dot_string = self.READ_PROGRESS_SYMBOL * dots
                    empty_dots = self.UNREAD_PROGRESS_SYMBOL * (10 - dots)
                    pBookTag.insert(ptc, NavigableString('%s%s' % (dot_string,empty_dots)))
                    ptc += 1

                    aTag = Tag(soup, "a")
                    if self.opts.generate_descriptions:
                        aTag['href'] = "book_%d.html" % (int(float(new_entry['id'])))
                    aTag.insert(0,escape(new_entry['title']))
                    pBookTag.insert(ptc, aTag)
                    ptc += 1

                    # Dot
                    pBookTag.insert(ptc, NavigableString(" &middot; "))
                    ptc += 1

                    # Link to author
                    emTag = Tag(soup, "em")
                    aTag = Tag(soup, "a")
                    if self.opts.generate_authors:
                        aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generateAuthorAnchor(new_entry['author']))
                    aTag.insert(0, NavigableString(new_entry['author']))
                    emTag.insert(0,aTag)
                    pBookTag.insert(ptc, emTag)
                    ptc += 1

                    divTag.insert(dtc, pBookTag)
                    dtc += 1
            return dtc

        soup = self.generateHTMLEmptyHeader(friendly_name)
        body = soup.find('body')

        btc = 0

        # Insert section tag
        aTag = Tag(soup,'a')
        aTag['name'] = 'section_start'
        body.insert(btc, aTag)
        btc += 1

        # Insert the anchor
        aTag = Tag(soup, "a")
        anchor_name = friendly_name.lower()
        aTag['name'] = anchor_name.replace(" ","")
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
                book[1]['percent_read'] = min(float(100*book[0].last_read / book[0].book_length),100)
            except:
                book[1]['percent_read'] = 0
            bookmarked_books.append(book[1])

        self.booksByDateRead = sorted(bookmarked_books,
                            key=lambda x:(x['bookmark_timestamp'], x['bookmark_timestamp']),reverse=True)

        # >>>> Recently read by day <<<<
        current_date = datetime.date.fromordinal(1)
        todays_list = []
        for book in self.booksByDateRead:
            bookmark_time = datetime.datetime.utcfromtimestamp(book['bookmark_timestamp'])
            if bookmark_time.day != current_date.day or \
                bookmark_time.month != current_date.month or \
                bookmark_time.year != current_date.year:
                dtc = add_books_to_HTML_by_day(todays_list, dtc)
                todays_list = []
                current_date = datetime.datetime.utcfromtimestamp(book['bookmark_timestamp']).date()
            todays_list.append(book)

        # Add the last day's list
        add_books_to_HTML_by_day(todays_list, dtc)

        # Add the divTag to the body
        body.insert(btc, divTag)

        # Write the generated file to contentdir
        outfile_spec = "%s/ByDateRead.html" % (self.contentDir)
        outfile = open(outfile_spec, 'w')
        outfile.write(soup.prettify())
        outfile.close()
        self.htmlFileList_2.append("content/ByDateRead.html")

    def generateHTMLBySeries(self):
        '''
        Generate a list of series
        '''
        self.updateProgressFullStep("Fetching series")

        self.opts.sort_by = 'series'

        # Merge self.exclude_tags with opts.search_text
        # Updated to use exact match syntax

        search_phrase = 'series:true '
        if self.exclude_tags:
            search_terms = []
            for tag in self.exclude_tags:
                search_terms.append("tag:=%s" % tag)
            search_phrase += "not (%s)" % " or ".join(search_terms)

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

        # Remove exclusions
        self.booksBySeries = self.processExclusions(data)

        if not self.booksBySeries:
            self.opts.generate_series = False
            self.opts.log(" no series found in selected books, cancelling series generation")
            return

        # Generate series_sort
        for book in self.booksBySeries:
            book['series_sort'] = self.generateSortTitle(book['series'])

        friendly_name = _("Series")

        soup = self.generateHTMLEmptyHeader(friendly_name)
        body = soup.find('body')

        btc = 0
        divTag = Tag(soup, "div")
        dtc = 0
        current_letter = ""
        current_series = None

        # Establish initial letter equivalencies
        sort_equivalents = self.establish_equivalencies(self.booksBySeries, key='series_sort')

        # Loop through booksBySeries
        series_count = 0
        for idx, book in enumerate(self.booksBySeries):
            # Check for initial letter change
            if self.letter_or_symbol(sort_equivalents[idx]) != current_letter :
                # Start a new letter with Index letter
                current_letter = self.letter_or_symbol(sort_equivalents[idx])
                pIndexTag = Tag(soup, "p")
                pIndexTag['class'] = "series_letter_index"
                aTag = Tag(soup, "a")
                if current_letter == self.SYMBOLS:
                    aTag['id'] = self.SYMBOLS + "_series"
                    pIndexTag.insert(0,aTag)
                    pIndexTag.insert(1,NavigableString(self.SYMBOLS))
                else:
                    aTag['id'] = self.generateUnicodeName(current_letter) + "_series"
                    pIndexTag.insert(0,aTag)
                    pIndexTag.insert(1,NavigableString(sort_equivalents[idx]))
                divTag.insert(dtc,pIndexTag)
                dtc += 1
            # Check for series change
            if book['series'] != current_series:
                # Start a new series
                series_count += 1
                current_series = book['series']
                pSeriesTag = Tag(soup,'p')
                pSeriesTag['class'] = "series"
                if self.opts.fmt == 'mobi':
                    pSeriesTag['class'] = "series_mobi"
                aTag = Tag(soup, 'a')
                aTag['id'] = self.generateSeriesAnchor(book['series'])
                pSeriesTag.insert(0,aTag)
                pSeriesTag.insert(1,NavigableString('%s' % book['series']))
                divTag.insert(dtc,pSeriesTag)
                dtc += 1

            # Add books
            pBookTag = Tag(soup, "p")
            pBookTag['class'] = "line_item"
            ptc = 0

            book['prefix'] = self.discoverPrefix(book)
            pBookTag.insert(ptc, self.formatPrefix(book['prefix'],soup))
            ptc += 1

            spanTag = Tag(soup, "span")
            spanTag['class'] = "entry"
            stc = 0

            aTag = Tag(soup, "a")
            if self.opts.generate_descriptions:
                aTag['href'] = "book_%d.html" % (int(float(book['id'])))
            # Use series, series index if avail else just title
            #aTag.insert(0,'%d. %s &middot; %s' % (book['series_index'],escape(book['title']), ' & '.join(book['authors'])))

            if is_date_undefined(book['pubdate']):
                book['date'] = None
            else:
                book['date'] = strftime(u'%B %Y', book['pubdate'].timetuple())

            args = self.generateFormatArgs(book)
            formatted_title = self.by_series_title_template.format(**args).rstrip()
            aTag.insert(0,NavigableString(escape(formatted_title)))

            spanTag.insert(stc, aTag)
            stc += 1

            # &middot;
            spanTag.insert(stc, NavigableString(' &middot; '))
            stc += 1

            # Link to author
            aTag = Tag(soup, "a")
            if self.opts.generate_authors:
                aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor",
                                            self.generateAuthorAnchor(escape(' & '.join(book['authors']))))
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
        aTag = Tag(soup,'a')
        aTag['id'] = 'section_start'
        pTag.insert(ptc, aTag)
        ptc += 1

        if not self.__generateForKindle:
            # Insert the <h2> tag with book_count at the head
            aTag = Tag(soup, "a")
            anchor_name = friendly_name.lower()
            aTag['id'] = anchor_name.replace(" ","")
            pTag.insert(0,aTag)
            pTag.insert(1,NavigableString('%s' % friendly_name))
        body.insert(btc,pTag)
        btc += 1

        # Add the divTag to the body
        body.insert(btc, divTag)

        # Write the generated file to contentdir
        outfile_spec = "%s/BySeries.html" % (self.contentDir)
        outfile = open(outfile_spec, 'w')
        outfile.write(soup.prettify())
        outfile.close()
        self.htmlFileList_1.append("content/BySeries.html")

    def generateHTMLByTags(self):
        '''
        Generate individual HTML files for each tag, e.g. Fiction, Nonfiction ...
        Note that special tags -  have already been filtered from books[]
        There may be synonomous tags
        '''
        self.updateProgressFullStep("'Genres'")

        self.genre_tags_dict = self.filterDbTags(self.db.all_tags())
        # Extract books matching filtered_tags
        genre_list = []
        for friendly_tag in sorted(self.genre_tags_dict, key=sort_key):
            #print("\ngenerateHTMLByTags(): looking for books with friendly_tag '%s'" % friendly_tag)
            # tag_list => { normalized_genre_tag : [{book},{},{}],
            #               normalized_genre_tag : [{book},{},{}] }

            tag_list = {}
            for book in self.booksByAuthor:
                # Scan each book for tag matching friendly_tag
                if 'tags' in book and friendly_tag in book['tags']:
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
                self.opts.log.info("     Genre summary: %d active genre tags used in generating catalog with %d titles" %
                                (len(genre_list), len(self.booksByTitle)))

                for genre in genre_list:
                    for key in genre:
                        self.opts.log.info("      %s: %d %s" % (self.getFriendlyGenreTag(key),
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
                    authors.append((book['author'],book['author_sort']))

                # authors[] contains a list of all book authors, with multiple entries for multiple books by author
                # Create unique_authors with a count of books per author as the third tuple element
                books_by_current_author = 1
                current_author = authors[0]
                unique_authors = []
                for (i,author) in enumerate(authors):
                    if author != current_author and i:
                        unique_authors.append((current_author[0], current_author[1], books_by_current_author))
                        current_author = author
                        books_by_current_author = 1
                    elif i==0 and len(authors) == 1:
                        # Allow for single-book lists
                        unique_authors.append((current_author[0], current_author[1], books_by_current_author))
                    else:
                        books_by_current_author += 1

                # Write the genre book list as an article
                titles_spanned = self.generateHTMLByGenre(genre, True if index==0 else False,
                                        genre_tag_set[genre],
                                        "%s/Genre_%s.html" % (self.contentDir,
                                                            genre))

                tag_file = "content/Genre_%s.html" % genre
                master_genre_list.append({'tag':genre,
                                            'file':tag_file,
                                            'authors':unique_authors,
                                            'books':genre_tag_set[genre],
                                            'titles_spanned':titles_spanned})

        self.genres = master_genre_list

    def generateThumbnails(self):
        '''
        Generate a thumbnail per cover.  If a current thumbnail exists, skip
        If a cover doesn't exist, use default
        Return list of active thumbs
        '''
        self.updateProgressFullStep("'Thumbnails'")
        thumbs = ['thumbnail_default.jpg']
        image_dir = "%s/images" % self.catalogPath
        for (i,title) in enumerate(self.booksByTitle):
            # Update status
            self.updateProgressMicroStep("Thumbnail %d of %d" % \
                (i,len(self.booksByTitle)),
                    i/float(len(self.booksByTitle)))

            thumb_file = 'thumbnail_%d.jpg' % int(title['id'])
            thumb_generated = True
            valid_cover = True
            try:
                self.generateThumbnail(title, image_dir, thumb_file)
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
                default_thumb_fp = os.path.join(image_dir,"thumbnail_default.jpg")
                cover = os.path.join(self.catalogPath, "DefaultCover.png")
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
                        if False and self.verbose:
                            self.opts.log.warn("updating thumbnail_default for %s" % title['title'])
                        self.generateThumbnail(title, image_dir,
                                            "thumbnail_default.jpg" if valid_cover else thumb_file)
                else:
                    if False and self.verbose:
                        self.opts.log.warn(" generating new thumbnail_default.jpg")
                    self.generateThumbnail(title, image_dir,
                                            "thumbnail_default.jpg" if valid_cover else thumb_file)
                # Clear the book's cover property
                title['cover'] = None


        # Write thumb_width to the file, validating cache contents
        # Allows detection of aborted catalog builds
        with ZipFile(self.__archive_path, mode='a') as zfw:
            zfw.writestr('thumb_width', self.opts.thumb_width)

        self.thumbs = thumbs

    def generateOPF(self):

        self.updateProgressFullStep("Generating OPF")

        header = '''
            <?xml version="1.0" encoding="UTF-8"?>
            <package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="calibre_id">
                <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf" xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
                    <dc:language>en-US</dc:language>
                    <meta name="calibre:publication_type" content="periodical:default"/>
                </metadata>
                <manifest></manifest>
                <spine toc="ncx"></spine>
                <guide></guide>
            </package>
            '''
        # Add the supplied metadata tags
        soup = BeautifulStoneSoup(header, selfClosingTags=['item','itemref', 'reference'])
        metadata = soup.find('metadata')
        mtc = 0

        titleTag = Tag(soup, "dc:title")
        titleTag.insert(0,self.title)
        metadata.insert(mtc, titleTag)
        mtc += 1

        creatorTag = Tag(soup, "dc:creator")
        creatorTag.insert(0, self.creator)
        metadata.insert(mtc, creatorTag)
        mtc += 1

        # Create the OPF tags
        manifest = soup.find('manifest')
        mtc = 0
        spine = soup.find('spine')
        stc = 0
        guide = soup.find('guide')

        itemTag = Tag(soup, "item")
        itemTag['id'] = "ncx"
        itemTag['href'] = '%s.ncx' % self.basename
        itemTag['media-type'] = "application/x-dtbncx+xml"
        manifest.insert(mtc, itemTag)
        mtc += 1

        itemTag = Tag(soup, "item")
        itemTag['id'] = 'stylesheet'
        itemTag['href'] = self.stylesheet
        itemTag['media-type'] = 'text/css'
        manifest.insert(mtc, itemTag)
        mtc += 1

        itemTag = Tag(soup, "item")
        itemTag['id'] = 'mastheadimage-image'
        itemTag['href'] = "images/mastheadImage.gif"
        itemTag['media-type'] = 'image/gif'
        manifest.insert(mtc, itemTag)
        mtc += 1

        # Write the thumbnail images, descriptions to the manifest
        sort_descriptions_by = []
        if self.opts.generate_descriptions:
            for thumb in self.thumbs:
                itemTag = Tag(soup, "item")
                itemTag['href'] = "images/%s" % (thumb)
                end = thumb.find('.jpg')
                itemTag['id'] = "%s-image" % thumb[:end]
                itemTag['media-type'] = 'image/jpeg'
                manifest.insert(mtc, itemTag)
                mtc += 1

            # HTML files - add descriptions to manifest and spine
            sort_descriptions_by = self.booksByAuthor if self.opts.sort_descriptions_by_author \
                                                    else self.booksByTitle
        # Add html_files to manifest and spine

        for file in self.htmlFileList_1:
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
            if False: self.opts.log.info("adding %s to manifest and spine" % genre['tag'])
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

        for file in self.htmlFileList_2:
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

        for book in sort_descriptions_by:
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
        referenceTag = Tag(soup, "reference")
        referenceTag['type'] = 'masthead'
        referenceTag['title'] = 'mastheadimage-image'
        referenceTag['href'] = 'images/mastheadImage.gif'
        guide.insert(0,referenceTag)

        # Write the OPF file
        outfile = open("%s/%s.opf" % (self.catalogPath, self.basename), 'w')
        outfile.write(soup.prettify())

    def generateNCXHeader(self):

        self.updateProgressFullStep("NCX header")

        header = '''
            <?xml version="1.0" encoding="utf-8"?>
            <ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata" version="2005-1" xml:lang="en">
            </ncx>
        '''
        soup = BeautifulStoneSoup(header, selfClosingTags=['content','calibre:meta-img'])

        ncx = soup.find('ncx')
        navMapTag = Tag(soup, 'navMap')
        navPointTag = Tag(soup, 'navPoint')
        navPointTag['class'] = "periodical"
        navPointTag['id'] = "title"
        navPointTag['playOrder'] = self.playOrder
        self.playOrder += 1
        navLabelTag = Tag(soup, 'navLabel')
        textTag = Tag(soup, 'text')
        textTag.insert(0, NavigableString(self.title))
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
        else:
            # Descriptions only
            sort_descriptions_by = self.booksByAuthor if self.opts.sort_descriptions_by_author \
                                                        else self.booksByTitle
            contentTag = Tag(soup, 'content')
            contentTag['src'] = "content/book_%d.html" % int(sort_descriptions_by[0]['id'])
            navPointTag.insert(1, contentTag)

        cmiTag = Tag(soup, '%s' % 'calibre:meta-img')
        cmiTag['id'] = "mastheadImage"
        cmiTag['src'] = "images/mastheadImage.gif"
        navPointTag.insert(2,cmiTag)
        navMapTag.insert(0,navPointTag)

        ncx.insert(0,navMapTag)
        self.ncxSoup = soup

    def generateNCXDescriptions(self, tocTitle):

        self.updateProgressFullStep("NCX 'Descriptions'")

        # --- Construct the 'Books by Title' section ---
        ncx_soup = self.ncxSoup
        body = ncx_soup.find("navPoint")
        btc = len(body.contents)

        # Add the section navPoint
        navPointTag = Tag(ncx_soup, 'navPoint')
        navPointTag['class'] = "section"
        navPointTag['id'] = "bytitle-ID"
        navPointTag['playOrder'] = self.playOrder
        self.playOrder += 1
        navLabelTag = Tag(ncx_soup, 'navLabel')
        textTag = Tag(ncx_soup, 'text')
        textTag.insert(0, NavigableString(tocTitle))
        navLabelTag.insert(0, textTag)
        nptc = 0
        navPointTag.insert(nptc, navLabelTag)
        nptc += 1
        contentTag = Tag(ncx_soup,"content")
        contentTag['src'] = "content/book_%d.html" % int(self.booksByTitle[0]['id'])
        navPointTag.insert(nptc, contentTag)
        nptc += 1

        # Loop over the titles
        sort_descriptions_by = self.booksByAuthor if self.opts.sort_descriptions_by_author \
                                                    else self.booksByTitle

        for book in sort_descriptions_by:
            navPointVolumeTag = Tag(ncx_soup, 'navPoint')
            navPointVolumeTag['class'] = "article"
            navPointVolumeTag['id'] = "book%dID" % int(book['id'])
            navPointVolumeTag['playOrder'] = self.playOrder
            self.playOrder += 1
            navLabelTag = Tag(ncx_soup, "navLabel")
            textTag = Tag(ncx_soup, "text")
            if book['series']:
                series_index = str(book['series_index'])
                if series_index.endswith('.0'):
                    series_index = series_index[:-2]
                if self.generateForKindle:
                    # Don't include Author for Kindle
                    textTag.insert(0, NavigableString(self.formatNCXText('%s (%s [%s])' %
                                    (book['title'], book['series'], series_index), dest='title')))
                else:
                    # Include Author for non-Kindle
                    textTag.insert(0, NavigableString(self.formatNCXText('%s (%s [%s]) &middot; %s ' %
                                    (book['title'], book['series'], series_index, book['author']), dest='title')))
            else:
                if self.generateForKindle:
                    # Don't include Author for Kindle
                    title_str = self.formatNCXText('%s' % (book['title']), dest='title')
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
                    textTag.insert(0, NavigableString(self.formatNCXText('%s &middot; %s' % \
                                                    (book['title'], book['author']), dest='title')))
            navLabelTag.insert(0,textTag)
            navPointVolumeTag.insert(0,navLabelTag)

            contentTag = Tag(ncx_soup, "content")
            contentTag['src'] = "content/book_%d.html#book%d" % (int(book['id']), int(book['id']))
            navPointVolumeTag.insert(1, contentTag)

            if self.generateForKindle:
                # Add the author tag
                cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                cmTag['name'] = "author"

                if book['date']:
                    navStr = '%s | %s' % (self.formatNCXText(book['author'], dest='author'),
                            book['date'].split()[1])
                else:
                    navStr = '%s' % (self.formatNCXText(book['author'], dest='author'))

                if 'tags' in book and len(book['tags']):
                    navStr = self.formatNCXText(navStr + ' | ' + ' &middot; '.join(sorted(book['tags'])), dest='author')
                cmTag.insert(0, NavigableString(navStr))
                navPointVolumeTag.insert(2, cmTag)

                # Add the description tag
                if book['short_description']:
                    cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                    cmTag['name'] = "description"
                    cmTag.insert(0, NavigableString(self.formatNCXText(book['short_description'], dest='description')))
                    navPointVolumeTag.insert(3, cmTag)

            # Add this volume to the section tag
            navPointTag.insert(nptc, navPointVolumeTag)
            nptc += 1

        # Add this section to the body
        body.insert(btc, navPointTag)
        btc += 1

        self.ncxSoup = ncx_soup

    def generateNCXBySeries(self, tocTitle):
        self.updateProgressFullStep("NCX 'Series'")

        def add_to_series_by_letter(current_series_list):
            current_series_list = " &bull; ".join(current_series_list)
            current_series_list = self.formatNCXText(current_series_list, dest="description")
            series_by_letter.append(current_series_list)

        soup = self.ncxSoup
        output = "BySeries"
        body = soup.find("navPoint")
        btc = len(body.contents)

        # --- Construct the 'Books By Series' section ---
        navPointTag = Tag(soup, 'navPoint')
        navPointTag['class'] = "section"
        navPointTag['id'] = "byseries-ID"
        navPointTag['playOrder'] = self.playOrder
        self.playOrder += 1
        navLabelTag = Tag(soup, 'navLabel')
        textTag = Tag(soup, 'text')
        textTag.insert(0, NavigableString(tocTitle))
        navLabelTag.insert(0, textTag)
        nptc = 0
        navPointTag.insert(nptc, navLabelTag)
        nptc += 1
        contentTag = Tag(soup,"content")
        contentTag['src'] = "content/%s.html#section_start" % (output)
        navPointTag.insert(nptc, contentTag)
        nptc += 1

        series_by_letter = []
        # Establish initial letter equivalencies
        sort_equivalents = self.establish_equivalencies(self.booksBySeries, key='series_sort')

        # Loop over the series titles, find start of each letter, add description_preview_count books
        # Special switch for using different title list

        title_list = self.booksBySeries

        # Prime the pump
        current_letter = self.letter_or_symbol(sort_equivalents[0])

        title_letters = [current_letter]
        current_series_list = []
        current_series = ""
        for idx, book in enumerate(title_list):
            sort_title = self.generateSortTitle(book['series'])
            self.establish_equivalencies([sort_title])[0]
            if self.letter_or_symbol(sort_equivalents[idx]) != current_letter:

                # Save the old list
                add_to_series_by_letter(current_series_list)

                # Start the new list
                current_letter = self.letter_or_symbol(sort_equivalents[idx])
                title_letters.append(current_letter)
                current_series = book['series']
                current_series_list = [book['series']]
            else:
                if len(current_series_list) < self.descriptionClip and \
                    book['series'] != current_series :
                    current_series = book['series']
                    current_series_list.append(book['series'])

        # Add the last book list
        add_to_series_by_letter(current_series_list)

        # Add *article* entries for each populated series title letter
        for (i,books) in enumerate(series_by_letter):
            navPointByLetterTag = Tag(soup, 'navPoint')
            navPointByLetterTag['class'] = "article"
            navPointByLetterTag['id'] = "%sSeries-ID" % (title_letters[i].upper())
            navPointTag['playOrder'] = self.playOrder
            self.playOrder += 1
            navLabelTag = Tag(soup, 'navLabel')
            textTag = Tag(soup, 'text')
            textTag.insert(0, NavigableString(_(u"Series beginning with %s") % \
                (title_letters[i] if len(title_letters[i])>1 else "'" + title_letters[i] + "'")))
            navLabelTag.insert(0, textTag)
            navPointByLetterTag.insert(0,navLabelTag)
            contentTag = Tag(soup, 'content')
            #contentTag['src'] = "content/%s.html#%s_series" % (output, title_letters[i])
            if title_letters[i] == self.SYMBOLS:
                contentTag['src'] = "content/%s.html#%s_series" % (output, self.SYMBOLS)
            else:
                contentTag['src'] = "content/%s.html#%s_series" % (output, self.generateUnicodeName(title_letters[i]))

            navPointByLetterTag.insert(1,contentTag)

            if self.generateForKindle:
                cmTag = Tag(soup, '%s' % 'calibre:meta')
                cmTag['name'] = "description"
                cmTag.insert(0, NavigableString(self.formatNCXText(books, dest='description')))
                navPointByLetterTag.insert(2, cmTag)

            navPointTag.insert(nptc, navPointByLetterTag)
            nptc += 1

        # Add this section to the body
        body.insert(btc, navPointTag)
        btc += 1

        self.ncxSoup = soup

    def generateNCXByTitle(self, tocTitle):
        self.updateProgressFullStep("NCX 'Titles'")

        def add_to_books_by_letter(current_book_list):
            current_book_list = " &bull; ".join(current_book_list)
            current_book_list = self.formatNCXText(current_book_list, dest="description")
            books_by_letter.append(current_book_list)

        soup = self.ncxSoup
        output = "ByAlphaTitle"
        body = soup.find("navPoint")
        btc = len(body.contents)

        # --- Construct the 'Books By Title' section ---
        navPointTag = Tag(soup, 'navPoint')
        navPointTag['class'] = "section"
        navPointTag['id'] = "byalphatitle-ID"
        navPointTag['playOrder'] = self.playOrder
        self.playOrder += 1
        navLabelTag = Tag(soup, 'navLabel')
        textTag = Tag(soup, 'text')
        textTag.insert(0, NavigableString(tocTitle))
        navLabelTag.insert(0, textTag)
        nptc = 0
        navPointTag.insert(nptc, navLabelTag)
        nptc += 1
        contentTag = Tag(soup,"content")
        contentTag['src'] = "content/%s.html#section_start" % (output)
        navPointTag.insert(nptc, contentTag)
        nptc += 1

        books_by_letter = []

        # Establish initial letter equivalencies
        sort_equivalents = self.establish_equivalencies(self.booksByTitle, key='title_sort')

        # Loop over the titles, find start of each letter, add description_preview_count books
        # Special switch for using different title list
        if self.useSeriesPrefixInTitlesSection:
            title_list = self.booksByTitle
        else:
            title_list = self.booksByTitle_noSeriesPrefix

        # Prime the list
        current_letter = self.letter_or_symbol(sort_equivalents[0])
        title_letters = [current_letter]
        current_book_list = []
        current_book = ""
        for idx, book in enumerate(title_list):
            #if self.letter_or_symbol(book['title_sort'][0]) != current_letter:
            if self.letter_or_symbol(sort_equivalents[idx]) != current_letter:

                # Save the old list
                add_to_books_by_letter(current_book_list)

                # Start the new list
                #current_letter = self.letter_or_symbol(book['title_sort'][0])
                current_letter = self.letter_or_symbol(sort_equivalents[idx])
                title_letters.append(current_letter)
                current_book = book['title']
                current_book_list = [book['title']]
            else:
                if len(current_book_list) < self.descriptionClip and \
                    book['title'] != current_book :
                    current_book = book['title']
                    current_book_list.append(book['title'])

        # Add the last book list
        add_to_books_by_letter(current_book_list)

        # Add *article* entries for each populated title letter
        for (i,books) in enumerate(books_by_letter):
            navPointByLetterTag = Tag(soup, 'navPoint')
            navPointByLetterTag['class'] = "article"
            navPointByLetterTag['id'] = "%sTitles-ID" % (title_letters[i].upper())
            navPointTag['playOrder'] = self.playOrder
            self.playOrder += 1
            navLabelTag = Tag(soup, 'navLabel')
            textTag = Tag(soup, 'text')
            textTag.insert(0, NavigableString(_(u"Titles beginning with %s") % \
                (title_letters[i] if len(title_letters[i])>1 else "'" + title_letters[i] + "'")))
            navLabelTag.insert(0, textTag)
            navPointByLetterTag.insert(0,navLabelTag)
            contentTag = Tag(soup, 'content')
            if title_letters[i] == self.SYMBOLS:
                contentTag['src'] = "content/%s.html#%s_titles" % (output, self.SYMBOLS)
            else:
                contentTag['src'] = "content/%s.html#%s_titles" % (output, self.generateUnicodeName(title_letters[i]))
            navPointByLetterTag.insert(1,contentTag)

            if self.generateForKindle:
                cmTag = Tag(soup, '%s' % 'calibre:meta')
                cmTag['name'] = "description"
                cmTag.insert(0, NavigableString(self.formatNCXText(books, dest='description')))
                navPointByLetterTag.insert(2, cmTag)

            navPointTag.insert(nptc, navPointByLetterTag)
            nptc += 1

        # Add this section to the body
        body.insert(btc, navPointTag)
        btc += 1

        self.ncxSoup = soup

    def generateNCXByAuthor(self, tocTitle):
        self.updateProgressFullStep("NCX 'Authors'")

        def add_to_author_list(current_author_list, current_letter):
            current_author_list = " &bull; ".join(current_author_list)
            current_author_list = self.formatNCXText(current_author_list, dest="description")
            master_author_list.append((current_author_list, current_letter))

        soup = self.ncxSoup
        HTML_file = "content/ByAlphaAuthor.html"
        body = soup.find("navPoint")
        btc = len(body.contents)

        # --- Construct the 'Books By Author' *section* ---
        navPointTag = Tag(soup, 'navPoint')
        navPointTag['class'] = "section"
        file_ID = "%s" % tocTitle.lower()
        file_ID = file_ID.replace(" ","")
        navPointTag['id'] = "%s-ID" % file_ID
        navPointTag['playOrder'] = self.playOrder
        self.playOrder += 1
        navLabelTag = Tag(soup, 'navLabel')
        textTag = Tag(soup, 'text')
        textTag.insert(0, NavigableString('%s' % tocTitle))
        navLabelTag.insert(0, textTag)
        nptc = 0
        navPointTag.insert(nptc, navLabelTag)
        nptc += 1
        contentTag = Tag(soup,"content")
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
                add_to_author_list(current_author_list, current_letter)

                # Start the new list
                current_letter = self.letter_or_symbol(sort_equivalents[idx])
                current_author_list = [author[0]]
            else:
                if len(current_author_list) < self.descriptionClip:
                    current_author_list.append(author[0])

        # Add the last author list
        add_to_author_list(current_author_list, current_letter)

        # Add *article* entries for each populated author initial letter
        # master_author_list{}: [0]:author list [1]:Initial letter
        for authors_by_letter in master_author_list:
            navPointByLetterTag = Tag(soup, 'navPoint')
            navPointByLetterTag['class'] = "article"
            navPointByLetterTag['id'] = "%sauthors-ID" % (authors_by_letter[1])
            navPointTag['playOrder'] = self.playOrder
            self.playOrder += 1
            navLabelTag = Tag(soup, 'navLabel')
            textTag = Tag(soup, 'text')
            textTag.insert(0, NavigableString(_("Authors beginning with '%s'") % (authors_by_letter[1])))
            navLabelTag.insert(0, textTag)
            navPointByLetterTag.insert(0,navLabelTag)
            contentTag = Tag(soup, 'content')
            if authors_by_letter[1] == self.SYMBOLS:
                contentTag['src'] = "%s#%s_authors" % (HTML_file, authors_by_letter[1])
            else:
                contentTag['src'] = "%s#%s_authors" % (HTML_file, self.generateUnicodeName(authors_by_letter[1]))
            navPointByLetterTag.insert(1,contentTag)

            if self.generateForKindle:
                cmTag = Tag(soup, '%s' % 'calibre:meta')
                cmTag['name'] = "description"
                cmTag.insert(0, NavigableString(authors_by_letter[0]))
                navPointByLetterTag.insert(2, cmTag)

            navPointTag.insert(nptc, navPointByLetterTag)
            nptc += 1

        # Add this section to the body
        body.insert(btc, navPointTag)
        btc += 1

        self.ncxSoup = soup

    def generateNCXByDateAdded(self, tocTitle):
        self.updateProgressFullStep("NCX 'Recently Added'")

        def add_to_master_month_list(current_titles_list):
            book_count = len(current_titles_list)
            current_titles_list = " &bull; ".join(current_titles_list)
            current_titles_list = self.formatNCXText(current_titles_list, dest='description')
            master_month_list.append((current_titles_list, current_date, book_count))

        def add_to_master_date_range_list(current_titles_list):
            book_count = len(current_titles_list)
            current_titles_list = " &bull; ".join(current_titles_list)
            current_titles_list = self.formatNCXText(current_titles_list, dest='description')
            master_date_range_list.append((current_titles_list, date_range, book_count))

        soup = self.ncxSoup
        HTML_file = "content/ByDateAdded.html"
        body = soup.find("navPoint")
        btc = len(body.contents)

        # --- Construct the 'Recently Added' *section* ---
        navPointTag = Tag(soup, 'navPoint')
        navPointTag['class'] = "section"
        file_ID = "%s" % tocTitle.lower()
        file_ID = file_ID.replace(" ","")
        navPointTag['id'] = "%s-ID" % file_ID
        navPointTag['playOrder'] = self.playOrder
        self.playOrder += 1
        navLabelTag = Tag(soup, 'navLabel')
        textTag = Tag(soup, 'text')
        textTag.insert(0, NavigableString('%s' % tocTitle))
        navLabelTag.insert(0, textTag)
        nptc = 0
        navPointTag.insert(nptc, navLabelTag)
        nptc += 1
        contentTag = Tag(soup,"content")
        contentTag['src'] = "%s#section_start" % HTML_file
        navPointTag.insert(nptc, contentTag)
        nptc += 1

        # Create an NCX article entry for each date range
        current_titles_list = []
        master_date_range_list = []
        today = datetime.datetime.now()
        today_time = datetime.datetime(today.year, today.month, today.day)
        for (i,date) in enumerate(self.DATE_RANGE):
            if i:
                date_range = '%d to %d days ago' % (self.DATE_RANGE[i-1], self.DATE_RANGE[i])
            else:
                date_range = 'Last %d days' % (self.DATE_RANGE[i])
            date_range_limit = self.DATE_RANGE[i]
            for book in self.booksByDateRange:
                book_time = datetime.datetime(book['timestamp'].year, book['timestamp'].month, book['timestamp'].day)
                if (today_time-book_time).days <= date_range_limit:
                    #print "generateNCXByDateAdded: %s added %d days ago" % (book['title'], (today_time-book_time).days)
                    current_titles_list.append(book['title'])
                else:
                    break
            if current_titles_list:
                add_to_master_date_range_list(current_titles_list)
            current_titles_list = [book['title']]

        # Add *article* entries for each populated date range
        # master_date_range_list{}: [0]:titles list [1]:datestr
        for books_by_date_range in master_date_range_list:
            navPointByDateRangeTag = Tag(soup, 'navPoint')
            navPointByDateRangeTag['class'] = "article"
            navPointByDateRangeTag['id'] = "%s-ID" %  books_by_date_range[1].replace(' ','')
            navPointTag['playOrder'] = self.playOrder
            self.playOrder += 1
            navLabelTag = Tag(soup, 'navLabel')
            textTag = Tag(soup, 'text')
            textTag.insert(0, NavigableString(books_by_date_range[1]))
            navLabelTag.insert(0, textTag)
            navPointByDateRangeTag.insert(0,navLabelTag)
            contentTag = Tag(soup, 'content')
            contentTag['src'] = "%s#bda_%s" % (HTML_file,
                books_by_date_range[1].replace(' ',''))

            navPointByDateRangeTag.insert(1,contentTag)

            if self.generateForKindle:
                cmTag = Tag(soup, '%s' % 'calibre:meta')
                cmTag['name'] = "description"
                cmTag.insert(0, NavigableString(books_by_date_range[0]))
                navPointByDateRangeTag.insert(2, cmTag)

                cmTag = Tag(soup, '%s' % 'calibre:meta')
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
        current_date = self.booksByMonth[0]['timestamp']

        for book in self.booksByMonth:
            if book['timestamp'].month != current_date.month or \
                book['timestamp'].year != current_date.year:
                # Save the old lists
                add_to_master_month_list(current_titles_list)

                # Start the new list
                current_date = book['timestamp'].date()
                current_titles_list = [book['title']]
            else:
                current_titles_list.append(book['title'])

        # Add the last month list
        add_to_master_month_list(current_titles_list)

        # Add *article* entries for each populated month
        # master_months_list{}: [0]:titles list [1]:date
        for books_by_month in master_month_list:
            datestr = strftime(u'%B %Y', books_by_month[1].timetuple())
            navPointByMonthTag = Tag(soup, 'navPoint')
            navPointByMonthTag['class'] = "article"
            navPointByMonthTag['id'] = "bda_%s-%s-ID" % (books_by_month[1].year,books_by_month[1].month )
            navPointTag['playOrder'] = self.playOrder
            self.playOrder += 1
            navLabelTag = Tag(soup, 'navLabel')
            textTag = Tag(soup, 'text')
            textTag.insert(0, NavigableString(datestr))
            navLabelTag.insert(0, textTag)
            navPointByMonthTag.insert(0,navLabelTag)
            contentTag = Tag(soup, 'content')
            contentTag['src'] = "%s#bda_%s-%s" % (HTML_file,
                books_by_month[1].year,books_by_month[1].month)

            navPointByMonthTag.insert(1,contentTag)

            if self.generateForKindle:
                cmTag = Tag(soup, '%s' % 'calibre:meta')
                cmTag['name'] = "description"
                cmTag.insert(0, NavigableString(books_by_month[0]))
                navPointByMonthTag.insert(2, cmTag)

                cmTag = Tag(soup, '%s' % 'calibre:meta')
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
        self.ncxSoup = soup

    def generateNCXByDateRead(self, tocTitle):
        self.updateProgressFullStep("NCX 'Recently Read'")
        if not self.booksByDateRead:
            return

        def add_to_master_day_list(current_titles_list):
            book_count = len(current_titles_list)
            current_titles_list = " &bull; ".join(current_titles_list)
            current_titles_list = self.formatNCXText(current_titles_list, dest='description')
            master_day_list.append((current_titles_list, current_date, book_count))

        def add_to_master_date_range_list(current_titles_list):
            book_count = len(current_titles_list)
            current_titles_list = " &bull; ".join(current_titles_list)
            current_titles_list = self.formatNCXText(current_titles_list, dest='description')
            master_date_range_list.append((current_titles_list, date_range, book_count))

        soup = self.ncxSoup
        HTML_file = "content/ByDateRead.html"
        body = soup.find("navPoint")
        btc = len(body.contents)

        # --- Construct the 'Recently Read' *section* ---
        navPointTag = Tag(soup, 'navPoint')
        navPointTag['class'] = "section"
        file_ID = "%s" % tocTitle.lower()
        file_ID = file_ID.replace(" ","")
        navPointTag['id'] = "%s-ID" % file_ID
        navPointTag['playOrder'] = self.playOrder
        self.playOrder += 1
        navLabelTag = Tag(soup, 'navLabel')
        textTag = Tag(soup, 'text')
        textTag.insert(0, NavigableString('%s' % tocTitle))
        navLabelTag.insert(0, textTag)
        nptc = 0
        navPointTag.insert(nptc, navLabelTag)
        nptc += 1
        contentTag = Tag(soup,"content")
        contentTag['src'] = "%s#section_start" % HTML_file
        navPointTag.insert(nptc, contentTag)
        nptc += 1

        # Create an NCX article entry for each date range
        current_titles_list = []
        master_date_range_list = []
        today = datetime.datetime.now()
        today_time = datetime.datetime(today.year, today.month, today.day)
        for (i,date) in enumerate(self.DATE_RANGE):
            if i:
                date_range = '%d to %d days ago' % (self.DATE_RANGE[i-1], self.DATE_RANGE[i])
            else:
                date_range = 'Last %d days' % (self.DATE_RANGE[i])
            date_range_limit = self.DATE_RANGE[i]
            for book in self.booksByDateRead:
                bookmark_time = datetime.datetime.utcfromtimestamp(book['bookmark_timestamp'])
                if (today_time-bookmark_time).days <= date_range_limit:
                    #print "generateNCXByDateAdded: %s added %d days ago" % (book['title'], (today_time-book_time).days)
                    current_titles_list.append(book['title'])
                else:
                    break
            if current_titles_list:
                add_to_master_date_range_list(current_titles_list)
            current_titles_list = [book['title']]

        # Create an NCX article entry for each populated day
        # Loop over the booksByDate list, find start of each month,
        # add description_preview_count titles
        # master_month_list(list,date,count)
        current_titles_list = []
        master_day_list = []
        current_date = datetime.datetime.utcfromtimestamp(self.booksByDateRead[0]['bookmark_timestamp'])

        for book in self.booksByDateRead:
            bookmark_time = datetime.datetime.utcfromtimestamp(book['bookmark_timestamp'])
            if bookmark_time.day != current_date.day or \
                bookmark_time.month != current_date.month or \
                bookmark_time.year != current_date.year:
                # Save the old lists
                add_to_master_day_list(current_titles_list)

                # Start the new list
                current_date = datetime.datetime.utcfromtimestamp(book['bookmark_timestamp']).date()
                current_titles_list = [book['title']]
            else:
                current_titles_list.append(book['title'])

        # Add the last day list
        add_to_master_day_list(current_titles_list)

        # Add *article* entries for each populated day
        # master_day_list{}: [0]:titles list [1]:date
        for books_by_day in master_day_list:
            datestr = strftime(u'%A, %B %d', books_by_day[1].timetuple())
            navPointByDayTag = Tag(soup, 'navPoint')
            navPointByDayTag['class'] = "article"
            navPointByDayTag['id'] = "bdr_%s-%s-%sID" % (books_by_day[1].year,
                                                            books_by_day[1].month,
                                                            books_by_day[1].day )
            navPointTag['playOrder'] = self.playOrder
            self.playOrder += 1
            navLabelTag = Tag(soup, 'navLabel')
            textTag = Tag(soup, 'text')
            textTag.insert(0, NavigableString(datestr))
            navLabelTag.insert(0, textTag)
            navPointByDayTag.insert(0,navLabelTag)
            contentTag = Tag(soup, 'content')
            contentTag['src'] = "%s#bdr_%s-%s-%s" % (HTML_file,
                                                        books_by_day[1].year,
                                                        books_by_day[1].month,
                                                        books_by_day[1].day)

            navPointByDayTag.insert(1,contentTag)

            if self.generateForKindle:
                cmTag = Tag(soup, '%s' % 'calibre:meta')
                cmTag['name'] = "description"
                cmTag.insert(0, NavigableString(books_by_day[0]))
                navPointByDayTag.insert(2, cmTag)

                cmTag = Tag(soup, '%s' % 'calibre:meta')
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
        self.ncxSoup = soup

    def generateNCXByGenre(self, tocTitle):
        # Create an NCX section for 'By Genre'
        # Add each genre as an article
        # 'tag', 'file', 'authors'

        self.updateProgressFullStep("NCX 'Genres'")

        if not len(self.genres):
            self.opts.log.warn(" No genres found in tags.\n"
                                " No Genre section added to Catalog")
            return

        ncx_soup = self.ncxSoup
        body = ncx_soup.find("navPoint")
        btc = len(body.contents)

        # --- Construct the 'Books By Genre' *section* ---
        navPointTag = Tag(ncx_soup, 'navPoint')
        navPointTag['class'] = "section"
        file_ID = "%s" % tocTitle.lower()
        file_ID = file_ID.replace(" ","")
        navPointTag['id'] = "%s-ID" % file_ID
        navPointTag['playOrder'] = self.playOrder
        self.playOrder += 1
        navLabelTag = Tag(ncx_soup, 'navLabel')
        textTag = Tag(ncx_soup, 'text')
        # textTag.insert(0, NavigableString('%s (%d)' % (section_title, len(genre_list))))
        textTag.insert(0, NavigableString('%s' % tocTitle))
        navLabelTag.insert(0, textTag)
        nptc = 0
        navPointTag.insert(nptc, navLabelTag)
        nptc += 1
        contentTag = Tag(ncx_soup,"content")
        contentTag['src'] = "content/Genre_%s.html#section_start" % self.genres[0]['tag']
        navPointTag.insert(nptc, contentTag)
        nptc += 1

        for genre in self.genres:
            # Add an article for each genre
            navPointVolumeTag = Tag(ncx_soup, 'navPoint')
            navPointVolumeTag['class'] = "article"
            navPointVolumeTag['id'] = "genre-%s-ID" % genre['tag']
            navPointVolumeTag['playOrder'] = self.playOrder
            self.playOrder += 1
            navLabelTag = Tag(ncx_soup, "navLabel")
            textTag = Tag(ncx_soup, "text")

            # GwR *** Can this be optimized?
            normalized_tag = None
            for friendly_tag in self.genre_tags_dict:
                if self.genre_tags_dict[friendly_tag] == genre['tag']:
                    normalized_tag = self.genre_tags_dict[friendly_tag]
                    break
            textTag.insert(0, self.formatNCXText(NavigableString(friendly_tag), dest='description'))
            navLabelTag.insert(0,textTag)
            navPointVolumeTag.insert(0,navLabelTag)
            contentTag = Tag(ncx_soup, "content")
            contentTag['src'] = "content/Genre_%s.html#Genre_%s" % (normalized_tag, normalized_tag)
            navPointVolumeTag.insert(1, contentTag)

            if self.generateForKindle:
                # Build the author tag
                cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                cmTag['name'] = "author"
                # First - Last author

                if len(genre['titles_spanned']) > 1 :
                    author_range = "%s - %s" % (genre['titles_spanned'][0][0], genre['titles_spanned'][1][0])
                else :
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
                    cmTag.insert(0, NavigableString(self.formatNCXText(title_range, dest='description')))
                else:
                    # Form 2: title &bull; title &bull; title ...
                    titles = []
                    for title in genre['books']:
                        titles.append(title['title'])
                    titles = sorted(titles, key=lambda x:(self.generateSortTitle(x),self.generateSortTitle(x)))
                    titles_list = self.generateShortDescription(u" &bull; ".join(titles), dest="description")
                    cmTag.insert(0, NavigableString(self.formatNCXText(titles_list, dest='description')))

                navPointVolumeTag.insert(3, cmTag)

            # Add this volume to the section tag
            navPointTag.insert(nptc, navPointVolumeTag)
            nptc += 1

        # Add this section to the body
        body.insert(btc, navPointTag)
        btc += 1
        self.ncxSoup = ncx_soup

    def writeNCX(self):
        self.updateProgressFullStep("Saving NCX")

        outfile = open("%s/%s.ncx" % (self.catalogPath, self.basename), 'w')
        outfile.write(self.ncxSoup.prettify())


    # ======================== Helpers ========================
    def author_to_author_sort(self, author):
        tokens = author.split()
        tokens = tokens[-1:] + tokens[:-1]
        if len(tokens) > 1:
            tokens[0] += ','
        return ' '.join(tokens).capitalize()

    def booksByAuthorSorter_author_sort(self, book):
        '''
        Sort non-series books before series books
        '''
        if not book['series']:
            key = '%s ~%s' % (capitalize(book['author_sort']),
                                capitalize(book['title_sort']))
        else:
            index = book['series_index']
            integer = int(index)
            fraction = index-integer
            series_index = '%04d%s' % (integer, str('%0.4f' % fraction).lstrip('0'))
            key = '%s %s %s' % (capitalize(book['author_sort']),
                                    self.generateSortTitle(book['series']),
                                    series_index)
        return key

    def booksByAuthorSorter_author(self, book):
        '''
        Sort non-series books before series books
        '''
        if not book['series']:
            key = '%s %s' % (self.author_to_author_sort(book['author']),
                                capitalize(book['title_sort']))
        else:
            index = book['series_index']
            integer = int(index)
            fraction = index-integer
            series_index = '%04d%s' % (integer, str('%0.4f' % fraction).lstrip('0'))
            key = '%s ~%s %s' % (self.author_to_author_sort(book['author']),
                                    self.generateSortTitle(book['series']),
                                    series_index)
        return key

    def calculateThumbnailSize(self):
        ''' Calculate thumbnail dimensions based on device DPI.  Scale Kindle by 50% '''
        from calibre.customize.ui import output_profiles
        for x in output_profiles():
            if x.short_name == self.opts.output_profile:
                # aspect ratio: 3:4
                self.thumbWidth = x.dpi * float(self.opts.thumb_width)
                self.thumbHeight = self.thumbWidth * 1.33
                if 'kindle' in x.short_name and self.opts.fmt == 'mobi':
                    # Kindle DPI appears to be off by a factor of 2
                    self.thumbWidth = self.thumbWidth/2
                    self.thumbHeight = self.thumbHeight/2
                break
        if True and self.verbose:
            self.opts.log("     DPI = %d; thumbnail dimensions: %d x %d" % \
                            (x.dpi, self.thumbWidth, self.thumbHeight))

    def convertHTMLEntities(self, s):
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
            if htmlentitydefs.name2codepoint.has_key(name):
                    s = s.replace(hit, unichr(htmlentitydefs.name2codepoint[name]))
        s = s.replace(amp, "&")
        return s

    def createDirectoryStructure(self):
        catalogPath = self.catalogPath
        self.cleanUp()

        if not os.path.isdir(catalogPath):
            os.makedirs(catalogPath)

        # Create /content and /images
        content_path = catalogPath + "/content"
        if not os.path.isdir(content_path):
            os.makedirs(content_path)
        images_path = catalogPath + "/images"
        if not os.path.isdir(images_path):
            os.makedirs(images_path)

    def discoverPrefix(self, record):
        '''
        Evaluate conditions for including prefixes in various listings
        '''
        def log_prefix_rule_match_info(rule, record):
            self.opts.log.info("     %s %s by %s (Prefix rule '%s': %s:%s)" %
                               (rule['prefix'],record['title'],
                                record['authors'][0], rule['name'],
                                rule['field'],rule['pattern']))

        # Compare the record to each rule looking for a match
        for rule in self.prefixRules:
            # Literal comparison for Tags field
            if rule['field'].lower() == 'tags':
                if rule['pattern'].lower() in map(unicode.lower,record['tags']):
                    if self.opts.verbose:
                        log_prefix_rule_match_info(rule, record)
                    return rule['prefix']

            # Regex match for custom field
            elif rule['field'].startswith('#'):
                field_contents = self.__db.get_field(record['id'],
                                    rule['field'],
                                    index_is_id=True)
                if field_contents == '':
                    field_contents = None

                if field_contents is not None:
                    try:
                        if re.search(rule['pattern'], unicode(field_contents),
                                re.IGNORECASE) is not None:
                            if self.opts.verbose:
                                log_prefix_rule_match_info(rule, record)
                            return rule['prefix']
                    except:
                        # Compiling of pat failed, ignore it
                        if self.opts.verbose:
                            self.opts.log.error("pattern failed to compile: %s" % rule['pattern'])
                        pass
                elif field_contents is None and rule['pattern'] == 'None':
                    if self.opts.verbose:
                        log_prefix_rule_match_info(rule, record)
                    return rule['prefix']

        return None

    def establish_equivalencies(self, item_list, key=None):
        # Filter for leading letter equivalencies

        # Hack to force the cataloged leading letter to be
        # an unadorned character if the accented version sorts before the unaccented
        exceptions = {
                        u'Ä':u'A',
                        u'Ö':u'O',
                        u'Ü':u'U'
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
            if last_ordnum != ordnum:
                last_c = icu_upper(c[0:ordlen])
                if last_c in exceptions.keys():
                    last_c = exceptions[unicode(last_c)]
                last_ordnum = ordnum
            cl_list[idx] = last_c

        if False:
            if key:
                for idx, item in enumerate(item_list):
                    print("%s %s" % (cl_list[idx],item[sort_field]))
            else:
                    print("%s %s" % (cl_list[0], item))

        return cl_list

    def filterDbTags(self, tags):
        # Remove the special marker tags from the database's tag list,
        # return sorted list of normalized genre tags

        def format_tag_list(tags, indent=5, line_break=70, header='Tag list'):
            def next_tag(sorted_tags):
                for (i, tag) in enumerate(sorted_tags):
                    if i < len(tags) - 1:
                        yield tag + ", "
                    else:
                        yield tag

            ans = '%s%d %s:\n' %  (' ' * indent, len(tags), header)
            ans += ' ' * (indent + 1)
            out_str = ''
            sorted_tags = sorted(tags, key=sort_key)
            for tag in next_tag(sorted_tags):
                out_str += tag
                if len(out_str) >= line_break:
                    ans += out_str + '\n'
                    out_str = ' ' * (indent + 1)
            return ans + out_str

        normalized_tags = []
        friendly_tags = []
        excluded_tags = []
        for tag in tags:
            if tag in self.markerTags:
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

            normalized_tags.append(re.sub('\W','',ascii_text(tag)).lower())
            friendly_tags.append(tag)

        genre_tags_dict = dict(zip(friendly_tags,normalized_tags))

        # Test for multiple genres resolving to same normalized form
        normalized_set = set(normalized_tags)
        for normalized in normalized_set:
            if normalized_tags.count(normalized) > 1:
                self.opts.log.warn("      Warning: multiple tags resolving to genre '%s':" % normalized)
                for key in genre_tags_dict:
                    if genre_tags_dict[key] == normalized:
                        self.opts.log.warn("       %s" % key)
        if self.verbose:
            self.opts.log.info('%s' % format_tag_list(genre_tags_dict, header="enabled genre tags in database"))
            self.opts.log.info('%s' % format_tag_list(excluded_tags, header="excluded genre tags"))

        return genre_tags_dict

    def formatNCXText(self, description, dest=None):
        # Kindle TOC descriptions won't render certain characters
        # Fix up
        massaged = unicode(BeautifulStoneSoup(description, convertEntities=BeautifulStoneSoup.HTML_ENTITIES))

        # Replace '&' with '&#38;'
        massaged = re.sub("&","&#38;", massaged)

        if massaged.strip() and dest:
            #print traceback.print_stack(limit=3)
            return self.generateShortDescription(massaged.strip(), dest=dest)
        else:
            return None

    def formatPrefix(self,prefix_char,soup):
        # Generate the HTML for the prefix portion of the listing
        # Kindle Previewer doesn't properly handle style=color:white
        # MOBI does a better job allocating blank space with <code>
        if self.opts.fmt == 'mobi':
            codeTag = Tag(soup, "code")
            if prefix_char is None:
                codeTag.insert(0,NavigableString('&nbsp;'))
            else:
                codeTag.insert(0,NavigableString(prefix_char))
            return codeTag
        else:
            spanTag = Tag(soup, "span")
            spanTag['class'] = "prefix"

            # color:white was the original technique used to align columns.
            # The new technique is to float the prefix left with CSS.
            if prefix_char is None:
                if True:
                    prefix_char = "&nbsp;"
                else:
                    del spanTag['class']
                    spanTag['style'] = "color:white"
                    prefix_char = self.defaultPrefix
            spanTag.insert(0,NavigableString(prefix_char))
            return spanTag

    def generateAuthorAnchor(self, author):
        # Generate a legal XHTML id/href string
        return re.sub("\W","", ascii_text(author))

    def generateFormatArgs(self, book):
        series_index = str(book['series_index'])
        if series_index.endswith('.0'):
            series_index = series_index[:-2]
        args = dict(
                title = book['title'],
                series = book['series'],
                series_index = series_index,
                rating = self.generateRatingString(book),
                rating_parens = '(%s)' % self.generateRatingString(book) if 'rating' in book else '',
                pubyear = book['date'].split()[1] if book['date'] else '',
                pubyear_parens = "(%s)" % book['date'].split()[1] if book['date'] else '')
        return args

    def generateHTMLByGenre(self, genre, section_head, books, outfile):
        # Write an HTML file of this genre's book list
        # Return a list with [(first_author, first_book), (last_author, last_book)]

        soup = self.generateHTMLGenreHeader(genre)
        body = soup.find('body')

        btc = 0
        divTag = Tag(soup, 'div')
        dtc = 0


        # Insert section tag if this is the section start - first article only
        if section_head:
            aTag = Tag(soup,'a')
            aTag['id'] = 'section_start'
            divTag.insert(dtc, aTag)
            dtc += 1
            #body.insert(btc, aTag)
            #btc += 1

        # Create an anchor from the tag
        aTag = Tag(soup, 'a')
        aTag['id'] = "Genre_%s" % genre
        divTag.insert(dtc, aTag)
        body.insert(btc,divTag)
        btc += 1

        titleTag = body.find(attrs={'class':'title'})
        titleTag.insert(0,NavigableString('%s' % escape(self.getFriendlyGenreTag(genre))))

        # Insert the books by author list
        divTag = body.find(attrs={'class':'authors'})
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
                    aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generateAuthorAnchor(book['author']))
                aTag.insert(0, book['author'])
                pAuthorTag.insert(0,aTag)
                divTag.insert(dtc,pAuthorTag)
                dtc += 1

            # Check for series
            if book['series'] and book['series'] != current_series:
                # Start a new series
                current_series = book['series']
                pSeriesTag = Tag(soup,'p')
                pSeriesTag['class'] = "series"
                if self.opts.fmt == 'mobi':
                    pSeriesTag['class'] = "series_mobi"
                if self.opts.generate_series:
                    aTag = Tag(soup,'a')
                    aTag['href'] = "%s.html#%s" % ('BySeries', self.generateSeriesAnchor(book['series']))
                    aTag.insert(0, book['series'])
                    pSeriesTag.insert(0, aTag)
                else:
                    pSeriesTag.insert(0,NavigableString('%s' % book['series']))
                divTag.insert(dtc,pSeriesTag)
                dtc += 1

            if current_series and not book['series']:
                current_series = None

            # Add books
            pBookTag = Tag(soup, "p")
            pBookTag['class'] = "line_item"
            ptc = 0

            pBookTag.insert(ptc, self.formatPrefix(book['prefix'],soup))
            ptc += 1

            spanTag = Tag(soup, "span")
            spanTag['class'] = "entry"
            stc = 0

            # Add the book title
            aTag = Tag(soup, "a")
            if self.opts.generate_descriptions:
                aTag['href'] = "book_%d.html" % (int(float(book['id'])))

            # Generate the title from the template
            args = self.generateFormatArgs(book)
            if current_series:
                #aTag.insert(0,escape(book['title'][len(book['series'])+1:]))
                formatted_title = self.by_genres_series_title_template.format(**args).rstrip()
            else:
                #aTag.insert(0,escape(book['title']))
                formatted_title = self.by_genres_normal_title_template.format(**args).rstrip()
                non_series_books += 1
            aTag.insert(0,NavigableString(escape(formatted_title)))

            spanTag.insert(stc, aTag)
            stc += 1

            pBookTag.insert(ptc, spanTag)
            ptc += 1

            divTag.insert(dtc, pBookTag)
            dtc += 1

        # Write the generated file to contentdir
        outfile = open(outfile, 'w')
        outfile.write(soup.prettify())
        outfile.close()

        if len(books) > 1:
            titles_spanned = [(books[0]['author'],books[0]['title']), (books[-1]['author'],books[-1]['title'])]
        else:
            titles_spanned = [(books[0]['author'],books[0]['title'])]

        return titles_spanned

    def generateHTMLDescriptionHeader(self, book):
        '''
        Generate description header from template
        '''
        from calibre.ebooks.oeb.base import XHTML_NS

        def generate_html():
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
            author_prefix = book['prefix'] + ' ' +  _("by ")
        elif self.opts.connected_kindle and book['id'] in self.bookmarked_books:
            author_prefix = self.READING_SYMBOL + ' ' + _("by ")
        else:
            author_prefix = _("by ")

        # Genres
        genres = ''
        if 'tags' in book:
            _soup = BeautifulSoup('')
            genresTag = Tag(_soup,'p')
            gtc = 0
            for (i, tag) in enumerate(sorted(book.get('tags', []))):
                aTag = Tag(_soup,'a')
                if self.opts.generate_genres:
                    aTag['href'] = "Genre_%s.html" % re.sub("\W","",ascii_text(tag).lower())
                aTag.insert(0,escape(NavigableString(tag)))
                genresTag.insert(gtc, aTag)
                gtc += 1
                if i < len(book['tags'])-1:
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
        _soup = BeautifulSoup('<html>',selfClosingTags=['img'])
        thumb = Tag(_soup,"img")
        if 'cover' in book and book['cover']:
            thumb['src']  = "../images/thumbnail_%d.jpg" % int(book['id'])
        else:
            thumb['src']  = "../images/thumbnail_default.jpg"
        thumb['alt'] = "cover thumbnail"

        # Publisher
        publisher = ' '
        if 'publisher' in book:
            publisher = book['publisher']

        # Rating
        stars = int(book['rating']) / 2
        rating = ''
        if stars:
            star_string = self.FULL_RATING_SYMBOL * stars
            empty_stars = self.EMPTY_RATING_SYMBOL * (5 - stars)
            rating = '%s%s <br/>' % (star_string,empty_stars)

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
        soup = generate_html()


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
        aTag = body.find('a', attrs={'class':'series_id'})
        if aTag:
            if book['series']:
                if self.opts.generate_series:
                    aTag['href'] = "%s.html#%s" % ('BySeries',self.generateSeriesAnchor(book['series']))
            else:
                aTag.extract()

        # Insert the author link
        aTag = body.find('a', attrs={'class':'author'})
        if self.opts.generate_authors and aTag:
            aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor",
                                        self.generateAuthorAnchor(book['author']))

        if publisher == ' ':
            publisherTag = body.find('td', attrs={'class':'publisher'})
            if publisherTag:
                publisherTag.contents[0].replaceWith('&nbsp;')

        if not genres:
            genresTag = body.find('p',attrs={'class':'genres'})
            if genresTag:
                genresTag.extract()

        if not formats:
            formatsTag = body.find('p',attrs={'class':'formats'})
            if formatsTag:
                formatsTag.extract()

        if note_content == '':
            tdTag = body.find('td', attrs={'class':'notes'})
            if tdTag:
                tdTag.contents[0].replaceWith('&nbsp;')

        emptyTags = body.findAll('td', attrs={'class':'empty'})
        for mt in emptyTags:
            newEmptyTag = Tag(BeautifulSoup(),'td')
            newEmptyTag.insert(0,NavigableString('&nbsp;'))
            mt.replaceWith(newEmptyTag)

        if False:
            print soup.prettify()
        return soup

    def generateHTMLEmptyHeader(self, title):
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
        titleTag.insert(0,NavigableString(title))
        return soup

    def generateHTMLGenreHeader(self, title):
        header = '''
            <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
            <html xmlns="http://www.w3.org/1999/xhtml" xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata">
            <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
                <link rel="stylesheet" type="text/css" href="stylesheet.css" media="screen" />
            <title></title>
            </head>
            <body>
                <p class="title"></p>
                <div class="authors"></div>
            </body>
            </html>
            '''
        # Insert the supplied title
        soup = BeautifulSoup(header)
        titleTag = soup.find('title')
        titleTag.insert(0,escape(NavigableString(title)))
        return soup

    def generateMastheadImage(self, out_path):
        from calibre.ebooks.conversion.config import load_defaults
        from calibre.utils.fonts import fontconfig
        font_path = default_font = P('fonts/liberation/LiberationSerif-Bold.ttf')
        recs = load_defaults('mobi_output')
        masthead_font_family = recs.get('masthead_font', 'Default')

        if masthead_font_family != 'Default':
            masthead_font = fontconfig.files_for_family(masthead_font_family)
            # Assume 'normal' always in dict, else use default
            # {'normal': (path_to_font, friendly name)}
            if 'normal' in masthead_font:
                font_path = masthead_font['normal'][0]

        if not font_path or not os.access(font_path, os.R_OK):
            font_path = default_font

        MI_WIDTH = 600
        MI_HEIGHT = 60

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
        text = self.title.encode('utf-8')
        width, height = draw.textsize(text, font=font)
        left = max(int((MI_WIDTH - width)/2.), 0)
        top = max(int((MI_HEIGHT - height)/2.), 0)
        draw.text((left, top), text, fill=(0,0,0), font=font)
        img.save(open(out_path, 'wb'), 'GIF')

    def generateRatingString(self, book):
        rating = ''
        try:
            if 'rating' in book:
                stars = int(book['rating']) / 2
                if stars:
                    star_string = self.FULL_RATING_SYMBOL * stars
                    empty_stars = self.EMPTY_RATING_SYMBOL * (5 - stars)
                    rating = '%s%s' % (star_string,empty_stars)
        except:
            # Rating could be None
            pass
        return rating

    def generateSeriesAnchor(self, series):
        # Generate a legal XHTML id/href string
        if self.letter_or_symbol(series) == self.SYMBOLS:
            return "symbol_%s_series" % re.sub('\W','',series).lower()
        else:
            return "%s_series" % re.sub('\W','',ascii_text(series)).lower()

    def generateShortDescription(self, description, dest=None):
        # Truncate the description, on word boundaries if necessary
        # Possible destinations:
        #  description  NCX summary
        #  title        NCX title
        #  author       NCX author

        def shortDescription(description, limit):
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
            if self.authorClip and len(description) < self.authorClip:
                return description
            else:
                return shortDescription(description, self.authorClip)
        elif dest == 'description':
            if self.descriptionClip and len(description) < self.descriptionClip:
                return description
            else:
                return shortDescription(description, self.descriptionClip)
        else:
            print " returning description with unspecified destination '%s'" % description
            raise RuntimeError

    def generateSortTitle(self, title):
        '''
        Generate a string suitable for sorting from the title
        Ignore leading stop words
        Optionally convert leading numbers to strings
        '''
        from calibre.ebooks.metadata import title_sort
        from calibre.library.catalogs.utils import NumberToText

        # Strip stop words
        title_words = title_sort(title).split()
        translated = []

        for (i,word) in enumerate(title_words):
            # Leading numbers optionally translated to text equivalent
            # Capitalize leading sort word
            if i==0:
                # *** Keep this code in case we need to restore numbers_as_text ***
                if False:
                #if self.opts.numbers_as_text and re.match('[0-9]+',word[0]):
                    translated.append(NumberToText(word).text.capitalize())
                else:
                    if re.match('[0-9]+',word[0]):
                        word =  word.replace(',','')
                        suffix = re.search('[\D]', word)
                        if suffix:
                            word = '%10.0f%s' % (float(word[:suffix.start()]),word[suffix.start():])
                        else:
                            word = '%10.0f' % (float(word))

                    # If leading char > 'A', insert symbol as leading forcing lower sort
                    # '/' sorts below numbers, g
                    if self.letter_or_symbol(word[0]) != word[0]:
                        if word[0] > 'A' or (ord('9') < ord(word[0]) < ord('A')) :
                            translated.append('/')
                    translated.append(capitalize(word))

            else:
                if re.search('[0-9]+',word[0]):
                    word =  word.replace(',','')
                    suffix = re.search('[\D]', word)
                    if suffix:
                        word = '%10.0f%s' % (float(word[:suffix.start()]),word[suffix.start():])
                    else:
                        word = '%10.0f' % (float(word))
                translated.append(word)
        return ' '.join(translated)

    def generateThumbnail(self, title, image_dir, thumb_file):
        '''
        Thumbs are cached with the full cover's crc.  If the crc doesn't
        match, the cover has been changed since the thumb was cached and needs
        to be replaced.
        '''

        def open_archive(mode='r'):
            try:
                return ZipFile(self.__archive_path, mode=mode, allowZip64=True)
            except:
                # Happens on windows if the file is opened by another
                # process
                pass

        # Generate crc for current cover
        #self.opts.log.info(" generateThumbnail():")
        with open(title['cover'], 'rb') as f:
            data = f.read()
        cover_crc = hex(zlib.crc32(data))

        # Test cache for uuid
        zf = open_archive()
        if zf is not None:
            with zf:
                try:
                    zf.getinfo(title['uuid']+cover_crc)
                except:
                    pass
                else:
                    # uuid found in cache with matching crc
                    thumb_data = zf.read(title['uuid']+cover_crc)
                    with open(os.path.join(image_dir, thumb_file), 'wb') as f:
                        f.write(thumb_data)
                    return


        # Save thumb for catalog
        thumb_data = thumbnail(data,
                width=self.thumbWidth, height=self.thumbHeight)[-1]
        with open(os.path.join(image_dir, thumb_file), 'wb') as f:
            f.write(thumb_data)

        # Save thumb to archive
        if zf is not None: # Ensure that the read succeeded
            # If we failed to open the zip file for reading,
            # we dont know if it contained the thumb or not
            zf = open_archive('a')
            if zf is not None:
                with zf:
                    zf.writestr(title['uuid']+cover_crc, thumb_data)

    def generateUnicodeName(self, c):
        '''
        Generate an anchor name string
        '''
        fullname = unicodedata.name(unicode(c))
        terms = fullname.split()
        return "_".join(terms)

    def getFriendlyGenreTag(self, genre):
        # Find the first instance of friendly_tag matching genre
        for friendly_tag in self.genre_tags_dict:
            if self.genre_tags_dict[friendly_tag] == genre:
                return friendly_tag

    def getMarkerTags(self):
        '''
        Return a list of special marker tags to be excluded from genre list
        exclusion_rules = ('name','Tags|#column','[]|pattern')
        '''
        markerTags = []
        for rule in self.opts.exclusion_rules:
            if rule[1].lower() == 'tags':
                markerTags.extend(rule[2].split(','))
        return markerTags

    def letter_or_symbol(self,char):
        if not re.search('[a-zA-Z]', ascii_text(char)):
            return self.SYMBOLS
        else:
            return char

    def markdownComments(self, comments):
        '''
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

        '''
        # Hackish - ignoring sentences ending or beginning in numbers to avoid
        # confusion with decimal points.

        # Explode lost CRs to \n\n
        for lost_cr in re.finditer('([a-z])([\.\?!])([A-Z])',comments):
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
                pTag = Tag(soup,'p')
                pTag.insert(0,p)
                soup.insert(tsc,pTag)
                tsc += 1
            comments = soup.renderContents(None)

        # Convert solo returns to <br />
        comments = re.sub('[\r\n]','<br />', comments)

        # Convert two hypens to emdash
        comments = re.sub('--','&mdash;',comments)
        soup = BeautifulSoup(comments)
        result = BeautifulSoup()
        rtc = 0
        open_pTag = False

        all_tokens = list(soup.contents)
        for token in all_tokens:
            if type(token) is NavigableString:
                if not open_pTag:
                    pTag = Tag(result,'p')
                    open_pTag = True
                    ptc = 0
                pTag.insert(ptc,prepare_string_for_xml(token))
                ptc += 1

            elif token.name in ['br','b','i','em']:
                if not open_pTag:
                    pTag = Tag(result,'p')
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
            result.insert(rtc,elem)
            rtc += 1

        return result.renderContents(encoding=None)

    def mergeComments(self, record):
        '''
        merge ['description'] with custom field contents to be displayed in Descriptions
        '''
        merged = ''
        if record['description']:
            addendum = self.__db.get_field(record['id'],
                                        self.__merge_comments['field'],
                                        index_is_id=True)
            if addendum is None:
                addendum = ''
            include_hr = eval(self.__merge_comments['hr'])
            if self.__merge_comments['position'] == 'before':
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
            # Return the custom field contents
            merged = self.__db.get_field(record['id'],
                                        self.__merge_comments['field'],
                                        index_is_id=True)

        return merged

    def processPrefixRules(self):
        if self.opts.prefix_rules:
            # Put the prefix rules into an ordered list of dicts
            try:
                for rule in self.opts.prefix_rules:
                    prefix_rule = {}
                    prefix_rule['name'] = rule[0]
                    prefix_rule['field'] = rule[1]
                    prefix_rule['pattern'] = rule[2]
                    prefix_rule['prefix'] = rule[3]
                    self.prefixRules.append(prefix_rule)
            except:
                self.opts.log.error("malformed self.opts.prefix_rules: %s" % repr(self.opts.prefix_rules))
                raise
            # Use the highest order prefix symbol as default
            self.defaultPrefix = self.opts.prefix_rules[0][3]

    def processExclusions(self, data_set):
        '''
        Remove excluded entries
        '''
        filtered_data_set = []
        exclusion_pairs = []
        exclusion_set = []
        for rule in self.opts.exclusion_rules:
            if rule[1].startswith('#') and rule[2] != '':
                field = rule[1]
                pat = rule[2]
                exclusion_pairs.append((field,pat))
            else:
                continue

        if exclusion_pairs:
            for record in data_set:
                for exclusion_pair in exclusion_pairs:
                    field,pat = exclusion_pair
                    field_contents = self.__db.get_field(record['id'],
                                                field,
                                                index_is_id=True)
                    if field_contents:
                        if re.search(pat, unicode(field_contents),
                                re.IGNORECASE) is not None:
                            if self.opts.verbose:
                                field_md = self.db.metadata_for_field(field)
                                self.opts.log.info("     - %s (Exclusion rule '%s': %s:%s)" %
                                                   (record['title'], field_md['name'], field,pat))
                            exclusion_set.append(record)
                            if record in filtered_data_set:
                                filtered_data_set.remove(record)
                            break
                    else:
                        if (record not in filtered_data_set and
                            record not in exclusion_set):
                            filtered_data_set.append(record)
            return filtered_data_set
        else:
            return data_set

    def processSpecialTags(self, tags, this_title, opts):

        tag_list = []

        try:
            for tag in tags:
                tag = self.convertHTMLEntities(tag)
                if re.search(opts.exclude_genre, tag):
                    continue
                else:
                    tag_list.append(tag)
        except:
            self.opts.log.error("\tprocessSpecialTags(): malformed --exclude-genre regex pattern: %s" % opts.exclude_genre)
            return tags

        return tag_list

    def updateProgressFullStep(self, description):
        self.currentStep += 1
        self.progressString = description
        self.progressInt = float((self.currentStep-1)/self.totalSteps)
        self.reporter(self.progressInt, self.progressString)
        if self.opts.cli_environment:
            self.opts.log(u"%3.0f%% %s" % (self.progressInt*100, self.progressString))

    def updateProgressMicroStep(self, description, micro_step_pct):
        step_range = 100/self.totalSteps
        self.progressString = description
        coarse_progress = float((self.currentStep-1)/self.totalSteps)
        fine_progress = float((micro_step_pct*step_range)/100)
        self.progressInt = coarse_progress + fine_progress
        self.reporter(self.progressInt, self.progressString)

