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

from calibre.ebooks.rtf2xml import copy, check_brackets
from calibre.ptempfile import better_mktemp

from . import open_for_read, open_for_write


class ProcessTokens:
    """
    Process each token on a line and add information that will be useful for
    later processing. Information will be put on one line, delimited by "<"
    for main fields, and ">" for sub fields
    """

    def __init__(self,
            in_file,
            exception_handler,
            bug_handler,
            copy=None,
            run_level=1,
            ):
        self.__file = in_file
        self.__bug_handler = bug_handler
        self.__copy = copy
        self.__run_level = run_level
        self.__write_to = better_mktemp()
        self.initiate_token_dict()
        # self.initiate_token_actions()
        self.compile_expressions()
        self.__bracket_count=0
        self.__exception_handler = exception_handler
        self.__bug_handler = bug_handler

    def compile_expressions(self):
        self.__num_exp = re.compile(r"([a-zA-Z]+)(.*)")
        self.__utf_exp = re.compile(r'(&.*?;)')

    def initiate_token_dict(self):
        self.__return_code = 0
        self.dict_token={
        # unicode
        'mshex'              :  ('nu', '__________', self.__ms_hex_func),
        # brackets
        '{'                  : ('nu', '{', self.ob_func),
        '}'                  : ('nu', '}', self.cb_func),
        # microsoft characters
        'ldblquote'          : ('mc', 'ldblquote', self.ms_sub_func),
        'rdblquote'          : ('mc', 'rdblquote', self.ms_sub_func),
        'rquote'             : ('mc', 'rquote', self.ms_sub_func),
        'lquote'             : ('mc', 'lquote', self.ms_sub_func),
        'emdash'             : ('mc', 'emdash', self.ms_sub_func),
        'endash'             : ('mc', 'endash', self.ms_sub_func),
        'bullet'             : ('mc', 'bullet', self.ms_sub_func),
        '~'                  : ('mc', '~', self.ms_sub_func),
        'tab'                : ('mc', 'tab', self.ms_sub_func),
        '_'                  : ('mc', '_', self.ms_sub_func),
        ';'                  : ('mc', ';', self.ms_sub_func),
        # this must be wrong
        '-'                  : ('mc', '-', self.ms_sub_func),
        'line'               :  ('mi', 'hardline-break', self.direct_conv_func),  # calibre
        # misc => ml
        '*'                  : ('ml', 'asterisk__', self.default_func),
        ':'                  : ('ml', 'colon_____', self.default_func),
        # text
        'backslash'          : ('nu', '\\', self.text_func),
        'ob'                 : ('nu', '{', self.text_func),
        'cb'                 : ('nu', '}', self.text_func),
        # paragraph formatting => pf
        'page'               :  ('pf', 'page-break', self.default_func),
        'par'                : ('pf', 'par-end___', self.default_func),
        'pard'               : ('pf', 'par-def___', self.default_func),
        'keepn'              : ('pf', 'keep-w-nex', self.bool_st_func),
        'widctlpar'          : ('pf', 'widow-cntl', self.bool_st_func),
        'adjustright'        : ('pf', 'adjust-rgt', self.bool_st_func),
        'lang'               : ('pf', 'language__', self.__language_func),
        'ri'                 : ('pf', 'right-inde', self.divide_by_20),
        'fi'                 : ('pf', 'fir-ln-ind', self.divide_by_20),
        'li'                 : ('pf', 'left-inden', self.divide_by_20),
        'sb'                 : ('pf', 'space-befo', self.divide_by_20),
        'sa'                 : ('pf', 'space-afte', self.divide_by_20),
        'sl'                 : ('pf', 'line-space', self.divide_by_20),
        'deftab'             : ('pf', 'default-ta', self.divide_by_20),
        'ql'                 : ('pf', 'align_____<left', self.two_part_func),
        'qc'                 : ('pf', 'align_____<cent', self.two_part_func),
        'qj'                 : ('pf', 'align_____<just', self.two_part_func),
        'qr'                 : ('pf', 'align_____<right', self.two_part_func),
        'nowidctlpar'        : ('pf', 'widow-cntr<false', self.two_part_func),
        'tx'                 :  ('pf', 'tab-stop__', self.divide_by_20),
        'tb'                 :  ('pf', 'tab-bar-st', self.divide_by_20),
        'tqr'                :  ('pf', 'tab-right_', self.default_func),
        'tqdec'              :  ('pf', 'tab-dec___', self.default_func),
        'tqc'                :  ('pf', 'tab-center', self.default_func),
        'tlul'               :  ('pf', 'leader-und', self.default_func),
        'tlhyph'             :  ('pf', 'leader-hyp', self.default_func),
        'tldot'              :  ('pf', 'leader-dot', self.default_func),
        # stylesheet = > ss
        'stylesheet'         : ('ss', 'style-shet', self.default_func),
        'sbasedon'           : ('ss', 'based-on__', self.default_func),
        'snext'              : ('ss', 'next-style', self.default_func),
        'cs'                 : ('ss', 'char-style', self.default_func),
        's'                  : ('ss', 'para-style', self.default_func),
        # graphics => gr
        'pict'               : ('gr', 'picture___', self.default_func),
        'objclass'           : ('gr', 'obj-class_', self.default_func),
        'macpict'            : ('gr', 'mac-pic___', self.default_func),
        # section => sc
        'sect'               : ('sc', 'section___', self.default_func),
        'sectd'              : ('sc', 'sect-defin', self.default_func),
        'endhere'            : ('sc', 'sect-note_', self.default_func),
        # list=> ls
        'pntext'             : ('ls', 'list-text_', self.default_func),
        # this line must be wrong because it duplicates an earlier one
        'listtext'           : ('ls', 'list-text_', self.default_func),
        'pn'                 : ('ls', 'list______', self.default_func),
        'pnseclvl'           : ('ls', 'list-level', self.default_func),
        'pncard'             : ('ls', 'list-cardi', self.bool_st_func),
        'pndec'              : ('ls', 'list-decim', self.bool_st_func),
        'pnucltr'            : ('ls', 'list-up-al', self.bool_st_func),
        'pnucrm'             : ('ls', 'list-up-ro', self.bool_st_func),
        'pnord'              : ('ls', 'list-ord__', self.bool_st_func),
        'pnordt'             : ('ls', 'list-ordte', self.bool_st_func),
        'pnlvlblt'           : ('ls', 'list-bulli', self.bool_st_func),
        'pnlvlbody'          : ('ls', 'list-simpi', self.bool_st_func),
        'pnlvlcont'          : ('ls', 'list-conti', self.bool_st_func),
        'pnhang'             : ('ls', 'list-hang_', self.bool_st_func),
        'pntxtb'             : ('ls', 'list-tebef', self.bool_st_func),
        'ilvl'               : ('ls', 'list-level', self.default_func),
        'ls'                 : ('ls', 'list-id___', self.default_func),
        'pnstart'            : ('ls', 'list-start', self.default_func),
        'itap'               : ('ls', 'nest-level', self.default_func),
        'leveltext'          :  ('ls', 'level-text', self.default_func),
        'levelnumbers'       :  ('ls', 'level-numb', self.default_func),
        'list'               :  ('ls', 'list-in-tb', self.default_func),
        'listlevel'          :  ('ls', 'list-tb-le', self.default_func),
        'listname'           :  ('ls', 'list-name_', self.default_func),
        'listtemplateid'     :  ('ls', 'ls-tem-id_', self.default_func),
        'leveltemplateid'    :  ('ls', 'lv-tem-id_', self.default_func),
        'listhybrid'         :  ('ls', 'list-hybri', self.default_func),
        'levelstartat'       :  ('ls', 'level-star', self.default_func),
        'levelspace'         :  ('ls', 'level-spac', self.divide_by_20),
        'levelindent'        :  ('ls', 'level-inde', self.default_func),
        'levelnfc'           :  ('ls', 'level-type', self.__list_type_func),
        'levelnfcn'          :  ('ls', 'level-type', self.__list_type_func),
        'listid'             :  ('ls', 'lis-tbl-id',  self.default_func),
        'listoverride'       :  ('ls', 'lis-overid', self.default_func),
        # duplicate
        'pnlvl'              : ('ls', 'list-level', self.default_func),
        # root info => ri
        'rtf'                : ('ri', 'rtf_______', self.default_func),
        'deff'               : ('ri', 'deflt-font', self.default_func),
        'mac'                : ('ri', 'macintosh_', self.default_func),
        'pc'                 : ('ri', 'pc________', self.default_func),
        'pca'                : ('ri', 'pca_______', self.default_func),
        'ansi'               : ('ri', 'ansi______', self.default_func),
        'ansicpg'            : ('ri', 'ansi-codpg', self.default_func),
        # notes => nt
        'footnote'           : ('nt', 'footnote__', self.default_func),
        'ftnalt'             : ('nt', 'type______<endnote', self.two_part_func),
        # anchor => an
        'tc'                 : ('an', 'toc_______', self.default_func),
        'bkmkstt'            : ('an', 'book-mk-st', self.default_func),
        'bkmkstart'          : ('an', 'book-mk-st', self.default_func),
        'bkmkend'            : ('an', 'book-mk-en', self.default_func),
        'xe'                 : ('an', 'index-mark', self.default_func),
        'rxe'                : ('an', 'place_____', self.default_func),
        # index => in
        'bxe'                : ('in', 'index-bold', self.default_func),
        'ixe'                : ('in', 'index-ital', self.default_func),
        'txe'                : ('in', 'index-see_', self.default_func),
        # table of contents => tc
        'tcl'               :   ('tc', 'toc-level_', self.default_func),
        'tcn'               :   ('tc', 'toc-sup-nu', self.default_func),
        # field => fd
        'field'              : ('fd', 'field_____', self.default_func),
        'fldinst'            : ('fd', 'field-inst', self.default_func),
        'fldrslt'            : ('fd', 'field-rslt', self.default_func),
        'datafield'          : ('fd', 'datafield_', self.default_func),
        # info-tables => it
        'fonttbl'            : ('it', 'font-table', self.default_func),
        'colortbl'           : ('it', 'colr-table', self.default_func),
        'listoverridetable'  : ('it', 'lovr-table', self.default_func),
        'listtable'          : ('it', 'listtable_', self.default_func),
        'revtbl'             : ('it', 'revi-table', self.default_func),
        # character info => ci
        'b'                  : ('ci', 'bold______', self.bool_st_func),
        'blue'               : ('ci', 'blue______', self.color_func),
        'caps'               : ('ci', 'caps______', self.bool_st_func),
        'cf'                 : ('ci', 'font-color', self.colorz_func),
        'chftn'              : ('ci', 'footnot-mk', self.bool_st_func),
        'dn'                 : ('ci', 'font-down_', self.divide_by_2),
        'embo'               : ('ci', 'emboss____', self.bool_st_func),
        'f'                  : ('ci', 'font-style', self.default_func),
        'fs'                 : ('ci', 'font-size_', self.divide_by_2),
        'green'              : ('ci', 'green_____', self.color_func),
        'i'                  : ('ci', 'italics___', self.bool_st_func),
        'impr'               : ('ci', 'engrave___', self.bool_st_func),
        'outl'               : ('ci', 'outline___', self.bool_st_func),
        'plain'              : ('ci', 'plain_____', self.bool_st_func),
        'red'                : ('ci', 'red_______', self.color_func),
        'scaps'              : ('ci', 'small-caps', self.bool_st_func),
        'shad'               : ('ci', 'shadow____', self.bool_st_func),
        'strike'             : ('ci', 'strike-thr', self.bool_st_func),
        'striked'            : ('ci', 'dbl-strike', self.bool_st_func),
        'sub'                : ('ci', 'subscript_', self.bool_st_func),
        'super'              : ('ci', 'superscrip', self.bool_st_func),
        'nosupersub'         : ('ci', 'no-su-supe', self.__no_sup_sub_func),
        'up'                 : ('ci', 'font-up___', self.divide_by_2),
        'v'                  : ('ci', 'hidden____', self.default_func),
        # underline
        # can't see why it isn't a char info: 'ul'=>'ci'
        'ul'                 : ('ci', 'underlined<continous', self.two_part_func),
        'uld'                : ('ci', 'underlined<dotted', self.two_part_func),
        'uldash'             : ('ci', 'underlined<dash', self.two_part_func),
        'uldashd'            : ('ci', 'underlined<dash-dot', self.two_part_func),
        'uldashdd'           : ('ci', 'underlined<dash-dot-dot', self.two_part_func),
        'uldb'               : ('ci', 'underlined<double', self.two_part_func),
        'ulhwave'            : ('ci', 'underlined<heavy-wave', self.two_part_func),
        'ulldash'            : ('ci', 'underlined<long-dash', self.two_part_func),
        'ulth'               : ('ci', 'underlined<thich', self.two_part_func),
        'ulthd'              : ('ci', 'underlined<thick-dotted', self.two_part_func),
        'ulthdash'           : ('ci', 'underlined<thick-dash', self.two_part_func),
        'ulthdashd'          : ('ci', 'underlined<thick-dash-dot', self.two_part_func),
        'ulthdashdd'         : ('ci', 'underlined<thick-dash-dot-dot', self.two_part_func),
        'ulthldash'          : ('ci', 'underlined<thick-long-dash', self.two_part_func),
        'ululdbwave'         : ('ci', 'underlined<double-wave', self.two_part_func),
        'ulw'                : ('ci', 'underlined<word', self.two_part_func),
        'ulwave'             : ('ci', 'underlined<wave', self.two_part_func),
        'ulnone'             : ('ci', 'underlined<false', self.two_part_func),
        # table => tb
        'trowd'              : ('tb', 'row-def___', self.default_func),
        'cell'               : ('tb', 'cell______', self.default_func),
        'row'                : ('tb', 'row_______', self.default_func),
        'intbl'              : ('tb', 'in-table__', self.default_func),
        'cols'               : ('tb', 'columns___', self.default_func),
        'trleft'             : ('tb', 'row-pos-le', self.divide_by_20),
        'cellx'              : ('tb', 'cell-posit', self.divide_by_20),
        'trhdr'              :  ('tb', 'row-header', self.default_func),
        # preamble => pr
        # document information => di
        # TODO integrate \userprops
        'info'               : ('di', 'doc-info__', self.default_func),
        'title'              : ('di', 'title_____', self.default_func),
        'author'             : ('di', 'author____', self.default_func),
        'operator'           : ('di', 'operator__', self.default_func),
        'manager'            : ('di', 'manager___', self.default_func),
        'company'            : ('di', 'company___', self.default_func),
        'keywords'           :  ('di', 'keywords__', self.default_func),
        'category'           :  ('di', 'category__', self.default_func),
        'doccomm'            :  ('di', 'doc-notes_', self.default_func),
        'comment'            :  ('di', 'doc-notes_', self.default_func),
        'subject'            :  ('di', 'subject___', self.default_func),
        'creatim'            : ('di', 'create-tim', self.default_func),
        'yr'                 : ('di', 'year______', self.default_func),
        'mo'                 : ('di', 'month_____', self.default_func),
        'dy'                 : ('di', 'day_______', self.default_func),
        'min'                : ('di', 'minute____', self.default_func),
        'sec'                : ('di', 'second____', self.default_func),
        'revtim'             : ('di', 'revis-time', self.default_func),
        'edmins'             : ('di', 'edit-time_', self.default_func),
        'printim'            : ('di', 'print-time', self.default_func),
        'buptim'             : ('di', 'backuptime', self.default_func),
        'nofwords'           : ('di', 'num-of-wor', self.default_func),
        'nofchars'           : ('di', 'num-of-chr', self.default_func),
        'nofcharsws'         : ('di', 'numofchrws', self.default_func),
        'nofpages'           : ('di', 'num-of-pag', self.default_func),
        'version'            : ('di', 'version___', self.default_func),
        'vern'               : ('di', 'intern-ver', self.default_func),
        'hlinkbase'          : ('di', 'linkbase__', self.default_func),
        'id'                 : ('di', 'internalID', self.default_func),
        # headers and footers => hf
        'headerf'            : ('hf', 'head-first', self.default_func),
        'headerl'            : ('hf', 'head-left_', self.default_func),
        'headerr'            : ('hf', 'head-right', self.default_func),
        'footerf'            : ('hf', 'foot-first', self.default_func),
        'footerl'            : ('hf', 'foot-left_', self.default_func),
        'footerr'            : ('hf', 'foot-right', self.default_func),
        'header'             : ('hf', 'header____', self.default_func),
        'footer'             : ('hf', 'footer____', self.default_func),
        # page => pa
        'margl'              : ('pa', 'margin-lef', self.divide_by_20),
        'margr'              : ('pa', 'margin-rig', self.divide_by_20),
        'margb'              : ('pa', 'margin-bot', self.divide_by_20),
        'margt'              : ('pa', 'margin-top', self.divide_by_20),
        'gutter'             : ('pa', 'gutter____', self.divide_by_20),
        'paperw'             : ('pa', 'paper-widt', self.divide_by_20),
        'paperh'             : ('pa', 'paper-hght', self.divide_by_20),
        # annotation => an
        'annotation'         :  ('an', 'annotation', self.default_func),
        # border => bd
        'trbrdrh'            : ('bd', 'bor-t-r-hi', self.default_func),
        'trbrdrv'            : ('bd', 'bor-t-r-vi', self.default_func),
        'trbrdrt'            : ('bd', 'bor-t-r-to', self.default_func),
        'trbrdrl'            : ('bd', 'bor-t-r-le', self.default_func),
        'trbrdrb'            : ('bd', 'bor-t-r-bo', self.default_func),
        'trbrdrr'            : ('bd', 'bor-t-r-ri', self.default_func),
        'clbrdrb'            : ('bd', 'bor-cel-bo', self.default_func),
        'clbrdrt'            : ('bd', 'bor-cel-to', self.default_func),
        'clbrdrl'            : ('bd', 'bor-cel-le', self.default_func),
        'clbrdrr'            : ('bd', 'bor-cel-ri', self.default_func),
        'brdrb'              : ('bd', 'bor-par-bo', self.default_func),
        'brdrt'              : ('bd', 'bor-par-to', self.default_func),
        'brdrl'              : ('bd', 'bor-par-le', self.default_func),
        'brdrr'              : ('bd', 'bor-par-ri', self.default_func),
        'box'                : ('bd', 'bor-par-bx', self.default_func),
        'chbrdr'            : ('bd', 'bor-par-bo', self.default_func),
        'brdrbtw'            : ('bd', 'bor-for-ev', self.default_func),
        'brdrbar'            : ('bd', 'bor-outsid', self.default_func),
        'brdrnone'           : ('bd', 'bor-none__<false', self.two_part_func),
        # border type => bt
        'brdrs'              : ('bt', 'bdr-single', self.default_func),
        'brdrth'             : ('bt', 'bdr-doubtb', self.default_func),
        'brdrsh'             : ('bt', 'bdr-shadow', self.default_func),
        'brdrdb'             : ('bt', 'bdr-double', self.default_func),
        'brdrdot'            : ('bt', 'bdr-dotted', self.default_func),
        'brdrdash'           : ('bt', 'bdr-dashed', self.default_func),
        'brdrhair'           : ('bt', 'bdr-hair__', self.default_func),
        'brdrinset'          : ('bt', 'bdr-inset_', self.default_func),
        'brdrdashsm'         : ('bt', 'bdr-das-sm', self.default_func),
        'brdrdashd'          : ('bt', 'bdr-dot-sm', self.default_func),
        'brdrdashdd'         : ('bt', 'bdr-dot-do', self.default_func),
        'brdroutset'         : ('bt', 'bdr-outset', self.default_func),
        'brdrtriple'         : ('bt', 'bdr-trippl', self.default_func),
        'brdrtnthsg'         : ('bt', 'bdr-thsm__', self.default_func),
        'brdrthtnsg'         : ('bt', 'bdr-htsm__', self.default_func),
        'brdrtnthtnsg'       : ('bt', 'bdr-hthsm_', self.default_func),
        'brdrtnthmg'         : ('bt', 'bdr-thm___', self.default_func),
        'brdrthtnmg'         : ('bt', 'bdr-htm___', self.default_func),
        'brdrtnthtnmg'       : ('bt', 'bdr-hthm__', self.default_func),
        'brdrtnthlg'         : ('bt', 'bdr-thl___', self.default_func),
        'brdrtnthtnlg'       : ('bt', 'bdr-hthl__', self.default_func),
        'brdrwavy'           : ('bt', 'bdr-wavy__', self.default_func),
        'brdrwavydb'         : ('bt', 'bdr-d-wav_', self.default_func),
        'brdrdashdotstr'     : ('bt', 'bdr-strip_', self.default_func),
        'brdremboss'         : ('bt', 'bdr-embos_', self.default_func),
        'brdrengrave'        : ('bt', 'bdr-engra_', self.default_func),
        'brdrframe'          : ('bt', 'bdr-frame_', self.default_func),
        'brdrw'              : ('bt', 'bdr-li-wid', self.divide_by_20),
        'brsp'              : ('bt', 'bdr-sp-wid', self.divide_by_20),
        'brdrcf'              : ('bt', 'bdr-color_', self.default_func),
        # comments
        # 'comment'              :	('cm', 'comment___', self.default_func),
        }
        self.__number_type_dict = {
            0:      'Arabic',
            1:      'uppercase Roman numeral',
            2:      'lowercase Roman numeral',
            3:      'uppercase letter',
            4:      'lowercase letter',
            5:      'ordinal number',
            6:      'cardianl text number',
            7:      'ordinal text number',
            10:     'Kanji numbering without the digit character',
            11:     'Kanji numbering with the digit character',
            1246:   'phonetic Katakana characters in aiueo order',
            1346:   'phonetic katakana characters in iroha order',
            14:     'double byte character',
            15:     'single byte character',
            16:     'Kanji numbering 3',
            17:     'Kanji numbering 4',
            18:     'Circle numbering' ,
            19:     'double-byte Arabic numbering',
            2046:   'phonetic double-byte Katakana characters',
            2146:   'phonetic double-byte katakana characters',
            22:     'Arabic with leading zero',
            23:     'bullet',
            24:     'Korean numbering 2',
            25:     'Korean numbering 1',
            26:     'Chinese numbering 1',
            27:     'Chinese numbering 2',
            28:     'Chinese numbering 3',
            29:     'Chinese numbering 4',
            30:     'Chinese Zodiac numbering 1',
            31:     'Chinese Zodiac numbering 2',
            32:     'Chinese Zodiac numbering 3',
            33:     'Taiwanese double-byte numbering 1',
            34:     'Taiwanese double-byte numbering 2',
            35:     'Taiwanese double-byte numbering 3',
            36:     'Taiwanese double-byte numbering 4',
            37:     'Chinese double-byte numbering 1',
            38:     'Chinese double-byte numbering 2',
            39:     'Chinese double-byte numbering 3',
            40:     'Chinese double-byte numbering 4',
            41:     'Korean double-byte numbering 1',
            42:     'Korean double-byte numbering 2',
            43:     'Korean double-byte numbering 3',
            44:     'Korean double-byte numbering 4',
            45:     'Hebrew non-standard decimal',
            46:     'Arabic Alif Ba Tah',
            47:     'Hebrew Biblical standard',
            48:     'Arabic Abjad style',
            255:    'No number',
        }
        self.__language_dict = {
            1078 	:  'Afrikaans',
            1052 	:  'Albanian',
            1025 	:  'Arabic',
            5121 	:  'Arabic Algeria',
            15361 	:  'Arabic Bahrain',
            3073 	:  'Arabic Egypt',
            1 	    :   'Arabic General',
            2049 	:  'Arabic Iraq',
            11265 	:  'Arabic Jordan',
            13313 	:  'Arabic Kuwait',
            12289 	:  'Arabic Lebanon',
            4097 	:  'Arabic Libya',
            6145 	:  'Arabic Morocco',
            8193 	:  'Arabic Oman',
            16385 	:  'Arabic Qatar',
            10241 	:  'Arabic Syria',
            7169 	:  'Arabic Tunisia',
            14337 	:  'Arabic U.A.E.',
            9217 	:  'Arabic Yemen',
            1067 	:  'Armenian',
            1101 	:  'Assamese',
            2092 	:  'Azeri Cyrillic',
            1068 	:  'Azeri Latin',
            1069 	:  'Basque',
            1093 	:  'Bengali',
            4122 	:  'Bosnia Herzegovina',
            1026 	:  'Bulgarian',
            1109 	:  'Burmese',
            1059 	:  'Byelorussian',
            1027 	:  'Catalan',
            2052 	:  'Chinese China',
            4 	    :  'Chinese General',
            3076 	:  'Chinese Hong Kong',
            4100 	:  'Chinese Singapore',
            1028 	:  'Chinese Taiwan',
            1050 	:  'Croatian',
            1029 	:  'Czech',
            1030 	:  'Danish',
            2067 	:  'Dutch Belgium',
            1043 	:  'Dutch Standard',
            3081 	:  'English Australia',
            10249 	:  'English Belize',
            2057 	:  'English British',
            4105 	:  'English Canada',
            9225 	:  'English Caribbean',
            9 	    :  'English General',
            6153 	:  'English Ireland',
            8201 	:  'English Jamaica',
            5129 	:  'English New Zealand',
            13321 	:  'English Philippines',
            7177 	:  'English South Africa',
            11273 	:  'English Trinidad',
            1033 	:  'English United States',
            1061 	:  'Estonian',
            1080 	:  'Faerose',
            1065 	:  'Farsi',
            1035 	:  'Finnish',
            1036 	:  'French',
            2060 	:  'French Belgium',
            11276 	:  'French Cameroon',
            3084 	:  'French Canada',
            12300 	:  'French Cote d\'Ivoire',
            5132 	:  'French Luxembourg',
            13324 	:  'French Mali',
            6156 	:  'French Monaco',
            8204 	:  'French Reunion',
            10252 	:  'French Senegal',
            4108 	:  'French Swiss',
            7180 	:  'French West Indies',
            9228 	:  'French Democratic Republic of the Congo',
            1122 	:  'Frisian',
            1084 	:  'Gaelic',
            2108 	:  'Gaelic Ireland',
            1110 	:  'Galician',
            1079 	:  'Georgian',
            1031 	:  'German',
            3079 	:  'German Austrian',
            5127 	:  'German Liechtenstein',
            4103 	:  'German Luxembourg',
            2055 	:  'German Switzerland',
            1032 	:  'Greek',
            1095 	:  'Gujarati',
            1037 	:  'Hebrew',
            1081 	:  'Hindi',
            1038 	:  'Hungarian',
            1039 	:  'Icelandic',
            1057 	:  'Indonesian',
            1040 	:  'Italian',
            2064 	:  'Italian Switzerland',
            1041 	:  'Japanese',
            1099 	:  'Kannada',
            1120 	:  'Kashmiri',
            2144 	:  'Kashmiri India',
            1087 	:  'Kazakh',
            1107 	:  'Khmer',
            1088 	:  'Kirghiz',
            1111 	:  'Konkani',
            1042 	:  'Korean',
            2066 	:  'Korean Johab',
            1108 	:  'Lao',
            1062 	:  'Latvian',
            1063 	:  'Lithuanian',
            2087 	:  'Lithuanian Classic',
            1086 	:  'Malay',
            2110 	:  'Malay Brunei Darussalam',
            1100 	:  'Malayalam',
            1082 	:  'Maltese',
            1112 	:  'Manipuri',
            1102 	:  'Marathi',
            1104 	:  'Mongolian',
            1121 	:  'Nepali',
            2145 	:  'Nepali India',
            1044 	:  'Norwegian Bokmal',
            2068 	:  'Norwegian Nynorsk',
            1096 	:  'Oriya',
            1045 	:  'Polish',
            1046 	:  'Portuguese (Brazil)',
            2070 	:  'Portuguese (Portugal)',
            1094 	:  'Punjabi',
            1047 	:  'Rhaeto-Romanic',
            1048 	:  'Romanian',
            2072 	:  'Romanian Moldova',
            1049 	:  'Russian',
            2073 	:  'Russian Moldova',
            1083 	:  'Sami Lappish',
            1103 	:  'Sanskrit',
            3098 	:  'Serbian Cyrillic',
            2074 	:  'Serbian Latin',
            1113 	:  'Sindhi',
            1051 	:  'Slovak',
            1060 	:  'Slovenian',
            1070 	:  'Sorbian',
            11274 	:  'Spanish Argentina',
            16394 	:  'Spanish Bolivia',
            13322 	:  'Spanish Chile',
            9226 	:  'Spanish Colombia',
            5130 	:  'Spanish Costa Rica',
            7178 	:  'Spanish Dominican Republic',
            12298 	:  'Spanish Ecuador',
            17418 	:  'Spanish El Salvador',
            4106 	:  'Spanish Guatemala',
            18442 	:  'Spanish Honduras',
            2058 	:  'Spanish Mexico',
            3082 	:  'Spanish Modern',
            19466 	:  'Spanish Nicaragua',
            6154 	:  'Spanish Panama',
            15370 	:  'Spanish Paraguay',
            10250 	:  'Spanish Peru',
            20490 	:  'Spanish Puerto Rico',
            1034 	:  'Spanish Traditional',
            14346 	:  'Spanish Uruguay',
            8202 	:  'Spanish Venezuela',
            1072 	:  'Sutu',
            1089 	:  'Swahili',
            1053 	:  'Swedish',
            2077 	:  'Swedish Finland',
            1064 	:  'Tajik',
            1097 	:  'Tamil',
            1092 	:  'Tatar',
            1098 	:  'Telugu',
            1054 	:  'Thai',
            1105 	:  'Tibetan',
            1073 	:  'Tsonga',
            1074 	:  'Tswana',
            1055 	:  'Turkish',
            1090 	:  'Turkmen',
            1058 	:  'Ukranian',
            1056 	:  'Urdu',
            2080 	:  'Urdu India',
            2115 	:  'Uzbek Cyrillic',
            1091 	:  'Uzbek Latin',
            1075 	:  'Venda',
            1066 	:  'Vietnamese',
            1106 	:  'Welsh',
            1076 	:  'Xhosa',
            1085 	:  'Yiddish',
            1077 	:  'Zulu',
            1024 	:  'Unkown',
            255 	:  'Unkown',
        }
    """
        # unknown
        # These must get passed on because they occurred after \\*
        'do'                :   ('un', 'unknown___', self.default_func),
        'company'           :	('un', 'company___', self.default_func),
        'shpinst'           :   ('un', 'unknown___', self.default_func),
        'panose'            :   ('un', 'unknown___', self.default_func),
        'falt'              :   ('un', 'unknown___', self.default_func),
        'listoverridetable' :   ('un', 'unknown___', self.default_func),
        'category'          :   ('un', 'unknown___', self.default_func),
        'template'          :   ('un', 'unknown___', self.default_func),
        'ud'                :   ('un', 'unknown___', self.default_func),
        'formfield'         :   ('un', 'unknown___', self.default_func),
        'ts'                :   ('un', 'unknown___', self.default_func),
        'rsidtbl'           :   ('un', 'unknown___', self.default_func),
        'generator'         :   ('un', 'unknown___', self.default_func),
        'ftnsep'            :   ('un', 'unknown___', self.default_func),
        'aftnsep'           :   ('un', 'unknown___', self.default_func),
        'aftnsepc'           :   ('un', 'unknown___', self.default_func),
        'aftncn'            :   ('un', 'unknown___', self.default_func),
        'objclass'           :   ('un', 'unknown___', self.default_func),
        'objdata'           :   ('un', 'unknown___', self.default_func),
        'picprop'           :   ('un', 'unknown___', self.default_func),
        'blipuid'           :   ('un', 'unknown___', self.default_func),
    """

    def __ms_hex_func(self, pre, token, num):
        num = num[1:]  # chop off leading 0, which I added
        num = num.upper()  # the mappings store hex in caps
        return 'tx<hx<__________<\'%s\n' % num  # add an ' for the mappings

    def ms_sub_func(self, pre, token, num):
        return 'tx<mc<__________<%s\n' % token

    def direct_conv_func(self, pre, token, num):
        return 'mi<tg<empty_____<%s\n' % token

    def default_func(self, pre, token, num):
        if num is None:
            num = 'true'
        return f'cw<{pre}<{token}<nu<{num}\n'

    def colorz_func(self, pre, token, num):
        if num is None:
            num = '0'
        return f'cw<{pre}<{token}<nu<{num}\n'

    def __list_type_func(self, pre, token, num):
        type = 'arabic'
        if num is None:
            type = 'Arabic'
        else:
            try:
                num = int(num)
            except ValueError:
                if self.__run_level > 3:
                    msg = 'Number "%s" cannot be converted to integer\n' % num
                    raise self.__bug_handler(msg)
            type = self.__number_type_dict.get(num)
            if type is None:
                if self.__run_level > 3:
                    msg = 'No type for "%s" in self.__number_type_dict\n'
                    raise self.__bug_handler
                type = 'Arabic'
        return f'cw<{pre}<{token}<nu<{type}\n'

    def __language_func(self, pre, token, num):
        lang_name = self.__language_dict.get(int(re.search('[0-9]+', num).group()))
        if not lang_name:
            lang_name = "not defined"
            if self.__run_level > 3:
                msg = 'No entry for number "%s"' % num
                raise self.__bug_handler(msg)
        return f'cw<{pre}<{token}<nu<{lang_name}\n'

    def two_part_func(self, pre, token, num):
        list = token.split("<")
        token = list[0]
        num = list[1]
        return f'cw<{pre}<{token}<nu<{num}\n'
        # return 'cw<nu<nu<nu<%s>num<%s\n' % (token, num)

    def divide_by_2(self, pre, token, num):
        num = self.divide_num(num, 2)
        return f'cw<{pre}<{token}<nu<{num}\n'
        # return 'cw<nu<nu<nu<%s>%s<%s\n' % (token, num, token)

    def divide_by_20(self, pre, token, num):
        num = self.divide_num(num, 20)
        return f'cw<{pre}<{token}<nu<{num}\n'
        # return 'cw<nu<nu<nu<%s>%s<%s\n' % (token, num, token)

    def text_func(self, pre, token, num=None):
        return 'tx<nu<__________<%s\n' % token

    def ob_func(self, pre, token, num=None):
        self.__bracket_count += 1
        return 'ob<nu<open-brack<%04d\n' % self.__bracket_count

    def cb_func(self, pre, token, num=None):
        line = 'cb<nu<clos-brack<%04d\n' % self.__bracket_count
        self.__bracket_count -= 1
        return line

    def color_func(self, pre, token, num):
        third_field = 'nu'
        if num[-1] == ';':
            num = num[:-1]
            third_field = 'en'
        num = '%X' % int(num)
        if len(num) != 2:
            num = "0" + num
        return f'cw<{pre}<{token}<{third_field}<{num}\n'
        # return 'cw<cl<%s<nu<nu<%s>%s<%s\n' % (third_field, token, num, token)

    def bool_st_func(self, pre, token, num):
        if num is None or num == '' or num == '1':
            return f'cw<{pre}<{token}<nu<true\n'
            # return 'cw<nu<nu<nu<%s>true<%s\n' % (token, token)
        elif num == '0':
            return f'cw<{pre}<{token}<nu<false\n'
            # return 'cw<nu<nu<nu<%s>false<%s\n' % (token, token)
        else:
            msg = f"boolean should have some value module process tokens\ntoken is {token}\n'{num}'\n"
            raise self.__bug_handler(msg)

    def __no_sup_sub_func(self, pre, token, num):
        the_string = 'cw<ci<subscript_<nu<false\n'
        the_string += 'cw<ci<superscrip<nu<false\n'
        return the_string

    def divide_num(self, numerator, denominator):
        try:
            # calibre why ignore negative number? Wrong in case of \fi
            numerator = float(re.search('[0-9.\\-]+', numerator).group())
        except TypeError as msg:
            if self.__run_level > 3:
                msg = ('No number to process?\nthis indicates that the token \\(\\li\\) \
                should have a number and does not\nnumerator is \
                "%s"\ndenominator is "%s"\n') % (numerator, denominator)
                raise self.__bug_handler(msg)
            if 5 > self.__return_code:
                self.__return_code = 5
            return 0
        num = '%0.2f' % round(numerator/denominator, 2)
        return num
        string_num = str(num)
        if string_num[-2:] == ".0":
            string_num = string_num[:-2]
        return string_num

    def split_let_num(self, token):
        match_obj = re.search(self.__num_exp,token)
        if match_obj is not None:
            first = match_obj.group(1)
            second = match_obj.group(2)
            if not second:
                if self.__run_level > 3:
                    msg = "token is '%s' \n" % token
                    raise self.__bug_handler(msg)
                return first, 0
        else:
            if self.__run_level > 3:
                msg = "token is '%s' \n" % token
                raise self.__bug_handler
            return token, 0
        return first, second

    def convert_to_hex(self,number):
        """Convert a string to uppercase hexadecimal"""
        num = int(number)
        try:
            hex_num = "%X" % num
            return hex_num
        except:
            raise self.__bug_handler

    def process_cw(self, token):
        """Change the value of the control word by determining what dictionary
        it belongs to"""
        special = ['*', ':', '}', '{', '~', '_', '-', ';']
        # if token != "{" or token != "}":
        token = token[1:]  # strip off leading \
        token = token.replace(" ", "")
        # if not token: return
        only_alpha = token.isalpha()
        num = None
        if not only_alpha and token not in special:
            token, num = self.split_let_num(token)
        pre, token, action = self.dict_token.get(token, (None, None, None))
        if action:
            return action(pre, token, num)

    def __check_brackets(self, in_file):
        self.__check_brack_obj = check_brackets.CheckBrackets(file=in_file)
        good_br =  self.__check_brack_obj.check_brackets()[0]
        if not good_br:
            return 1

    def process_tokens(self):
        """Main method for handling other methods. """
        line_count = 0
        with open_for_read(self.__file) as read_obj:
            with open_for_write(self.__write_to) as write_obj:
                for line in read_obj:
                    token = line.replace("\n", "")
                    line_count += 1
                    if line_count == 1 and token != '\\{':
                        msg = '\nInvalid RTF: document doesn\'t start with {\n'
                        raise self.__exception_handler(msg)
                    elif line_count == 2 and token[0:4] != '\\rtf':
                        msg = '\nInvalid RTF: document doesn\'t start with \\rtf \n'
                        raise self.__exception_handler(msg)

                    the_index = token.find('\\ ')
                    if token is not None and the_index > -1:
                        msg = '\nInvalid RTF: token "\\ " not valid.\nError at line %d'\
                            % line_count
                        raise self.__exception_handler(msg)
                    elif token[:1] == "\\":
                        line = self.process_cw(token)
                        if line is not None:
                            write_obj.write(line)
                    else:
                        fields = re.split(self.__utf_exp, token)
                        for field in fields:
                            if not field:
                                continue
                            if field[0:1] == '&':
                                write_obj.write('tx<ut<__________<%s\n' % field)
                            else:
                                write_obj.write('tx<nu<__________<%s\n' % field)

        if not line_count:
            msg = '\nInvalid RTF: file appears to be empty.\n'
            raise self.__exception_handler(msg)

        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "processed_tokens.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)

        bad_brackets = self.__check_brackets(self.__file)
        if bad_brackets:
            msg = '\nInvalid RTF: document does not have matching brackets.\n'
            raise self.__exception_handler(msg)
        else:
            return self.__return_code
