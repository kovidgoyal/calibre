#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2012, Kovid Goyal <kovid@kovidgoyal.net>
 Released under the GPLv3 License
###

log = (args...) -> # {{{
    if args
        msg = args.join(' ')
        if window?.console?.log
            window.console.log(msg)
        else if process?.stdout?.write
            process.stdout.write(msg + '\n')
# }}}

window_scroll_pos = (win=window) -> # {{{
    if typeof(win.pageXOffset) == 'number'
        x = win.pageXOffset
        y = win.pageYOffset
    else # IE < 9
        if document.body and ( document.body.scrollLeft or document.body.scrollTop )
            x = document.body.scrollLeft
            y = document.body.scrollTop
        else if document.documentElement and ( document.documentElement.scrollLeft or document.documentElement.scrollTop)
            y = document.documentElement.scrollTop
            x = document.documentElement.scrollLeft
    return [x, y]
# }}}

viewport_to_document = (x, y, doc=window?.document) -> # {{{
    until doc == window.document
        # We are in a frame
        frame = doc.defaultView.frameElement
        rect = frame.getBoundingClientRect()
        x += rect.left
        y += rect.top
        doc = frame.ownerDocument
    win = doc.defaultView
    [wx, wy] = window_scroll_pos(win)
    x += wx
    y += wy
    return [x, y]
# }}}

absleft = (elem) -> # {{{
    r = elem.getBoundingClientRect()
    return viewport_to_document(r.left, 0, elem.ownerDocument)[0]
# }}}

