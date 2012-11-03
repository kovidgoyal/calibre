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

#ifndef SFNTLY_CPP_SRC_SFNTLY_FONT_H_
#define SFNTLY_CPP_SRC_SFNTLY_FONT_H_

#include <vector>

#include "sfntly/port/refcount.h"
#include "sfntly/port/type.h"
#include "sfntly/port/endian.h"
#include "sfntly/data/font_input_stream.h"
#include "sfntly/data/font_output_stream.h"
#include "sfntly/data/writable_font_data.h"
#include "sfntly/table/table.h"

namespace sfntly {

// Note: following constants are embedded in Font class in Java.  They are
//       extracted out for easier reference from other classes.  Offset is the
//       one that is kept within class.
// Platform ids. These are used in a number of places within the font whenever
// the platform needs to be specified.
struct PlatformId {
  enum {
    kUnknown = -1,
    kUnicode = 0,
    kMacintosh = 1,
    kISO = 2,
    kWindows = 3,
    kCustom = 4
  };
};

// Unicode encoding ids. These are used in a number of places within the font
// whenever character encodings need to be specified.
struct UnicodeEncodingId {
  enum {
    kUnknown = -1,
    kUnicode1_0 = 0,
    kUnicode1_1 = 1,
    kISO10646 = 2,
    kUnicode2_0_BMP = 3,
    kUnicode2_0 = 4,
    kUnicodeVariationSequences = 5
  };
};

// Windows encoding ids. These are used in a number of places within the font
// whenever character encodings need to be specified.
struct WindowsEncodingId {
  enum {
    kUnknown = 0xffffffff,
    kSymbol = 0,
    kUnicodeUCS2 = 1,
    kShiftJIS = 2,
    kPRC = 3,
    kBig5 = 4,
    kWansung = 5,
    kJohab = 6,
    kUnicodeUCS4 = 10
  };
};

// Macintosh encoding ids. These are used in a number of places within the
// font whenever character encodings need to be specified.
struct MacintoshEncodingId {
  // Macintosh Platform Encodings
  enum {
    kUnknown = -1,
    kRoman = 0,
    kJapanese = 1,
    kChineseTraditional = 2,
    kKorean = 3,
    kArabic = 4,
    kHebrew = 5,
    kGreek = 6,
    kRussian = 7,
    kRSymbol = 8,
    kDevanagari = 9,
    kGurmukhi = 10,
    kGujarati = 11,
    kOriya = 12,
    kBengali = 13,
    kTamil = 14,
    kTelugu = 15,
    kKannada = 16,
    kMalayalam = 17,
    kSinhalese = 18,
    kBurmese = 19,
    kKhmer = 20,
    kThai = 21,
    kLaotian = 22,
    kGeorgian = 23,
    kArmenian = 24,
    kChineseSimplified = 25,
    kTibetan = 26,
    kMongolian = 27,
    kGeez = 28,
    kSlavic = 29,
    kVietnamese = 30,
    kSindhi = 31,
    kUninterpreted = 32
  };
};

class FontFactory;

// An sfnt container font object. This object is immutable and thread safe. To
// construct one use an instance of Font::Builder.
class Font : public RefCounted<Font> {
 public:
  // A builder for a font object. The builder allows the for the creation of
  // immutable Font objects. The builder is a one use non-thread safe object and
  // once the Font object has been created it is no longer usable. To create a
  // further Font object new builder will be required.
  class Builder : public RefCounted<Builder> {
   public:
    virtual ~Builder();

    static CALLER_ATTACH Builder*
        GetOTFBuilder(FontFactory* factory, InputStream* is);
    static CALLER_ATTACH Builder*
        GetOTFBuilder(FontFactory* factory,
                      WritableFontData* ba,
                      int32_t offset_to_offset_table);
    static CALLER_ATTACH Builder* GetOTFBuilder(FontFactory* factory);

    // Get the font factory that created this font builder.
    FontFactory* GetFontFactory() { return factory_; }

    // Is the font ready to build?
    bool ReadyToBuild();

    // Build the Font. After this call this builder will no longer be usable.
    CALLER_ATTACH Font* Build();

    // Set a unique fingerprint for the font object.
    void SetDigest(ByteVector* digest);

    // Clear all table builders.
    void ClearTableBuilders();

    // Does this font builder have the specified table builder.
    bool HasTableBuilder(int32_t tag);

    // Get the table builder for the given tag. If there is no builder for that
    // tag then return a null.
    Table::Builder* GetTableBuilder(int32_t tag);

    // Creates a new table builder for the table type given by the table id tag.
    // This new table has been added to the font and will replace any existing
    // builder for that table.
    // @return new empty table of the type specified by tag; if tag is not known
    //         then a generic OpenTypeTable is returned
    virtual Table::Builder* NewTableBuilder(int32_t tag);

    // Creates a new table builder for the table type given by the table id tag.
    // It makes a copy of the data provided and uses that copy for the table.
    // This new table has been added to the font and will replace any existing
    // builder for that table.
    virtual Table::Builder* NewTableBuilder(int32_t tag,
                                            ReadableFontData* src_data);

    // Get a map of the table builders in this font builder accessed by table
    // tag.
    virtual TableBuilderMap* table_builders() { return &table_builders_; }

    // Remove the specified table builder from the font builder.
    // Note: different from Java: we don't return object in removeTableBuilder
    virtual void RemoveTableBuilder(int32_t tag);

    // Get the number of table builders in the font builder.
    virtual int32_t number_of_table_builders() {
      return (int32_t)table_builders_.size();
    }

