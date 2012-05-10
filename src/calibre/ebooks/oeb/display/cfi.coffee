#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2011, Kovid Goyal <kovid@kovidgoyal.net>
 Released under the GPLv3 License
 Based on code originally written by Peter Sorotkin
 http://code.google.com/p/epub-revision/source/browse/trunk/src/samples/cfi/epubcfi.js

 Improvements with respect to that code:
 1. Works on all browsers (WebKit, Firefox and IE >= 9)
 2. Works for content in elements that are scrollable (i.e. have their own scrollbars)
 3. Much more comprehensive testing/error handling
 4. Properly encodes/decodes assertions
 5. Handles points in the padding of elements consistently
 6. Has a utility method to calculate the CFI for the current viewport position robustly

 To check if this script is compatible with the current browser, call
 window.cfi.is_compatible() it will throw an exception if not compatible.

 Tested on: Firefox 9, IE 9, Chromium 16, Qt WebKit 2.1
###

log = (error) -> # {{{
    if error
        if window?.console?.log
            window.console.log(error)
        else if process?.stdout?.write
            process.stdout.write(error + '\n')
# }}}

# CFI escaping {{{
escape_for_cfi = (raw) ->
    if raw
        for c in ['^', '[', ']', ',', '(', ')', ';', '~', '@', '-', '!']
            raw = raw.replace(c, '^'+c)
    raw

unescape_from_cfi = (raw) ->
    ans = raw
    if raw
        dropped = false
        ans = []
        for c in raw
            if not dropped and c == '^'
                dropped = true
                continue
            dropped = false
            ans.push(c)
        ans = ans.join('')
    ans
# }}}

fstr = (d) -> # {{{
    # Convert a timestamp floating point number to a string
    ans = ""
    if ( d < 0 )
        ans = "-"
        d = -d
    n = Math.floor(d)
    ans += n
    n = Math.round((d-n)*100)
    if( n != 0 )
        ans += "."
        ans += if (n % 10 == 0) then (n/10) else n
    ans
# }}}

get_current_time = (target) -> # {{{
    ans = 0
    if target.currentTime != undefined
        ans = target.currentTime
    fstr(ans)
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

# Convert point to character offset {{{
range_has_point = (range, x, y) ->
    for rect in range.getClientRects()
        if (rect.left <= x <= rect.right) and (rect.top <= y <= rect.bottom)
            return true
    return false

offset_in_text_node = (node, range, x, y) ->
    limits = [0, node.nodeValue.length]
    while limits[0] != limits[1]
        pivot = Math.floor( (limits[0] + limits[1]) / 2 )
        lr = [limits[0], pivot]
        rr = [pivot+1, limits[1]]
        range.setStart(node, pivot)
        range.setEnd(node, pivot+1)
        if range_has_point(range, x, y)
            return pivot
        range.setStart(node, rr[0])
        range.setEnd(node, rr[1])
        if range_has_point(range, x, y)
            limits = rr
            continue
        range.setStart(node, lr[0])
        range.setEnd(node, lr[1])
        if range_has_point(range, x, y)
            limits = lr
            continue
        break
    return limits[0]

find_offset_for_point = (x, y, node, cdoc) ->
    range = cdoc.createRange()
    child = node.firstChild
    while child
        if child.nodeType in [3, 4, 5, 6] and child.nodeValue?.length
            range.setStart(child, 0)
            range.setEnd(child, child.nodeValue.length)
            if range_has_point(range, x, y)
                return [child, offset_in_text_node(child, range, x, y)]
        child = child.nextSibling

    # The point must be after the last bit of text/in the padding/border, we dont know
    # how to get a good point in this case
    throw "Point (#{x}, #{y}) is in the padding/border of #{node}, so cannot calculate offset"

# }}}

