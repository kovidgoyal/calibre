__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import re

NAME_MAP = {
             u'aliceblue': u'#F0F8FF',
             u'antiquewhite': u'#FAEBD7',
             u'aqua': u'#00FFFF',
             u'aquamarine': u'#7FFFD4',
             u'azure': u'#F0FFFF',
             u'beige': u'#F5F5DC',
             u'bisque': u'#FFE4C4',
             u'black': u'#000000',
             u'blanchedalmond': u'#FFEBCD',
             u'blue': u'#0000FF',
             u'brown': u'#A52A2A',
             u'burlywood': u'#DEB887',
             u'cadetblue': u'#5F9EA0',
             u'chartreuse': u'#7FFF00',
             u'chocolate': u'#D2691E',
             u'coral': u'#FF7F50',
             u'crimson': u'#DC143C',
             u'cyan': u'#00FFFF',
             u'darkblue': u'#00008B',
             u'darkgoldenrod': u'#B8860B',
             u'darkgreen': u'#006400',
             u'darkkhaki': u'#BDB76B',
             u'darkmagenta': u'#8B008B',
             u'darkolivegreen': u'#556B2F',
             u'darkorange': u'#FF8C00',
             u'darkorchid': u'#9932CC',
             u'darkred': u'#8B0000',
             u'darksalmon': u'#E9967A',
             u'darkslateblue': u'#483D8B',
             u'darkslategrey': u'#2F4F4F',
             u'darkviolet': u'#9400D3',
             u'deeppink': u'#FF1493',
             u'dodgerblue': u'#1E90FF',
             u'firebrick': u'#B22222',
             u'floralwhite': u'#FFFAF0',
             u'forestgreen': u'#228B22',
             u'fuchsia': u'#FF00FF',
             u'gainsboro': u'#DCDCDC',
             u'ghostwhite': u'#F8F8FF',
             u'gold': u'#FFD700',
             u'goldenrod': u'#DAA520',
             u'indianred ': u'#CD5C5C',
             u'indigo  ': u'#4B0082',
             u'khaki': u'#F0E68C',
             u'lavenderblush': u'#FFF0F5',
             u'lawngreen': u'#7CFC00',
             u'lightblue': u'#ADD8E6',
             u'lightcoral': u'#F08080',
             u'lightgoldenrodyellow': u'#FAFAD2',
             u'lightgray': u'#D3D3D3',
             u'lightgrey': u'#D3D3D3',
             u'lightskyblue': u'#87CEFA',
             u'lightslategrey': u'#778899',
             u'lightsteelblue': u'#B0C4DE',
             u'lime': u'#87CEFA',
             u'linen': u'#FAF0E6',
             u'magenta': u'#FF00FF',
             u'maroon': u'#800000',
             u'mediumaquamarine': u'#66CDAA',
             u'mediumblue': u'#0000CD',
             u'mediumorchid': u'#BA55D3',
             u'mediumpurple': u'#9370D8',
             u'mediumseagreen': u'#3CB371',
             u'mediumslateblue': u'#7B68EE',
             u'midnightblue': u'#191970',
             u'moccasin': u'#FFE4B5',
             u'navajowhite': u'#FFDEAD',
             u'navy': u'#000080',
             u'oldlace': u'#FDF5E6',
             u'olive': u'#808000',
             u'orange': u'#FFA500',
             u'orangered': u'#FF4500',
             u'orchid': u'#DA70D6',
             u'paleturquoise': u'#AFEEEE',
             u'papayawhip': u'#FFEFD5',
             u'peachpuff': u'#FFDAB9',
             u'powderblue': u'#B0E0E6',
             u'rosybrown': u'#BC8F8F',
             u'royalblue': u'#4169E1',
             u'saddlebrown': u'#8B4513',
             u'sandybrown': u'#8B4513',
             u'seashell': u'#FFF5EE',
             u'sienna': u'#A0522D',
             u'silver': u'#C0C0C0',
             u'skyblue': u'#87CEEB',
             u'slategrey': u'#708090',
             u'snow': u'#FFFAFA',
             u'springgreen': u'#00FF7F',
             u'violet': u'#EE82EE',
             u'yellowgreen': u'#9ACD32'
            }

hex_pat = re.compile('#(\d{2})(\d{2})(\d{2})')
rgb_pat = re.compile('rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', re.IGNORECASE)


def lrs_color(html_color):
    hcol = html_color.lower()
    match = hex_pat.search(hcol)
    if match:
        return '0x00'+match.group(1)+match.group(2)+match.group(3)
    match = rgb_pat.search(hcol)
    if match:
        return '0x00'+hex(int(match.group(1)))[2:]+hex(int(match.group(2)))[2:]+hex(int(match.group(3)))[2:]
    if hcol in NAME_MAP:
        return NAME_MAP[hcol].replace('#', '0x00')
    return '0x00000000'


