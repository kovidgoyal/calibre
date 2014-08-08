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

is_footnote_link = (node, url) ->
    if not url or url.substr(0, 'file://'.length).toLowerCase() != 'file://'
        return false  # Ignore non-local links
    # Check for epub:type="noteref", a little complex as we dont operate in XML
    # mode
    epub_type = node.getAttributeNS("http://www.idpf.org/2007/ops", 'type') or node.getAttribute('epub:type')
    if not epub_type
        for x in node.attributes  # consider any xxx:type="noteref" attribute as marking a note
            if x.nodeName and x.nodeValue == 'noteref' and x.nodeName.slice(-':type'.length) == ':type'
                epub_type = 'noteref'
                break
    if epub_type and epub_type.toLowerCase() == 'noteref'
        return true

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

    return false

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

    get_footnote_data: () =>
        ans = {}
        for a in document.querySelectorAll('a[href]')
            url = a.href  # .href returns the full URL while getAttribute() returns the value of the attribute
            if not is_footnote_link(a, url)
                continue
            ans[url] = 1
        return JSON.stringify(ans)

if window?
    window.calibre_extract = new CalibreExtract()


