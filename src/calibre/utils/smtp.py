

__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'
'''
This module implements a simple commandline SMTP client that supports:

  * Delivery via an SMTP relay with SSL or TLS
  * Background delivery with failures being saved in a maildir mailbox
'''

import sys, traceback, os, socket, encodings.idna as idna
from calibre import isbytestring
from calibre.constants import iswindows
from polyglot.builtins import unicode_type, as_unicode, native_string_type


def decode_fqdn(fqdn):
    if isinstance(fqdn, bytes):
        enc = 'mbcs' if iswindows else 'utf-8'
        try:
            fqdn = fqdn.decode(enc)
        except Exception:
            fqdn = ''
    return fqdn


def sanitize_hostname(hostname):
    return hostname.replace('..', '_')


def safe_localhost():
    # RFC 2821 says we should use the fqdn in the EHLO/HELO verb, and
    # if that can't be calculated, that we should use a domain literal
    # instead (essentially an encoded IP address like [A.B.C.D]).
    fqdn = decode_fqdn(socket.getfqdn())
    if '.' in fqdn and fqdn != '.':
        # Some mail servers have problems with non-ascii local hostnames, see
        # https://bugs.launchpad.net/bugs/1256549
        try:
            local_hostname = as_unicode(idna.ToASCII(fqdn))
        except Exception:
            local_hostname = 'localhost.localdomain'
    else:
        # We can't find an fqdn hostname, so use a domain literal
        addr = '127.0.0.1'
        try:
            addr = socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            pass
        local_hostname = '[%s]' % addr
    return local_hostname


def get_msgid_domain(from_):
    from email.utils import parseaddr
    try:
        # Parse out the address from the From line, and then the domain from that
        from_email = parseaddr(from_)[1]
        msgid_domain = from_email.partition('@')[2].strip()
        # This can sometimes sneak through parseaddr if the input is malformed
        msgid_domain = msgid_domain.rstrip('>').strip()
    except Exception:
        msgid_domain = ''
    return msgid_domain or safe_localhost()


def create_mail(from_, to, subject, text=None, attachment_data=None,
                 attachment_type=None, attachment_name=None):
    assert text or attachment_data

    from email.mime.multipart import MIMEMultipart
    from email.utils import formatdate
    from email import encoders
    import uuid

    outer = MIMEMultipart()
    outer['Subject'] = subject
    outer['To'] = to
    outer['From'] = from_
    outer['Date'] = formatdate(localtime=True)
    outer['Message-Id'] = "<{}@{}>".format(uuid.uuid4(), get_msgid_domain(from_))
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
        from email.header import Header
        assert attachment_data and attachment_name
        try:
            maintype, subtype = attachment_type.split('/', 1)
        except AttributeError:
            maintype, subtype = 'application', 'octet-stream'
        msg = MIMEBase(maintype, subtype, name=Header(attachment_name, 'utf-8').encode())
        msg.set_payload(attachment_data)
        encoders.encode_base64(msg)
        msg.add_header('Content-Disposition', 'attachment',
                       filename=Header(attachment_name, 'utf-8').encode())
        outer.attach(msg)

    return outer.as_string()


def get_mx(host, verbose=0):
    import dns.resolver
    if verbose:
        print('Find mail exchanger for', host)
    answers = list(dns.resolver.query(host, 'MX'))
    answers.sort(key=lambda x: int(getattr(x, 'preference', sys.maxsize)))
    return [unicode_type(x.exchange) for x in answers if hasattr(x, 'exchange')]


def sendmail_direct(from_, to, msg, timeout, localhost, verbose,
        debug_output=None):
    import polyglot.smtplib as smtplib
    hosts = get_mx(to.split('@')[-1].strip(), verbose)
    timeout=None  # Non blocking sockets sometimes don't work
    kwargs = dict(timeout=timeout, local_hostname=sanitize_hostname(localhost or safe_localhost()))
    if debug_output is not None:
        kwargs['debug_to'] = debug_output
    s = smtplib.SMTP(**kwargs)
    s.set_debuglevel(verbose)
    if not hosts:
        raise ValueError('No mail server found for address: %s'%to)
    last_error = last_traceback = None
    for host in hosts:
        try:
            s.connect(host, 25)
            s.sendmail(from_, [to], msg)
            return s.quit()
        except Exception as e:
            last_error, last_traceback = e, traceback.format_exc()
    if last_error is not None:
        print(last_traceback)
        raise IOError('Failed to send mail: '+repr(last_error))


def get_smtp_class(use_ssl=False, debuglevel=0):
    # We need this as in python 3.7 we have to pass the hostname
    # in the constructor, because of https://bugs.python.org/issue36094
    # which means the constructor calls connect(),
    # but there is no way to set debuglevel before connect() is called
    import polyglot.smtplib as smtplib
    cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    bases = (cls,)
    return type(native_string_type('SMTP'), bases, {native_string_type('debuglevel'): debuglevel})


