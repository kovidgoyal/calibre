"""Microsoft Internet Explorer cookie loading on Windows.

Copyright 2002-2003 Johnny Lee <typo_pl@hotmail.com> (MSIE Perl code)
Copyright 2002-2006 John J Lee <jjl@pobox.com> (The Python port)

This code is free software; you can redistribute it and/or modify it
under the terms of the BSD or ZPL 2.1 licenses (see the file
COPYING.txt included with the distribution).

"""

# XXX names and comments are not great here

import os, re, time, struct, logging
if os.name == "nt":
    import _winreg

from _clientcookie import FileCookieJar, CookieJar, Cookie, \
     MISSING_FILENAME_TEXT, LoadError

debug = logging.getLogger("mechanize").debug


def regload(path, leaf):
    key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, path, 0,
                          _winreg.KEY_ALL_ACCESS)
    try:
        value = _winreg.QueryValueEx(key, leaf)[0]
    except WindowsError:
        value = None
    return value

WIN32_EPOCH = 0x019db1ded53e8000L  # 1970 Jan 01 00:00:00 in Win32 FILETIME

def epoch_time_offset_from_win32_filetime(filetime):
    """Convert from win32 filetime to seconds-since-epoch value.

    MSIE stores create and expire times as Win32 FILETIME, which is 64
    bits of 100 nanosecond intervals since Jan 01 1601.

    mechanize expects time in 32-bit value expressed in seconds since the
    epoch (Jan 01 1970).

    """
    if filetime < WIN32_EPOCH:
        raise ValueError("filetime (%d) is before epoch (%d)" %
                         (filetime, WIN32_EPOCH))

    return divmod((filetime - WIN32_EPOCH), 10000000L)[0]

def binary_to_char(c): return "%02X" % ord(c)
def binary_to_str(d): return "".join(map(binary_to_char, list(d)))

