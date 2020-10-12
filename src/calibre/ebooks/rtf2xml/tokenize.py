
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
import os, re

from calibre.ebooks.rtf2xml import copy
from calibre.utils.mreplace import MReplace
from calibre.ptempfile import better_mktemp
from polyglot.builtins import codepoint_to_chr, range, filter, map
from . import open_for_read, open_for_write


class Tokenize:
    """Tokenize RTF into one line per field. Each line will contain information useful for the rest of the script"""

    def __init__(self,
            in_file,
            bug_handler,
            copy=None,
            run_level=1,
            # out_file = None,
        ):
        self.__file = in_file
        self.__bug_handler = bug_handler
        self.__copy = copy
        self.__write_to = better_mktemp()
        # self.__write_to = out_file
        self.__compile_expressions()
        # variables
        self.__uc_char = 0
        self.__uc_bin = False
        self.__uc_value = [1]

    def __reini_utf8_counters(self):
        self.__uc_char = 0
        self.__uc_bin = False

    def __remove_uc_chars(self, startchar, token):
        for i in range(startchar, len(token)):
            if self.__uc_char:
                self.__uc_char -= 1
            else:
                return token[i:]
        # if only char to skip
        return ''

    def __unicode_process(self, token):
        # change scope in
        if token == r'\{':
            self.__uc_value.append(self.__uc_value[-1])
            # basic error handling
            self.__reini_utf8_counters()
            return token
        # change scope out
        elif token == r'\}':
            self.__uc_value.pop()
            self.__reini_utf8_counters()
            return token
        # add a uc control
        elif token[:3] == '\\uc':
            self.__uc_value[-1] = int(token[3:])
            self.__reini_utf8_counters()
            return token
        # bin data to slip
        elif self.__uc_bin:
            self.__uc_bin = False
            return ''
        # uc char to remove
        elif self.__uc_char:
            # handle \bin tag in case of uc char to skip
            if token[:4] == '\bin':
                self.__uc_char -=1
                self.__uc_bin = True
                return ''
            elif token[:1] == "\\" :
                self.__uc_char -=1
                return ''
            else:
                return self.__remove_uc_chars(0, token)
        # go for real \u token
        match_obj = self.__utf_exp.match(token)
        if match_obj is not None:
            self.__reini_utf8_counters()
            # get value and handle negative case
            uni_char = int(match_obj.group(1))
            uni_len = len(match_obj.group(0))
            if uni_char < 0:
                uni_char += 65536
            uni_char = codepoint_to_chr(uni_char).encode('ascii', 'xmlcharrefreplace').decode('ascii')
            self.__uc_char = self.__uc_value[-1]
            # there is only an unicode char
            if len(token)<= uni_len:
                return uni_char
            # an unicode char and something else
            # must be after as it is splited on \
            # necessary? maybe for \bin?
            elif not self.__uc_char:
                return uni_char + token[uni_len:]
            # if not uc0 and chars
            else:
                return uni_char + self.__remove_uc_chars(uni_len, token)
        # default
        return token

    def __sub_reg_split(self,input_file):
        input_file = self.__replace_spchar.mreplace(input_file)
        # this is for older RTF
        input_file = self.__par_exp.sub(r'\n\\par \n', input_file)
        input_file = self.__cwdigit_exp.sub(r"\g<1>\n\g<2>", input_file)
        input_file = self.__cs_ast.sub(r"\g<1>", input_file)
        input_file = self.__ms_hex_exp.sub(r"\\mshex0\g<1> ", input_file)
        input_file = self.__utf_ud.sub(r"\\{\\uc0 \g<1>\\}", input_file)
        # remove \n in bin data
        input_file = self.__bin_exp.sub(lambda x:
                                        x.group().replace('\n', '') + '\n', input_file)
        # split
        tokens = re.split(self.__splitexp, input_file)
        # remove empty tokens and \n
        return list(filter(lambda x: len(x) > 0 and x != '\n', tokens))

    def __compile_expressions(self):
        SIMPLE_RPL = {
            "\\\\": "\\backslash ",
            "\\~": "\\~ ",
            "\\;": "\\; ",
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            "\\~": "\\~ ",
            "\\_": "\\_ ",
            "\\:": "\\: ",
            "\\-": "\\- ",
            # turn into a generic token to eliminate special
            # cases and make processing easier
            "\\{": "\\ob ",
            # turn into a generic token to eliminate special
            # cases and make processing easier
            "\\}": "\\cb ",
            # put a backslash in front of to eliminate special cases and
            # make processing easier
            "{": "\\{",
            # put a backslash in front of to eliminate special cases and
            # make processing easier
            "}": "\\}",
            }
        self.__replace_spchar = MReplace(SIMPLE_RPL)
        # add ;? in case of char following \u
        self.__ms_hex_exp = re.compile(r"\\\'([0-9a-fA-F]{2})")
        self.__utf_exp = re.compile(r"\\u(-?\d{3,6}) ?")
        self.__bin_exp = re.compile(r"(?:\\bin(-?\d{0,10})[\n ]+)[01\n]+")
        # manage upr/ud situations
        self.__utf_ud = re.compile(r"\\{[\n ]?\\upr[\n ]?(?:\\{.*?\\})[\n ]?" +
                       r"\\{[\n ]?\\*[\n ]?\\ud[\n ]?(\\{.*?\\})[\n ]?\\}[\n ]?\\}")
        # add \n in split for whole file reading
        # why keep backslash whereas \is replaced before?
        # remove \n from endline char
        self.__splitexp = re.compile(r"(\\[{}]|\n|\\[^\s\\{}&]+(?:[ \t\r\f\v])?)")
        # this is for old RTF
        self.__par_exp = re.compile(r'(\\\n+|\\ )')
        # handle improper cs char-style with \* before without {
        self.__cs_ast = re.compile(r'\\\*([\n ]*\\cs\d+[\n \\]+)')
        # handle cw using a digit as argument and without space as delimiter
        self.__cwdigit_exp = re.compile(r"(\\[a-zA-Z]+[\-0-9]+)([^0-9 \\]+)")

    def tokenize(self):
        """Main class for handling other methods. Reads the file \
        , uses method self.sub_reg to make basic substitutions,\
        and process tokens by itself"""
        # read
        with open_for_read(self.__file) as read_obj:
            input_file = read_obj.read()

        # process simple replacements and split giving us a correct list
        # remove '' and \n in the process
        tokens = self.__sub_reg_split(input_file)
        # correct unicode
        tokens = map(self.__unicode_process, tokens)
        # remove empty items created by removing \uc
        tokens = list(filter(lambda x: len(x) > 0, tokens))

        # write
        with open_for_write(self.__write_to) as write_obj:
            write_obj.write('\n'.join(tokens))
        # Move and copy
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "tokenize.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)

        # self.__special_tokens = [ '_', '~', "'", '{', '}' ]

# import sys
# def main(args=sys.argv):
    # if len(args) < 2:
        # print 'No file'
        # return
    # file = 'data_tokens.txt'
    # if len(args) == 3:
        # file = args[2]
    # to = Tokenize(args[1], Exception, out_file = file)
    # to.tokenize()


# if __name__ == '__main__':
    # sys.exit(main())

# calibre-debug -e src/calibre/ebooks/rtf2xml/tokenize.py
