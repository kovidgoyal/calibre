# -*- coding: utf-8 -*-

"""unsmarten : html2textile helper function"""

__version__ = '0.1'
__author__ = 'Leigh Parry'

import re

def unsmarten(txt):
    txt = re.sub(u'&#8211;|&ndash;|–', r'-', txt) # en-dash
    txt = re.sub(u'&#8212;|&mdash;|—', r'--', txt) # em-dash
    txt = re.sub(u'&#8230;|&hellip;|…', r'...', txt) # ellipsis

    txt = re.sub(u'&#8220;|&#8221;|&#8243;|&ldquo;|&rdquo;|&Prime;|“|”|″', r'"', txt)  # double quote
    txt = re.sub(u'(["\'‘“]|\s)’', r"\1{'/}", txt)  # apostrophe
    txt = re.sub(u'&#8216;|&#8217;|&#8242;|&lsquo;|&rsquo;|&prime;|‘|’|′', r"'", txt)  # single quote

    txt = re.sub(u'&#162;|&cent;|¢',     r'{c\}',  txt)  # cent
    txt = re.sub(u'&#163;|&pound;|£',    r'{L-}',  txt)  # pound
    txt = re.sub(u'&#165;|&yen;|¥',      r'{Y=}',  txt)  # yen
    txt = re.sub(u'&#169;|&copy;|©',     r'{(c)}', txt)  # copyright
    txt = re.sub(u'&#174;|&reg;|®',      r'{(r)}', txt)  # registered
    txt = re.sub(u'&#188;|&frac14;|¼',   r'{1/4}', txt)  # quarter
    txt = re.sub(u'&#189;|&frac12;|½',   r'{1/2}', txt)  # half
    txt = re.sub(u'&#190;|&frac34;|¾',   r'{3/4}', txt)  # three-quarter
    txt = re.sub(u'&#192;|&Agrave;|À',   r'{A`)}', txt)  # A-grave
    txt = re.sub(u'&#193;|&Aacute;|Á',   r"{A'}",  txt)  # A-acute
    txt = re.sub(u'&#194;|&Acirc;|Â',    r'{A^}', txt)  # A-circumflex
    txt = re.sub(u'&#195;|&Atilde;|Ã',   r'{A~}',  txt)  # A-tilde
    txt = re.sub(u'&#196;|&Auml;|Ä',     r'{A"}',  txt)  # A-umlaut
    txt = re.sub(u'&#197;|&Aring;|Å',    r'{Ao}',  txt)  # A-ring
    txt = re.sub(u'&#198;|&AElig;|Æ',    r'{AE}',  txt)  # AE
    txt = re.sub(u'&#199;|&Ccedil;|Ç',   r'{C,}',  txt)  # C-cedilla
    txt = re.sub(u'&#200;|&Egrave;|È',   r'{E`}',  txt)  # E-grave
    txt = re.sub(u'&#201;|&Eacute;|É',   r"{E'}",  txt)  # E-acute
    txt = re.sub(u'&#202;|&Ecirc;|Ê',    r'{E^}', txt)  # E-circumflex
    txt = re.sub(u'&#203;|&Euml;|Ë',     r'{E"}',  txt)  # E-umlaut
    txt = re.sub(u'&#204;|&Igrave;|Ì',   r'{I`}',  txt)  # I-grave
    txt = re.sub(u'&#205;|&Iacute;|Í',   r"{I'}",  txt)  # I-acute
    txt = re.sub(u'&#206;|&Icirc;|Î',    r'{I^}', txt)  # I-circumflex
    txt = re.sub(u'&#207;|&Iuml;|Ï',     r'{I"}',  txt)  # I-umlaut
    txt = re.sub(u'&#208;|&ETH;|Ð',      r'{D-}',  txt)  # ETH
    txt = re.sub(u'&#209;|&Ntilde;|Ñ',   r'{N~}',  txt)  # N-tilde
    txt = re.sub(u'&#210;|&Ograve;|Ò',   r'{O`}',  txt)  # O-grave
    txt = re.sub(u'&#211;|&Oacute;|Ó',   r"{O'}",  txt)  # O-acute
    txt = re.sub(u'&#212;|&Ocirc;|Ô',    r'{O^}', txt)  # O-circumflex
    txt = re.sub(u'&#213;|&Otilde;|Õ',   r'{O~}',  txt)  # O-tilde
    txt = re.sub(u'&#214;|&Ouml;|Ö',     r'{O"}',  txt)  # O-umlaut
    txt = re.sub(u'&#215;|&times;|×',    r'{x}',   txt)  # dimension
    txt = re.sub(u'&#216;|&Oslash;|Ø',   r'{O/}',  txt)  # O-slash
    txt = re.sub(u'&#217;|&Ugrave;|Ù',   r"{U`}",  txt)  # U-grave
    txt = re.sub(u'&#218;|&Uacute;|Ú',   r"{U'}",  txt)  # U-acute
    txt = re.sub(u'&#219;|&Ucirc;|Û',    r'{U^}', txt)  # U-circumflex
    txt = re.sub(u'&#220;|&Uuml;|Ü',     r'{U"}',  txt)  # U-umlaut
    txt = re.sub(u'&#221;|&Yacute;|Ý',   r"{Y'}",  txt)  # Y-grave
    txt = re.sub(u'&#223;|&szlig;|ß',    r'{sz}',  txt)  # sharp-s
    txt = re.sub(u'&#224;|&agrave;|à',   r'{a`}',  txt)  # a-grave
    txt = re.sub(u'&#225;|&aacute;|á',   r"{a'}",  txt)  # a-acute
    txt = re.sub(u'&#226;|&acirc;|â',    r'{a^}', txt)  # a-circumflex
    txt = re.sub(u'&#227;|&atilde;|ã',   r'{a~}',  txt)  # a-tilde
    txt = re.sub(u'&#228;|&auml;|ä',     r'{a"}',  txt)  # a-umlaut
    txt = re.sub(u'&#229;|&aring;|å',    r'{ao}',  txt)  # a-ring
    txt = re.sub(u'&#230;|&aelig;|æ',    r'{ae}',  txt)  # ae
    txt = re.sub(u'&#231;|&ccedil;|ç',   r'{c,}',  txt)  # c-cedilla
    txt = re.sub(u'&#232;|&egrave;|è',   r'{e`}',  txt)  # e-grave
    txt = re.sub(u'&#233;|&eacute;|é',   r"{e'}",  txt)  # e-acute
    txt = re.sub(u'&#234;|&ecirc;|ê',    r'{e^}', txt)  # e-circumflex
    txt = re.sub(u'&#235;|&euml;|ë',     r'{e"}',  txt)  # e-umlaut
    txt = re.sub(u'&#236;|&igrave;|ì',   r'{i`}',  txt)  # i-grave
    txt = re.sub(u'&#237;|&iacute;|í',   r"{i'}",  txt)  # i-acute
    txt = re.sub(u'&#238;|&icirc;|î',    r'{i^}', txt)  # i-circumflex
    txt = re.sub(u'&#239;|&iuml;|ï',     r'{i"}',  txt)  # i-umlaut
    txt = re.sub(u'&#240;|&eth;|ð',      r'{d-}',  txt)  # eth
    txt = re.sub(u'&#241;|&ntilde;|ñ',   r'{n~}',  txt)  # n-tilde
    txt = re.sub(u'&#242;|&ograve;|ò',   r'{o`}',  txt)  # o-grave
    txt = re.sub(u'&#243;|&oacute;|ó',   r"{o'}",  txt)  # o-acute
    txt = re.sub(u'&#244;|&ocirc;|ô',    r'{o^}', txt)  # o-circumflex
    txt = re.sub(u'&#245;|&otilde;|õ',   r'{o~}',  txt)  # o-tilde
    txt = re.sub(u'&#246;|&ouml;|ö',     r'{o"}',  txt)  # o-umlaut
    txt = re.sub(u'&#248;|&oslash;|ø',   r'{o/}',  txt)  # o-stroke
    txt = re.sub(u'&#249;|&ugrave;|ù',   r'{u`}',  txt)  # u-grave
    txt = re.sub(u'&#250;|&uacute;|ú',   r"{u'}",  txt)  # u-acute
    txt = re.sub(u'&#251;|&ucirc;|û',    r'{u^}', txt)  # u-circumflex
    txt = re.sub(u'&#252;|&uuml;|ü',     r'{u"}',  txt)  # u-umlaut
    txt = re.sub(u'&#253;|&yacute;|ý',   r"{y'}",  txt)  # y-acute
    txt = re.sub(u'&#255;|&yuml;|ÿ',     r'{y"}',  txt)  # y-umlaut
    txt = re.sub(u'&#338;|&OElig;|Œ',    r'{OE}',  txt)  # OE
    txt = re.sub(u'&#339;|&oelig;|œ',    r'{oe}',  txt)  # oe
    txt = re.sub(u'&#348;|&Scaron;|Ŝ',   r'{S^}', txt)  # Scaron
    txt = re.sub(u'&#349;|&scaron;|ŝ',   r'{s^}', txt)  # scaron
    txt = re.sub(u'&#8226;|&bull;|•',    r'{*}',   txt)  # bullet
    txt = re.sub(u'&#8355;|₣',           r'{Fr}',  txt)  # Franc
    txt = re.sub(u'&#8356;|₤',           r'{L=}',  txt)  # Lira
    txt = re.sub(u'&#8360;|₨',           r'{Rs}',  txt)  # Rupee
    txt = re.sub(u'&#8364;|&euro;|€',    r'{C=}',  txt)  # euro
    txt = re.sub(u'&#8482;|&trade;|™',   r'{tm}',  txt)  # trademark
    txt = re.sub(u'&#9824;|&spades;|♠',  r'{spade}',   txt)  # spade
    txt = re.sub(u'&#9827;|&clubs;|♣',   r'{club}',    txt)  # club
    txt = re.sub(u'&#9829;|&hearts;|♥',  r'{heart}',   txt)  # heart
    txt = re.sub(u'&#9830;|&diams;|♦',   r'{diamond}', txt)  # diamond

    # Move into main code?
#    txt = re.sub(u'\xa0',   r'p. ', txt)              # blank paragraph
#    txt = re.sub(u'\n\n\n\n',   r'\n\np. \n\n', txt)  # blank paragraph
#    txt = re.sub(u'\n  \n',   r'\n<br />\n', txt)     # blank paragraph - br tag

    return txt
