Reverse engineering the trailing byte sequences for hierarchical periodicals
===============================================================================

In the following, *vwi* means variable width integer and *fvwi* means a vwi whose lowest four bits are used as a flag.

Opening record
----------------

The text record that contains the opening node for the periodical (depth=0 node in the NCX) can have TBS of 3 different forms:

    1. If it has only the periodical node and no section/article nodes, TBS of type 2, like this::

            Record #1: Starts at: 0 Ends at: 4095
                Contains: 1 index entries (0 ends, 0 complete, 1 starts)
            TBS bytes: 82 80
                Starts:
                    Index Entry: 0 (Parent index: -1, Depth: 0, Offset: 215, Size: 68470) [j_x's Google reader]
            TBS Type: 010 (2)
            Outer Index entry: 0
            Unknown (vwi: always 0?): 0

    2. A periodical and a section node, but no article nodes, TBS type of 6, like this::

            Record #1: Starts at: 0 Ends at: 4095
                Contains: 2 index entries (0 ends, 0 complete, 2 starts)
            TBS bytes: 86 80 2
                Starts:
                    Index Entry: 0 (Parent index: -1, Depth: 0, Offset: 215, Size: 93254) [j_x's Google reader]
                    Index Entry: 1 (Parent index: 0, Depth: 1, Offset: 541, Size: 49280) [Ars Technica]
            TBS Type: 110 (6)
            Outer Index entry: 0
            Unknown (vwi: always 0?): 0
            Unknown (byte: always 2?): 2

    3. If it has both the section 1 node and at least one article node, TBS of type 6, like this::

            Record #1: Starts at: 0 Ends at: 4095
                Contains: 4 index entries (0 ends, 1 complete, 3 starts)
            TBS bytes: 86 80 2 c4 2
                Complete:
                    Index Entry: 5 (Parent index: 1, Depth: 2, Offset: 549, Size: 1866) [Week in gaming: 3DS review, Crysis 2, George Hotz]
                Starts:
                    Index Entry: 0 (Parent index: -1, Depth: 0, Offset: 215, Size: 79253) [j_x's Google reader]
                    Index Entry: 1 (Parent index: 0, Depth: 1, Offset: 541, Size: 35279) [Ars Technica]
                    Index Entry: 6 (Parent index: 1, Depth: 2, Offset: 2415, Size: 2764) [Week in Apple: ZFS on Mac OS X, rogue tethering, DUI apps, and more]
            TBS Type: 110 (6)
            Outer Index entry: 0
            Unknown (vwi: always 0?): 0
            Unknown (byte: always 2?): 2
            Article index at start of record or first article index, relative to parent section (fvwi): 4 [5 absolute]
            Number of article nodes in the record (byte): 2

        If there was only a single article, instead of 2, then the last two bytes would be: c0, i.e. there would be no byte giving the number of articles in the record.


Records with no nodes
------------------------

These records are spanned by a single article. They are of two types:

    1. If the parent section index is 1, TBS type of 6, like this::

            Record #4: Starts at: 12288 Ends at: 16383
                Contains: 0 index entries (0 ends, 0 complete, 0 starts)
            TBS bytes: 86 80 2 c1 80
            TBS Type: 110 (6)
            Outer Index entry: 0
            Unknown (vwi: always 0?): 0
            Unknown (byte: always 2?): 2
            Article index at start of record or first article index, relative to parent section (fvwi): 4 [5 absolute]
            EOF (vwi: should be 0): 0

        If the record is before the first article, the TBS bytes would be: 86 80 2

    2. If the parent section index is > 1, TBS type of 2, like this::

            Record #14: Starts at: 53248 Ends at: 57343
                Contains: 0 index entries (0 ends, 0 complete, 0 starts)
            TBS bytes: 82 80 a0 1 e1 80
            TBS Type: 010 (2)
            Outer Index entry: 0
            Unknown (vwi: always 0?): 0
            Parent section index (fvwi): 2
            Flags: 0
            Article index at start of record or first article index, relative to parent section (fvwi): 14 [16 absolute]
            EOF (vwi: should be 0): 0

Records with only article nodes
-----------------------------------

Such records have no section transitions (i.e. a section end/section start pair). They have only one or more article nodes. They are of two types:

    1. If the parent section index is 1, TBS type of 7, like this::

            Record #6: Starts at: 20480 Ends at: 24575
                Contains: 2 index entries (1 ends, 0 complete, 1 starts)
            TBS bytes: 87 80 2 80 1 84 2
                Ends:
                    Index Entry: 9 (Parent index: 1, Depth: 2, Offset: 16453, Size: 4199) [Vaccine's success spurs whooping cough comeback]
                Starts:
                    Index Entry: 10 (Parent index: 1, Depth: 2, Offset: 20652, Size: 4246) [Apple's mobile products do not violate Nokia patents, says ITC]
            TBS Type: 111 (7)
            Outer Index entry: 0
            Unknown (vwi: always 0?): 0
            Unknown: '\x02\x80' (vwi?: Always 256)
            Article at start of record (fvwi): 8
            Number of articles in record (byte): 2

        If there was only one article in the record, the last two bytes would be replaced by a single byte: 80

        If this record is the first record with an article, then the article at the start of the record should be the last section index. At least, that's what kindlegen does, though if you ask me, it should be the first section index.


    2. If the parent section index is > 1, TBS type of 2, like this::

            Record #16: Starts at: 61440 Ends at: 65535
                Contains: 5 index entries (1 ends, 3 complete, 1 starts)
            TBS bytes: 82 80 a1 80 1 f4 5
                Ends:
                    Index Entry: 17 (Parent index: 2, Depth: 2, Offset: 60920, Size: 1082) [Microsoft's Joe Belfiore still working on upcoming Zune hardware]
                Complete:
                    Index Entry: 18 (Parent index: 2, Depth: 2, Offset: 62002, Size: 1016) [Rumour: OS X Lion nearing Golden Master stage]
                    Index Entry: 19 (Parent index: 2, Depth: 2, Offset: 63018, Size: 1045) [iOS 4.3.1 released]
                    Index Entry: 20 (Parent index: 2, Depth: 2, Offset: 64063, Size: 972) [Windows 8 'system reset' image leaks]
                Starts:
                    Index Entry: 21 (Parent index: 2, Depth: 2, Offset: 65035, Size: 1057) [Windows Phone 7: Why it's failing]
            TBS Type: 010 (2)
            Outer Index entry: 0
            Unknown (vwi: always 0?): 0
            Parent section index (fvwi) : 2
            Flags: 1
            Unknown (vwi: always 0?): 0
            Article index at start of record or first article index, relative to parent section (fvwi): 15 [17 absolute]
            Number of article nodes in the record (byte): 5

        If there was only one article in the record, the last two bytes would be replaced by a single byte: f0

Records with a section transition
-----------------------------------

In such a record there is a transition from one section to the next. As such the record must have at least one article ending and one article starting.

TODO: Note you have to test the case of a single transition and multiple transitions

Ending record
----------------

Logically, ending records must have at least one article ending, one section ending and the periodical ending. They are of TBS type 2, like this::

    Record #17: Starts at: 65536 Ends at: 68684
        Contains: 4 index entries (3 ends, 1 complete, 0 starts)
    TBS bytes: 82 80 c0 4 f4 2
        Ends:
            Index Entry: 0 (Parent index: -1, Depth: 0, Offset: 215, Size: 68470) [j_x's Google reader]
            Index Entry: 4 (Parent index: 0, Depth: 1, Offset: 51234, Size: 17451) [Slashdot]
            Index Entry: 43 (Parent index: 4, Depth: 2, Offset: 65422, Size: 1717) [US ITC May Reverse Judge&#39;s Ruling In Kodak vs. Apple]
        Complete:
            Index Entry: 44 (Parent index: 4, Depth: 2, Offset: 67139, Size: 1546) [Google Starts Testing Google Music Internally]
    TBS Type: 010 (2)
    Outer Index entry: 0
    Unknown (vwi: always 0?): 0
    Parent section index (fvwi): 4
    Flags: 0
    Article at start of block as offset from parent index (fvwi): 39 [43 absolute]
    Number of nodes (byte): 2

If the record had only a single article end, the last two bytes would be replaced with: f0

