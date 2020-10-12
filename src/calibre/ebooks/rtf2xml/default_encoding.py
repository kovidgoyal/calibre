
#########################################################################
#                                                                       #
#   copyright 2002 Paul Henry Tremblay                                  #
#                                                                       #
#########################################################################

'''
Codepages as to RTF 1.9.1:
    437	United States IBM
    708	Arabic (ASMO 708)
    709	Arabic (ASMO 449+, BCON V4)
    710	Arabic (transparent Arabic)
    711	Arabic (Nafitha Enhanced)
    720	Arabic (transparent ASMO)
    819	Windows 3.1 (United States and Western Europe)
    850	IBM multilingual
    852	Eastern European
    860	Portuguese
    862	Hebrew
    863	French Canadian
    864	Arabic
    865	Norwegian
    866	Soviet Union
    874	Thai
    932	Japanese
    936	Simplified Chinese
    949	Korean
    950	Traditional Chinese
    1250	Eastern European
    1251	Cyrillic
    1252	Western European
    1253	Greek
    1254	Turkish
    1255	Hebrew
    1256	Arabic
    1257	Baltic
    1258	Vietnamese
    1361	Johab
    10000	MAC Roman
    10001	MAC Japan
    10004	MAC Arabic
    10005	MAC Hebrew
    10006	MAC Greek
    10007	MAC Cyrillic
    10029	MAC Latin2
    10081	MAC Turkish
    57002	Devanagari
    57003	Bengali
    57004	Tamil
    57005	Telugu
    57006	Assamese
    57007	Oriya
    57008	Kannada
    57009	Malayalam
    57010	Gujarati
    57011	Punjabi
'''
import re
from . import open_for_read


class DefaultEncoding:
    """
    Find the default encoding for the doc
    """

    # Note: not all those encoding are really supported by rtf2xml
    # See http://msdn.microsoft.com/en-us/library/windows/desktop/dd317756%28v=vs.85%29.aspx
    # and src\calibre\gui2\widgets.py for the input list in calibre
    ENCODINGS = {
                # Special cases
                'cp1252':'1252',
                'utf-8':'1252',
                'ascii':'1252',
                # Normal cases
                'big5':'950',
                'cp1250':'1250',
                'cp1251':'1251',
                'cp1253':'1253',
                'cp1254':'1254',
                'cp1255':'1255',
                'cp1256':'1256',
                'shift_jis':'932',
                'gb2312':'936',
                # Not in RTF 1.9.1 codepage specification
                'hz':'52936',
                'iso8859_5':'28595',
                'iso2022_jp':'50222',
                'iso2022_kr':'50225',
                'euc_jp':'51932',
                'euc_kr':'51949',
                'gb18030':'54936',
                }

    def __init__(self, in_file, bug_handler, default_encoding, run_level=1, check_raw=False):
        self.__file = in_file
        self.__bug_handler = bug_handler
        self.__platform = 'Windows'
        self.__default_num = 'not-defined'
        self.__code_page = self.ENCODINGS.get(default_encoding, '1252')
        self.__datafetched = False
        self.__fetchraw = check_raw

    def find_default_encoding(self):
        if not self.__datafetched:
            self._encoding()
            self.__datafetched = True
            code_page = 'ansicpg' + self.__code_page
            # if self.__code_page == '10000':
            # self.__code_page = 'mac_roman'
        return self.__platform, code_page, self.__default_num

    def get_codepage(self):
        if not self.__datafetched:
            self._encoding()
            self.__datafetched = True
            # if self.__code_page == '10000':
            # self.__code_page = 'mac_roman'
        return self.__code_page

    def get_platform(self):
        if not self.__datafetched:
            self._encoding()
            self.__datafetched = True
        return self.__platform

    def _encoding(self):
        with open_for_read(self.__file) as read_obj:
            cpfound = False
            if not self.__fetchraw:
                for line in read_obj:
                    self.__token_info = line[:16]
                    if self.__token_info == 'mi<mk<rtfhed-end':
                        break
                    if self.__token_info == 'cw<ri<macintosh_':
                        self.__platform = 'Macintosh'
                    elif self.__token_info == 'cw<ri<pc________':
                        self.__platform = 'IBMPC'
                    elif self.__token_info == 'cw<ri<pca_______':
                        self.__platform = 'OS/2'
                    if self.__token_info == 'cw<ri<ansi-codpg' \
                        and int(line[20:-1]):
                        self.__code_page = line[20:-1]
                    if self.__token_info == 'cw<ri<deflt-font':
                        self.__default_num = line[20:-1]
                        cpfound = True
                        # cw<ri<deflt-font<nu<0
                if self.__platform != 'Windows' and \
                        not cpfound:
                    if self.__platform == 'Macintosh':
                        self.__code_page = '10000'
                    elif self.__platform == 'IBMPC':
                        self.__code_page = '437'
                    elif self.__platform == 'OS/2':
                        self.__code_page = '850'
            else:
                fenc = re.compile(r'\\(mac|pc|ansi|pca)[\\ \{\}\t\n]+')
                fenccp = re.compile(r'\\ansicpg(\d+)[\\ \{\}\t\n]+')

                for line in read_obj:
                    if fenc.search(line):
                        enc = fenc.search(line).group(1)
                    if fenccp.search(line):
                        cp = fenccp.search(line).group(1)
                        if not int(cp):
                            self.__code_page = cp
                        cpfound = True
                        break
                if self.__platform != 'Windows' and \
                        not cpfound:
                    if enc == 'mac':
                        self.__code_page = '10000'
                    elif enc == 'pc':
                        self.__code_page = '437'
                    elif enc == 'pca':
                        self.__code_page = '850'


if __name__ == '__main__':
    import sys
    encode_obj = DefaultEncoding(
            in_file=sys.argv[1],
            default_encoding=sys.argv[2],
            bug_handler=Exception,
            check_raw=True,
            )
    print(encode_obj.get_codepage())
