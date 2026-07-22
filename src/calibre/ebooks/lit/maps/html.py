# License: GPLv3 Copyright: 2008, Marshall T. Vandegrift <llasram@gmail.com>

"""
Microsoft LIT HTML tag and attribute tables, copied from ConvertLIT.
"""

TAGS = [
    None,
    None,
    None,
    'a',
    'acronym',
    'address',
    'applet',
    'area',
    'b',
    'base',
    'basefont',
    'bdo',
    'bgsound',
    'big',
    'blink',
    'blockquote',
    'body',
    'br',
    'button',
    'caption',
    'center',
    'cite',
    'code',
    'col',
    'colgroup',
    None,
    None,
    'dd',
    'del',
    'dfn',
    'dir',
    'div',
    'dl',
    'dt',
    'em',
    'embed',
    'fieldset',
    'font',
    'form',
    'frame',
    'frameset',
    None,
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'head',
    'hr',
    'html',
    'i',
    'iframe',
    'img',
    'input',
    'ins',
    'kbd',
    'label',
    'legend',
    'li',
    'link',
    'tag61',
    'map',
    'tag63',
    'tag64',
    'meta',
    'nextid',
    'nobr',
    'noembed',
    'noframes',
    'noscript',
    'object',
    'ol',
    'option',
    'p',
    'param',
    'plaintext',
    'pre',
    'q',
    'rp',
    'rt',
    'ruby',
    's',
    'samp',
    'script',
    'select',
    'small',
    'span',
    'strike',
    'strong',
    'style',
    'sub',
    'sup',
    'table',
    'tbody',
    'tc',
    'td',
    'textarea',
    'tfoot',
    'th',
    'thead',
    'title',
    'tr',
    'tt',
    'u',
    'ul',
    'var',
    'wbr',
    None,
]

