#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2012, Kovid Goyal <kovid at kovidgoyal.net>
 Released under the GPLv3 License
###

if window?.calibre_utils
    log = window.calibre_utils.log

merge = (node, cnode) ->
    rules = node.ownerDocument.defaultView.getMatchedCSSRules(node, '')
    if rules
        for rule in rules
            style = rule.style
            for name in style
                val = style.getPropertyValue(name)
                if val and not cnode.style.getPropertyValue(name)
                    cnode.style.setProperty(name, val)

inline_styles = (node) ->
    cnode = node.cloneNode(true)
    merge(node, cnode)
    nl = node.getElementsByTagName('*')
    cnl = cnode.getElementsByTagName('*')
    for node, i in nl
        merge(node, cnl[i])

    return cnode

get_epub_type = (node, possible_values) ->
    # Try to get the value of the epub:type attribute. Complex as we dont
    # operate in XML mode
    epub_type = node.getAttributeNS("http://www.idpf.org/2007/ops", 'type') or node.getAttribute('epub:type')
    if not epub_type
        for x in node.attributes  # consider any xxx:type="noteref" attribute as marking a note
            if x.nodeName and x.nodeValue in possible_values and x.nodeName.slice(-':type'.length) == ':type'
                epub_type = x.nodeValue
                break
    return epub_type

get_containing_block = (node) ->
    until node?.tagName?.toLowerCase() in ['p', 'div', 'li', 'td', 'h1', 'h2', 'h2', 'h3', 'h4', 'h5', 'h6', 'body']
        node = node.parentNode
        if not node
            break
    return node

trim = (str) ->
    return str.replace(/^\s\s*/, '').replace(/\s\s*$/, '')

is_footnote_link = (node, url, linked_to_anchors, prefix) ->
    if not url or url.substr(0, prefix.length) != prefix
        return false  # Ignore non-local links
    epub_type = get_epub_type(node, ['noteref'])
    if epub_type and epub_type.toLowerCase() == 'noteref'
        return true
    if epub_type and epub_type == 'link'
        return false

    # Check if node or any of its first few parents have vertical-align set
    [x, num] = [node, 3]
    while x and num > 0
        style = window.getComputedStyle(x)
        if not style.display not in ['inline', 'inline-block']
            break
        if style.verticalAlign in ['sub', 'super', 'top', 'bottom']
            return true
        x = x.parentNode
        num -= 1

    # Check if node has a single child with the appropriate css
    children = (x for x in node.childNodes when x.nodeType == Node.ELEMENT_NODE)
    if children.length == 1
        style = window.getComputedStyle(children[0])
        if style.display in ['inline', 'inline-block'] and style.verticalAlign in ['sub', 'super', 'top', 'bottom']
            text_children = (x for x in node.childNodes when x.nodeType == Node.TEXT_NODE and x.nodeValue and /\S+/.test(x.nodeValue))
            if not text_children.length
                return true

    eid = node.getAttribute('id') or node.getAttribute('name')
    if eid and linked_to_anchors.hasOwnProperty(eid)
        # An <a href="..." id="..."> link that is linked back from some other
        # file in the spine, most likely an endnote. We exclude links that are
        # the only content of their parent block tag, as these are not likely
        # to be endnotes.
        cb = get_containing_block(node)
        if not cb or cb.tagName.toLowerCase() == 'body'
            return false
        ltext = node.textContent
        if not ltext
            return false
        ctext = cb.textContent
        if not ctext
            return false
        if trim(ctext) == trim(ltext)
            return false
        return true

    return false

is_epub_footnote = (node) ->
    pv = ['note', 'footnote', 'rearnote']
    epub_type = get_epub_type(node, pv)
    if epub_type and epub_type.toLowerCase() in pv
        return true
    return false

block_tags = ['p', 'div', 'li', 'td', 'h1', 'h2', 'h2', 'h3', 'h4', 'h5', 'h6', 'body']
block_display_styles = ['block', 'list-item', 'table-cell', 'table']

get_note_container = (node) ->
    until node.tagName.toLowerCase() in block_tags or is_epub_footnote(node) or getComputedStyle(node).display in block_display_styles
        node = node.parentNode
        if not node
            break
    return node

get_parents_and_self = (node) ->
    ans = []
    while node and node isnt document.body
        ans.push(node)
        node = node.parentNode
    return ans

get_page_break = (node) ->
    style = getComputedStyle(node)
    ans = {}
    for x in ['before', 'after']
        ans[x] = style.getPropertyValue('page-break-'.concat(x)) in ['always', 'left', 'right']
    return ans

hide_children = (node) ->
    for child in node.childNodes
        if child.nodeType == Node.ELEMENT_NODE
            if child.do_not_hide
                hide_children(child)
                delete child.do_not_hide
            else
                child.style.display = 'none'

unhide_tree = (elem) ->
    elem.do_not_hide = true
    for c in elem.getElementsByTagName('*')
        c.do_not_hide = true

class CalibreExtract
    # This class is a namespace to expose functions via the
    # window.calibre_extract object.

    constructor: () ->
        if not this instanceof arguments.callee
            throw new Error('CalibreExtract constructor called as function')
        this.marked_node = null

    mark: (node) =>
        this.marked_node = node

    extract: (node=null) =>
        if node == null
            node = this.marked_node
        cnode = inline_styles(node)
        return cnode.outerHTML

    is_footnote_link: (a, prefix, linked_to_anchors) ->
        return is_footnote_link(a, a.href, linked_to_anchors, prefix)

    show_footnote: (target, known_targets) ->
        if not target
            return
        start_elem = document.getElementById(target)
        if not start_elem
            return
        start_elem = get_note_container(start_elem)
        for elem in get_parents_and_self(start_elem)
            elem.do_not_hide = true
            style = window.getComputedStyle(elem)
            if style.display == 'list-item' and style.listStyleType not in ['disc', 'circle', 'square']
                # We cannot display list numbers since they will be
                # incorrect as we are removing siblings of this element.
                elem.style.listStyleType = 'none'
        if is_epub_footnote(start_elem)
            unhide_tree(start_elem)
        else
            # Try to detect natural boundaries based on markup for this note
            found_note_start = false
            for elem in document.body.getElementsByTagName('*')
                if found_note_start
                    eid = elem.getAttribute('id')
                    if eid != target and known_targets.hasOwnProperty(eid) and get_note_container(elem) != start_elem
                        console.log('Breaking footnote on anchor: ' + elem.getAttribute('id'))
                        delete get_note_container(elem).do_not_hide
                        break
                    pb = get_page_break(elem)
                    if pb['before']
                        console.log('Breaking footnote on page break before')
                        break
                    if pb['after']
                        unhide_tree(elem)
                        console.log('Breaking footnote on page break after')
                        break
                    elem.do_not_hide = true
                else if elem is start_elem
                    found_note_start = true

        hide_children(document.body)
        location.hash = '#' + target

if window?
    window.calibre_extract = new CalibreExtract()
