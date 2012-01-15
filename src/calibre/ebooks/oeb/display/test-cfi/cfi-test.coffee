#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2011, Kovid Goyal <kovid@kovidgoyal.net>
 Released under the GPLv3 License
###

log = (error) ->
    if error
        if window?.console?.log
            window.console.log(error)
        else if process?.stdout?.write
            process.stdout.write(error + '\n')

show_cfi = () ->
    if window.current_cfi
        fn = (x, y) ->
            ms = document.getElementById("marker").style
            ms.display = 'block'
            ms.top = y - 30 + 'px'
            ms.left = x - 1 + 'px'

        window.cfi.scroll_to(window.current_cfi, fn)
    null

window_ypos = (pos=null) ->
    if pos == null
        return window.pageYOffset
    window.scrollTo(0, pos)

mark_and_reload = (evt) ->
    # Remove image in case the click was on the image itself, we want the cfi to
    # be on the underlying element
    x = evt.clientX
    y = evt.clientY
    if evt.button == 2
        return # Right mouse click, generated only in firefox
    reset = document.getElementById('reset')
    if document.elementFromPoint(x, y) == reset
        return
    ms = document.getElementById("marker")
    if ms
        ms.parentNode?.removeChild(ms)

    fn = () ->
        try
            window.current_cfi = window.cfi.at(x, y)
        catch err
            alert("Failed to calculate cfi: #{ err }")
            return
        if window.current_cfi
            epubcfi = "epubcfi(#{ window.current_cfi })"
            ypos = window_ypos()
            newloc = window.location.href.replace(/#.*$/, '') + "#" + ypos + epubcfi
            window.location.replace(newloc)
            window.location.reload()

    setTimeout(fn, 1)
    null

window_scroll_pos = (win) ->
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

frame_clicked = (evt) ->
    iframe = evt.target.ownerDocument.defaultView.frameElement
    # We know that the offset parent of the iframe is body
    # So we can easily calculate the event co-ords w.r.t. the browser window
    [winx, winy] = window_scroll_pos(window)
    x = evt.clientX + iframe.offsetLeft - winx
    y = evt.clientY + iframe.offsetTop  - winy
    mark_and_reload({'clientX':x, 'clientY':y, 'button':evt.button})

window.onload = ->
    try
        window.cfi.is_compatible()
    catch error
        alert(error)
        return
    document.onclick = mark_and_reload
    for iframe in document.getElementsByTagName("iframe")
        iframe.contentWindow.document.onclick = frame_clicked

    r = location.hash.match(/#(\d*)epubcfi\((.+)\)$/)
    if r
        window.current_cfi = r[2]
        ypos = if r[1] then 0+r[1] else 0
        base = document.getElementById('first-h1').innerHTML
        document.title = base + ": " + window.current_cfi
        fn = () ->
            show_cfi()
            window_ypos(ypos)
        setTimeout(fn, 100)
    null