ATTRS0 = {
    0x8010: 'tabindex',
    0x8046: 'title',
    0x804B: 'style',
    0x804D: 'disabled',
    0x83EA: 'class',
    0x83EB: 'id',
    0x83FE: 'datafld',
    0x83FF: 'datasrc',
    0x8400: 'dataformatas',
    0x87D6: 'accesskey',
    0x9392: 'lang',
    0x93ED: 'language',
    0x93FE: 'dir',
    0x9771: 'onmouseover',
    0x9772: 'onmouseout',
    0x9773: 'onmousedown',
    0x9774: 'onmouseup',
    0x9775: 'onmousemove',
    0x9776: 'onkeydown',
    0x9777: 'onkeyup',
    0x9778: 'onkeypress',
    0x9779: 'onclick',
    0x977A: 'ondblclick',
    0x977E: 'onhelp',
    0x977F: 'onfocus',
    0x9780: 'onblur',
    0x9783: 'onrowexit',
    0x9784: 'onrowenter',
    0x9786: 'onbeforeupdate',
    0x9787: 'onafterupdate',
    0x978A: 'onreadystatechange',
    0x9790: 'onscroll',
    0x9794: 'ondragstart',
    0x9795: 'onresize',
    0x9796: 'onselectstart',
    0x9797: 'onerrorupdate',
    0x9799: 'ondatasetchanged',
    0x979A: 'ondataavailable',
    0x979B: 'ondatasetcomplete',
    0x979C: 'onfilterchange',
    0x979F: 'onlosecapture',
    0x97A0: 'onpropertychange',
    0x97A2: 'ondrag',
    0x97A3: 'ondragend',
    0x97A4: 'ondragenter',
    0x97A5: 'ondragover',
    0x97A6: 'ondragleave',
    0x97A7: 'ondrop',
    0x97A8: 'oncut',
    0x97A9: 'oncopy',
    0x97AA: 'onpaste',
    0x97AB: 'onbeforecut',
    0x97AC: 'onbeforecopy',
    0x97AD: 'onbeforepaste',
    0x97AF: 'onrowsdelete',
    0x97B0: 'onrowsinserted',
    0x97B1: 'oncellchange',
    0x97B2: 'oncontextmenu',
    0x97B6: 'onbeforeeditfocus',
}
ATTRS3 = {
    0x0001: 'href',
    0x03EC: 'target',
    0x03EE: 'rel',
    0x03EF: 'rev',
    0x03F0: 'urn',
    0x03F1: 'methods',
    0x8001: 'name',
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS5 = {
    0x9399: 'clear',
}
ATTRS6 = {
    0x8001: 'name',
    0x8006: 'width',
    0x8007: 'height',
    0x804A: 'align',
    0x8BBB: 'classid',
    0x8BBC: 'data',
    0x8BBF: 'codebase',
    0x8BC0: 'codetype',
    0x8BC1: 'code',
    0x8BC2: 'type',
    0x8BC5: 'vspace',
    0x8BC6: 'hspace',
    0x978E: 'onerror',
}
ATTRS7 = {
    0x0001: 'href',
    0x03EA: 'shape',
    0x03EB: 'coords',
    0x03ED: 'target',
    0x03EE: 'alt',
    0x03EF: 'nohref',
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS8 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS9 = {
    0x03EC: 'href',
    0x03ED: 'target',
}
ATTRS10 = {
    0x938B: 'color',
    0x939B: 'face',
    0x93A3: 'size',
}
ATTRS12 = {
    0x03EA: 'src',
    0x03EB: 'loop',
    0x03EC: 'volume',
    0x03ED: 'balance',
}
ATTRS13 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS15 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x9399: 'clear',
}
ATTRS16 = {
    0x07DB: 'link',
    0x07DC: 'alink',
    0x07DD: 'vlink',
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x938A: 'background',
    0x938B: 'text',
    0x938E: 'nowrap',
    0x93AE: 'topmargin',
    0x93AF: 'rightmargin',
    0x93B0: 'bottommargin',
    0x93B1: 'leftmargin',
    0x93B6: 'bgproperties',
    0x93D8: 'scroll',
    0x977B: 'onselect',
    0x9791: 'onload',
    0x9792: 'onunload',
    0x9798: 'onbeforeunload',
    0x97B3: 'onbeforeprint',
    0x97B4: 'onafterprint',
    0xFE0C: 'bgcolor',
}
ATTRS17 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x9399: 'clear',
}
ATTRS18 = {
    0x07D1: 'type',
    0x8001: 'name',
}
ATTRS19 = {
    0x8046: 'title',
    0x8049: 'align',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x93A8: 'valign',
}
ATTRS20 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x9399: 'clear',
}
ATTRS21 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS22 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS23 = {
    0x03EA: 'span',
    0x8006: 'width',
    0x8049: 'align',
    0x93A8: 'valign',
    0xFE0C: 'bgcolor',
}
ATTRS24 = {
    0x03EA: 'span',
    0x8006: 'width',
    0x8049: 'align',
    0x93A8: 'valign',
    0xFE0C: 'bgcolor',
}
ATTRS27 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x938E: 'nowrap',
}
ATTRS29 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS31 = {
    0x8046: 'title',
    0x8049: 'align',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x938E: 'nowrap',
}
ATTRS32 = {
    0x03EA: 'compact',
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS33 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x938E: 'nowrap',
}
ATTRS34 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS35 = {
    0x8001: 'name',
    0x8006: 'width',
    0x8007: 'height',
    0x804A: 'align',
    0x8BBD: 'palette',
    0x8BBE: 'pluginspage',
    # 0x8bbf: "codebase",
    0x8BBF: 'src',
    0x8BC1: 'units',
    0x8BC2: 'type',
    0x8BC3: 'hidden',
}
ATTRS36 = {
    0x804A: 'align',
}
ATTRS37 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x938B: 'color',
    0x939B: 'face',
    0x939C: 'size',
}
ATTRS38 = {
    0x03EA: 'action',
    0x03EC: 'enctype',
    0x03ED: 'method',
    0x03EF: 'target',
    0x03F4: 'accept-charset',
    0x8001: 'name',
    0x977C: 'onsubmit',
    0x977D: 'onreset',
}
ATTRS39 = {
    0x8000: 'align',
    0x8001: 'name',
    0x8BB9: 'src',
    0x8BBB: 'border',
    0x8BBC: 'frameborder',
    0x8BBD: 'framespacing',
    0x8BBE: 'marginwidth',
    0x8BBF: 'marginheight',
    0x8BC0: 'noresize',
    0x8BC1: 'scrolling',
    0x8FA2: 'bordercolor',
}
ATTRS40 = {
    0x03E9: 'rows',
    0x03EA: 'cols',
    0x03EB: 'border',
    0x03EC: 'bordercolor',
    0x03ED: 'frameborder',
    0x03EE: 'framespacing',
    0x8001: 'name',
    0x9791: 'onload',
    0x9792: 'onunload',
    0x9798: 'onbeforeunload',
    0x97B3: 'onbeforeprint',
    0x97B4: 'onafterprint',
}
ATTRS42 = {
    0x8046: 'title',
    0x8049: 'align',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x9399: 'clear',
}
ATTRS43 = {
    0x8046: 'title',
    0x8049: 'align',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x9399: 'clear',
}
ATTRS44 = {
    0x8046: 'title',
    0x8049: 'align',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x9399: 'clear',
}
ATTRS45 = {
    0x8046: 'title',
    0x8049: 'align',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x9399: 'clear',
}
ATTRS46 = {
    0x8046: 'title',
    0x8049: 'align',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x9399: 'clear',
}
ATTRS47 = {
    0x8046: 'title',
    0x8049: 'align',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x9399: 'clear',
}
ATTRS49 = {
    0x03EA: 'noshade',
    0x8006: 'width',
    0x8007: 'size',
    0x8046: 'title',
    0x8049: 'align',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x938B: 'color',
}
ATTRS51 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS52 = {
    0x8001: 'name',
    0x8006: 'width',
    0x8007: 'height',
    0x804A: 'align',
    0x8BB9: 'src',
    0x8BBB: 'border',
    0x8BBC: 'frameborder',
    0x8BBD: 'framespacing',
    0x8BBE: 'marginwidth',
    0x8BBF: 'marginheight',
    0x8BC0: 'noresize',
    0x8BC1: 'scrolling',
    0x8FA2: 'vspace',
    0x8FA3: 'hspace',
}
ATTRS53 = {
    0x03EB: 'alt',
    0x03EC: 'src',
    0x03ED: 'border',
    0x03EE: 'vspace',
    0x03EF: 'hspace',
    0x03F0: 'lowsrc',
    0x03F1: 'vrml',
    0x03F2: 'dynsrc',
    0x03F4: 'loop',
    0x03F6: 'start',
    0x07D3: 'ismap',
    0x07D9: 'usemap',
    0x8001: 'name',
    0x8006: 'width',
    0x8007: 'height',
    0x8046: 'title',
    0x804A: 'align',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x978D: 'onabort',
    0x978E: 'onerror',
    0x9791: 'onload',
}
ATTRS54 = {
    0x07D1: 'type',
    0x07D3: 'size',
    0x07D4: 'maxlength',
    0x07D6: 'readonly',
    0x07D8: 'indeterminate',
    0x07DA: 'checked',
    0x07DB: 'alt',
    0x07DC: 'src',
    0x07DD: 'border',
    0x07DE: 'vspace',
    0x07DF: 'hspace',
    0x07E0: 'lowsrc',
    0x07E1: 'vrml',
    0x07E2: 'dynsrc',
    0x07E4: 'loop',
    0x07E5: 'start',
    0x8001: 'name',
    0x8006: 'width',
    0x8007: 'height',
    0x804A: 'align',
    0x93EE: 'value',
    0x977B: 'onselect',
    0x978D: 'onabort',
    0x978E: 'onerror',
    0x978F: 'onchange',
    0x9791: 'onload',
}
ATTRS56 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS57 = {
    0x03E9: 'for',
}
ATTRS58 = {
    0x804A: 'align',
}
ATTRS59 = {
    0x03EA: 'value',
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x939A: 'type',
}
ATTRS60 = {
    0x03EE: 'href',
    0x03EF: 'rel',
    0x03F0: 'rev',
    0x03F1: 'type',
    0x03F9: 'media',
    0x03FA: 'target',
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x978E: 'onerror',
    0x9791: 'onload',
}
ATTRS61 = {
    0x9399: 'clear',
}
ATTRS62 = {
    0x8001: 'name',
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS63 = {
    0x1771: 'scrolldelay',
    0x1772: 'direction',
    0x1773: 'behavior',
    0x1774: 'scrollamount',
    0x1775: 'loop',
    0x1776: 'vspace',
    0x1777: 'hspace',
    0x1778: 'truespeed',
    0x8006: 'width',
    0x8007: 'height',
    0x9785: 'onbounce',
    0x978B: 'onfinish',
    0x978C: 'onstart',
    0xFE0C: 'bgcolor',
}
ATTRS65 = {
    0x03EA: 'http-equiv',
    0x03EB: 'content',
    0x03EC: 'url',
    0x03F6: 'charset',
    0x8001: 'name',
}
ATTRS66 = {
    0x03F5: 'n',
}
ATTRS71 = {
    # 0x8000: "border",
    0x8000: 'usemap',
    0x8001: 'name',
    0x8006: 'width',
    0x8007: 'height',
    0x8046: 'title',
    0x804A: 'align',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x8BBB: 'classid',
    0x8BBC: 'data',
    0x8BBF: 'codebase',
    0x8BC0: 'codetype',
    0x8BC1: 'code',
    0x8BC2: 'type',
    0x8BC5: 'vspace',
    0x8BC6: 'hspace',
    0x978E: 'onerror',
}
ATTRS72 = {
    0x03EB: 'compact',
    0x03EC: 'start',
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x939A: 'type',
}
ATTRS73 = {
    0x03EA: 'selected',
    0x03EB: 'value',
}
ATTRS74 = {
    0x8046: 'title',
    0x8049: 'align',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x9399: 'clear',
}
ATTRS75 = {
    # 0x8000: "name",
    # 0x8000: "value",
    0x8000: 'type',
}
ATTRS76 = {
    0x9399: 'clear',
}
ATTRS77 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x9399: 'clear',
}
ATTRS78 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS82 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS83 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS84 = {
    0x03EA: 'src',
    0x03ED: 'for',
    0x03EE: 'event',
    0x03F0: 'defer',
    0x03F2: 'type',
    0x978E: 'onerror',
}
ATTRS85 = {
    0x03EB: 'size',
    0x03EC: 'multiple',
    0x8000: 'align',
    0x8001: 'name',
    0x978F: 'onchange',
}
ATTRS86 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS87 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS88 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS89 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS90 = {
    0x03EB: 'type',
    0x03EF: 'media',
    0x8046: 'title',
    0x978E: 'onerror',
    0x9791: 'onload',
}
ATTRS91 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS92 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS93 = {
    0x03EA: 'cols',
    0x03EB: 'border',
    0x03EC: 'rules',
    0x03ED: 'frame',
    0x03EE: 'cellspacing',
    0x03EF: 'cellpadding',
    0x03FA: 'datapagesize',
    0x8006: 'width',
    0x8007: 'height',
    0x8046: 'title',
    0x804A: 'align',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x938A: 'background',
    0x93A5: 'bordercolor',
    0x93A6: 'bordercolorlight',
    0x93A7: 'bordercolordark',
    0xFE0C: 'bgcolor',
}
ATTRS94 = {
    0x8049: 'align',
    0x93A8: 'valign',
    0xFE0C: 'bgcolor',
}
ATTRS95 = {
    0x8049: 'align',
    0x93A8: 'valign',
}
ATTRS96 = {
    0x07D2: 'rowspan',
    0x07D3: 'colspan',
    0x8006: 'width',
    0x8007: 'height',
    0x8046: 'title',
    0x8049: 'align',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x938A: 'background',
    0x938E: 'nowrap',
    0x93A5: 'bordercolor',
    0x93A6: 'bordercolorlight',
    0x93A7: 'bordercolordark',
    0x93A8: 'valign',
    0xFE0C: 'bgcolor',
}
ATTRS97 = {
    0x1B5A: 'rows',
    0x1B5B: 'cols',
    0x1B5C: 'wrap',
    0x1B5D: 'readonly',
    0x8001: 'name',
    0x977B: 'onselect',
    0x978F: 'onchange',
}
ATTRS98 = {
    0x8049: 'align',
    0x93A8: 'valign',
    0xFE0C: 'bgcolor',
}
ATTRS99 = {
    0x07D2: 'rowspan',
    0x07D3: 'colspan',
    0x8006: 'width',
    0x8007: 'height',
    0x8046: 'title',
    0x8049: 'align',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x938A: 'background',
    0x938E: 'nowrap',
    0x93A5: 'bordercolor',
    0x93A6: 'bordercolorlight',
    0x93A7: 'bordercolordark',
    0x93A8: 'valign',
    0xFE0C: 'bgcolor',
}
ATTRS100 = {
    0x8049: 'align',
    0x93A8: 'valign',
    0xFE0C: 'bgcolor',
}
ATTRS102 = {
    0x8007: 'height',
    0x8046: 'title',
    0x8049: 'align',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x93A5: 'bordercolor',
    0x93A6: 'bordercolorlight',
    0x93A7: 'bordercolordark',
    0x93A8: 'valign',
    0xFE0C: 'bgcolor',
}
ATTRS103 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS104 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS105 = {
    0x03EB: 'compact',
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
    0x939A: 'type',
}
ATTRS106 = {
    0x8046: 'title',
    0x804B: 'style',
    0x83EA: 'class',
    0x83EB: 'id',
}
ATTRS108 = {
    0x9399: 'clear',
}

