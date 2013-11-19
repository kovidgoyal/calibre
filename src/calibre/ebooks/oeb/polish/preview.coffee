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

class PreviewIntegration

    ###
    # Namespace to expose all the functions used for integration with the Tweak
    # Book Preview Panel.
    ###

    constructor: () ->
        if not this instanceof arguments.callee
            throw new Error('PreviewIntegration constructor called as function')

    go_to_line: (lnum) ->
        for node in document.querySelectorAll('[data-lnum="' + lnum + '"]')
            if is_hidden(node)
                continue
            top = window.calibre_utils.abstop(node) - (window.innerHeight / 2)
            if (top < 0)
                top = 0
            window.scrollTo(0, top)
            return

    line_numbers: () ->
        found_body = false
        ans = []
        for node in document.getElementsByTagName('*')
            if not found_body and node.tagName.toLowerCase() == "body"
                found_body = true
            if found_body
                ans.push(node.getAttribute("data-lnum"))
        return ans

    find_blocks: () =>
        for elem in document.body.getElementsByTagName('*')
            style = window.getComputedStyle(elem)
            if style.display in ['block', 'flex-box', 'box']
                elem.setAttribute('data-is-block', '1')
                elem.onclick = this.onclick

    onload: () ->
        window.document.body.addEventListener('click', window.calibre_preview_integration.onclick, true)

    onclick: (event) ->
        event.preventDefault()
        window.py_bridge.request_sync(event.target.getAttribute("data-lnum"))

window.calibre_preview_integration = new PreviewIntegration()
window.onload = window.calibre_preview_integration.onload

