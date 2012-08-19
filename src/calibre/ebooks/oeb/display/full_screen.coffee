#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2012, Kovid Goyal <kovid at kovidgoyal.net>
 Released under the GPLv3 License
###


log = window.calibre_utils.log

class FullScreen
    # This class is a namespace to expose functions via the
    # window.full_screen object. The most important functions are:

    constructor: () ->
        if not this instanceof arguments.callee
            throw new Error('FullScreen constructor called as function')
        this.in_full_screen = false
        this.initial_left_margin = null
        this.initial_right_margin = null

    save_margins: () ->
        bs = document.body.style
        this.initial_left_margin = bs.marginLeft
        this.initial_right_margin = bs.marginRight

    on: (max_text_width, in_paged_mode) ->
        if in_paged_mode
            window.paged_display.max_col_width = max_text_width
        else
            s = document.body.style
            s.maxWidth = max_text_width + 'px'
            s.marginLeft = 'auto'
            s.marginRight = 'auto'
        window.addEventListener('click', this.handle_click, false)

    off: (in_paged_mode) ->
        window.removeEventListener('click', this.handle_click, false)
        if in_paged_mode
            window.paged_display.max_col_width = -1
        else
            s = document.body.style
            s.maxWidth = 'none'
            if this.initial_left_margin != null
                s.marginLeft = this.initial_left_margin
            if this.initial_right_margin != null
                s.marginRight = this.initial_right_margin

    handle_click: (event) ->
        if event.target != document.documentElement or event.button != 0
            return
        res = null
        if window.paged_display.in_paged_mode
            res = window.paged_display.click_for_page_turn(event)
        else
            br = document.body.getBoundingClientRect()
            if not (br.left <= event.clientX <= br.right)
                res = event.clientX < br.left
        if res != null
            window.py_bridge.page_turn_requested(res)

if window?
    window.full_screen = new FullScreen()

