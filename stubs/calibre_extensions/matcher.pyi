from collections.abc import Sequence
from typing import Any

class Matcher:
    def __init__(self, items: Sequence[str], collator: Any, level1: str, level2: str, level3: str) -> None:
        'Matcher'
        pass

    def calculate_scores(self, query: str) -> tuple[tuple[float, ...], tuple[tuple[int, ...], ...]]:
        'calculate_scores(query) -> Return the scores for all items given query as a tuple.'
        pass
