#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import time, os, hashlib
from operator import attrgetter
from collections import defaultdict
from functools import partial

from calibre import jsbrowser
from calibre.ebooks.chardet import strip_encoding_declarations
from calibre.utils.imghdr import what
from calibre.web.jsbrowser.browser import Timeout

# remove_comments() {{{
remove_comments = '''
function remove_comments(node) {
    var nodes = node.childNodes, i=0, t;
    while((t = nodes.item(i++))) {
        switch(t.nodeType){
            case Node.ELEMENT_NODE:
                remove_comments(t);
                break;
            case Node.COMMENT_NODE:
                node.removeChild(t);
                i--;
        }
    }
}
remove_comments(document)
'''  # }}}

class AbortFetch(ValueError):
    pass

def children(elem):
    elem = elem.firstChild()
    while not elem.isNull():
        yield elem
        elem = elem.nextSibling()

def apply_keep_only(browser, keep_only):
    mf = browser.page.mainFrame()
    body = mf.findFirstElement('body')
    if body.isNull():
        browser.log.error('Document has no body, cannot apply keep_only')
        return
    keep = []
    for selector in keep_only:
        keep.extend(x for x in mf.findAllElements(selector))
    if not keep:
        browser.log.error('Failed to find any elements matching the keep_only selectors: %r' % keep_only)
        return
    for elem in keep:
        body.appendInside(elem)
    for elem in tuple(children(body)):
        preserve = False
        for x in keep:
            if x == elem:
                preserve = True
                break
        if preserve:
            break
        elem.removeFromDocument()

def apply_remove(browser, remove):
    mf = browser.page.mainFrame()
    for selector in remove:
        for elem in mf.findAllElements(selector):
            if not elem.isNull():
                elem.removeFromDocument()

def remove_beyond(browser, selector, before=True):
    mf = browser.page.mainFrame()
    elem = mf.findFirstElement(selector)
    if elem.isNull():
        browser.log('Failed to find any element matching the selector: %s' % selector)
        return
    next_sibling = attrgetter('previousSibling' if before else 'nextSibling')

    while not elem.isNull() and unicode(elem.tagName()) != 'body':
        remove = []
        after = next_sibling(elem)()
        while not after.isNull():
            remove.append(after)
            after = next_sibling(after)()
        for x in remove:
            x.removeFromDocument()
        elem = elem.parent()

def is_tag(elem, name):
    return unicode(elem.tagName()).lower() == name.lower()

def download_resources(browser, resource_cache, output_dir):
    img_counter = style_counter = 0
    resources = defaultdict(list)
    for img in browser.css_select('img[src]', all=True):
        # Using javascript ensures that absolute URLs are returned, direct
        # attribute access does not do that
        src = unicode(img.evaluateJavaScript('this.src').toString()).strip()
        if src:
            resources[src].append(img)
    for link in browser.css_select('link[href]', all=True):
        lt = unicode(link.attribute('type')).strip() or 'text/css'
        rel = unicode(link.attribute('rel')).strip() or 'stylesheet'
        if lt == 'text/css' and rel == 'stylesheet':
            href = unicode(link.evaluateJavaScript('this.href').toString()).strip()
            if href:
                resources[href].append(link)
            else:
                link.removeFromDocument()
        else:
            link.removeFromDocument()
    loaded_resources = browser.wait_for_resources(resources)
    for url, raw in loaded_resources.iteritems():
        h = hashlib.sha1(raw).digest()
        if h in resource_cache:
            href = os.path.relpath(resource_cache[h], output_dir).replace(os.sep, '/')
        else:
            elem = resources[url][0]
            if is_tag(elem, 'link'):
                style_counter += 1
                href = 'style_%d.css' % style_counter
            else:
                img_counter += 1
                ext = what(None, raw) or 'jpg'
                if ext == 'jpeg':
                    ext = 'jpg'  # Apparently Moon+ cannot handle .jpeg
                href = 'img_%d.%s' % (img_counter, ext)
            dest = os.path.join(output_dir, href)
            resource_cache[h] = dest
            with open(dest, 'wb') as f:
                f.write(raw)
        for elem in resources[url]:
            elem.setAttribute('href' if is_tag(elem, 'link') else 'src', href)

    failed = set(resources) - set(loaded_resources)
    for url in failed:
        browser.log.warn('Failed to download resource:', url)
        for elem in resources[url]:
            elem.removeFromDocument()

