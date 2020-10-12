
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
import sys, re


class FieldStrings:
    """
    This module is given a string. It processes the field instruction string and
    returns a list of three values.
    """

    def __init__(self, bug_handler, run_level=1):
        """
        Requires:
            nothing
        Returns:
            nothing
        """
        self.__run_level = run_level
        self.__bug_handler = bug_handler
        self.__initiate_values()

    def __initiate_values(self):
        """
        Requires:
            nothing.
        Returns:
            nothing.
        Logic:
            initiate values for rest of class.
            self.__field_instruction_dict:
                The dictionary for all field names.
        """
        self.__field_instruction_dict = {
        # number type (arabic, etc.) and number format (\# " ")
        'EDITTIME'      :       (self.__num_type_and_format_func, 'editing-time'),
        'NUMCHARS'      :       (self.__num_type_and_format_func, 'number-of-characters-in-doc'),
        'NUMPAGES'      :       (self.__num_type_and_format_func, 'number-of-pages-in-doc'),
        'NUMWORDS'      :       (self.__num_type_and_format_func, 'number-of-words-in-doc'),
        'REVNUM'        :       (self.__num_type_and_format_func, 'revision-number'),
        'SECTIONPAGES'  :       (self.__num_type_and_format_func, 'num-of-pages-in-section'),
        'SECTION'       :       (self.__num_type_and_format_func, 'insert-section-number'),
        'QUOTE'         :       (self.__num_type_and_format_func, 'quote'),
        # number formatting (\# "")
        'PAGE'          :       (self.__default_inst_func, 'insert-page-number'),
        'page'          :       (self.__default_inst_func, 'insert-page-number'),
        # date format (\@ "")
        'CREATEDATE'    :       (self.__date_func, 'insert-date'),
        'PRINTDATE'     :       (self.__date_func, 'insert-date'),
        # PRINTDATE?
        'SAVEDATE'      :       (self.__date_func, 'last-saved'),
        'TIME'          :       (self.__date_func, 'insert-time'),
        # numbers?
        # these fields take four switches
        'AUTHOR'        :       (self.__simple_info_func, 'user-name'),
        'COMMENTS'      :       (self.__simple_info_func, 'comments'),
        'FILENAME'      :       (self.__simple_info_func, 'file-name'),
        'filename'      :       (self.__simple_info_func, 'file-name'),
        'KEYWORDS'      :       (self.__simple_info_func, 'keywords'),
        'LASTSAVEDBY'   :       (self.__simple_info_func, 'last-saved-by'),
        'SUBJECT'       :       (self.__simple_info_func, 'subject'),
        'TEMPLATE'      :       (self.__simple_info_func, 'based-on-template'),
        'TITLE'         :       (self.__simple_info_func, 'document-title'),
        'USERADDRESS'   :       (self.__simple_info_func, 'user-address'),
        'USERINITIALS'  :       (self.__simple_info_func, 'user-initials'),
        'USERNAME'      :       (self.__simple_info_func, 'user-name'),
        'EQ'            :       (self.__equation_func, 'equation'),
        'HYPERLINK'     :       (self.__hyperlink_func, 'hyperlink'),
        'INCLUDEPICTURE':       (self.__include_pict_func, 'include-picture'),
        'INCLUDETEXT'   :       (self.__include_text_func, 'include-text-from-file'),
        'INDEX'         :       (self.__index_func, 'index'),
        'NOTEREF'       :       (self.__note_ref_func, 'reference-to-note'),
        'PAGEREF'	: (self.__page_ref_func, 'reference-to-page'),
        'REF'           :       (self.__ref_func, 'reference'),
        'ref'           :       (self.__ref_func, 'reference'),
        'SEQ'           :       (self.__sequence_func, 'numbering-sequence'),
        'SYMBOL'        :       (self.__symbol_func, 'symbol'),
        'TA'            :       (self.__ta_func, 'anchor-for-table-of-authorities'),
        'TOA'           :       (self.__toc_table_func, 'table-of-authorities'),
        'TOC'           :       (self.__toc_table_func, 'table-of-contents'),
        # no switches
        'AUTONUMOUT'    :       (self.__no_switch_func, 'auto-num-out?'),
        'COMPARE'       :       (self.__no_switch_func, 'compare'),
        'DOCVARIABLE'   :       (self.__no_switch_func, 'document-variable'),
        'GOTOBUTTON'    :       (self.__no_switch_func, 'go-button'),
        'NEXT'          :       (self.__no_switch_func, 'next'),
        'NEXTIF'        :       (self.__no_switch_func, 'next-if'),
        'SKIPIF'        :       (self.__no_switch_func, 'skip-if'),
        'IF'            :       (self.__no_switch_func, 'if'),
        'MERGEFIELD'    :       (self.__no_switch_func, 'merge-field'),
        'MERGEREC'      :       (self.__no_switch_func, 'merge-record'),
        'MERGESEQ'      :       (self.__no_switch_func, 'merge-sequence'),
        'PLACEHOLDER'   :       (self.__no_switch_func, 'place-holder'),
        'PRIVATE'       :       (self.__no_switch_func, 'private'),
        'RD'            :       (self.__no_switch_func, 'referenced-document'),
        'SET'           :       (self.__no_switch_func, 'set'),
        # default instructions (haven't written a method for them
        'ADVANCE'       :       (self.__default_inst_func, 'advance'),
        'ASK'           :       (self.__default_inst_func, 'prompt-user'),
        'AUTONUMLGL'    :       (self.__default_inst_func, 'automatic-number'),
        'AUTONUM'       : (self.__default_inst_func, 'automatic-number'),
        'AUTOTEXTLIST'  :       (self.__default_inst_func, 'auto-list-text'),
        'AUTOTEXT'      :       (self.__default_inst_func, 'auto-text'),
        'BARCODE'       :       (self.__default_inst_func, 'barcode'),
        'CONTACT'       :       (self.__default_inst_func, 'contact'),
        'DATABASE'      :       (self.__default_inst_func, 'database'),
        'DATE'          :       (self.__default_inst_func, 'date'),
        'date'          :       (self.__default_inst_func, 'date'),
        'DOCPROPERTY'   :       (self.__default_inst_func, 'document-property'),
        'FILESIZE'      :       (self.__default_inst_func, 'file-size'),
        'FILLIN'        :       (self.__default_inst_func, 'fill-in'),
        'INFO'          :       (self.__default_inst_func, 'document-info'),
        'LINK'          :       (self.__default_inst_func, 'link'),
        'PA'            :       (self.__default_inst_func, 'page'),
        'PRINT'         :       (self.__default_inst_func, 'print'),
        'STYLEREF'      :       (self.__default_inst_func, 'style-reference'),
        'USERPROPERTY'  :       (self.__default_inst_func, 'user-property'),
        'FORMCHECKBOX'  :       (self.__default_inst_func, 'form-checkbox'),
        'FORMTEXT'      :       (self.__default_inst_func, 'form-text'),
        # buttons
        'MACROBUTTON'   :       (self.__default_inst_func, 'macro-button'),
        }
        self.__number_dict = {
            'Arabic'        :   'arabic',
            'alphabetic'    :   'alphabetic',
            'ALPHABETIC'    :   'capital-alphabetic',
            'roman'         :   'roman',
            'ROMAN'         :   'capital-roman',
            'Ordinal'       :   'ordinal',
            'CardText'      :   'cardinal-text',
            'OrdText'       :   'ordinal-text',
            'Hex'           :   'hexidecimal',
            'DollarText'    :   'dollar-text',
            'Upper'         :   'upper-case',
            'Lower'         :   'lower-case',
            'FirstCap'      :   'first-cap',
            'Caps'          :   'caps',
        }
        self.__text_format_dict = {
            'Upper'         :   'upper',
            'Lower'         :   'lower',
            'FirstCap'      :   'first-cap',
            'Caps'          :   'caps',
        }
        self.__symbol_num_exp = re.compile(r'SYMBOL (.*?) ')
        self.__symbol_font_exp = re.compile(r'\\f "(.*?)"')
        self.__symbol_size_exp = re.compile(r'\\s (\d+)')
        # self.__toc_figure_exp = re.compile(r'\\c "Figure"')
        # \\@ "dddd, MMMM d, yyyy"
        self.__date_exp = re.compile(r'\\@\s{1,}"(.*?)"')
        self.__num_type_exp = re.compile(
            r'\\\*\s{1,}(Arabic|alphabetic|ALPHABETIC|roman|ROMAN|Ordinal|CardText|OrdText|Hex|DollarText|Upper|Lower|FirstCap|Caps)')
        self.__format_text_exp = re.compile(r'\\\*\s{1,}(Upper|Lower|FirstCap|Caps)')
        self.__merge_format_exp = re.compile(r'\\\*\s{1,}MERGEFORMAT')
        self.__ta_short_field_exp = re.compile(r'\\s\s{1,}"(.*?)"')
        self.__ta_long_field_exp = re.compile(r'\\l\s{1,}"(.*?)"')
        self.__ta_category_exp = re.compile(r'\\c\s{1,}(\d+)')
        # indices
        self.__index_insert_blank_line_exp = re.compile(r'\\h\s{1,}""')
        self.__index_insert_letter_exp = re.compile(r'\\h\s{1,}"()"')
        self.__index_columns_exp = re.compile(r'\\c\s{1,}"(.*?)"')
        self.__bookmark_exp = re.compile(r'\\b\s{1,}(.*?)\s')
        self.__d_separator = re.compile(r'\\d\s{1,}(.*?)\s')
        self.__e_separator = re.compile(r'\\e\s{1,}(.*?)\s')
        self.__l_separator = re.compile(r'\\l\s{1,}(.*?)\s')
        self.__p_separator = re.compile(r'\\p\s{1,}(.*?)\s')
        self.__index_sequence = re.compile(r'\\s\s{1,}(.*?)\s')
        self.__index_entry_typ_exp = re.compile(r'\\f\s{1,}"(.*?)"')
        self.__quote_exp = re.compile(r'"(.*?)"')
        self.__filter_switch = re.compile(r'\\c\s{1,}(.*?)\s')
        self.__link_switch = re.compile(r'\\l\s{1,}(.*?)\s')

    def process_string(self, my_string, type):
        """
        Requires:
            my_string --the string to parse.
            type -- the type of string.
        Returns:
            Returns a string for a field instrution attribute.
        Logic:
            This handles all "large" fields, which means everything except
            toc entries, index entries, and bookmarks
            Split the string by spaces, and get the first item in the
            resulting list. This item is the field's type. Check for the
            action in the field instructions dictionary for further parsing.
            If no action is found, print out an error message.
        """
        changed_string = ''
        lines = my_string.split('\n')
        for line in lines:
            if line[0:2] == 'tx':
                changed_string += line[17:]
        fields = changed_string.split()
        field_name = fields[0]
        action, name = self.__field_instruction_dict.get(field_name, (None, None))
        match_obj = re.search(self.__merge_format_exp, changed_string)
        if match_obj and name:
            name += '<update>dynamic'
        elif name:
            name += '<update>static'
        else:
            pass
            # no name--not in list above
        if action:
            the_list = action(field_name, name, changed_string)
        else:
            # change -1 to 0--for now, I want users to report bugs
            msg = 'no key for "%s" "%s"\n' % (field_name, changed_string)
            sys.stderr.write(msg)
            if self.__run_level > 3:
                msg = 'no key for "%s" "%s"\n' % (field_name, changed_string)
                raise self.__bug_handler(msg)
            the_list = self.__fall_back_func(field_name, line)
            return the_list
        return the_list

    def __default_inst_func(self, field_name, name, line):
        """
        Requires:
            field_name -- the first word in the string
            name -- the changed name according to the dictionary
            line -- the string to be parsed
        Returns:
            The name of the field.
        Logic:
            I only need the changed name for the field.
        """
        return [None, None, name]

    def __fall_back_func(self, field_name,  line):
        """
        Requires:
            field_name -- the first word in the string
            name -- the changed name according to the dictionary
            line -- the string to be parsed
        Returns:
            The name of the field.
        Logic:
            Used for fields not found in dict
        """
        the_string = field_name
        the_string += '<update>none'
        return [None, None, the_string]

    def __equation_func(self, field_name, name, line):
        """
        Requried:
            field_name -- the first word in the string
            name --the changed name according to the dictionary
            line -- the string to be parse
        Retuns:
            The name of the field
        Logic:
        """
        return [None, None, name]

    def __no_switch_func(self, field_name, name, line):
        """
        Required:
            field_name --the first
            field_name -- the first word in the string
            name --the changed name according to the dictionary
            line -- the string to be parse
        Retuns:
            The name of the field
        Logic:
        """
        return [None, None, name]

    def __num_type_and_format_func(self, field_name, name, line):
        """
        Required:
            field_name -- the first word in the string
            name --the changed name according to the dictionary
            line -- the string to be parse
        Returns:
            list of None, None, and part of a tag
        Logic:
            parse num_type
            parse num_format
        """
        the_string = name
        num_format = self.__parse_num_format(line)
        if num_format:
            the_string += '<number-format>%s' % num_format
        num_type = self.__parse_num_type(line)
        if num_type:
            the_string += '<number-type>%s' % num_type
        # Only QUOTE takes a (mandatory?) argument
        if field_name == 'QUOTE':
            match_group = re.search(r'QUOTE\s{1,}"(.*?)"', line)
            if match_group:
                arg = match_group.group(1)
                the_string += '<argument>%s' % arg
        return [None, None, the_string]

    def __num_format_func(self, field_name, name, line):
        """
        Required:
            field_name -- the first word in the string
            name --the changed name according to the dictionary
            line -- the string to be parse
        Returns:
            list of None, None, and part of a tag
        Logic:
        """
        the_string = name
        num_format = self.__parse_num_format(line)
        if num_format:
            the_string += '<number-format>%s' % num_format
        return [None, None, the_string]

    def __parse_num_format(self, the_string):
        """
        Required:
            the_string -- the string to parse
        Returns:
            a string if the_string contains number formatting information
            None, otherwise
        Logic:
        """
        match_group = re.search(self.__date_exp, the_string)
        if match_group:
            return match_group(1)

    def __parse_num_type(self, the_string):
        """
        Required:
            the_string -- the string to parse
        Returns:
            a string if the_string contains number type information
            None, otherwise
        Logic:
            the_string might look like:
            USERNAME \\* Arabic \\* MERGEFORMAT
            Get the \\* Upper part. Use a dictionary to convert the "Arabic" to
            a more-readable word for the value of the key "number-type".
            (<field number-type = "Arabic">
        """
        match_group = re.search(self.__num_type_exp, the_string)
        if match_group:
            name =  match_group.group(1)
            changed_name =   self.__number_dict.get(name)
            if changed_name:
                return changed_name
            else:
                sys.stderr.write('module is fields_string\n')
                sys.stderr.write('method is __parse_num_type\n')
                sys.stderr.write('no dictionary entry for %s\n' % name)

    def __date_func(self, field_name, name, line):
        """
        Required:
            field_name --the fist
            field_name -- the first word in the string
            name --the changed name according to the dictionary
            line -- the string to be parse
        Returns:
            list of None, None, and part of a tag
        Logic:
        """
        the_string = name
        match_group = re.search(self.__date_exp, line)
        if match_group:
            the_string += '<date-format>%s' % match_group.group(1)
        return [None, None, the_string]

    def __simple_info_func(self, field_name, name, line):
        """
        Requried:
            field_name -- the first word in the string
            name --the changed name according to the dictionary
            line -- the string to be parse
        Retuns:
            The name of the field
        Logic:
            These fields can only have the following switches:
                1. Upper
                2. Lower
                3. FirstCap
                4. Caps
        """
        the_string = name
        match_group = re.search(self.__format_text_exp, line)
        if match_group:
            name =  match_group.group(1)
            changed_name =   self.__text_format_dict.get(name)
            if changed_name:
                the_string += '<format>%s' % changed_name
            else:
                sys.stderr.write('module is fields_string\n')
                sys.stderr.write('method is __parse_num_type\n')
                sys.stderr.write('no dictionary entry for %s\n' % name)
        return [None, None, the_string]

    def __hyperlink_func(self, field_name, name, line):
        """
        Requried:
            field_name -- the first word in the string
            name --the changed name according to the dictionary
            line -- the string to be parse
        Retuns:
            The name of the field
        """
        self.__link_switch = re.compile(r'\\l\s{1,}"{0,1}(.*?)"{0,1}\s')
        the_string = name
        match_group = re.search(self.__link_switch, line)
        if match_group:
            link = match_group.group(1)
            link = link.replace('"', "&quot;")
            the_string += '<link>%s' % link
        # \l "txt" "link"
        # want "file name" so must get rid of \c "txt"
        line = re.sub(self.__link_switch, '', line)
        match_group = re.search(self.__quote_exp, line)
        if match_group:
            arg = match_group.group(1)
            the_string += '<argument>%s' % arg
        else:
            pass
        index = line.find('\\m')
        if index > -1:
            the_string += '<html2-image-map>true'
        index = line.find('\\n')
        if index > -1:
            the_string += '<new-window>true'
        index = line.find('\\h')
        if index > -1:
            the_string += '<no-history>true'
        return [None, None, the_string]

    def __include_text_func(self, field_name, name, line):
        """
        Requried:
            field_name -- the first word in the string
            name --the changed name according to the dictionary
            line -- the string to be parse
        Retuns:
            The name of the field
        Logic:
        """
        the_string = name
        match_group = re.search(self.__format_text_exp, line)
        if match_group:
            name =  match_group.group(1)
            changed_name =   self.__text_format_dict.get(name)
            if changed_name:
                the_string += '<format>%s' % changed_name
            else:
                sys.stderr.write('module is fields_string\n')
                sys.stderr.write('method is __parse_num_type\n')
                sys.stderr.write('no dictionary entry for %s\n' % name)
        match_group = re.search(self.__filter_switch, line)
        if match_group:
            arg = match_group.group(1)
            the_string += '<filter>%s' % arg
        # \c "txt" "file name"
        # want "file name" so must get rid of \c "txt"
        line = re.sub(self.__filter_switch, '', line)
        match_group = re.search(self.__quote_exp, line)
        if match_group:
            arg = match_group.group(1)
            arg = arg.replace('"', "&quot;")
            the_string += '<argument>%s' % arg
        else:
            sys.stderr.write('Module is field_strings\n')
            sys.stderr.write('method is include_text_func\n')
            sys.stderr.write('no argument for include text\n')
        index = line.find('\\!')
        if index > -1:
            the_string += '<no-field-update>true'
        return [None, None, the_string]

    def __include_pict_func(self, field_name, name, line):
        """
        Requried:
            field_name -- the first word in the string
            name --the changed name according to the dictionary
            line -- the string to be parse
        Retuns:
            The name of the field
        Logic:
        """
        the_string = name
        match_group = re.search(self.__filter_switch, line)
        if match_group:
            arg = match_group.group(1)
            arg = arg.replace('"', "&quot;")
            the_string += '<filter>%s' % arg
        # \c "txt" "file name"
        # want "file name" so must get rid of \c "txt"
        line = re.sub(self.__filter_switch, '', line)
        match_group = re.search(self.__quote_exp, line)
        if match_group:
            arg = match_group.group(1)
            the_string += '<argument>%s' % arg
        else:
            sys.stderr.write('Module is field_strings\n')
            sys.stderr.write('method is include_pict_func\n')
            sys.stderr.write('no argument for include pict\n')
        index = line.find('\\d')
        if index > -1:
            the_string += '<external>true'
        return [None, None, the_string]

    def __ref_func(self, field_name, name, line):
        """
        Requires:
            field_name -- the first word in the string
            name -- the changed name according to the dictionary
            line -- the string to be parsed
        Returns:
            The name of the field.
        Logic:
            A page reference field looks like this:
                PAGEREF _Toc440880424 \\h
            I want to extract the second line of info, which is used as an
            achor in the resulting XML file.
        """
        the_string = name
        match_group = re.search(self.__format_text_exp, line)
        if match_group:
            name =  match_group.group(1)
            changed_name =   self.__text_format_dict.get(name)
            if changed_name:
                the_string += '<format>%s' % changed_name
            else:
                sys.stderr.write('module is fields_string\n')
                sys.stderr.write('method is __parse_num_type\n')
                sys.stderr.write('no dictionary entry for %s\n' % name)
        line = re.sub(self.__merge_format_exp, '', line)
        words = line.split()
        words = words[1:]  # get rid of field name
        for word in words:
            if word[0:1] != '\\':
                the_string += '<bookmark>%s' % word
        index = line.find('\\f')
        if index > -1:
            the_string += '<include-note-number>true'
        index = line.find('\\h')
        if index > -1:
            the_string += '<hyperlink>true'
        index = line.find('\\n')
        if index > -1:
            the_string += '<insert-number>true'
        index = line.find('\\r')
        if index > -1:
            the_string += '<insert-number-relative>true'
        index = line.find('\\p')
        if index > -1:
            the_string += '<paragraph-relative-position>true'
        index = line.find('\\t')
        if index > -1:
            the_string += '<suppress-non-delimeter>true'
        index = line.find('\\w')
        if index > -1:
            the_string += '<insert-number-full>true'
        return [None, None, the_string]

    def __toc_table_func(self, field_name, name, line):
        """
        Requires:
            field_name -- the name of the first word in the string
            name --the changed name, according to the dictionary.
            line --the string to be parsed.
        Returns:
            A string for a TOC table field.
        Logic:
            If the string contains Figure, it is a table of figures.
            Otherwise, it is a plain old table of contents.
        """
        the_string = name
        index = line.find('\\c "Figure"')
        if index > -1:
            the_string = the_string.replace('table-of-contents', 'table-of-figures')
        # don't really need the first value in this list, I don't believe
        return [name, None, the_string]

    def __sequence_func(self, field_name, name, line):
        """
        Requires:
            field_name --the name of the first word in the string.
            name --the changed name according to the dictionary.
            line -- the string to parse.
        Returns:
            A string with a value for the type and label attributes
        Logic:
            The type of sequence--whether figure, graph, my-name, or
            whatever--is represented by the second word in the string. Extract
            and return.
            SEQ Figure \\* ARABIC
        """
        fields = line.split()
        label = fields[1]
        my_string = '%s<label>%s' % (name, label)
        return [None, None, my_string]

    def __ta_func(self, field_name, name, line):
        """
        Requires:
            field_name --the name of the first word in the string.
            name --the changed name according to the dictionary.
            line -- the string to parse.
        Returns:
            A string with a value for the type and label attributes
        Logic:
        """
        the_string = name
        match_group = re.search(self.__ta_short_field_exp, line)
        if match_group:
            short_name =  match_group.group(1)
            the_string += '<short-field>%s' % short_name
        match_group = re.search(self.__ta_long_field_exp, line)
        if match_group:
            long_name =  match_group.group(1)
            the_string += '<long-field>%s' % long_name
        match_group = re.search(self.__ta_category_exp, line)
        if match_group:
            category =  match_group.group(1)
            the_string += '<category>%s' % category
        index = line.find('\\b')
        if index > -1:
            the_string += '<bold>true'
        index = line.find('\\i')
        if index > -1:
            the_string += '<italics>true'
        return [None, None, the_string]

    def __index_func(self, field_name, name, line):
        """
        Requires:
            field_name --the name of the first word in the string.
            name --the changed name according to the dictionary.
            line -- the string to parse.
        Returns:
            A string with a value for the type and label attributes
        Logic:
        """
        # self.__index_insert_blank_line_exp = re.compile(r'\\h\s{1,}""')
        # self.__index_insert_letter_exp = re.compile(r'\\h\s{1,}(".*?")')
        the_string = name
        match_group = re.search(self.__index_insert_blank_line_exp, line)
        if match_group:
            the_string += '<insert-blank-line>true'
        else:
            match_group = re.search(self.__index_insert_letter_exp, line)
            if match_group:
                insert_letter = match_group.group(1)
                the_string += '<insert-letter>%s' % insert_letter
        match_group = re.search(self.__index_columns_exp, line)
        if match_group:
            columns = match_group.group(1)
            the_string += '<number-of-columns>%s' % columns
        # self.__bookmark_exp = re.compile(r'\\b\s{1,}(.*?)\s')
        match_group = re.search(self.__bookmark_exp, line)
        if match_group:
            bookmark = match_group.group(1)
            the_string += '<use-bookmark>%s' % bookmark
        match_group = re.search(self.__d_separator, line)
        if match_group:
            separator = match_group.group(1)
            separator = separator.replace('"', '&quot;')
            the_string += '<sequence-separator>%s' % separator
        # self.__e_separator = re.compile(r'\\e\s{1,}(.*?)\s')
        match_group = re.search(self.__e_separator, line)
        if match_group:
            separator = match_group.group(1)
            separator = separator.replace('"', '&quot;')
            the_string += '<page-separator>%s' % separator
        # self.__index_sequence = re.compile(r'\\s\s{1,}(.*?)\s')
        match_group = re.search(self.__index_sequence, line)
        if match_group:
            sequence = match_group.group(1)
            separator = separator.replace('"', '&quot;')
            the_string += '<use-sequence>%s' % sequence
        # self.__index_entry_typ_exp = re.compile(r'\\f\s{1,}"(.*?)"')
        match_group = re.search(self.__index_entry_typ_exp, line)
        if match_group:
            entry_type = match_group.group(1)
            the_string += '<entry-type>%s' % entry_type
        # self.__p_separator = re.compile(r'\\p\s{1,}(.*?)\s')
        match_group = re.search(self.__p_separator, line)
        if match_group:
            limit = match_group.group(1)
            the_string += '<limit-to-letters>%s' % limit
        match_group = re.search(self.__l_separator, line)
        if match_group:
            separator = match_group.group(1)
            separator = separator.replace('"', '&quot;')
            the_string += '<multi-page-separator>%s' % separator
        index = line.find('\\a')
        if index > -1:
            the_string += '<accented>true'
        index = line.find('\\r')
        if index > -1:
            the_string += '<sub-entry-on-same-line>true'
        index = line.find('\\t')
        if index > -1:
            the_string += '<enable-yomi-text>true'
        return [None, None, the_string]

    def __page_ref_func(self, field_name, name, line):
        """
        Requires:
            field_name --first name in the string.
            name -- the changed name according to the dictionary.
            line -- the string to parse.
        Returns:
            A string .
        Logic:
        """
        the_string = name
        num_format = self.__parse_num_format(line)
        if num_format:
            the_string += '<number-format>%s' % num_format
        num_type = self.__parse_num_type(line)
        if num_type:
            the_string += '<number-type>%s' % num_type
        line = re.sub(self.__merge_format_exp, '', line)
        words = line.split()
        words = words[1:]  # get rid of field name
        for word in words:
            if word[0:1] != '\\':
                the_string += '<bookmark>%s' % word
        index = line.find('\\h')
        if index > -1:
            the_string += '<hyperlink>true'
        index = line.find('\\p')
        if index > -1:
            the_string += '<paragraph-relative-position>true'
        return [None, None, the_string]

    def __note_ref_func(self, field_name, name, line):
        """
        Requires:
            field_name --first name in the string.
            name -- the changed name according to the dictionary.
            line -- the string to parse.
        Returns:
            A string .
        Logic:
        """
        the_string = name
        line = re.sub(self.__merge_format_exp, '', line)
        words = line.split()
        words = words[1:]  # get rid of field name
        for word in words:
            if word[0:1] != '\\':
                the_string += '<bookmark>%s' % word
        index = line.find('\\h')
        if index > -1:
            the_string += '<hyperlink>true'
        index = line.find('\\p')
        if index > -1:
            the_string += '<paragraph-relative-position>true'
        index = line.find('\\f')
        if index > -1:
            the_string += '<include-note-number>true'
        return [None, None, the_string]

    def __symbol_func(self, field_name, name, line):
        """
        Requires:
            field_name --first name in the string.
            name -- the changed name according to the dictionary.
            line -- the string to parse.
        Returns:
            A string containing font size, font style, and a hexidecimal value.
        Logic:
            The SYMBOL field is one of Microsoft's many quirky ways of
            entering text. The string that results from this method looks like
            this:
                SYMBOL 97 \\f "Symbol" \\s 12
            The first word merely tells us that we have encountered a SYMBOL
            field.
            The next value is the Microsoft decimal value. Change this to
            hexidecimal.
            The pattern '\\f "some font' tells us the font.
            The pattern '\\s some size'  tells us the font size.
            Extract all of this information. Store this information in a
            string, and make this string the last item in a list. The first
            item in the list is the simple word 'symbol', which tells me that
            I don't really have  field, but UTF-8 data.
        """
        num = ''
        font = ''
        font_size = ''
        changed_line = ''
        search_obj = re.search(self.__symbol_num_exp, line)
        if search_obj:
            num = search_obj.group(1)
            num = int(num)
            num = '%X' % num
        search_obj = re.search(self.__symbol_font_exp, line)
        if search_obj:
            font = search_obj.group(1)
            changed_line += 'cw<ci<font-style<nu<%s\n' % font
        search_obj = re.search(self.__symbol_size_exp, line)
        if search_obj:
            font_size = search_obj.group(1)
            font_size = int(font_size)
            font_size = '%.2f' % font_size
            changed_line += 'cw<ci<font-size_<nu<%s\n' % font_size
        changed_line += 'tx<hx<__________<\'%s\n' % num
        return ['Symbol', None, changed_line]
