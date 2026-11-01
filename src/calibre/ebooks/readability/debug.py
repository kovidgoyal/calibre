from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lxml.etree import _Element


def save_to_file(text: str, filename: str) -> None:
    with open(filename, 'wb') as f:
        f.write(b'<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />')
        f.write(text.encode('utf-8'))


uids: dict[_Element, int] = {}


def describe(node: _Element, depth: int = 2) -> str:
    if not hasattr(node, 'tag'):
        return f'[{type(node)}]'
    name = node.tag
    assert isinstance(name, str)  # comments/PIs would have failed at name[:4] below anyway
    if nid := node.get('id', ''):
        name += '#' + nid
    if ncls := node.get('class', ''):
        name += '.' + ncls.replace(' ', '.')
    if name[:4] in ['div#', 'div.']:
        name = name[3:]
    if name in ['tr', 'td', 'div', 'p']:
        if node not in uids:
            uid = uids[node] = len(uids) + 1
        else:
            uid = uids.get(node)
        name += f'{uid:02}'
    if depth and (parent := node.getparent()) is not None:
        return name + ' - ' + describe(parent, depth - 1)
    return name
