#!/usr/bin/env python
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


from calibre.constants import ismacos, iswindows

if iswindows:
    from calibre_extensions.winutil import (
        ES_CONTINUOUS, ES_DISPLAY_REQUIRED, ES_SYSTEM_REQUIRED,
        set_thread_execution_state
    )

    def prevent_sleep(reason=''):
        set_thread_execution_state(ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED)
        return 1

    def allow_sleep(cookie):
        set_thread_execution_state(ES_CONTINUOUS)
elif ismacos:
    from calibre_extensions.cocoa import (
        create_io_pm_assertion, kIOPMAssertionTypeNoDisplaySleep,
        release_io_pm_assertion
    )

    def prevent_sleep(reason=''):
        return create_io_pm_assertion(kIOPMAssertionTypeNoDisplaySleep, reason or 'E-book viewer automated reading in progress')

    def allow_sleep(cookie):
        release_io_pm_assertion(cookie)

else:
    def prevent_sleep(reason=''):
        return 0

    def allow_sleep(cookie):
        pass
