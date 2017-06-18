#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

from docutils import nodes
from itertools import count

id_counter = count()
ID = 'sidebar-collapsible-toc'

CSS = r'''
ID li {
    list-style: none;
    margin-left: 0;
    padding-left: 0.2em;
    text-indent: -0.7em;
}

ID li.leaf-node {
    text-indent: 0;
}

ID li input[type=checkbox] {
    display: none;
}

ID li > label {
    cursor: pointer;
}

ID li > input[type=checkbox] ~ ul > li {
    display: none;
}

ID li > input[type=checkbox]:checked ~ ul > li {
    display: block;
}

ID li > input[type=checkbox]:checked + label:before {
    content: "\025bf";
}

ID li > input[type=checkbox]:not(:checked) + label:before {
    content: "\025b8";
}
'''.replace('ID', 'ul#' + ID)


class checkbox(nodes.Element):
    pass


def visit_checkbox(self, node):
    cid = node['ids'][0]
    node['classes'] = []
    self.body.append('<input id="{0}" type="checkbox" />'
                     '<label for="{0}">&nbsp;</label>'.format(cid))


def modify_li(li):
    sublist = li.first_child_matching_class(nodes.bullet_list)
    if sublist is None or li[sublist].first_child_matching_class(nodes.list_item) is None:
        if not li.get('classes'):
            li['classes'] = []
        li['classes'].append('leaf-node')
    else:
        c = checkbox()
        c['ids'] = ['collapse-checkbox-{}'.format(next(id_counter))]
        li.insert(0, c)


def create_toc(app, pagename):
    toctree = app.env.get_toc_for(pagename, app.builder)
    if toctree is not None:
        subtree = toctree[toctree.first_child_matching_class(nodes.list_item)]
        bl = subtree.first_child_matching_class(nodes.bullet_list)
        if bl is None:
            return  # Empty ToC
        subtree = subtree[bl]
        for li in subtree.traverse(nodes.list_item):
            modify_li(li)
        subtree['ids'] = [ID]
        return '<style>' + CSS + '</style>' + app.builder.render_partial(
            subtree)['fragment']


def add_html_context(app, pagename, templatename, context, *args):
    if 'toc' in context:
        context['toc'] = create_toc(app, pagename) or context['toc']


def setup(app):
    app.add_node(checkbox, html=(visit_checkbox, lambda *x: None))
    app.connect('html-page-context', add_html_context)