class PagedDisplay
    ###
    This class is a namespace to expose functions via the
    window.paged_display object. The most important functions are:

    layout(): causes the currently loaded document to be laid out in columns.
    ###

    constructor: () ->
        if not this instanceof arguments.callee
            throw new Error('PagedDisplay constructor called as function')
        this.set_geometry()
        this.page_width = 0
        this.screen_width = 0
        this.in_paged_mode = false
        this.current_margin_side = 0

    set_geometry: (cols_per_screen=2, margin_top=20, margin_side=40, margin_bottom=20) ->
        this.margin_top = margin_top
        this.margin_side = margin_side
        this.margin_bottom = margin_bottom
        this.cols_per_screen = cols_per_screen

    layout: () ->
        # When laying body out in columns, webkit bleeds the top margin of the
        # first block element out above the columns, leading to an extra top
        # margin for the page. We compensate for that here. Computing the
        # boundingrect of body is very expensive with column layout, so we do
        # it before the column layout is applied.
        document.body.style.marginTop = '0px'
        extra_margin = document.body.getBoundingClientRect().top

        ww = window.innerWidth

        # Calculate the column width so that cols_per_screen columns fit in the
        # window in such a way the right margin of the last column is <=
        # side_margin (it may be less if the window width is not a
        # multiple of n*(col_width+2*side_margin).

        n = this.cols_per_screen
        adjust = ww - Math.floor(ww/n)*n
        # Ensure that the margins are large enough that the adjustment does not
        # cause them to become negative semidefinite
        sm = Math.max(2*adjust, this.margin_side)
        # Minimum column width, for the cases when the window is too
        # narrow
        col_width = Math.max(100, ((ww - adjust)/n) - 2*sm)
        this.page_width = col_width + 2*sm
        this.screen_width = this.page_width * this.cols_per_screen

        body_style = window.getComputedStyle(document.body)
        fgcolor = body_style.getPropertyValue('color')
        bs = document.body.style

        bs.setProperty('-webkit-column-gap', (2*sm)+'px')
        bs.setProperty('-webkit-column-width', col_width+'px')
        bs.setProperty('-webkit-column-rule-color', fgcolor)
        bs.setProperty('overflow', 'visible')
        bs.setProperty('height', (window.innerHeight - this.margin_top - this.margin_bottom) + 'px')
        bs.setProperty('width', 'auto')
        bs.setProperty('margin-top', (this.margin_top - extra_margin)+'px')
        bs.setProperty('margin-bottom', this.margin_bottom+'px')
        bs.setProperty('margin-left', sm+'px')
        bs.setProperty('margin-right', sm+'px')
        for edge in ['left', 'right', 'top', 'bottom']
            bs.setProperty('padding-'+edge, '0px')
            bs.setProperty('border-'+edge+'-width', '0px')
        bs.setProperty('min-width', '0')
        bs.setProperty('max-width', 'none')
        bs.setProperty('min-height', '0')
        bs.setProperty('max-height', 'none')

        # Convert page-breaks to column-breaks
        for sheet in document.styleSheets
            for rule in sheet.rules
                if rule.type == 1 # CSSStyleRule
                    for prop in ['page-break-before', 'page-break-after', 'page-break-inside']
                        val = rule.style.getPropertyValue(prop)
                        if val
                            cprop = '-webkit-column-' + prop.substr(5)
                            priority = rule.style.getPropertyPriority(prop)
                            rule.style.setProperty(cprop, val, priority)

        this.in_paged_mode = true
        this.current_margin_side = sm
        return sm

    scroll_to_pos: (frac) ->
        # Scroll to the position represented by frac (number between 0 and 1)
        xpos = Math.floor(document.body.scrollWidth * frac)
        this.scroll_to_xpos(xpos)

    scroll_to_xpos: (xpos) ->
        # Scroll so that the column containing xpos is the left most column in
        # the viewport
        if typeof(xpos) != 'number'
            log(xpos, 'is not a number, cannot scroll to it!')
            return
        pos = 0
        until (pos <= xpos < pos + this.page_width)
            pos += this.page_width
        limit = document.body.scrollWidth - this.screen_width
        pos = limit if pos > limit
        window.scrollTo(pos, 0)

    current_pos: (frac) ->
        # The current scroll position as a fraction between 0 and 1
        limit = document.body.scrollWidth - window.innerWidth
        if limit <= 0
            return 0.0
        return window.pageXOffset / limit

    current_column_location: () ->
        # The location of the left edge of the left most column currently
        # visible in the viewport
        x = window.pageXOffset + Math.max(10, this.current_margin_side)
        edge = Math.floor(x/this.page_width) * this.page_width
        while edge < x
            edge += this.page_width
        return edge - this.page_width

    next_screen_location: () ->
        # The position to scroll to for the next screen (which could contain
        # more than one pages). Returns -1 if no further scrolling is possible.
        cc = this.current_column_location()
        ans = cc + this.screen_width
        limit = document.body.scrollWidth - window.innerWidth
        if ans > limit
            ans = if window.pageXOffset < limit then limit else -1
        return ans

    previous_screen_location: () ->
        # The position to scroll to for the previous screen (which could contain
        # more than one pages). Returns -1 if no further scrolling is possible.
        cc = this.current_column_location()
        ans = cc - this.screen_width
        if ans < 0
            # We ignore small scrolls (less than 15px) when going to previous
            # screen
            ans = if window.pageXOffset > 15 then 0 else -1
        return ans

    next_col_location: () ->
        # The position to scroll to for the next column (same as
        # next_screen_location() if columns per screen == 1). Returns -1 if no
        # further scrolling is possible.
        cc = this.current_column_location()
        ans = cc + this.page_width
        limit = document.body.scrollWidth - window.innerWidth
        if ans > limit
            ans = if window.pageXOffset < limit then limit else -1
        return ans

    previous_col_location: () ->
        # The position to scroll to for the previous column (same as
        # previous_screen_location() if columns per screen == 1). Returns -1 if
        # no further scrolling is possible.
        cc = this.current_column_location()
        ans = cc - this.page_width
        if ans < 0
            ans = if window.pageXOffset > 0 then 0 else -1
        return ans

    jump_to_anchor: (name) ->
        # Jump to the element identified by anchor name. Ensures that the left
        # most column in the viewport is the column containing the start of the
        # element and that the scroll position is at the start of the column.
        elem = document.getElementById(name)
        if not elem
            elems = document.getElementsByName(name)
            if elems
                elem = elems[0]
        if not elem
            return
        elem.scrollIntoView()
        if this.in_paged_mode
            # Ensure we are scrolled to the column containing elem
            this.scroll_to_xpos(absleft(elem) + 5)

    snap_to_selection: () ->
        # Ensure that the viewport is positioned at the start of the column
        # containing the start of the current selection
        if this.in_paged_mode
            sel = window.getSelection()
            r = sel.getRangeAt(0).getBoundingClientRect()
            node = sel.anchorNode
            left = viewport_to_document(r.left, r.top, doc=node.ownerDocument)[0]

            # Ensure we are scrolled to the column containing the start of the
            # selection
            this.scroll_to_xpos(left+5)

    jump_to_cfi: (cfi) ->
        # Jump to the position indicated by the specified conformal fragment
        # indicator (requires the cfi.coffee library). When in paged mode, the
        # scroll is performed so that the column containing the position
        # pointed to by the cfi is the left most column in the viewport
        window.cfi.scroll_to(cfi, (x, y) =>
            if this.in_paged_mode
                this.scroll_to_xpos(x)
            else
                window.scrollTo(0, y)
        )

    current_cfi: () ->
        # The Conformal Fragment Identifier at the current position, returns
        # null if it could not be calculated. Requires the cfi.coffee library.
        ans = null
        if not window.cfi?
            return ans
        if this.in_paged_mode
            c = this.current_column_location()
            for x in [c, c-this.page_width, c+this.page_width]
                # Try the current column, the previous column and the next
                # column. Each column is tried from top to bottom.
                [left, right] = [x, x + this.page_width]
                if left < 0 or right > document.body.scrollWidth
                    continue
                deltax = Math.floor(this.page_width/25)
                deltay = Math.floor(window.innerHeight/25)
                cury = this.margin_top
                until cury >= (window.innerHeight - this.margin_bottom)
                    curx = left + this.current_margin_side
                    until curx >= (right - this.current_margin_side)
                        cfi = window.cfi.at_point(curx-window.pageXOffset, cury-window.pageYOffset)
                        if cfi
                            log('Viewport cfi:', cfi)
                            return cfi
                        curx += deltax
                    cury += deltay
        else
            try
                ans = window.cfi.at_current()
                if not ans
                    ans = null
            catch err
                log(err)
        if ans
            log('Viewport cfi:', ans)
        return ans

if window?
    window.paged_display = new PagedDisplay()

# TODO:
# Go to reference positions
# Indexing
# Resizing of images
# Special handling for identifiable covers (colspan)?
# Full screen mode
