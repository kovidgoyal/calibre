#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os
from polyglot.builtins import itervalues, range

NBSP = '\xa0'


def mergeable(previous, current):
    if previous.tail or current.tail:
        return False
    if previous.get('class', None) != current.get('class', None):
        return False
    if current.get('id', False):
        return False
    for attr in ('style', 'lang', 'dir'):
        if previous.get(attr) != current.get(attr):
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
    prefixes = {x.partition('-')[0] for x in css}
    return not (prefixes - {'text', 'font', 'letter', 'color', 'background'})


def add_text(elem, attr, text):
    old = getattr(elem, attr) or ''
    setattr(elem, attr, old + text)


def lift(span):
    # Replace an element by its content (text, children and tail)
    parent = span.getparent()
    idx = parent.index(span)
    try:
        last_child = span[-1]
    except IndexError:
        last_child = None

    if span.text:
        if idx == 0:
            add_text(parent, 'text', span.text)
        else:
            add_text(parent[idx - 1], 'tail', span.text)

    for child in reversed(span):
        parent.insert(idx, child)
    parent.remove(span)

    if span.tail:
        if last_child is None:
            if idx == 0:
                add_text(parent, 'text', span.tail)
            else:
                add_text(parent[idx - 1], 'tail', span.tail)
        else:
            add_text(last_child, 'tail', span.tail)


def before_count(root, tag, limit=10):
    body = root.xpath('//body[1]')
    if not body:
        return limit
    ans = 0
    for elem in body[0].iterdescendants():
        if elem is tag:
            return ans
        ans += 1
        if ans > limit:
            return limit


def wrap_contents(tag_name, elem):
    wrapper = elem.makeelement(tag_name)
    wrapper.text, elem.text = elem.text, ''
    for child in elem:
        elem.remove(child)
        wrapper.append(child)
    elem.append(wrapper)


def cleanup_markup(log, root, styles, dest_dir, detect_cover, XPath):
    # Apply vertical-align
    for span in root.xpath('//span[@data-docx-vert]'):
        wrap_contents(span.attrib.pop('data-docx-vert'), span)

    # Move <hr>s outside paragraphs, if possible.
    pancestor = XPath('|'.join('ancestor::%s[1]' % x for x in ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6')))
    for hr in root.xpath('//span/hr'):
        p = pancestor(hr)
        if p:
            p = p[0]
            descendants = tuple(p.iterdescendants())
            if descendants[-1] is hr:
                parent = p.getparent()
                idx = parent.index(p)
                parent.insert(idx+1, hr)
                hr.tail = '\n\t'

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

    # Process dir attributes
    class_map = dict(itervalues(styles.classes))
    parents = ('p', 'div') + tuple('h%d' % i for i in range(1, 7))
    for parent in root.xpath('//*[(%s)]' % ' or '.join('name()="%s"' % t for t in parents)):
        # Ensure that children of rtl parents that are not rtl have an
        # explicit dir set. Also, remove dir from children if it is the same as
        # that of the parent.
        if len(parent):
            parent_dir = parent.get('dir')
            for child in parent.iterchildren('span'):
                child_dir = child.get('dir')
                if parent_dir == 'rtl' and child_dir != 'rtl':
                    child_dir = 'ltr'
                    child.set('dir', child_dir)
                if child_dir and child_dir == parent_dir:
                    child.attrib.pop('dir')

    # Remove unnecessary span tags that are the only child of a parent block
    # element
    for parent in root.xpath('//*[(%s) and count(span)=1]' % ' or '.join('name()="%s"' % t for t in parents)):
        if len(parent) == 1 and not parent.text and not parent[0].tail and not parent[0].get('id', None):
            # We have a block whose contents are entirely enclosed in a <span>
            span = parent[0]
            span_class = span.get('class', None)
            span_css = class_map.get(span_class, {})
            span_dir = span.get('dir')
            if liftable(span_css) and (not span_dir or span_dir == parent.get('dir')):
                pclass = parent.get('class', None)
                if span_class:
                    pclass = (pclass + ' ' + span_class) if pclass else span_class
                    parent.set('class', pclass)
                parent.text = span.text
                parent.remove(span)
                if span.get('lang'):
                    parent.set('lang', span.get('lang'))
                if span.get('dir'):
                    parent.set('dir', span.get('dir'))
                for child in span:
                    parent.append(child)

    # Make spans whose only styling is bold or italic into <b> and <i> tags
    for span in root.xpath('//span[@class and not(@style)]'):
        css = class_map.get(span.get('class', None), {})
        if len(css) == 1:
            if css == {'font-style':'italic'}:
                span.tag = 'i'
                del span.attrib['class']
            elif css == {'font-weight':'bold'}:
                span.tag = 'b'
                del span.attrib['class']

    # Get rid of <span>s that have no styling
    for span in root.xpath('//span[not(@class or @id or @style or @lang or @dir)]'):
        lift(span)

    # Convert <p><br style="page-break-after:always"> </p> style page breaks
    # into something the viewer will render as a page break
    for p in root.xpath('//p[br[@style="page-break-after:always"]]'):
        if len(p) == 1 and (not p[0].tail or not p[0].tail.strip()):
            p.remove(p[0])
            prefix = p.get('style', '')
            if prefix:
                prefix += '; '
            p.set('style', prefix + 'page-break-after:always')
            p.text = NBSP if not p.text else p.text

    if detect_cover:
        # Check if the first image in the document is possibly a cover
        img = root.xpath('//img[@src][1]')
        if img:
            img = img[0]
            path = os.path.join(dest_dir, img.get('src'))
            if os.path.exists(path) and before_count(root, img, limit=10) < 5:
                from calibre.utils.imghdr import identify
                try:
                    with lopen(path, 'rb') as imf:
                        fmt, width, height = identify(imf)
                except:
                    width, height, fmt = 0, 0, None  # noqa
                del fmt
                try:
                    is_cover = 0.8 <= height/width <= 1.8 and height*width >= 160000
                except ZeroDivisionError:
                    is_cover = False
                if is_cover:
                    log.debug('Detected an image that looks like a cover')
                    img.getparent().remove(img)
                    return path
