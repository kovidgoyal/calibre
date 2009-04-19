#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (C) 2006-2007 Søren Roug, European Environment Agency
#
# This is free software.  You may redistribute it under the terms
# of the Apache license and the GNU General Public License Version
# 2 or at your option any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# Contributor(s): Michael Howitz, gocept gmbh & co. kg
#
# $Id: userfield.py 447 2008-07-10 20:01:30Z roug $

"""Class to show and manipulate user fields in odf documents."""

import sys
import time
import zipfile

import xml.sax
import xml.sax.handler
import xml.sax.saxutils

from odf.namespaces import OFFICENS, TEXTNS

from cStringIO import StringIO

OUTENCODING = "utf-8"


# OpenDocument v.1.0 section 6.7.1
VALUE_TYPES = {
    'float': (OFFICENS, u'value'),
    'percentage': (OFFICENS, u'value'),
    'currency': (OFFICENS, u'value'),
    'date': (OFFICENS, u'date-value'),
    'time': (OFFICENS, u'time-value'),
    'boolean': (OFFICENS, u'boolean-value'),
    'string': (OFFICENS, u'string-value'),
    }


class UserFields(object):
    """List, view and manipulate user fields."""

    # these attributes can be a filename or a file like object
    src_file = None
    dest_file = None

    def __init__(self, src=None, dest=None):
        """Constructor

        src ... source document name, file like object or None for stdin
        dest ... destination document name, file like object or None for stdout
   
        """
        self.src_file = src
        self.dest_file = dest

    def list_fields(self):
        """List (extract) all known user-fields.
        
        Returns list of user-field names.
        
        """
        return [x[0] for x in self.list_fields_and_values()]

    def list_fields_and_values(self, field_names=None):
        """List (extract) user-fields with type and value.

        field_names ... list of field names to show or None for all.

        Returns list of tuples (<field name>, <field type>, <value>).

        """
        found_fields = []
        def _callback(field_name, value_type, value, attrs):
            if field_names is None or field_name in field_names:
                found_fields.append((field_name.encode(OUTENCODING),
                                     value_type.encode(OUTENCODING),
                                     value.encode(OUTENCODING)))
            return attrs
        
        self._content_handler(_callback)
        return found_fields

    def list_values(self, field_names):
        """Extract the contents of given field names from the file.

        field_names ... list of field names

        Returns list of field values.

        """
        return [x[2] for x in self.list_fields_and_values(field_names)]

    def get(self, field_name):
        """Extract the contents of this field from the file.

        Returns field value or None if field does not exist.

        """
        values = self.list_values([field_name])
        if not values:
            return None
        return values[0]

    def get_type_and_value(self, field_name):
        """Extract the type and contents of this field from the file.

        Returns tuple (<type>, <field-value>) or None if field does not exist.

        """
        fields = self.list_fields_and_values([field_name])
        if not fields:
            return None
        field_name, value_type, value = fields[0]
        return value_type, value

    def update(self, data):
        """Set the value of user fields. The field types will be the same.

        data ... dict, with field name as key, field value as value

        Returns None

        """
        def _callback(field_name, value_type, value, attrs):
            if field_name in data:
                valattr = VALUE_TYPES.get(value_type)
                attrs = dict(attrs.items())
                # Take advantage that startElementNS can take a normal
                # dict as attrs
                attrs[valattr] = data[field_name]
            return attrs
        self._content_handler(_callback, write_file=True)

    def _content_handler(self, callback_func, write_file=False):
        """Handle the content using the callback function and write result if
           necessary.

        callback_func ... function called for each field found in odf document
                          signature: field_name ... name of current field
                                     value_type ... type of current field
                                     value ... value of current field
                                     attrs ... tuple of attrs of current field
                          returns: tuple or dict of attrs
        write_file ... boolean telling wether write result to file

        """
        class DevNull(object):
            """IO-object which behaves like /dev/null."""
            def write(self, str):
                pass

        # get input
        if isinstance(self.src_file, basestring):
            # src_file is a filename, check if it is a zip-file
            if not zipfile.is_zipfile(self.src_file):
                raise TypeError("%s is no odt file." % self.src_file)
        elif self.src_file is None:
            # use stdin if no file given
            self.src_file = sys.stdin

        zin = zipfile.ZipFile(self.src_file, 'r')
        content_xml = zin.read('content.xml')

        # prepare output
        if write_file:
            output_io = StringIO()
            if self.dest_file is None:
                # use stdout if no filename given
                self.dest_file = sys.stdout
            zout = zipfile.ZipFile(self.dest_file, 'w')
        else:
            output_io = DevNull()


        # parse input
        odfs = ODFContentParser(callback_func, output_io)
        parser = xml.sax.make_parser()
        parser.setFeature(xml.sax.handler.feature_namespaces, 1)
        parser.setContentHandler(odfs)
        parser.parse(StringIO(content_xml))

        # write output
        if write_file:
            # Loop through the input zipfile and copy the content to
            # the output until we get to the content.xml. Then
            # substitute.
            for zinfo in zin.infolist():
                if zinfo.filename == "content.xml":
                    # Write meta
                    zi = zipfile.ZipInfo("content.xml", time.localtime()[:6])
                    zi.compress_type = zipfile.ZIP_DEFLATED
                    zout.writestr(zi, odfs.content())
                else:
                    payload = zin.read(zinfo.filename)
                    zout.writestr(zinfo, payload)
            zout.close()
        zin.close()


