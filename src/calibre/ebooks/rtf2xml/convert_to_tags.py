
import os, sys

from calibre.ebooks.rtf2xml import copy, check_encoding
from calibre.ptempfile import better_mktemp
from . import open_for_read, open_for_write

public_dtd = 'rtf2xml1.0.dtd'


class ConvertToTags:
    """
    Convert file to XML
    """

    def __init__(self,
            in_file,
            bug_handler,
            dtd_path,
            no_dtd,
            encoding,
            indent=None,
            copy=None,
            run_level=1,
            ):
        """
        Required:
            'file'
        Optional:
            'copy'-- whether to make a copy of result for debugging
            'temp_dir' --where to output temporary results (default is
            directory from which the script is run.)
        Returns:
            nothing
            """
        self.__file = in_file
        self.__bug_handler = bug_handler
        self.__copy = copy
        self.__dtd_path = dtd_path
        self.__no_dtd = no_dtd
        self.__encoding = 'cp' + encoding
        # if encoding == 'mac_roman':
        # self.__encoding = 'mac_roman'
        self.__indent = indent
        self.__run_level = run_level
        self.__write_to = better_mktemp()
        self.__convert_utf = False
        self.__bad_encoding = False

    def __initiate_values(self):
        """
        Set values, including those for the dictionary.
        """
        self.__state = 'default'
        self.__new_line = 0
        self.__block = ('doc', 'preamble', 'rtf-definition', 'font-table',
                'font-in-table', 'color-table', 'color-in-table', 'style-sheet',
                'paragraph-styles', 'paragraph-style-in-table', 'character-styles',
                'character-style-in-table', 'list-table', 'doc-information', 'title',
                'author', 'operator', 'creation-time', 'revision-time',
                'editing-time', 'time', 'number-of-pages', 'number-of-words',
                'number-of-characters', 'page-definition', 'section-definition',
                'headers-and-footers', 'section', 'para', 'body',
                'paragraph-definition', 'cell', 'row', 'table', 'revision-table',
                'style-group', 'border-group','styles-in-body', 'paragraph-style-in-body',
                'list-in-table', 'level-in-table', 'override-table','override-list',
                )
        self.__two_new_line = ('section',  'body',  'table', 'row' 'list-table')
        self.__state_dict = {
        'default'           :   self.__default_func,
        'mi<tg<open______'  :   self.__open_func,
        'mi<tg<close_____'  :   self.__close_func,
        'mi<tg<open-att__'  :   self.__open_att_func,
        'mi<tg<empty-att_'  :   self.__empty_att_func,
        'tx<nu<__________'  :   self.__text_func,
        'tx<ut<__________'  :   self.__text_func,
        'mi<tg<empty_____'  :   self.__empty_func,
        }

    def __open_func(self, line):
        """
        Print the opening tag and newlines when needed.
        """
        # mi<tg<open______<style-sheet
        info = line[17:-1]
        self.__new_line = 0
        if info in self.__block:
            self.__write_new_line()
        if info in self.__two_new_line:
            self.__write_extra_new_line()
        self.__write_obj.write('<%s>' % info)

    def __empty_func(self, line):
        """
        Print out empty tag and newlines when needed.
        """
        info = line[17:-1]
        self.__write_obj.write(
        '<%s/>' % info)
        self.__new_line = 0
        if info in self.__block:
            self.__write_new_line()
        if info in self.__two_new_line:
            self.__write_extra_new_line()

    def __open_att_func(self, line):
        """
        Process lines for open tags that have attributes.
        The important info is between [17:-1]. Take this info and split it
        with the delimeter '<'. The first token in this group is the element
        name. The rest are attributes, separated fromt their values by '>'. So
        read each token one at a time, and split them by '>'.
        """
        # mi<tg<open-att__<footnote<num>
        info = line[17:-1]
        tokens = info.split("<")
        element_name = tokens[0]
        tokens = tokens[1:]
        self.__write_obj.write('<%s' % element_name)
        for token in tokens:
            groups = token.split('>')
            try:
                val = groups[0]
                att = groups[1]
                att = att.replace('"', '&quot;')
                att = att.replace("'", '&quot;')
                self.__write_obj.write(
                ' %s="%s"' % (val, att)
                )
            except:
                if self.__run_level > 3:
                    msg = 'index out of range\n'
                    raise self.__bug_handler(msg)
        self.__write_obj.write('>')
        self.__new_line = 0
        if element_name in self.__block:
            self.__write_new_line()
        if element_name in self.__two_new_line:
            self.__write_extra_new_line()

    def __empty_att_func(self, line):
        """
        Same as the __open_att_func, except a '/' is placed at the end of the tag.
        """
        # mi<tg<open-att__<footnote<num>
        info = line[17:-1]
        tokens = info.split("<")
        element_name = tokens[0]
        tokens = tokens[1:]
        self.__write_obj.write('<%s' % element_name)
        for token in tokens:
            groups = token.split('>')
            val = groups[0]
            att = groups[1]
            att = att.replace('"', '&quot;')
            att = att.replace("'", '&quot;')
            self.__write_obj.write(
            ' %s="%s"' % (val, att))
        self.__write_obj.write('/>')
        self.__new_line = 0
        if element_name in self.__block:
            self.__write_new_line()
        if element_name in self.__two_new_line:
            self.__write_extra_new_line()

    def __close_func(self, line):
        """
        Print out the closed tag and new lines, if appropriate.
        """
        # mi<tg<close_____<style-sheet\n
        info = line[17:-1]
        self.__write_obj.write(
        '</%s>' % info)
        self.__new_line = 0
        if info in self.__block:
            self.__write_new_line()
        if info in self.__two_new_line:
            self.__write_extra_new_line()

    def __text_func(self, line):
        """
        Simply print out the information between [17:-1]
        """
        # tx<nu<__________<Normal;
        # change this!
        self.__write_obj.write(line[17:-1])

    def __write_extra_new_line(self):
        """
        Print out extra new lines if the new lines have not exceeded two. If
        the new lines are greater than two, do nothing.
        """
        if not self.__indent:
            return
        if self.__new_line < 2:
            self.__write_obj.write('\n')

    def __default_func(self, line):
        pass

    def __write_new_line(self):
        """
        Print out a new line if a new line has not already been printed out.
        """
        if not self.__indent:
            return
        if not self.__new_line:
            self.__write_obj.write('\n')
            self.__new_line += 1

    def __write_dec(self):
        """
        Write the XML declaration at the top of the document.
        """
        # keep maximum compatibility with previous version
        check_encoding_obj = check_encoding.CheckEncoding(
                    bug_handler=self.__bug_handler)

        if not check_encoding_obj.check_encoding(self.__file, verbose=False):
            self.__write_obj.write('<?xml version="1.0" encoding="US-ASCII" ?>')
        elif not check_encoding_obj.check_encoding(self.__file, self.__encoding, verbose=False):
            self.__write_obj.write('<?xml version="1.0" encoding="UTF-8" ?>')
            self.__convert_utf = True
        else:
            self.__write_obj.write('<?xml version="1.0" encoding="US-ASCII" ?>')
            sys.stderr.write('Bad RTF encoding, revert to US-ASCII chars and'
                    ' hope for the best')
            self.__bad_encoding = True
        self.__new_line = 0
        self.__write_new_line()
        if self.__no_dtd:
            pass
        elif self.__dtd_path:
            self.__write_obj.write(
            '<!DOCTYPE doc SYSTEM "%s">' % self.__dtd_path
            )
        elif self.__dtd_path == '':
            # don't print dtd if further transformations are going to take
            # place
            pass
        else:
            self.__write_obj.write(
                    '<!DOCTYPE doc PUBLIC "publicID" '
                    '"http://rtf2xml.sourceforge.net/dtd/%s">' % public_dtd
            )
        self.__new_line = 0
        self.__write_new_line()

    def convert_to_tags(self):
        """
        Read in the file one line at a time. Get the important info, between
        [:16]. Check if this info matches a dictionary entry. If it does, call
        the appropriate function.
        The functions that are called:
            a text function for text
            an open function for open tags
            an open with attribute function for tags with attributes
            an empty with attribute function for tags that are empty but have
            attribtes.
            a closed function for closed tags.
            an empty tag function.
            """
        self.__initiate_values()
        with open_for_write(self.__write_to) as self.__write_obj:
            self.__write_dec()
            with open_for_read(self.__file) as read_obj:
                for line in read_obj:
                    self.__token_info = line[:16]
                    action = self.__state_dict.get(self.__token_info)
                    if action is not None:
                        action(line)
        # convert all encodings to UTF8 or ASCII to avoid unsupported encodings in lxml
        if self.__convert_utf or self.__bad_encoding:
            copy_obj = copy.Copy(bug_handler=self.__bug_handler)
            copy_obj.rename(self.__write_to, self.__file)
            with open_for_read(self.__file) as read_obj:
                with open_for_write(self.__write_to) as write_obj:
                    for line in read_obj:
                        write_obj.write(line)
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "convert_to_tags.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