def save_html(browser, output_dir, postprocess_html, url, recursion_level):
    html = strip_encoding_declarations(browser.html)
    import html5lib
    root = html5lib.parse(html, treebuilder='lxml', namespaceHTMLElements=False).getroot()
    root = postprocess_html(root, url, recursion_level)
    if root is None:
        # user wants this page to be aborted
        raise AbortFetch('%s was aborted during postprocess' % url)
    with open(os.path.join(output_dir, 'index.html'), 'wb') as f:
        from lxml.html import tostring
        f.write(tostring(root, include_meta_content_type=True, encoding='utf-8', pretty_print=True))
        return f.name

def links_from_selectors(selectors, recursions, browser, url, recursion_level):
    ans = []
    if recursions > recursion_level:
        for selector in selectors:
            for a in browser.css_select(selector, all=True):
                href = unicode(a.evaluateJavaScript('this.href').toString()).strip()
                if href:
                    ans.append(href)
    return ans


def clean_dom(
    browser, url, recursion_level, preprocess_browser, remove_javascript,
    keep_only, remove_after, remove_before, remove):

    # Remove comments as otherwise we can end up with nested comments, which
    # cause problems later
    browser.page.mainFrame().evaluateJavaScript(remove_comments)

    preprocess_browser(browser, url, 1, recursion_level)
    if remove_javascript:
        for elem in browser.css_select('script', all=True):
            elem.removeFromDocument()
    if keep_only:
        apply_keep_only(browser, keep_only)
    if remove_after:
        remove_beyond(browser, remove_after, before=False)
    if remove_before:
        remove_beyond(browser, remove_before, before=True)
    if remove:
        apply_remove(browser, remove)
    preprocess_browser(browser, url, 2, recursion_level)

def fetch_page(
    url=None,
    load_complete=lambda browser, url, recursion_level: True,
    links=lambda browser, url, recursion_level: (),
    keep_only=(),
    remove_after=None,
    remove_before=None,
    remove=(),
    remove_javascript=True,
    delay=0,
    preprocess_browser=lambda browser, url, stage, recursion_level:None,
    postprocess_html=lambda root, url, recursion_level: root,
    resource_cache={},
    output_dir=None,
    browser=None,
    recursion_level=0
    ):

    output_dir = output_dir or os.getcwdu()
    if browser is None:
        browser = jsbrowser()

    if delay:
        time.sleep(delay)

    # Load the DOM
    if url is not None:
        start_time = time.time()
        browser.start_load(url)
        while not load_complete(browser, url, recursion_level):
            browser.run_for_a_time(0.1)
            if time.time() - start_time > browser.default_timeout:
                raise Timeout('Timed out while waiting for %s to load' % url)

    children = links(browser, url, recursion_level)

    # Cleanup the DOM
    clean_dom(
        browser, url, recursion_level, preprocess_browser,
        remove_javascript, keep_only, remove_after, remove_before, remove)

    # Download resources
    download_resources(browser, resource_cache, output_dir)

    # Get HTML from the DOM
    pages = [save_html(browser, output_dir, postprocess_html, url, recursion_level)]

    # Fetch the linked pages
    for i, curl in enumerate(children):
        odir = os.path.join(output_dir, 'link%d' % (i + 1))
        if not os.path.exists(odir):
            os.mkdir(odir)
        try:
            pages.extend(fetch_page(
                curl, load_complete=load_complete, links=links, keep_only=keep_only,
                remove_after=remove_after, remove_before=remove_before, remove=remove,
                preprocess_browser=preprocess_browser, postprocess_html=postprocess_html,
                resource_cache=resource_cache, output_dir=odir, browser=browser, delay=delay,
                recursion_level=recursion_level+1))
        except AbortFetch:
            continue
    return tuple(pages)

if __name__ == '__main__':
    browser = jsbrowser()
    fetch_page('http://www.time.com/time/magazine/article/0,9171,2145057,00.html', browser=browser,
               links=partial(links_from_selectors, ('.wp-paginate a.page[href]',), 1),
               keep_only=('article.post',), remove=('.entry-sharing', '.entry-footer', '.wp-paginate', '.post-rail'))




