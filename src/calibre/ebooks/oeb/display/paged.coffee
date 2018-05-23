#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2012, Kovid Goyal <kovid@kovidgoyal.net>
 Released under the GPLv3 License
###

log = window.calibre_utils.log

runscripts = (parent) ->
    for script in parent.getElementsByTagName('script')
        eval(script.text || script.textContent || script.innerHTML || '')

first_child = (parent) ->
    c = parent.firstChild
    count = 0
    while c?.nodeType != 1 and count < 20
        c = c?.nextSibling
        count += 1
    if c?.nodeType == 1
        return c
    return null

has_start_text = (elem) ->
    # Returns true if elem has some non-whitespace text before its first child
    # element
    for c in elem.childNodes
        if c.nodeType not in [Node.TEXT_NODE, Node.COMMENT_NODE, Node.PROCESSING_INSTRUCTION_NODE]
            break
        if c.nodeType == Node.TEXT_NODE and c.nodeValue != null and /\S/.test(c.nodeValue)
            return true
    return false

create_page_div = (elem) ->
    div = document.createElement('blank-page-div')
    div.innerText = ' \n    '
    document.body.appendChild(div)
    div.style.setProperty('-webkit-column-break-before', 'always')
    div.style.setProperty('display', 'block')
    div.style.setProperty('white-space', 'pre')
    div.style.setProperty('background-color', 'transparent')
    div.style.setProperty('background-image', 'none')
    div.style.setProperty('border-width', '0')
    div.style.setProperty('float', 'none')
    div.style.setProperty('position', 'static')

