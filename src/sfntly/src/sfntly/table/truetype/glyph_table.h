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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_TRUETYPE_GLYPH_TABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_TRUETYPE_GLYPH_TABLE_H_

#include <vector>

#include "sfntly/table/table.h"
#include "sfntly/table/subtable.h"
#include "sfntly/table/subtable_container_table.h"

namespace sfntly {

struct GlyphType {
  enum {
    kSimple = 0,
    kComposite = 1
  };
};

class GlyphTable : public SubTableContainerTable,
                   public RefCounted<GlyphTable> {
 public:
  class Builder;
  class Glyph : public SubTable {
   public:
    // Note: Contour is an empty class for the version ported
    class Contour {
     protected:
      Contour() {}
      virtual ~Contour() {}
    };

    class Builder : public SubTable::Builder {
     public:
      virtual ~Builder();

     protected:
      // Incoming table_builder is GlyphTable::Builder*.
      // Note: constructor refactored in C++ to avoid heavy lifting.
      //       caller need to do data->Slice(offset, length) beforehand.
      explicit Builder(WritableFontData* data);
      explicit Builder(ReadableFontData* data);

      static CALLER_ATTACH Builder*
          GetBuilder(GlyphTable::Builder* table_builder,
                     ReadableFontData* data);
      static CALLER_ATTACH Builder*
          GetBuilder(GlyphTable::Builder* table_builder,
                     ReadableFontData* data,
                     int32_t offset,
                     int32_t length);
      virtual void SubDataSet();
      virtual int32_t SubDataSizeToSerialize();
      virtual bool SubReadyToSerialize();
      virtual int32_t SubSerialize(WritableFontData* new_data);

     private:
      int32_t format_;
      friend class GlyphTable::Builder;
    };

    virtual ~Glyph();
    static CALLER_ATTACH Glyph* GetGlyph(GlyphTable* table,
                                         ReadableFontData* data,
                                         int32_t offset,
                                         int32_t length);

    virtual int32_t Padding();
    virtual int32_t GlyphType();
    virtual int32_t NumberOfContours();
    virtual int32_t XMin();
    virtual int32_t XMax();
    virtual int32_t YMin();
    virtual int32_t YMax();

    virtual int32_t InstructionSize() = 0;
    virtual ReadableFontData* Instructions() = 0;

   protected:
    // Note: constructor refactored in C++ to avoid heavy lifting.
    //       caller need to do data->Slice(offset, length) beforehand.
    Glyph(ReadableFontData* data, int32_t glyph_type);
    virtual void Initialize() = 0;
    // Note: Derived class to define initialization_lock_.

   private:
    static int32_t GlyphType(ReadableFontData* data,
                             int32_t offset,
                             int32_t length);

    int32_t glyph_type_;
    int32_t number_of_contours_;
  };  // class GlyphTable::Glyph
  typedef Ptr<GlyphTable::Glyph::Builder> GlyphBuilderPtr;
  typedef std::vector<GlyphBuilderPtr> GlyphBuilderList;

  class Builder : public SubTableContainerTable::Builder,
                  public RefCounted<GlyphTable::Builder> {
   public:
    // Note: Constructor scope altered to public for base class to instantiate.
    Builder(Header* header, ReadableFontData* data);
    virtual ~Builder();

    virtual void SetLoca(const IntegerList& loca);
    virtual void GenerateLocaList(IntegerList* locas);

    static CALLER_ATTACH Builder* CreateBuilder(Header* header,
                                                WritableFontData* data);

    // Gets the List of glyph builders for the glyph table builder. These may be
    // manipulated in any way by the caller and the changes will be reflected in
    // the final glyph table produced.
    // If there is no current data for the glyph builder or the glyph builders
    // have not been previously set then this will return an empty glyph builder
    // List. If there is current data (i.e. data read from an existing font) and
    // the <code>loca</code> list has not been set or is null, empty, or
    // invalid, then an empty glyph builder List will be returned.
    GlyphBuilderList* GlyphBuilders();

    // Replace the internal glyph builders with the one provided. The provided
    // list and all contained objects belong to this builder.
    // This call is only required if the entire set of glyphs in the glyph
    // table builder are being replaced. If the glyph builder list provided from
    // the GlyphTable.Builder::GlyphBuilders() is being used and modified
    // then those changes will already be reflected in the glyph table builder.
    void SetGlyphBuilders(GlyphBuilderList* glyph_builders);

    // Glyph builder factories
    CALLER_ATTACH Glyph::Builder* GlyphBuilder(ReadableFontData* data);

   protected:  // internal API for building
    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);
    virtual void SubDataSet();
    virtual int32_t SubDataSizeToSerialize();
    virtual bool SubReadyToSerialize();
    virtual int32_t SubSerialize(WritableFontData* new_data);

   private:
    void Initialize(ReadableFontData* data, const IntegerList& loca);
    GlyphBuilderList* GetGlyphBuilders();
    void Revert();

    GlyphBuilderList glyph_builders_;
    IntegerList loca_;
  };

  class SimpleGlyph : public Glyph, public RefCounted<SimpleGlyph> {
   public:
    static const int32_t kFLAG_ONCURVE;
    static const int32_t kFLAG_XSHORT;
    static const int32_t kFLAG_YSHORT;
    static const int32_t kFLAG_REPEAT;
    static const int32_t kFLAG_XREPEATSIGN;
    static const int32_t kFLAG_YREPEATSIGN;

    class SimpleContour : public Glyph::Contour {
     protected:
      SimpleContour() {}
      virtual ~SimpleContour() {}
    };