   private:
    explicit Builder(FontFactory* factory);
    virtual void LoadFont(InputStream* is);
    virtual void LoadFont(WritableFontData* wfd,
                          int32_t offset_to_offset_table);
    int32_t SfntWrapperSize();
    void BuildAllTableBuilders(DataBlockMap* table_data,
                               TableBuilderMap* builder_map);
    CALLER_ATTACH Table::Builder*
        GetTableBuilder(Header* header, WritableFontData* data);
    void BuildTablesFromBuilders(Font* font,
                                 TableBuilderMap* builder_map,
                                 TableMap* tables);
    static void InterRelateBuilders(TableBuilderMap* builder_map);

    void ReadHeader(FontInputStream* is,
                    HeaderOffsetSortedSet* records);

    void ReadHeader(ReadableFontData* fd,
                    int32_t offset,
                    HeaderOffsetSortedSet* records);

    void LoadTableData(HeaderOffsetSortedSet* headers,
                       FontInputStream* is,
                       DataBlockMap* table_data);

    void LoadTableData(HeaderOffsetSortedSet* headers,
                       WritableFontData* fd,
                       DataBlockMap* table_data);

    TableBuilderMap table_builders_;
    FontFactory* factory_;  // dumb pointer, avoid circular refcounting
    int32_t sfnt_version_;
    int32_t num_tables_;
    int32_t search_range_;
    int32_t entry_selector_;
    int32_t range_shift_;
    DataBlockMap data_blocks_;
    ByteVector digest_;
  };

  virtual ~Font();

  // Gets the sfnt version set in the sfnt wrapper of the font.
  int32_t sfnt_version();

  // Gets a copy of the fonts digest that was created when the font was read. If
  // no digest was set at creation time then the return result will be null.
  ByteVector* digest();

  // Get the checksum for this font.
  int64_t checksum();

  // Get the number of tables in this font.
  int32_t num_tables();

  // Whether the font has a particular table.
  bool HasTable(int32_t tag);

  // UNIMPLEMENTED: public Iterator<? extends Table> iterator

  // Get the table in this font with the specified id.
  // @param tag the identifier of the table
  // @return the table specified if it exists; null otherwise
  // C++ port: rename table() to GetTable()
  Table* GetTable(int32_t tag);

  // Get a map of the tables in this font accessed by table tag.
  // @return an unmodifiable view of the tables in this font
  // Note: renamed tableMap() to GetTableMap()
  const TableMap* GetTableMap();

  // UNIMPLEMENTED: toString()

  // Serialize the font to the output stream.
  // @param os the destination for the font serialization
  // @param tableOrdering the table ordering to apply
  void Serialize(OutputStream* os, IntegerList* table_ordering);

 private:
  // Offsets to specific elements in the underlying data. These offsets are
  // relative to the start of the table or the start of sub-blocks within the
  // table.
  struct Offset {
    enum {
      // Offsets within the main directory
      kSfntVersion = 0,
      kNumTables = 4,
      kSearchRange = 6,
      kEntrySelector = 8,
      kRangeShift = 10,
      kTableRecordBegin = 12,
      kSfntHeaderSize = 12,

      // Offsets within a specific table record
      kTableTag = 0,
      kTableCheckSum = 4,
      kTableOffset = 8,
      kTableLength = 12,
      kTableRecordSize = 16
    };
  };

  // Note: the two constants are moved to tag.h to avoid VC++ bug.
//  static const int32_t CFF_TABLE_ORDERING[];
//  static const int32_t TRUE_TYPE_TABLE_ORDERING[];

  // Constructor.
  // @param sfntVersion the sfnt version
  // @param digest the computed digest for the font; null if digest was not
  //        computed
  // Note: Current C++ port does not support SHA digest validation.
  Font(int32_t sfnt_version, ByteVector* digest);

  // Build the table headers to be used for serialization. These headers will be
  // filled out with the data required for serialization. The headers will be
  // sorted in the order specified and only those specified will have headers
  // generated.
  // @param tableOrdering the tables to generate headers for and the order to
  //        sort them
  // @return a list of table headers ready for serialization
  void BuildTableHeadersForSerialization(IntegerList* table_ordering,
                                         TableHeaderList* table_headers);

  // Searialize the headers.
  // @param fos the destination stream for the headers
  // @param tableHeaders the headers to serialize
  // @throws IOException
  void SerializeHeader(FontOutputStream* fos, TableHeaderList* table_headers);

  // Serialize the tables.
  // @param fos the destination stream for the headers
  // @param tableHeaders the headers for the tables to serialize
  // @throws IOException
  void SerializeTables(FontOutputStream* fos, TableHeaderList* table_headers);

  // Generate the full table ordering to used for serialization. The full
  // ordering uses the partial ordering as a seed and then adds all remaining
  // tables in the font in an undefined order.
  // @param defaultTableOrdering the partial ordering to be used as a seed for
  //        the full ordering
  // @param (out) table_ordering the full ordering for serialization
  void GenerateTableOrdering(IntegerList* default_table_ordering,
                             IntegerList* table_ordering);

  // Get the default table ordering based on the type of the font.
  // @param (out) default_table_ordering the default table ordering
  void DefaultTableOrdering(IntegerList* default_table_ordering);

  int32_t sfnt_version_;
  ByteVector digest_;
  int64_t checksum_;
  TableMap tables_;
};
typedef Ptr<Font> FontPtr;
typedef std::vector<FontPtr> FontArray;
typedef Ptr<Font::Builder> FontBuilderPtr;
typedef std::vector<FontBuilderPtr> FontBuilderArray;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_FONT_H_