class PagedDisplay
    # This class is a namespace to expose functions via the
    # window.paged_display object. The most important functions are:
    #
    # set_geometry(): sets the parameters used to layout text in paged mode
    #
    # layout(): causes the currently loaded document to be laid out in columns.

    constructor: () ->
        if not this instanceof arguments.callee
            throw new Error('PagedDisplay constructor called as function')
        this.set_geometry()
        this.page_width = 0
        this.screen_width = 0
        this.side_margin = 0
        this.in_paged_mode = false
        this.current_margin_side = 0
        this.is_full_screen_layout = false
        this.max_col_width = -1
        this.max_col_height = - 1
        this.current_page_height = null
        this.document_margins = null
        this.use_document_margins = false
        this.footer_template = null
        this.header_template = null
        this.header = null
        this.footer = null
        this.hf_style = null

    read_document_margins: () ->
        # Read page margins from the document. First checks for an @page rule.
        # If that is not found, side margins are set to the side margins of the
        # body element.
        if this.document_margins is null
            this.document_margins = {left:null, top:null, right:null, bottom:null}
            tmp = document.createElement('div')
            tmp.style.visibility = 'hidden'
            tmp.style.position = 'absolute'
            document.body.appendChild(tmp)
            for sheet in document.styleSheets
                if sheet.rules
                    for rule in sheet.rules
                        if rule.type == CSSRule.PAGE_RULE
                            for prop in ['left', 'top', 'bottom', 'right']
                                val = rule.style.getPropertyValue('margin-'+prop)
                                if val
                                    tmp.style.height = val
                                    pxval = parseInt(window.getComputedStyle(tmp).height)
                                    if not isNaN(pxval)
                                        this.document_margins[prop] = pxval
            document.body.removeChild(tmp)
            if this.document_margins.left is null
                val = parseInt(window.getComputedStyle(document.body).marginLeft)
                if not isNaN(val)
                    this.document_margins.left = val
            if this.document_margins.right is null
                val = parseInt(window.getComputedStyle(document.body).marginRight)
                if not isNaN(val)
                    this.document_margins.right = val

    set_geometry: (cols_per_screen=1, margin_top=20, margin_side=40, margin_bottom=20) ->
        this.cols_per_screen = cols_per_screen
        if this.use_document_margins and this.document_margins != null
            this.margin_top = if this.document_margins.top != null then this.document_margins.top else margin_top
            this.margin_bottom = if this.document_margins.bottom != null then this.document_margins.bottom else margin_bottom
            if this.document_margins.left != null
                this.margin_side = this.document_margins.left
            else if this.document_margins.right != null
                this.margin_side = this.document_margins.right
            else
                this.margin_side = margin_side
            this.effective_margin_top = this.margin_top
            this.effective_margin_bottom = this.margin_bottom
        else
            this.margin_top = margin_top
            this.margin_side = margin_side
            this.margin_bottom = margin_bottom
            this.effective_margin_top = this.margin_top
            this.effective_margin_bottom = this.margin_bottom

    handle_rtl_body: (body_style) ->
        if body_style.direction == "rtl"
            for node in document.body.childNodes
                if node.nodeType == node.ELEMENT_NODE and window.getComputedStyle(node).direction == "rtl"
                    node.style.setProperty("direction", "rtl")
            document.body.style.direction = "ltr"
            document.documentElement.style.direction = 'ltr'

    layout: (is_single_page=false) ->
        # start_time = new Date().getTime()
        body_style = window.getComputedStyle(document.body)
        bs = document.body.style
        first_layout = false
        if not this.in_paged_mode
            # Check if the current document is a full screen layout like
            # cover, if so we treat it specially.
            single_screen = (document.body.scrollHeight < window.innerHeight + 75)
            has_svg = document.getElementsByTagName('svg').length > 0
            only_img = document.getElementsByTagName('img').length == 1 and document.getElementsByTagName('div').length < 3 and document.getElementsByTagName('p').length < 2
            if only_img
                has_viewport = document.head and document.head.querySelector('meta[name="viewport"]')
                if has_viewport
                    # Has a viewport and only an img, is probably a comic, see for
                    # example: https://bugs.launchpad.net/bugs/1667357
                    single_screen = true
            this.handle_rtl_body(body_style)
            first_layout = true
            if not single_screen and this.cols_per_screen > 1
                num = this.cols_per_screen - 1
                elems = document.querySelectorAll('body > *')
                if elems.length == 1
                    # Workaround for the case when the content is wrapped in a
                    # 100% height <div>. This causes the generated page divs to
                    # not be in the correct location. See
                    # https://bugs.launchpad.net/bugs/1594657 for an example.
                    elems[0].style.height = 'auto'
                while num > 0
                    num -= 1
                    create_page_div()

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
        if this.max_col_width > 0 and col_width > this.max_col_width
            # Increase the side margin to ensure that col_width is no larger
            # than max_col_width
            sm += Math.ceil( (col_width - this.max_col_width) / 2*n )
            col_width = Math.max(100, ((ww - adjust)/n) - 2*sm)
        this.col_width = col_width
        this.page_width = col_width + 2*sm
        this.side_margin = sm
        this.screen_width = this.page_width * this.cols_per_screen

        fgcolor = body_style.getPropertyValue('color')

        bs.setProperty('box-sizing', 'content-box')
        bs.setProperty('-webkit-column-gap', 2*sm + 'px')
        bs.setProperty('-webkit-column-width', col_width + 'px')
        bs.setProperty('-webkit-column-rule', '0px inset blue')

        # Without this, webkit bleeds the margin of the first block(s) of body
        # above the columns, which causes them to effectively be added to the
        # page margins (the margin collapse algorithm)
        bs.setProperty('-webkit-margin-collapse', 'separate')
        c = first_child(document.body)
        if c != null
            # Remove page breaks on the first few elements to prevent blank pages
            # at the start of a chapter
            c.style.setProperty('-webkit-column-break-before', 'avoid')
            if c.tagName?.toLowerCase() == 'div'
                c2 = first_child(c)
                if c2 != null and not has_start_text(c)
                    # Common pattern of all content being enclosed in a wrapper
                    # <div>, see for example: https://bugs.launchpad.net/bugs/1366074
                    # In this case, we also modify the first child of the div
                    # as long as there was no text before it.
                    c2.style.setProperty('-webkit-column-break-before', 'avoid')


        this.effective_margin_top = this.margin_top
        this.effective_margin_bottom = this.margin_bottom
        this.current_page_height = window.innerHeight - this.margin_top - this.margin_bottom
        if this.max_col_height > 0 and this.current_page_height > this.max_col_height
            eh = Math.ceil((this.current_page_height - this.max_col_height) / 2)
            this.effective_margin_top += eh
            this.effective_margin_bottom += eh
            this.current_page_height -= 2 * eh

        bs.setProperty('overflow', 'visible')
        bs.setProperty('height', this.current_page_height + 'px')
        bs.setProperty('width', (window.innerWidth - 2*sm)+'px')
        bs.setProperty('padding-top', this.effective_margin_top + 'px')
        bs.setProperty('padding-bottom', this.effective_margin_bottom+'px')
        bs.setProperty('padding-left', sm+'px')
        bs.setProperty('padding-right', sm+'px')
        for edge in ['left', 'right', 'top', 'bottom']
            bs.setProperty('margin-'+edge, '0px')
            bs.setProperty('border-'+edge+'-width', '0px')
        bs.setProperty('min-width', '0')
        bs.setProperty('max-width', 'none')
        bs.setProperty('min-height', '0')
        bs.setProperty('max-height', 'none')

        # Convert page-breaks to column-breaks
        for sheet in document.styleSheets
            if sheet.rules
                for rule in sheet.rules
                    if rule.type == CSSRule.STYLE_RULE
                        for prop in ['page-break-before', 'page-break-after', 'page-break-inside']
                            val = rule.style.getPropertyValue(prop)
                            if val
                                cprop = '-webkit-column-' + prop.substr(5)
                                priority = rule.style.getPropertyPriority(prop)
                                rule.style.setProperty(cprop, val, priority)

        if first_layout
            # Because of a bug in webkit column mode, svg elements defined with
            # width 100% are wider than body and lead to a blank page after the
            # current page (when cols_per_screen == 1). Similarly img elements
            # with height=100% overflow the first column
            # We only set full_screen_layout if scrollWidth is in (body_width,
            # 2*body_width) as if it is <= body_width scrolling will work
            # anyway and if it is >= 2*body_width it can't be a full screen
            # layout
            body_width = document.body.offsetWidth + 2 * sm
            this.is_full_screen_layout = (only_img or has_svg) and single_screen and document.body.scrollWidth > body_width and document.body.scrollWidth < 2 * body_width
            if is_single_page
                this.is_full_screen_layout = true
            # Prevent the TAB key from shifting focus as it causes partial
            # scrolling
            document.documentElement.addEventListener('keydown', (evt) ->
                if evt.keyCode == 9
                    evt.preventDefault()
            )


        ncols = document.body.scrollWidth / this.page_width
        if ncols != Math.floor(ncols) and not this.is_full_screen_layout
            # In Qt 5 WebKit will sometimes adjust the individual column widths for
            # better text layout. This is allowed as per the CSS spec, so the
            # only way to ensure fixed column widths is to make sure the body
            # width is an exact multiple of the column widths
            bs.setProperty('width', Math.floor(ncols) * this.page_width - 2 * sm)

        this.in_paged_mode = true
        this.current_margin_side = sm
        # log('Time to layout:', new Date().getTime() - start_time)
        return sm

    create_header_footer: (uuid) ->
        if this.header_template != null
            this.header = document.createElement('div')
            this.header.setAttribute('style', "overflow:hidden; display:block; position:absolute; left:#{ this.side_margin }px; top: 0px; height: #{ this.effective_margin_top }px; width: #{ this.col_width }px; margin: 0; padding: 0")
            this.header.setAttribute('id', 'pdf_page_header_'+uuid)
            document.body.appendChild(this.header)
        if this.footer_template != null
            this.footer = document.createElement('div')
            this.footer.setAttribute('style', "overflow:hidden; display:block; position:absolute; left:#{ this.side_margin }px; top: #{ window.innerHeight - this.effective_margin_bottom }px; height: #{ this.effective_margin_bottom }px; width: #{ this.col_width }px; margin: 0; padding: 0")
            this.footer.setAttribute('id', 'pdf_page_footer_'+uuid)
            document.body.appendChild(this.footer)
        if this.header != null or this.footer != null
            this.hf_uuid = uuid
            this.hf_style = document.createElement('style')
            this.hf_style.setAttribute('type', 'text/css')
            document.head.appendChild(this.hf_style)
        this.update_header_footer(1)

    position_header_footer: () ->
        [left, top] = calibre_utils.viewport_to_document(0, 0, document.body.ownerDocument)
        if this.header != null
            this.header.style.setProperty('left', left+'px')
        if this.footer != null
            this.footer.style.setProperty('left', left+'px')

    update_header_footer: (pagenum) ->
        has_images = false
        this.header_footer_images = []
        if this.hf_style != null
            if pagenum%2 == 1 then cls = "even_page" else cls = "odd_page"
            this.hf_style.innerHTML = "#pdf_page_header_#{ this.hf_uuid } .#{ cls }, #pdf_page_footer_#{ this.hf_uuid } .#{ cls } { display: none }"
            title = py_bridge.title()
            author = py_bridge.author()
            section = py_bridge.section()
            tl_section = py_bridge.tl_section()
        if this.header != null
            this.header.innerHTML = this.header_template.replace(/_PAGENUM_/g, pagenum+"").replace(/_TITLE_/g, title+"").replace(/_AUTHOR_/g, author+"").replace(/_TOP_LEVEL_SECTION_/g, tl_section+"").replace(/_SECTION_/g, section+"")
            runscripts(this.header)
            for img in this.header.getElementsByTagName('img')
                this.header_footer_images.push(img)
                has_images = true
        if this.footer != null
            this.footer.innerHTML = this.footer_template.replace(/_PAGENUM_/g, pagenum+"").replace(/_TITLE_/g, title+"").replace(/_AUTHOR_/g, author+"").replace(/_TOP_LEVEL_SECTION_/g, tl_section+"").replace(/_SECTION_/g, section+"")
            runscripts(this.footer)
            for img in this.header.getElementsByTagName('img')
                this.header_footer_images.push(img)
                has_images = true
        has_images

    header_footer_images_loaded: () ->
        for img in this.header_footer_images
            if not img.complete
                return false
        return true

    fit_images: () ->
        # Ensure no images are wider than the available width in a column. Note
        # that this method use getBoundingClientRect() which means it will
        # force a relayout if the render tree is dirty.
        images = []
        vimages = []
        maxh = this.current_page_height
        for img in document.getElementsByTagName('img')
            previously_limited = calibre_utils.retrieve(img, 'width-limited', false)
            data = calibre_utils.retrieve(img, 'img-data', null)
            br = img.getBoundingClientRect()
            if data == null
                data = {'left':br.left, 'right':br.right, 'height':br.height, 'display': img.style.display}
                calibre_utils.store(img, 'img-data', data)
            left = calibre_utils.viewport_to_document(br.left, 0, doc=img.ownerDocument)[0]
            col = this.column_at(left) * this.page_width
            rleft = left - col - this.current_margin_side
            width  = br.right - br.left
            rright = rleft + width
            col_width = this.page_width - 2*this.current_margin_side
            if previously_limited or rright > col_width
                images.push([img, col_width - rleft])
            previously_limited = calibre_utils.retrieve(img, 'height-limited', false)
            if previously_limited or br.height > maxh
                vimages.push(img)
            if previously_limited
                img.style.setProperty('-webkit-column-break-before', 'auto')
                img.style.setProperty('display', data.display)
            img.style.setProperty('-webkit-column-break-inside', 'avoid')

        for [img, max_width] in images
            img.style.setProperty('max-width', max_width+'px')
            calibre_utils.store(img, 'width-limited', true)

        for img in vimages
            data = calibre_utils.retrieve(img, 'img-data', null)
            img.style.setProperty('-webkit-column-break-before', 'always')
            img.style.setProperty('max-height', maxh+'px')
            if data.height > maxh
                # This is needed to force the image onto a new page, without
                # it, the webkit algorithm may still decide to split the image
                # by keeping it part of its parent block
                img.style.setProperty('display', 'block')
            calibre_utils.store(img, 'height-limited', true)

    scroll_to_pos: (frac) ->
        # Scroll to the position represented by frac (number between 0 and 1)
        xpos = Math.floor(document.body.scrollWidth * frac)
        this.scroll_to_xpos(xpos)

    scroll_to_xpos: (xpos, animated=false, notify=false, duration=1000) ->
        # Scroll so that the column containing xpos is the left most column in
        # the viewport
        if typeof(xpos) != 'number'
            log(xpos, 'is not a number, cannot scroll to it!')
            return
        if this.is_full_screen_layout
            window.scrollTo(0, 0)
            return
        pos = Math.floor(xpos/this.page_width) * this.page_width
        limit = document.body.scrollWidth - this.screen_width
        pos = limit if pos > limit
        if animated
            this.animated_scroll(pos, duration=1000, notify=notify)
        else
            window.scrollTo(pos, 0)

    scroll_to_column: (number) ->
        this.scroll_to_xpos(number * this.page_width + 10)

    column_at: (xpos) ->
        # Return the number of the column that contains xpos
        return Math.floor(xpos/this.page_width)

    column_location: (elem) ->
        # Return the location of elem relative to its containing column.
        # WARNING: This method may cause the viewport to scroll (to workaround
        # a bug in WebKit).
        br = elem.getBoundingClientRect()
        # Because of a bug in WebKit's getBoundingClientRect() in column
        # mode, this position can be inaccurate, see
        # https://bugs.launchpad.net/calibre/+bug/1202390 for a test case.
        # The usual symptom of the inaccuracy is br.top is highly negative.
        if br.top < -100
            # We have to actually scroll the element into view to get its
            # position
            elem.scrollIntoView()
            [left, top] = calibre_utils.viewport_to_document(elem.scrollLeft, elem.scrollTop, elem.ownerDocument)
        else
            [left, top] = calibre_utils.viewport_to_document(br.left, br.top, elem.ownerDocument)
        c = this.column_at(left)
        width = Math.min(br.right, (c+1)*this.page_width) - br.left
        if br.bottom < br.top
            br.bottom = window.innerHeight
        height = Math.min(br.bottom, window.innerHeight) - br.top
        left -= c*this.page_width
        return {'column':c, 'left':left, 'top':top, 'width':width, 'height':height}

    column_boundaries: () ->
        # Return the column numbers at the left edge and after the right edge
        # of the viewport
        l = this.column_at(window.pageXOffset + 10)
        return [l, l + this.cols_per_screen]

    animated_scroll: (pos, duration=1000, notify=true) ->
        # Scroll the window to X-position pos in an animated fashion over
        # duration milliseconds. If notify is true, py_bridge.animated_scroll_done is
        # called.
        delta = pos - window.pageXOffset
        interval = 50
        steps = Math.floor(duration/interval)
        step_size = Math.floor(delta/steps)
        this.current_scroll_animation = {target:pos, step_size:step_size, interval:interval, notify:notify, fn: () =>
            a = this.current_scroll_animation
            npos = window.pageXOffset + a.step_size
            completed = false
            if Math.abs(npos - a.target) < Math.abs(a.step_size)
                completed = true
                npos = a.target
            window.scrollTo(npos, 0)
            if completed
                if notify
                    window.py_bridge.animated_scroll_done()
            else
                setTimeout(a.fn, a.interval)
        }
        this.current_scroll_animation.fn()

    current_pos: (frac) ->
        # The current scroll position as a fraction between 0 and 1
        limit = document.body.scrollWidth - window.innerWidth
        if limit <= 0
            return 0.0
        return window.pageXOffset / limit

    current_column_location: () ->
        # The location of the left edge of the left most column currently
        # visible in the viewport
        if this.is_full_screen_layout
            return 0
        x = window.pageXOffset + Math.max(10, this.current_margin_side)
        return Math.floor(x/this.page_width) * this.page_width

    next_screen_location: () ->
        # The position to scroll to for the next screen (which could contain
        # more than one pages). Returns -1 if no further scrolling is possible.
        if this.is_full_screen_layout
            return -1
        cc = this.current_column_location()
        ans = cc + this.screen_width
        if this.cols_per_screen > 1
            width_left = document.body.scrollWidth - (window.pageXOffset + window.innerWidth)
            pages_left = width_left / this.page_width
            if Math.ceil(pages_left) < this.cols_per_screen
                return -1  # Only blank, dummy pages left
        limit = document.body.scrollWidth - window.innerWidth
        if ans > limit
            ans = if window.pageXOffset < limit then limit else -1
        return ans

    previous_screen_location: () ->
        # The position to scroll to for the previous screen (which could contain
        # more than one pages). Returns -1 if no further scrolling is possible.
        if this.is_full_screen_layout
            return -1
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
        if this.is_full_screen_layout
            return -1
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
        if this.is_full_screen_layout
            return -1
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
        if window.mathjax?.math_present
            # MathJax links to children of SVG tags and scrollIntoView doesn't
            # work properly for them, so if this link points to something
            # inside an <svg> tag we instead scroll the parent of the svg tag
            # into view.
            parent = elem
            while parent and parent?.tagName?.toLowerCase() != 'svg'
                parent = parent.parentNode
            if parent?.tagName?.toLowerCase() == 'svg'
                elem = parent.parentNode
        elem.scrollIntoView()
        if this.in_paged_mode
            # Ensure we are scrolled to the column containing elem

            # Because of a bug in WebKit's getBoundingClientRect() in column
            # mode, this position can be inaccurate, see
            # https://bugs.launchpad.net/calibre/+bug/1132641 for a test case.
            # The usual symptom of the inaccuracy is br.top is highly negative.
            br = elem.getBoundingClientRect()
            if br.top < -100
                # This only works because of the preceding call to
                # elem.scrollIntoView(). However, in some cases it gives
                # inaccurate results, so we prefer the bounding client rect,
                # when possible.
                left = elem.scrollLeft
            else
                left = br.left
            this.scroll_to_xpos(calibre_utils.viewport_to_document(
                left+this.margin_side, elem.scrollTop, elem.ownerDocument)[0])

    snap_to_selection: () ->
        # Ensure that the viewport is positioned at the start of the column
        # containing the start of the current selection
        if this.in_paged_mode
            sel = window.getSelection()
            r = sel.getRangeAt(0).getBoundingClientRect()
            node = sel.anchorNode
            left = calibre_utils.viewport_to_document(r.left, r.top, doc=node.ownerDocument)[0]

            # Ensure we are scrolled to the column containing the start of the
            # selection
            this.scroll_to_xpos(left+5)

    jump_to_cfi: (cfi, job_id=-1) ->
        # Jump to the position indicated by the specified conformal fragment
        # indicator (requires the cfi.coffee library). When in paged mode, the
        # scroll is performed so that the column containing the position
        # pointed to by the cfi is the left most column in the viewport
        window.cfi.scroll_to(cfi, (x, y) =>
            if this.in_paged_mode
                this.scroll_to_xpos(x)
            else
                window.scrollTo(0, y)
            if window.py_bridge
                window.py_bridge.jump_to_cfi_finished(job_id)
        )

    current_cfi: () ->
        # The Conformal Fragment Identifier at the current position, returns
        # null if it could not be calculated. Requires the cfi.coffee library.
        ans = null
        if not window.cfi? or (window.mathjax?.math_present and not window.mathjax?.math_loaded)
            # If MathJax is loading, it is changing the DOM, so we cannot
            # reliably generate a CFI
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
                cury = this.effective_margin_top
                until cury >= (window.innerHeight - this.effective_margin_bottom)
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

    click_for_page_turn: (event) ->
        # Check if the click event should generate a page turn. Returns
        # null if it should not, true if it is a backwards page turn, false if
        # it is a forward page turn.
        left_boundary = this.current_margin_side
        right_bondary = this.screen_width - this.current_margin_side
        if left_boundary > event.clientX
            return true
        if right_bondary < event.clientX
            return false
        return null

if window?
    window.paged_display = new PagedDisplay()

# TODO:
# Highlight on jump_to_anchor
