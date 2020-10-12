
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
import sys, os
from calibre.ebooks.rtf2xml import field_strings, copy
from calibre.ptempfile import better_mktemp
from . import open_for_read, open_for_write


class FieldsLarge:
    r"""
=========================
Logic
=========================
Make tags for fields.
-Fields reflect text that Microsoft Word automatically generates.
-Each file contains (or should contain) an inner group called field instructions.
-Fields can be nested.
--------------
Logic
--------------
1. As soon as a field is found, make a new text string by appending an empty
text string to the field list. Collect all the lines in this string until the
field instructions are found.
2. Collect all the tokens and text in the field instructions. When the end of
the field instructions is found, process the string of text with the
field_strings module. Append the processed string to the field instructins
list.
3. Continue collecting tokens. Check for paragraphs or sections. If either is found, add to the paragraph or section list.
4. Continue collecting tokens and text either the beginning of a new field is found, or the end of this field is found.
5. If a new field is found, repeat steps 1-3.
6. If the end of the field is found, process the last text string of the field list.
7. If the field list is empty (after removing the last text string), there are
no more fields. Print out the final string. If the list contains other strings,
add the processed string to the last string in the field list.
============================
Examples
============================
    This line of RTF:
        {\field{\*\fldinst { CREATEDATE  \\* MERGEFORMAT }}{\fldrslt {
        \lang1024 1/11/03 10:34 PM}}}
    Becomes:
        <field type = "insert-time">
            10:34 PM
        </field>
    The simple field in the above example conatins no paragraph or sections breaks.
    This line of RTF:
        {{\field{\*\fldinst SYMBOL 97 \\f "Symbol" \\s 12}{\fldrslt\f3\fs24}}}
    Becomes:
        <para><inline font-size="18"><inline font-style="Symbol">&#x03A7;</inline></inline></para>
        The RTF in the example above should be represented as UTF-8 rather than a field.
    This RTF:
        {\field\fldedit{\*\fldinst { TOC \\o "1-3" }}{\fldrslt {\lang1024
        Heading one\tab }{\field{\*\fldinst {\lang1024  PAGEREF _Toc440880424
        \\h }{\lang1024 {\*\datafield
        {\lang1024 1}}}{\lang1024 \par }\pard\plain
        \s18\li240\widctlpar\tqr\tldot\tx8630\aspalpha\aspnum\faauto\adjustright\rin0\lin240\itap0
        \f4\lang1033\cgrid {\lang1024 Heading 2\tab }{\field{\*\fldinst
        {\lang1024  PAGEREF _Toc440880425 \\h }{\lang1024 {\*\datafield
        {\lang1024 1}}}{\lang1024 \par }\pard\plain
        \widctlpar\aspalpha\aspnum\faauto\adjustright\rin0\lin0\itap0
        \f4\lang1033\cgrid }}\pard\plain
        \widctlpar\aspalpha\aspnum\faauto\adjustright\rin0\lin0\itap0
        \f4\lang1033\cgrid {\fs28 \\u214\'85 \par }{\fs36 {\field{\*\fldinst
        SYMBOL 67 \\f "Symbol" \\s 18}{\fldrslt\f3\fs36}}}
    Becomes:
        <field-block type="table-of-contents">
        <paragraph-definition language="1033" nest-level="0"
        font-style="Times" name="toc 1" adjust-right="true"
        widow-control="true">
        <para><inline language="1024">Heading one&#x009;</inline><field
        type="reference-to-page" ref="_Toc440880424"><inline
        language="1024">1</inline></field></para>
        </paragraph-definition>
        <paragraph-definition language="1033" nest-level="0" left-indent="12"
        font-style="Times" name="toc 2" adjust-right="true"
        widow-control="true">
        <para><inline language="1024">Heading 2&#x009;</inline><field
        type="reference-to-page" ref="_Toc440880425"><inline
        language="1024">1</inline></field></para>
        </paragraph-definition>
        </field-block>
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
        self.__field_instruction_string = ''
        self.__marker = 'mi<mk<inline-fld\n'
        self.__state = 'before_body'
        self.__string_obj = field_strings.FieldStrings(run_level=self.__run_level,
                bug_handler=self.__bug_handler,)
        self.__state_dict = {
        'before_body'       : self.__before_body_func,
        'in_body'           : self.__in_body_func,
        'field'             : self.__in_field_func,
        'field_instruction' : self.__field_instruction_func,
        }
        self.__in_body_dict = {
        'cw<fd<field_____'  : self.__found_field_func,
        }
        self.__field_dict = {
        'cw<fd<field-inst'  :   self.__found_field_instruction_func,
        'cw<fd<field_____'  : self.__found_field_func,
        'cw<pf<par-end___'  : self.__par_in_field_func,
        'cw<sc<section___'  : self.__sec_in_field_func,
        }
        self.__field_count = []  # keep track of the brackets
        self.__field_instruction = []  # field instruction strings
        self.__symbol = 0   # wheter or not the field is really UTF-8
        # (these fields cannot be nested.)
        self.__field_instruction_string = ''  # string that collects field instruction
        self.__par_in_field = []  # paragraphs in field?
        self.__sec_in_field = []  # sections in field?
        self.__field_string = []  # list of field strings

    def __before_body_func(self, line):
        """
        Requried:
            line --line ro parse
        Returns:
            nothing (changes an instant and writes a line)
        Logic:
            Check for the beginninf of the body. If found, changed the state.
            Always write out the line.
        """
        if self.__token_info == 'mi<mk<body-open_':
            self.__state = 'in_body'
        self.__write_obj.write(line)

    def __in_body_func(self, line):
        """
        Required:
            line --line to parse
        Returns:
            nothing. (Writes a line to the output file, or performs other actions.)
        Logic:
            Check of the beginning of a field. Always output the line.
        """
        action = self.__in_body_dict.get(self.__token_info)
        if action:
            action(line)
        self.__write_obj.write(line)

    def __found_field_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing
        Logic:
            Set the values for parseing the field. Four lists have to have
            items appended to them.
        """
        self.__state = 'field'
        self.__cb_count = 0
        ob_count = self.__ob_count
        self.__field_string.append('')
        self.__field_count.append(ob_count)
        self.__sec_in_field.append(0)
        self.__par_in_field.append(0)

    def __in_field_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing.
        Logic:
            Check for the end of the field; a paragaph break; a section break;
            the beginning of another field; or the beginning of the field
            instruction.
        """
        if self.__cb_count == self.__field_count[-1]:
            self.__field_string[-1] += line
            self.__end_field_func()
        else:
            action = self.__field_dict.get(self.__token_info)
            if action:
                action(line)
            else:
                self.__field_string[-1] += line

    def __par_in_field_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing
        Logic:
            Write the line to the output file and set the last item in the
            paragraph in field list to true.
        """
        self.__field_string[-1] += line
        self.__par_in_field[-1] = 1

    def __sec_in_field_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing
        Logic:
            Write the line to the output file and set the last item in the
            section in field list to true.
        """
        self.__field_string[-1] += line
        self.__sec_in_field[-1] = 1

    def __found_field_instruction_func(self, line):
        """
        Requires:
            line -- line to parse
        Returns:
            nothing
        Change the state to field instruction. Set the open bracket count of
        the beginning of this field so  you know when it ends. Set the closed
        bracket count to 0 so you don't prematureley exit this state.
        """
        self.__state = 'field_instruction'
        self.__field_instruction_count = self.__ob_count
        self.__cb_count = 0

    def __field_instruction_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing
        Logic:
            Collect all the lines until the end of the field is reached.
            Process these lines with the module rtr.field_strings.
            Check if the field instruction is 'Symbol' (really UTF-8).
        """
        if self.__cb_count == self.__field_instruction_count:
            # The closing bracket should be written, since the opening bracket
            # was written
            self.__field_string[-1] += line
            my_list = self.__string_obj.process_string(
                self.__field_instruction_string, 'field_instruction')
            instruction = my_list[2]
            self.__field_instruction.append(instruction)
            if my_list[0] == 'Symbol':
                self.__symbol = 1
            self.__state = 'field'
            self.__field_instruction_string = ''
        else:
            self.__field_instruction_string += line

    def __end_field_func(self):
        """
        Requires:
            nothing
        Returns:
            Nothing
        Logic:
            Pop the last values in the instructions list, the fields list, the
            paragaph list, and the section list.
            If the field is a symbol, do not write the tags <field></field>,
            since this field is really just UTF-8.
            If the field contains paragraph or section breaks, it is a
            field-block rather than just a field.
            Write the paragraph or section markers for later parsing of the
            file.
            If the filed list contains more strings, add the latest
            (processed) string to the last string in the list. Otherwise,
            write the string to the output file.
        """
        last_bracket = self.__field_count.pop()
        instruction = self.__field_instruction.pop()
        inner_field_string = self.__field_string.pop()
        sec_in_field = self.__sec_in_field.pop()
        par_in_field = self.__par_in_field.pop()
        # add a closing bracket, since the closing bracket is not included in
        # the field string
        if self.__symbol:
            inner_field_string = '%scb<nu<clos-brack<%s\n' % \
            (instruction, last_bracket)
        elif sec_in_field or par_in_field:
            inner_field_string = \
            'mi<mk<fldbkstart\n'\
            'mi<tg<open-att__<field-block<type>%s\n%s'\
            'mi<mk<fldbk-end_\n' \
            'mi<tg<close_____<field-block\n'\
            'mi<mk<fld-bk-end\n' \
            % (instruction, inner_field_string)
        # write a marker to show an inline field for later parsing
        else:
            inner_field_string = \
            '%s' \
            'mi<tg<open-att__<field<type>%s\n%s'\
            'mi<tg<close_____<field\n'\
            % (self.__marker, instruction, inner_field_string)
        if sec_in_field:
            inner_field_string = 'mi<mk<sec-fd-beg\n' + inner_field_string + \
            'mi<mk<sec-fd-end\n'
        if par_in_field:
            inner_field_string = 'mi<mk<par-in-fld\n' + inner_field_string
        if len(self.__field_string) == 0:
            self.__write_field_string(inner_field_string)
        else:
            self.__field_string[-1] += inner_field_string
        self.__symbol = 0

    def __write_field_string(self, the_string):
        self.__state = 'in_body'
        self.__write_obj.write(the_string)

    def fix_fields(self):
        """
        Requires:
            nothing
        Returns:
            nothing (changes the original file)
        Logic:
            Read one line in at a time. Determine what action to take based on
            the state. If the state is before the body, look for the
            beginning of the body.
            If the state is body, send the line to the body method.
        """
        self.__initiate_values()
        read_obj = open_for_read(self.__file)
        self.__write_obj = open_for_write(self.__write_to)
        line_to_read = 1
        while line_to_read:
            line_to_read = read_obj.readline()
            line = line_to_read
            self.__token_info = line[:16]
            if self.__token_info == 'ob<nu<open-brack':
                self.__ob_count = line[-5:-1]
            if self.__token_info == 'cb<nu<clos-brack':
                self.__cb_count = line[-5:-1]
            action = self.__state_dict.get(self.__state)
            if action is None:
                sys.stderr.write('no no matching state in module styles.py\n')
                sys.stderr.write(self.__state + '\n')
            action(line)
        read_obj.close()
        self.__write_obj.close()
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "fields_large.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
