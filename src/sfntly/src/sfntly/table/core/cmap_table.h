/*
 * Copyright 2011 Google Inc. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_CMAP_TABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_CMAP_TABLE_H_

// type.h needs to be included first because of building issues on Windows
// Type aliases we delcare are defined in other headers and make the build
// fail otherwise.
#include "sfntly/port/type.h"
#include <vector>
#include <map>

#include "sfntly/port/refcount.h"
#include "sfntly/table/subtable.h"
#include "sfntly/table/subtable_container_table.h"

namespace sfntly {

// CMap subtable formats
struct CMapFormat {
  enum {
    kFormat0 = 0,
    kFormat2 = 2,
    kFormat4 = 4,
    kFormat6 = 6,
    kFormat8 = 8,
    kFormat10 = 10,
    kFormat12 = 12,
    kFormat13 = 13,
    kFormat14 = 14
  };
};

// A CMap table
class CMapTable : public SubTableContainerTable, public RefCounted<CMapTable> {
public:
  // CMapTable::CMapId
  struct CMapId {
    int32_t platform_id;
    int32_t encoding_id;
    bool operator==(const CMapId& obj) const {
      return platform_id == obj.platform_id && encoding_id == obj.encoding_id;
    }
  };
  static CMapId WINDOWS_BMP;
  static CMapId WINDOWS_UCS4;
  static CMapId MAC_ROMAN;

  // CMapTable::CMapIdComparator
  class CMapIdComparator {
   public:
    bool operator()(const CMapId& lhs, const CMapId& rhs) const;
  };

  // A filter on cmap
  // CMapTable::CMapFilter
  class CMapFilter {
   public:
    // Test on whether the cmap is acceptable or not
    // @param cmap_id the id of the cmap
    // @return true if the cmap is acceptable; false otherwise
    virtual bool accept(const CMapId& cmap_id) const = 0;
    // Make gcc -Wnon-virtual-dtor happy.
    virtual ~CMapFilter() {}
  };

  // Filters CMaps by CMapId to implement CMapTable::get()
  // wanted_id is the CMap we'd like to find.
  // We compare the current CMap to it either by equality (==) or using a
  // comparator.
  // CMapTable::CMapIdFilter
  class CMapIdFilter : public CMapFilter {
   public:
    explicit CMapIdFilter(const CMapId wanted_id);
    CMapIdFilter(const CMapId wanted_id,
                 const CMapIdComparator* comparator);
    ~CMapIdFilter() {}
    virtual bool accept(const CMapId& cmap_id) const;
   private:
    CMapIdFilter& operator=(const CMapIdFilter& that);
    const CMapId wanted_id_;
    const CMapIdComparator *comparator_;
  };

  // The abstract base class for all cmaps.
  //
  // CMap equality is based on the equality of the (@link {@link CMapId} that
  // defines the CMap. In the cmap table for a font there can only be one cmap
  // with a given cmap id (pair of platform and encoding ids) no matter what the
  // type of the cmap is.
  //
  // The cmap offers CharacterIterator to allow iteration over
  // characters that are mapped by the cmap. This iteration mostly returns the
  // characters mapped by the cmap. It will return all characters mapped by the
  // cmap to anything but .notdef <b>but</b> it may return some that are not
  // mapped or are mapped to .notdef. Various cmap tables provide ranges and
  // such to describe characters for lookup but without going the full way to
  // mapping to the glyph id it isn't always possible to tell if a character
  // will end up with a valid glyph id. So, some of the characters returned from
  // the Iterator may still end up pointing to the .notdef glyph. However, the
  // number of such characters should be small in most cases with well designed
  // cmaps.
  class Builder;
  class CMap : public SubTable {
   public:
    // CMapTable::CMap::Builder
    class Builder : public SubTable::Builder {
     public:
      virtual ~Builder();

      CALLER_ATTACH static Builder*
          GetBuilder(ReadableFontData* data,
                     int32_t offset,
                     const CMapId& cmap_id);
      CALLER_ATTACH static Builder*
          GetBuilder(int32_t format,
                     const CMapId& cmap_id);

      // Note: yes, an object is returned on stack since it's small enough.
      virtual CMapId cmap_id() { return cmap_id_; }
      virtual int32_t platform_id() { return cmap_id_.platform_id; }
      virtual int32_t encoding_id() { return cmap_id_.encoding_id; }
      virtual int32_t format() { return format_; }
      virtual int32_t language() { return language_; }
      virtual void set_language(int32_t language) { language_ = language; }

     protected:
      Builder(ReadableFontData* data,
              int32_t format,
              const CMapId& cmap_id);
      Builder(WritableFontData* data,
              int32_t format,
              const CMapId& cmap_id);

      virtual int32_t SubSerialize(WritableFontData* new_data);
      virtual bool SubReadyToSerialize();
      virtual int32_t SubDataSizeToSerialize();
      virtual void SubDataSet();

     private:
      int32_t format_;
      CMapId cmap_id_;
      int32_t language_;

      friend class CMapTable::Builder;
    };
    // Abstract CMap character iterator
    // The fully qualified name is CMapTable::CMap::CharacterIterator
    class CharacterIterator {
     public:
      virtual ~CharacterIterator() {}
      virtual bool HasNext() = 0;
      // Returns -1 if there are no more characters to iterate through
      // and exceptions are turned off
      virtual int32_t Next() = 0;

     protected:
      // Use the CMap::Iterator method below instead of directly requesting
      // a CharacterIterator.
      CharacterIterator() {}
    };

    CMap(ReadableFontData* data, int32_t format, const CMapId& cmap_id);
    virtual ~CMap();

    virtual CMap::CharacterIterator* Iterator() = 0;

    virtual int32_t format() { return format_; }
    virtual CMapId cmap_id() { return cmap_id_; }
    virtual int32_t platform_id() { return cmap_id_.platform_id; }
    virtual int32_t encoding_id() { return cmap_id_.encoding_id; }

    // Get the language of the cmap.
    //
    // Note on the language field in 'cmap' subtables: The language field must
    // be set to zero for all cmap subtables whose platform IDs are other than
    // Macintosh (platform ID 1). For cmap subtables whose platform IDs are
    // Macintosh, set this field to the Macintosh language ID of the cmap
    // subtable plus one, or to zero if the cmap subtable is not
    // language-specific. For example, a Mac OS Turkish cmap subtable must set
    // this field to 18, since the Macintosh language ID for Turkish is 17. A
    // Mac OS Roman cmap subtable must set this field to 0, since Mac OS Roman
    // is not a language-specific encoding.
    //
    // @return the language id
    virtual int32_t Language() = 0;

    // Gets the glyph id for the character code provided.
    // The character code provided must be in the encoding used by the cmap
    // table.
    virtual int32_t GlyphId(int32_t character) = 0;

   private:
    int32_t format_;
    CMapId cmap_id_;
  };
  typedef Ptr<CMap> CMapPtr;
  typedef Ptr<CMap::Builder> CMapBuilderPtr;
  typedef std::map<CMapId, CMapBuilderPtr, CMapIdComparator> CMapBuilderMap;

  // A cmap format 0 sub table
  class CMapFormat0 : public CMap, public RefCounted<CMapFormat0> {
   public:
    // The fully qualified name is CMapTable::CMapFormat0::Builder
    class Builder : public CMap::Builder,
                    public RefCounted<Builder> {
     public:
      CALLER_ATTACH static Builder* NewInstance(ReadableFontData* data,
                                                int32_t offset,
                                                const CMapId& cmap_id);
      CALLER_ATTACH static Builder* NewInstance(WritableFontData* data,
                                                int32_t offset,
                                                const CMapId& cmap_id);
      CALLER_ATTACH static Builder* NewInstance(const CMapId& cmap_id);
      virtual ~Builder();

     protected:
      virtual CALLER_ATTACH FontDataTable*
          SubBuildTable(ReadableFontData* data);

     private:
      // When creating a new CMapFormat0 Builder, use NewInstance instead of
      // the constructors! This avoids a memory leak when slicing the FontData.
      Builder(ReadableFontData* data, int32_t offset, const CMapId& cmap_id);
      Builder(WritableFontData* data, int32_t offset, const CMapId& cmap_id);
      Builder(const CMapId& cmap_id);
    };

    // The fully qualified name is CMapTable::CMapFormat0::CharacterIterator
    class CharacterIterator : public CMap::CharacterIterator {
     public:
      virtual ~CharacterIterator();
      virtual bool HasNext();
      virtual int32_t Next();

     private:
      CharacterIterator(int32_t start, int32_t end);
      friend class CMapFormat0;
      int32_t character_, max_character_;
    };

    virtual ~CMapFormat0();
    virtual int32_t Language();
    virtual int32_t GlyphId(int32_t character);
    CMap::CharacterIterator* Iterator();

   private:
    CMapFormat0(ReadableFontData* data, const CMapId& cmap_id);
  };

  // A cmap format 2 sub table
  // The format 2 cmap is used for multi-byte encodings such as SJIS,
  // EUC-JP/KR/CN, Big5, etc.
  class CMapFormat2 : public CMap, public RefCounted<CMapFormat2> {
   public:
    // CMapTable::CMapFormat2::Builder
    class Builder : public CMap::Builder,
                    public RefCounted<Builder> {
     public:
      Builder(ReadableFontData* data,
              int32_t offset,
              const CMapId& cmap_id);
      Builder(WritableFontData* data,
              int32_t offset,
              const CMapId& cmap_id);
      virtual ~Builder();

     protected:
      virtual CALLER_ATTACH FontDataTable*
          SubBuildTable(ReadableFontData* data);
    };
    // CMapTable::CMapFormat2::CharacterIterator
    class CharacterIterator : public CMap::CharacterIterator {
     public:
      virtual ~CharacterIterator();
      virtual bool hasNext();
      virtual int32_t next();

     private:
      CharacterIterator();
    };

    virtual int32_t Language();
    virtual int32_t GlyphId(int32_t character);

    // Returns how many bytes would be consumed by a lookup of this character
    // with this cmap. This comes about because the cmap format 2 table is
    // designed around multi-byte encodings such as SJIS, EUC-JP, Big5, etc.
    // return the number of bytes consumed from this "character" - either 1 or 2
    virtual int32_t BytesConsumed(int32_t character);

    virtual ~CMapFormat2();

   private:
    CMapFormat2(ReadableFontData* data, const CMapId& cmap_id);

    int32_t SubHeaderOffset(int32_t sub_header_index);
    int32_t FirstCode(int32_t sub_header_index);
    int32_t EntryCount(int32_t sub_header_index);
    int32_t IdRangeOffset(int32_t sub_header_index);
    int32_t IdDelta(int32_t sub_header_index);
    CMap::CharacterIterator* Iterator();
  };

    // CMapTable::CMapFormat4
  class CMapFormat4 : public CMap,
                      public RefCounted<CMapFormat4> {
   public:
    // CMapTable::CMapFormat4::Builder
    class Builder : public CMap::Builder,
                    public RefCounted<Builder> {
     public:
        // CMapTable::CMapFormat4::Builder::Segment
      class Segment : public RefCounted<Segment> {
       public:
        Segment();
        explicit Segment(Segment* other);
        Segment(int32_t start_count,
                int32_t end_count,
                int32_t id_delta,
                int32_t id_range_offset);
        ~Segment();

        // @return the startCount
        int32_t start_count();
        // @param startCount the startCount to set
        void set_start_count(int32_t start_count);
        // @return the endCount
        int32_t end_count();
        // @param endcount the endCount to set
        void set_end_count(int32_t end_count);
        // @return the idDelta
        int32_t id_delta();
        // @param idDelta the idDelta to set
        void set_id_delta(int32_t id_delta);
        // @return the idRangeOffset
        int32_t id_range_offset();
        // @param idRangeOffset the idRangeOffset to set
        void set_id_range_offset(int32_t id_range_offset);

        static CALLER_ATTACH
        std::vector<Ptr<Segment> >*
        DeepCopy(std::vector<Ptr<Segment> >* original);

       private:
        int32_t start_count_;
        int32_t end_count_;
        int32_t id_delta_;
        int32_t id_range_offset_;
      };
      typedef std::vector<Ptr<Segment> > SegmentList;

      static CALLER_ATTACH Builder* NewInstance(WritableFontData* data,
                                                int32_t offset,
                                                const CMapId& cmap_id);
      static CALLER_ATTACH Builder* NewInstance(ReadableFontData* data,
                                                int32_t offset,
                                                const CMapId& cmap_id);
      static CALLER_ATTACH Builder* NewInstance(const CMapId& cmap_id);
      virtual ~Builder();
      SegmentList* segments();
      void set_segments(SegmentList* segments);
      IntegerList* glyph_id_array();
      void set_glyph_id_array(IntegerList* glyph_id_array);

     protected:
      Builder(WritableFontData* data, int32_t offset, const CMapId& cmap_id);
      Builder(ReadableFontData* data, int32_t offset, const CMapId& cmap_id);
      Builder(SegmentList* segments, IntegerList* glyph_id_array,
              const CMapId& cmap_id);
      explicit Builder(const CMapId& cmap_id);

      virtual CALLER_ATTACH FontDataTable* SubBuildTable(
          ReadableFontData* data);
      virtual void SubDataSet();
      virtual int32_t SubDataSizeToSerialize();
      virtual bool SubReadyToSerialize();
      virtual int32_t SubSerialize(WritableFontData* new_data);

     private:
      void Initialize(ReadableFontData* data);

      SegmentList segments_;
      IntegerList glyph_id_array_;
    };

    CMap::CharacterIterator* Iterator();
    // CMapTable::CMapFormat4::CharacterIterator
    class CharacterIterator : public CMap::CharacterIterator {
     public:
      bool HasNext();
      int32_t Next();
      virtual ~CharacterIterator() {}

     private:
      explicit CharacterIterator(CMapFormat4 *parent);
      friend CMap::CharacterIterator* CMapFormat4::Iterator();

      CMapFormat4* parent_;
      int32_t segment_index_;
      int32_t first_char_in_segment_;
      int32_t last_char_in_segment_;
      int32_t next_char_;
      bool next_char_set_;
    };

    virtual int32_t GlyphId(int32_t character);

    // Lower level glyph code retrieval that requires processing the Format 4
    // segments to use.
    // @param segment the cmap segment
    // @param startCode the start code for the segment
    // @param character the character to be looked up
    // @return the glyph id for the character; CMapTable.NOTDEF if not found
    int32_t RetrieveGlyphId(int32_t segment,
                            int32_t start_count,
                            int32_t character);
    virtual int32_t Language();

    // Get the count of the number of segments in this cmap.
    // @return the number of segments
    int32_t seg_count();
    int32_t Length();
    // Get the start code for a segment.
    // @param segment the segment in the lookup table
    // @return the start code for a segment
    int32_t StartCode(int32_t segment);
    // Get the end code for a segment.
    // @param segment the segment in the look up table
    // @return the end code for the segment
    int32_t EndCode(int32_t segment);
    // Get the id delta for a segment
    // @param segment the segment in the look up table
    // @return the id delta for the segment
    int32_t IdDelta(int32_t segment);
    // Get the id range offset for a segment
    // @param segment the segment in the look up table
    // @return the id range offset for the segment
    int32_t IdRangeOffset(int32_t segment);
    // Get the location of the id range offset for a segment
    // @param segment the segment in the look up table
    // @return the location of the id range offset for the segment
    int32_t IdRangeOffsetLocation(int32_t segment);
    // Declared above to allow friending inside CharacterIterator class.
    // CMap::CharacterIterator* Iterator();
    virtual ~CMapFormat4();

   protected:
    CMapFormat4(ReadableFontData* data, const CMapId& cmap_id);

   private:
    static int32_t Language(ReadableFontData* data);
    static int32_t Length(ReadableFontData* data);
    static int32_t SegCount(ReadableFontData* data);
    static int32_t StartCode(ReadableFontData* data,
                             int32_t seg_count,
                             int32_t index);
    static int32_t StartCodeOffset(int32_t seg_count);
    static int32_t EndCode(ReadableFontData* data,
                           int32_t seg_count,
                           int32_t index);
    static int32_t IdDelta(ReadableFontData* data,
                           int32_t seg_count,
                           int32_t index);
    static int32_t IdDeltaOffset(int32_t seg_count);
    static int32_t IdRangeOffset(ReadableFontData* data,
                                 int32_t seg_count,
                                 int32_t index);
    static int32_t IdRangeOffsetOffset(int32_t seg_count);
    static int32_t GlyphIdArrayOffset(int32_t seg_count);
    // Refactored void to bool to work without exceptions.
    bool IsValidIndex(int32_t segment);
    int32_t GlyphIdArray(int32_t index);

    int32_t seg_count_;
    int32_t start_code_offset_;
    int32_t end_code_offset_;
    int32_t id_delta_offset_;
    int32_t id_range_offset_offset_;
    int32_t glyph_id_array_offset_;
  };

  // CMapTable::Builder
  class Builder : public SubTableContainerTable::Builder,
                  public RefCounted<Builder> {
   public:
    // Constructor scope is public because C++ does not allow base class to
    // instantiate derived class with protected constructors.
    Builder(Header* header, WritableFontData* data);
    Builder(Header* header, ReadableFontData* data);
    virtual ~Builder();

    virtual int32_t SubSerialize(WritableFontData* new_data);
    virtual bool SubReadyToSerialize();
    virtual int32_t SubDataSizeToSerialize();
    virtual void SubDataSet();
    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);

    static CALLER_ATTACH Builder* CreateBuilder(Header* header,
                                                WritableFontData* data);

    CMap::Builder* NewCMapBuilder(const CMapId& cmap_id,
                                  ReadableFontData* data);
    // Create a new empty CMapBuilder of the type specified in the id.
    CMap::Builder* NewCMapBuilder(int32_t format, const CMapId& cmap_id);
    CMap::Builder* CMapBuilder(const CMapId& cmap_id);

    int32_t NumCMaps();
    void SetVersion(int32_t version);

    CMapBuilderMap* GetCMapBuilders();

   protected:
    static CALLER_ATTACH CMap::Builder* CMapBuilder(ReadableFontData* data,
                                                    int32_t index);

   private:
    void Initialize(ReadableFontData* data);
    static int32_t NumCMaps(ReadableFontData* data);

    int32_t version_;
    CMapBuilderMap cmap_builders_;
  };
  typedef Ptr<Builder> CMapTableBuilderPtr;

  class CMapIterator {
   public:
    // If filter is NULL, filter through all tables.
    CMapIterator(CMapTable* table, const CMapFilter* filter);
    bool HasNext();
    CMap* Next();

   private:
    int32_t table_index_;
    const CMapFilter* filter_;
    CMapTable* table_;
  };

  // Make a CMapId from a platform_id, encoding_id pair
  static CMapId NewCMapId(int32_t platform_id, int32_t encoding_id);
  // Make a CMapId from another CMapId
  static CMapId NewCMapId(const CMapId& obj);

  // Get the CMap with the specified parameters if it exists.
  // Returns NULL otherwise.
  CALLER_ATTACH CMap* GetCMap(const int32_t index);
  CALLER_ATTACH CMap* GetCMap(const int32_t platform_id,
                              const int32_t encoding_id);
  CALLER_ATTACH CMap* GetCMap(const CMapId GetCMap_id);

  // Get the table version.
  virtual int32_t Version();

  // Get the number of cmaps within the CMap table.
  virtual int32_t NumCMaps();

  // Get the cmap id for the cmap with the given index.
  // Note: yes, an object is returned on stack since it's small enough.
  //       This function is renamed from cmapId to GetCMapId().
  virtual CMapId GetCMapId(int32_t index);

  virtual int32_t PlatformId(int32_t index);
  virtual int32_t EncodingId(int32_t index);

  // Get the offset in the table data for the cmap table with the given index.
  // The offset is from the beginning of the table.
  virtual int32_t Offset(int32_t index);

  virtual ~CMapTable();

  static const int32_t NOTDEF;

 private:
  // Offsets to specific elements in the underlying data. These offsets are
  // relative to the start of the table or the start of sub-blocks within
  // the table.
  struct Offset {
    enum {
      kVersion = 0,
      kNumTables = 2,
      kEncodingRecordStart = 4,

      // offsets relative to the encoding record
      kEncodingRecordPlatformId = 0,
      kEncodingRecordEncodingId = 2,
      kEncodingRecordOffset = 4,
      kEncodingRecordSize = 8,

      kFormat = 0,

      // Format 0: Byte encoding table
      kFormat0Format = 0,
      kFormat0Length = 2,
      kFormat0Language = 4,
      kFormat0GlyphIdArray = 6,

      // Format 2: High-byte mapping through table
      kFormat2Format = 0,
      kFormat2Length = 2,
      kFormat2Language = 4,
      kFormat2SubHeaderKeys = 6,
      kFormat2SubHeaders = 518,
      // offset relative to the subHeader structure
      kFormat2SubHeader_firstCode = 0,
      kFormat2SubHeader_entryCount = 2,
      kFormat2SubHeader_idDelta = 4,
      kFormat2SubHeader_idRangeOffset = 6,
      kFormat2SubHeader_structLength = 8,

      // Format 4: Segment mapping to delta values
      kFormat4Format = 0,
      kFormat4Length = 2,
      kFormat4Language = 4,
      kFormat4SegCountX2 = 6,
      kFormat4SearchRange = 8,
      kFormat4EntrySelector = 10,
      kFormat4RangeShift = 12,
      kFormat4EndCount = 14,
      kFormat4FixedSize = 16,

      // format 6: Trimmed table mapping
      kFormat6Format = 0,
      kFormat6Length = 2,
      kFormat6Language = 4,
      kFormat6FirstCode = 6,
      kFormat6EntryCount = 8,
      kFormat6GlyphIdArray = 10,

      // Format 8: mixed 16-bit and 32-bit coverage
      kFormat8Format = 0,
      kFormat8Length = 4,
      kFormat8Language = 8,
      kFormat8Is32 = 12,
      kFormat8nGroups204 = 8204,
      kFormat8Groups208 = 8208,
      // offset relative to the group structure
      kFormat8Group_startCharCode = 0,
      kFormat8Group_endCharCode = 4,
      kFormat8Group_startGlyphId = 8,
      kFormat8Group_structLength = 12,

      // Format 10: Trimmed array
      kFormat10Format = 0,
      kFormat10Length = 4,
      kFormat10Language = 8,
      kFormat10StartCharCode = 12,
      kFormat10NumChars = 16,
      kFormat10Glyphs0 = 20,

      // Format 12: Segmented coverage
      kFormat12Format = 0,
      kFormat12Length = 4,
      kFormat12Language = 8,
      kFormat12nGroups = 12,
      kFormat12Groups = 16,
      kFormat12Groups_structLength = 12,
      // offsets within the group structure
      kFormat12_startCharCode = 0,
      kFormat12_endCharCode = 4,
      kFormat12_startGlyphId = 8,

      // Format 13: Last Resort Font
      kFormat13Format = 0,
      kFormat13Length = 4,
      kFormat13Language = 8,
      kFormat13nGroups = 12,
      kFormat13Groups = 16,
      kFormat13Groups_structLength = 12,
      // offsets within the group structure
      kFormat13_startCharCode = 0,
      kFormat13_endCharCode = 4,
      kFormat13_glyphId = 8,

      // Format 14: Unicode Variation Sequences
      kFormat14Format = 0,
      kFormat14Length = 2,

      // TODO(stuartg): finish tables
      // Default UVS Table

      // Non-default UVS Table
      kLast = -1
    };
  };

  CMapTable(Header* header, ReadableFontData* data);

  // Get the offset in the table data for the encoding record for the cmap with
  // the given index. The offset is from the beginning of the table.
  static int32_t OffsetForEncodingRecord(int32_t index);
};
typedef std::vector<CMapTable::CMapId> CMapIdList;
typedef Ptr<CMapTable> CMapTablePtr;
typedef std::vector<Ptr<CMapTable::CMapFormat4::Builder::Segment> > SegmentList;
}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_CMAP_TABLE_H_
