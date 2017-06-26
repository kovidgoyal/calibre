#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import sys
from functools import partial

from calibre import prints
from calibre.constants import preferred_encoding

# Manage users CLI {{{


def manage_users_cli(path=None):
    from calibre.srv.users import UserManager
    m = UserManager(path)
    enc = getattr(sys.stdin, 'encoding', preferred_encoding) or preferred_encoding

    def get_input(prompt):
        prints(prompt, end=' ')
        return raw_input().decode(enc)

    def choice(
        question=_('What do you want to do?'), choices=(), default=None, banner=''):
        prints(banner)
        for i, choice in enumerate(choices):
            prints('%d)' % (i + 1), choice)
        print()
        while True:
            prompt = question + ' [1-%d]:' % len(choices)
            if default is not None:
                prompt = question + ' [1-%d %s: %d]' % (
                    len(choices), _('default'), default + 1)
            reply = get_input(prompt)
            if not reply and default is not None:
                reply = str(default + 1)
            if not reply:
                prints(_('No choice selected, exiting...'))
                raise SystemExit(0)
            reply = reply.strip()
            try:
                num = int(reply) - 1
                if not (0 <= num < len(choices)):
                    raise Exception('bad num')
                return num
            except Exception:
                prints(_('%s is not a valid choice, try again') % reply)

    def get_valid(prompt, invalidq=lambda x: None):
        while True:
            ans = get_input(prompt + ':').strip()
            fail_message = invalidq(ans)
            if fail_message is None:
                return ans
            prints(fail_message)

    def get_valid_user():
        prints(_('Existing user names:'))
        users = sorted(m.all_user_names)
        if not users:
            raise SystemExit(_('There are no users, you must first add an user'))
        prints(', '.join(users))

        def validate(username):
            if not m.has_user(username):
                return _('The username %s does not exist') % username

        return get_valid(_('Enter the username'), validate)

    def get_pass(username):
        while True:
            from getpass import getpass
            one = getpass(
                _('Enter the new password for %s: ') % username).decode(enc)
            if not one:
                prints(_('Empty passwords are not allowed'))
                continue
            two = getpass(
                _('Re-enter the new password for %s, to verify: ') % username
            ).decode(enc)
            if one != two:
                prints(_('Passwords do not match'))
                continue
            msg = m.validate_password(one)
            if msg is None:
                return one
            prints(msg)

    def add_user():
        username = get_valid(_('Enter the username'), m.validate_username)
        pw = get_pass(username)
        m.add_user(username, pw)
        prints(_('User %s added successfully!') % username)

    def remove_user():
        un = get_valid_user()
        if get_input((_('Are you sure you want to remove the user %s?') % un) +
                     ' [y/n]:') != 'y':
            raise SystemExit(0)
        m.remove_user(un)
        prints(_('User %s successfully removed!') % un)

    def change_password(username):
        pw = get_pass(username)
        m.change_password(username, pw)
        prints(_('Password for %s successfully changed!') % username)

    def show_password(username):
        pw = m.get(username)
        prints(_('Current password for {0} is: {1}').format(username, pw))

    def change_readonly(username):
        readonly = m.is_readonly(username)
        if readonly:
            q = _('Allow {} to make changes (i.e. grant write access)?')
        else:
            q = _('Prevent {} from making changes (i.e. remove write access)?')
        if get_input(q.format(username) + ' [y/n]:').lower() == 'y':
            m.set_readonly(username, not readonly)

    def change_restriction(username):
        r = m.restrictions(username)
        if r is None:
            raise SystemExit('The user {} does not exist'.format(username))
        if r['allowed_library_names']:
            prints(
                _('{} is currently only allowed to access the libraries named: {}')
                .format(username, ', '.join(r['allowed_library_names'])))
        if r['blocked_library_names']:
            prints(
                _('{} is currently not allowed to access the libraries named: {}')
                .format(username, ', '.join(r['blocked_library_names'])))
        if r['library_restrictions']:
            prints(
                _('{} has the following additional per-library restrictions:')
                .format(username))
            for k, v in r['library_restrictions'].iteritems():
                prints(k + ':', v)
        else:
            prints(_('{} has the no additional per-library restrictions'))
        c = choice(
            choices=[
                _('Allow access to all libraries'),
                _('Allow access to only specified libraries'),
                _('Allow access to all, except specified libraries'),
                _('Change per-library restrictions'),
                _('Cancel')])
        if c == 0:
            m.update_user_restrictions(username, {})
        elif c == 3:
            while True:
                library = get_input(_('Enter the name of the library:'))
                if not library:
                    break
                prints(
                    _(
                        'Enter a search expression, access will be granted only to books matching this expression.'
                        ' An empty expression will grant access to all books.'))
                plr = get_input(_('Search expression:'))
                if plr:
                    r['library_restrictions'][library] = plr
                else:
                    r['library_restrictions'].pop(library, None)
                m.update_user_restrictions(username, r)
                if get_input(_('Another restriction?') + ' (y/n):') != 'y':
                    break
        elif c == 4:
            pass
        else:
            names = get_input(_('Enter a comma separated list of library names:'))
            names = filter(None, [x.strip() for x in names.split(',')])
            w = 'allowed_library_names' if c == 1 else 'blocked_library_names'
            t = _('Allowing access only to libraries: {}') if c == 1 else _(
                'Allowing access to all libraries, except: {}')
            prints(t.format(', '.join(names)))
            m.update_user_restrictions(username, {w: names})

    def edit_user(username=None):
        username = username or get_valid_user()
        c = choice(
            choices=[
                _('Show password for {}').format(username),
                _('Change password for {}').format(username),
                _('Change read/write permission for {}').format(username),
                _('Change the libraries {} is allowed to access').format(username),
                _('Cancel'), ],
            banner='\n' + _('{} has {} access').format(
                username,
                _('readonly') if m.is_readonly(username) else _('read-write')))
        print()
        if c > 3:
            actions.append(toplevel)
            return
        {
            0: show_password,
            1: change_password,
            2: change_readonly,
            3: change_restriction}[c](username)
        actions.append(partial(edit_user, username=username))

    def toplevel():
        {
            0: add_user,
            1: edit_user,
            2: remove_user,
            3: lambda: None}[choice(
                choices=[
                    _('Add a new user'),
                    _('Edit an existing user'),
                    _('Remove a user'),
                    _('Cancel')])]()

    actions = [toplevel]
    while actions:
        actions[0]()
        del actions[0]


# }}}
