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
