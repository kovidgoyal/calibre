class HunspellError(Exception):
    pass

class Dictionary:
    def __init__(self, dic: str, aff: str) -> None:
        'Dictionary object'
        pass

    def recognized(self, word: str) -> bool:
        (
            'Checks the spelling of the given word. The word must be a unicode object. If encoding of the word to the encoding of the dictionary fails, a'
            ' UnicodeEncodeError is raised. Returns False if the input word is not recognized.'
        )
        pass

    def suggest(self, word: str) -> tuple[str, ...]:
        (
            'Provide suggestions for the given word. The input word must be a unicode object. If encoding of the word to the encoding of the dictionary fails,'
            ' a UnicodeEncodeError is raised. Returns the list of suggested words as unicode objects.'
        )
        pass

    def add(self, word: str) -> bool:
        'Adds the given word into the runtime dictionary'
        pass

    def remove(self, word: str) -> bool:
        'Removes the given word from the runtime dictionary'
        pass
