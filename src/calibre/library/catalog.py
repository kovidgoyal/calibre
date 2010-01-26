import os, re, shutil, htmlentitydefs

from collections import namedtuple
from xml.sax.saxutils import escape

from calibre import filesystem_encoding, prints
from calibre.customize import CatalogPlugin
from calibre.customize.conversion import OptionRecommendation, DummyReporter
from calibre.ebooks.BeautifulSoup import BeautifulSoup, BeautifulStoneSoup, Tag, NavigableString
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.logging import Log

FIELDS = ['all', 'author_sort', 'authors', 'comments',
          'cover', 'formats', 'id', 'isbn', 'pubdate', 'publisher', 'rating',
          'series_index', 'series', 'size', 'tags', 'timestamp', 'title',
          'uuid']

class CSV_XML(CatalogPlugin):
    'CSV/XML catalog generator'

    Option = namedtuple('Option', 'option, default, dest, help')

    name = 'Catalog_CSV_XML'
    description = 'CSV/XML catalog generator'
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Greg Riker'
    version = (1, 0, 0)
    file_types = set(['csv','xml'])

    cli_options = [
            Option('--fields',
                default = 'all',
                dest = 'fields',
                help = _('The fields to output when cataloging books in the '
                    'database.  Should be a comma-separated list of fields.\n'
                    'Available fields: %s.\n'
                    "Default: '%%default'\n"
                    "Applies to: CSV, XML output formats")%', '.join(FIELDS)),

            Option('--sort-by',
                default = 'id',
                dest = 'sort_by',
                help = _('Output field to sort on.\n'
                'Available fields: author_sort, id, rating, size, timestamp, title.\n'
                "Default: '%default'\n"
                "Applies to: CSV, XML output formats"))]

    def run(self, path_to_output, opts, db, notification=DummyReporter()):
        log = Log()
        self.fmt = path_to_output.rpartition('.')[2]
        self.notification = notification

        if False and opts.verbose:
            log("%s:run" % self.name)
            log(" path_to_output: %s" % path_to_output)
            log(" Output format: %s" % self.fmt)

            # Display opts
            opts_dict = vars(opts)
            keys = opts_dict.keys()
            keys.sort()
            log(" opts:")
            for key in keys:
                log("  %s: %s" % (key, opts_dict[key]))

        # If a list of ids are provided, don't use search_text
        if opts.ids:
            opts.search_text = None

        data = self.search_sort_db(db, opts)

        if not len(data):
            log.error("\nNo matching database entries for search criteria '%s'" % opts.search_text)
            raise SystemExit(1)

        # Get the requested output fields as a list
        fields = self.get_output_fields(opts)

        if self.fmt == 'csv':
            outfile = open(path_to_output, 'w')

            # Output the field headers
            outfile.write(u'%s\n' % u','.join(fields))

            # Output the entry fields
            for entry in data:
                outstr = ''
                for (x, field) in enumerate(fields):
                    item = entry[field]
                    if field in ['authors','tags','formats']:
                        item = ', '.join(item)
                    if x < len(fields) - 1:
                        if item is not None:
                            outstr += u'"%s",' % unicode(item).replace('"','""')
                        else:
                            outstr += '"",'
                    else:
                        if item is not None:
                            outstr += u'"%s"\n' % unicode(item).replace('"','""')
                        else:
                            outstr += '""\n'
                outfile.write(outstr.encode('utf-8'))
            outfile.close()

        elif self.fmt == 'xml':
            from lxml import etree

            from calibre.utils.genshi.template import MarkupTemplate

            PY_NAMESPACE = "http://genshi.edgewall.org/"
            PY = "{%s}" % PY_NAMESPACE
            NSMAP = {'py' : PY_NAMESPACE}
            root = etree.Element('calibredb', nsmap=NSMAP)
            py_for = etree.SubElement(root, PY + 'for', each="record in data")
            record = etree.SubElement(py_for, 'record')

            if 'id' in fields:
                record_child = etree.SubElement(record, 'id')
                record_child.set(PY + "if", "record['id']")
                record_child.text = "${record['id']}"

            if 'uuid' in fields:
                record_child = etree.SubElement(record, 'uuid')
                record_child.set(PY + "if", "record['uuid']")
                record_child.text = "${record['uuid']}"

            if 'title' in fields:
                record_child = etree.SubElement(record, 'title')
                record_child.set(PY + "if", "record['title']")
                record_child.text = "${record['title']}"

            if 'authors' in fields:
                record_child = etree.SubElement(record, 'authors', sort="${record['author_sort']}")
                record_subchild = etree.SubElement(record_child, PY + 'for', each="author in record['authors']")
                record_subsubchild = etree.SubElement(record_subchild, 'author')
                record_subsubchild.text = '$author'

            if 'publisher' in fields:
                record_child = etree.SubElement(record, 'publisher')
                record_child.set(PY + "if", "record['publisher']")
                record_child.text = "${record['publisher']}"

            if 'rating' in fields:
                record_child = etree.SubElement(record, 'rating')
                record_child.set(PY + "if", "record['rating']")
                record_child.text = "${record['rating']}"

            if 'date' in fields:
                record_child = etree.SubElement(record, 'date')
                record_child.set(PY + "if", "record['date']")
                record_child.text = "${record['date']}"

            if 'pubdate' in fields:
                record_child = etree.SubElement(record, 'pubdate')
                record_child.set(PY + "if", "record['pubdate']")
                record_child.text = "${record['pubdate']}"

            if 'size' in fields:
                record_child = etree.SubElement(record, 'size')
                record_child.set(PY + "if", "record['size']")
                record_child.text = "${record['size']}"

            if 'tags' in fields:
                # <tags py:if="record['tags']">
                #  <py:for each="tag in record['tags']">
                #   <tag>$tag</tag>
                #  </py:for>
                # </tags>
                record_child = etree.SubElement(record, 'tags')
                record_child.set(PY + "if", "record['tags']")
                record_subchild = etree.SubElement(record_child, PY + 'for', each="tag in record['tags']")
                record_subsubchild = etree.SubElement(record_subchild, 'tag')
                record_subsubchild.text = '$tag'

            if 'comments' in fields:
                record_child = etree.SubElement(record, 'comments')
                record_child.set(PY + "if", "record['comments']")
                record_child.text = "${record['comments']}"

            if 'series' in fields:
                # <series py:if="record['series']" index="${record['series_index']}">
                #  ${record['series']}
                # </series>
                record_child = etree.SubElement(record, 'series')
                record_child.set(PY + "if", "record['series']")
                record_child.set('index', "${record['series_index']}")
                record_child.text = "${record['series']}"

            if 'isbn' in fields:
                record_child = etree.SubElement(record, 'isbn')
                record_child.set(PY + "if", "record['isbn']")
                record_child.text = "${record['isbn']}"

            if 'cover' in fields:
                # <cover py:if="record['cover']">
                #  ${record['cover'].replace(os.sep, '/')}
                # </cover>
                record_child = etree.SubElement(record, 'cover')
                record_child.set(PY + "if", "record['cover']")
                record_child.text = "${record['cover']}"

            if 'formats' in fields:
                # <formats py:if="record['formats']">
                #  <py:for each="path in record['formats']">
                #    <format>${path.replace(os.sep, '/')}</format>
                #  </py:for>
                # </formats>
                record_child = etree.SubElement(record, 'formats')
                record_child.set(PY + "if", "record['formats']")
                record_subchild = etree.SubElement(record_child, PY + 'for', each="path in record['formats']")
                record_subsubchild = etree.SubElement(record_subchild, 'format')
                record_subsubchild.text = "${path.replace(os.sep, '/')}"

            outfile = open(path_to_output, 'w')
            template = MarkupTemplate(etree.tostring(root, xml_declaration=True,
                                      encoding="UTF-8", pretty_print=True))
            outfile.write(template.generate(data=data, os=os).render('xml'))
            outfile.close()

        return None

