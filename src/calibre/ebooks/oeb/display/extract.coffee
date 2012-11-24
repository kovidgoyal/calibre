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

if window?
    window.calibre_extract = new CalibreExtract()


