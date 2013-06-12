#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'


def mergeable(previous, current):
    if previous.tail or current.tail:
        return False
    if previous.get('class', None) != current.get('class', None):
        return False
    if current.get('id', False):
        return False
    try:
        return next(previous.itersiblings()) is current
    except StopIteration:
        return False


def append_text(parent, text):
    if len(parent) > 0:
        parent[-1].tail = (parent[-1].tail or '') + text
    else:
        parent.text = (parent.text or '') + text


def merge(parent, span):
    if span.text:
        append_text(parent, span.text)
    for child in span:
        parent.append(child)
    if span.tail:
        append_text(parent, span.tail)
    span.getparent().remove(span)


def merge_run(run):
    parent = run[0]
    for span in run[1:]:
        merge(parent, span)


def liftable(css):
    # A <span> is liftable if all its styling would work just as well if it is
    # specified on the parent element.
    prefixes = {x.partition('-')[0] for x in css.iterkeys()}
    return not (prefixes - {'text', 'font', 'letter', 'color', 'background'})

def cleanup_markup(root, styles):
    # Merge consecutive spans that have the same styling
    current_run = []
    for span in root.xpath('//span'):
        if not current_run:
            current_run.append(span)
        else:
            last = current_run[-1]
            if mergeable(last, span):
                current_run.append(span)
            else:
                if len(current_run) > 1:
                    merge_run(current_run)
                current_run = [span]

    # Remove unnecessary span tags that are the only child of a parent block
    # element
    class_map = dict(styles.classes.itervalues())
    parents = ('p', 'div') + tuple('h%d' % i for i in xrange(1, 7))
    for parent in root.xpath('//*[(%s) and count(span)=1]' % ' or '.join('name()="%s"' % t for t in parents)):
        if len(parent) == 1 and not parent.text and not parent[0].tail and not parent[0].get('id', None):
            # We have a block whose contents are entirely enclosed in a <span>
            span = parent[0]
            span_class = span.get('class', None)
            span_css = class_map.get(span_class, {})
            if liftable(span_css):
                pclass = parent.get('class', None)
                if span_class:
                    pclass = (pclass + ' ' + span_class) if pclass else span_class
                    parent.set('class', pclass)
                parent.text = span.text
                parent.remove(span)
                for child in span:
                    parent.append(child)

    # Make spans whose only styling is bold or italic into <b> and <i> tags
    for span in root.xpath('//span[@class]'):
        css = class_map.get(span.get('class', None), {})
        if len(css) == 1:
            if css == {'font-style':'italic'}:
                span.tag = 'i'
                del span.attrib['class']
            elif css == {'font-weight':'bold'}:
                span.tag = 'b'
                del span.attrib['class']

