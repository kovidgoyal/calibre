from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'
'''
This module implements a simple commandline SMTP client that supports:

  * Delivery via an SMTP relay with SSL or TLS
  * Background delivery with failures being saved in a maildir mailbox
'''

import sys, traceback, os
from email import encoders
from calibre import isbytestring

def create_mail(from_, to, subject, text=None, attachment_data=None,
                 attachment_type=None, attachment_name=None):
    assert text or attachment_data

    from email.mime.multipart import MIMEMultipart

    outer = MIMEMultipart()
    outer['Subject'] = subject
    outer['To'] = to
    outer['From'] = from_
    outer.preamble = 'You will not see this in a MIME-aware mail reader.\n'

    if text is not None:
        from email.mime.text import MIMEText
        if isbytestring(text):
            msg = MIMEText(text)
        else:
            msg = MIMEText(text, 'plain', 'utf-8')
        outer.attach(msg)

    if attachment_data is not None:
        from email.mime.base import MIMEBase
        assert attachment_data and attachment_name
        try:
            maintype, subtype = attachment_type.split('/', 1)
        except AttributeError:
            maintype, subtype = 'application', 'octet-stream'
        msg = MIMEBase(maintype, subtype)
        msg.set_payload(attachment_data)
        encoders.encode_base64(msg)
        msg.add_header('Content-Disposition', 'attachment',
                       filename=attachment_name)
        outer.attach(msg)

    return outer.as_string()

def get_mx(host, verbose=0):
    import dns.resolver
    if verbose:
        print 'Find mail exchanger for', host
    answers = list(dns.resolver.query(host, 'MX'))
    answers.sort(cmp=lambda x, y: cmp(int(getattr(x, 'preference', sys.maxint)),
                                      int(getattr(y, 'preference', sys.maxint))))
    return [str(x.exchange) for x in answers if hasattr(x, 'exchange')]

def sendmail_direct(from_, to, msg, timeout, localhost, verbose):
    import smtplib
    hosts = get_mx(to.split('@')[-1].strip(), verbose)
    timeout=None # Non blocking sockets sometimes don't work
    s = smtplib.SMTP(timeout=timeout, local_hostname=localhost)
    s.set_debuglevel(verbose)
    if not hosts:
        raise ValueError('No mail server found for address: %s'%to)
    last_error = last_traceback = None
    for host in hosts:
        try:
            s.connect(host, 25)
            s.sendmail(from_, [to], msg)
            return s.quit()
        except Exception, e:
            last_error, last_traceback = e, traceback.format_exc()
    if last_error is not None:
        print last_traceback
        raise IOError('Failed to send mail: '+repr(last_error))


def sendmail(msg, from_, to, localhost=None, verbose=0, timeout=30,
             relay=None, username=None, password=None, encryption='TLS',
             port=-1):
    if relay is None:
        for x in to:
            return sendmail_direct(from_, x, msg, timeout, localhost, verbose)
    import smtplib
    cls = smtplib.SMTP if encryption == 'TLS' else smtplib.SMTP_SSL
    timeout = None # Non-blocking sockets sometimes don't work
    port = int(port)
    s = cls(timeout=timeout, local_hostname=localhost)
    s.set_debuglevel(verbose)
    if port < 0:
        port = 25 if encryption == 'TLS' else 465
    s.connect(relay, port)
    if encryption == 'TLS':
        s.starttls()
        s.ehlo()
    if username is not None and password is not None:
        if encryption == 'SSL':
            s.sock = s.file.sslobj
        s.login(username, password)
    s.sendmail(from_, to, msg)
    return s.quit()

