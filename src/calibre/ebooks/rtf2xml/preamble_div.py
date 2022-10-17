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
from calibre.ebooks.rtf2xml import copy, override_table, list_table
from calibre.ptempfile import better_mktemp
from . import open_for_read, open_for_write


class PreambleDiv:
    """
    Break the preamble into divisions.
    """

    def __init__(self, in_file,
            bug_handler,
            copy=None,
            no_namespace=None,
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
        self.__no_namespace = no_namespace
        self.__write_to = better_mktemp()
        self.__run_level = run_level

    def __initiate_values(self):
        """
        Set values, including those for the dictionary.
        """
        self.__all_lists = {}
        self.__page = {
        'margin-top'    : 72,
        'margin-bottom' : 72,
        'margin-left'   : 90,
        'margin-right'  : 90,
        'gutter'        : 0,
        }
        self.__cb_count = ''
        self.__ob_count = ''
        self.__state = 'preamble'
        self.__rtf_final = ''
        self.__close_group_count = ''
        self.__found_font_table = 0
        self.__list_table_final = ''
        self.__override_table_final = ''
        self.__revision_table_final = ''
        self.__doc_info_table_final = ''
        self.__state_dict = {
        'default'           :   self.__default_func,
        'rtf_header'        :   self.__rtf_head_func,
        'preamble'          :   self.__preamble_func,
        'font_table'        :   self.__font_table_func,
        'color_table'       :   self.__color_table_func,
        'style_sheet'       :   self.__style_sheet_func,
        'list_table'        :   self.__list_table_func,
        'override_table'    :   self.__override_table_func,
        'revision_table'    :   self.__revision_table_func,
        'doc_info'          :   self.__doc_info_func,
        'body'              :   self.__body_func,
        'ignore'            :   self.__ignore_func,
        'cw<ri<rtf_______'  :   self.__found_rtf_head_func,
        'cw<pf<par-def___'  :   self.__para_def_func,
        'tx<nu<__________'  :   self.__text_func,
        'cw<tb<row-def___'  :   self.__row_def_func,
        'cw<sc<section___'  :   self.__new_section_func,
        'cw<sc<sect-defin'  :   self.__new_section_func,
        'cw<it<font-table'  :   self.__found_font_table_func,
        'cw<it<colr-table'  :   self.__found_color_table_func,
        'cw<ss<style-shet'  :   self.__found_style_sheet_func,
        'cw<it<listtable_'  :   self.__found_list_table_func,
        'cw<it<lovr-table'  :   self.__found_override_table_func,
        'cw<it<revi-table'  :   self.__found_revision_table_func,
        'cw<di<doc-info__'  :   self.__found_doc_info_func,
        'cw<pa<margin-lef'  :   self.__margin_func,
        'cw<pa<margin-rig'  :   self.__margin_func,
        'cw<pa<margin-top'  :   self.__margin_func,
        'cw<pa<margin-bot'  :   self.__margin_func,
        'cw<pa<gutter____'  :   self.__margin_func,
        'cw<pa<paper-widt'  :   self.__margin_func,
        'cw<pa<paper-hght'  :   self.__margin_func,
        # 'cw<tb<columns___'  :   self.__section_func,
        }
        self.__margin_dict = {
        'margin-lef'        :   'margin-left',
        'margin-rig'        :   'margin-right',
        'margin-top'        :   'margin-top',
        'margin-bot'        :   'margin-bottom',
        'gutter____'        :   'gutter',
        'paper-widt'        :   'paper-width',
        'paper-hght'        :   'paper-height',
        }
        self.__translate_sec = {
        'columns___'        :   'column',
        }
        self.__section = {}
        # self.__write_obj.write(self.__color_table_final)
        self.__color_table_final = ''
        self.__style_sheet_final = ''
        self.__individual_font = 0
        self.__old_font = 0
        self.__ob_group = 0  # depth of group
        self.__font_table_final = 0
        self.__list_table_obj = list_table.ListTable(
                run_level=self.__run_level,
                bug_handler=self.__bug_handler,
                )

    def __ignore_func(self, line):
        """
        Ignore all  lines, until the bracket is found that marks the end of
        the group.
        """
        if self.__ignore_num == self.__cb_count:
            self.__state = self.__previous_state

    def __found_rtf_head_func(self, line):
        self.__state = 'rtf_header'

    def __rtf_head_func(self, line):
        if self.__ob_count == '0002':
            self.__rtf_final = (
            'mi<mk<rtfhed-beg\n' +
            self.__rtf_final +
            'mi<mk<rtfhed-end\n'
            )
            self.__state = 'preamble'
        elif self.__token_info == 'tx<nu<__________' or \
            self.__token_info == 'cw<pf<par-def___':
            self.__state = 'body'
            self.__rtf_final = (
            'mi<mk<rtfhed-beg\n' +
            self.__rtf_final +
            'mi<mk<rtfhed-end\n'
            )
            self.__make_default_font_table()
            self.__write_preamble()
            self.__write_obj.write(line)
        else:
            self.__rtf_final = self.__rtf_final + line

    def __make_default_font_table(self):
        """
        If not font table is found, need to write one out.
        """
        self.__font_table_final = 'mi<tg<open______<font-table\n'
        self.__font_table_final += 'mi<mk<fonttb-beg\n'
        self.__font_table_final += 'mi<mk<fontit-beg\n'
        self.__font_table_final += 'cw<ci<font-style<nu<0\n'
        self.__font_table_final += 'tx<nu<__________<Times;\n'
        self.__font_table_final += 'mi<mk<fontit-end\n'
        self.__font_table_final +=  'mi<mk<fonttb-end\n'
        self.__font_table_final += 'mi<tg<close_____<font-table\n'

    def __make_default_color_table(self):
        """
        If no color table is found, write a string for a default one
        """
        self.__color_table_final = 'mi<tg<open______<color-table\n'
        self.__color_table_final += 'mi<mk<clrtbl-beg\n'
        self.__color_table_final += 'cw<ci<red_______<nu<00\n'
        self.__color_table_final += 'cw<ci<green_____<nu<00\n'
        self.__color_table_final += 'cw<ci<blue______<en<00\n'
        self.__color_table_final += 'mi<mk<clrtbl-end\n'
        self.__color_table_final += 'mi<tg<close_____<color-table\n'

    def __make_default_style_table(self):
        """
        If not font table is found, make a string for a default one
        """
        """
        self.__style_sheet_final = 'mi<tg<open______<style-table\n'
        self.__style_sheet_final +=
        self.__style_sheet_final +=
        self.__style_sheet_final +=
        self.__style_sheet_final +=
        self.__style_sheet_final +=
        self.__style_sheet_final += 'mi<tg<close_____<style-table\n'
        """
        self.__style_sheet_final = """mi<tg<open______<style-table
mi<mk<styles-beg
mi<mk<stylei-beg
cw<ci<font-style<nu<0
tx<nu<__________<Normal;
mi<mk<stylei-end
mi<mk<stylei-beg
cw<ss<char-style<nu<0
tx<nu<__________<Default Paragraph Font;
mi<mk<stylei-end
mi<mk<styles-end
mi<tg<close_____<style-table
"""

    def __found_font_table_func(self, line):
        if self.__found_font_table:
            self.__state = 'ignore'
        else:
            self.__state = 'font_table'
            self.__font_table_final = ''
        self.__close_group_count = self.__ob_count
        self.__cb_count = 0
        self.__found_font_table = 1

    def __font_table_func(self, line):
        """
        Keep adding to the self.__individual_font string until end of group
        found. If a bracket is found, check that it is only one bracket deep.
        If it is, then set the marker for an individual font. If it is not,
        then ignore all data in this group.
cw<ci<font-style<nu<0
        """
        if self.__cb_count == self.__close_group_count:
            self.__state = 'preamble'
            self.__font_table_final = 'mi<tg<open______<font-table\n' + \
            'mi<mk<fonttb-beg\n' + self.__font_table_final
            self.__font_table_final += \
            'mi<mk<fonttb-end\n' + 'mi<tg<close_____<font-table\n'
        elif self.__token_info == 'ob<nu<open-brack':
            if int(self.__ob_count) == int(self.__close_group_count) + 1:
                self.__font_table_final +=  \
                'mi<mk<fontit-beg\n'
                self.__individual_font = 1
            else:
                # ignore
                self.__previous_state = 'font_table'
                self.__state = 'ignore'
                self.__ignore_num = self.__ob_count
        elif self.__token_info == 'cb<nu<clos-brack':
            if int(self.__cb_count) == int(self.__close_group_count) + 1:
                self.__individual_font = 0
                self.__font_table_final +=  \
                'mi<mk<fontit-end\n'
        elif self.__individual_font:
            if self.__old_font and self.__token_info == 'tx<nu<__________':
                if ';' in line:
                    self.__font_table_final +=  line
                    self.__font_table_final +=   'mi<mk<fontit-end\n'
                    self.__individual_font = 0
            else:
                self.__font_table_final +=  line
        elif self.__token_info == 'cw<ci<font-style':
            self.__old_font = 1
            self.__individual_font = 1
            self.__font_table_final +=   'mi<mk<fontit-beg\n'
            self.__font_table_final +=  line

    def __old_font_func(self, line):
        """
        Required:
            line --line to parse
        Returns:
            nothing
        Logic:
            used for older forms of RTF:
            \f3\fswiss\fcharset77 Helvetica-Oblique;\f4\fnil\fcharset77 Geneva;}
            Note how each font is not divided by a bracket
        """

    def __found_color_table_func(self, line):
        """
        all functions that start with __found operate the same. They set the
        state, initiate a string, determine the self.__close_group_count, and
        set self.__cb_count to zero.
        """
        self.__state = 'color_table'
        self.__color_table_final = ''
        self.__close_group_count = self.__ob_count
        self.__cb_count = 0

    def __color_table_func(self, line):
        if int(self.__cb_count) == int(self.__close_group_count):
            self.__state = 'preamble'
            self.__color_table_final = 'mi<tg<open______<color-table\n' + \
            'mi<mk<clrtbl-beg\n' + self.__color_table_final
            self.__color_table_final += \
            'mi<mk<clrtbl-end\n' + 'mi<tg<close_____<color-table\n'
        else:
            self.__color_table_final += line

    def __found_style_sheet_func(self, line):
        self.__state = 'style_sheet'
        self.__style_sheet_final = ''
        self.__close_group_count = self.__ob_count
        self.__cb_count = 0

    def __style_sheet_func(self, line):
        """
        Same logic as the  font_table_func.
        """
        if self.__cb_count == self.__close_group_count:
            self.__state = 'preamble'
            self.__style_sheet_final = 'mi<tg<open______<style-table\n' + \
            'mi<mk<styles-beg\n' + self.__style_sheet_final
            self.__style_sheet_final += \
            'mi<mk<styles-end\n' + 'mi<tg<close_____<style-table\n'
        elif self.__token_info == 'ob<nu<open-brack':
            if int(self.__ob_count) == int(self.__close_group_count) + 1:
                self.__style_sheet_final +=  \
                'mi<mk<stylei-beg\n'
        elif self.__token_info == 'cb<nu<clos-brack':
            if int(self.__cb_count) == int(self.__close_group_count) + 1:
                self.__style_sheet_final +=  \
                'mi<mk<stylei-end\n'
        else:
            self.__style_sheet_final +=  line

    def __found_list_table_func(self, line):
        self.__state = 'list_table'
        self.__list_table_final = ''
        self.__close_group_count = self.__ob_count
        self.__cb_count = 0

    def __list_table_func(self, line):
        if self.__cb_count == self.__close_group_count:
            self.__state = 'preamble'
            self.__list_table_final, self.__all_lists =\
                self.__list_table_obj.parse_list_table(
                self.__list_table_final)
            # sys.stderr.write(repr(all_lists))
        elif self.__token_info == '':
            pass
        else:
            self.__list_table_final += line
            pass

    def __found_override_table_func(self, line):
        self.__override_table_obj = override_table.OverrideTable(
            run_level=self.__run_level,
            list_of_lists=self.__all_lists,
            )
        self.__state = 'override_table'
        self.__override_table_final = ''
        self.__close_group_count = self.__ob_count
        self.__cb_count = 0
        # cw<it<lovr-table

    def __override_table_func(self, line):
        if self.__cb_count == self.__close_group_count:
            self.__state = 'preamble'
            self.__override_table_final, self.__all_lists =\
                self.__override_table_obj.parse_override_table(self.__override_table_final)
        elif self.__token_info == '':
            pass
        else:
            self.__override_table_final += line

    def __found_revision_table_func(self, line):
        self.__state = 'revision_table'
        self.__revision_table_final = ''
        self.__close_group_count = self.__ob_count
        self.__cb_count = 0

    def __revision_table_func(self, line):
        if int(self.__cb_count) == int(self.__close_group_count):
            self.__state = 'preamble'
            self.__revision_table_final = 'mi<tg<open______<revision-table\n' + \
            'mi<mk<revtbl-beg\n' + self.__revision_table_final
            self.__revision_table_final += \
            'mi<mk<revtbl-end\n' + 'mi<tg<close_____<revision-table\n'
        else:
            self.__revision_table_final += line

    def __found_doc_info_func(self, line):
        self.__state = 'doc_info'
        self.__doc_info_table_final = ''
        self.__close_group_count = self.__ob_count
        self.__cb_count = 0

    def __doc_info_func(self, line):
        if self.__cb_count == self.__close_group_count:
            self.__state = 'preamble'
            self.__doc_info_table_final = 'mi<tg<open______<doc-information\n' + \
            'mi<mk<doc-in-beg\n' + self.__doc_info_table_final
            self.__doc_info_table_final += \
            'mi<mk<doc-in-end\n' + 'mi<tg<close_____<doc-information\n'
        elif self.__token_info == 'ob<nu<open-brack':
            if int(self.__ob_count) == int(self.__close_group_count) + 1:
                self.__doc_info_table_final +=  \
                'mi<mk<docinf-beg\n'
        elif self.__token_info == 'cb<nu<clos-brack':
            if int(self.__cb_count) == int(self.__close_group_count) + 1:
                self.__doc_info_table_final +=  \
                'mi<mk<docinf-end\n'
        else:
            self.__doc_info_table_final +=  line

    def __margin_func(self, line):
        """
        Handles lines that describe page info. Add the appropriate info in the
        token to the self.__margin_dict dictionary.
        """
        info = line[6:16]
        changed = self.__margin_dict.get(info)
        if changed is None:
            print('woops!')
        else:
            self.__page[changed] = line[20:-1]
        # cw<pa<margin-lef<nu<1728

    def __print_page_info(self):
        self.__write_obj.write('mi<tg<empty-att_<page-definition')
        for key in self.__page.keys():
            self.__write_obj.write(
            f'<{key}>{self.__page[key]}'
            )
        self.__write_obj.write('\n')
# mi<tg<open-att__<footn

    def __print_sec_info(self):
        """
        Check if there is any section info. If so, print it out.
        If not, print out an empty tag to satisfy the dtd.
        """
        if len(self.__section.keys()) == 0:
            self.__write_obj.write(
            'mi<tg<open______<section-definition\n'
                    )
        else:
            self.__write_obj.write(
            'mi<tg<open-att__<section-definition')
            keys = self.__section.keys()
            for key in keys:
                self.__write_obj.write(
                '<%s>%s' %  (key, self.__section[key])
                )
            self.__write_obj.write('\n')

    def __section_func(self, line):
        """
        Add info pertaining to section to the self.__section dictionary, to be
        printed out later.
        """
        info = self.__translate_sec.get(line[6:16])
        if info is None:
            sys.stderr.write('woops!\n')
        else:
            self.__section[info] = 'true'

    def __body_func(self, line):
        self.__write_obj.write(line)

    def __default_func(self, line):
        # either in preamble or in body
        pass

    def __para_def_func(self, line):
        # if self.__ob_group == 1
        # this tells dept of group
        if self.__cb_count == '0002':
            self.__state = 'body'
            self.__write_preamble()
        self.__write_obj.write(line)

    def __text_func(self, line):
        """
        If the cb_count is less than 1, you have hit the body
        For older RTF
        Newer RTF should never have to use this function
        """
        if self.__cb_count == '':
            cb_count = '0002'
        else:
            cb_count = self.__cb_count
        # ignore previous lines
        # should be
        # if self.__ob_group == 1
        # this tells dept of group
        if cb_count == '0002':
            self.__state = 'body'
            self.__write_preamble()
        self.__write_obj.write(line)

    def __row_def_func(self, line):
        # if self.__ob_group == 1
        # this tells dept of group
        if self.__cb_count == '0002':
            self.__state = 'body'
            self.__write_preamble()
        self.__write_obj.write(line)

    def __new_section_func(self, line):
        """
        This is new. The start of a section marks the end of the preamble
        """
        if self.__cb_count == '0002':
            self.__state = 'body'
            self.__write_preamble()
        else:
            sys.stderr.write('module is preamble_div\n')
            sys.stderr.write('method is __new_section_func\n')
            sys.stderr.write('bracket count should be 2?\n')
        self.__write_obj.write(line)

    def __write_preamble(self):
        """
        Write all the strings, which represent all the data in the preamble.
        Write a body and section beginning.
        """
        if self.__no_namespace:
            self.__write_obj.write(
                'mi<tg<open______<doc\n'
                    )
        else:
            self.__write_obj.write(
                    'mi<tg<open-att__<doc<xmlns>http://rtf2xml.sourceforge.net/\n')
        self.__write_obj.write('mi<tg<open______<preamble\n')
        self.__write_obj.write(self.__rtf_final)
        if not self.__color_table_final:
            self.__make_default_color_table()
        if not self.__font_table_final:
            self.__make_default_font_table()
        self.__write_obj.write(self.__font_table_final)
        self.__write_obj.write(self.__color_table_final)
        if not self.__style_sheet_final:
            self.__make_default_style_table()
        self.__write_obj.write(self.__style_sheet_final)
        self.__write_obj.write(self.__list_table_final)
        self.__write_obj.write(self.__override_table_final)
        self.__write_obj.write(self.__revision_table_final)
        self.__write_obj.write(self.__doc_info_table_final)
        self.__print_page_info()
        self.__write_obj.write('ob<nu<open-brack<0001\n')
        self.__write_obj.write('ob<nu<open-brack<0002\n')
        self.__write_obj.write('cb<nu<clos-brack<0002\n')
        self.__write_obj.write('mi<tg<close_____<preamble\n')
        self.__write_obj.write('mi<tg<open______<body\n')
        # self.__write_obj.write('mi<tg<open-att__<section<num>1\n')
        # self.__print_sec_info()
        # self.__write_obj.write('mi<tg<open______<headers-and-footers\n')
        # self.__write_obj.write('mi<mk<head_foot_<\n')
        # self.__write_obj.write('mi<tg<close_____<headers-and-footers\n')
        self.__write_obj.write('mi<mk<body-open_\n')

    def __preamble_func(self, line):
        """
        Check if the token info belongs to the dictionary. If so, take the
        appropriate action.
        """
        action = self.__state_dict.get(self.__token_info)
        if action:
            action(line)

    def make_preamble_divisions(self):
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
                self.__ob_group += 1
            if self.__token_info == 'cb<nu<clos-brack':
                self.__cb_count = line[-5:-1]
                self.__ob_group -= 1
            action = self.__state_dict.get(self.__state)
            if action is None:
                print(self.__state)
            action(line)
        read_obj.close()
        self.__write_obj.close()
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "preamble_div.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
        return self.__all_lists
