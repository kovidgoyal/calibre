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
import sys

from . import open_for_read


class OldRtf:
    """
    Check to see if the RTF is an older version
    Logic:
    If allowable control word/properties happen in text without being enclosed
    in brackets the file will be considered old rtf
    """

    def __init__(self, in_file,
                bug_handler,
                run_level,
                ):
        """
        Required:
            'file'--file to parse
            'table_data' -- a dictionary for each table.
        Optional:
            'copy'-- whether to make a copy of result for debugging
            'temp_dir' --where to output temporary results (default is
            directory from which the script is run.)
        Returns:
            nothing
            """
        self.__file = in_file
        self.__bug_handler = bug_handler
        self.__run_level = run_level
        self.__allowable = [
            'annotation' ,
            'blue______'  ,
            'bold______',
            'caps______',
            'char-style' ,
            'dbl-strike' ,
            'emboss____',
            'engrave___' ,
            'font-color',
            'font-down_' ,
            'font-size_',
            'font-style',
            'font-up___',
            'footnot-mk' ,
            'green_____' ,
            'hidden____',
            'italics___',
            'outline___',
            'red_______',
            'shadow____' ,
            'small-caps',
            'strike-thr',
            'subscript_',
            'superscrip' ,
            'underlined' ,
        ]
        self.__action_dict = {
            'before_body'   : self.__before_body_func,
            'in_body'       : self.__check_tokens_func,
            'after_pard'    : self.__after_pard_func,
        }

    def __initiate_values(self):
        self.__previous_token = ''
        self.__state = 'before_body'
        self.__found_new = 0
        self.__ob_group = 0

    def __check_tokens_func(self, line):
        if self.__inline_info in self.__allowable:
            if self.__ob_group == self.__base_ob_count:
                return 'old_rtf'
            else:
                self.__found_new += 1
        elif self.__token_info ==  'cw<pf<par-def___':
            self.__state = 'after_pard'

    def __before_body_func(self, line):
        if self.__token_info == 'mi<mk<body-open_':
            self.__state = 'in_body'
            self.__base_ob_count = self.__ob_group

    def __after_pard_func(self, line):
        if line[0:2] != 'cw':
            self.__state = 'in_body'

    def check_if_old_rtf(self):
        """
        Requires:
            nothing
        Returns:
            True if file is older RTf
            False if file is newer RTF
        """
        self.__initiate_values()
        line_num = 0
        with open_for_read(self.__file) as read_obj:
            for line in read_obj:
                line_num += 1
                self.__token_info = line[:16]
                if self.__token_info == 'mi<mk<body-close':
                    return False
                if self.__token_info == 'ob<nu<open-brack':
                    self.__ob_group += 1
                    self.__ob_count = line[-5:-1]
                if self.__token_info == 'cb<nu<clos-brack':
                    self.__ob_group -= 1
                    self.__cb_count = line[-5:-1]
                self.__inline_info = line[6:16]
                if self.__state == 'after_body':
                    return False
                action = self.__action_dict.get(self.__state)
                if action is None:
                    try:
                        sys.stderr.write('No action for this state!\n')
                    except:
                        pass
                result = action(line)
                if result == 'new_rtf':
                    return False
                elif result == 'old_rtf':
                    if self.__run_level > 3:
                        sys.stderr.write(
                            'Old rtf construction %s (bracket %s, line %s)\n' % (
                                self.__inline_info, str(self.__ob_group), line_num)
                        )
                    return True
                self.__previous_token = line[6:16]
        return False
