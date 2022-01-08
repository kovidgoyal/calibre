#!/usr/bin/env python
# Copyright (C) 2006-2009 Søren Roug, European Environment Agency
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
import zipfile

from odf.text import UserFieldDecl
from odf.namespaces import OFFICENS
from odf.opendocument import load

OUTENCODING = "utf-8"


# OpenDocument v.1.0 section 6.7.1
VALUE_TYPES = {
    'float': (OFFICENS, 'value'),
    'percentage': (OFFICENS, 'value'),
    'currency': (OFFICENS, 'value'),
    'date': (OFFICENS, 'date-value'),
    'time': (OFFICENS, 'time-value'),
    'boolean': (OFFICENS, 'boolean-value'),
    'string': (OFFICENS, 'string-value'),
    }


class UserFields:
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
        self.document = None

    def loaddoc(self):
        if isinstance(self.src_file, (bytes, str)):
            # src_file is a filename, check if it is a zip-file
            if not zipfile.is_zipfile(self.src_file):
                raise TypeError("%s is no odt file." % self.src_file)
        elif self.src_file is None:
            # use stdin if no file given
            self.src_file = sys.stdin

        self.document = load(self.src_file)

    def savedoc(self):
        # write output
        if self.dest_file is None:
            # use stdout if no filename given
            self.document.save('-')
        else:
            self.document.save(self.dest_file)

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
        self.loaddoc()
        found_fields = []
        all_fields = self.document.getElementsByType(UserFieldDecl)
        for f in all_fields:
            value_type = f.getAttribute('valuetype')
            if value_type == 'string':
                value = f.getAttribute('stringvalue')
            else:
                value = f.getAttribute('value')
            field_name = f.getAttribute('name')

            if field_names is None or field_name in field_names:
                found_fields.append((field_name.encode(OUTENCODING),
                                     value_type.encode(OUTENCODING),
                                     value.encode(OUTENCODING)))
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
        self.loaddoc()
        all_fields = self.document.getElementsByType(UserFieldDecl)
        for f in all_fields:
            field_name = f.getAttribute('name')
            if field_name in data:
                value_type = f.getAttribute('valuetype')
                value = data.get(field_name)
                if value_type == 'string':
                    f.setAttribute('stringvalue', value)
                else:
                    f.setAttribute('value', value)
        self.savedoc()