def option_parser():
    try:
        from calibre.utils.config import OptionParser
        OptionParser
    except ImportError:
        from optparse import OptionParser
    import textwrap
    parser = OptionParser(textwrap.dedent('''\
    %prog [options] [from to text]

    Send mail using the SMTP protocol. %prog has two modes of operation. In the
    compose mode you specify from to and text and these are used to build and
    send an email message. In the filter mode, %prog reads a complete email
    message from STDIN and sends it.

    text is the body of the email message.
    If text is not specified, a complete email message is read from STDIN.
    from is the email address of the sender and to is the email address
    of the recipient. When a complete email is read from STDIN, from and to
    are only used in the SMTP negotiation, the message headers are not modified.
    '''))
    c=parser.add_option_group('COMPOSE MAIL',
        'Options to compose an email. Ignored if text is not specified').add_option
    c('-a', '--attachment', help='File to attach to the email')
    c('-s', '--subject', help='Subject of the email')

    parser.add_option('-l', '--localhost',
                      help=('Host name of localhost. Used when connecting '
                            'to SMTP server.'))
    r=parser.add_option_group('SMTP RELAY',
        'Options to use an SMTP relay server to send mail. '
        'calibre will try to send the email directly unless --relay is '
        'specified.').add_option
    r('-r', '--relay', help=('An SMTP relay server to use to send mail.'))
    r('-p', '--port', default=-1,
      help='Port to connect to on relay server. Default is to use 465 if '
      'encryption method is SSL and 25 otherwise.')
    r('-u', '--username', help='Username for relay')
    r('-p', '--password', help='Password for relay')
    r('-e', '--encryption-method', default='TLS',
      choices=['TLS', 'SSL'],
      help='Encryption method to use when connecting to relay. Choices are '
      'TLS and SSL. Default is TLS.')
    parser.add_option('-o', '--outbox', help='Path to maildir folder to store '
                      'failed email messages in.')
    parser.add_option('-f', '--fork', default=False, action='store_true',
                      help='Fork and deliver message in background. '
                      'If you use this option, you should also use --outbox '
                      'to handle delivery failures.')
    parser.add_option('-t', '--timeout', help='Timeout for connection')
    parser.add_option('-v', '--verbose', default=0, action='count',
                      help='Be more verbose')
    return parser

def extract_email_address(raw):
    from email.utils import parseaddr
    return parseaddr(raw)[-1]

def compose_mail(from_, to, text, subject=None, attachment=None,
        attachment_name=None):
    attachment_type = attachment_data = None
    if attachment is not None:
        try:
            from calibre import guess_type
            guess_type
        except ImportError:
            from mimetypes import guess_type
        attachment_data = attachment.read() if hasattr(attachment, 'read') \
                            else open(attachment, 'rb').read()
        attachment_type = guess_type(getattr(attachment, 'name', attachment))[0]
        if attachment_name is None:
            attachment_name = os.path.basename(getattr(attachment,
                'name', attachment))
    subject = subject if subject else 'no subject'
    return create_mail(from_, to, subject, text=text,
            attachment_data=attachment_data, attachment_type=attachment_type,
            attachment_name=attachment_name)

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)


    if len(args) > 1:
        msg = compose_mail(args[1], args[2], args[3], subject=opts.subject,
                           attachment=opts.attachment)
        from_, to = args[1:3]
        efrom, eto = map(extract_email_address, (from_, to))
        eto = [eto]
    else:
        msg = sys.stdin.read()
        from email.parser import Parser
        from email.utils import getaddresses
        eml = Parser.parsestr(msg, headersonly=True)
        tos = eml.get_all('to', [])
        ccs = eml.get_all('cc', [])
        eto = getaddresses(tos + ccs)
        if not eto:
            raise ValueError('Email from STDIN does not specify any recipients')
        efrom = getaddresses(eml.get_all('from', []))
        if not efrom:
            raise ValueError('Email from STDIN does not specify a sender')
        efrom = efrom[0]


    outbox = None
    if opts.outbox is not None:
        outbox = os.path.abspath(os.path.expanduser(opts.outbox))
        from mailbox import Maildir
        outbox = Maildir(opts.outbox, factory=None)
    if opts.fork:
        if os.fork() != 0:
            return 0
    try:
        sendmail(msg, efrom, eto, localhost=opts.localhost, verbose=opts.verbose,
             timeout=opts.timeout, relay=opts.relay, username=opts.username,
             password=opts.password, port=opts.port,
             encryption=opts.encryption_method)
    except:
        if outbox is not None:
            outbox.add(msg)
            print 'Delivery failed. Message saved to', opts.outbox
        raise
    return 0

def config(defaults=None):
    from calibre.utils.config import Config, StringConfig
    desc = _('Control email delivery')
    c = Config('smtp',desc) if defaults is None else StringConfig(defaults,desc)
    c.add_opt('from_')
    c.add_opt('accounts', default={})
    c.add_opt('relay_host')
    c.add_opt('relay_port', default=25)
    c.add_opt('relay_username')
    c.add_opt('relay_password')
    c.add_opt('encryption', default='TLS', choices=['TLS', 'SSL'])
    return c


if __name__ == '__main__':
    sys.exit(main())