class CanonicalFragmentIdentifier

    ###
    This class is a namespace to expose CFI functions via the window.cfi
    object. The most important functions are:

    is_compatible(): Throws an error if the browser is not compatible with
                     this script

    at(x, y): Maps a point to a CFI, if possible
    at_current(): Returns the CFI corresponding to the current viewport scroll location

    scroll_to(cfi): which scrolls the browser to a point corresponding to the
                    given cfi, and returns the x and y co-ordinates of the point.
    ###

    constructor: () -> # {{{
        if not this instanceof arguments.callee
            throw new Error('CFI constructor called as function')
        this.CREATE_RANGE_ERR = "Your browser does not support the createRange function. Update it to a newer version."
        this.IE_ERR = "Your browser is too old. You need Internet Explorer version 9 or newer."
        div = document.createElement('div')
        ver = 3
        while true
            div.innerHTML = "<!--[if gt IE #{ ++ver }]><i></i><![endif]-->"
            if div.getElementsByTagName('i').length == 0
                break
        this.iever = ver
        this.isie = ver > 4

    # }}}

    is_compatible: () -> # {{{
        if not window.document.createRange
            throw this.CREATE_RANGE_ERR
        # Check if Internet Explorer >= 8 as getClientRects returns physical
        # rather than logical pixels on older IE
        if this.isie and this.iever < 9
            # We have IE < 9
            throw this.IE_ERR
    # }}}

    set_current_time: (target, val) -> # {{{
        if target.currentTime == undefined
            return
        if target.readyState == 4 or target.readyState == "complete"
            target.currentTime = val + 0
        else
            fn = ()-> target.currentTime = val
            target.addEventListener("canplay", fn, false)
    #}}}

    encode: (doc, node, offset, tail) -> # {{{
        cfi = tail or ""

        # Handle the offset, if any
        switch node.nodeType
            when 1 # Element node
                if typeof(offset) == 'number'
                    node = node.childNodes.item(offset)
            when 3, 4, 5, 6 # Text/entity/CDATA node
                offset or= 0
                while true
                    p = node.previousSibling
                    if not p or p.nodeType > 8
                        break
                    # log("previous sibling:"+ p + " " + p?.nodeType + " length: " + p?.nodeValue?.length)
                    if p.nodeType not in [2, 8] and p.nodeValue?.length?
                        offset += p.nodeValue.length
                    node = p
                cfi = ":" + offset + cfi
            else # Not handled
                log("Offsets for nodes of type #{ node.nodeType } are not handled")

        # Construct the path to node from root
        until node == doc
            p = node.parentNode
            if not p
                if node.nodeType == 9 # Document node (iframe)
                    win = node.defaultView
                    if win.frameElement
                        node = win.frameElement
                        cfi = "!" + cfi
                        continue
                break
            # Find position of node in parent
            index = 0
            child = p.firstChild
            while true
                index |= 1 # Increment index by 1 if it is even
                if child.nodeType == 1
                    index++
                if child == node
                    break
                child = child.nextSibling

            # Add id assertions for robustness where possible
            id = node.getAttribute?('id')
            idspec = if id then "[#{ escape_for_cfi(id) }]" else ''
            cfi = '/' + index + idspec + cfi
            node = p

        cfi
    # }}}

    decode: (cfi, doc=window?.document) -> # {{{
        simple_node_regex = ///
            ^/(\d+)          # The node count
              (\[[^\]]*\])?  # The optional id assertion
        ///
        error = null
        node = doc

        until cfi.length < 1 or error
            if (r = cfi.match(simple_node_regex)) # Path step
                target = parseInt(r[1])
                assertion = r[2]
                if assertion
                    assertion = unescape_from_cfi(assertion.slice(1, assertion.length-1))
                index = 0
                child = node.firstChild

                while true
                    if not child
                        if assertion # Try to use the assertion to find the node
                            child = doc.getElementById(assertion)
                            if child
                                node = child
                        if not child
                            error = "No matching child found for CFI: " + cfi
                        break
                    index |= 1 # Increment index by 1 if it is even
                    if child.nodeType == 1
                        index++
                    if index == target
                        cfi = cfi.substr(r[0].length)
                        node = child
                        if assertion and node.id != assertion
                            # The found child does not match the id assertion,
                            # trust the id assertion if an element with that id
                            # exists
                            child = doc.getElementById(assertion)
                            if child
                                node = child
                        break
                    child = child.nextSibling

            else if cfi[0] == '!' # Indirection
                if node.contentDocument
                    node = node.contentDocument
                    cfi = cfi.substr(1)
                else
                    error = "Cannot reference #{ node.nodeName }'s content:" + cfi

            else
                break

        if error
            log(error)
            return null

        point = {}
        error = null
        offset = null

        if (r = cfi.match(/^:(\d+)/)) != null
            # Character offset
            offset = parseInt(r[1])
            cfi = cfi.substr(r[0].length)

        if (r = cfi.match(/^~(-?\d+(\.\d+)?)/)) != null
            # Temporal offset
            point.time = r[1] - 0 # Coerce to number
            cfi = cfi.substr(r[0].length)

        if (r = cfi.match(/^@(-?\d+(\.\d+)?):(-?\d+(\.\d+)?)/)) != null
            # Spatial offset
            point.x = r[1] - 0 # Coerce to number
            point.y = r[3] - 0 # Coerce to number
            cfi = cfi.substr(r[0].length)

        if( (r = cfi.match(/^\[([^\]]+)\]/)) != null )
            assertion = r[1]
            cfi = cfi.substr(r[0].length)
            if (r = assertion.match(/;s=([ab])$/)) != null
                if r.index > 0 and assertion[r.index - 1] != '^'
                    assertion = assertion.substr(0, r.index)
                    point.forward = (r[1] == 'a')
                assertion = unescape_from_cfi(assertion)
                # TODO: Handle text assertion

        # Find the text node that contains the offset
        node?.parentNode?.normalize()
        if offset != null
            while true
                len = node.nodeValue.length
                if offset < len or (not point.forward and offset == len)
                    break
                next = false
                while true
                    nn = node.nextSibling
                    if not nn
                        break
                    if nn.nodeType in [3, 4, 5, 6] and nn.nodeValue?.length # Text node, entity, cdata
                        next = nn
                        break
                    node = nn
                if not next
                    if offset > len
                        error = "Offset out of range: #{ offset }"
                        offset = len
                    break
                node = next
                offset -= len
            point.offset = offset

        point.node = node
        if error
            point.error = error
        else if cfi.length > 0
            point.error = "Undecoded CFI: #{ cfi }"

        log(point.error)

        point

    # }}}

    at: (x, y, doc=window?.document) -> # {{{
        # x, y are in viewport co-ordinates
        cdoc = doc
        target = null
        cwin = cdoc.defaultView
        tail = ''
        offset = null
        name = null

        # Drill down into iframes, etc.
        while true
            target = cdoc.elementFromPoint x, y
            if not target or target.localName in ['html', 'body']
                # log("No element at (#{ x }, #{ y })")
                return null

            name = target.localName
            if name not in ['iframe', 'embed', 'object']
                break

            cd = target.contentDocument
            if not cd
                break

            # We have an embedded document, transforms x, y into the co-prd
            # system of the embedded document's viewport
            rect = target.getBoundingClientRect()
            x -= rect.left
            y -= rect.top
            cdoc = cd
            cwin = cdoc.defaultView

        (if target.parentNode then target.parentNode else target).normalize()

        if name in ['audio', 'video']
            tail = "~" + get_current_time(target)

        if name in ['img', 'video']
            rect = target.getBoundingClientRect()
            px = ((x - rect.left)*100)/target.offsetWidth
            py = ((y - rect.top)*100)/target.offsetHeight
            tail = "#{ tail }@#{ fstr px }:#{ fstr py }"
        else if name != 'audio'
            # Get the text offset
            # We use a custom function instead of caretRangeFromPoint as
            # caretRangeFromPoint does weird things when the point falls in the
            # padding of the element
            if cdoc.createRange
                [target, offset] = find_offset_for_point(x, y, target, cdoc)
            else
                throw this.CREATE_RANGE_ERR

        this.encode(doc, target, offset, tail)
    # }}}

    point: (cfi, doc=window?.document) -> # {{{
        r = this.decode(cfi, doc)
        if not r
            return null
        node = r.node
        ndoc = node.ownerDocument
        if not ndoc
            log("CFI node has no owner document: #{ cfi } #{ node }")
            return null

        nwin = ndoc.defaultView
        x = null
        y = null
        range = null

        if typeof(r.offset) == "number"
            # Character offset
            if not ndoc.createRange
                throw this.CREATE_RANGE_ERR
            range = ndoc.createRange()
            if r.forward
                try_list = [{start:0, end:0, a:0.5}, {start:0, end:1, a:1}, {start:-1, end:0, a:0}]
            else
                try_list = [{start:0, end:0, a:0.5}, {start:-1, end:0, a:0}, {start:0, end:1, a:1}]
            a = null
            rects = null
            node_len = node.nodeValue.length
            offset = r.offset
            for i in [0, 1]
                # Try reducing the offset by 1 if we get no match as if it refers to the position after the
                # last character we wont get a match with getClientRects
                offset = r.offset - i
                if offset < 0
                    offset = 0
                k = 0
                until rects?.length or k >= try_list.length
                    t = try_list[k++]
                    start_offset = offset + t.start
                    end_offset = offset + t.end
                    a = t.a
                    if start_offset < 0 or end_offset >= node_len
                        continue
                    range.setStart(node, start_offset)
                    range.setEnd(node, end_offset)
                    rects = range.getClientRects()
                if rects?.length
                    break


            if not rects?.length
                log("Could not find caret position: rects: #{ rects } offset: #{ r.offset }")
                return null

        else
            [x, y] = [r.x, r.y]

        {x:x, y:y, node:r.node, time:r.time, range:range, a:a}

    # }}}

    scroll_to: (cfi, callback=false, doc=window?.document) -> # {{{
        point = this.point(cfi, doc)
        if not point
            log("No point found for cfi: #{ cfi }")
            return
        if typeof point.time == 'number'
            this.set_current_time(point.node, point.time)

        if point.range != null
            # Character offset
            r = point.range
            [so, eo, sc, ec] = [r.startOffset, r.endOffset, r.startContainer, r.endContainer]
            node = r.startContainer
            ndoc = node.ownerDocument
            nwin = ndoc.defaultView
            span = ndoc.createElement('span')
            span.setAttribute('style', 'border-width: 0; padding: 0; margin: 0')
            r.surroundContents(span)
            span.scrollIntoView()
            fn = ->
                # Remove the span and get the new position now that scrolling
                # has (hopefully) completed
                #
                # In WebKit, the boundingrect of the span is wrong in some
                # situations, whereas in IE resetting the range causes it to
                # loose bounding info. So we use the range's rects unless they
                # are absent, in which case we use the span's rect
                #
                rect = span.getBoundingClientRect()

                # Remove the span we inserted
                p = span.parentNode
                for node in span.childNodes
                    span.removeChild(node)
                    p.insertBefore(node, span)
                p.removeChild(span)
                p.normalize()

                # Reset the range to what it was before the span was added
                r.setStart(sc, so)
                r.setEnd(ec, eo)
                rects = r.getClientRects()
                if rects.length > 0
                    rect = rects[0]

                x = (point.a*rect.left + (1-point.a)*rect.right)
                y = (rect.top + rect.bottom)/2
                [x, y] = viewport_to_document(x, y, ndoc)
                if callback
                    callback(x, y)
        else
            node = point.node
            nwin = node.ownerDocument.defaultView
            node.scrollIntoView()

            fn = ->
                r = node.getBoundingClientRect()
                [x, y] = viewport_to_document(r.left, r.top, node.ownerDocument)
                if typeof(point.x) == 'number' and node.offsetWidth
                    x += (point.x*node.offsetWidth)/100
                if typeof(point.y) == 'number' and node.offsetHeight
                    y += (point.y*node.offsetHeight)/100
                scrollTo(x, y)
                if callback
                    callback(x, y)

        setTimeout(fn, 10)

        null
    # }}}

    at_current: () -> # {{{
        [winx, winy] = window_scroll_pos()
        [winw, winh] = [window.innerWidth, window.innerHeight]
        max = Math.max
        winw = max(winw, 400)
        winh = max(winh, 600)
        deltay = Math.floor(winh/50)
        deltax = Math.floor(winw/25)
        miny = max(-winy, -winh)
        maxy = winh
        minx = max(-winx, -winw)
        maxx = winw

        dist = (p1, p2) ->
            Math.sqrt(Math.pow(p1[0]-p2[0], 2), Math.pow(p1[1]-p2[1], 2))

        get_cfi = (ox, oy) ->
            try
                cfi = window.cfi.at(ox, oy)
                point = window.cfi.point(cfi)
            catch err
                cfi = null

            if cfi
                if point.range != null
                    r = point.range
                    rect = r.getClientRects()[0]

                    x = (point.a*rect.left + (1-point.a)*rect.right)
                    y = (rect.top + rect.bottom)/2
                    [x, y] = viewport_to_document(x, y, r.startContainer.ownerDocument)
                else
                    node = point.node
                    r = node.getBoundingClientRect()
                    [x, y] = viewport_to_document(r.left, r.top, node.ownerDocument)
                    if typeof(point.x) == 'number' and node.offsetWidth
                        x += (point.x*node.offsetWidth)/100
                    if typeof(point.y) == 'number' and node.offsetHeight
                        y += (point.y*node.offsetHeight)/100

                if dist(viewport_to_document(ox, oy), [x, y]) > 50
                    cfi = null

            return cfi

        x_loop = (cury) ->
            for direction in [-1, 1]
                delta = deltax * direction
                curx = 0
                until (direction < 0 and curx < minx) or (direction > 0 and curx > maxx)
                    cfi = get_cfi(curx, cury)
                    if cfi
                        return cfi
                    curx += delta
            null

        for direction in [-1, 1]
            delta = deltay * direction
            cury = 0
            until (direction < 0 and cury < miny) or (direction > 0 and cury > maxy)
                cfi = x_loop(cury, -1)
                if cfi
                    return cfi
                cury += delta

        # Use a spatial offset on the html element, since we could not find a
        # normal CFI
        [x, y] = window_scroll_pos()
        de = document.documentElement
        rect = de.getBoundingClientRect()
        px = (x*100)/rect.width
        py = (y*100)/rect.height
        cfi = "/2@#{ fstr px }:#{ fstr py }"

        return cfi

    # }}}

if window?
    window.cfi = new CanonicalFragmentIdentifier()
else if process?
    # Some debugging code goes here to be run with the coffee interpreter
    cfi = new CanonicalFragmentIdentifier()
    t = 'a^!,1'
    log(t)
    log(escape_for_cfi(t))
    log(unescape_from_cfi(escape_for_cfi(t)))
