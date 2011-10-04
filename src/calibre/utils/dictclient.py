# Client for the DICT protocol (RFC2229)
#
# Copyright (C) 2002 John Goerzen
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.

import socket, re

version = '1.0'

def dequote(str):
    """Will remove single or double quotes from the start and end of a string
    and return the result."""
    quotechars = "'\""
    while len(str) and str[0] in quotechars:
        str = str[1:]
    while len(str) and str[-1] in quotechars:
        str = str[0:-1]
    return str

def enquote(str):
    """This function will put a string in double quotes, properly
    escaping any existing double quotes with a backslash.  It will
    return the result."""
    return '"' + str.replace('"', "\\\"") + '"'

class Connection:
    """This class is used to establish a connection to a database server.
    You will usually use this as the first call into the dictclient library.
    Instantiating it takes two optional arguments: a hostname (a string)
    and a port (an int).  The hostname defaults to localhost
    and the port to 2628, the port specified in RFC."""
    def __init__(self, hostname = 'localhost', port = 2628):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((hostname, port))
        self.rfile = self.sock.makefile("rt")
        self.wfile = self.sock.makefile("wt", 0)
        self.saveconnectioninfo()

    def getresultcode(self):
        """Generic function to get a result code.  It will return a list
        consisting of two items: the integer result code and the text
        following.  You will not usually use this function directly."""
        line = self.rfile.readline().strip()
        code, text = line.split(' ', 1)
        return [int(code), text]

    def get200result(self):
        """Used when expecting a single line of text -- a 200-class
        result.  Returns [intcode, remaindertext]"""

        code, text = self.getresultcode()
        if code < 200 or code >= 300:
            raise Exception, "Got '%s' when 200-class response expected" % \
                  text
        return [code, text]

    def get100block(self):
        """Used when expecting multiple lines of text -- gets the block
        part only.  Does not get any codes or anything!  Returns a string."""
        data = []
        while 1:
            line = self.rfile.readline().strip()
            if line == '.':
                break
            data.append(line)
        return "\n".join(data)

    def get100result(self):
        """Used when expecting multiple lines of text, terminated by a period
        and a 200 code.  Returns: [initialcode, [bodytext_1lineperentry],
        finalcode]"""
        code, text = self.getresultcode()
        if code < 100 or code >= 200:
            raise Exception, "Got '%s' when 100-class response expected" % \
                  code

        bodylines = self.get100block().split("\n")

        code2 = self.get200result()[0]
        return [code, bodylines, code2]

    def get100dict(self):
        """Used when expecting a dictionary of results.  Will read from
        the initial 100 code, to a period and the 200 code."""
        dict = {}
        for line in self.get100result()[1]:
            key, val = line.split(' ', 1)
            dict[key] = dequote(val)
        return dict

    def saveconnectioninfo(self):
        """Called by __init__ to handle the initial connection.  Will
        save off the capabilities and messageid."""
        code, string = self.get200result()
        assert code == 220
        capstr, msgid = re.search('<(.*)> (<.*>)$', string).groups()
        self.capabilities = capstr.split('.')
        self.messageid = msgid

    def getcapabilities(self):
        """Returns a list of the capabilities advertised by the server."""
        return self.capabilities

    def getmessageid(self):
        """Returns the message id, including angle brackets."""
        return self.messageid

    def getdbdescs(self):
        """Gets a dict of available databases.  The key is the db name
        and the value is the db description.  This command may generate
        network traffic!"""
        if hasattr(self, 'dbdescs'):
            return self.dbdescs

        self.sendcommand("SHOW DB")
        self.dbdescs = self.get100dict()
        return self.dbdescs

    def getstratdescs(self):
        """Gets a dict of available strategies.  The key is the strat
        name and the value is the strat description.  This call may
        generate network traffic!"""
        if hasattr(self, 'stratdescs'):
            return self.stratdescs

        self.sendcommand("SHOW STRAT")
        self.stratdescs = self.get100dict()
        return self.stratdescs

    def getdbobj(self, dbname):
        """Gets a Database object corresponding to the database name passed
        in.  This function explicitly will *not* generate network traffic.
        If you have not yet run getdbdescs(), it will fail."""
        if not hasattr(self, 'dbobjs'):
            self.dbobjs = {}

        if self.dbobjs.has_key(dbname):
            return self.dbobjs[dbname]

        # We use self.dbdescs explicitly since we don't want to
        # generate net traffic with this request!

        if dbname != '*' and dbname != '!' and \
               not dbname in self.dbdescs.keys():
            raise Exception, "Invalid database name '%s'" % dbname

        self.dbobjs[dbname] = Database(self, dbname)
        return self.dbobjs[dbname]

    def sendcommand(self, command):
        """Takes a command, without a newline character, and sends it to
        the server."""
        self.wfile.write(command + "\n")

    def define(self, database, word):
        """Returns a list of Definition objects for each matching
        definition.  Parameters are the database name and the word
        to look up.  This is one of the main functions you will use
        to interact with the server.  Returns a list of Definition
        objects.  If there are no matches, an empty list is returned.

        Note: database may be '*' which means to search all databases,
        or '!' which means to return matches from the first database that
        has a match."""
        self.getdbdescs()               # Prime the cache

        if database != '*' and database != '!' and \
           not database in self.getdbdescs():
            raise Exception, "Invalid database '%s' specified" % database

        self.sendcommand("DEFINE " + enquote(database) + " " + enquote(word))
        code = self.getresultcode()[0]

        retval = []

        if code == 552:
            # No definitions.
            return []
        if code != 150:
            raise Exception, "Unknown code %d" % code

        while 1:
            code, text = self.getresultcode()
            if code != 151:
                break

            resultword, resultdb = re.search('^"(.+)" (\S+)', text).groups()
            defstr = self.get100block()
            retval.append(Definition(self, self.getdbobj(resultdb),
                                     resultword, defstr))
        return retval

    def match(self, database, strategy, word):
        """Gets matches for a query.  Arguments are database name,
        the strategy (see available ones in getstratdescs()), and the
        pattern/word to look for.  Returns a list of Definition objects.
        If there is no match, an empty list is returned.

        Note: database may be '*' which means to search all databases,
        or '!' which means to return matches from the first database that
        has a match."""
        self.getstratdescs()            # Prime the cache
        self.getdbdescs()               # Prime the cache
        if not strategy in self.getstratdescs().keys():
            raise Exception, "Invalid strategy '%s'" % strategy
        if database != '*' and database != '!' and \
               not database in self.getdbdescs().keys():
            raise Exception, "Invalid database name '%s'" % database

        self.sendcommand("MATCH %s %s %s" % (enquote(database),
                                             enquote(strategy),
                                             enquote(word)))
        code = self.getresultcode()[0]
        if code == 552:
            # No Matches
            return []
        if code != 152:
            raise Exception, "Unexpected code %d" % code

        retval = []

        for matchline in self.get100block().split("\n"):
            matchdict, matchword = matchline.split(" ", 1)
            retval.append(Definition(self, self.getdbobj(matchdict),
                                     dequote(matchword)))
        if self.getresultcode()[0] != 250:
            raise Exception, "Unexpected end-of-list code %d" % code
        return retval

