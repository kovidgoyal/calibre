

def _optimize(tagList, tagName, conversion):
    # copy the tag of interest plus any text
    newTagList = []
    for tag in tagList:
        if tag.name == tagName or tag.name == "rawtext":
            newTagList.append(tag)

    # now, eliminate any duplicates (leaving the last one)
    for i, newTag in enumerate(newTagList[:-1]):
        if newTag.name == tagName and newTagList[i+1].name == tagName:
            tagList.remove(newTag)

    # eliminate redundant settings to same value across text strings
    newTagList = []
    for tag in tagList:
        if tag.name == tagName:
            newTagList.append(tag)

    for i, newTag in enumerate(newTagList[:-1]):
        value = conversion(newTag.parameter)
        nextValue = conversion(newTagList[i+1].parameter)
        if value == nextValue:
            tagList.remove(newTagList[i+1])

    # eliminate any setting that don't have text after them
    while len(tagList) > 0 and tagList[-1].name == tagName:
        del tagList[-1]


def tagListOptimizer(tagList):
    # this function eliminates redundant or unnecessary tags
    # it scans a list of tags, looking for text settings that are
    # changed before any text is output
    # for example,
    #  fontsize=100, fontsize=200, text, fontsize=100, fontsize=200
    # should be:
    # fontsize=200 text
    oldSize = len(tagList)
    _optimize(tagList, "fontsize", int)
    _optimize(tagList, "fontweight", int)
    return oldSize - len(tagList)
