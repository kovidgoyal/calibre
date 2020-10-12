/*
 * cocoa.m
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#import <AppKit/AppKit.h>
#import <AppKit/NSWindow.h>
#import <Availability.h>

#include <string.h>

void
disable_window_tabbing(void) {
	if ([NSWindow respondsToSelector:@selector(allowsAutomaticWindowTabbing)])
        NSWindow.allowsAutomaticWindowTabbing = NO;
}

void
remove_cocoa_menu_items(void) {
	// Remove (disable) the "Start Dictation..." and "Emoji & Symbols" menu
	// items from the "Edit" menu
	[[NSUserDefaults standardUserDefaults] setBool:YES forKey:@"NSDisabledDictationMenuItem"];
	[[NSUserDefaults standardUserDefaults] setBool:YES forKey:@"NSDisabledCharacterPaletteMenuItem"];

	// Remove (don't have) the "Enter Full Screen" menu item from the "View" menu
	[[NSUserDefaults standardUserDefaults] setBool:NO forKey:@"NSFullScreenMenuItemEverywhere"];
}

void
activate_cocoa_multithreading(void) {
	if (![NSThread isMultiThreaded]) [[NSThread new] start];
}

const char*
cocoa_send2trash(const char *utf8_path) {
	@autoreleasepool {
	const char *ret = NULL;
	NSError* ns_error = nil;
	if (![[NSFileManager defaultManager] trashItemAtURL:[NSURL fileURLWithPath:@(utf8_path)] resultingItemURL:nil error:&ns_error]) {
		ret = strdup([[ns_error localizedDescription] UTF8String]);
	}
	return ret;
	}
}


extern void macos_notification_callback(const char*);

@interface NotificationDelegate : NSObject <NSUserNotificationCenterDelegate>
@end


void
cocoa_send_notification(const char *identifier, const char *title, const char *subtitle, const char *informativeText, const char* path_to_image) {
	@autoreleasepool {
    NSUserNotificationCenter *center = [NSUserNotificationCenter defaultUserNotificationCenter];
    if (!center) {return;}
    if (!center.delegate) center.delegate = [[NotificationDelegate alloc] init];
    NSUserNotification *n = [NSUserNotification new];
    NSImage *img = nil;
    if (path_to_image) {
		img = [[NSImage alloc] initWithContentsOfURL:[NSURL fileURLWithPath:@(path_to_image)]];
        if (img) {
            [n setValue:img forKey:@"_identityImage"];
            [n setValue:@(false) forKey:@"_identityImageHasBorder"];
        }
		[img release];
    }
#define SET(x) { \
    if (x) { \
        n.x = @(x); \
    }}
    SET(title); SET(subtitle); SET(informativeText);
#undef SET
    if (identifier) {
        n.userInfo = @{@"user_id": @(identifier)};
    }
    [center deliverNotification:n];
	}
}

@implementation NotificationDelegate
    - (void)userNotificationCenter:(NSUserNotificationCenter *)center
            didDeliverNotification:(NSUserNotification *)notification {
        (void)(center); (void)(notification);
    }

    - (BOOL) userNotificationCenter:(NSUserNotificationCenter *)center
            shouldPresentNotification:(NSUserNotification *)notification {
        (void)(center); (void)(notification);
        return YES;
    }

    - (void) userNotificationCenter:(NSUserNotificationCenter *)center
            didActivateNotification:(NSUserNotification *)notification {
        (void)(center);
			macos_notification_callback(notification.userInfo[@"user_id"] ? [notification.userInfo[@"user_id"] UTF8String] : NULL);
    }
@end


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

int
cocoa_transient_scroller(void) {
    return [NSScroller preferredScrollerStyle] == NSScrollerStyleOverlay;
}
