from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from .pylrf import LrfTag


def _optimize(tagList: list[LrfTag], tagName: str, conversion: Callable[[str | float], int]) -> None:
    # copy the tag of interest plus any text
    newTagList: list[LrfTag] = []
    for tag in tagList:
        if tag.name in {tagName, 'rawtext'}:
            newTagList.append(tag)

    # now, eliminate any duplicates (leaving the last one)
    for i, newTag in enumerate(newTagList[:-1]):
        if newTag.name == tagName and newTagList[i + 1].name == tagName:
            tagList.remove(newTag)

    # eliminate redundant settings to same value across text strings
    newTagList = []
    for tag in tagList:
        if tag.name == tagName:
            newTagList.append(tag)

    for i, newTag in enumerate(newTagList[:-1]):
        # the parameters of the fontsize and fontweight tags are str or numeric setting values
        value = conversion(cast('str | float', newTag.parameter))
        nextValue = conversion(cast('str | float', newTagList[i + 1].parameter))
        if value == nextValue:
            tagList.remove(newTagList[i + 1])

    # eliminate any setting that don't have text after them
    while len(tagList) > 0 and tagList[-1].name == tagName:
        del tagList[-1]


def tagListOptimizer(tagList: list[LrfTag]) -> int:
    # this function eliminates redundant or unnecessary tags
    # it scans a list of tags, looking for text settings that are
    # changed before any text is output
    # for example,
    #  fontsize=100, fontsize=200, text, fontsize=100, fontsize=200
    # should be:
    # fontsize=200 text
    oldSize = len(tagList)
    _optimize(tagList, 'fontsize', int)
    _optimize(tagList, 'fontweight', int)
    return oldSize - len(tagList)
