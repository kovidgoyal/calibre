# License: GPLv3 Copyright: 2006, Ed Summers <ehs@pobox.com>


class URL:
    """
    Class for representing a URL in an opensearch v1.1 query
    """

    def __init__(self, type: str = '', template: str = '', method: str = 'GET') -> None:
        self.type = type
        self.template = template
        self.method = 'GET'
        self.params = []
