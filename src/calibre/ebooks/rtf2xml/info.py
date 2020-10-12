
#########################################################################
#                                                                       #
#                                                                       #
#   copyright 2002 Paul Henry Tremblay                                  #
#                                                                       #
#   This program is distributed in the hope that it will be useful,     #
#   but WITHOUT ANY WARRANTY; without even the implied warranty of      #
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU    #
#   General Public License for more details.                            #
#                                                                       #
#                                                                       #
#########################################################################
import sys, os, re

from calibre.ebooks.rtf2xml import copy
from calibre.ptempfile import better_mktemp
from . import open_for_read, open_for_write


class Info:
    """
    Make tags for document-information
    """

    def __init__(self,
            in_file,
            bug_handler,
            copy=None,
            run_level=1,
            ):
        """
        Required:
            'file'--file to parse
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
        self.__run_level = run_level
        self.__write_to = better_mktemp()

    def __initiate_values(self):
        """
        Initiate all values.
        """
        self.__text_string = ''
        self.__state = 'before_info_table'
        self.rmspace = re.compile(r'\s+')
        self.__state_dict = {
        'before_info_table': self.__before_info_table_func,
        'after_info_table': self.__after_info_table_func,
        'in_info_table'    : self.__in_info_table_func,
        'collect_text'      : self.__collect_text_func,
        'collect_tokens'      : self.__collect_tokens_func,
        }
        self.__info_table_dict = {
        'cw<di<title_____'  : (self.__found_tag_with_text_func, 'title'),
        'cw<di<author____'  : (self.__found_tag_with_text_func, 'author'),
        'cw<di<operator__'  : (self.__found_tag_with_text_func, 'operator'),
        'cw<di<manager___'  : (self.__found_tag_with_text_func, 'manager'),
        'cw<di<company___'  : (self.__found_tag_with_text_func, 'company'),
        'cw<di<keywords__'  : (self.__found_tag_with_text_func, 'keywords'),
        'cw<di<category__'  : (self.__found_tag_with_text_func, 'category'),
        'cw<di<doc-notes_'  : (self.__found_tag_with_text_func, 'doc-notes'),
        'cw<di<subject___'  : (self.__found_tag_with_text_func, 'subject'),
        'cw<di<linkbase__'  : (self.__found_tag_with_text_func, 'hyperlink-base'),

        'cw<di<create-tim'  : (self.__found_tag_with_tokens_func, 'creation-time'),
        'cw<di<revis-time'  : (self.__found_tag_with_tokens_func, 'revision-time'),
        'cw<di<print-time'  : (self.__found_tag_with_tokens_func, 'printing-time'),
        'cw<di<backuptime'  : (self.__found_tag_with_tokens_func, 'backup-time'),

        'cw<di<num-of-wor'  : (self.__single_field_func, 'number-of-words'),
        'cw<di<num-of-chr'  : (self.__single_field_func, 'number-of-characters'),
        'cw<di<numofchrws'  : (self.__single_field_func, 'number-of-characters-without-space'),
        'cw<di<num-of-pag'  : (self.__single_field_func, 'number-of-pages'),
        'cw<di<version___'  : (self.__single_field_func, 'version'),
        'cw<di<edit-time_'  : (self.__single_field_func, 'editing-time'),
        'cw<di<intern-ver'  : (self.__single_field_func, 'internal-version-number'),
        'cw<di<internalID'  : (self.__single_field_func, 'internal-id-number'),
        }
        self.__token_dict = {
        'year______'        : 'year',
        'month_____'        : 'month',
        'day_______'        : 'day',
        'minute____'        : 'minute',
        'second____'        : 'second',
        'revis-time'        : 'revision-time',
        'create-tim'        : 'creation-time',
        'edit-time_'        : 'editing-time',
        'print-time'        : 'printing-time',
        'backuptime'        : 'backup-time',
        'num-of-wor'        : 'number-of-words',
        'num-of-chr'        : 'number-of-characters',
        'numofchrws'        : 'number-of-characters-without-space',
        'num-of-pag'        : 'number-of-pages',
        'version___'        : 'version',
        'intern-ver'        : 'internal-version-number',
        'internalID'        : 'internal-id-number',
        }

    def __before_info_table_func(self, line):
        """
        Required:
            line -- the line to parse
        Returns:
            nothing
        Logic:
            Check for the beginning of the informatin table. When found, set
            the state to the information table. Always write the line.
        """
        if self.__token_info == 'mi<mk<doc-in-beg':
            self.__state = 'in_info_table'
        self.__write_obj.write(line)

    def __in_info_table_func(self, line):
        """
        Requires:
            line -- line to parse
        Returns:
            nothing.
        Logic:
            Check for the end of information. If not found, check if the
            token has a special value in the info table dictionay. If it
            does, execute that function.
            Otherwise, output the line to the file.
        """
        if self.__token_info == 'mi<mk<doc-in-end':
            self.__state = 'after_info_table'
        else:
            action, tag = self.__info_table_dict.get(self.__token_info, (None, None))
            if action:
                action(line, tag)
            else:
                self.__write_obj.write(line)

    def __found_tag_with_text_func(self, line, tag):
        """
        Requires:
            line -- line to parse
            tag --what kind of line
        Returns:
            nothing
        Logic:
            This function marks the beginning of informatin fields that have
            text that must be collected.  Set the type of information field
            with the tag option. Set the state to collecting text
        """
        self.__tag = tag
        self.__state = 'collect_text'

    def __collect_text_func(self, line):
        """
        Requires:
            line -- line to parse
        Returns:
            nothing
        Logic:
            If the end of the information field is found, write the text
            string to the file.
            Otherwise, if the line contains text, add it to the text string.
        """
        if self.__token_info == 'mi<mk<docinf-end':
            self.__state = 'in_info_table'
            # Don't print empty tags
            if len(self.rmspace.sub('',self.__text_string)):
                self.__write_obj.write(
                    'mi<tg<open______<%s\n'
                    'tx<nu<__________<%s\n'
                    'mi<tg<close_____<%s\n' % (self.__tag, self.__text_string, self.__tag)
                )
            self.__text_string = ''
        elif line[0:2] == 'tx':
            self.__text_string += line[17:-1]

    def __found_tag_with_tokens_func(self, line, tag):
        """
        Requires:
            line -- line to parse
            tag -- type of field
        Returns:
            nothing
        Logic:
            Some fields have a series of tokens (cw<di<year______<nu<2003)
            that must be parsed as attributes for the element.
            Set the state to collect tokesn, and set the text string to
            start an empty element with attributes.
        """
        self.__state = 'collect_tokens'
        self.__text_string = 'mi<tg<empty-att_<%s' % tag
        # mi<tg<empty-att_<page-definition<margin>33\n

    def __collect_tokens_func(self, line):
        """
        Requires:
            line -- line to parse
        Returns:
            nothing
        Logic:
            This function collects all the token information and adds it to
            the text string until the end of the field is found.
            First check of the end of the information field. If found, write
            the text string to the file.
            If not found, get the relevant information from the text string.
            This information cannot be directly added to the text string,
            because it exists in abbreviated form.  (num-of-wor)
            I want to check this information in a dictionary to convert it
            to a longer, readable form. If the key does not exist in the
            dictionary, print out an error message. Otherise add the value
            to the text string.
            (num-of-wor => number-of-words)
        """
        # cw<di<year______<nu<2003
        if self.__token_info == 'mi<mk<docinf-end':
            self.__state = 'in_info_table'
            self.__write_obj.write(
            '%s\n' % self.__text_string
            )
            self.__text_string = ''
        else:
            att = line[6:16]
            value = line[20:-1]
            att_changed = self.__token_dict.get(att)
            if att_changed is None:
                if self.__run_level > 3:
                    msg = 'No dictionary match for %s\n' % att
                    raise self.__bug_handler(msg)
            else:
                self.__text_string += '<%s>%s' % (att_changed, value)

    def __single_field_func(self, line, tag):
        value = line[20:-1]
        self.__write_obj.write(
        'mi<tg<empty-att_<%s<%s>%s\n' % (tag, tag, value)
        )

    def __after_info_table_func(self, line):
        """
        Requires:
            line --line to write to file
        Returns:
            nothing
        Logic:
            After the end of the information table, simple write the line to
            the file.
        """
        self.__write_obj.write(line)

    def fix_info(self):
        """
        Requires:
            nothing
        Returns:
            nothing (changes the original file)
        Logic:
            Read one line in at a time. Determine what action to take based on
            the state. If the state is before the information table, look for the
            beginning of the style table.
            If the state is in the information table, use other methods to
            parse the information
            style table, look for lines with style info, and substitute the
            number with the name of the style.  If the state if afer the
            information table, simply write the line to the output file.
        """
        self.__initiate_values()
        with open_for_read(self.__file) as read_obj:
            with open_for_write(self.__write_to) as self.__write_obj:
                for line in read_obj:
                    self.__token_info = line[:16]
                    action = self.__state_dict.get(self.__state)
                    if action is None:
                        sys.stderr.write('No matching state in module styles.py\n')
                        sys.stderr.write(self.__state + '\n')
                    action(line)
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "info.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