class MSIEBase:
    magic_re = re.compile(r"Client UrlCache MMF Ver \d\.\d.*")
    padding = "\x0d\xf0\xad\x0b"

    msie_domain_re = re.compile(r"^([^/]+)(/.*)$")
    cookie_re = re.compile("Cookie\:.+\@([\x21-\xFF]+).*?"
                           "(.+\@[\x21-\xFF]+\.txt)")

    # path under HKEY_CURRENT_USER from which to get location of index.dat
    reg_path = r"software\microsoft\windows" \
               r"\currentversion\explorer\shell folders"
    reg_key = "Cookies"

    def __init__(self):
        self._delayload_domains = {}

    def _delayload_domain(self, domain):
        # if necessary, lazily load cookies for this domain
        delayload_info = self._delayload_domains.get(domain)
        if delayload_info is not None:
            cookie_file, ignore_discard, ignore_expires = delayload_info
            try:
                self.load_cookie_data(cookie_file,
                                      ignore_discard, ignore_expires)
            except (LoadError, IOError):
                debug("error reading cookie file, skipping: %s", cookie_file)
            else:
                del self._delayload_domains[domain]

    def _load_cookies_from_file(self, filename):
        debug("Loading MSIE cookies file: %s", filename)
        cookies = []

        cookies_fh = open(filename)

        try:
            while 1:
                key = cookies_fh.readline()
                if key == "": break

                rl = cookies_fh.readline
                def getlong(rl=rl): return long(rl().rstrip())
                def getstr(rl=rl): return rl().rstrip()

                key = key.rstrip()
                value = getstr()
                domain_path = getstr()
                flags = getlong()  # 0x2000 bit is for secure I think
                lo_expire = getlong()
                hi_expire = getlong()
                lo_create = getlong()
                hi_create = getlong()
                sep = getstr()

                if "" in (key, value, domain_path, flags, hi_expire, lo_expire,
                          hi_create, lo_create, sep) or (sep != "*"):
                    break

                m = self.msie_domain_re.search(domain_path)
                if m:
                    domain = m.group(1)
                    path = m.group(2)

                    cookies.append({"KEY": key, "VALUE": value, "DOMAIN": domain,
                                    "PATH": path, "FLAGS": flags, "HIXP": hi_expire,
                                    "LOXP": lo_expire, "HICREATE": hi_create,
                                    "LOCREATE": lo_create})
        finally:
            cookies_fh.close()

        return cookies

    def load_cookie_data(self, filename,
                         ignore_discard=False, ignore_expires=False):
        """Load cookies from file containing actual cookie data.

        Old cookies are kept unless overwritten by newly loaded ones.

        You should not call this method if the delayload attribute is set.

        I think each of these files contain all cookies for one user, domain,
        and path.

        filename: file containing cookies -- usually found in a file like
         C:\WINNT\Profiles\joe\Cookies\joe@blah[1].txt

        """
        now = int(time.time())

        cookie_data = self._load_cookies_from_file(filename)

        for cookie in cookie_data:
            flags = cookie["FLAGS"]
            secure = ((flags & 0x2000) != 0)
            filetime = (cookie["HIXP"] << 32) + cookie["LOXP"]
            expires = epoch_time_offset_from_win32_filetime(filetime)
            if expires < now:
                discard = True
            else:
                discard = False
            domain = cookie["DOMAIN"]
            initial_dot = domain.startswith(".")
            if initial_dot:
                domain_specified = True
            else:
                # MSIE 5 does not record whether the domain cookie-attribute
                # was specified.
                # Assuming it wasn't is conservative, because with strict
                # domain matching this will match less frequently; with regular
                # Netscape tail-matching, this will match at exactly the same
                # times that domain_specified = True would.  It also means we
                # don't have to prepend a dot to achieve consistency with our
                # own & Mozilla's domain-munging scheme.
                domain_specified = False

            # assume path_specified is false
            # XXX is there other stuff in here? -- eg. comment, commentURL?
            c = Cookie(0,
                       cookie["KEY"], cookie["VALUE"],
                       None, False,
                       domain, domain_specified, initial_dot,
                       cookie["PATH"], False,
                       secure,
                       expires,
                       discard,
                       None,
                       None,
                       {"flags": flags})
            if not ignore_discard and c.discard:
                continue
            if not ignore_expires and c.is_expired(now):
                continue
            CookieJar.set_cookie(self, c)

    def load_from_registry(self, ignore_discard=False, ignore_expires=False,
                           username=None):
        """
        username: only required on win9x

        """
        cookies_dir = regload(self.reg_path, self.reg_key)
        filename = os.path.normpath(os.path.join(cookies_dir, "INDEX.DAT"))
        self.load(filename, ignore_discard, ignore_expires, username)

    def _really_load(self, index, filename, ignore_discard, ignore_expires,
                     username):
        now = int(time.time())

        if username is None:
            username = os.environ['USERNAME'].lower()

        cookie_dir = os.path.dirname(filename)

        data = index.read(256)
        if len(data) != 256:
            raise LoadError("%s file is too short" % filename)

        # Cookies' index.dat file starts with 32 bytes of signature
        # followed by an offset to the first record, stored as a little-
        # endian DWORD.
        sig, size, data = data[:32], data[32:36], data[36:]
        size = struct.unpack("<L", size)[0]

        # check that sig is valid
        if not self.magic_re.match(sig) or size != 0x4000:
            raise LoadError("%s ['%s' %s] does not seem to contain cookies" %
                          (str(filename), sig, size))

        # skip to start of first record
        index.seek(size, 0)

        sector = 128  # size of sector in bytes

        while 1:
            data = ""

            # Cookies are usually in two contiguous sectors, so read in two
            # sectors and adjust if not a Cookie.
            to_read = 2 * sector
            d = index.read(to_read)
            if len(d) != to_read:
                break
            data = data + d

            # Each record starts with a 4-byte signature and a count
            # (little-endian DWORD) of sectors for the record.
            sig, size, data = data[:4], data[4:8], data[8:]
            size = struct.unpack("<L", size)[0]

            to_read = (size - 2) * sector