TAGS_ATTRS = [
    None,
    None,
    None,
    ATTRS3,  # a
    None,  # acronym
    ATTRS5,  # address
    ATTRS6,  # applet
    ATTRS7,  # area
    ATTRS8,  # b
    ATTRS9,  # base
    ATTRS10,  # basefont
    None,  # bdo
    ATTRS12,  # bgsound
    ATTRS13,  # big
    None,  # blink
    ATTRS15,  # blockquote
    ATTRS16,  # body
    ATTRS17,  # br
    ATTRS18,  # button
    ATTRS19,  # caption
    ATTRS20,  # center
    ATTRS21,  # cite
    ATTRS22,  # code
    ATTRS23,  # col
    ATTRS24,  # colgroup
    None,
    None,
    ATTRS27,  # dd
    None,  # del
    ATTRS29,  # dfn
    None,  # dir
    ATTRS31,  # div
    ATTRS32,  # dl
    ATTRS33,  # dt
    ATTRS34,  # em
    ATTRS35,  # embed
    ATTRS36,  # fieldset
    ATTRS37,  # font
    ATTRS38,  # form
    ATTRS39,  # frame
    ATTRS40,  # frameset
    None,
    ATTRS42,  # h1
    ATTRS43,  # h2
    ATTRS44,  # h3
    ATTRS45,  # h4
    ATTRS46,  # h5
    ATTRS47,  # h6
    None,  # head
    ATTRS49,  # hr
    None,  # html
    ATTRS51,  # i
    ATTRS52,  # iframe
    ATTRS53,  # img
    ATTRS54,  # input
    None,  # ins
    ATTRS56,  # kbd
    ATTRS57,  # label
    ATTRS58,  # legend
    ATTRS59,  # li
    ATTRS60,  # link
    ATTRS61,  # tag61
    ATTRS62,  # map
    ATTRS63,  # tag63
    None,  # tag64
    ATTRS65,  # meta
    ATTRS66,  # nextid
    None,  # nobr
    None,  # noembed
    None,  # noframes
    None,  # noscript
    ATTRS71,  # object
    ATTRS72,  # ol
    ATTRS73,  # option
    ATTRS74,  # p
    ATTRS75,  # param
    ATTRS76,  # plaintext
    ATTRS77,  # pre
    ATTRS78,  # q
    None,  # rp
    None,  # rt
    None,  # ruby
    ATTRS82,  # s
    ATTRS83,  # samp
    ATTRS84,  # script
    ATTRS85,  # select
    ATTRS86,  # small
    ATTRS87,  # span
    ATTRS88,  # strike
    ATTRS89,  # strong
    ATTRS90,  # style
    ATTRS91,  # sub
    ATTRS92,  # sup
    ATTRS93,  # table
    ATTRS94,  # tbody
    ATTRS95,  # tc
    ATTRS96,  # td
    ATTRS97,  # textarea
    ATTRS98,  # tfoot
    ATTRS99,  # th
    ATTRS100,  # thead
    None,  # title
    ATTRS102,  # tr
    ATTRS103,  # tt
    ATTRS104,  # u
    ATTRS105,  # ul
    ATTRS106,  # var
    None,  # wbr
    None,
]

MAP = (TAGS, ATTRS0, TAGS_ATTRS)
