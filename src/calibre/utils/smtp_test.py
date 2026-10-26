#!/usr/bin/env python
# License: GPLv3

import unittest
from base64 import b64encode
from smtplib import SMTPAuthenticationError
from unittest.mock import Mock

from polyglot.smtplib import SMTP, SMTP_SSL


class TestSMTPAuthLogging(unittest.TestCase):
    def test_login_redacts_challenge_responses(self):
        username, password = 'example-user', 'synthetic-password-for-test'
        encoded_username = b64encode(username.encode())
        encoded_password = b64encode(password.encode())

        for cls in (SMTP, SMTP_SSL):
            for succeeds in (True, False):
                with self.subTest(cls=cls.__name__, succeeds=succeeds):
                    log = []
                    smtp = cls(debug_to=lambda *args: log.append(args))
                    smtp.set_debuglevel(1)
                    smtp.sock = Mock()
                    smtp.esmtp_features = {'auth': 'LOGIN'}
                    smtp.ehlo_or_helo_if_needed = Mock()
                    smtp.getreply = Mock(side_effect=[
                        (334, b64encode(b'Password:')),
                        (235 if succeeds else 535, b'ok' if succeeds else b'bad credentials'),
                    ])

                    if succeeds:
                        self.assertEqual(smtp.login(username, password)[0], 235)
                    else:
                        with self.assertRaises(SMTPAuthenticationError):
                            smtp.login(username, password)

                    sent = b''.join(call.args[0] for call in smtp.sock.sendall.call_args_list)
                    self.assertIn(encoded_username, sent)
                    self.assertIn(encoded_password, sent)
                    logged = repr(log)
                    self.assertNotIn(username, logged)
                    self.assertNotIn(password, logged)
                    self.assertNotIn(encoded_username.decode(), logged)
                    self.assertNotIn(encoded_password.decode(), logged)
                    self.assertIn('<censored>', logged)

                    # Logging must resume after either success or failure.
                    smtp.send('NOOP\r\n')
                    self.assertIn('NOOP', repr(log))


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestSMTPAuthLogging)