class EPUB_MOBI(CatalogPlugin):
    'ePub catalog generator'

    Option = namedtuple('Option', 'option, default, dest, help')

    name = 'Catalog_EPUB_MOBI'
    description = 'EPUB/MOBI catalog generator'
    supported_platforms = ['windows', 'osx', 'linux']
    minimum_calibre_version = (0, 6, 34)
    author = 'Greg Riker'
    version = (0, 0, 1)
    file_types = set(['epub','mobi'])

    cli_options = [Option('--catalog-title',
                          default = 'My Books',
                          dest = 'catalog_title',
                          help = _('Title of generated catalog used as title in metadata.\n'
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--debug-pipeline',
                           default=None,
                           dest='debug_pipeline',
                           help=_("Save the output from different stages of the conversion "
                           "pipeline to the specified "
                           "directory. Useful if you are unsure at which stage "
                           "of the conversion process a bug is occurring.\n"
                           "Default: '%default'None\n"
                           "Applies to: ePub, MOBI output formats")),
                   Option('--exclude-genre',
                          default='\[[\w ]*\]',
                          dest='exclude_genre',
                          help=_("Regex describing tags to exclude as genres.\n" "Default: '%default' excludes bracketed tags, e.g. '[<tag>]'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--exclude-tags',
                          default=('~,'+_('Catalog')),
                          dest='exclude_tags',
                          help=_("Comma-separated list of tag words indicating book should be excluded from output.  Case-insensitive.\n"
                          "--exclude-tags=skip will match 'skip this book' and 'Skip will like this'.\n"
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--read-tag',
                          default='+',
                          dest='read_tag',
                          help=_("Tag indicating book has been read.\n" "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--note-tag',
                          default='*',
                          dest='note_tag',
                          help=_("Tag prefix for user notes, e.g. '*Jeff might enjoy reading this'.\n"
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--output-profile',
                          default=None,
                          dest='output_profile',
                          help=_("Specifies the output profile.  In some cases, an output profile is required to optimize the catalog for the device.  For example, 'kindle' or 'kindle_dx' creates a structured Table of Contents with Sections and Articles.\n"
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats"))
                          ]

    class NumberToText(object):
        '''
        Converts numbers to text
        4.56    => four point fifty-six
        456     => four hundred fifty-six
        4:56    => four fifty-six
        '''

        lessThanTwenty = ["<zero>","one","two","three","four","five","six","seven","eight","nine",
                          "ten","eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen",
                          "eighteen","nineteen"]
        tens = ["<zero>","<tens>","twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"]
        hundreds = ["<zero>","one","two","three","four","five","six","seven","eight","nine"]

        def __init__(self, number):
            self.number = number
            self.text = ''
            self.numberTranslate()

        def stringFromInt(self, intToTranslate):
            # Convert intToTranslate to string
            # intToTranslate is a three-digit number

            tensComponentString = ""

            hundredsComponent = intToTranslate - (intToTranslate % 100)
            tensComponent = intToTranslate % 100

            # Build the hundreds component
            if hundredsComponent:
                hundredsComponentString = "%s hundred" % self.hundreds[hundredsComponent/100]
            else:
                hundredsComponentString = ""

            # Build the tens component
            if tensComponent < 20:
                if tensComponent > 0:
                    tensComponentString = self.lessThanTwenty[tensComponent]
            else:
                tensPart = ""
                onesPart = ""

                # Get the tens part
                tensPart = self.tens[tensComponent / 10]
                onesPart = self.lessThanTwenty[tensComponent % 10]

                if intToTranslate % 10:
                    tensComponentString = "%s-%s" % (tensPart, onesPart)
                else:
                    tensComponentString = "%s" % tensPart

            # Concatenate the results
            result = ''
            if hundredsComponent and not tensComponent:
                result = hundredsComponentString
            elif not hundredsComponent and tensComponent:
                result = tensComponentString
            elif hundredsComponent and tensComponent:
                result = hundredsComponentString + " " + tensComponentString
            else:
                prints(" NumberToText.stringFromInt(): empty result translating %d" % intToTranslate)
            return result

        def numberTranslate(self):
            hundredsNumber = 0
            thousandsNumber = 0
            hundredsString = ""
            thousandsString = ""
            resultString = ""

            # Test for time
            if re.search(':',self.number):
                time_strings = self.number.split(":")
                hours = EPUB_MOBI.NumberToText(time_strings[0]).text
                minutes = EPUB_MOBI.NumberToText(time_strings[1]).text
                self.text = '%s-%s' % (hours.capitalize(), minutes)

            # Test for decimal
            elif re.search('\.',self.number):
                decimal_strings = self.number.split(".")
                left = EPUB_MOBI.NumberToText(decimal_strings[0]).text
                right = EPUB_MOBI.NumberToText(decimal_strings[1]).text
                self.text = '%s point %s' % (left.capitalize(), right)

            # Test for hypenated
            elif re.search('-', self.number):
                strings = self.number.split('-')
                if re.search('[0-9]+', strings[0]):
                    left = EPUB_MOBI.NumberToText(strings[0]).text
                    right = strings[1]
                else:
                    left = strings[0]
                    right = EPUB_MOBI.NumberToText(strings[1]).text
                self.text = '%s-%s' % (left, right)

            # Test for comma
            elif re.search(',', self.number):
                self.text = EPUB_MOBI.NumberToText(self.number.replace(',','')).text

            # Test for hybrid e.g., 'K2'
            elif re.search('[\D]+', self.number):
                result = []
                for char in self.number:
                    if re.search('[\d]+', char):
                        result.append(EPUB_MOBI.NumberToText(char).text)
                    else:
                        result.append(char)
                self.text = ''.join(result)

            else:
                try:
                    number = int(self.number)
                except:
                    return

                if number > 1000000:
                    self.text = "%d out of range" % number
                    return

                if number == 1000000:
                    self.text = "one million"
                else :
                    # Strip out the three-digit number groups
                    thousandsNumber = number/1000
                    hundredsNumber = number - (thousandsNumber * 1000)

                    # Convert the lower 3 numbers - hundredsNumber
                    if hundredsNumber :
                        hundredsString = self.stringFromInt(hundredsNumber)

                    # Convert the upper 3 numbers - thousandsNumber
                    if thousandsNumber:
                        if number > 1099 and number < 2000:
                            resultString = '%s %s' % (self.lessThanTwenty[number/100],
                                                     self.stringFromInt(number % 100))
                            self.text = resultString.strip().capitalize()
                            return
                        else:
                            thousandsString = self.stringFromInt(thousandsNumber)

                    # Concatenate the strings
                    if thousandsNumber and not hundredsNumber:
                        resultString = "%s thousand" % thousandsString

                    if thousandsNumber and hundredsNumber:
                        resultString = "%s thousand %s" % (thousandsString, hundredsString)

                    if not thousandsNumber and hundredsNumber:
                        resultString = "%s" % hundredsString

                    if not thousandsNumber and not hundredsNumber:
                        resultString = "zero"

                    self.text = resultString.strip().capitalize()

    class CatalogBuilder(object):
        '''
        Generates catalog source files from calibre database

        Implementation notes
        - 'Marker tags' in a book's metadata are used to flag special conditions:
                    (Defaults)
                    '~' : Do not catalog this book
                    '+' : Mark this book as read (check mark) in lists
                    '*' : Display trailing text as 'Note: <text>' in top frame next to cover
            '[<source>] : Source of content (e.g., Amazon, Project Gutenberg).  Do not create genre

        - Program flow
            catalog = Catalog(notification=Reporter())
            catalog.createDirectoryStructure()
            catalog.copyResources()
            catalog.buildSources()

        - To do:
    ***     generateThumbnails() creates a default book image from book.svg, but the background
            is black instead of white.  This needs to be fixed (approx line #1418)

        '''

        # Number of discrete steps to catalog creation
        current_step = 0.0
        total_steps = 13.0

        # Used to xlate pubdate to friendly format
        MONTHS = ['January', 'February','March','April','May','June',
                      'July','August','September','October','November','December']
        THUMB_WIDTH = 75
        THUMB_HEIGHT = 100

        # basename              output file basename
        # creator               dc:creator in OPF metadata
        # descriptionClip       limits size of NCX descriptions (Kindle only)
        # includeSources        Used in processSpecialTags to skip tags like '[SPL]'
        # notification          Used to check for cancel, report progress
        # plugin_path           Plugin zip file (resources)
        # stylesheet            CSS stylesheet
        # title                 dc:title in OPF metadata, NCX periodical
        # verbosity             level of diagnostic printout

        def __init__(self, db, opts, plugin,
                     notification=DummyReporter(),
                     stylesheet="content/stylesheet.css"):
            self.__opts = opts
            self.__authors = None
            self.__basename = opts.basename
            self.__booksByAuthor = None
            self.__booksByTitle = None
            self.__catalogPath = PersistentTemporaryDirectory("_epub_mobi_catalog", prefix='')
            self.__contentDir = os.path.join(self.catalogPath, "content")
            self.__creator = opts.creator
            self.__db = db
            self.__descriptionClip = opts.descriptionClip
            self.__error = None
            self.__generateForKindle = True if (self.opts.fmt == 'mobi' and \
                                       self.opts.output_profile and \
                                       self.opts.output_profile.startswith("kindle")) else False
            self.__genres = None
            self.__htmlFileList = []
            self.__markerTags = self.getMarkerTags()
            self.__ncxSoup = None
            self.__playOrder = 1
            self.__plugin = plugin
            self.__plugin_path = opts.plugin_path
            self.__progressInt = 0.0
            self.__progressString = ''
            self.__reporter = notification
            self.__stylesheet = stylesheet
            self.__thumbs = None
            self.__title = opts.catalog_title
            self.__verbose = opts.verbose

            self.opts.log.info("CatalogBuilder(): Generating %s %s"% \
                                (self.opts.fmt,
                                 "for %s" % self.opts.output_profile if self.opts.output_profile \
                                  else ''))
        # Accessors
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
        def booksByAuthor(self):
            def fget(self):
                return self.__booksByAuthor
            def fset(self, val):
                self.__booksByAuthor = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def booksByTitle(self):
            def fget(self):
                return self.__booksByTitle
            def fset(self, val):
                self.__booksByTitle = val
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
            return property(fget=fget)
        @dynamic_property
        def generateForKindle(self):
            def fget(self):
                return self.__generateForKindle
            def fset(self, val):
                self.__generateForKindle = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def genres(self):
            def fget(self):
                return self.__genres
            def fset(self, val):
                self.__genres = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def htmlFileList(self):
            def fget(self):
                return self.__htmlFileList
            def fset(self, val):
                self.__htmlFileList = val
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
        def pluginPath(self):
            def fget(self):
                return self.__pluginPath
            def fset(self, val):
                self.__pluginPath = val
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
        @dynamic_property
        def title(self):
            def fget(self):
                return self.__title
            def fset(self, val):
                self.__title = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def verbose(self):
            def fget(self):
                return self.__verbose
            def fset(self, val):
                self.__verbose = val
            return property(fget=fget, fset=fset)

        @dynamic_property
        def READ_SYMBOL(self):
            def fget(self):
                return '<font style="color:black">&#x2713;</font>' if self.generateForKindle else \
                       '<font style="color:black">%s</font>' % self.opts.read_tag
            return property(fget=fget)
        @dynamic_property
        def NOT_READ_SYMBOL(self):
            def fget(self):
                return '<font style="color:white">&#x2713;</font>' if self.generateForKindle else \
                       '<font style="color:white">%s</font>' % self.opts.read_tag
            return property(fget=fget)
        @dynamic_property
        def FULL_RATING_SYMBOL(self):
            def fget(self):
                return "&#9733;" if self.generateForKindle else "*"
            return property(fget=fget)
        @dynamic_property
        def EMPTY_RATING_SYMBOL(self):
            def fget(self):
                return "&#9734;" if self.generateForKindle else ' '
            return property(fget=fget)

        # Methods
        def buildSources(self):
            if getattr(self.reporter, 'cancel_requested', False): return 1
            if not self.booksByTitle:
                self.fetchBooksByTitle()

            if getattr(self.reporter, 'cancel_requested', False): return 1
            self.fetchBooksByAuthor()

            if getattr(self.reporter, 'cancel_requested', False): return 1
            self.generateHTMLDescriptions()

            if getattr(self.reporter, 'cancel_requested', False): return 1
            self.generateHTMLByTitle()

            if getattr(self.reporter, 'cancel_requested', False): return 1
            self.generateHTMLByAuthor()

            if getattr(self.reporter, 'cancel_requested', False): return 1
            self.generateHTMLByTags()

            if getattr(self.reporter, 'cancel_requested', False): return 1
            from calibre.utils.PythonMagickWand import ImageMagick
            with ImageMagick():
                self.generateThumbnails()

            if getattr(self.reporter, 'cancel_requested', False): return 1
            self.generateOPF()

            if getattr(self.reporter, 'cancel_requested', False): return 1
            self.generateNCXHeader()

            if getattr(self.reporter, 'cancel_requested', False): return 1
            self.generateNCXDescriptions("Descriptions")

            if getattr(self.reporter, 'cancel_requested', False): return 1
            self.generateNCXByTitle("Titles")

            if getattr(self.reporter, 'cancel_requested', False): return 1
            self.generateNCXByAuthor("Authors")

            if getattr(self.reporter, 'cancel_requested', False): return 1
            self.generateNCXByTags("Genres")

            if getattr(self.reporter, 'cancel_requested', False): return 1
            self.writeNCX()

            return 0

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

        def fetchBooksByTitle(self):

            self.opts.log.info(self.updateProgressFullStep("fetchBooksByTitle()"))

            # Get the database as a dictionary
            # Sort by title
            # Search is a string like this:
            # not tag:<exclude_tag> author:"Riker"
            # So we need to merge opts.exclude_tag with opts.search_text
            # not tag:"~" author:"Riker"

            self.opts.sort_by = 'title'

            # Merge opts.exclude_tag with opts.search_text

            # What if no exclude tags?
            exclude_tags = self.opts.exclude_tags.split(',')
            search_terms = []
            for tag in exclude_tags:
                search_terms.append("tag:%s" % tag)
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

            # Populate this_title{} from data[{},{}]
            titles = []
            for record in data:
                this_title = {}

                title = this_title['title'] = self.convertHTMLEntities(record['title'])
                this_title['title_sort'] = self.generateSortTitle(title)
                this_title['author'] = " &amp; ".join(record['authors'])
                this_title['author_sort'] = record['author_sort'] if len(record['author_sort']) \
                     else self.author_to_author_sort(this_title['author'])
                this_title['id'] = record['id']
                if record['publisher']:
                    this_title['publisher'] = re.sub('&', '&amp;', record['publisher'])

                this_title['rating'] = record['rating'] if record['rating'] else 0
                # <pubdate>2009-11-05 09:29:37</pubdate>
                date_strings = str(record['pubdate']).split("-")
                this_title['date'] = '%s %s' % (self.MONTHS[int(date_strings[1])-1], date_strings[0])

                if record['comments']:
                    this_title['description'] = re.sub('&', '&amp;', record['comments'])
                    this_title['short_description'] = self.generateShortDescription(this_title['description'])
                else:
                    this_title['description'] = None
                    this_title['short_description'] = None

                if record['cover']:
                    this_title['cover'] = re.sub('&amp;', '&', record['cover'])

                # This may be updated in self.processSpecialTags()
                this_title['read'] = False

                if record['tags']:
                    this_title['tags'] = self.processSpecialTags(record['tags'],
                                            this_title, self.opts)
                if record['formats']:
                    formats = []
                    for format in record['formats']:
                        formats.append(self.convertHTMLEntities(format))
                    this_title['formats'] = formats

                titles.append(this_title)

            # Re-sort based on title_sort
            self.booksByTitle = sorted(titles,
                                 key=lambda x:(x['title_sort'].upper(), x['title_sort'].upper()))
            if False and self.verbose:
                self.opts.log.info("fetchBooksByTitle(): %d books" % len(self.booksByTitle))
                for title in self.booksByTitle:
                    self.opts.log.info((u" %-50s %-25s" % (title['title'][0:45], title['title_sort'][0:20])).encode('utf-8'))

        def fetchBooksByAuthor(self):
            # Generate a list of titles sorted by author from the database

            self.opts.log.info(self.updateProgressFullStep("fetchBooksByAuthor()"))

            # Sort titles case-insensitive
            self.booksByAuthor = sorted(self.booksByTitle,
                                 key=lambda x:(x['author_sort'].upper(), x['author_sort'].upper()))

            # Build the unique_authors set from existing data
            authors = [(record['author'], record['author_sort']) for record in self.booksByAuthor]

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

                if author != current_author and i:
                    # Warn if friendly matches previous, but sort doesn't
                    if author[0] == current_author[0]:
                        self.opts.log.warn("Warning: multiple entries for Author '%s' with differing Author Sort metadata:" % author[0])
                        self.opts.log.warn(" '%s' != '%s'" % (author[1], current_author[1]))

                    # New author, save the previous author/sort/count
                    unique_authors.append((current_author[0], current_author[1].title(),
                                           books_by_current_author))
                    current_author = author
                    books_by_current_author = 1
                elif i==0 and len(authors) == 1:
                    # Allow for single-book lists
                    unique_authors.append((current_author[0], current_author[1].title(),
                                           books_by_current_author))
                else:
                    books_by_current_author += 1
            else:
                # Add final author to list or single-author dataset
                if (current_author == author and len(authors) > 1) or not multiple_authors:
                    unique_authors.append((current_author[0], current_author[1].title(),
                                           books_by_current_author))

            if False and self.verbose:
                self.opts.log.info("\nfetchBooksByauthor(): %d unique authors" % len(unique_authors))
                for author in unique_authors:
                    self.opts.log.info((u" %-50s %-25s %2d" % (author[0][0:45], author[1][0:20],
                       author[2])).encode('utf-8'))
            self.authors = unique_authors

        def generateHTMLDescriptions(self):
            # Write each title to a separate HTML file in contentdir
            self.opts.log.info(self.updateProgressFullStep("generateHTMLDescriptions()"))

            for (title_num, title) in enumerate(self.booksByTitle):
                if False:
                    self.opts.log.info("%3s: %s - %s" % (title['id'], title['title'], title['author']))

                self.updateProgressMicroStep("generating book descriptions ...",
                        float(title_num*100/len(self.booksByTitle))/100)

                # Generate the header
                soup = self.generateHTMLDescriptionHeader("%s" % title['title'])
                body = soup.find('body')

                btc = 0

                # Insert the anchor
                aTag = Tag(soup, "a")
                aTag['name'] = "book%d" % int(title['id'])
                body.insert(btc, aTag)
                btc += 1

                # Insert the book title
                #<p class="title"><a name="<database_id>"></a><em>Book Title</em></p>
                emTag = Tag(soup, "em")
                emTag.insert(0, NavigableString(escape(title['title'])))
                titleTag = body.find(attrs={'class':'title'})
                titleTag.insert(0,emTag)

                # Insert the author
                authorTag = body.find(attrs={'class':'author'})
                aTag = Tag(soup, "a")
                aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generateAuthorAnchor(title['author']))
                #aTag.insert(0, escape(title['author']))
                aTag.insert(0, title['author'])
                authorTag.insert(0, NavigableString("by "))
                authorTag.insert(1, aTag)

                '''
                # Insert the unlinked genres.
                if 'tags' in title:
                    tagsTag = body.find(attrs={'class':'tags'})
                    emTag = Tag(soup,"em")
                    emTag.insert(0,NavigableString(', '.join(title['tags'])))
                    tagsTag.insert(0,emTag)

                '''
                # Insert linked genres
                if 'tags' in title:
                    tagsTag = body.find(attrs={'class':'tags'})
                    ttc = 0

                    # Insert a spacer to match the author indent
                    fontTag = Tag(soup,"font")
                    fontTag['style'] = 'color:white;font-size:large'
                    if self.opts.fmt == 'epub':
                        fontTag['style'] += ';opacity: 0.0'
                    fontTag.insert(0, NavigableString("by "))
                    tagsTag.insert(ttc, fontTag)
                    ttc += 1

                    for tag in title['tags']:
                        aTag = Tag(soup,'a')
                        aTag['href'] = "Genre%s.html" % re.sub("\W","",self.convertHTMLEntities(tag))
                        aTag.insert(0,escape(NavigableString(tag)))
                        emTag = Tag(soup, "em")
                        emTag.insert(0, aTag)
                        if ttc < len(title['tags']):
                            emTag.insert(1, NavigableString(', '))
                        tagsTag.insert(ttc, emTag)
                        ttc += 1

                # Insert the cover <img> if available
                imgTag = Tag(soup,"img")
                if 'cover' in title:
                    imgTag['src']  = "../images/thumbnail_%d.jpg" % int(title['id'])
                else:
                    imgTag['src']  = "../images/thumbnail_default.jpg"
                imgTag['alt'] = "cover"
                imgTag['style'] = 'width: %dpx; height:%dpx;' % (self.THUMB_WIDTH, self.THUMB_HEIGHT)
                thumbnailTag = body.find(attrs={'class':'thumbnail'})
                thumbnailTag.insert(0,imgTag)

                # Insert the publisher
                publisherTag = body.find(attrs={'class':'publisher'})
                if 'publisher' in title:
                    publisherTag.insert(0,NavigableString(title['publisher'] + '<br/>' ))
                else:
                    publisherTag.insert(0,NavigableString('<br/>'))

                # Insert the publication date
                pubdateTag = body.find(attrs={'class':'date'})
                if title['date'] is not None:
                    pubdateTag.insert(0,NavigableString(title['date'] + '<br/>'))
                else:
                    pubdateTag.insert(0,NavigableString('<br/>'))

                # Insert the rating
                # Render different ratings chars for epub/mobi
                stars = int(title['rating']) / 2
                star_string = self.FULL_RATING_SYMBOL * stars
                empty_stars = self.EMPTY_RATING_SYMBOL * (5 - stars)

                ratingTag = body.find(attrs={'class':'rating'})
                ratingTag.insert(0,NavigableString('%s%s <br/>' % (star_string,empty_stars)))

                # Insert user notes or remove Notes label.  Notes > 1 line will push formatting down
                if 'notes' in title:
                    notesTag = body.find(attrs={'class':'notes'})
                    notesTag.insert(0,NavigableString(title['notes'] + '<br/>'))
                else:
                    notes_labelTag = body.find(attrs={'class':'notes_label'})
                    empty_labelTag = Tag(soup, "td")
                    empty_labelTag.insert(0,NavigableString('<br/>'))
                    notes_labelTag.replaceWith(empty_labelTag)

                # Insert the blurb
                if 'description' in title and title['description'] > '':
                    blurbTag = body.find(attrs={'class':'description'})
                    blurbTag.insert(0,NavigableString(title['description']))

                # Write the book entry to contentdir
                outfile = open("%s/book_%d.html" % (self.contentDir, int(title['id'])), 'w')
                outfile.write(soup.prettify())
                outfile.close()

        def generateHTMLByTitle(self):
            # Write books by title A-Z to HTML file

            self.opts.log.info(self.updateProgressFullStep("generateHTMLByTitle()"))

            soup = self.generateHTMLEmptyHeader("Books By Alpha Title")
            body = soup.find('body')
            btc = 0

            # Insert section tag
            aTag = Tag(soup,'a')
            aTag['name'] = 'section_start'
            body.insert(btc, aTag)
            btc += 1

            # Insert the anchor
            aTag = Tag(soup, "a")
            aTag['name'] = "bytitle"
            body.insert(btc, aTag)
            btc += 1

            '''
            # We don't need this because the Kindle shows section titles
            #<h2><a name="byalphatitle" id="byalphatitle"></a>By Title</h2>
            h2Tag = Tag(soup, "h2")
            aTag = Tag(soup, "a")
            aTag['name'] = "bytitle"
            h2Tag.insert(0,aTag)
            h2Tag.insert(1,NavigableString('By Title (%d)' % len(self.booksByTitle)))
            body.insert(btc,h2Tag)
            btc += 1
            '''

            # <p class="letter_index">
            # <p class="book_title">
            divTag = Tag(soup, "div")
            dtc = 0
            current_letter = ""

            # Loop through the books by title
            for book in self.booksByTitle:
                if book['title_sort'][0].upper() != current_letter :
                    # Start a new letter
                    current_letter = book['title_sort'][0].upper()
                    pIndexTag = Tag(soup, "p")
                    pIndexTag['class'] = "letter_index"
                    aTag = Tag(soup, "a")
                    aTag['name'] = "%stitles" % book['title_sort'][0].upper()
                    pIndexTag.insert(0,aTag)
                    pIndexTag.insert(1,NavigableString(book['title_sort'][0].upper()))
                    divTag.insert(dtc,pIndexTag)
                    dtc += 1

                # Add books
                pBookTag = Tag(soup, "p")
                ptc = 0

                # Prefix book with read/unread symbol
                if book['read']:
                    # check mark
                    pBookTag.insert(ptc,NavigableString(self.READ_SYMBOL))
                    pBookTag['class'] = "read_book"
                    ptc += 1
                else:
                    # hidden check mark
                    pBookTag['class'] = "unread_book"
                    pBookTag.insert(ptc,NavigableString(self.NOT_READ_SYMBOL))
                    ptc += 1

                # Link to book
                aTag = Tag(soup, "a")
                aTag['href'] = "book_%d.html" % (int(float(book['id'])))
                aTag.insert(0,escape(book['title']))
                pBookTag.insert(ptc, aTag)
                ptc += 1

                # Dot
                pBookTag.insert(ptc, NavigableString(" &middot; "))
                ptc += 1

                # Link to author
                emTag = Tag(soup, "em")
                aTag = Tag(soup, "a")
                aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generateAuthorAnchor(book['author']))
                aTag.insert(0, NavigableString(book['author']))
                emTag.insert(0,aTag)
                pBookTag.insert(ptc, emTag)
                ptc += 1

                divTag.insert(dtc, pBookTag)
                dtc += 1

            # Add the divTag to the body
            body.insert(btc, divTag)
            btc += 1

            # Write the volume to contentdir
            outfile_spec = "%s/ByAlphaTitle.html" % (self.contentDir)
            outfile = open(outfile_spec, 'w')
            outfile.write(soup.prettify())
            outfile.close()
            self.htmlFileList.append("content/ByAlphaTitle.html")

        def generateHTMLByAuthor(self):
            # Write books by author A-Z
            self.opts.log.info(self.updateProgressFullStep("generateHTMLByAuthor()"))

            friendly_name = "By Author"

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
            '''
            # We don't need this because the kindle inserts section titles
            #<h2><a name="byalphaauthor" id="byalphaauthor"></a>By Author</h2>
            h2Tag = Tag(soup, "h2")
            aTag = Tag(soup, "a")
            anchor_name = friendly_name.lower()
            aTag['name'] = anchor_name.replace(" ","")
            h2Tag.insert(0,aTag)
            h2Tag.insert(1,NavigableString('%s' % friendly_name))
            body.insert(btc,h2Tag)
            btc += 1
            '''

            # <p class="letter_index">
            # <p class="author_index">
            divTag = Tag(soup, "div")
            dtc = 0
            current_letter = ""
            current_author = ""

            # Loop through books_by_author
            book_count = 0
            for book in self.booksByAuthor:
                book_count += 1
                if book['author_sort'][0].upper() != current_letter :
                    '''
                    # Start a new letter - anchor only, hidden
                    current_letter = book['author_sort'][0].upper()
                    aTag = Tag(soup, "a")
                    aTag['name'] = "%sauthors" % current_letter
                    divTag.insert(dtc, aTag)
                    dtc += 1
                    '''
                    # Start a new letter with Index letter
                    current_letter = book['author_sort'][0].upper()
                    pIndexTag = Tag(soup, "p")
                    pIndexTag['class'] = "letter_index"
                    aTag = Tag(soup, "a")
                    aTag['name'] = "%sauthors" % current_letter
                    pIndexTag.insert(0,aTag)
                    pIndexTag.insert(1,NavigableString(book['author_sort'][0].upper()))
                    divTag.insert(dtc,pIndexTag)
                    dtc += 1

                if book['author'] != current_author:
                    # Start a new author
                    current_author = book['author']
                    pAuthorTag = Tag(soup, "p")
                    pAuthorTag['class'] = "author_index"
                    emTag = Tag(soup, "em")
                    aTag = Tag(soup, "a")
                    aTag['name'] = "%s" % self.generateAuthorAnchor(current_author)
                    aTag.insert(0,NavigableString(current_author))
                    emTag.insert(0,aTag)
                    pAuthorTag.insert(0,emTag)
                    divTag.insert(dtc,pAuthorTag)
                    dtc += 1

                # Add books
                pBookTag = Tag(soup, "p")
                ptc = 0

                # Prefix book with read/unread symbol
                if book['read']:
                    # check mark
                    pBookTag.insert(ptc,NavigableString(self.READ_SYMBOL))
                    pBookTag['class'] = "read_book"
                    ptc += 1
                else:
                    # hidden check mark
                    pBookTag['class'] = "unread_book"
                    pBookTag.insert(ptc,NavigableString(self.NOT_READ_SYMBOL))
                    ptc += 1

                aTag = Tag(soup, "a")
                aTag['href'] = "book_%d.html" % (int(float(book['id'])))
                aTag.insert(0,escape(book['title']))
                pBookTag.insert(ptc, aTag)
                ptc += 1

                divTag.insert(dtc, pBookTag)
                dtc += 1

            '''
            # Insert the <h2> tag with book_count at the head
            #<h2><a name="byalphaauthor" id="byalphaauthor"></a>By Author</h2>
            h2Tag = Tag(soup, "h2")
            aTag = Tag(soup, "a")
            anchor_name = friendly_name.lower()
            aTag['name'] = anchor_name.replace(" ","")
            h2Tag.insert(0,aTag)
            h2Tag.insert(1,NavigableString('%s (%d)' % (friendly_name, book_count)))
            body.insert(btc,h2Tag)
            btc += 1
            '''

            # Add the divTag to the body
            body.insert(btc, divTag)


            # Write the generated file to contentdir
            outfile_spec = "%s/ByAlphaAuthor.html" % (self.contentDir)
            outfile = open(outfile_spec, 'w')
            outfile.write(soup.prettify())
            outfile.close()
            self.htmlFileList.append("content/ByAlphaAuthor.html")

        def generateHTMLByTags(self):
            # Generate individual HTML files for each tag, e.g. Fiction, Nonfiction ...
            # Note that special tags - ~+*[] -  have already been filtered from books[]

            self.opts.log.info(self.updateProgressFullStep("generateHTMLByTags()"))

            # Filter out REMOVE_TAGS, sort
            filtered_tags = self.filterDbTags(self.db.all_tags())

            # Extract books matching filtered_tags
            genre_list = []
            for tag in filtered_tags:
                tag_list = {}
                tag_list['tag'] = tag
                tag_list['books'] = []
                for book in self.booksByAuthor:
                    if 'tags' in book and tag in book['tags']:
                        this_book = {}
                        this_book['author'] = book['author']
                        this_book['title'] = book['title']
                        this_book['author_sort'] = book['author_sort']
                        this_book['read'] = book['read']
                        this_book['id'] = book['id']
                        tag_list['books'].append(this_book)

                if len(tag_list['books']):
                    # Possible to have an empty tag list if the books were excluded
                    genre_list.append(tag_list)

            # Write the results
            # genre_list = [ [tag_list], [tag_list] ...]
            master_genre_list = []
            for (index, genre) in enumerate(genre_list):
                # Create sorted_authors[0] = friendly, [1] = author_sort for NCX creation
                authors = []
                for book in genre['books']:
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
                '''
                # Extract the unique entries
                unique_authors = []
                for author in authors:
                    if not author in unique_authors:
                        unique_authors.append(author)
                '''

                # Write the genre book list as an article
                titles_spanned = self.generateHTMLByGenre(genre['tag'], True if index==0 else False, genre['books'],
                                    "%s/Genre%s.html" % (self.contentDir, re.sub("\W","", self.convertHTMLEntities(genre['tag']))))

                tag_file = "content/Genre%s.html" % (re.sub("\W","", self.convertHTMLEntities(genre['tag'])))
                master_genre_list.append({'tag':genre['tag'],
                                          'file':tag_file,
                                          'authors':unique_authors,
                                          'books':genre['books'],
                                          'titles_spanned':titles_spanned})

            self.genres = master_genre_list

        def generateThumbnails(self):
            # Generate a thumbnail per cover.  If a current thumbnail exists, skip
            # If a cover doesn't exist, use default
            # Return list of active thumbs

            thumbs = ['thumbnail_default.jpg']

            image_dir = "%s/images" % self.catalogPath

            for (i,title) in enumerate(self.booksByTitle):
                # Update status
                self.updateProgressMicroStep("generating thumbnails ...",
                        i/float(len(self.booksByTitle)))
                # Check to see if source file exists
                if 'cover' in title and os.path.isfile(title['cover']):
                    # Add the thumb spec to thumbs[]
                    thumbs.append("thumbnail_%d.jpg" % int(title['id']))

                    # Check to see if thumbnail exists
                    thumb_fp = "%s/thumbnail_%d.jpg" % (image_dir,int(title['id']))
                    thumb_file = 'thumbnail_%d.jpg' % int(title['id'])
                    if os.path.isfile(thumb_fp):
                        # Check to see if cover is newer than thumbnail
                        # os.path.getmtime() = modified time
                        # os.path.ctime() = creation time
                        cover_timestamp = os.path.getmtime(title['cover'])
                        thumb_timestamp = os.path.getmtime(thumb_fp)
                        if thumb_timestamp < cover_timestamp:
                           self.generateThumbnail(title, image_dir, thumb_file)
                    else:
                        self.generateThumbnail(title, image_dir, thumb_file)
                else:
                    # Use default cover
                    if self.verbose:
                        self.opts.log.warn(" using default cover for '%s'" % \
                        (title['title']))
                    # Check to make sure default is current
                    # Check to see if thumbnail exists
                    thumb_fp = "%s/thumbnail_default.jpg" % (image_dir)
                    cover = "%s/DefaultCover.png" % (self.catalogPath)

                    # Init Qt for image conversion
                    from calibre.gui2 import is_ok_to_use_qt
                    if is_ok_to_use_qt():
                        from PyQt4.Qt import QImage, QColor, QPainter, Qt

                        # Convert .svg to .jpg
                        cover_img = QImage(I('book.svg'))
                        i = QImage(cover_img.size(),
                                QImage.Format_ARGB32_Premultiplied)
                        i.fill(QColor(Qt.white).rgb())
                        p = QPainter(i)
                        p.drawImage(0, 0, cover_img)
                        p.end()
                        i.save(cover)
                    else:
                        if not os.path.exists(cover):
                            shutil.copyfile(I('library.png'), cover)

                    if os.path.isfile(thumb_fp):
                        # Check to see if default cover is newer than thumbnail
                        # os.path.getmtime() = modified time
                        # os.path.ctime() = creation time
                        cover_timestamp = os.path.getmtime(cover)
                        thumb_timestamp = os.path.getmtime(thumb_fp)
                        if thumb_timestamp < cover_timestamp:
                            if self.verbose:
                                self.opts.log.warn("updating thumbnail_default for %s" % title['title'])
                            #title['cover'] = "%s/DefaultCover.jpg" % self.catalogPath
                            title['cover'] = cover
                            self.generateThumbnail(title, image_dir, "thumbnail_default.jpg")
                    else:
                        if self.verbose:
                            self.opts.log.warn(" generating new thumbnail_default.jpg")
                        #title['cover'] = "%s/DefaultCover.jpg" % self.catalogPath
                        title['cover'] = cover
                        self.generateThumbnail(title, image_dir, "thumbnail_default.jpg")

            self.thumbs = thumbs

        def generateOPF(self):

            self.opts.log.info(self.updateProgressFullStep("generateOPF()"))

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

            # Write the thumbnail images to the manifest
            for thumb in self.thumbs:
                itemTag = Tag(soup, "item")
                itemTag['href'] = "images/%s" % (thumb)
                end = thumb.find('.jpg')
                itemTag['id'] = "%s-image" % thumb[:end]
                itemTag['media-type'] = 'image/jpeg'
                manifest.insert(mtc, itemTag)
                mtc += 1

            # HTML files - add books to manifest and spine
            for book in self.booksByTitle:
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

            # Add other html_files to manifest and spine

            for file in self.htmlFileList:
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

            self.opts.log.info(self.updateProgressFullStep("generateNCXHeader()"))

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
            contentTag = Tag(soup, 'content')
            contentTag['src'] = "content/book_%d.html" % int(self.booksByTitle[0]['id'])
            navPointTag.insert(1, contentTag)
            cmiTag = Tag(soup, '%s' % 'calibre:meta-img')
            cmiTag['name'] = "mastheadImage"
            cmiTag['src'] = "images/mastheadImage.gif"
            navPointTag.insert(2,cmiTag)
            navMapTag.insert(0,navPointTag)

            ncx.insert(0,navMapTag)

            self.ncxSoup = soup

        def generateNCXDescriptions(self, tocTitle):

            self.opts.log.info(self.updateProgressFullStep("generateNCXDescriptions()"))

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
            for book in self.booksByTitle:
                navPointVolumeTag = Tag(ncx_soup, 'navPoint')
                navPointVolumeTag['class'] = "article"
                navPointVolumeTag['id'] = "book%dID" % int(book['id'])
                navPointVolumeTag['playOrder'] = self.playOrder
                self.playOrder += 1
                navLabelTag = Tag(ncx_soup, "navLabel")
                textTag = Tag(ncx_soup, "text")
                textTag.insert(0, NavigableString(self.formatNCXText(book['title'])))
                navLabelTag.insert(0,textTag)
                navPointVolumeTag.insert(0,navLabelTag)

                contentTag = Tag(ncx_soup, "content")
                contentTag['src'] = "content/book_%d.html#book%d" % (int(book['id']), int(book['id']))
                navPointVolumeTag.insert(1, contentTag)

                if self.generateForKindle:
                    # Add the author tag
                    cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                    cmTag['name'] = "author"
                    cmTag.insert(0, NavigableString(self.formatNCXText(book['author'])))
                    navPointVolumeTag.insert(2, cmTag)

                    # Add the description tag
                    if book['short_description']:
                        cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                        cmTag['name'] = "description"
                        cmTag.insert(0, NavigableString(self.formatNCXText(book['short_description'])))
                        navPointVolumeTag.insert(3, cmTag)

                # Add this volume to the section tag
                navPointTag.insert(nptc, navPointVolumeTag)
                nptc += 1

            # Add this section to the body
            body.insert(btc, navPointTag)
            btc += 1

            self.ncxSoup = ncx_soup

        def generateNCXByTitle(self, tocTitle):

            self.opts.log.info(self.updateProgressFullStep("generateNCXByTitle()"))

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

            # Loop over the titles, find start of each letter, add description_preview_count books
            current_letter = self.booksByTitle[0]['title_sort'][0].upper()
            title_letters = [current_letter]
            current_book_list = []
            current_book = ""
            for book in self.booksByTitle:
                if book['title_sort'][0].upper() != current_letter:
                    # Save the old list
                    book_list = " &bull; ".join(current_book_list)
                    short_description = self.generateShortDescription(self.formatNCXText(book_list))
                    books_by_letter.append(short_description)

                    # Start the new list
                    current_letter = book['title_sort'][0].upper()
                    title_letters.append(current_letter)
                    current_book = book['title']
                    current_book_list = [book['title']]
                else:
                    if len(current_book_list) < self.descriptionClip and \
                       book['title'] != current_book :
                        current_book = book['title']
                        current_book_list.append(book['title'])

            # Add the last book list
            book_list = " &bull; ".join(current_book_list)
            short_description = self.generateShortDescription(self.formatNCXText(book_list))
            books_by_letter.append(short_description)


            # Add *article* entries for each populated title letter
            for (i,books) in enumerate(books_by_letter):
                navPointByLetterTag = Tag(soup, 'navPoint')
                navPointByLetterTag['class'] = "article"
                navPointByLetterTag['id'] = "%sTitles-ID" % (title_letters[i].upper())
                navPointTag['playOrder'] = self.playOrder
                self.playOrder += 1
                navLabelTag = Tag(soup, 'navLabel')
                textTag = Tag(soup, 'text')
                textTag.insert(0, NavigableString("Books beginning with '%s'" % (title_letters[i].upper())))
                navLabelTag.insert(0, textTag)
                navPointByLetterTag.insert(0,navLabelTag)
                contentTag = Tag(soup, 'content')
                contentTag['src'] = "content/%s.html#%stitles" % (output, title_letters[i].upper())
                navPointByLetterTag.insert(1,contentTag)

                if self.generateForKindle:
                    cmTag = Tag(soup, '%s' % 'calibre:meta')
                    cmTag['name'] = "description"
                    cmTag.insert(0, NavigableString(self.formatNCXText(books)))
                    navPointByLetterTag.insert(2, cmTag)

                navPointTag.insert(nptc, navPointByLetterTag)
                nptc += 1

            # Add this section to the body
            body.insert(btc, navPointTag)
            btc += 1

            self.ncxSoup = soup

        def generateNCXByAuthor(self, tocTitle):

            self.opts.log.info(self.updateProgressFullStep("generateNCXByAuthor()"))

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
            master_author_list = []
            # self.authors[0][1][0] = Initial letter of author_sort[0]
            current_letter = self.authors[0][1][0]
            current_author_list = []
            for author in self.authors:
                if author[1][0] != current_letter:
                    # Save the old list
                    author_list = " &bull; ".join(current_author_list)
                    if len(current_author_list) == self.descriptionClip:
                        author_list += " &hellip;"

                    author_list = self.formatNCXText(author_list)
                    if False and self.verbose:
                        self.opts.log.info(" adding '%s' to master_author_list" % current_letter)
                    master_author_list.append((author_list, current_letter))

                    # Start the new list
                    current_letter = author[1][0]
                    current_author_list = [author[0]]
                else:
                    if len(current_author_list) < self.descriptionClip:
                        current_author_list.append(author[0])

            # Add the last author list
            author_list = " &bull; ".join(current_author_list)
            if len(current_author_list) == self.descriptionClip:
                author_list += " &hellip;"
            author_list = self.formatNCXText(author_list)
            if False and self.verbose:
                self.opts.log.info(" adding '%s' to master_author_list" % current_letter)
            master_author_list.append((author_list, current_letter))

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
                textTag.insert(0, NavigableString("Authors beginning with '%s'" % (authors_by_letter[1])))
                navLabelTag.insert(0, textTag)
                navPointByLetterTag.insert(0,navLabelTag)
                contentTag = Tag(soup, 'content')
                contentTag['src'] = "%s#%sauthors" % (HTML_file, authors_by_letter[1])

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

        def generateNCXByTags(self, tocTitle):
            # Create an NCX section for 'By Genre'
            # Add each genre as an article
            # 'tag', 'file', 'authors'

            self.opts.log.info(self.updateProgressFullStep("generateNCXByTags()"))

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
            contentTag['src'] = "content/Genre%s.html#section_start" % (re.sub("\W","", self.convertHTMLEntities(self.genres[0]['tag'])))
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
                textTag.insert(0, self.formatNCXText(NavigableString(genre['tag'])))
                navLabelTag.insert(0,textTag)
                navPointVolumeTag.insert(0,navLabelTag)

                contentTag = Tag(ncx_soup, "content")
                genre_name = re.sub("\W","", self.convertHTMLEntities(genre['tag']))
                contentTag['src'] = "content/Genre%s.html#Genre%s" % (genre_name, genre_name)
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
                        cmTag.insert(0, NavigableString(self.formatNCXText(title_range)))
                    else:
                        # Form 2: title &bull; title &bull; title ...
                        titles = []
                        for title in genre['books']:
                            titles.append(title['title'])
                        titles = sorted(titles, key=lambda x:(self.generateSortTitle(x),self.generateSortTitle(x)))
                        titles_list = self.generateShortDescription(" &bull; ".join(titles))
                        cmTag.insert(0, NavigableString(self.formatNCXText(titles_list)))

                    navPointVolumeTag.insert(3, cmTag)

                # Add this volume to the section tag
                navPointTag.insert(nptc, navPointVolumeTag)
                nptc += 1

            # Add this section to the body
            body.insert(btc, navPointTag)
            btc += 1

            self.ncxSoup = ncx_soup

        def writeNCX(self):

            self.opts.log.info(self.updateProgressFullStep("writeNCX()"))

            outfile = open("%s/%s.ncx" % (self.catalogPath, self.basename), 'w')
            outfile.write(self.ncxSoup.prettify())

        # Helpers
        def author_to_author_sort(self, author):
            tokens = author.split()
            tokens = tokens[-1:] + tokens[:-1]
            if len(tokens) > 1:
                tokens[0] += ','
            return ' '.join(tokens)


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

        def getMarkerTags(self):
            ''' Return a list of special marker tags to be excluded from genre list '''
            markerTags = []
            markerTags.extend(self.opts.exclude_tags.split(','))
            markerTags.extend(self.opts.note_tag.split(','))
            markerTags.extend(self.opts.read_tag.split(','))
            return markerTags

        def filterDbTags(self, tags):
            # Remove the special marker tags from the database's tag list,
            # return sorted list of tags representing valid genres

            filtered_tags = []
            for tag in tags:
                if tag[0] in self.markerTags:
                    continue
                if re.search(self.opts.exclude_genre, tag):
                    continue
                if tag == ' ':
                    continue

                filtered_tags.append(tag)

            filtered_tags.sort()

            # Enable this code to force certain tags to the front of the genre list
            if False:
                for (i, tag) in enumerate(filtered_tags):
                    if tag == 'Fiction':
                        filtered_tags.insert(0, (filtered_tags.pop(i)))
                    elif tag == 'Nonfiction':
                        filtered_tags.insert(1, (filtered_tags.pop(i)))
                    else:
                        continue
            if self.verbose:
                self.opts.log.info(' %d Genre tags in database (exclude_genre: %s):' % \
                                     (len(filtered_tags), self.opts.exclude_genre))
                self.opts.log.info(' %s' % ', '.join(filtered_tags))

            return filtered_tags

        def formatNCXText(self, description):
            # Kindle TOC descriptions won't render certain characters
            # Fix up
            massaged = unicode(BeautifulStoneSoup(description, convertEntities=BeautifulStoneSoup.HTML_ENTITIES))

            # Replace '&' with '&#38;'
            massaged = re.sub("&","&#38;", massaged)

            return massaged.strip()

        def generateAuthorAnchor(self, author):
            # Strip white space to ''
            return re.sub("\W","", author)

        def generateHTMLByGenre(self, genre, section_head, books, outfile):
            # Write an HTML file of this genre's book list
            # Return a list with [(first_author, first_book), (last_author, last_book)]

            soup = self.generateHTMLGenreHeader(genre)
            body = soup.find('body')

            btc = 0

            # Insert section tag if this is the section start - first article only
            if section_head:
                aTag = Tag(soup,'a')
                aTag['name'] = 'section_start'
                body.insert(btc, aTag)
                btc += 1

            # Insert the anchor with spaces stripped
            aTag = Tag(soup, 'a')
            aTag['name'] = "Genre%s" % re.sub("\W","", genre)
            body.insert(btc,aTag)
            btc += 1

            # Insert the genre title
            titleTag = body.find(attrs={'class':'title'})
            titleTag.insert(0,NavigableString('<b><i>%s</i></b>' % escape(genre)))

            # Insert the books by author list
            divTag = body.find(attrs={'class':'authors'})
            dtc = 0

            current_author = ''
            for book in books:
                if book['author'] != current_author:
                    # Start a new author with link
                    current_author = book['author']
                    pAuthorTag = Tag(soup, "p")
                    pAuthorTag['class'] = "author_index"
                    emTag = Tag(soup, "em")
                    aTag = Tag(soup, "a")
                    aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generateAuthorAnchor(book['author']))
                    aTag.insert(0, book['author'])
                    emTag.insert(0,aTag)
                    pAuthorTag.insert(0,emTag)
                    divTag.insert(dtc,pAuthorTag)
                    dtc += 1

                # Add books
                pBookTag = Tag(soup, "p")
                ptc = 0

                # Prefix book with read/unread symbol
                if book['read']:
                    pBookTag.insert(ptc,NavigableString(self.READ_SYMBOL))
                    pBookTag['class'] = "read_book"
                else:
                    pBookTag['class'] = "unread_book"
                    pBookTag.insert(ptc,NavigableString(self.NOT_READ_SYMBOL))
                ptc += 1

                # Add the book title
                aTag = Tag(soup, "a")
                aTag['href'] = "book_%d.html" % (int(float(book['id'])))
                aTag.insert(0,escape(book['title']))
                pBookTag.insert(ptc, aTag)
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

        def generateHTMLDescriptionHeader(self, title):

            title_border = '' if self.opts.fmt == 'epub' else \
                    '<div class="hr"><blockquote><hr/></blockquote></div>'
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
            {0}
            <p class="author"></p>
            <p class="tags">&nbsp;</p>
            <table width="100%" border="0">
              <tr>
                <td class="thumbnail" rowspan="7"></td>
                <td>&nbsp;</td>
                <td>&nbsp;</td>
              </tr>
              <tr>
                <td>&nbsp;</td>
                <td>&nbsp;</td>
              </tr>
              <tr>
                <td>Publisher</td>
                <td class="publisher"></td>
              </tr>
              <tr>
                <td>Published</td>
                <td class="date"></td>
              </tr>
              <tr>
                <td>Rating</td>
                <td class="rating"></td>
              </tr>
              <tr>
                <td class="notes_label">Notes</td>
                <td class="notes"></td>
              </tr>
              <tr>
                <td>&nbsp;</td>
                <td>&nbsp;</td>
              </tr>
            </table>
            <blockquote><hr/></blockquote>
            <p class="description"></p>
            <!--blockquote><hr/></blockquote-->
            <!--p class="instructions">&#9654; Press <span style="font-variant:small-caps"><b>back</b></span> to return to list &#9664;</p-->
            </body>
            </html>
            '''.format(title_border)

            # Insert the supplied title
            soup = BeautifulSoup(header, selfClosingTags=['mbp:pagebreak'])
            titleTag = soup.find('title')
            titleTag.insert(0,NavigableString(escape(title)))
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
                    <div class="hr"><blockquote><hr/></blockquote></div>
                    <div class="authors"></div>
                </body>
                </html>
                '''
            # Insert the supplied title
            soup = BeautifulSoup(header)
            titleTag = soup.find('title')
            titleTag.insert(0,escape(NavigableString(title)))
            return soup

        def generateShortDescription(self, description):
            # Truncate the description to description_clip, on word boundaries if necessary

            if not description:
                return None

            if not self.descriptionClip:
                return description

            if len(description) < self.descriptionClip:
                return description

            # Start adding words until we reach description_clip
            short_description = ""
            words = description.split(" ")
            for word in words:
                short_description += word + " "
                if len(short_description) > self.descriptionClip:
                    short_description += "..."
                    return short_description

            return short_description

        def generateSortTitle(self, title):
            # Convert the actual title to a string suitable for sorting.
            # Convert numbers to strings, ignore leading stop words
            # The 21-Day Consciousness Cleanse
            # Scan for numbers in each word clump.
            from calibre.ebooks.metadata import title_sort

            title_words = title_sort(title).split()
            translated = []

            for (i,word) in enumerate(title_words):
                # Initial numbers translated to text equivalent
                if i==0 and re.search('[0-9]+',word):
                    translated.append(EPUB_MOBI.NumberToText(word).text)
                else:
                    if re.search('[0-9]+',word):
                        # Coerce standard-width strings for numbers
                        word = '%03d' % int(re.sub('\D','',word))
                    translated.append(word)
            return ' '.join(translated)

        def generateThumbnail(self, title, image_dir, thumb_file):
            import calibre.utils.PythonMagickWand as pw
            try:
                img = pw.NewMagickWand()
                if img < 0:
                    raise RuntimeError('generateThumbnail(): Cannot create wand')
                # Read the cover
                if not pw.MagickReadImage(img,
                        title['cover'].encode(filesystem_encoding)):
                    self.opts.log.error('generateThumbnail(): Failed to read cover image from: %s' % title['cover'])
                    raise IOError
                thumb = pw.CloneMagickWand(img)
                if thumb < 0:
                    self.opts.log.error('generateThumbnail(): Cannot clone cover')
                    raise RuntimeError
                # img, width, height
                pw.MagickThumbnailImage(thumb, self.THUMB_WIDTH, self.THUMB_HEIGHT)
                pw.MagickWriteImage(thumb, os.path.join(image_dir, thumb_file))
                pw.DestroyMagickWand(thumb)
                pw.DestroyMagickWand(img)
            except IOError:
                self.opts.log.error("generateThumbnail(): IOError with %s" % title['title'])
            except RuntimeError:
                self.opts.log.error("generateThumbnail(): RuntimeError with %s" % title['title'])

        def processSpecialTags(self, tags, this_title, opts):
            tag_list = []
            for tag in tags:
                tag = self.convertHTMLEntities(tag)
                if tag.startswith(opts.note_tag):
                    this_title['notes'] = tag[1:]
                elif tag == opts.read_tag:
                    this_title['read'] = True
                elif re.search(opts.exclude_genre, tag):
                    continue
                else:
                    tag_list.append(tag)
            return tag_list

        class NotImplementedError:
            def __init__(self, error):
                self.error = error

            def logerror(self):
                self.opts.log.info('%s not implemented' % self.error)

        def updateProgressFullStep(self, description):

            self.current_step += 1
            self.progressString = description
            self.progressInt = float((self.current_step-1)/self.total_steps)
            self.reporter(self.progressInt/100., self.progressString)
            return u"%.2f%% %s" % (self.progressInt, self.progressString)

        def updateProgressMicroStep(self, description, micro_step_pct):
            step_range = 100/self.total_steps
            self.progressString = description
            coarse_progress = float((self.current_step-1)/self.total_steps)
            fine_progress = float((micro_step_pct*step_range)/100)
            self.progressInt = coarse_progress + fine_progress
            self.reporter(self.progressInt/100., self.progressString)
            return u"%.2f%% %s" % (self.progressInt, self.progressString)

    def run(self, path_to_output, opts, db, notification=DummyReporter()):

        opts.log = log = Log()
        opts.fmt = self.fmt = path_to_output.rpartition('.')[2]
        self.opts = opts

        # Add local options
        opts.creator = "calibre"
        opts.descriptionClip = 250
        opts.basename = "Catalog"
        opts.plugin_path = self.plugin_path

        if opts.verbose:
            opts_dict = vars(opts)
            log("%s:run" % self.name)
            log(" path_to_output: %s" % path_to_output)
            log(" Output format: %s" % self.fmt)
            if opts_dict['ids']:
                log(" Book count: %d" % len(opts_dict['ids']))
            # Display opts
            keys = opts_dict.keys()
            keys.sort()
            log(" opts:")
            for key in keys:
                if key == 'ids':
                    if opts_dict[key]:
                        continue
                    else:
                        log("  %s: (all)" % key)
                log("  %s: %s" % (key, opts_dict[key]))

        # Launch the Catalog builder
        catalog = self.CatalogBuilder(db, opts, self, notification=notification)
        catalog.createDirectoryStructure()
        catalog.copyResources()
        catalog.buildSources()

        recommendations = []

        dp = getattr(opts, 'debug_pipeline', None)
        if dp is not None:
            recommendations.append(('debug_pipeline', dp,
                OptionRecommendation.HIGH))

        if opts.fmt == 'mobi' and opts.output_profile and opts.output_profile.startswith("kindle"):
            recommendations.append(('output_profile', opts.output_profile,
                OptionRecommendation.HIGH))
            recommendations.append(('no_inline_toc', True,
                OptionRecommendation.HIGH))

        # Run ebook-convert
        from calibre.ebooks.conversion.plumber import Plumber
        plumber = Plumber(os.path.join(catalog.catalogPath,
                        opts.basename + '.opf'), path_to_output, log, report_progress=notification,
                        abort_after_input_dump=False)
        plumber.merge_ui_recommendations(recommendations)

        plumber.run()