def sendmail(msg, from_, to, localhost=None, verbose=0, timeout=None,
             relay=None, username=None, password=None, encryption='TLS',
             port=-1, debug_output=None, verify_server_cert=False, cafile=None):
    if relay is None:
        for x in to:
            return sendmail_direct(from_, x, msg, timeout, localhost, verbose)
    timeout = None  # Non-blocking sockets sometimes don't work
    port = int(port)
    if port < 0:
        port = 25 if encryption != 'SSL' else 465
    kwargs = dict(host=relay, port=port, timeout=timeout, local_hostname=sanitize_hostname(localhost or safe_localhost()))
    if debug_output is not None:
        kwargs['debug_to'] = debug_output
    cls = get_smtp_class(use_ssl=encryption == 'SSL', debuglevel=verbose)
    s = cls(**kwargs)
    if encryption == 'TLS':
        context = None
        if verify_server_cert:
            import ssl
            context = ssl.create_default_context(cafile=cafile)
        s.starttls(context=context)
        s.ehlo()
    if username is not None and password is not None:
        s.login(username, password)
    ret = None
    try:
        s.sendmail(from_, to, msg)
    finally:
        try:
            ret = s.quit()
        except:
            pass  # Ignore so as to not hide original error
    return ret


def option_parser():
    try:
        from calibre.utils.config import OptionParser
        OptionParser
    except ImportError:
        from optparse import OptionParser
    parser = OptionParser(_('''\
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
        _('Options to compose an email. Ignored if text is not specified')).add_option
    c('-a', '--attachment', help=_('File to attach to the email'))
    c('-s', '--subject', help=_('Subject of the email'))

    parser.add_option('-l', '--localhost',
                      help=_('Host name of localhost. Used when connecting '
                            'to SMTP server.'))
    r=parser.add_option_group('SMTP RELAY',
        _('Options to use an SMTP relay server to send mail. '
        'calibre will try to send the email directly unless --relay is '
        'specified.')).add_option
    r('-r', '--relay', help=_('An SMTP relay server to use to send mail.'))
    r('-p', '--port', default=-1,
      help=_('Port to connect to on relay server. Default is to use 465 if '
      'encryption method is SSL and 25 otherwise.'))
    r('-u', '--username', help=_('Username for relay'))
    r('-p', '--password', help=_('Password for relay'))
    r('-e', '--encryption-method', default='TLS',
      choices=['TLS', 'SSL', 'NONE'],
      help=_('Encryption method to use when connecting to relay. Choices are '
      'TLS, SSL and NONE. Default is TLS. WARNING: Choosing NONE is highly insecure'))
    r('--dont-verify-server-certificate', help=_(
        'Do not verify the server certificate when connecting using TLS. This used'
        ' to be the default behavior in calibre versions before 3.27. If you are using'
        ' a relay with a self-signed or otherwise invalid certificate, you can use this option to restore'
        ' the pre 3.27 behavior'))
    r('--cafile', help=_(
        'Path to a file of concatenated CA certificates in PEM format, used to verify the'
        ' server certificate when using TLS. By default, the system CA certificates are used.'))
    parser.add_option('-o', '--outbox', help=_('Path to maildir folder to store '
                      'failed email messages in.'))
    parser.add_option('-f', '--fork', default=False, action='store_true',
                      help=_('Fork and deliver message in background. '
                      'If you use this option, you should also use --outbox '
                      'to handle delivery failures.'))
    parser.add_option('-t', '--timeout', help=_('Timeout for connection'))
    parser.add_option('-v', '--verbose', default=0, action='count',
                      help=_('Be more verbose'))
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
        if len(args) < 4:
            print('You must specify the from address, to address and body text'
                    ' on the command line')
            return 1
        msg = compose_mail(args[1], args[2], args[3], subject=opts.subject,
                           attachment=opts.attachment)
        from_, to = args[1:3]
        eto = [extract_email_address(x.strip()) for x in to.split(',')]
        efrom = extract_email_address(from_)
    else:
        msg = sys.stdin.read()
        from email import message_from_string
        from email.utils import getaddresses
        eml = message_from_string(msg)
        tos = eml.get_all('to', [])
        ccs = eml.get_all('cc', []) + eml.get_all('bcc', [])
        eto = [x[1] for x in getaddresses(tos + ccs) if x[1]]
        if not eto:
            raise ValueError('Email from STDIN does not specify any recipients')
        efrom = getaddresses(eml.get_all('from', []))
        if not efrom:
            raise ValueError('Email from STDIN does not specify a sender')
        efrom = efrom[0][1]

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
             encryption=opts.encryption_method, verify_server_cert=not opts.dont_verify_server_certificate, cafile=opts.cafile)
    except:
        if outbox is not None:
            outbox.add(msg)
            outbox.close()
            print('Delivery failed. Message saved to', opts.outbox)
        raise
    return 0


def config(defaults=None):
    from calibre.utils.config import Config, StringConfig
    desc = _('Control email delivery')
    c = Config('smtp',desc) if defaults is None else StringConfig(defaults,desc)
    c.add_opt('from_')
    c.add_opt('accounts', default={})
    c.add_opt('subjects', default={})
    c.add_opt('aliases', default={})
    c.add_opt('tags', default={})
    c.add_opt('relay_host')
    c.add_opt('relay_port', default=25)
    c.add_opt('relay_username')
    c.add_opt('relay_password')
    c.add_opt('encryption', default='TLS', choices=['TLS', 'SSL'])
    return c


if __name__ == '__main__':
    sys.exit(main())
