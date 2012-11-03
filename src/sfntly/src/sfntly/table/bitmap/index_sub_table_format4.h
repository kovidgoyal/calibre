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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_INDEX_SUBTABLE_FORMAT4_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_INDEX_SUBTABLE_FORMAT4_H_

#include "sfntly/table/bitmap/index_sub_table.h"

namespace sfntly {

class IndexSubTableFormat4 : public IndexSubTable,
                             public RefCounted<IndexSubTableFormat4> {
 public:
  class CodeOffsetPair {
   public:
    int32_t glyph_code() const { return glyph_code_; }
    int32_t offset() const { return offset_; }

   protected:
    CodeOffsetPair(int32_t glyph_code, int32_t offset);

    // TODO(arthurhsu): C++ style guide prohibits protected members.
    int32_t glyph_code_;
    int32_t offset_;
  };

  class CodeOffsetPairBuilder : public CodeOffsetPair {
   public:
    CodeOffsetPairBuilder();
    CodeOffsetPairBuilder(int32_t glyph_code, int32_t offset);
    void set_glyph_code(int32_t v) { glyph_code_ = v; }
    void set_offset(int32_t v) { offset_ = v; }
  };

  class CodeOffsetPairGlyphCodeComparator {
   public:
    bool operator()(const CodeOffsetPair& lhs, const CodeOffsetPair& rhs);
  };

  class Builder : public IndexSubTable::Builder,
                  public RefCounted<Builder> {
   public:
    class BitmapGlyphInfoIterator
        : public RefIterator<BitmapGlyphInfo, Builder, IndexSubTable::Builder> {
     public:
      explicit BitmapGlyphInfoIterator(Builder* container);
      virtual ~BitmapGlyphInfoIterator() {}

      virtual bool HasNext();
      CALLER_ATTACH virtual BitmapGlyphInfo* Next();

     private:
      int32_t code_offset_pair_index_;
    };

    virtual ~Builder();
    virtual int32_t NumGlyphs();
    virtual int32_t GlyphLength(int32_t glyph_id);
    virtual int32_t GlyphStartOffset(int32_t glyph_id);
    CALLER_ATTACH virtual BitmapGlyphInfoIterator* GetIterator();

    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);
    virtual void SubDataSet();
    virtual int32_t SubDataSizeToSerialize();
    virtual bool SubReadyToSerialize();
    virtual int32_t SubSerialize(WritableFontData* new_data);

    void Revert();
    void SetOffsetArray(const std::vector<CodeOffsetPairBuilder>& pair_array);

    static CALLER_ATTACH Builder* CreateBuilder();
    static CALLER_ATTACH Builder* CreateBuilder(ReadableFontData* data,
                                                int32_t index_sub_table_offset,
                                                int32_t first_glyph_index,
                                                int32_t last_glyph_index);
    static CALLER_ATTACH Builder* CreateBuilder(WritableFontData* data,
                                                int32_t index_sub_table_offset,
                                                int32_t first_glyph_index,
                                                int32_t last_glyph_index);
   private:
    Builder();
    Builder(WritableFontData* data,
            int32_t first_glyph_index,
            int32_t last_glyph_index);
    Builder(ReadableFontData* data,
            int32_t first_glyph_index,
            int32_t last_glyph_index);
    std::vector<CodeOffsetPairBuilder>* GetOffsetArray();
    void Initialize(ReadableFontData* data);
    int32_t FindCodeOffsetPair(int32_t glyph_id);

    static int32_t DataLength(ReadableFontData* data,
                              int32_t index_sub_table_offset,
                              int32_t first_glyph_index,
                              int32_t last_glyph_index);

    std::vector<CodeOffsetPairBuilder> offset_pair_array_;
  };

  virtual ~IndexSubTableFormat4();

  virtual int32_t NumGlyphs();
  virtual int32_t GlyphStartOffset(int32_t glyph_id);
  virtual int32_t GlyphLength(int32_t glyph_id);

 private:
  IndexSubTableFormat4(ReadableFontData* data,
                       int32_t first_glyph_index,
                       int32_t last_glyph_index);

  int32_t FindCodeOffsetPair(int32_t glyph_id);
  static int32_t NumGlyphs(ReadableFontData* data, int32_t table_offset);

  friend class Builder;
};
typedef Ptr<IndexSubTableFormat4> IndexSubTableFormat4Ptr;
typedef Ptr<IndexSubTableFormat4::Builder> IndexSubTableFormat4BuilderPtr;
typedef std::vector<IndexSubTableFormat4::CodeOffsetPairBuilder>
            CodeOffsetPairBuilderList;
}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_INDEX_SUBTABLE_FORMAT4_H_