class ODFContentParser(xml.sax.saxutils.XMLGenerator):

    def __init__(self, callback_func, out=None, encoding=OUTENCODING):
        """Constructor.

        callback_func ... function called for each field found in odf document
                          signature: field_name ... name of current field
                                     value_type ... type of current field
                                     value ... value of current field
                                     attrs ... tuple of attrs of current field
                          returns: tuple or dict of attrs
        out ... file like object for output
        encoding ... encoding for output

        """
        self._callback_func = callback_func
        xml.sax.saxutils.XMLGenerator.__init__(self, out, encoding)

    def _qname(self, name):
        """Builds a qualified name from a (ns_url, localname) pair"""
        if name[0]:
            if name[0] == u'http://www.w3.org/XML/1998/namespace':
                return u'xml' + ":" + name[1]
            # The name is in a non-empty namespace
            prefix = self._current_context[name[0]]
            if prefix:
                # If it is not the default namespace, prepend the prefix
                return prefix + ":" + name[1]
        # Return the unqualified name
        return name[1]

    def startElementNS(self, name, qname, attrs):
        if name == (TEXTNS, u'user-field-decl'):
            field_name = attrs.get((TEXTNS, u'name'))
            value_type = attrs.get((OFFICENS, u'value-type'))
            if value_type == 'string':
                value = attrs.get((OFFICENS, u'string-value'))
            else:
                value = attrs.get((OFFICENS, u'value'))

            attrs = self._callback_func(field_name, value_type, value, attrs)

        self._startElementNS(name, qname, attrs)

    def _startElementNS(self, name, qname, attrs):
        # copy of xml.sax.saxutils.XMLGenerator.startElementNS
        # necessary because we have to provide our own writeattr
        # function which is called by this method
        if name[0] is None:
            name = name[1]
        elif self._current_context[name[0]] is None:
            # default namespace
            name = name[1]
        else:
            name = self._current_context[name[0]] + ":" + name[1]
        self._out.write('<' + name)

        for k,v in self._undeclared_ns_maps:
            if k is None:
                self._out.write(' xmlns="%s"' % (v or ''))
            else:
                self._out.write(' xmlns:%s="%s"' % (k,v))
        self._undeclared_ns_maps = []

        for (name, value) in attrs.items():
            if name[0] is None:
                name = name[1]
            elif self._current_context[name[0]] is None:
                # default namespace
                #If an attribute has a nsuri but not a prefix, we must
                #create a prefix and add a nsdecl
                prefix = self.GENERATED_PREFIX % self._generated_prefix_ctr
                self._generated_prefix_ctr = self._generated_prefix_ctr + 1
                name = prefix + ':' + name[1]
                self._out.write(' xmlns:%s=%s' % (prefix, quoteattr(name[0])))
                self._current_context[name[0]] = prefix
            else:
                name = self._current_context[name[0]] + ":" + name[1]
            self._out.write(' %s=' % name)
            writeattr(self._out, value)
        self._out.write('>')

    def content(self):
        return self._out.getvalue()


ATTR_ENTITIES = {
    '\n': '&#x0a;' # convert newlines into entities inside attributes
    }


def writetext(stream, text, entities={}):
    text = xml.sax.saxutils.escape(text, entities)
    try:
        stream.write(text)
    except UnicodeError:
        for c in text:
            try:
                stream.write(c)
            except UnicodeError:
                stream.write(u"&#%d;" % ord(c))

def writeattr(stream, text):
    # copied from xml.sax.saxutils.writeattr added support for an
    # additional entity mapping
    countdouble = text.count('"')
    entities = ATTR_ENTITIES.copy()
    if countdouble:
        countsingle = text.count("'")
        if countdouble <= countsingle:
            entities['"'] = "&quot;"
            quote = '"'
        else:
            entities["'"] =  "&apos;"
            quote = "'"
    else:
        quote = '"'
    stream.write(quote)
    writetext(stream, text, entities)
    stream.write(quote)
