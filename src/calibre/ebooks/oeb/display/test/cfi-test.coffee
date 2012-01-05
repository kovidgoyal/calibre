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

viewport_top = (node) ->
    $(node).offset().top - window.pageYOffset

viewport_left = (node) ->
    $(node).offset().left - window.pageXOffset

show_cfi = (dont_seek) ->
    if window.current_cfi
        fn = (x, y) ->
            ms = $("#marker")
            ms.css('visibility', 'visible')
            # This strange sequence is needed to get it to work in Chrome
            # when called from the onload handler
            ms.offset({left:x-1, top:y-30})
            ms.offset()
            ms.offset({left:x-1, top:y-30})


        window.cfi.scroll_to(window.current_cfi, fn)
    null


mark_and_reload = (evt) ->
    window.current_cfi = window.cfi.at(evt.clientX, evt.clientY)
    if window.current_cfi
        fn = () ->
            epubcfi = "#epubcfi(#{ window.current_cfi })"
            newloc = window.location.href.replace(/#.*$/, '') + epubcfi
            window.location.replace(newloc)
            document.getElementById('current-cfi').innerHTML = window.current_cfi
            window.location.reload()

        setTimeout(fn, 1)
    null

window.onload = ->
    window.onscroll = show_cfi
    window.onresize = show_cfi
    document.onclick = mark_and_reload
    for iframe in document.getElementsByTagName("iframe")
        iframe.contentWindow.onscroll = show_cfi
    r = location.hash.match(/#epubcfi\((.+)\)$/)
    if r
        window.current_cfi = r[1]
        document.getElementById('current-cfi').innerHTML = window.current_cfi
        setTimeout(show_cfi, 100)
    null

