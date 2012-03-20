from htmlserializer import HTMLSerializer

class XHTMLSerializer(HTMLSerializer):
    quote_attr_values = True
    minimize_boolean_attributes = False
    use_trailing_solidus = True
    escape_lt_in_attrs = True
    omit_optional_tags = False
    escape_rcdata = True