class Database:
    """An object corresponding to a particular database in a server."""
    def __init__(self, dictconn, dbname):
        """Initialize the object -- requires a Connection object and
        a database name."""
        self.conn = dictconn
        self.name = dbname

    def getname(self):
        """Returns the short name for this database."""
        return self.name

    def getdescription(self):
        if hasattr(self, 'description'):
            return self.description
        if self.getname() == '*':
            self.description = 'All Databases'
        elif self.getname() == '!':
            self.description = 'First matching database'
        else:
            self.description = self.conn.getdbdescs()[self.getname()]
        return self.description

    def getinfo(self):
        """Returns a string of info describing this database."""
        if hasattr(self, 'info'):
            return self.info

        if self.getname() == '*':
            self.info = "This special database will search all databases on the system."
        elif self.getname() == '!':
            self.info = "This special database will return matches from the first matching database."
        else:
            self.conn.sendcommand("SHOW INFO " + self.name)
            self.info = "\n".join(self.conn.get100result()[1])
        return self.info

    def define(self, word):
        """Get a definition from within this database.
        The argument, word, is the word to look up.  The return value is the
        same as from Connection.define()."""
        return self.conn.define(self.getname(), word)

    def match(self, strategy, word):
        """Get a match from within this database.
        The argument, word, is the word to look up.  The return value is
        the same as from Connection.define()."""
        return self.conn.match(self.getname(), strategy, word)

class Definition:
    """An object corresponding to a single definition."""
    def __init__(self, dictconn, db, word, defstr = None):
        """Instantiate the object.  Requires: a Connection object,
        a Database object (NOT corresponding to '*' or '!' databases),
        a word.  Optional: a definition string.  If not supplied,
        it will be fetched if/when it is requested."""
        self.conn = dictconn
        self.db = db
        self.word = word
        self.defstr = defstr

    def getdb(self):
        """Get the Database object corresponding to this definition."""
        return self.db

    def getdefstr(self):
        """Get the definition string (the actual content) of this
        definition."""
        if not self.defstr:
            self.defstr = self.conn.define(self.getdb().getname(), self.word)[0].getdefstr()
        return self.defstr

    def getword(self):
        """Get the word this object describes."""
        return self.word
