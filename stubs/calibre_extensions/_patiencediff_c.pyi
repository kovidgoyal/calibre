from collections.abc import Callable, Sequence

def unique_lcs_c(a: Sequence[str], b: Sequence[str]) -> list[tuple[int, int]]:
    "Find the longest common subsequence of unique lines in a and b"
    pass

def recurse_matches_c(a: Sequence[str], b: Sequence[str], alo: int, blo: int, ahi: int, bhi: int, answer: list[tuple[int, int]], maxrecursion: int) -> None:
    "Recursively find pairs of lines that match uniquely, appending (a, b) index pairs to answer"
    pass

class PatienceSequenceMatcher_c:
    def __init__(self, isjunk: Callable[[str], bool] | None, a: Sequence[str], b: Sequence[str]) -> None:
        "C implementation of PatienceSequenceMatcher"
        pass

    def get_matching_blocks(self) -> list[tuple[int, int, int]]:
        "Return list of triples describing matching subsequences."
        pass

    def get_opcodes(self) -> list[tuple[str, int, int, int, int]]:
        "Return list of 5-tuples describing how to turn a into b."
        pass

    def get_grouped_opcodes(self, n: int = 3) -> list[list[tuple[str, int, int, int, int]]]:
        "Isolate change clusters by eliminating ranges with no changes."
        pass
