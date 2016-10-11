#!/usr/bin/env python2
# This is a patched version of sheel.py to fix
# https://code.google.com/p/apsw/issues/detail?id=142

import sys
import apsw
import shlex
import os
import csv
import re
import textwrap
import time
import codecs
import base64

if sys.platform=="win32":
    _win_colour=False
    try:
        import colorama
        colorama.init()
        del colorama
        _win_colour=True
    except:  # there are several failure reasons, ignore them all
        pass


class Shell(object):
    """Implements a SQLite shell

    :param stdin: Where to read input from (default sys.stdin)
    :param stdout: Where to send output (default sys.stdout)
    :param stderr: Where to send errors (default sys.stderr)
    :param encoding: Default encoding for files opened/created by the
      Shell.  If you want stdin/out/err to use a particular encoding
      then you need to provide them `already configured <http://docs.python.org/library/codecs.html#codecs.open>`__ that way.
    :param args: This should be program arguments only (ie if
      passing in sys.argv do not include sys.argv[0] which is the
      program name.  You can also pass in None and then call
      :meth:`process_args` if you want to catch any errors
      in handling the arguments yourself.
    :param db: A existing :class:`Connection` you wish to use

    The commands and behaviour are modelled after the `interactive
    shell <https://sqlite.org/sqlite.html>`__ that is part of
    SQLite.

    You can inherit from this class to embed in your own code and user
    interface.  Internally everything is handled as unicode.
    Conversions only happen at the point of input or output which you
    can override in your own code.

    This implementation fixes a number of bugs/quirks present in the
    sqlite shell.  Its control-C handling is also friendlier.  Some
    examples of issues not present in this implementation:

    * https://sqlite.org/src/info/c25aab7e7e
    * https://sqlite.org/src/info/7b61b6c6ce
    * https://sqlite.org/src/info/ee19e690ec
    * https://sqlite.org/src/info/2466653295

    Errors and diagnostics are only ever sent to error output
    (self.stderr) and never to the regular output (self.stdout).  This
    means using shell output is always easy and consistent.

    Shell commands begin with a dot (eg .help).  They are implemented
    as a method named after the command (eg command_help).  The method
    is passed one parameter which is the list of arguments to the
    command.

    Output modes are implemented by functions named after the mode (eg
    output_column).

    When you request help the help information is automatically
    generated from the docstrings for the command and output
    functions.

    You should not use a Shell object concurrently from multiple
    threads.  It is one huge set of state information which would
    become inconsistent if used simultaneously, and then give baffling
    errors.  It is safe to call methods one at a time from different
    threads.  ie it doesn't care what thread calls methods as long as
    you don't call more than one concurrently.
    """

    class Error(Exception):
        """Class raised on errors.  The expectation is that the error
        will be displayed by the shell as text so there are no
        specific subclasses as the distinctions between different
        types of errors doesn't matter."""
        pass

    def __init__(self, stdin=None, stdout=None, stderr=None, encoding="utf8", args=None, db=None):
        """Create instance, set defaults and do argument processing."""
        super(Shell, self).__init__()
        # The parameter doc has to be in main class doc as sphinx
        # ignores any described here
        self.exceptions=False
        self.history_file="~/.sqlite_history"
        self._db=None
        self.dbfilename=None
        if db:
            self.db=db, db.filename
        else:
            self.db=None, None
        self.prompt=    "sqlite> "
        self.moreprompt="    ..> "
        self.separator="|"
        self.bail=False
        self.echo=False
        self.timer=False
        self.header=False
        self.nullvalue=""
        self.output=self.output_list
        self._output_table=self._fmt_sql_identifier("table")
        self.widths=[]
        # do we truncate output in list mode?  (explain doesn't, regular does)
        self.truncate=True
        # a stack of previous outputs. turning on explain saves previous, off restores
        self._output_stack=[]

        # other stuff
        self.set_encoding(encoding)
        if stdin is None:
            stdin=sys.stdin
        if stdout is None:
            stdout=sys.stdout
        if stderr is None:
            stderr=sys.stderr
        self.stdin=stdin
        self.stdout=stdout
        self._original_stdout=stdout
        self.stderr=stderr
        # we don't become interactive until the command line args are
        # successfully parsed and acted upon
        self.interactive=None
        # current colouring object
        self.command_colour()  # set to default
        self._using_readline=False
        self._input_stack=[]
        self.input_line_number=0
        self.push_input()
        self.push_output()
        self._input_descriptions=[]

        if args:
            try:
                self.process_args(args)
            except:
                if len(self._input_descriptions):
                    self._input_descriptions.append("Processing command line arguments")
                self.handle_exception()
                raise

        if self.interactive is None:
            self.interactive=getattr(self.stdin, "isatty", False) and self.stdin.isatty() and getattr(self.stdout, "isatty", False) and self.stdout.isatty()

    def _ensure_db(self):
        "The database isn't opened until first use.  This function ensures it is now open."
        if not self._db:
            if not self.dbfilename:
                self.dbfilename=":memory:"
            self._db=apsw.Connection(self.dbfilename, flags=apsw.SQLITE_OPEN_URI | apsw.SQLITE_OPEN_READWRITE | apsw.SQLITE_OPEN_CREATE)
        return self._db

    def _set_db(self, newv):
        "Sets the open database (or None) and filename"
        (db, dbfilename)=newv
        if self._db:
            self._db.close()
            self._db=None
        self._db=db
        self.dbfilename=dbfilename

    db=property(_ensure_db, _set_db, None, "The current :class:`Connection`")

    def process_args(self, args):
        """Process command line options specified in args.  It is safe to
        call this multiple times.  We try to be compatible with SQLite shell
        argument parsing.

        :param args: A list of string options.  Do not include the
           program as args[0]

        :returns: A tuple of (databasefilename, initfiles,
           sqlncommands).  This is provided for informational purposes
           only - they have already been acted upon.  An example use
           is that the SQLite shell does not enter the main interactive
           loop if any sql/commands were provided.

        The first non-option is the database file name.  Each
        remaining non-option is treated as a complete input (ie it
        isn't joined with others looking for a trailing semi-colon).

        The SQLite shell uses single dash in front of options.  We
        allow both single and double dashes.  When an unrecognized
        argument is encountered then
        :meth:`process_unknown_args` is called.
        """
        # we don't use optparse as we need to use single dashes for
        # options - all hand parsed
        if not args:
            return None, [], []

        # are options still valid?
        options=True
        # have we seen the database name?
        havedbname=False
        # List of init files to read
        inits=[]
        # List of sql/dot commands
        sqls=[]

        while args:
            if not options or not args[0].startswith("-"):
                options=False
                if not havedbname:
                    # grab new database
                    self.db=None, args[0]
                    havedbname=True
                else:
                    sqls.append(args[0])
                args=args[1:]
                continue

            # remove initial single or double dash
            args[0]=args[0][1:]
            if args[0].startswith("-"):
                args[0]=args[0][1:]

            if args[0]=="init":
                if len(args)<2:
                    raise self.Error("You need to specify a filename after -init")
                inits.append(args[1])
                args=args[2:]
                continue

            if args[0]=="header" or args[0]=="noheader":
                self.header=args[0]=="header"
                args=args[1:]
                continue

            if args[0] in ("echo", "bail", "interactive"):
                setattr(self, args[0], True)
                args=args[1:]
                continue

            if args[0]=="batch":
                self.interactive=False
                args=args[1:]
                continue

            if args[0] in ("separator", "nullvalue", "encoding"):
                if len(args)<2:
                    raise self.Error("You need to specify a value after -"+args[0])
                getattr(self, "command_"+args[0])([args[1]])
                args=args[2:]
                continue

            if args[0]=="version":
                self.write(self.stdout, apsw.sqlitelibversion()+"\n")
                # A pretty gnarly thing to do
                sys.exit(0)

            if args[0]=="help":
                self.write(self.stderr, self.usage())
                sys.exit(0)

            if args[0] in ("no-colour", "no-color", "nocolour", "nocolor"):
                self.colour_scheme="off"
                self._out_colour()
                args=args[1:]
                continue

            # only remaining known args are output modes
            if getattr(self, "output_"+args[0], None):
                self.command_mode(args[:1])
                args=args[1:]
                continue

            newargs=self.process_unknown_args(args)
            if newargs is None:
                raise self.Error("Unrecognized argument '"+args[0]+"'")
            args=newargs

        for f in inits:
            self.command_read([f])

        for s in sqls:
            self.process_complete_line(s)

        return self.dbfilename, inits, sqls

    def process_unknown_args(self, args):
        """This is called when :meth:`process_args` encounters an
        argument it doesn't understand.  Override this method if you
        want to be able to understand additional command line arguments.

        :param args: A list of the remaining arguments.  The initial one will
           have had the leading dashes removed (eg if it was --foo on the command
           line then args[0] will be "foo"
        :returns: None if you don't recognize the argument either.  Otherwise
           return the list of remaining arguments after you have processed
           yours.
        """
        return None

    def usage(self):
        "Returns the usage message.  Make sure it is newline terminated"

        msg="""
Usage: program [OPTIONS] FILENAME [SQL|CMD] [SQL|CMD]...
FILENAME is the name of a SQLite database. A new database is
created if the file does not exist.
OPTIONS include:
   -init filename       read/process named file
   -echo                print commands before execution
   -[no]header          turn headers on or off
   -bail                stop after hitting an error
   -interactive         force interactive I/O
   -batch               force batch I/O
   -column              set output mode to 'column'
   -csv                 set output mode to 'csv'
   -html                set output mode to 'html'
   -line                set output mode to 'line'
   -list                set output mode to 'list'
   -python              set output mode to 'python'
   -separator 'x'       set output field separator (|)
   -nullvalue 'text'    set text string for NULL values
   -version             show SQLite version
   -encoding 'name'     the encoding to use for files
                        opened via .import, .read & .output
   -nocolour            disables colour output to screen
"""
        return msg.lstrip()

    ###
    # Value formatting routines.  They take a value and return a
    # text formatting of them.  Mostly used by the various output's
    # but also by random other pieces of code.
    ###

    _binary_type = eval(("buffer", "bytes")[sys.version_info>=(3,0)])
    _basestring = eval(("basestring", "str")[sys.version_info>=(3,0)])

    # bytes that are ok in C strings - no need for quoting
    _printable=[ord(x) for x in
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789~!@#$%^&*()`_-+={}[]:;,.<>/?|"
                ]

    def _fmt_c_string(self, v):
        "Format as a C string including surrounding double quotes"
        if isinstance(v, self._basestring):
            op=['"']
            for c in v:
                if c=="\\":
                    op.append("\\\\")
                elif c=="\r":
                    op.append("\\r")
                elif c=="\n":
                    op.append("\\n")
                elif c=="\t":
                    op.append("\\t")
                elif ord(c) not in self._printable:
                    op.append("\\"+c)
                else:
                    op.append(c)
            op.append('"')
            return "".join(op)
        elif v is None:
            return '"'+self.nullvalue+'"'
        elif isinstance(v, self._binary_type):
            if sys.version_info<(3,0):
                o=lambda x: ord(x)
                fromc=lambda x: x
            else:
                o=lambda x: x
                fromc=lambda x: chr(x)
            res=['"']
            for c in v:
                if o(c) in self._printable:
                    res.append(fromc(c))
                else:
                    res.append("\\x%02X" % (o(c),))
            res.append('"')
            return "".join(res)
        else:
            # number of some kind
            return '"%s"' % (v,)

    def _fmt_html_col(self, v):
        "Format as HTML (mainly escaping &/</>"
        return self._fmt_text_col(v).\
           replace("&", "&amp;"). \
           replace(">", "&gt;"). \
           replace("<", "&lt;"). \
           replace("'", "&apos;"). \
           replace('"', "&quot;")

    def _fmt_json_value(self, v):
        "Format a value."
        if isinstance(v, self._basestring):
            # we assume utf8 so only some characters need to be escaed
            op=['"']
            for c in v:
                if c=="\\":
                    op.append("\\\\")
                elif c=="\r":
                    op.append("\\r")
                elif c=="\n":
                    op.append("\\n")
                elif c=="\t":
                    op.append("\\t")
                elif c=="/":  # yes you have to escape forward slash for some reason
                    op.append("\\/")
                elif c=='"':
                    op.append("\\"+c)
                elif c=="\\b":
                    op.append("\\b")
                elif c=="\\f":
                    op.append("\\f")
                else:
                    # It isn't clear when \u sequences *must* be used.
                    # Assuming not needed due to utf8 output which
                    # corresponds to what rfc4627 implies.
                    op.append(c)
            op.append('"')
            return "".join(op)
        elif v is None:
            return 'null'
        elif isinstance(v, self._binary_type):
            if sys.version_info<(3,0):
                o=base64.encodestring(v)
            else:
                o=base64.encodebytes(v).decode("ascii")
            if o[-1]=="\n":
                o=o[:-1]
            return '"'+o+'"'
        else:
            # number of some kind
            return '%s' % (v,)

    def _fmt_python(self, v):
        "Format as python literal"
        if v is None:
            return "None"
        elif isinstance(v, self._basestring):
            return repr(v)
        elif isinstance(v, self._binary_type):
            if sys.version_info<(3,0):
                res=["buffer(\""]
                for i in v:
                    if ord(i) in self._printable:
                        res.append(i)
                    else:
                        res.append("\\x%02X" % (ord(i),))
                res.append("\")")
                return "".join(res)
            else:
                res=['b"']
                for i in v:
                    if i in self._printable:
                        res.append(chr(i))
                    else:
                        res.append("\\x%02X" % (i,))
                res.append('"')
                return "".join(res)
        else:
            return "%s" % (v,)

    def _fmt_sql_identifier(self, v):
        "Return the identifier quoted in SQL syntax if needed (eg table and column names)"
        if not len(v):  # yes sqlite does allow zero length identifiers
            return '""'
        nonalnum=re.sub("[A-Za-z_0-9]+", "", v)
        if len(nonalnum)==0:
            if v.upper() not in self._sqlite_reserved:
                # Ok providing it doesn't start with a digit
                if v[0] not in "0123456789":
                    return v
        # double quote it unless there are any double quotes in it
        if '"' in nonalnum:
            return "[%s]" % (v,)
        return '"%s"' % (v,)

    def _fmt_text_col(self, v):
        "Regular text formatting"
        if v is None:
            return self.nullvalue
        elif isinstance(v, self._basestring):
            return v
        elif isinstance(v, self._binary_type):
            # sqlite gives back raw bytes!
            return "<Binary data>"
        else:
            return "%s" % (v,)

    ###
    # The various output routines.  They are always called with the
    # header irrespective of the setting allowing for some per query
    # setup. (see output_column for example).  The doc strings are
    # used to generate help.
    ###

    def output_column(self, header, line):
        """
        Items left aligned in space padded columns.  They are
        truncated if they do not fit. If the width hasn't been
        specified for a column then 10 is used unless the column name
        (header) is longer in which case that width is used.  Use the
        .width command to change column sizes.
        """
        # as an optimization we calculate self._actualwidths which is
        # reset for each query
        if header:
            def gw(n):
                if n<len(self.widths) and self.widths[n]!=0:
                    return self.widths[n]
                # if width is not present or 0 then autosize
                text=self._fmt_text_col(line[n])
                return max(len(text), 10)

            widths=[gw(i) for i in range(len(line))]

            if self.truncate:
                self._actualwidths=["%"+("-%d.%ds", "%d.%ds")[w<0]%(abs(w), abs(w)) for w in widths]
            else:
                self._actualwidths=["%"+("-%ds", "%ds")[w<0]%(abs(w),) for w in widths]

            if self.header:
                # output the headers
                c=self.colour
                cols=[c.header+(self._actualwidths[i] % (self._fmt_text_col(line[i]),))+c.header_ for i in range(len(line))]
                # sqlite shell uses two spaces between columns
                self.write(self.stdout, "  ".join(cols)+"\n")
                if c is self._colours["off"]:
                    self.output_column(False, ["-"*abs(widths[i]) for i in range(len(widths))])
            return
        cols=[self.colour.colour_value(line[i], self._actualwidths[i] % (self._fmt_text_col(line[i]),)) for i in range(len(line))]
        # sqlite shell uses two spaces between columns
        self.write(self.stdout, "  ".join(cols)+"\n")

    def output_csv(self, header, line):
        """
        Items in csv format (comma separated).  Use tabs mode for tab
        separated.  You can use the .separator command to use a
        different one after switching mode.  A separator of comma uses
        double quotes for quoting while other separators do not do any
        quoting.  The Python csv library used for this only supports
        single character separators.
        """

        # we use self._csv for the work, setup when header is
        # supplied. _csv is a tuple of a StringIO and the csv.writer
        # instance.

        # Sigh
        if sys.version_info<(3,0):
            fixdata=lambda x: x.encode("utf8")
        else:
            fixdata=lambda x: x

        if header:
            if sys.version_info<(3,0):
                import StringIO as io
            else:
                import io
            s=io.StringIO()
            kwargs={}
            if self.separator==",":
                kwargs["dialect"]="excel"
            elif self.separator=="\t":
                kwargs["dialect"]="excel-tab"
            else:
                kwargs["quoting"]=csv.QUOTE_NONE
                kwargs["delimiter"]=fixdata(self.separator)
                kwargs["doublequote"]=False
                # csv module is bug ridden junk - I already say no
                # quoting so it still looks for the quotechar and then
                # gets upset that it can't be quoted.  Which bit of no
                # quoting was ambiguous?
                kwargs["quotechar"]="\x00"

            writer=csv.writer(s, **kwargs)
            self._csv=(s, writer)
            if self.header:
                self.output_csv(None, line)
            return

        if header is None:
            c=self.colour
            line=[c.header+fixdata(self._fmt_text_col(l))+c.header_ for l in line]
        else:
            fmt=lambda x: self.colour.colour_value(x, fixdata(self._fmt_text_col(x)))
            line=[fmt(l) for l in line]
        self._csv[1].writerow(line)
        t=self._csv[0].getvalue()
        if sys.version_info<(3,0):
            t=t.decode("utf8")
        # csv lib always does DOS eol
        assert(t.endswith("\r\n"))
        t=t[:-2]
        # should not be other eol irregularities
        assert(not t.endswith("\r") and not t.endswith("\n"))
        self.write(self.stdout, t+"\n")
        self._csv[0].truncate(0)
        self._csv[0].seek(0)

    def output_html(self, header, line):
        "HTML table style"
        if header:
            if not self.header:
                return
            fmt=lambda x: self.colour.header+self._fmt_html_col(x)+self.colour.header_
        else:
            fmt=lambda x: self.colour.colour_value(x, self._fmt_html_col(x))
        line=[fmt(l) for l in line]
        out=["<TR>"]
        for l in line:
            out.append(("<TD>","<TH>")[header])
            out.append(l)
            out.append(("</TD>\n","</TH>\n")[header])
        out.append("</TR>\n")
        self.write(self.stdout, "".join(out))

    def output_insert(self, header, line):
        """
        Lines as SQL insert statements.  The table name is "table"
        unless you specified a different one as the second parameter
        to the .mode command.
        """
        if header:
            return
        fmt=lambda x: self.colour.colour_value(x, apsw.format_sql_value(x))
        out="INSERT INTO "+self._output_table+" VALUES("+",".join([fmt(l) for l in line])+");\n"
        self.write(self.stdout, out)

    def output_json(self, header, line):
        """
        Each line as a JSON object with a trailing comma.  Blobs are
        output as base64 encoded strings.  You should be using UTF8
        output encoding.
        """
        if header:
            self._output_json_cols=line
            return
        fmt=lambda x: self.colour.colour_value(x, self._fmt_json_value(x))
        out=["%s: %s" % (self._fmt_json_value(k), fmt(line[i])) for i,k in enumerate(self._output_json_cols)]
        self.write(self.stdout, "{ "+", ".join(out)+"},\n")

    def output_line(self, header, line):
        """
        One value per line in the form 'column = value' with a blank
        line between rows.
        """
        if header:
            w=5
            for l in line:
                if len(l)>w:
                    w=len(l)
            self._line_info=(w, line)
            return
        fmt=lambda x: self.colour.colour_value(x, self._fmt_text_col(x))
        w=self._line_info[0]
        for i in range(len(line)):
            self.write(self.stdout, "%*s = %s\n" % (w, self._line_info[1][i], fmt(line[i])))
        self.write(self.stdout, "\n")

    def output_list(self, header, line):
        "All items on one line with separator"
        if header:
            if not self.header:
                return
            c=self.colour
            fmt=lambda x: c.header+x+c.header_
        else:
            fmt=lambda x: self.colour.colour_value(x, self._fmt_text_col(x))
        self.write(self.stdout, self.separator.join([fmt(x) for x in line])+"\n")

    def output_python(self, header, line):
        "Tuples in Python source form for each row"
        if header:
            if not self.header:
                return
            c=self.colour
            fmt=lambda x: c.header+self._fmt_python(x)+c.header_
        else:
            fmt=lambda x: self.colour.colour_value(x, self._fmt_python(x))
        self.write(self.stdout, '('+", ".join([fmt(l) for l in line])+"),\n")

    def output_tcl(self, header, line):
        "Outputs TCL/C style strings using current separator"
        # In theory you could paste the output into your source ...
        if header:
            if not self.header:
                return
            c=self.colour
            fmt=lambda x: c.header+self._fmt_c_string(x)+c.header_
        else:
            fmt=lambda x: self.colour.colour_value(x, self._fmt_c_string(x))
        self.write(self.stdout, self.separator.join([fmt(l) for l in line])+"\n")

    def _output_summary(self, summary):
        # internal routine to output a summary line or two
        self.write(self.stdout, self.colour.summary+summary+self.colour.summary_)

    ###
    # Various routines
    ###

    def cmdloop(self, intro=None):
        """Runs the main interactive command loop.

        :param intro: Initial text banner to display instead of the
           default.  Make sure you newline terminate it.
        """
        if intro is None:
            intro="""
SQLite version %s (APSW %s)
Enter ".help" for instructions
Enter SQL statements terminated with a ";"
""" % (apsw.sqlitelibversion(), apsw.apswversion())
            intro=intro.lstrip()
        if self.interactive and intro:
            if sys.version_info<(3,0):
                intro=unicode(intro)
            c=self.colour
            self.write(self.stdout, c.intro+intro+c.intro_)

        using_readline=False
        try:
            if self.interactive and self.stdin is sys.stdin:
                import readline
                old_completer=readline.get_completer()
                readline.set_completer(self.complete)
                readline.parse_and_bind("tab: complete")
                using_readline=True
                try:
                    readline.read_history_file(os.path.expanduser(self.history_file))
                except:
                    # We only expect IOError here but if the history
                    # file does not exist and this code has been
                    # compiled into the module it is possible to get
                    # an IOError that doesn't match the IOError from
                    # Python parse time resulting in an IOError
                    # exception being raised.  Consequently we just
                    # catch all exceptions.
                    pass
        except ImportError:
            pass

        try:
            while True:
                self._input_descriptions=[]
                if using_readline:
                    # we drop completion cache because it contains
                    # table and column names which could have changed
                    # with last executed SQL
                    self._completion_cache=None
                    self._using_readline=True
                try:
                    command=self.getcompleteline()
                    if command is None:  # EOF
                        return
                    self.process_complete_line(command)
                except:
                    self._append_input_description()
                    try:
                        self.handle_exception()
                    except UnicodeDecodeError:
                        self.handle_exception()
        finally:
            if using_readline:
                readline.set_completer(old_completer)
                readline.set_history_length(256)
                readline.write_history_file(os.path.expanduser(self.history_file))

    def handle_exception(self):
        """Handles the current exception, printing a message to stderr as appropriate.
        It will reraise the exception if necessary (eg if bail is true)"""
        eclass,eval,etb=sys.exc_info()  # py2&3 compatible way of doing this
        if isinstance(eval, SystemExit):
            eval._handle_exception_saw_this=True
            raise

        self._out_colour()
        self.write(self.stderr, self.colour.error)

        if isinstance(eval, KeyboardInterrupt):
            self.handle_interrupt()
            text="Interrupted"
        else:
            text=str(eval)

        if not text.endswith("\n"):
            text=text+"\n"

        if len(self._input_descriptions):
            for i in range(len(self._input_descriptions)):
                if i==0:
                    pref="At "
                else:
                    pref=" "*i+"From "
                self.write(self.stderr, pref+self._input_descriptions[i]+"\n")

        self.write(self.stderr, text)
        if self.exceptions:
            stack=[]
            while etb:
                stack.append(etb.tb_frame)
                etb = etb.tb_next

            for frame in stack:
                self.write(self.stderr, "\nFrame %s in %s at line %d\n" %
                           (frame.f_code.co_name, frame.f_code.co_filename,
                            frame.f_lineno))
                vars=list(frame.f_locals.items())
                vars.sort()
                for k,v in vars:
                    try:
                        v=repr(v)[:80]
                    except:
                        v="<Unable to convert to string>"
                    self.write(self.stderr, "%10s = %s\n" % (k,v))
            self.write(self.stderr, "\n%s: %s\n" % (eclass, repr(eval)))

        self.write(self.stderr, self.colour.error_)

        eval._handle_exception_saw_this=True
        if self.bail:
            raise

    def process_sql(self, sql, bindings=None, internal=False, summary=None):
        """Processes SQL text consisting of one or more statements

        :param sql: SQL to execute

        :param bindings: bindings for the *sql*

        :param internal: If True then this is an internal execution
          (eg the .tables or .database command).  When executing
          internal sql timings are not shown nor is the SQL echoed.

        :param summary: If not None then should be a tuple of two
          items.  If the ``sql`` returns any data then the first item
          is printed before the first row, and the second item is
          printed after the last row.  An example usage is the .find
          command which shows table names.
        """
        cur=self.db.cursor()
        # we need to know when each new statement is executed
        state={'newsql': True, 'timing': None}

        def et(cur, sql, bindings):
            state['newsql']=True
            # if time reporting, do so now
            if not internal and self.timer:
                if state['timing']:
                    self.display_timing(state['timing'], self.get_resource_usage())
            # print statement if echo is on
            if not internal and self.echo:
                # ? should we strip leading and trailing whitespace? backslash quote stuff?
                if bindings:
                    self.write(self.stderr, "%s [%s]\n" % (sql, bindings))
                else:
                    self.write(self.stderr, sql+"\n")
            # save resource from begining of command (ie don't include echo time above)
            if not internal and self.timer:
                state['timing']=self.get_resource_usage()
            return True
        cur.setexectrace(et)
        # processing loop
        try:
            for row in cur.execute(sql, bindings):
                if state['newsql']:
                    # summary line?
                    if summary:
                        self._output_summary(summary[0])
                    # output a header always
                    cols=[h for h,d in cur.getdescription()]
                    self.output(True, cols)
                    state['newsql']=False
                self.output(False, row)
            if not state['newsql'] and summary:
                self._output_summary(summary[1])
        except:
            # If echo is on and the sql to execute is a syntax error
            # then the exec tracer won't have seen it so it won't be
            # printed and the user will be wondering exactly what sql
            # had the error.  We look in the traceback and deduce if
            # the error was happening in a prepare or not.  Also we
            # need to ignore the case where SQLITE_SCHEMA happened and
            # a reprepare is being done since the exec tracer will
            # have been called in that situation.
            if not internal and self.echo:
                tb=sys.exc_info()[2]
                last=None
                while tb:
                    last=tb.tb_frame
                    tb=tb.tb_next

                if last and last.f_code.co_name=="sqlite3_prepare" \
                   and last.f_code.co_filename.endswith("statementcache.c") \
                   and "sql" in last.f_locals:
                    self.write(self.stderr, last.f_locals["sql"]+"\n")
            raise

        if not internal and self.timer:
            self.display_timing(state['timing'], self.get_resource_usage())

    def process_command(self, cmd):
        """Processes a dot command.  It is split into parts using the
        `shlex.split
        <http://docs.python.org/library/shlex.html#shlex.split>`__
        function which is roughly the same method used by Unix/POSIX
        shells.
        """
        if self.echo:
            self.write(self.stderr, cmd+"\n")
        # broken with unicode on Python 2!!!
        if sys.version_info<(3,0):
            cmd=cmd.encode("utf8")
            cmd=[c.decode("utf8") for c in shlex.split(cmd)]
        else:
            cmd=shlex.split(cmd)
        assert cmd[0][0]=="."
        cmd[0]=cmd[0][1:]
        fn=getattr(self, "command_"+cmd[0], None)
        if not fn:
            raise self.Error("Unknown command \"%s\".  Enter \".help\" for help" % (cmd[0],))
        fn(cmd[1:])

    ###
    # Commands start here
    ###

    def _boolean_command(self, name, cmd):
        "Parse and verify boolean parameter"
        if len(cmd)!=1 or cmd[0].lower() not in ("on", "off"):
            raise self.Error(name+" expected ON or OFF")
        return cmd[0].lower()=="on"

    # Note that doc text is used for generating help output.

    def command_backup(self, cmd):
        """backup ?DB? FILE: Backup DB (default "main") to FILE

        Copies the contents of the current database to FILE
        overwriting whatever was in FILE.  If you have attached databases
        then you can specify their name instead of the default of "main".

        The backup is done at the page level - SQLite copies the pages
        as is.  There is no round trip through SQL code.
        """
        dbname="main"
        if len(cmd)==1:
            fname=cmd[0]
        elif len(cmd)==2:
            dbname=cmd[0]
            fname=cmd[1]
        else:
            raise self.Error("Backup takes one or two parameters")
        out=apsw.Connection(fname)
        b=out.backup("main", self.db, dbname)
        try:
            while not b.done:
                b.step()
        finally:
            b.finish()
            out.close()

    def command_bail(self, cmd):
        """bail ON|OFF: Stop after hitting an error (default OFF)

        If an error is encountered while processing commands or SQL
        then exit.  (Note this is different than SQLite shell which
        only exits for errors in SQL.)
        """
        self.bail=self._boolean_command("bail", cmd)

    def command_colour(self, cmd=[]):
        """colour SCHEME: Selects a colour scheme

        Residents of both countries that have not adopted the metric
        system may also spell this command without a 'u'.  If using a
        colour terminal in interactive mode then output is
        automatically coloured to make it more readable.  Use 'off' to
        turn off colour, and no name or 'default' for the default.
        """
        if len(cmd)>1:
            raise self.Error("Too many colour schemes")
        c=cmd and cmd[0] or "default"
        if c not in self._colours:
            raise self.Error("No such colour scheme: "+c)
        self.colour_scheme=c
        self._out_colour()

    command_color=command_colour

    def command_databases(self, cmd):
        """databases: Lists names and files of attached databases

        """
        if len(cmd):
            raise self.Error("databases command doesn't take any parameters")
        self.push_output()
        self.header=True
        self.output=self.output_column
        self.truncate=False
        self.widths=[3,15,58]
        try:
            self.process_sql("pragma database_list", internal=True)
        finally:
            self.pop_output()

    def command_dump(self, cmd):
        """dump ?TABLE? [TABLE...]: Dumps all or specified tables in SQL text format

        The table name is treated as like pattern so you can use % as
        a wildcard.  You can use dump to make a text based backup of
        the database.  It is also useful for comparing differences or
        making the data available to other databases.  Indices and
        triggers for the table(s) are also dumped.  Finally views
        matching the table pattern name are dumped (it isn't possible
        to work out which views access which table and views can
        access multiple tables anyway).

        Note that if you are dumping virtual tables such as used by
        the FTS3 module then they may use other tables to store
        information.  For example if you create a FTS3 table named
        *recipes* then it also creates *recipes_content*,
        *recipes_segdir* etc.  Consequently to dump this example
        correctly use::

           .dump recipes recipes_%

        If the database is empty or no tables/views match then there
        is no output.
        """
        # Simple tables are easy to dump.  More complicated is dealing
        # with virtual tables, foreign keys etc.

        # Lock the database while doing the dump so nothing changes
        # under our feet
        self.process_sql("BEGIN IMMEDIATE", internal=True)

        try:
            # first pass -see if virtual tables or foreign keys are in
            # use.  If they are we emit pragmas to deal with them, but
            # prefer not to emit them
            v={"virtuals": False,
               "foreigns": False}

            def check(name, sql):
                if name.lower().startswith("sqlite_"):
                    return False
                sql=sql.lower()
                if re.match(r"^\s*create\s+virtual\s+.*", sql):
                    v["virtuals"]=True
                # pragma table_info doesn't tell us if foreign keys
                # are involved so we guess if any the various strings are
                # in the sql somewhere
                if re.match(r".*\b(foreign\s*key|references)\b.*", sql):
                    v["foreigns"]=True
                return True

            if len(cmd)==0:
                cmd=["%"]

            tables=[]
            for pattern in cmd:
                for name,sql in self.db.cursor().execute("SELECT name,sql FROM sqlite_master "
                                                         "WHERE sql NOT NULL AND type IN ('table','view') "
                                                         "AND tbl_name LIKE ?1", (pattern,)):
                    if check(name, sql) and name not in tables:
                        tables.append(name)

            if not tables:
                return

            # will we need to analyze anything later?
            analyze_needed=[]
            for stat in self.db.cursor().execute("select name from sqlite_master where sql not null and type='table' and tbl_name like 'sqlite_stat%'"):
                for name in tables:
                    if len(self.db.cursor().execute("select * from "+self._fmt_sql_identifier(stat[0])+" WHERE tbl=?", (name,)).fetchall()):
                        if name not in analyze_needed:
                            analyze_needed.append(name)
            analyze_needed.sort()

            def blank():
                self.write(self.stdout, "\n")

            def comment(s):
                if isinstance(s, bytes):
                    s = s.decode('utf-8', 'replace')
                self.write(self.stdout, textwrap.fill(s, 78, initial_indent="-- ", subsequent_indent="-- ")+"\n")

            pats=", ".join([(x,"(All)")[x=="%"] for x in cmd])
            comment("SQLite dump (by APSW %s)" % (apsw.apswversion(),))
            comment("SQLite version " + apsw.sqlitelibversion())
            comment("Date: " +time.ctime())
            comment("Tables like: "+pats)
            comment("Database: "+self.db.filename)
            try:
                import getpass
                import socket
                comment("User: %s @ %s" % (getpass.getuser(), socket.gethostname()))
            except ImportError:
                pass
            blank()

            comment("The values of various per-database settings")
            comment("PRAGMA page_size="+str(self.db.cursor().execute("pragma page_size").fetchall()[0][0])+";\n")
            comment("PRAGMA encoding='"+self.db.cursor().execute("pragma encoding").fetchall()[0][0]+"';\n")
            vac={0: "NONE", 1: "FULL", 2: "INCREMENTAL"}
            vacvalue=self.db.cursor().execute("pragma auto_vacuum").fetchall()[0][0]
            comment("PRAGMA auto_vacuum="+vac.get(vacvalue, str(vacvalue))+";\n")
            comment("PRAGMA max_page_count="+str(self.db.cursor().execute("pragma max_page_count").fetchall()[0][0])+";\n")
            blank()

            # different python versions have different requirements
            # about specifying cmp to sort routine so we use this
            # portable workaround with a decorated list instead
            dectables=[(x.lower(), x) for x in tables]
            dectables.sort()
            tables=[y for x,y in dectables]

            virtuals=v["virtuals"]
            foreigns=v["foreigns"]

            if virtuals:
                comment("This pragma is needed to restore virtual tables")
                self.write(self.stdout, "PRAGMA writable_schema=ON;\n")
            if foreigns:
                comment("This pragma turns off checking of foreign keys "
                        "as tables would be inconsistent while restoring.  It was introduced "
                        "in SQLite 3.6.19.")
                self.write(self.stdout, "PRAGMA foreign_keys=OFF;\n")

            if virtuals or foreigns:
                blank()

            self.write(self.stdout, "BEGIN TRANSACTION;\n")
            blank()

            def sqldef(s):
                # return formatted sql watching out for embedded
                # comments at the end forcing trailing ; onto next
                # line https://sqlite.org/src/info/c04a8b8a4f
                if "--" in s.split("\n")[-1]:
                    nl="\n"
                else:
                    nl=""
                return s+nl+";\n"

            # do the table dumping loops
            oldtable=self._output_table
            try:
                self.push_output()
                self.output=self.output_insert
                # Dump the table
                for table in tables:
                    for sql in self.db.cursor().execute("SELECT sql FROM sqlite_master WHERE name=?1 AND type='table'", (table,)):
                        comment("Table  "+table)
                        # Special treatment for virtual tables - they
                        # get called back on drops and creates and
                        # could thwart us so we have to manipulate
                        # sqlite_master directly
                        if sql[0].lower().split()[:3]==["create", "virtual", "table"]:
                            self.write(self.stdout, "DELETE FROM sqlite_master WHERE name="+apsw.format_sql_value(table)+" AND type='table';\n")
                            self.write(self.stdout, "INSERT INTO sqlite_master(type,name,tbl_name,rootpage,sql) VALUES('table',%s,%s,0,%s);\n"
                                       % (apsw.format_sql_value(table), apsw.format_sql_value(table), apsw.format_sql_value(sql[0])))
                        else:
                            self.write(self.stdout, "DROP TABLE IF EXISTS "+self._fmt_sql_identifier(table)+";\n")
                            self.write(self.stdout, sqldef(sql[0]))
                            self._output_table=self._fmt_sql_identifier(table)
                            self.process_sql("select * from "+self._fmt_sql_identifier(table), internal=True)
                        # Now any indices or triggers
                        first=True
                        for name,sql in self.db.cursor().execute("SELECT name,sql FROM sqlite_master "
                                                                 "WHERE sql NOT NULL AND type IN ('index', 'trigger') "
                                                                 "AND tbl_name=?1 AND name NOT LIKE 'sqlite_%' "
                                                                 "ORDER BY lower(name)", (table,)):
                            if first:
                                comment("Triggers and indices on  "+table)
                                first=False
                            self.write(self.stdout, sqldef(sql))
                        blank()
                # Views done last.  They have to be done in the same order as they are in sqlite_master
                # as they could refer to each other
                first=True
                for name,sql in self.db.cursor().execute("SELECT name,sql FROM sqlite_master "
                                                         "WHERE sql NOT NULL AND type='view' "
                                                         "AND name IN ( "+",".join([apsw.format_sql_value(i) for i in tables])+
                                                         ") ORDER BY _ROWID_"):
                    if first:
                        comment("Views")
                        first=False
                    self.write(self.stdout, "DROP VIEW IF EXISTS %s;\n" % (self._fmt_sql_identifier(name),))
                    self.write(self.stdout, sqldef(sql))
                if not first:
                    blank()

                # sqlite sequence
                # does it exist
                if len(self.db.cursor().execute("select * from sqlite_master where name='sqlite_sequence'").fetchall()):
                    first=True
                    for t in tables:
                        v=self.db.cursor().execute("select seq from main.sqlite_sequence where name=?1", (t,)).fetchall()
                        if len(v):
                            assert len(v)==1
                            if first:
                                comment("For primary key autoincrements the next id "
                                        "to use is stored in sqlite_sequence")
                                first=False
                            self.write(self.stdout, 'DELETE FROM main.sqlite_sequence WHERE name=%s;\n' % (apsw.format_sql_value(t),))
                            self.write(self.stdout, 'INSERT INTO main.sqlite_sequence VALUES (%s, %s);\n' % (apsw.format_sql_value(t), v[0][0]))
                    if not first:
                        blank()
            finally:
                self.pop_output()
                self._output_table=oldtable

            # analyze
            if analyze_needed:
                comment("You had used the analyze command on these tables before.  Rerun for this new data.")
                for n in analyze_needed:
                    self.write(self.stdout, "ANALYZE "+self._fmt_sql_identifier(n)+";\n")
                blank()

            # user version pragma
            uv=self.db.cursor().execute("pragma user_version").fetchall()[0][0]
            if uv:
                comment("Your database may need this.  It is sometimes used to keep track of the schema version (eg Firefox does this).")
                comment("pragma user_version=%d;" % (uv,))
                blank()

            # Save it all
            self.write(self.stdout, "COMMIT TRANSACTION;\n")

            # cleanup pragmas
            if foreigns:
                blank()
                comment("Restoring foreign key checking back on.  Note that SQLite 3.6.19 is off by default")
                self.write(self.stdout, "PRAGMA foreign_keys=ON;\n")
            if virtuals:
                blank()
                comment("Restoring writable schema back to default")
                self.write(self.stdout, "PRAGMA writable_schema=OFF;\n")
                # schema reread
                blank()
                comment("We need to force SQLite to reread the schema because otherwise it doesn't know that "
                        "the virtual tables we inserted directly into sqlite_master exist.  See "
                        "last comments of https://sqlite.org/cvstrac/tktview?tn=3425")
                self.write(self.stdout, "BEGIN;\nCREATE TABLE no_such_table(x,y,z);\nROLLBACK;\n")

        finally:
            self.process_sql("END", internal=True)

    def command_echo(self, cmd):
        """echo ON|OFF: If ON then each SQL statement or command is printed before execution (default OFF)

        The SQL statement or command is sent to error output so that
        it is not intermingled with regular output.
        """
        self.echo=self._boolean_command("echo", cmd)

    def set_encoding(self, enc):
        """Saves *enc* as the default encoding, after verifying that
        it is valid.  You can also include :error to specify error
        handling - eg 'cp437:replace'

        Raises an exception on invalid encoding or error
        """
        enc=enc.split(":", 1)
        if len(enc)>1:
            enc, errors=enc
        else:
            enc=enc[0]
            errors=None
        try:
            codecs.lookup(enc)
        except LookupError:
            raise self.Error("No known encoding '%s'" % (enc,))
        try:
            if errors is not None:
                codecs.lookup_error(errors)
        except LookupError:
            raise self.Error("No known codec error handler '%s'" % (errors,))
        self.encoding=enc, errors

    def command_encoding(self, cmd):
        """encoding ENCODING: Set the encoding used for new files opened via .output and imports

        SQLite and APSW work internally using Unicode and characters.
        Files however are a sequence of bytes.  An encoding describes
        how to convert between bytes and characters.  The default
        encoding is utf8 and that is generally the best value to use
        when other programs give you a choice.

        You can also specify an error handler.  For example
        'cp437:replace' will use code page 437 and any Unicode
        codepoints not present in cp437 will be replaced (typically
        with something like a question mark).  Other error handlers
        include 'ignore', 'strict' (default) and 'xmlcharrefreplace'.

        For the default input/output/error streams on startup the
        shell defers to Python's detection of encoding.  For example
        on Windows it asks what code page is in use and on Unix it
        looks at the LC_CTYPE environment variable.  You can set the
        PYTHONIOENCODING environment variable to override this
        detection.

        This command affects files opened after setting the encoding
        as well as imports.

        See the online APSW documentation for more details.
        """
        if len(cmd)!=1:
            raise self.Error("Encoding takes one argument")
        self.set_encoding(cmd[0])

    def command_exceptions(self, cmd):
        """exceptions ON|OFF: If ON then detailed tracebacks are shown on exceptions (default OFF)

        Normally when an exception occurs the error string only is
        displayed.  However it is sometimes useful to get a full
        traceback.  An example would be when you are developing
        virtual tables and using the shell to exercise them.  In
        addition to displaying each stack frame, the local variables
        within each frame are also displayed.
        """
        self.exceptions=self._boolean_command("exceptions", cmd)

    def command_exit(self, cmd):
        """exit:Exit this program"""
        if len(cmd):
            raise self.Error("Exit doesn't take any parameters")
        sys.exit(0)

    def command_quit(self, cmd):
        """quit:Exit this program"""
        if len(cmd):
            raise self.Error("Quit doesn't take any parameters")
        sys.exit(0)

    def command_explain(self, cmd):
        """explain ON|OFF: Set output mode suitable for explain (default OFF)

        Explain shows the underlying SQLite virtual machine code for a
        statement.  You need to prefix the SQL with explain.  For example:

           explain select * from table;

        This output mode formats the explain output nicely.  If you do
        '.explain OFF' then the output mode and settings in place when
        you did '.explain ON' are restored.
        """
        if len(cmd)==0 or self._boolean_command("explain", cmd):
            self.push_output()
            self.header=True
            self.widths=[4,13,4,4,4,13,2,13]
            self.truncate=False
            self.output=self.output_column
        else:
            self.pop_output()

    def command_find(self, cmd):
        """find what ?TABLE?: Searches all columns of all tables for a value

        The find command helps you locate data across your database
        for example to find a string or any references to an id.

        You can specify a like pattern to limit the search to a subset
        of tables (eg specifying 'CUSTOMER%' for all tables beginning
        with CUSTOMER).

        The what value will be treated as a string and/or integer if
        possible.  If what contains % or _ then it is also treated as
        a like pattern.

        This command will take a long time to execute needing to read
        all of the relevant tables.
        """
        if len(cmd)<1 or len(cmd)>2:
            raise self.Error("At least one argument required and at most two accepted")
        tablefilter="%"
        if len(cmd)==2:
            tablefilter=cmd[1]
        querytemplate=[]
        queryparams=[]

        def qp():  # binding for current queryparams
            return "?"+str(len(queryparams))
        s=cmd[0]
        if '%' in s or '_' in s:
            queryparams.append(s)
            querytemplate.append("%s LIKE "+qp())
        queryparams.append(s)
        querytemplate.append("%s = "+qp())
        try:
            i=int(s)
            queryparams.append(i)
            querytemplate.append("%s = "+qp())
        except ValueError:
            pass
        querytemplate=" OR ".join(querytemplate)
        for (table,) in self.db.cursor().execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?1", (tablefilter,)):
            t=self._fmt_sql_identifier(table)
            query="SELECT * from %s WHERE " % (t,)
            colq=[]
            for _,column,_,_,_,_ in self.db.cursor().execute("pragma table_info(%s)" % (t,)):
                colq.append(querytemplate % ((self._fmt_sql_identifier(column),)*len(queryparams)))
            query=query+" OR ".join(colq)
            self.process_sql(query, queryparams, internal=True, summary=("Table "+table+"\n", "\n"))

    def command_header(self, cmd):
        """header(s) ON|OFF: Display the column names in output (default OFF)

        """
        self.header=self._boolean_command("header", cmd)

    command_headers=command_header

    _help_info=None

    def command_help(self, cmd):
        """help ?COMMAND?: Shows list of commands and their usage.  If COMMAND
        is specified then shows detail about that COMMAND.  ('.help all' will
        show detailed help about all commands.)
        """
        if not self._help_info:
            # buildup help database
            self._help_info={}
            for c in dir(self):
                if not c.startswith("command_"):
                    continue
                # help is 3 parts
                # - the syntax string (eg backup ?dbname? filename)
                # - the one liner description (eg saves database to filename)
                # - the multi-liner detailed description
                # We grab this from the doc string for the function in the form
                #   syntax: one liner\nmulti\nliner
                d=getattr(self, c).__doc__
                assert d, c+" command must have documentation"
                c=c[len("command_"):]
                if c in ("headers", "color"):
                    continue
                while d[0]=="\n":
                    d=d[1:]
                parts=d.split("\n", 1)
                firstline=parts[0].strip().split(":", 1)
                assert len(firstline)==2, c+" command must have usage: description doc"
                if len(parts)==1 or len(parts[1].strip())==0:  # work around textwrap bug
                    multi=""
                else:
                    multi=textwrap.dedent(parts[1])
                if c=="mode":
                    if not self._output_modes:
                        self._cache_output_modes()
                    firstline[1]=firstline[1]+" "+" ".join(self._output_modes)
                    multi=multi+"\n\n"+"\n\n".join(self._output_modes_detail)
                if c=="colour":
                    colours=list(self._colours.keys())
                    colours.sort()
                    firstline[1]=firstline[1]+" from "+", ".join(colours)
                if len(multi.strip())==0:  # All whitespace
                    multi=None
                else:
                    multi=multi.strip("\n")
                    # we need to keep \n\n as a newline but turn all others into spaces
                    multi=multi.replace("\n\n", "\x00")
                    multi=multi.replace("\n", " ")
                    multi=multi.replace("\x00", "\n\n")
                    multi=multi.split("\n\n")
                self._help_info[c]=('.'+firstline[0].strip(), firstline[1].strip(), multi)

        self.write(self.stderr, "\n")

        tw=self._terminal_width()
        if tw<32:
            tw=32
        if len(cmd)==0:
            commands=list(self._help_info.keys())
            commands.sort()
            w=0
            for command in commands:
                if len(self._help_info[command][0])>w:
                    w=len(self._help_info[command][0])
            out=[]
            for command in commands:
                hi=self._help_info[command]
                # usage string
                out.append(hi[0])
                # space padding (including 2 for between columns)
                out.append(" "*(2+w-len(hi[0])))
                # usage message wrapped if need be
                out.append(("\n"+" "*(2+w)).join(textwrap.wrap(hi[1], tw-w-2)))
                # newline
                out.append("\n")
            self.write(self.stderr, "".join(out))
        else:
            if cmd[0]=="all":
                cmd=list(self._help_info.keys())
                cmd.sort()
            w=0
            for command in self._help_info:
                if len(self._help_info[command][0])>w:
                    w=len(self._help_info[command][0])

            for command in cmd:
                if command=="headers":
                    command="header"
                if command not in self._help_info:
                    raise self.Error("No such command \"%s\"" % (command,))
                out=[]
                hi=self._help_info[command]
                # usage string
                out.append(hi[0])
                # space padding (2)
                out.append(" "*(2+w-len(hi[0])))
                # usage message wrapped if need be
                out.append(("\n"+" "*(2+w)).join(textwrap.wrap(hi[1], tw-w-2))+"\n")
                if hi[2]:
                    # newlines
                    out.append("\n")
                    # detailed message
                    for i,para in enumerate(hi[2]):
                        out.append(textwrap.fill(para, tw)+"\n")
                        if i<len(hi[2])-1:
                            out.append("\n")
                # if not first one then print separator header
                if command!=cmd[0]:
                    self.write(self.stderr, "\n"+"="*tw+"\n")
                self.write(self.stderr, "".join(out))
        self.write(self.stderr, "\n")

    def command_import(self, cmd):
        """import FILE TABLE: Imports separated data from FILE into TABLE

        Reads data from the file into the named table using the
        current separator and encoding.  For example if the separator
        is currently a comma then the file should be CSV (comma
        separated values).

        All values read in are supplied to SQLite as strings.  If you
        want SQLite to treat them as other types then declare your
        columns appropriately.  For example declaring a column 'REAL'
        will result in the values being stored as floating point if
        they can be safely converted.  See this page for more details:

          https://sqlite.org/datatype3.html

        Another alternative is to create a tempory table, insert the
        values into that and then use casting.

          CREATE TEMPORARY TABLE import(a,b,c);

          .import filename import

          CREATE TABLE final AS SELECT cast(a as BLOB), cast(b as INTEGER), cast(c as CHAR) from import;

          DROP TABLE import;

        You can also get more sophisticated using the SQL CASE
        operator.  For example this will turn zero length strings into
        null:

          SELECT CASE col WHEN '' THEN null ELSE col END FROM ...
        """
        if len(cmd)!=2:
            raise self.Error("import takes two parameters")

        try:
            final=None
            # start transaction so database can't be changed
            # underneath us
            self.db.cursor().execute("BEGIN IMMEDIATE")
            final="ROLLBACK"

            # how many columns?
            ncols=len(self.db.cursor().execute("pragma table_info("+self._fmt_sql_identifier(cmd[1])+")").fetchall())
            if ncols<1:
                raise self.Error("No such table '%s'" % (cmd[1],))

            cur=self.db.cursor()
            sql="insert into %s values(%s)" % (self._fmt_sql_identifier(cmd[1]), ",".join("?"*ncols))

            kwargs={}
            if self.separator==",":
                kwargs["dialect"]="excel"
            elif self.separator=="\t":
                kwargs["dialect"]="excel-tab"
            else:
                kwargs["quoting"]=csv.QUOTE_NONE
                kwargs["delimiter"]=self.separator
                kwargs["doublequote"]=False
                kwargs["quotechar"]="\x00"
            row=1
            for line in self._csvin_wrapper(cmd[0], kwargs):
                if len(line)!=ncols:
                    raise self.Error("row %d has %d columns but should have %d" % (row, len(line), ncols))
                try:
                    cur.execute(sql, line)
                except:
                    self.write(self.stderr, "Error inserting row %d" % (row,))
                    raise
                row+=1
            self.db.cursor().execute("COMMIT")

        except:
            if final:
                self.db.cursor().execute(final)
            raise

    def _csvin_wrapper(self, filename, dialect):
        # Returns a csv reader that works around python bugs and uses
        # dialect dict to configure reader

        # Very easy for python 3
        if sys.version_info>=(3,0):
            thefile=codecs.open(filename, "r", self.encoding[0])
            for line in csv.reader(thefile, **dialect.copy()):
                yield line
            thefile.close()
            return

        ###
        # csv module is not good at unicode so we have to
        # indirect unless utf8 is in use
        ###
        if self.encoding[0].lower()=="utf8":  # no need for tempfile
            thefile=open(filename, "rb")
        else:
            import tempfile
            thefile=tempfile.TemporaryFile(prefix="apsw_import")
            thefile.write(codecs.open(filename, "r", self.encoding[0]).read().encode("utf8"))
            # move back to beginning
            thefile.seek(0,0)

        # Ensure all values are utf8 not unicode
        for k,v in dialect.items():
            if isinstance(v, unicode):
                dialect[k]=v.encode("utf8")
        for line in csv.reader(thefile, **dialect):
            # back to unicode again
            yield [x.decode("utf8") for x in line]
        thefile.close()

    def command_autoimport(self, cmd):
        """autoimport FILENAME ?TABLE?: Imports filename creating a table and automatically working out separators and data types (alternative to .import command)

        The import command requires that you precisely pre-setup the
        table and schema, and set the data separators (eg commas or
        tabs).  In many cases this information can be automatically
        deduced from the file contents which is what this command
        does.  There must be at least two columns and two rows.

        If the table is not specified then the basename of the file
        will be used.

        Additionally the type of the contents of each column is also
        deduced - for example if it is a number or date.  Empty values
        are turned into nulls.  Dates are normalized into YYYY-MM-DD
        format and DateTime are normalized into ISO8601 format to
        allow easy sorting and searching.  4 digit years must be used
        to detect dates.  US (swapped day and month) versus rest of
        the world is also detected providing there is at least one
        value that resolves the ambiguity.

        Care is taken to ensure that columns looking like numbers are
        only treated as numbers if they do not have unnecessary
        leading zeroes or plus signs.  This is to avoid treating phone
        numbers and similar number like strings as integers.

        This command can take quite some time on large files as they
        are effectively imported twice.  The first time is to
        determine the format and the types for each column while the
        second pass actually imports the data.
        """
        if len(cmd)<1 or len(cmd)>2:
            raise self.Error("Expected one or two parameters")
        if not os.path.exists(cmd[0]):
            raise self.Error("File \"%s\" does not exist" % (cmd[0],))
        if len(cmd)==2:
            tablename=cmd[1]
        else:
            tablename=None
        try:
            final=None
            c=self.db.cursor()
            c.execute("BEGIN IMMEDIATE")
            final="ROLLBACK"

            if not tablename:
                tablename=os.path.splitext(os.path.basename(cmd[0]))[0]

            if c.execute("pragma table_info(%s)" % (self._fmt_sql_identifier(tablename),)).fetchall():
                raise self.Error("Table \"%s\" already exists" % (tablename,))

            # The types we support deducing
            def DateUS(v):  # US formatted date with wrong ordering of day and month
                return DateWorld(v, switchdm=True)

            def DateWorld(v, switchdm=False):  # Sensibly formatted date as used anywhere else in the world
                y,m,d=self._getdate(v)
                if switchdm:
                    m,d=d,m
                if m<1 or m>12 or d<1 or d>31:
                    raise ValueError
                return "%d-%02d-%02d" % (y,m,d)

            def DateTimeUS(v):  # US date and time
                return DateTimeWorld(v, switchdm=True)

            def DateTimeWorld(v, switchdm=False):  # Sensible date and time
                y,m,d,h,M,s=self._getdatetime(v)
                if switchdm:
                    m,d=d,m
                if m<1 or m>12 or d<1 or d>31 or h<0 or h>23 or M<0 or M>59 or s<0 or s>65:
                    raise ValueError
                return "%d-%02d-%02dT%02d:%02d:%02d" % (y,m,d,h,M,s)

            def Number(v):  # we really don't want phone numbers etc to match
                # Python's float & int constructors allow whitespace which we don't
                if re.search(r"\s", v):
                    raise ValueError
                if v=="0":
                    return 0
                if v[0]=="+":  # idd prefix
                    raise ValueError
                if re.match("^[0-9]+$", v):
                    if v[0]=="0":
                        raise ValueError  # also a phone number
                    return int(v)
                if v[0]=="0" and not v.startswith("0."):  # deceptive not a number
                    raise ValueError
                return float(v)

            # Work out the file format
            formats=[
                {"dialect": "excel"},
                {"dialect": "excel-tab"}]
            seps=["|", ";", ":"]
            if self.separator not in seps:
                seps.append(self.separator)
            for sep in seps:
                formats.append(
                    {"quoting": csv.QUOTE_NONE,
                     "delimiter": sep,
                     "doublequote": False,
                     "quotechar": "\x00"}
                    )
            possibles=[]
            errors=[]
            encodingissue=False
            # format is copy() on every use.  This appears bizarre and
            # unnecessary.  However Python 2.3 and 2.4 somehow manage
            # to empty it if not copied.
            for format in formats:
                ncols=-1
                lines=0
                try:
                    for line in self._csvin_wrapper(cmd[0], format.copy()):
                        if lines==0:
                            lines=1
                            ncols=len(line)
                            # data type guess setup
                            datas=[]
                            for i in range(ncols):
                                datas.append([DateUS, DateWorld, DateTimeUS, DateTimeWorld, Number])
                            allblanks=[True]*ncols
                            continue
                        if len(line)!=ncols:
                            raise ValueError("Expected %d columns - got %d" % (ncols, len(line)))
                        lines+=1
                        for i in range(ncols):
                            if not line[i]:
                                continue
                            allblanks[i]=False
                            if not datas[i]:
                                continue
                            # remove datas that give ValueError
                            d=[]
                            for dd in datas[i]:
                                try:
                                    dd(line[i])
                                    d.append(dd)
                                except ValueError:
                                    pass
                            datas[i]=d
                    if ncols>1 and lines>1:
                        # if a particular column was allblank then clear datas for it
                        for i in range(ncols):
                            if allblanks[i]:
                                datas[i]=[]
                        possibles.append((format.copy(), ncols, lines, datas))
                except UnicodeDecodeError:
                    encodingissue=True
                except:
                    s=str(sys.exc_info()[1])
                    if s not in errors:
                        errors.append(s)

            if len(possibles)==0:
                if encodingissue:
                    raise self.Error("The file is probably not in the current encoding \"%s\" and didn't match a known file format" % (self.encoding[0],))
                v="File doesn't appear to match a known type."
                if len(errors):
                    v+="  Errors reported:\n"+"\n".join(["  "+e for e in errors])
                raise self.Error(v)
            if len(possibles)>1:
                raise self.Error("File matches more than one type!")
            format, ncols, lines, datas=possibles[0]
            fmt=format.get("dialect", None)
            if fmt is None:
                fmt="(delimited by \"%s\")" % (format["delimiter"],)
            self.write(self.stdout, "Detected Format %s  Columns %d  Rows %d\n" % (fmt, ncols, lines))
            # Header row
            reader=self._csvin_wrapper(cmd[0], format)
            for header in reader:
                break
            # Check schema
            identity=lambda x:x
            for i in range(ncols):
                if len(datas[i])>1:
                    raise self.Error("Column #%d \"%s\" has ambiguous data format - %s" % (i+1, header[i], ", ".join([dl.__name__ for dl in datas[i]])))
                if datas[i]:
                    datas[i]=datas[i][0]
                else:
                    datas[i]=identity
            # Make the table
            sql="CREATE TABLE %s(%s)" % (self._fmt_sql_identifier(tablename), ", ".join([self._fmt_sql_identifier(h) for h in header]))
            c.execute(sql)
            # prep work for each row
            sql="INSERT INTO %s VALUES(%s)" % (self._fmt_sql_identifier(tablename), ",".join(["?"]*ncols))
            for line in reader:
                vals=[]
                for i in range(ncols):
                    l=line[i]
                    if not l:
                        vals.append(None)
                    else:
                        vals.append(datas[i](l))
                c.execute(sql, vals)

            c.execute("COMMIT")
            self.write(self.stdout, "Auto-import into table \"%s\" complete\n" % (tablename,))
        except:
            if final:
                self.db.cursor().execute(final)
            raise

    def _getdate(self, v):
        # Returns a tuple of 3 items y,m,d from string v
        m=re.match(r"^([0-9]+)[^0-9]([0-9]+)[^0-9]([0-9]+)$", v)
        if not m:
            raise ValueError
        y,m,d=int(m.group(1)), int(m.group(2)), int(m.group(3))
        if d>1000:  # swap order
            y,m,d=d,m,y
        if y<1000 or y>9999:
            raise ValueError
        return y,m,d

    def _getdatetime(self, v):
        # must be at least HH:MM
        m=re.match(r"^([0-9]+)[^0-9]([0-9]+)[^0-9]([0-9]+)[^0-9]+([0-9]+)[^0-9]([0-9]+)([^0-9]([0-9]+))?$", v)
        if not m:
            raise ValueError
        items=list(m.group(1,2,3,4,5,7))
        for i in range(len(items)):
            if items[i] is None:
                items[i]=0
        items=[int(i) for i in items]
        if items[2]>1000:
            items=[items[2], items[1], items[0]]+items[3:]
        if items[0]<1000 or items[0]>9999:
            raise ValueError
        return items

    def command_indices(self, cmd):
        """indices TABLE: Lists all indices on table TABLE

        """
        if len(cmd)!=1:
            raise self.Error("indices takes one table name")
        self.push_output()
        self.header=False
        self.output=self.output_list
        try:
            self.process_sql("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name LIKE ?1 "
                             "UNION ALL SELECT name FROM sqlite_temp_master WHERE type='index' AND tbl_name LIKE "
                             "?1 ORDER by name", cmd, internal=True)
        finally:
            self.pop_output()

    def command_load(self, cmd):
        """load FILE ?ENTRY?: Loads a SQLite extension library

        Note: Extension loading may not be enabled in the SQLite
        library version you are using.

        Extensions are an easy way to add new functions and
        functionality.  For a useful extension look at the bottom of
        https://sqlite.org/contrib

        By default sqlite3_extension_init is called in the library but
        you can specify an alternate entry point.

        If you get an error about the extension not being found you
        may need to explicitly specify the directory.  For example if
        it is in the current directory then use:

          .load ./extension.so
        """
        if len(cmd)<1 or len(cmd)>2:
            raise self.Error("load takes one or two parameters")
        try:
            self.db.enableloadextension(True)
        except:
            raise self.Error("Extension loading is not supported")

        self.db.loadextension(*cmd)

    _output_modes=None

    def command_mode(self, cmd):
        """mode MODE ?TABLE?: Sets output mode to one of"""
        if len(cmd) in (1,2):
            w=cmd[0]
            if w=="tabs":
                w="list"
            m=getattr(self, "output_"+w, None)
            if w!="insert":
                if len(cmd)==2:
                    raise self.Error("Output mode %s doesn't take parameters" % (cmd[0]))
            if m:
                self.output=m
                # set some defaults
                self.truncate=True
                if cmd[0]=="csv":
                    self.separator=","
                elif cmd[0]=="tabs":
                    self.separator="\t"
                else:
                    pass
                    # self.separator=self._output_stack[0]["separator"]
                if w=="insert":
                    if len(cmd)==2:
                        self._output_table=cmd[1]
                    else:
                        self._output_table="table"
                    self._output_table=self._fmt_sql_identifier(self._output_table)
                return
        if not self._output_modes:
            self._cache_output_modes()
        raise self.Error("Expected a valid output mode: "+", ".join(self._output_modes))

    # needed so command completion and help can use it
    def _cache_output_modes(self):
        modes=[m[len("output_"):] for m in dir(self) if m.startswith("output_")]
        modes.append("tabs")
        modes.sort()
        self._output_modes=modes

        detail=[]

        for m in modes:
            if m=='tabs':
                continue
            d=getattr(self, "output_"+m).__doc__
            assert d, "output mode "+m+" needs doc"
            d=d.replace("\n", " ").strip()
            while "  " in d:
                d=d.replace("  ", " ")
            detail.append(m+": "+d)
        self._output_modes_detail=detail

    def command_nullvalue(self, cmd):
        """nullvalue STRING: Print STRING in place of null values

        This affects textual output modes like column and list and
        sets how SQL null values are shown.  The default is a zero
        length string.  Insert mode and dumps are not affected by this
        setting.  You can use double quotes to supply a zero length
        string.  For example:

          .nullvalue ""         # the default
          .nullvalue <NULL>     # rather obvious
          .nullvalue " \\t "     # A tab surrounded by spaces
        """
        if len(cmd)!=1:
            raise self.Error("nullvalue takes exactly one parameter")
        self.nullvalue=self.fixup_backslashes(cmd[0])

    def command_output(self, cmd):
        """output FILENAME: Send output to FILENAME (or stdout)

        If the FILENAME is stdout then output is sent to standard
        output from when the shell was started.  The file is opened
        using the current encoding (change with .encoding command).
        """
        # Flush everything
        self.stdout.flush()
        self.stderr.flush()
        if hasattr(self.stdin, "flush"):
            try:
                self.stdin.flush()
            except IOError:  # see issue 117
                pass

        # we will also close stdout but only do so once we have a
        # replacement so that stdout is always valid

        if len(cmd)!=1:
            raise self.Error("You must specify a filename")

        try:
            fname=cmd[0]
            if fname=="stdout":
                old=None
                if self.stdout!=self._original_stdout:
                    old=self.stdout
                self.stdout=self._original_stdout
                if old is not None:  # done here in case close raises exception
                    old.close()
                return

            newf=codecs.open(fname, "w", self.encoding[0], self.encoding[1])
            old=None
            if self.stdout!=self._original_stdout:
                old=self.stdout
            self.stdout=newf
            if old is not None:
                old.close()
        finally:
            self._out_colour()

    def command_print(self, cmd):
        """print STRING: print the literal STRING

        If more than one argument is supplied then they are printed
        space separated.  You can use backslash escapes such as \\n
        and \\t.
        """
        self.write(self.stdout, " ".join([self.fixup_backslashes(i) for i in cmd])+"\n")

    def command_prompt(self, cmd):
        """prompt MAIN ?CONTINUE?: Changes the prompts for first line and continuation lines

        The default is to print 'sqlite> ' for the main prompt where
        you can enter a dot command or a SQL statement.  If the SQL
        statement is complete (eg not ; terminated) then you are
        prompted for more using the continuation prompt which defaults
        to ' ..> '.  Example:

          .prompt "Yes, Master> " "More, Master> "

        You can use backslash escapes such as \\n and \\t.
        """
        if len(cmd)<1 or len(cmd)>2:
            raise self.Error("prompt takes one or two arguments")
        self.prompt=self.fixup_backslashes(cmd[0])
        if len(cmd)==2:
            self.moreprompt=self.fixup_backslashes(cmd[1])

    def command_read(self, cmd):
        """read FILENAME: Processes SQL and commands in FILENAME (or Python if FILENAME ends with .py)

        Treats the specified file as input (a mixture or SQL and/or
        dot commands).  If the filename ends in .py then it is treated
        as Python code instead.

        For Python code the symbol 'shell' refers to the instance of
        the shell and 'apsw' is the apsw module.
        """
        if len(cmd)!=1:
            raise self.Error("read takes a single filename")
        if cmd[0].lower().endswith(".py"):
            g={}
            g.update({'apsw': apsw, 'shell': self})
            if sys.version_info<(3,0):
                execfile(cmd[0], g, g)
            else:
                # compile step is needed to associate name with code
                exec(compile(open(cmd[0]).read(), cmd[0], 'exec'), g, g)
        else:
            f=codecs.open(cmd[0], "rU", self.encoding[0])
            try:
                try:
                    self.push_input()
                    self.stdin=f
                    self.interactive=False
                    self.input_line_number=0
                    while True:
                        line=self.getcompleteline()
                        if line is None:
                            break
                        self.process_complete_line(line)
                except:
                    eval=sys.exc_info()[1]
                    if not isinstance(eval, SystemExit):
                        self._append_input_description()
                    raise

            finally:
                self.pop_input()
                f.close()

    def command_restore(self, cmd):
        """restore ?DB? FILE: Restore database from FILE into DB (default "main")

        Copies the contents of FILE to the current database (default "main").
        The backup is done at the page level - SQLite copies the pages as
        is.  There is no round trip through SQL code.
        """
        dbname="main"
        if len(cmd)==1:
            fname=cmd[0]
        elif len(cmd)==2:
            dbname=cmd[0]
            fname=cmd[1]
        else:
            raise self.Error("Restore takes one or two parameters")
        input=apsw.Connection(fname)
        b=self.db.backup(dbname, input, "main")
        try:
            while not b.done:
                b.step()
        finally:
            b.finish()
            input.close()

    def command_schema(self, cmd):
        """schema ?TABLE? [TABLE...]: Shows SQL for table

        If you give one or more tables then their schema is listed
        (including indices).  If you don't specify any then all
        schemas are listed. TABLE is a like pattern so you can % for
        wildcards.
        """
        self.push_output()
        self.output=self.output_list
        self.header=False
        try:
            if len(cmd)==0:
                cmd=['%']
            for n in cmd:
                self.process_sql("SELECT sql||';' FROM "
                                 "(SELECT sql sql, type type, tbl_name tbl_name, name name "
                                 "FROM sqlite_master UNION ALL "
                                 "SELECT sql, type, tbl_name, name FROM sqlite_temp_master) "
                                 "WHERE tbl_name LIKE ?1 AND type!='meta' AND sql NOTNULL AND name NOT LIKE 'sqlite_%' "
                                 "ORDER BY substr(type,2,1), name", (n,), internal=True)
        finally:
            self.pop_output()

    def command_separator(self, cmd):
        """separator STRING: Change separator for output mode and .import

        You can use quotes and backslashes.  For example to set the
        separator to space tab space you can use:

          .separator " \\t "

        The setting is automatically changed when you switch to csv or
        tabs output mode.  You should also set it before doing an
        import (ie , for CSV and \\t for TSV).
        """
        if len(cmd)!=1:
            raise self.Error("separator takes exactly one parameter")
        self.separator=self.fixup_backslashes(cmd[0])

    _shows=("echo", "explain", "headers", "mode", "nullvalue", "output", "separator", "width", "exceptions", "encoding")

    def command_show(self, cmd):
        """show: Show the current values for various settings."""
        if len(cmd)>1:
            raise self.Error("show takes at most one parameter")
        if len(cmd):
            what=cmd[0]
            if what not in self._shows:
                raise self.Error("Unknown show: '%s'" % (what,))
        else:
            what=None

        outs=[]
        for i in self._shows:
            k=i
            if what and i!=what:
                continue
            # boolean settings
            if i in ("echo", "headers", "exceptions"):
                if i=="headers":
                    i="header"
                v="off"
                if getattr(self, i):
                    v="on"
            elif i=="explain":
                # we cheat by looking at truncate setting!
                v="on"
                if self.truncate:
                    v="off"
            elif i in ("nullvalue", "separator"):
                v=self._fmt_c_string(getattr(self, i))
            elif i=="mode":
                if not self._output_modes:
                    self._cache_output_modes()
                for v in self._output_modes:
                    if self.output==getattr(self, "output_"+v):
                        break
                else:
                    assert False, "Bug: didn't find output mode"
            elif i=="output":
                if self.stdout is self._original_stdout:
                    v="stdout"
                else:
                    v=getattr(self.stdout, "name", "<unknown stdout>")
            elif i=="width":
                v=" ".join(["%d"%(i,) for i in self.widths])
            elif i=="encoding":
                v=self.encoding[0]
                if self.encoding[1]:
                    v+=" (Errors "+self.encoding[1]+")"
            else:
                assert False, "Bug: unknown show handling"
            outs.append((k,v))

        # find width of k column
        l=0
        for k,v in outs:
            if len(k)>l:
                l=len(k)

        for k,v in outs:
            self.write(self.stderr, "%*.*s: %s\n" % (l,l, k, v))

    def command_tables(self, cmd):
        """tables ?PATTERN?: Lists names of tables matching LIKE pattern

        This also returns views.
        """
        self.push_output()
        self.output=self.output_list
        self.header=False
        try:
            if len(cmd)==0:
                cmd=['%']

            # The SQLite shell code filters out sqlite_ prefixes if
            # you specified an argument else leaves them in.  It also
            # has a hand coded output mode that does space separation
            # plus wrapping at 80 columns.
            for n in cmd:
                self.process_sql("SELECT name FROM sqlite_master "
                                 "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' "
                                 "AND name like ?1 "
                                 "UNION ALL "
                                 "SELECT name FROM sqlite_temp_master "
                                 "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' "
                                 "ORDER BY 1", (n,), internal=True)
        finally:
            self.pop_output()

    def command_timeout(self, cmd):
        """timeout MS: Try opening locked tables for MS milliseconds

        If a database is locked by another process SQLite will keep
        retrying.  This sets how many thousandths of a second it will
        keep trying for.  If you supply zero or a negative number then
        all busy handlers are disabled.
        """
        if len(cmd)!=1:
            raise self.Error("timeout takes a number")
        try:
            t=int(cmd[0])
        except:
            raise self.Error("%s is not a number" % (cmd[0],))
        self.db.setbusytimeout(t)

    def command_timer(self, cmd):
        """timer ON|OFF: Control printing of time and resource usage after each query

        The values displayed are in seconds when shown as floating
        point or an absolute count.  Only items that have changed
        since starting the query are shown.  On non-Windows platforms
        considerably more information can be shown.
        """
        if self._boolean_command("timer", cmd):
            try:
                self.get_resource_usage()
            except:
                raise self.Error("Timing not supported by this Python version/platform")
            self.timer=True
        else:
            self.timer=False

    def command_width(self, cmd):
        """width NUM NUM ...: Set the column widths for "column" mode

        In "column" output mode, each column is a fixed width with values truncated to
        fit.  Specify new widths using this command.  Use a negative number
        to right justify and zero for default column width.
        """
        if len(cmd)==0:
            raise self.Error("You need to specify some widths!")
        w=[]
        for i in cmd:
            try:
                w.append(int(i))
            except:
                raise self.Error("'%s' is not a valid number" % (i,))
        self.widths=w

    def _terminal_width(self):
        """Works out the terminal width which is used for word wrapping
        some output (eg .help)"""
        try:
            if sys.platform=="win32":
                import ctypes, struct
                h=ctypes.windll.kernel32.GetStdHandle(-12)  # -12 is stderr
                buf=ctypes.create_string_buffer(22)
                if ctypes.windll.kernel32.GetConsoleScreenBufferInfo(h, buf):
                    _,_,_,_,_,left,top,right,bottom,_,_=struct.unpack("hhhhHhhhhhh", buf.raw)
                    return right-left
                raise Exception()
            else:
                # posix
                import struct, fcntl, termios
                s=struct.pack('HHHH', 0,0,0,0)
                x=fcntl.ioctl(2, termios.TIOCGWINSZ, s)
                return struct.unpack('HHHH', x)[1]
        except:
            try:
                v=int(os.getenv("COLUMNS"))
                if v<10:
                    return 80
                return v
            except:
                return 80

    def push_output(self):
        """Saves the current output settings onto a stack.  See
        :meth:`pop_output` for more details as to why you would use
        this."""
        o={}
        for k in "separator", "header", "nullvalue", "output", "widths", "truncate":
            o[k]=getattr(self, k)
        self._output_stack.append(o)

    def pop_output(self):
        """Restores most recently pushed output.  There are many
        output parameters such as nullvalue, mode
        (list/tcl/html/insert etc), column widths, header etc.  If you
        temporarily need to change some settings then
        :meth:`push_output`, change the settings and then pop the old
        ones back.

        A simple example is implementing a command like .dump.  Push
        the current output, change the mode to insert so we get SQL
        inserts printed and then pop to go back to what was there
        before.

        """
        # first item should always be present
        assert len(self._output_stack)
        if len(self._output_stack)==1:
            o=self._output_stack[0]
        else:
            o=self._output_stack.pop()
        for k,v in o.items():
            setattr(self,k,v)

    def _append_input_description(self):
        """When displaying an error in :meth:`handle_exception` we
        want to give context such as when the commands being executed
        came from a .read command (which in turn could execute another
        .read).
        """
        if self.interactive:
            return
        res=[]
        res.append("Line %d" % (self.input_line_number,))
        res.append(": "+getattr(self.stdin, "name", "<stdin>"))
        self._input_descriptions.append(" ".join(res))

    def fixup_backslashes(self, s):
        """Implements the various backlash sequences in s such as
        turning backslash t into a tab.

        This function is needed because shlex does not do it for us.
        """
        if "\\" not in s:
            return s
        # See the resolve_backslashes function in SQLite shell source
        res=[]
        i=0
        while i<len(s):
            if s[i]!="\\":
                res.append(s[i])
                i+=1
                continue
            i+=1
            if i>=len(s):
                raise self.Error("Backslash with nothing following")
            c=s[i]
            res.append({
                "\\": "\\",
                "r": "\r",
                "n": "\n",
                "t": "\t"
                }.get(c, None))
            i+=1  # advance again
            if res[-1] is None:
                raise self.Error("Unknown backslash sequence \\"+c)
        return "".join(res)

    if sys.version_info<(3,0):
        def write(self, dest, text):
            """Writes text to dest.  dest will typically be one of self.stdout or self.stderr."""
            # ensure text is unicode to catch codeset issues here
            if type(text)!=unicode:
                text=unicode(text)
            try:
                dest.write(text)
            except UnicodeEncodeError:
                ev=sys.exc_info()[1]
                # See issue108 and try to work around it
                if ev.args[0]=="ascii" and dest.encoding and ev.args[0]!=dest.encoding and hasattr(dest, "fileno") and \
                   isinstance(dest.fileno(), int) and dest.fileno()>=0:
                    args=[dest.encoding,]
                    if dest.errors:
                        args.append(dest.errors)
                    dest.write(text.encode(*args))
                else:
                    raise

        _raw_input=raw_input
    else:
        def write(self, dest, text):
            "Writes text to dest.  dest will typically be one of self.stdout or self.stderr."
            dest.write(text)
        _raw_input=input

    def getline(self, prompt=""):
        """Returns a single line of input (may be incomplete SQL) from self.stdin.

        If EOF is reached then return None.  Do not include trailing
        newline in return.
        """
        self.stdout.flush()
        self.stderr.flush()
        try:
            if self.interactive:
                if self.stdin is sys.stdin:
                    c=self.colour.prompt, self.colour.prompt_
                    if self._using_readline and sys.platform!="win32":
                        # these are needed so that readline knows they are non-printing characters
                        c="\x01"+c[0]+"\x02", "\x01"+c[1]+"\x02",
                    line=self._raw_input(c[0]+prompt+c[1])+"\n"  # raw_input excludes newline
                else:
                    self.write(self.stdout, prompt)
                    line=self.stdin.readline()  # includes newline unless last line of file doesn't have one
            else:
                line=self.stdin.readline()  # includes newline unless last line of file doesn't have one
            self.input_line_number+=1
            if sys.version_info<(3,0):
                if type(line)!=unicode:
                    enc=getattr(self.stdin, "encoding", self.encoding[0])
                    if not enc:
                        enc=self.encoding[0]
                    line=line.decode(enc)
        except EOFError:
            return None
        if len(line)==0:  # always a \n on the end normally so this is EOF
            return None
        if line[-1]=="\n":
            line=line[:-1]
        return line

    def getcompleteline(self):
        """Returns a complete input.

        For dot commands it will be one line.  For SQL statements it
        will be as many as is necessary to have a
        :meth:`~apsw.complete` statement (ie semicolon terminated).
        Returns None on end of file."""
        try:
            self._completion_first=True
            command=self.getline(self.prompt)
            if command is None:
                return None
            if len(command.strip())==0:
                return ""
            if command[0]=="?":
                command=".help "+command[1:]
            # incomplete SQL?
            while command[0]!="." and not apsw.complete(command):
                self._completion_first=False
                line=self.getline(self.moreprompt)
                if line is None:  # unexpected eof
                    raise self.Error("Incomplete SQL (line %d of %s): %s\n" % (self.input_line_number, getattr(self.stdin, "name", "<stdin>"), command))
                if line in ("go", "/"):
                    break
                command=command+"\n"+line
            return command
        except KeyboardInterrupt:
            self.handle_interrupt()
            return ""

    def handle_interrupt(self):
        """Deal with keyboard interrupt (typically Control-C).  It
        will :meth:`~Connection.interrupt` the database and print"^C" if interactive."""
        self.db.interrupt()
        if not self.bail and self.interactive:
            self.write(self.stderr, "^C\n")
            return
        raise

    def process_complete_line(self, command):
        """Given some text will call the appropriate method to process
        it (eg :meth:`process_sql` or :meth:`process_command`)"""
        try:
            if len(command.strip())==0:
                return
            if command[0]==".":
                self.process_command(command)
            else:
                self.process_sql(command)
        except KeyboardInterrupt:
            self.handle_interrupt()

    def push_input(self):
        """Saves the current input paramaters to a stack.  See :meth:`pop_input`."""
        d={}
        for i in "interactive", "stdin", "input_line_number":
            d[i]=getattr(self, i)
        self._input_stack.append(d)

    def pop_input(self):
        """Restore most recently pushed input parameters (interactive,
        self.stdin, linenumber etc).  Use this if implementing a
        command like read.  Push the current input, read the file and
        then pop the input to go back to before.
        """
        assert(len(self._input_stack))>1
        d=self._input_stack.pop()
        for k,v in d.items():
            setattr(self, k, v)

    def complete(self, token, state):
        """Return a possible completion for readline

        This function is called with state starting at zero to get the
        first completion, then one/two/three etc until you return None.  The best
        implementation is to generate the list when state==0, save it,
        and provide members on each increase.

        The default implementation extracts the current full input
        from readline and then calls :meth:`complete_command` or
        :meth:`complete_sql` as appropriate saving the results for
        subsequent calls.
        """
        if state==0:
            import readline
            # the whole line
            line=readline.get_line_buffer()
            # begining and end(+1) of the token in line
            beg=readline.get_begidx()
            end=readline.get_endidx()
            # Are we matching a command?
            try:
                if self._completion_first and line.startswith("."):
                    self.completions=self.complete_command(line, token, beg, end)
                else:
                    self.completions=self.complete_sql(line, token, beg, end)
            except:
                # Readline swallows any exceptions we raise.  We
                # shouldn't be raising any so this is to catch that
                import traceback
                traceback.print_exc()
                raise

        if state>len(self.completions):
            return None
        return self.completions[state]

    # Taken from https://sqlite.org/lang_keywords.html
    _sqlite_keywords="""ABORTADD AFTER ALL ALTER ANALYZE AND AS ASC ATTACH AUTOINCREMENT
           BEFORE BEGIN BETWEEN BY CASCADE CASE CAST CHECK COLLATE COLUMN COMMIT
           CONFLICT CONSTRAINT CREATE CROSS CURRENT_DATE CURRENT_TIME
           CURRENT_TIMESTAMP DATABASE DEFAULT DEFERRABLE DEFERRED DELETE DESC
           DETACH DISTINCT DROP EACH ELSE END ESCAPE EXCEPT EXCLUSIVE EXISTS
           EXPLAIN FAIL FOR FOREIGN FROM FULL GLOB GROUP HAVING IF IGNORE
           IMMEDIATE IN INDEX INDEXED INITIALLY INNER INSERT INSTEAD INTERSECT
           INTO IS ISNULL JOIN KEY LEFT LIKE LIMIT MATCH NATURAL NOT NOTNULL NULL
           OF OFFSET ON OR ORDER OUTER PLAN PRAGMA PRIMARY QUERY RAISE REFERENCES
           REGEXP REINDEX RELEASE RENAME REPLACE RESTRICT RIGHT ROLLBACK ROW
           SAVEPOINT SELECT SET TABLE TEMP TEMPORARY THEN TO TRANSACTION TRIGGER
           UNION UNIQUE UPDATE USING VACUUM VALUES VIEW VIRTUAL WHEN WHERE""".split()
    # reserved words need to be quoted.  Only a subset of the above are reserved
    # but what the heck
    _sqlite_reserved=_sqlite_keywords
    # add a space after each of them except functions which get parentheses
    _sqlite_keywords=[x+(" ", "(")[x in ("VALUES", "CAST")] for x in _sqlite_keywords]

    _sqlite_special_names="""_ROWID_ OID ROWID SQLITE_MASTER
           SQLITE_SEQUENCE""".split()

    _sqlite_functions="""abs( changes() char( coalesce( glob( ifnull(
           hex( instr( last_insert_rowid() length( like(
           load_extension( lower( ltrim( max( min( nullif( quote(
           random() randomblob( replace( round( rtrim( soundex(
           sqlite_compileoption_get( sqlite_compileoption_used(
           sqlite_source_id() sqlite_version() substr( total_changes()
           trim( typeof( unicode( upper( zeroblob( date( time( datetime(
           julianday( strftime(  avg( count( group_concat( sum( total(""".split()

    _pragmas_bool=("yes", "true", "on", "no", "false", "off")
    _pragmas={"application_id": None,
              "auto_vacuum=": ("NONE", "FULL", "INCREMENTAL"),
              "automatic_index=": _pragmas_bool,
              "cache_size=": None,
              "case_sensitive_like=": _pragmas_bool,
              "checkpoint_fullfsync=": _pragmas_bool,
              "collation_list": None,
              "compile_options": None,
              "database_list": None,
              "default_cache_size=": None,
              "encoding=": None,
              # ('"UTF-8"', '"UTF-16"', '"UTF-16le"', '"UTF16-16be"'),
              # too hard to get " to be part of token just in this special case
              "foreign_key_check": None,
              "foreign_key_list(": None,
              "foreign_keys": _pragmas_bool,
              "freelist_count": None,
              "fullfsync=": _pragmas_bool,
              "ignore_check_constraints": _pragmas_bool,
              "incremental_vacuum(": None,
              "index_info(": None,
              "index_list(": None,
              "integrity_check": None,
              "journal_mode=": ("DELETE", "TRUNCATE", "PERSIST", "MEMORY", "OFF", "WAL"),
              "journal_size_limit=": None,
              "legacy_file_format=": _pragmas_bool,
              "locking_mode=": ("NORMAL", "EXCLUSIVE"),
              "max_page_count=": None,
              "page_count;": None,
              "page_size=": None,
              "quick_check": None,
              "read_uncommitted=": _pragmas_bool,
              "recursive_triggers=": _pragmas_bool,
              "reverse_unordered_selects=": _pragmas_bool,
              "schema_version": None,
              "secure_delete=": _pragmas_bool,
              "shrink_memory": None,
              "synchronous=": ("OFF", "NORMAL", "FULL"),
              "table_info(": None,
              "temp_store=": ("DEFAULT", "FILE", "MEMORY"),
              "temp_store_directory=": None,
              "wal_autocheckpoint=": None,
              "wal_checkpoint": None,
              "writable_schema": _pragmas_bool,
              }

    def _get_prev_tokens(self, line, end):
        "Returns the tokens prior to pos end in the line"
        return re.findall(r'"?\w+"?', line[:end])

    def complete_sql(self, line, token, beg, end):
        """Provide some completions for SQL

        :param line: The current complete input line
        :param token: The word readline is looking for matches
        :param beg: Integer offset of token in line
        :param end: Integer end of token in line
        :return: A list of completions, or an empty list if none
        """
        if self._completion_cache is None:
            cur=self.db.cursor()
            collations=[row[1] for row in cur.execute("pragma collation_list")]
            databases=[row[1] for row in cur.execute("pragma database_list")]
            other=[]
            for db in databases:
                if db=="temp":
                    master="sqlite_temp_master"
                else:
                    master="[%s].sqlite_master" % (db,)
                for row in cur.execute("select * from "+master).fetchall():
                    for col in (1,2):
                        if row[col] not in other and not row[col].startswith("sqlite_"):
                            other.append(row[col])
                    if row[0]=="table":
                        try:
                            for table in cur.execute("pragma [%s].table_info([%s])" % (db, row[1],)).fetchall():
                                if table[1] not in other:
                                    other.append(table[1])
                                for item in table[2].split():
                                    if item not in other:
                                        other.append(item)
                        except apsw.SQLError:
                            # See https://code.google.com/p/apsw/issues/detail?id=86
                            pass

            self._completion_cache=[self._sqlite_keywords, self._sqlite_functions, self._sqlite_special_names, collations, databases, other]
            for i in range(len(self._completion_cache)):
                self._completion_cache[i].sort()

        # be somewhat sensible about pragmas
        if "pragma " in line.lower():
            t=self._get_prev_tokens(line.lower(), end)

            # pragma foo = bar
            if len(t)>2 and t[-3]=="pragma":
                # t[-2] should be a valid one
                for p in self._pragmas:
                    if p.replace("=","")==t[-2]:
                        vals=self._pragmas[p]
                        if not vals:
                            return []
                        return [x+";" for x in vals if x.startswith(token)]
            # at equals?
            if len(t)>1 and t[-2]=="pragma" and line[:end].replace(" ","").endswith("="):
                for p in self._pragmas:
                    if p.replace("=","")==t[-1]:
                        vals=self._pragmas[p]
                        if not vals:
                            return []
                        return vals
            # pragma foo
            if len(t)>1 and t[-2]=="pragma":
                res=[x for x in self._pragmas.keys() if x.startswith(token)]
                res.sort()
                return res

            # pragma
            if len(t) and t[-1]=="pragma":
                res=list(self._pragmas.keys())
                res.sort()
                return res

        # This is currently not context sensitive (eg it doesn't look
        # to see if last token was 'FROM' and hence next should only
        # be table names.  That is a SMOP like pragmas above
        res=[]
        ut=token.upper()
        for corpus in self._completion_cache:
            for word in corpus:
                if word.upper().startswith(ut):
                    # potential match - now match case
                    if word.startswith(token):  # exact
                        if word not in res:
                            res.append(word)
                    elif word.lower().startswith(token):  # lower
                        if word.lower() not in res:
                            res.append(word.lower())
                    elif word.upper().startswith(token):  # upper
                        if word.upper() not in res:
                            res.append(word.upper())
                    else:
                        # match letter by letter otherwise readline mangles what was typed in
                        w=token+word[len(token):]
                        if w not in res:
                            res.append(w)
        return res

    _builtin_commands=None

    def complete_command(self, line, token, beg, end):
        """Provide some completions for dot commands

        :param line: The current complete input line
        :param token: The word readline is looking for matches
        :param beg: Integer offset of token in line
        :param end: Integer end of token in line
        :return: A list of completions, or an empty list if none
        """
        if not self._builtin_commands:
            self._builtin_commands=["."+x[len("command_"):] for x in dir(self) if x.startswith("command_") and x!="command_headers"]
        if beg==0:
            # some commands don't need a space because they take no
            # params but who cares?
            return [x+" " for x in self._builtin_commands if x.startswith(token)]
        return None

    def get_resource_usage(self):
        """Return a dict of various numbers (ints or floats).  The
        .timer command shows the difference between before and after
        results of what this returns by calling :meth:`display_timing`"""
        if sys.platform=="win32":
            import ctypes, time, platform
            ctypes.windll.kernel32.GetProcessTimes.argtypes=[
                platform.architecture()[0]=='64bit' and ctypes.c_int64 or ctypes.c_int32,
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

            # All 4 out params have to be present.  FILETIME is really
            # just a 64 bit quantity in 100 nanosecond granularity
            dummy=ctypes.c_ulonglong()
            utime=ctypes.c_ulonglong()
            stime=ctypes.c_ulonglong()
            rc=ctypes.windll.kernel32.GetProcessTimes(
                ctypes.windll.kernel32.GetCurrentProcess(),
                ctypes.byref(dummy),  # creation time
                ctypes.byref(dummy),  # exit time
                ctypes.byref(stime),
                ctypes.byref(utime))
            if rc:
                return {'Wall clock': time.time(),
                        'User time': float(utime.value)/10000000,
                        'System time': float(stime.value)/10000000}
            return {}
        else:
            import resource, time
            r=resource.getrusage(resource.RUSAGE_SELF)
            res={'Wall clock': time.time()}
            for i,desc in (("utime", "User time"),
                       ("stime", "System time"),
                       ("maxrss", "Max rss"),
                       ("idrss", "Memory"),
                       ("isrss", "Stack"),
                       ("ixrss", "Shared Memory"),
                       ("minflt", "PF (no I/O)"),
                       ("majflt", "PF (I/O)"),
                       ("inblock", "Blocks in"),
                       ("oublock", "Blocks out"),
                       ("nsignals", "Signals"),
                       ("nvcsw", "Voluntary context switches"),
                       ("nivcsw", "Involunary context switches"),
                       ("msgrcv", "Messages received"),
                       ("msgsnd", "Messages sent"),
                       ("nswap", "Swaps"),
                       ):
                f="ru_"+i
                if hasattr(r, f):
                    res[desc]=getattr(r,f)
            return res

    def display_timing(self, b4, after):
        """Writes the difference between b4 and after to self.stderr.
        The data is dictionaries returned from
        :meth:`get_resource_usage`."""
        v=list(b4.keys())
        for i in after:
            if i not in v:
                v.append(i)
        v.sort()
        for k in v:
            if k in b4 and k in after:
                one=b4[k]
                two=after[k]
                val=two-one
                if val:
                    if type(val)==float:
                        self.write(self.stderr, "+ %s: %.4f\n" % (k, val))
                    else:
                        self.write(self.stderr, "+ %s: %d\n" % (k, val))

    # Colour support

    def _out_colour(self):
        # Sets up color for output.  Input being interactive doesn't
        # matter.  This method needs to be called on all changes to
        # output.
        if getattr(self.stdout, "isatty", False) and self.stdout.isatty():
            self.colour=self._colours[self.colour_scheme]
        else:
            self.colour=self._colours["off"]

    # This class returns an empty string for all undefined attributes
    # so that it doesn't matter if a colour scheme leaves something
    # out.
    class _colourscheme:

        def __init__(self, **kwargs):
            for k,v in kwargs.items():
                setattr(self, k, v)

        def __nonzero__(self):
            return True

        def __str__(self):
            return "_colourscheme("+str(self.__dict__)+")"

        def __getattr__(self, k):
            return ""

        def colour_value(self, val, formatted):
            self.colour
            if val is None:
                return self.vnull+formatted+self.vnull_
            if isinstance(val, Shell._basestring):
                return self.vstring+formatted+self.vstring_
            if isinstance(val, Shell._binary_type):
                return self.vblob+formatted+self.vblob_
            # must be a number - we don't distinguish between float/int
            return self.vnumber+formatted+self.vnumber_

    # The colour definitions - the convention is the name to turn
    # something on and the name with an underscore suffix to turn it
    # off
    d=_colourscheme(**dict([(v, "\x1b["+str(n)+"m") for n,v in {0: "reset", 1: "bold", 4: "underline", 22: "bold_", 24: "underline_",
     7: "inverse", 27: "inverse_",
     30: "fg_black", 31: "fg_red", 32: "fg_green", 33: "fg_yellow", 34: "fg_blue", 35: "fg_magenta", 36: "fg_cyan", 37: "fg_white", 39: "fg_",
     40: "bg_black", 41: "bg_red", 42: "bg_green", 43: "bg_yellow", 44: "bg_blue", 45: "bg_magenta", 46: "bg_cyan", 47: "bg_white", 49: "bg_"}.items()]))

    _colours={"off": _colourscheme(colour_value=lambda x,y: y)}

    _colours["default"]=_colourscheme(prompt=d.bold, prompt_=d.bold_,
                                      error=d.fg_red+d.bold, error_=d.bold_+d.fg_,
                                      intro=d.fg_blue+d.bold, intro_=d.bold_+d.fg_,
                                      summary=d.fg_blue+d.bold, summary_=d.bold_+d.fg_,
                                      header=sys.platform=="win32" and d.inverse or d.underline,
                                      header_=sys.platform=="win32" and d.inverse_ or d.underline_,
                                      vnull=d.fg_red, vnull_=d.fg_,
                                      vstring=d.fg_yellow, vstring_=d.fg_,
                                      vblob=d.fg_blue, vblob_=d.fg_,
                                      vnumber=d.fg_magenta, vnumber_=d.fg_)
    if sys.platform=="win32":
        if not _win_colour:
            for k in _colours:
                _colours[k]=_colours["off"]
    # unpollute namespace
    del d
    del _colourscheme
    try:
        del n
        del x
        del v
    except:
        pass


def main():
    # Docstring must start on second line so dedenting works correctly
    """
    Call this to run the interactive shell.  It automatically passes
    in sys.argv[1:] and exits Python when done.

    """
    try:
        s=Shell()
        _,_,cmds=s.process_args(sys.argv[1:])
        if len(cmds)==0:
            s.cmdloop()
    except:
        v=sys.exc_info()[1]
        if getattr(v, "_handle_exception_saw_this", False):
            pass
        else:
            # Where did this exception come from?
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__=='__main__':
    main()
