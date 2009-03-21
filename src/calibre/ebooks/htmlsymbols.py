# -*- coding: utf-8 -*-
'''
Maping of non-acii symbols and their corresponding html entity number and name
'''
__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'

# http://www.w3schools.com/tags/ref_symbols.asp
HTML_SYMBOLS = {
                # Math Symbols
                u'∀' : ['&#8704;', '&forall;'], # for all
                u'∂' : ['&#8706;', '&part;'], # part
                u'∃' : ['&#8707;', '&exists;'], # exists
                u'∅' : ['&#8709;', '&empty;'], # empty
                u'∇' : ['&#8711;', '&nabla;'], # nabla
                u'∈' : ['&#8712;', '&isin;'], # isin
                u'∉' : ['&#8713;', '&notin;'], # notin
                u'∋' : ['&#8715;', '&ni;'], # ni
                u'∏' : ['&#8719;', '&prod;'], # prod
                u'∑' : ['&#8721;', '&sum;'], # sum
                u'−' : ['&#8722;', '&minus;'], # minus
                u'∗' : ['&#8727;', '&lowast;'], # lowast
                u'√' : ['&#8730;', '&radic;'], # square root
                u'∝' : ['&#8733;', '&prop;'], # proportional to
                u'∞' : ['&#8734;', '&infin;'], # infinity
                u'∠' : ['&#8736;', '&ang;'], # angle
                u'∧' : ['&#8743;', '&and;'], # and
                u'∨' : ['&#8744;', '&or;'], # or
                u'∩' : ['&#8745;', '&cap;'], # cap
                u'∪' : ['&#8746;', '&cup;'], # cup
                u'∫' : ['&#8747;', '&int;'], # integral
                u'∴' : ['&#8756;', '&there4;'], # therefore
                u'∼' : ['&#8764;', '&sim;'], # simular to
                u'≅' : ['&#8773;', '&cong;'], # approximately equal
                u'≈' : ['&#8776;', '&asymp;'], # almost equal
                u'≠' : ['&#8800;', '&ne;'], # not equal
                u'≡' : ['&#8801;', '&equiv;'], # equivalent
                u'≤' : ['&#8804;', '&le;'], # less or equal
                u'≥' : ['&#8805;', '&ge;'], # greater or equal
                u'⊂' : ['&#8834;', '&sub;'], # subset of
                u'⊃' : ['&#8835;', '&sup;'], # superset of
                u'⊄' : ['&#8836;', '&nsub;'], # not subset of
                u'⊆' : ['&#8838;', '&sube;'], # subset or equal
                u'⊇' : ['&#8839;', '&supe;'], # superset or equal
                u'⊕' : ['&#8853;', '&oplus;'], # circled plus
                u'⊗' : ['&#8855;', '&otimes;'], # cirled times
                u'⊥' : ['&#8869;', '&perp;'], # perpendicular
                u'⋅' : ['&#8901;', '&sdot;'], # dot operator
                # Greek Letters
                u'Α' : ['&#913;', '&Alpha;'], # Alpha
                u'Β' : ['&#914;', '&Beta;'], # Beta
                u'Γ' : ['&#915;', '&Gamma;'], # Gamma
                u'Δ' : ['&#916;', '&Delta;'], # Delta
                u'Ε' : ['&#917;', '&Epsilon;'], # Epsilon
                u'Ζ' : ['&#918;', '&Zeta;'], # Zeta
                u'Η' : ['&#919;', '&Eta;'], # Eta
                u'Θ' : ['&#920;', '&Theta;'], # Theta
                u'Ι' : ['&#921;', '&Iota;'], # Iota
                u'Κ' : ['&#922;', '&Kappa;'], # Kappa
                u'Λ' : ['&#923;', '&Lambda;'], # Lambda
                u'Μ' : ['&#924;', '&Mu;'], # Mu
                u'Ν' : ['&#925;', '&Nu;'], # Nu
                u'Ξ' : ['&#926;', '&Xi;'], # Xi
                u'Ο' : ['&#927;', '&Omicron;'], # Omicron
                u'Π' : ['&#928;', '&Pi;'], # Pi
                u'Ρ' : ['&#929;', '&Rho;'], # Rho
                u'Σ' : ['&#931;', '&Sigma;'], # Sigma
                u'Τ' : ['&#932;', '&Tau;'], # Tau
                u'Υ' : ['&#933;', '&Upsilon;'], # Upsilon
                u'Φ' : ['&#934;', '&Phi;'], # Phi
                u'Χ' : ['&#935;', '&Chi;'], # Chi
                u'Ψ' : ['&#936;', '&Psi;'], # Psi
                u'ω' : ['&#969;', '&omega;'], # omega
                u'ϑ' : ['&#977;', '&thetasym;'], # theta symbol
                u'ϒ' : ['&#978;', '&upsih;'], # upsilon symbol
                u'ϖ' : ['&#982;', '&piv;'], # pi symbol
                # Other
                u'Œ' : ['&#338;', '&OElig;'], # capital ligature OE
                u'œ' : ['&#339;', '&oelig;'], # small ligature oe
                u'Š' : ['&#352;', '&Scaron;'], # capital S with caron
                u'š' : ['&#353;', '&scaron;'], # small S with caron
                u'Ÿ' : ['&#376;', '&Yuml;'], # capital Y with diaeres
                u'ƒ' : ['&#402;', '&fnof;'], # f with hook
                u'ˆ' : ['&#710;', '&circ;'], # modifier letter circumflex accent
                u'˜' : ['&#732;', '&tilde;'], # small tilde
                u'–' : ['&#8211;', '&ndash;'], # en dash
                u'—' : ['&#8212;', '&mdash;'], # em dash
                u'‘' : ['&#8216;', '&lsquo;'], # left single quotation mark
                u'’' : ['&#8217;', '&rsquo;'], # right single quotation mark
                u'‚' : ['&#8218;', '&sbquo;'], # single low-9 quotation mark
                u'“' : ['&#8220;', '&ldquo;'], # left double quotation mark
                u'”' : ['&#8221;', '&rdquo;'], # right double quotation mark
                u'„' : ['&#8222;', '&bdquo;'], # double low-9 quotation mark
                u'†' : ['&#8224;', '&dagger;'], # dagger
                u'‡' : ['&#8225;', '&Dagger;'], # double dagger
                u'•' : ['&#8226;', '&bull;'], # bullet
                u'…' : ['&#8230;', '&hellip;'], # horizontal ellipsis
                u'‰' : ['&#8240;', '&permil;'], # per mille 
                u'′' : ['&#8242;', '&prime;'], # minutes
                u'″' : ['&#8243;', '&Prime;'], # seconds
                u'‹' : ['&#8249;', '&lsaquo;'], # single left angle quotation
                u'›' : ['&#8250;', '&rsaquo;'], # single right angle quotation
                u'‾' : ['&#8254;', '&oline;'], # overline
                u'€' : ['&#8364;', '&euro;'], # euro
                u'™' : ['&#8482;', '&trade;'], # trademark
                u'←' : ['&#8592;', '&larr;'], # left arrow
                u'↑' : ['&#8593;', '&uarr;'], # up arrow
                u'→' : ['&#8594;', '&rarr;'], # right arrow
                u'↓' : ['&#8595;', '&darr;'], # down arrow
                u'↔' : ['&#8596;', '&harr;'], # left right arrow
                u'↵' : ['&#8629;', '&crarr;'], # carriage return arrow
                u'⌈' : ['&#8968;', '&lceil;'], # left ceiling
                u'⌉' : ['&#8969;', '&rceil;'], # right ceiling
                u'⌊' : ['&#8970;', '&lfloor;'], # left floor
                u'⌋' : ['&#8971;', '&rfloor;'], # right floor
                u'◊' : ['&#9674;', '&loz;'], # lozenge
                u'♠' : ['&#9824;', '&spades;'], # spade
                u'♣' : ['&#9827;', '&clubs;'], # club
                u'♥' : ['&#9829;', '&hearts;'], # heart
                u'♦' : ['&#9830;', '&diams;'], # diamond
                # Extra http://www.ascii.cl/htmlcodes.htm
                u' ' : ['&#32;'], # space
                u'!' : ['&#33;'], # exclamation point
                u'#' : ['&#35;'], # number sign
                u'$' : ['&#36;'], # dollar sign
                u'%' : ['&#37;'], # percent sign
                u'\'' : ['&#39;'], # single quote
                u'(' : ['&#40;'], # opening parenthesis
                u')' : ['&#41;'], # closing parenthesis
                u'*' : ['&#42;'], # asterisk
                u'+' : ['&#43;'], # plus sign
                u',' : ['&#44;'], # comma
                u'-' : ['&#45;'], # minus sign - hyphen
                u'.' : ['&#46;'], # period
                u'/' : ['&#47;'], # slash
                u'0' : ['&#48;'], # zero
                u'1' : ['&#49;'], # one
                u'2' : ['&#50;'], # two
                u'3' : ['&#51;'], # three
                u'4' : ['&#52;'], # four
                u'5' : ['&#53;'], # five
                u'6' : ['&#54;'], # six
                u'7' : ['&#55;'], # seven
                u'8' : ['&#56;'], # eight
                u'9' : ['&#57;'], # nine
                u':' : ['&#58;'], # colon
                u';' : ['&#59;'], # semicolon
                u'=' : ['&#61;'], # equal sign
                u'?' : ['&#63;'], # question mark
                u'@' : ['&#64;'], # at symbol
                u'A' : ['&#65;'], # 
                u'B' : ['&#66;'], # 
                u'C' : ['&#67;'], # 
                u'D' : ['&#68;'], # 
                u'E' : ['&#69;'], # 
                u'F' : ['&#70;'], # 
                u'G' : ['&#71;'], # 
                u'H' : ['&#72;'], # 
                u'I' : ['&#73;'], # 
                u'J' : ['&#74;'], # 
                u'K' : ['&#75;'], # 
                u'L' : ['&#76;'], # 
                u'M' : ['&#77;'], # 
                u'N' : ['&#78;'], # 
                u'O' : ['&#79;'], # 
                u'P' : ['&#80;'], # 
                u'Q' : ['&#81;'], # 
                u'R' : ['&#82;'], # 
                u'S' : ['&#83;'], # 
                u'T' : ['&#84;'], # 
                u'U' : ['&#85;'], # 
                u'V' : ['&#86;'], # 
                u'W' : ['&#87;'], # 
                u'X' : ['&#88;'], # 
                u'Y' : ['&#89;'], # 
                u'Z' : ['&#90;'], # 
                u'[' : ['&#91;'], # opening bracket
                u'\\' : ['&#92;'], # backslash
                u']' : ['&#93;'], # closing bracket
                u'^' : ['&#94;'], # caret - circumflex
                u'_' : ['&#95;'], # underscore
                u'`' : ['&#96;'], # grave accent
                u'a' : ['&#97;'], # 
                u'b' : ['&#98;'], # 
                u'c' : ['&#99;'], # 
                u'd' : ['&#100;'], # 
                u'e' : ['&#101;'], # 
                u'f' : ['&#102;'], # 
                u'g' : ['&#103;'], # 
                u'h' : ['&#104;'], # 
                u'i' : ['&#105;'], # 
                u'j' : ['&#106;'], # 
                u'k' : ['&#107;'], # 
                u'l' : ['&#108;'], # 
                u'm' : ['&#109;'], # 
                u'n' : ['&#110;'], # 
                u'o' : ['&#111;'], # 
                u'p' : ['&#112;'], # 
                u'q' : ['&#113;'], # 
                u'r' : ['&#114;'], # 
                u's' : ['&#115;'], # 
                u't' : ['&#116;'], # 
                u'u' : ['&#117;'], # 
                u'v' : ['&#118;'], # 
                u'w' : ['&#119;'], # 
                u'x' : ['&#120;'], # 
                u'y' : ['&#121;'], # 
                u'z' : ['&#122;'], # 
                u'{' : ['&#123;'], # opening brace
                u'|' : ['&#124;'], # vertical bar
                u'}' : ['&#125;'], # closing brace
                u'~' : ['&#126;'], # equivalency sign - tilde
                u'<' : ['&#60;', '&lt;'], # less than sign
                u'>' : ['&#62;', '&gt;'], # greater than sign
                u'¡' : ['&#161;', '&iexcl;'], # inverted exclamation mark
                u'¢' : ['&#162;', '&cent;'], # cent sign
                u'£' : ['&#163;', '&pound;'], # pound sign
                u'¤' : ['&#164;', '&curren;'], # currency sign
                u'¥' : ['&#165;', '&yen;'], # yen sign
                u'¦' : ['&#166;', '&brvbar;'], # broken vertical bar
                u'§' : ['&#167;', '&sect;'], # section sign
                u'¨' : ['&#168;', '&uml;'], # spacing diaeresis - umlaut
                u'©' : ['&#169;', '&copy;'], # copyright sign
                u'ª' : ['&#170;', '&ordf;'], # feminine ordinal indicator
                u'«' : ['&#171;', '&laquo;'], # left double angle quotes
                u'¬' : ['&#172;', '&not;'], # not sign
                u'®' : ['&#174;', '&reg;'], # registered trade mark sign
                u'¯' : ['&#175;', '&macr;'], # spacing macron - overline
                u'°' : ['&#176;', '&deg;'], # degree sign
                u'±' : ['&#177;', '&plusmn;'], # plus-or-minus sign
                u'²' : ['&#178;', '&sup2;'], # superscript two - squared
                u'³' : ['&#179;', '&sup3;'], # superscript three - cubed
                u'´' : ['&#180;', '&acute;'], # acute accent - spacing acute
                u'µ' : ['&#181;', '&micro;'], # micro sign
                u'¶' : ['&#182;', '&para;'], # pilcrow sign - paragraph sign
                u'·' : ['&#183;', '&middot;'], # middle dot - Georgian comma
                u'¸' : ['&#184;', '&cedil;'], # spacing cedilla
                u'¹' : ['&#185;', '&sup1;'], # superscript one
                u'º' : ['&#186;', '&ordm;'], # masculine ordinal indicator
                u'»' : ['&#187;', '&raquo;'], # right double angle quotes
                u'¼' : ['&#188;', '&frac14;'], # fraction one quarter
                u'½' : ['&#189;', '&frac12;'], # fraction one half
                u'¾' : ['&#190;', '&frac34;'], # fraction three quarters
                u'¿' : ['&#191;', '&iquest;'], # inverted question mark
                u'À' : ['&#192;', '&Agrave;'], # latin capital letter A with grave
                u'Á' : ['&#193;', '&Aacute;'], # latin capital letter A with acute
                u'Â' : ['&#194;', '&Acirc;'], # latin capital letter A with circumflex
                u'Ã' : ['&#195;', '&Atilde;'], # latin capital letter A with tilde
                u'Ä' : ['&#196;', '&Auml;'], # latin capital letter A with diaeresis
                u'Å' : ['&#197;', '&Aring;'], # latin capital letter A with ring above
                u'Æ' : ['&#198;', '&AElig;'], # latin capital letter AE
                u'Ç' : ['&#199;', '&Ccedil;'], # latin capital letter C with cedilla
                u'È' : ['&#200;', '&Egrave;'], # latin capital letter E with grave
                u'É' : ['&#201;', '&Eacute;'], # latin capital letter E with acute
                u'Ê' : ['&#202;', '&Ecirc;'], # latin capital letter E with circumflex
                u'Ë' : ['&#203;', '&Euml;'], # latin capital letter E with diaeresis
                u'Ì' : ['&#204;', '&Igrave;'], # latin capital letter I with grave
                u'Í' : ['&#205;', '&Iacute;'], # latin capital letter I with acute
                u'Î' : ['&#206;', '&Icirc;'], # latin capital letter I with circumflex
                u'Ï' : ['&#207;', '&Iuml;'], # latin capital letter I with diaeresis
                u'Ð' : ['&#208;', '&ETH;'], # latin capital letter ETH
                u'Ñ' : ['&#209;', '&Ntilde;'], # latin capital letter N with tilde
                u'Ò' : ['&#210;', '&Ograve;'], # latin capital letter O with grave
                u'Ó' : ['&#211;', '&Oacute;'], # latin capital letter O with acute
                u'Ô' : ['&#212;', '&Ocirc;'], # latin capital letter O with circumflex
                u'Õ' : ['&#213;', '&Otilde;'], # latin capital letter O with tilde
                u'Ö' : ['&#214;', '&Ouml;'], # latin capital letter O with diaeresis
                u'×' : ['&#215;', '&times;'], # multiplication sign
                u'Ø' : ['&#216;', '&Oslash;'], # latin capital letter O with slash
                u'Ù' : ['&#217;', '&Ugrave;'], # latin capital letter U with grave
                u'Ú' : ['&#218;', '&Uacute;'], # latin capital letter U with acute
                u'Û' : ['&#219;', '&Ucirc;'], # latin capital letter U with circumflex
                u'Ü' : ['&#220;', '&Uuml;'], # latin capital letter U with diaeresis
                u'Ý' : ['&#221;', '&Yacute;'], # latin capital letter Y with acute
                u'Þ' : ['&#222;', '&THORN;'], # latin capital letter THORN
                u'ß' : ['&#223;', '&szlig;'], # latin small letter sharp s - ess-zed
                u'à' : ['&#224;', '&agrave;'], # latin small letter a with grave
                u'á' : ['&#225;', '&aacute;'], # latin small letter a with acute
                u'â' : ['&#226;', '&acirc;'], # latin small letter a with circumflex
                u'ã' : ['&#227;', '&atilde;'], # latin small letter a with tilde
                u'ä' : ['&#228;', '&auml;'], # latin small letter a with diaeresis
                u'å' : ['&#229;', '&aring;'], # latin small letter a with ring above
                u'æ' : ['&#230;', '&aelig;'], # latin small letter ae
                u'ç' : ['&#231;', '&ccedil;'], # latin small letter c with cedilla
                u'è' : ['&#232;', '&egrave;'], # latin small letter e with grave
                u'é' : ['&#233;', '&eacute;'], # latin small letter e with acute
                u'ê' : ['&#234;', '&ecirc;'], # latin small letter e with circumflex
                u'ë' : ['&#235;', '&euml;'], # latin small letter e with diaeresis
                u'ì' : ['&#236;', '&igrave;'], # latin small letter i with grave
                u'í' : ['&#237;', '&iacute;'], # latin small letter i with acute
                u'î' : ['&#238;', '&icirc;'], # latin small letter i with circumflex
                u'ï' : ['&#239;', '&iuml;'], # latin small letter i with diaeresis
                u'ð' : ['&#240;', '&eth;'], # latin small letter eth
                u'ñ' : ['&#241;', '&ntilde;'], # latin small letter n with tilde
                u'ò' : ['&#242;', '&ograve;'], # latin small letter o with grave
                u'ó' : ['&#243;', '&oacute;'], # latin small letter o with acute
                u'ô' : ['&#244;', '&ocirc;'], # latin small letter o with circumflex
                u'õ' : ['&#245;', '&otilde;'], # latin small letter o with tilde
                u'ö' : ['&#246;', '&ouml;'], # latin small letter o with diaeresis
                u'÷' : ['&#247;', '&divide;'], # division sign
                u'ø' : ['&#248;', '&oslash;'], # latin small letter o with slash
                u'ù' : ['&#249;', '&ugrave;'], # latin small letter u with grave
                u'ú' : ['&#250;', '&uacute;'], # latin small letter u with acute
                u'û' : ['&#251;', '&ucirc;'], # latin small letter u with circumflex
                u'ü' : ['&#252;', '&uuml;'], # latin small letter u with diaeresis
                u'ý' : ['&#253;', '&yacute;'], # latin small letter y with acute
                u'þ' : ['&#254;', '&thorn;'], # latin small letter thorn
                u'ÿ' : ['&#255;', '&yuml;'], # latin small letter y with diaeresis
               }

