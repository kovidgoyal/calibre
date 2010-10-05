"""This is a copy of the htmlDecode function in Webware.

@@TR: It implemented more efficiently.

"""

from Cheetah.Utils.htmlEncode import htmlCodesReversed

def htmlDecode(s, codes=htmlCodesReversed):
    """ Returns the ASCII decoded version of the given HTML string. This does
    NOT remove normal HTML tags like <p>. It is the inverse of htmlEncode()."""
    for code in codes:
        s = s.replace(code[1], code[0])
    return s
