#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2011, Kovid Goyal <kovid@kovidgoyal.net>
 Released under the GPLv3 License
 Based on code originally written by Peter Sorotkin (epubcfi.js)
###
#
log = (error) ->
    if error
        if window?.console?.log
            window.console.log(error)
        else if process?.stdout?.write
            process.stdout.write(error + '\n')

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

class CanonicalFragmentIdentifier

    # This class is a namespace to expose CFI functions via the window.cfi
    # object

    constructor: () ->

    encode: (doc, node, offset, tail) -> # {{{
        cfi = tail or ""

        # Handle the offset, if any
        switch node.nodeType
            when 1 # Element node
                if typeoff(offset) == 'number'
                    node = node.childNodes.item(offset)
            when 3, 4, 5, 6 # Text/entity/CDATA node
                offset or= 0
                while true
                    p = node.previousSibling
                    if (p?.nodeType not in [3, 4, 5, 6])
                        break
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
            # Increase index by the length of all previous sibling text nodes
            index = 0
            child = p.firstChild
            while true
                index |= 1
                if child.nodeType in [1, 7]
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

        until cfi.length <= 0 or error
            if ( (r = cfi.match(simple_node_regex)) is not null ) # Path step
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
                    if child.nodeType in [1, 7] # We have an element or a PI
                        index++
                    if ( index == target )
                        cfi = cfi.substr(r[0].length)
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

        if (r = cfi.match(/^@(-?\d+(\.\d+)?),(-?\d+(\.\d+)?)/)) != null
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
                    if nn.nodeType in [3, 4, 5, 6] # Text node, entity, cdata
                        next = nn
                        break
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
        cdoc = doc
        target = null
        cwin = cdoc.defaultView
        tail = ''
        offset = null
        name = null

        # Drill down into iframes, etc.
        while true
            target = cdoc.elementFromPoint x, y
            if not target or target.localName == 'html'
                log("No element at (#{ x }, #{ y })")
                return null

            name = target.localName
            if name not in ['iframe', 'embed', 'object']
                break

            cd = target.contentDocument
            if not cd
                break

            x = x + cwin.pageXOffset - target.offsetLeft
            y = y + cwin.pageYOffset - target.offsetTop
            cdoc = cd
            cwin = cdoc.defaultView

        (if target.parentNode then target.parentNode else target).normalize()

        if name in ['audio', 'video']
            tail = "~" + fstr target.currentTime

        if name in ['img', 'video']
            px = ((x + cwin.scrollX - target.offsetLeft)*100)/target.offsetWidth
            py = ((y + cwin.scrollY - target.offsetTop)*100)/target.offsetHeight
            tail = "#{ tail }@#{ fstr px },#{ fstr py }"
        else if name != 'audio'
            if cdoc.caretRangeFromPoint # WebKit
                range = cdoc.caretRangeFromPoint(x, y)
                if range
                    target = range.startContainer
                    offset = range.startOffset
            else
                # TODO: implement a span bisection algorithm for UAs
                # without caretRangeFromPoint (Gecko, IE)

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

        if typeof(r.offset) == "number"
            # Character offset
            range = ndoc.createRange()
            if r.forward
                try_list = [{start:0, end:0, a:0.5}, {start:0, end:1, a:1}, {start:-1, end:0, a:0}]
            else
                try_list = [{start:0, end:0, a:0.5}, {start:-1, end:0, a:0}, {start:0, end:1, a:1}]
            k = 0
            a = null
            rects = null
            node_len = node.nodeValue.length
            until rects or rects.length or k >= try_list.length
                t = try_list[k++]
                start_offset = r.offset + t.start
                end_offset = r.offset + t.end
                a = t.a
                if start_offset < 0 or end_offset >= node_len
                    continue
                range.setStart(node, start_offset)
                range.setEnd(node, end_offset)
                rects = range.getClientRects()

            if not rects or not rects.length
                log("Could not find caret position: rects: #{ rects } offset: #{ r.offset }")
                return null

            rect = rects[0]
            x = (a*rect.left + (1-a)*rect.right)
            y = (rect.top + rect.bottom)/2
        else
            x = node.offsetLeft - nwin.scrollX
            y = node.offsetTop - nwin.scrollY
            if typeof(r.x) == "number" and node.offsetWidth
                x += (r.x*node.offsetWidth)/100
                y += (r.y*node.offsetHeight)/100

        until ndoc == doc
            node = nwin.frameElement
            ndoc = node.ownerDocument
            nwin = ndoc.defaultView
            x += node.offsetLeft - nwin.scrollX
            y += node.offsetTop - nwin.scrollY

        {x:x, y:y, node:r.node, time:r.time}

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
