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

is_footnote_link = (node, url, linked_to_anchors) ->
    if not url or url.substr(0, 'file://'.length).toLowerCase() != 'file://'
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
        if style.verticalAlign in ['sub', 'super']
            return true
        x = x.parentNode
        num -= 1

    # Check if node has a single child with the appropriate css
    children = (x for x in node.childNodes when x.nodeType == Node.ELEMENT_NODE)
    if children.length == 1
        style = window.getComputedStyle(children[0])
        if style.verticalAlign in ['sub', 'super']
            return true

    eid = node.getAttribute('id') or node.getAttribute('name')
    if eid and linked_to_anchors.hasOwnProperty(eid)
        # An <a href="..." id="..."> link that is linked back from some other
        # file in the spine, most likely a footnote
        return true

    return false

is_epub_footnote = (node) ->
    pv = ['note', 'footnote', 'rearnote']
    epub_type = get_epub_type(node, pv)
    if epub_type and epub_type.toLowerCase() in pv
        return true
    return false

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
            else
                child.style.display = 'none'

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

    is_footnote_link: (a) ->
        return is_footnote_link(a, a.href, py_bridge.value)

    show_footnote: (target, known_targets) ->
        if not target
            return
        start_elem = document.getElementById(target)
        if not start_elem
            return
        in_note = false
        is_footnote_container = is_epub_footnote(start_elem)
        for elem in get_parents_and_self(start_elem)
            elem.do_not_hide = true
        for elem in document.body.getElementsByTagName('*')
            if in_note
                if known_targets.hasOwnProperty(elem.getAttribute('id'))
                    in_note = false
                    continue
                pb = get_page_break(elem)
                if pb['before']
                    in_note = false
                else if pb['after']
                    in_note = false
                    for child in elem.getElementsByTagName('*')
                        child.do_not_hide = true
                else
                    elem.do_not_hide = true
            else
                if elem is start_elem
                    in_note = not is_footnote_container and not get_page_break(elem)['after']
                    if not in_note
                        for child in elem.getElementsByTagName('*')
                            child.do_not_hide = true
        hide_children(document.body)
        location.hash = '#' + target

if window?
    window.calibre_extract = new CalibreExtract()


