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
    if evt.button == 2
        return # Right mouse click, generated only in firefox
    reset = document.getElementById('reset')
    if document.elementFromPoint(evt.clientX, evt.clientY) == reset
        return
    ms = document.getElementById("marker")
    if ms
        ms.parentNode?.removeChild(ms)

    fn = () ->
        try
            window.current_cfi = window.cfi.at(evt.clientX, evt.clientY)
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

window.onload = ->
    try
        window.cfi.is_compatible()
    catch error
        alert(error)
        return
    document.onclick = mark_and_reload
    for iframe in document.getElementsByTagName("iframe")
        iframe.contentWindow.document.onclick = mark_and_reload

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

