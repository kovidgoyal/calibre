
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
import sys


class BorderParse:
    """
    Parse a border line and return a dictionary of attributes and values
    """

    def __init__(self):
        # cw<bd<bor-t-r-hi<nu<true
        self.__border_dict = {
        'bor-t-r-hi'    : 'border-table-row-horizontal-inside',
        'bor-t-r-vi'    : 'border-table-row-vertical-inside',
        'bor-t-r-to'    : 'border-table-row-top',
        'bor-t-r-le'    : 'border-table-row-left',
        'bor-t-r-bo'    : 'border-table-row-bottom',
        'bor-t-r-ri'    : 'border-table-row-right',
        'bor-cel-bo'    : 'border-cell-bottom',
        'bor-cel-to'    : 'border-cell-top',
        'bor-cel-le'    : 'border-cell-left',
        'bor-cel-ri'    : 'border-cell-right',
        'bor-par-bo'    : 'border-paragraph-bottom',
        'bor-par-to'    : 'border-paragraph-top',
        'bor-par-le'    : 'border-paragraph-left',
        'bor-par-ri'    : 'border-paragraph-right',
        'bor-par-bx'    : 'border-paragraph-box',
        'bor-for-ev'    : 'border-for-every-paragraph',
        'bor-outsid'    : 'border-outside',
        'bor-none__'    : 'border',
        # border type => bt
        'bdr-li-wid'    : 'line-width',
        'bdr-sp-wid'    :       'padding',
        'bdr-color_'    :       'color',
        }
        self.__border_style_dict = {
        'bdr-single'    : 'single',
        'bdr-doubtb'    : 'double-thickness-border',
        'bdr-shadow'    : 'shadowed-border',
        'bdr-double'    : 'double-border',
        'bdr-dotted'    : 'dotted-border',
        'bdr-dashed'    : 'dashed',
        'bdr-hair__'    : 'hairline',
        'bdr-inset_'    : 'inset',
        'bdr-das-sm'    : 'dash-small',
        'bdr-dot-sm'    : 'dot-dash',
        'bdr-dot-do'    : 'dot-dot-dash',
        'bdr-outset'    : 'outset',
        'bdr-trippl'    : 'tripple',
        'bdr-thsm__'    : 'thick-thin-small',
        'bdr-htsm__'    : 'thin-thick-small',
        'bdr-hthsm_'    : 'thin-thick-thin-small',
        'bdr-thm___'     : 'thick-thin-medium',
        'bdr-htm___'     : 'thin-thick-medium',
        'bdr-hthm__'     : 'thin-thick-thin-medium',
        'bdr-thl___'     : 'thick-thin-large',
        'bdr-hthl__'     : 'thin-thick-thin-large',
        'bdr-wavy__'     : 'wavy',
        'bdr-d-wav_'     : 'double-wavy',
        'bdr-strip_'     : 'striped',
        'bdr-embos_'     : 'emboss',
        'bdr-engra_'     : 'engrave',
        'bdr-frame_'     : 'frame',
        }

    def parse_border(self, line):
        """
        Requires:
            line -- line with border definition in it
        Returns:
            ?
        Logic:
        """
        border_dict = {}
        border_style_dict = {}
        border_style_list = []
        border_type = self.__border_dict.get(line[6:16])
        if not border_type:
            sys.stderr.write(
            'module is border_parse.py\n'
            'function is parse_border\n'
            'token does not have a dictionary value\n'
            'token is "%s"' % line
            )
            return border_dict
        att_line = line[20:-1]
        atts = att_line.split('|')
        # cw<bd<bor-cel-ri<nu<
        # border has no value--should be no lines
        if len(atts) == 1 and atts[0] == '':
            border_dict[border_type] = 'none'
            return border_dict
            # border-paragraph-right
        for att in atts:
            values = att.split(':')
            if len(values) ==2:
                att = values[0]
                value = values[1]
            else:
                value = 'true'
            style_att = self.__border_style_dict.get(att)
            if style_att:
                att = '%s-%s' % (border_type, att)
                border_style_dict[att] = value
                border_style_list.append(style_att)
            else:
                att = self.__border_dict.get(att)
                if not att:
                    sys.stderr.write(
                    'module is border_parse_def.py\n'
                    'function is parse_border\n'
                    'token does not have an att value\n'
                    'line is "%s"' % line
                    )
                att = '%s-%s' % (border_type, att)
                border_dict[att] = value
        new_border_dict = self.__determine_styles(border_type, border_style_list)
        border_dict.update(new_border_dict)
        return border_dict

    def __determine_styles(self, border_type, border_style_list):
        new_border_dict = {}
        att = '%s-style' % border_type
        if 'shadowed-border' in border_style_list:
            new_border_dict[att] = 'shadowed'
        elif 'engraved' in border_style_list:
            new_border_dict[att] = 'engraved'
        elif 'emboss' in border_style_list:
            new_border_dict[att] = 'emboss'
        elif 'striped' in border_style_list:
            new_border_dict[att] = 'striped'
        elif 'thin-thick-thin-small' in border_style_list:
            new_border_dict[att] = 'thin-thick-thin-small'
        elif 'thick-thin-large' in border_style_list:
            new_border_dict[att] = 'thick-thin-large'
        elif 'thin-thick-thin-medium' in border_style_list:
            new_border_dict[att] = 'thin-thick-thin-medium'
        elif 'thin-thick-medium' in border_style_list:
            new_border_dict[att] = 'thin-thick-medium'
        elif 'thick-thin-medium' in border_style_list:
            new_border_dict[att] = 'thick-thin-medium'
        elif 'thick-thin-small' in border_style_list:
            new_border_dict[att] = 'thick-thin-small'
        elif 'thick-thin-small' in border_style_list:
            new_border_dict[att] = 'thick-thin-small'
        elif 'double-wavy' in border_style_list:
            new_border_dict[att] = 'double-wavy'
        elif 'dot-dot-dash' in border_style_list:
            new_border_dict[att] = 'dot-dot-dash'
        elif 'dot-dash' in border_style_list:
            new_border_dict[att] = 'dot-dash'
        elif 'dotted-border' in border_style_list:
            new_border_dict[att] = 'dotted'
        elif 'wavy' in border_style_list:
            new_border_dict[att] = 'wavy'
        elif 'dash-small' in border_style_list:
            new_border_dict[att] = 'dash-small'
        elif 'dashed' in border_style_list:
            new_border_dict[att] = 'dashed'
        elif 'frame' in border_style_list:
            new_border_dict[att] = 'frame'
        elif 'inset' in border_style_list:
            new_border_dict[att] = 'inset'
        elif 'outset' in border_style_list:
            new_border_dict[att] = 'outset'
        elif 'tripple-border' in border_style_list:
            new_border_dict[att] = 'tripple'
        elif 'double-border' in border_style_list:
            new_border_dict[att] = 'double'
        elif 'double-thickness-border' in border_style_list:
            new_border_dict[att] = 'double-thickness'
        elif 'hairline' in border_style_list:
            new_border_dict[att] = 'hairline'
        elif 'single' in border_style_list:
            new_border_dict[att] = 'single'
        else:
            if border_style_list:
                new_border_dict[att] = border_style_list[0]
        return new_border_dict