##             from urllib import quote
##             print "data", quote(data)
##             print "sig", quote(sig)
##             print "size in sectors", size
##             print "size in bytes", size*sector
##             print "size in units of 16 bytes", (size*sector) / 16
##             print "size to read in bytes", to_read
##             print

            if sig != "URL ":
                assert (sig in ("HASH", "LEAK",
                                self.padding, "\x00\x00\x00\x00"),
                        "unrecognized MSIE index.dat record: %s" %
                        binary_to_str(sig))
                if sig == "\x00\x00\x00\x00":
                    # assume we've got all the cookies, and stop
                    break
                if sig == self.padding:
                    continue
                # skip the rest of this record
                assert to_read >= 0
                if size != 2:
                    assert to_read != 0
                    index.seek(to_read, 1)
                continue

            # read in rest of record if necessary
            if size > 2:
                more_data = index.read(to_read)
                if len(more_data) != to_read: break
                data = data + more_data

            cookie_re = ("Cookie\:%s\@([\x21-\xFF]+).*?" % username +
                         "(%s\@[\x21-\xFF]+\.txt)" % username)
            m = re.search(cookie_re, data, re.I)
            if m:
                cookie_file = os.path.join(cookie_dir, m.group(2))
                if not self.delayload:
                    try:
                        self.load_cookie_data(cookie_file,
                                              ignore_discard, ignore_expires)
                    except (LoadError, IOError):
                        debug("error reading cookie file, skipping: %s",
                              cookie_file)
                else:
                    domain = m.group(1)
                    i = domain.find("/")
                    if i != -1:
                        domain = domain[:i]

                    self._delayload_domains[domain] = (
                        cookie_file, ignore_discard, ignore_expires)


class MSIECookieJar(MSIEBase, FileCookieJar):
    """FileCookieJar that reads from the Windows MSIE cookies database.

    MSIECookieJar can read the cookie files of Microsoft Internet Explorer
    (MSIE) for Windows version 5 on Windows NT and version 6 on Windows XP and
    Windows 98.  Other configurations may also work, but are untested.  Saving
    cookies in MSIE format is NOT supported.  If you save cookies, they'll be
    in the usual Set-Cookie3 format, which you can read back in using an
    instance of the plain old CookieJar class.  Don't save using the same
    filename that you loaded cookies from, because you may succeed in
    clobbering your MSIE cookies index file!

    You should be able to have LWP share Internet Explorer's cookies like
    this (note you need to supply a username to load_from_registry if you're on
    Windows 9x or Windows ME):

    cj = MSIECookieJar(delayload=1)
    # find cookies index file in registry and load cookies from it
    cj.load_from_registry()
    opener = mechanize.build_opener(mechanize.HTTPCookieProcessor(cj))
    response = opener.open("http://example.com/")

    Iterating over a delayloaded MSIECookieJar instance will not cause any
    cookies to be read from disk.  To force reading of all cookies from disk,
    call read_all_cookies.  Note that the following methods iterate over self:
    clear_temporary_cookies, clear_expired_cookies, __len__, __repr__, __str__
    and as_string.

    Additional methods:

    load_from_registry(ignore_discard=False, ignore_expires=False,
                       username=None)
    load_cookie_data(filename, ignore_discard=False, ignore_expires=False)
    read_all_cookies()

    """
    def __init__(self, filename=None, delayload=False, policy=None):
        MSIEBase.__init__(self)
        FileCookieJar.__init__(self, filename, delayload, policy)

    def set_cookie(self, cookie):
        if self.delayload:
            self._delayload_domain(cookie.domain)
        CookieJar.set_cookie(self, cookie)

    def _cookies_for_request(self, request):
        """Return a list of cookies to be returned to server."""
        domains = self._cookies.copy()
        domains.update(self._delayload_domains)
        domains = domains.keys()

        cookies = []
        for domain in domains:
            cookies.extend(self._cookies_for_domain(domain, request))
        return cookies

    def _cookies_for_domain(self, domain, request):
        if not self._policy.domain_return_ok(domain, request):
            return []
        debug("Checking %s for cookies to return", domain)
        if self.delayload:
            self._delayload_domain(domain)
        return CookieJar._cookies_for_domain(self, domain, request)

    def read_all_cookies(self):
        """Eagerly read in all cookies."""
        if self.delayload:
            for domain in self._delayload_domains.keys():
                self._delayload_domain(domain)

    def load(self, filename, ignore_discard=False, ignore_expires=False,
             username=None):
        """Load cookies from an MSIE 'index.dat' cookies index file.

        filename: full path to cookie index file
        username: only required on win9x

        """
        if filename is None:
            if self.filename is not None: filename = self.filename
            else: raise ValueError(MISSING_FILENAME_TEXT)

        index = open(filename, "rb")

        try:
            self._really_load(index, filename, ignore_discard, ignore_expires,
                              username)
        finally:
            index.close()
