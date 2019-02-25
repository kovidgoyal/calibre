/*
 * cocoa.m
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */


#include <Cocoa/Cocoa.h>


double
cocoa_cursor_blink_time(void) {
    NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];
    double on_period_ms = [defaults doubleForKey:@"NSTextInsertionPointBlinkPeriodOn"];
    double off_period_ms = [defaults doubleForKey:@"NSTextInsertionPointBlinkPeriodOff"];
    double period_ms = [defaults doubleForKey:@"NSTextInsertionPointBlinkPeriod"];
    double max_value = 60 * 1000.0, ans = -1.0;
    if (on_period_ms || off_period_ms) {
        ans = on_period_ms + off_period_ms;
    } else if (period_ms) {
        ans = period_ms;
    }
    return ans > max_value ? 0.0 : ans;
}
