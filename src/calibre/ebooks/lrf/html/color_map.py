

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import re

NAME_MAP = {
             'aliceblue': '#F0F8FF',
             'antiquewhite': '#FAEBD7',
             'aqua': '#00FFFF',
             'aquamarine': '#7FFFD4',
             'azure': '#F0FFFF',
             'beige': '#F5F5DC',
             'bisque': '#FFE4C4',
             'black': '#000000',
             'blanchedalmond': '#FFEBCD',
             'blue': '#0000FF',
             'brown': '#A52A2A',
             'burlywood': '#DEB887',
             'cadetblue': '#5F9EA0',
             'chartreuse': '#7FFF00',
             'chocolate': '#D2691E',
             'coral': '#FF7F50',
             'crimson': '#DC143C',
             'cyan': '#00FFFF',
             'darkblue': '#00008B',
             'darkgoldenrod': '#B8860B',
             'darkgreen': '#006400',
             'darkkhaki': '#BDB76B',
             'darkmagenta': '#8B008B',
             'darkolivegreen': '#556B2F',
             'darkorange': '#FF8C00',
             'darkorchid': '#9932CC',
             'darkred': '#8B0000',
             'darksalmon': '#E9967A',
             'darkslateblue': '#483D8B',
             'darkslategrey': '#2F4F4F',
             'darkviolet': '#9400D3',
             'deeppink': '#FF1493',
             'dodgerblue': '#1E90FF',
             'firebrick': '#B22222',
             'floralwhite': '#FFFAF0',
             'forestgreen': '#228B22',
             'fuchsia': '#FF00FF',
             'gainsboro': '#DCDCDC',
             'ghostwhite': '#F8F8FF',
             'gold': '#FFD700',
             'goldenrod': '#DAA520',
             'indianred ': '#CD5C5C',
             'indigo  ': '#4B0082',
             'khaki': '#F0E68C',
             'lavenderblush': '#FFF0F5',
             'lawngreen': '#7CFC00',
             'lightblue': '#ADD8E6',
             'lightcoral': '#F08080',
             'lightgoldenrodyellow': '#FAFAD2',
             'lightgray': '#D3D3D3',
             'lightgrey': '#D3D3D3',
             'lightskyblue': '#87CEFA',
             'lightslategrey': '#778899',
             'lightsteelblue': '#B0C4DE',
             'lime': '#87CEFA',
             'linen': '#FAF0E6',
             'magenta': '#FF00FF',
             'maroon': '#800000',
             'mediumaquamarine': '#66CDAA',
             'mediumblue': '#0000CD',
             'mediumorchid': '#BA55D3',
             'mediumpurple': '#9370D8',
             'mediumseagreen': '#3CB371',
             'mediumslateblue': '#7B68EE',
             'midnightblue': '#191970',
             'moccasin': '#FFE4B5',
             'navajowhite': '#FFDEAD',
             'navy': '#000080',
             'oldlace': '#FDF5E6',
             'olive': '#808000',
             'orange': '#FFA500',
             'orangered': '#FF4500',
             'orchid': '#DA70D6',
             'paleturquoise': '#AFEEEE',
             'papayawhip': '#FFEFD5',
             'peachpuff': '#FFDAB9',
             'powderblue': '#B0E0E6',
             'rosybrown': '#BC8F8F',
             'royalblue': '#4169E1',
             'saddlebrown': '#8B4513',
             'sandybrown': '#8B4513',
             'seashell': '#FFF5EE',
             'sienna': '#A0522D',
             'silver': '#C0C0C0',
             'skyblue': '#87CEEB',
             'slategrey': '#708090',
             'snow': '#FFFAFA',
             'springgreen': '#00FF7F',
             'violet': '#EE82EE',
             'yellowgreen': '#9ACD32'
            }

hex_pat = re.compile(r'#(\d{2})(\d{2})(\d{2})')
rgb_pat = re.compile(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', re.IGNORECASE)


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
