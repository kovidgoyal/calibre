" Project wide builtins
let $PYFLAKES_BUILTINS = "_,dynamic_property,__,P,I,lopen,icu_lower,icu_upper,icu_title,ngettext"

fun! CalibreLog()
    " Setup buffers to edit the calibre changelog and version info prior to
    " making a release.
    enew
    read ! bzr log -l 500
    set nomodifiable noswapfile buftype=nofile
    edit Changelog.yaml
    edit src/calibre/constants.py
endfun

nnoremap \log :call CalibreLog()<CR>