    class SimpleGlyphBuilder : public Glyph::Builder,
                               public RefCounted<SimpleGlyphBuilder> {
     public:
      virtual ~SimpleGlyphBuilder();

     protected:
      // Note: constructor refactored in C++ to avoid heavy lifting.
      //       caller need to do data->Slice(offset, length) beforehand.
      explicit SimpleGlyphBuilder(WritableFontData* data);
      explicit SimpleGlyphBuilder(ReadableFontData* data);
      virtual CALLER_ATTACH FontDataTable*
          SubBuildTable(ReadableFontData* data);

     private:
      friend class Glyph::Builder;
    };

    // Note: constructor refactored in C++ to avoid heavy lifting.
    //       caller need to do data->Slice(offset, length) beforehand.
    explicit SimpleGlyph(ReadableFontData* data);
    virtual ~SimpleGlyph();

    virtual int32_t InstructionSize();
    virtual CALLER_ATTACH ReadableFontData* Instructions();
    virtual void Initialize();

    int32_t NumberOfPoints(int32_t contour);
    int32_t XCoordinate(int32_t contour, int32_t point);
    int32_t YCoordinate(int32_t contour, int32_t point);
    bool OnCurve(int32_t contour, int32_t point);

   private:
    void ParseData(bool fill_arrays);
    int32_t FlagAsInt(int32_t index);
    int32_t ContourEndPoint(int32_t contour);

    bool initialized_;
    Lock initialization_lock_;
    int32_t instruction_size_;
    int32_t number_of_points_;

    // start offsets of the arrays
    int32_t instructions_offset_;
    int32_t flags_offset_;
    int32_t x_coordinates_offset_;
    int32_t y_coordinates_offset_;

    int32_t flag_byte_count_;
    int32_t x_byte_count_;
    int32_t y_byte_count_;

    IntegerList x_coordinates_;
    IntegerList y_coordinates_;
    std::vector<bool> on_curve_;
    IntegerList contour_index_;
  };

  class CompositeGlyph : public Glyph, public RefCounted<CompositeGlyph> {
   public:
    static const int32_t kFLAG_ARG_1_AND_2_ARE_WORDS;
    static const int32_t kFLAG_ARGS_ARE_XY_VALUES;
    static const int32_t kFLAG_ROUND_XY_TO_GRID;
    static const int32_t kFLAG_WE_HAVE_A_SCALE;
    static const int32_t kFLAG_RESERVED;
    static const int32_t kFLAG_MORE_COMPONENTS;
    static const int32_t kFLAG_WE_HAVE_AN_X_AND_Y_SCALE;
    static const int32_t kFLAG_WE_HAVE_A_TWO_BY_TWO;
    static const int32_t kFLAG_WE_HAVE_INSTRUCTIONS;
    static const int32_t kFLAG_USE_MY_METRICS;
    static const int32_t kFLAG_OVERLAP_COMPOUND;
    static const int32_t kFLAG_SCALED_COMPONENT_OFFSET;
    static const int32_t kFLAG_UNSCALED_COMPONENT_OFFSET;

    class CompositeGlyphBuilder : public Glyph::Builder,
                                  public RefCounted<CompositeGlyphBuilder> {
     public:
      virtual ~CompositeGlyphBuilder();

     protected:
      // Note: constructor refactored in C++ to avoid heavy lifting.
      //       caller need to do data->Slice(offset, length) beforehand.
      explicit CompositeGlyphBuilder(WritableFontData* data);
      explicit CompositeGlyphBuilder(ReadableFontData* data);

      virtual CALLER_ATTACH FontDataTable*
          SubBuildTable(ReadableFontData* data);

     private:
      friend class Glyph::Builder;
    };

    // Note: constructor refactored in C++ to avoid heavy lifting.
    //       caller need to do data->Slice(offset, length) beforehand.
    explicit CompositeGlyph(ReadableFontData* data);
    virtual ~CompositeGlyph();

    int32_t Flags(int32_t contour);
    int32_t NumGlyphs();
    int32_t GlyphIndex(int32_t contour);
    int32_t Argument1(int32_t contour);
    int32_t Argument2(int32_t contour);
    int32_t TransformationSize(int32_t contour);
    void Transformation(int32_t contour, ByteVector* transformation);
    virtual int32_t InstructionSize();
    virtual CALLER_ATTACH ReadableFontData* Instructions();

   protected:
    virtual void Initialize();

   private:
    IntegerList contour_index_;
    int32_t instruction_size_;
    int32_t instructions_offset_;
    bool initialized_;
    Lock initialization_lock_;
  };

  virtual ~GlyphTable();

  // C++ port: rename glyph() to GetGlyph().
  Glyph* GetGlyph(int32_t offset, int32_t length);

 private:
  struct Offset {
    enum {
      // header
      kNumberOfContours = 0,
      kXMin = 2,
      kYMin = 4,
      kXMax = 6,
      kYMax = 8,

      // Simple Glyph Description
      kSimpleEndPtsOfCountours = 10,
      // offset from the end of the contours array
      kSimpleInstructionLength = 0,
      kSimpleInstructions = 2,
      // flags
      // xCoordinates
      // yCoordinates

      // Composite Glyph Description
      kCompositeFlags = 0,
      kCompositeGyphIndexWithoutFlag = 0,
      kCompositeGlyphIndexWithFlag = 2,
    };
  };

  GlyphTable(Header* header, ReadableFontData* data);
};
typedef Ptr<GlyphTable> GlyphTablePtr;
typedef Ptr<GlyphTable::Builder> GlyphTableBuilderPtr;
typedef std::vector<GlyphTableBuilderPtr> GlyphTableBuilderList;
typedef Ptr<GlyphTable::Glyph> GlyphPtr;
typedef Ptr<GlyphTable::Glyph::Builder> GlyphBuilderPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_TRUETYPE_GLYPH_TABLE_H_
