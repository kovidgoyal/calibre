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

from calibre.ebooks.rtf2xml import copy
from calibre.ptempfile import better_mktemp
from . import open_for_read, open_for_write


class Paragraphs:
    """
    =================
    Purpose
    =================
    Write paragraph tags for a tokenized file. (This module won't be any use to use
    to you unless you use it as part of the other modules.)
    -------------
    Method
    -------------
    RTF does not tell you when a paragraph begins. It only tells you when the
    paragraph ends.
    In order to make paragraphs out of this limited info, the parser starts in the
    body of the documents and assumes it is not in a paragraph. It looks for clues
    to begin a paragraph. Text starts a paragraph; so does an inline field or
    list-text. If an end of paragraph marker (\\par) is found, then this indicates
    a blank paragraph.
    Once a paragraph is found, the state changes to 'paragraph.' In this state,
    clues are looked to for the end of a paragraph. The end of a paragraph marker
    (\\par) marks the end of a paragraph. So does the end of a footnote or heading;
    a paragraph definition; the end of a field-block; and the beginning of a
    section. (How about the end of a section or the end of a field-block?)
    """

    def __init__(self,
            in_file,
            bug_handler,
            copy=None,
            write_empty_para=1,
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
        self.__write_empty_para = write_empty_para
        self.__run_level = run_level
        self.__write_to = better_mktemp()

    def __initiate_values(self):
        """
        Initiate all values.
        """
        self.__state = 'before_body'
        self.__start_marker =  'mi<mk<para-start\n'  # outside para tags
        self.__start2_marker = 'mi<mk<par-start_\n'  # inside para tags
        self.__end2_marker =   'mi<mk<par-end___\n'  # inside para tags
        self.__end_marker =    'mi<mk<para-end__\n'  # outside para tags
        self.__state_dict = {
        'before_body'       : self.__before_body_func,
        'not_paragraph'     : self.__not_paragraph_func,
        'paragraph'         : self.__paragraph_func,
        }
        self.__paragraph_dict = {
        'cw<pf<par-end___'      : self.__close_para_func,   # end of paragraph
        'mi<mk<headi_-end'      : self.__close_para_func,   # end of header or footer
        # 'cw<pf<par-def___'      : self.__close_para_func,   # paragraph definition
        # 'mi<mk<fld-bk-end'      : self.__close_para_func,   # end of field-block
        'mi<mk<fldbk-end_'      : self.__close_para_func,   # end of field-block
        'mi<mk<body-close'      : self.__close_para_func,   # end of body
        'mi<mk<sect-close'      : self.__close_para_func,   # end of body
        'mi<mk<sect-start'      : self.__close_para_func,   # start of section
        'mi<mk<foot___clo'      : self.__close_para_func,   # end of footnote
        'cw<tb<cell______'      : self.__close_para_func,   # end of cell
        'mi<mk<par-in-fld'      : self.__close_para_func,   # start of block field
        'cw<pf<par-def___'      : self.__bogus_para__def_func,   # paragraph definition
        }
        self.__not_paragraph_dict = {
        'tx<nu<__________'      : self.__start_para_func,
        'tx<hx<__________'      : self.__start_para_func,
        'tx<ut<__________'      : self.__start_para_func,
        'tx<mc<__________'      : self.__start_para_func,
        'mi<mk<inline-fld'      : self.__start_para_func,
        'mi<mk<para-beg__'      : self.__start_para_func,
        'cw<pf<par-end___'      : self.__empty_para_func,
        'mi<mk<pict-start'      : self.__start_para_func,
        'cw<pf<page-break'      : self.__empty_pgbk_func,    # page break
        }

    def __before_body_func(self, line):
        """
        Required:
            line -- line to parse
        Returns:
            nothing
        Logic:
            This function handles all the lines before the start of the body.
            Once the body starts, the state is switched to 'not_paragraph'
        """
        if self.__token_info == 'mi<mk<body-open_':
            self.__state = 'not_paragraph'
        self.__write_obj.write(line)

    def __not_paragraph_func(self, line):
        """
        Required:
            line --line to parse
        Returns:
            nothing
        Logic:
            This function handles all lines that are outside of the paragraph.
            It looks for clues that start a paragraph, and when found,
            switches states and writes the start tags.
        """
        action = self.__not_paragraph_dict.get(self.__token_info)
        if action:
            action(line)
        self.__write_obj.write(line)

    def __paragraph_func(self, line):
        """
        Required:
            line --line to parse
        Returns:
            nothing
        Logic:
            This function handles all the lines that are in the paragraph. It
            looks for clues to the end of the paragraph. When a clue is found,
            it calls on another method to write the end of the tag and change
            the state.
        """
        action = self.__paragraph_dict.get(self.__token_info)
        if action:
            action(line)
        else:
            self.__write_obj.write(line)

    def __start_para_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing
        Logic:
            This function writes the beginning tags for a paragraph and
            changes the state to paragraph.
        """
        self.__write_obj.write(self.__start_marker)  # marker for later parsing
        self.__write_obj.write(
        'mi<tg<open______<para\n'
        )
        self.__write_obj.write(self.__start2_marker)
        self.__state = 'paragraph'

    def __empty_para_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing
        Logic:
            This function writes the empty tags for a paragraph.
            It does not do anything if self.__write_empty_para is 0.
        """
        if self.__write_empty_para:
            self.__write_obj.write(self.__start_marker)  # marker for later parsing
            self.__write_obj.write(
            'mi<tg<empty_____<para\n'
            )
            self.__write_obj.write(self.__end_marker)   # marker for later parsing

    def __empty_pgbk_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing
        Logic:
            This function writes the empty tags for a page break.
        """
        self.__write_obj.write(
        'mi<tg<empty_____<page-break\n'
        )

    def __close_para_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing
        Logic:
            This function writes the end tags for a paragraph and
            changes the state to not_paragraph.
        """
        self.__write_obj.write(self.__end2_marker)  # marker for later parser
        self.__write_obj.write(
        'mi<tg<close_____<para\n'
        )
        self.__write_obj.write(self.__end_marker)  # marker for later parser
        self.__write_obj.write(line)
        self.__state = 'not_paragraph'

    def __bogus_para__def_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing
        Logic:
            if a \\pard occurs in a paragraph, I want to ignore it. (I believe)
        """
        self.__write_obj.write('mi<mk<bogus-pard\n')

    def make_paragraphs(self):
        """
        Requires:
            nothing
        Returns:
            nothing (changes the original file)
        Logic:
            Read one line in at a time. Determine what action to take based on
            the state. If the state is before the body, look for the
            beginning of the body.
            When the body is found, change the state to 'not_paragraph'. The
            only other state is 'paragraph'.
        """
        self.__initiate_values()
        with open_for_read(self.__file) as read_obj:
            with open_for_write(self.__write_to) as self.__write_obj:
                for line in read_obj:
                    self.__token_info = line[:16]
                    action = self.__state_dict.get(self.__state)
                    if action is None:
                        try:
                            sys.stderr.write('no matching state in module paragraphs.py\n')
                            sys.stderr.write(self.__state + '\n')
                        except:
                            pass
                    action(line)
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "paragraphs.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
