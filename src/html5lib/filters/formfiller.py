#
# The goal is to finally have a form filler where you pass data for
# each form, using the algorithm for "Seeding a form with initial values"
# See http://www.whatwg.org/specs/web-forms/current-work/#seeding
#

import _base

from html5lib.constants import spaceCharacters
spaceCharacters = u"".join(spaceCharacters)

class SimpleFilter(_base.Filter):
    def __init__(self, source, fieldStorage):
        _base.Filter.__init__(self, source)
        self.fieldStorage = fieldStorage

    def __iter__(self):
        field_indices = {}
        state = None
        field_name = None
        for token in _base.Filter.__iter__(self):
            type = token["type"]
            if type in ("StartTag", "EmptyTag"):
                name = token["name"].lower()
                if name == "input":
                    field_name = None
                    field_type = None
                    input_value_index = -1
                    input_checked_index = -1
                    for i,(n,v) in enumerate(token["data"]):
                        n = n.lower()
                        if n == u"name":
                            field_name = v.strip(spaceCharacters)
                        elif n == u"type":
                            field_type = v.strip(spaceCharacters)
                        elif n == u"checked":
                            input_checked_index = i
                        elif n == u"value":
                            input_value_index = i

                    value_list = self.fieldStorage.getlist(field_name)
                    field_index = field_indices.setdefault(field_name, 0)
                    if field_index < len(value_list):
                        value = value_list[field_index]
                    else:
                        value = ""

                    if field_type in (u"checkbox", u"radio"):
                        if value_list:
                            if token["data"][input_value_index][1] == value:
                                if input_checked_index < 0:
                                    token["data"].append((u"checked", u""))
                                field_indices[field_name] = field_index + 1
                            elif input_checked_index >= 0:
                                del token["data"][input_checked_index]

                    elif field_type not in (u"button", u"submit", u"reset"):
                        if input_value_index >= 0:
                            token["data"][input_value_index] = (u"value", value)
                        else:
                            token["data"].append((u"value", value))
                        field_indices[field_name] = field_index + 1

                    field_type = None
                    field_name = None

                elif name == "textarea":
                    field_type = "textarea"
                    field_name = dict((token["data"])[::-1])["name"]

                elif name == "select":
                    field_type = "select"
                    attributes = dict(token["data"][::-1])
                    field_name = attributes.get("name")
                    is_select_multiple = "multiple" in attributes
                    is_selected_option_found = False

                elif field_type == "select" and field_name and name == "option":
                    option_selected_index = -1
                    option_value = None
                    for i,(n,v) in enumerate(token["data"]):
                        n = n.lower()
                        if n == "selected":
                            option_selected_index = i
                        elif n == "value":
                            option_value = v.strip(spaceCharacters)
                    if option_value is None:
                        raise NotImplementedError("<option>s without a value= attribute")
                    else:
                        value_list = self.fieldStorage.getlist(field_name)
                        if value_list:
                            field_index = field_indices.setdefault(field_name, 0)
                            if field_index < len(value_list):
                                value = value_list[field_index]
                            else:
                                value = ""
                            if (is_select_multiple or not is_selected_option_found) and option_value == value:
                                if option_selected_index < 0:
                                    token["data"].append((u"selected", u""))
                                field_indices[field_name] = field_index + 1
                                is_selected_option_found = True
                            elif option_selected_index >= 0:
                                del token["data"][option_selected_index]

            elif field_type is not None and field_name and type == "EndTag":
                name = token["name"].lower()
                if name == field_type:
                    if name == "textarea":
                        value_list = self.fieldStorage.getlist(field_name)
                        if value_list:
                            field_index = field_indices.setdefault(field_name, 0)
                            if field_index < len(value_list):
                                value = value_list[field_index]
                            else:
                                value = ""
                            yield {"type": "Characters", "data": value}
                            field_indices[field_name] = field_index + 1

                    field_name = None

                elif name == "option" and field_type == "select":
                    pass # TODO: part of "option without value= attribute" processing

            elif field_type == "textarea":
                continue # ignore token

            yield token
