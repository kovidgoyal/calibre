#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2013, Kovid Goyal <kovid at kovidgoyal.net>
 Released under the GPLv3 License
###


if window?.calibre_utils
    log = window.calibre_utils.log

is_hidden = (elem) ->
    while elem
        if (elem.style && (elem.style.visibility == 'hidden' || elem.style.display == 'none'))
            return true
        elem = elem.parentNode
    return false

is_block = (elem) ->
    style = window.getComputedStyle(elem)
    return style.display in ['block', 'flex-box', 'box']

in_table = (elem) ->
    while elem
        if elem.tagName?.toLowerCase() == 'table'
            return true
        elem = elem.parentNode
    return false

find_containing_block = (elem) ->
    while elem and elem.getAttribute('data-is-block') != '1'
        elem = elem.parentNode
    return elem

class PreviewIntegration

    ###
    # Namespace to expose all the functions used for integration with the Tweak
    # Book Preview Panel.
    ###

    constructor: () ->
        if not this instanceof arguments.callee
            throw new Error('PreviewIntegration constructor called as function')
        this.blocks_found = false
        this.in_split_mode = false

    go_to_line: (lnum) =>
        for node in document.querySelectorAll('[data-lnum="' + lnum + '"]')
            if is_hidden(node)
                continue
            if node is document.body
                window.scrollTo(0, 0)
            else
                node.scrollIntoView()
            return

    line_numbers: () =>
        found_body = false
        ans = []
        for node in document.getElementsByTagName('*')
            if not found_body and node.tagName.toLowerCase() == "body"
                found_body = true
            if found_body
                ans.push(node.getAttribute("data-lnum"))
        return ans

    find_blocks: () =>
        if this.blocks_found
            return
        for elem in document.body.getElementsByTagName('*')
            if is_block(elem) and not in_table(elem)
                elem.setAttribute('data-is-block', '1')
        this.blocks_found = true

    split_mode: (enabled) =>
        this.in_split_mode = enabled
        document.body.setAttribute('data-in-split-mode', if enabled then '1' else '0')
        if enabled
            this.find_blocks()

    report_split: (node) =>
        loc = []
        totals = []
        parent = find_containing_block(node)
        while parent and parent.tagName.toLowerCase() != 'body'
            totals.push(parent.parentNode.children.length)
            num = 0
            sibling = parent.previousElementSibling
            while sibling
                num += 1
                sibling = sibling.previousElementSibling
            loc.push(num)
            parent = parent.parentNode
        loc.reverse()
        totals.reverse()
        window.py_bridge.request_split(JSON.stringify(loc), JSON.stringify(totals))

    onload: () =>
        window.document.body.addEventListener('click', this.onclick, true)

    onclick: (event) =>
        event.preventDefault()
        if this.in_split_mode
            this.report_split(event.target)
        else
            e = event.target
            # Find the closest containing link, if any
            lnum = e.getAttribute('data-lnum')
            href = tn = ''
            while e and e != document.body and e != document and (tn != 'a' or not href)
                tn = e.tagName?.toLowerCase()
                href = e.getAttribute('href')
                e = e.parentNode
            window.py_bridge.request_sync(tn, href, lnum)
        return false

    go_to_anchor: (anchor, lnum) =>
        elem = document.getElementById(anchor)
        if not elem
            elem = document.querySelector('[name="' + anchor + '"]')
        if elem
            elem.scrollIntoView()
            lnum = elem.getAttribute('data-lnum')
        window.py_bridge.request_sync('', '', lnum)

window.calibre_preview_integration = new PreviewIntegration()
window.onload = window.calibre_preview_integration.onload

