__license__ = 'GPL 3'
__copyright__ = '2011, Leigh Parry <leighparry@blueyonder.co.uk>'
__docformat__ = 'restructuredtext en'

import re


def unsmarten(txt):
    txt = re.sub(r'&#162;|&cent;|¢',     r'{c\}',  txt)  # cent
    txt = re.sub(r'&#163;|&pound;|£',    r'{L-}',  txt)  # pound
    txt = re.sub(r'&#165;|&yen;|¥',      r'{Y=}',  txt)  # yen
    txt = re.sub(r'&#169;|&copy;|©',     r'{(c)}', txt)  # copyright
    txt = re.sub(r'&#174;|&reg;|®',      r'{(r)}', txt)  # registered
    txt = re.sub(r'&#188;|&frac14;|¼',   r'{1/4}', txt)  # quarter
    txt = re.sub(r'&#189;|&frac12;|½',   r'{1/2}', txt)  # half
    txt = re.sub(r'&#190;|&frac34;|¾',   r'{3/4}', txt)  # three-quarter
    txt = re.sub(r'&#192;|&Agrave;|À',   r'{A`)}', txt)  # A-grave
    txt = re.sub(r'&#193;|&Aacute;|Á',   r"{A'}",  txt)  # A-acute
    txt = re.sub(r'&#194;|&Acirc;|Â',    r'{A^}',  txt)  # A-circumflex
    txt = re.sub(r'&#195;|&Atilde;|Ã',   r'{A~}',  txt)  # A-tilde
    txt = re.sub(r'&#196;|&Auml;|Ä',     r'{A"}',  txt)  # A-umlaut
    txt = re.sub(r'&#197;|&Aring;|Å',    r'{Ao}',  txt)  # A-ring
    txt = re.sub(r'&#198;|&AElig;|Æ',    r'{AE}',  txt)  # AE
    txt = re.sub(r'&#199;|&Ccedil;|Ç',   r'{C,}',  txt)  # C-cedilla
    txt = re.sub(r'&#200;|&Egrave;|È',   r'{E`}',  txt)  # E-grave
    txt = re.sub(r'&#201;|&Eacute;|É',   r"{E'}",  txt)  # E-acute
    txt = re.sub(r'&#202;|&Ecirc;|Ê',    r'{E^}',  txt)  # E-circumflex
    txt = re.sub(r'&#203;|&Euml;|Ë',     r'{E"}',  txt)  # E-umlaut
    txt = re.sub(r'&#204;|&Igrave;|Ì',   r'{I`}',  txt)  # I-grave
    txt = re.sub(r'&#205;|&Iacute;|Í',   r"{I'}",  txt)  # I-acute
    txt = re.sub(r'&#206;|&Icirc;|Î',    r'{I^}',  txt)  # I-circumflex
    txt = re.sub(r'&#207;|&Iuml;|Ï',     r'{I"}',  txt)  # I-umlaut
    txt = re.sub(r'&#208;|&ETH;|Ð',      r'{D-}',  txt)  # ETH
    txt = re.sub(r'&#209;|&Ntilde;|Ñ',   r'{N~}',  txt)  # N-tilde
    txt = re.sub(r'&#210;|&Ograve;|Ò',   r'{O`}',  txt)  # O-grave
    txt = re.sub(r'&#211;|&Oacute;|Ó',   r"{O'}",  txt)  # O-acute
    txt = re.sub(r'&#212;|&Ocirc;|Ô',    r'{O^}',  txt)  # O-circumflex
    txt = re.sub(r'&#213;|&Otilde;|Õ',   r'{O~}',  txt)  # O-tilde
    txt = re.sub(r'&#214;|&Ouml;|Ö',     r'{O"}',  txt)  # O-umlaut
    txt = re.sub(r'&#215;|&times;|×',    r'{x}',   txt)  # dimension
    txt = re.sub(r'&#216;|&Oslash;|Ø',   r'{O/}',  txt)  # O-slash
    txt = re.sub(r'&#217;|&Ugrave;|Ù',   r'{U`}',  txt)  # U-grave
    txt = re.sub(r'&#218;|&Uacute;|Ú',   r"{U'}",  txt)  # U-acute
    txt = re.sub(r'&#219;|&Ucirc;|Û',    r'{U^}',  txt)  # U-circumflex
    txt = re.sub(r'&#220;|&Uuml;|Ü',     r'{U"}',  txt)  # U-umlaut
    txt = re.sub(r'&#221;|&Yacute;|Ý',   r"{Y'}",  txt)  # Y-grave
    txt = re.sub(r'&#223;|&szlig;|ß',    r'{sz}',  txt)  # sharp-s
    txt = re.sub(r'&#224;|&agrave;|à',   r'{a`}',  txt)  # a-grave
    txt = re.sub(r'&#225;|&aacute;|á',   r"{a'}",  txt)  # a-acute
    txt = re.sub(r'&#226;|&acirc;|â',    r'{a^}',  txt)  # a-circumflex
    txt = re.sub(r'&#227;|&atilde;|ã',   r'{a~}',  txt)  # a-tilde
    txt = re.sub(r'&#228;|&auml;|ä',     r'{a"}',  txt)  # a-umlaut
    txt = re.sub(r'&#229;|&aring;|å',    r'{ao}',  txt)  # a-ring
    txt = re.sub(r'&#230;|&aelig;|æ',    r'{ae}',  txt)  # ae
    txt = re.sub(r'&#231;|&ccedil;|ç',   r'{c,}',  txt)  # c-cedilla
    txt = re.sub(r'&#232;|&egrave;|è',   r'{e`}',  txt)  # e-grave
    txt = re.sub(r'&#233;|&eacute;|é',   r"{e'}",  txt)  # e-acute
    txt = re.sub(r'&#234;|&ecirc;|ê',    r'{e^}',  txt)  # e-circumflex
    txt = re.sub(r'&#235;|&euml;|ë',     r'{e"}',  txt)  # e-umlaut
    txt = re.sub(r'&#236;|&igrave;|ì',   r'{i`}',  txt)  # i-grave
    txt = re.sub(r'&#237;|&iacute;|í',   r"{i'}",  txt)  # i-acute
    txt = re.sub(r'&#238;|&icirc;|î',    r'{i^}',  txt)  # i-circumflex
    txt = re.sub(r'&#239;|&iuml;|ï',     r'{i"}',  txt)  # i-umlaut
    txt = re.sub(r'&#240;|&eth;|ð',      r'{d-}',  txt)  # eth
    txt = re.sub(r'&#241;|&ntilde;|ñ',   r'{n~}',  txt)  # n-tilde
    txt = re.sub(r'&#242;|&ograve;|ò',   r'{o`}',  txt)  # o-grave
    txt = re.sub(r'&#243;|&oacute;|ó',   r"{o'}",  txt)  # o-acute
    txt = re.sub(r'&#244;|&ocirc;|ô',    r'{o^}',  txt)  # o-circumflex
    txt = re.sub(r'&#245;|&otilde;|õ',   r'{o~}',  txt)  # o-tilde
    txt = re.sub(r'&#246;|&ouml;|ö',     r'{o"}',  txt)  # o-umlaut
    txt = re.sub(r'&#248;|&oslash;|ø',   r'{o/}',  txt)  # o-stroke
    txt = re.sub(r'&#249;|&ugrave;|ù',   r'{u`}',  txt)  # u-grave
    txt = re.sub(r'&#250;|&uacute;|ú',   r"{u'}",  txt)  # u-acute
    txt = re.sub(r'&#251;|&ucirc;|û',    r'{u^}',  txt)  # u-circumflex
    txt = re.sub(r'&#252;|&uuml;|ü',     r'{u"}',  txt)  # u-umlaut
    txt = re.sub(r'&#253;|&yacute;|ý',   r"{y'}",  txt)  # y-acute
    txt = re.sub(r'&#255;|&yuml;|ÿ',     r'{y"}',  txt)  # y-umlaut

    txt = re.sub(r'&#268;|&Ccaron;|Č',   r'{Cˇ}',  txt)  # C-caron
    txt = re.sub(r'&#269;|&ccaron;|č',   r'{cˇ}',  txt)  # c-caron
    txt = re.sub(r'&#270;|&Dcaron;|Ď',   r'{Dˇ}',  txt)  # D-caron
    txt = re.sub(r'&#271;|&dcaron;|ď',   r'{dˇ}',  txt)  # d-caron
    txt = re.sub(r'&#282;|&Ecaron;|Ě',   r'{Eˇ}',  txt)  # E-caron
    txt = re.sub(r'&#283;|&ecaron;|ě',   r'{eˇ}',  txt)  # e-caron
    txt = re.sub(r'&#313;|&Lacute;|Ĺ',   r"{L'}",  txt)  # L-acute
    txt = re.sub(r'&#314;|&lacute;|ĺ',   r"{l'}",  txt)  # l-acute
    txt = re.sub(r'&#317;|&Lcaron;|Ľ',   r'{Lˇ}',  txt)  # L-caron
    txt = re.sub(r'&#318;|&lcaron;|ľ',   r'{lˇ}',  txt)  # l-caron
    txt = re.sub(r'&#327;|&Ncaron;|Ň',   r'{Nˇ}',  txt)  # N-caron
    txt = re.sub(r'&#328;|&ncaron;|ň',   r'{nˇ}',  txt)  # n-caron

    txt = re.sub(r'&#338;|&OElig;|Œ',    r'{OE}',  txt)  # OE
    txt = re.sub(r'&#339;|&oelig;|œ',    r'{oe}',  txt)  # oe

    txt = re.sub(r'&#340;|&Racute;|Ŕ',   r"{R'}",  txt)  # R-acute
    txt = re.sub(r'&#341;|&racute;|ŕ',   r"{r'}",  txt)  # r-acute
    txt = re.sub(r'&#344;|&Rcaron;|Ř',   r'{Rˇ}',  txt)  # R-caron
    txt = re.sub(r'&#345;|&rcaron;|ř',   r'{rˇ}',  txt)  # r-caron
    txt = re.sub(r'&#348;|Ŝ',            r'{S^}',  txt)  # S-circumflex
    txt = re.sub(r'&#349;|ŝ',            r'{s^}',  txt)  # s-circumflex
    txt = re.sub(r'&#352;|&Scaron;|Š',   r'{Sˇ}',  txt)  # S-caron
    txt = re.sub(r'&#353;|&scaron;|š',   r'{sˇ}',  txt)  # s-caron
    txt = re.sub(r'&#356;|&Tcaron;|Ť',   r'{Tˇ}',  txt)  # T-caron
    txt = re.sub(r'&#357;|&tcaron;|ť',   r'{tˇ}',  txt)  # t-caron
    txt = re.sub(r'&#366;|&Uring;|Ů',    r'{U°}',  txt)  # U-ring
    txt = re.sub(r'&#367;|&uring;|ů',    r'{u°}',  txt)  # u-ring
    txt = re.sub(r'&#381;|&Zcaron;|Ž',   r'{Zˇ}',  txt)  # Z-caron
    txt = re.sub(r'&#382;|&zcaron;|ž',   r'{zˇ}',  txt)  # z-caron

    txt = re.sub(r'&#8226;|&bull;|•',    r'{*}',   txt)  # bullet
    txt = re.sub(r'&#8355;|₣',           r'{Fr}',  txt)  # Franc
    txt = re.sub(r'&#8356;|₤',           r'{L=}',  txt)  # Lira
    txt = re.sub(r'&#8360;|₨',           r'{Rs}',  txt)  # Rupee
    txt = re.sub(r'&#8364;|&euro;|€',    r'{C=}',  txt)  # euro
    txt = re.sub(r'&#8482;|&trade;|™',   r'{tm}',  txt)  # trademark
    txt = re.sub(r'&#9824;|&spades;|♠',  r'{spade}',   txt)  # spade
    txt = re.sub(r'&#9827;|&clubs;|♣',   r'{club}',    txt)  # club
    txt = re.sub(r'&#9829;|&hearts;|♥',  r'{heart}',   txt)  # heart
    txt = re.sub(r'&#9830;|&diams;|♦',   r'{diamond}', txt)  # diamond

    # Move into main code?
    # txt = re.sub(r'\xa0',     r'p. ',         txt)  # blank paragraph
    # txt = re.sub(r'\n\n\n\n', r'\n\np. \n\n', txt)  # blank paragraph
    # txt = re.sub(r'\n  \n',   r'\n<br />\n',  txt)  # blank paragraph - br tag

    return txt
