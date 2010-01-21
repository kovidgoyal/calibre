import os

from calibre.customize import CatalogPlugin

class CSV_XML(CatalogPlugin):
    'CSV/XML catalog generator'

    from collections import namedtuple

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
                    'Available fields: all, author_sort, authors, comments, '
                    'cover, formats, id, isbn, pubdate, publisher, rating, '
                    'series_index, series, size, tags, timestamp, title, uuid.\n'
                    "Default: '%default'\n"
                    "Applies to: CSV, XML output formats")),

            Option('--sort-by',
                default = 'id',
                dest = 'sort_by',
                help = _('Output field to sort on.\n'
                'Available fields: author_sort, id, rating, size, timestamp, title.\n'
                "Default: '%default'\n"
                "Applies to: CSV, XML output formats"))]

    def run(self, path_to_output, opts, db):
        from calibre.utils.logging import Log

        log = Log()
        self.fmt = path_to_output.rpartition('.')[2]
        
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
		
        # Get the sorted, filtered database as a dictionary
        data = self.search_sort_db(db, opts)

        if not len(data):
            log.error("\nNo matching database entries for search criteria '%s'" % opts.search_text)
            raise SystemExit(1)

        # Get the requested output fields as a list
        fields = self.get_output_fields(opts)

        if self.fmt == 'csv':
            outfile = open(path_to_output, 'w')

            # Output the field headers
            outfile.write('%s\n' % ','.join(fields))

            # Output the entry fields
            for entry in data:
                outstr = ''
                for (x, field) in enumerate(fields):
                    item = entry[field]
                    if field in ['authors','tags','formats']:
                        item = ', '.join(item)
                    if x < len(fields) - 1:
                        if item is not None:
                            outstr += '"%s",' % str(item).replace('"','""')
                        else:
                            outstr += '"",'
                    else:
                        if item is not None:
                            outstr += '"%s"\n' % str(item).replace('"','""')
                        else:
                            outstr += '""\n'
                outfile.write(outstr)
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

