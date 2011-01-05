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

class DefaultEncoding:
    """
    Find the default encoding for the doc
    """
    def __init__(self, in_file, bug_handler, run_level = 1,):
        self.__file = in_file
        self.__bug_handler = bug_handler
        self.__platform = 'Windows'
        self.__default_num = 'not-defined'
        self.__code_page = '1252'
        self.__datafetched = False

    def find_default_encoding(self):
        if not self.__datafetched:
            self._encoding()
            self.__datafetched = True
        if self.__platform == 'Macintosh':
            code_page = self.__code_page
        else
            code_page = 'ansicpg' + self.__code_page
        return platform, code_page, self.__default_num
    
    def get_codepage(self):
        if not self.__datafetched:
            self._encoding()
            self.__datafetched = True
        return self.__code_page

    def get_platform(self):
        if not self.__datafetched:
            self._encoding()
            self.__datafetched = True
        return self.__platform
    
    def _encoding(self):
        with open(self.__file, 'r') as read_obj:
            for line in read_obj:
                self.__token_info = line[:16]
                if self.__token_info == 'mi<mk<rtfhed-end':
                    break
                if self.__token_info == 'cw<ri<ansi-codpg':
                    #cw<ri<ansi-codpg<nu<10000
                    self.__code_page = line[20:-1] if line[20:-1] \
                                        else '1252'
                if self.__token_info == 'cw<ri<macintosh_':
                    self.__platform = 'Macintosh'
                elif self.__token_info == 'cw<ri<pc________':
                    self.__platform = 'IBMPC'
                elif self.__token_info == 'cw<ri<pca_______':
                    self.__platform = 'OS/2'
                if self.__token_info == 'cw<ri<deflt-font':
                    self.__default_num = line[20:-1]
                    #cw<ri<deflt-font<nu<0
        if self.__platform == 'Macintosh':
            self.__code_page = 'mac_roman'
        elif self.__platform == 'IBMPC':
            self.__code_page = '437'
        elif self.__platform == 'OS/2':
            self.__code_page = '850'

