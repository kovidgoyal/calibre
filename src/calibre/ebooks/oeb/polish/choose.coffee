#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2013, Kovid Goyal <kovid at kovidgoyal.net>
 Released under the GPLv3 License
###


if window?.calibre_utils
    log = window.calibre_utils.log

class AnchorLocator

    ###
    # Allow the user to click on any block level element to choose it as the
    # location for an anchor.
    ###
    constructor: () ->
        if not this instanceof arguments.callee
            throw new Error('AnchorLocator constructor called as function')

    find_blocks: () =>
        for elem in document.body.getElementsByTagName('*')
            style = window.getComputedStyle(elem)
            if style.display in ['block', 'flex-box', 'box']
                elem.className += " calibre_toc_hover"
                elem.onclick = this.onclick

    onclick: (event) ->
        # We dont want this event to trigger onclick on this element's parent
        # block, if any.
        event.stopPropagation()
        frac = window.pageYOffset/document.body.scrollHeight
        window.py_bridge.onclick(this, frac)
        return false

calibre_anchor_locator = new AnchorLocator()
calibre_anchor_locator.find_blocks()


