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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_MAXIMUM_PROFILE_TABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_MAXIMUM_PROFILE_TABLE_H_

#include "sfntly/port/refcount.h"
#include "sfntly/table/table.h"
#include "sfntly/table/table_based_table_builder.h"

namespace sfntly {

// A Maximum Profile table - 'maxp'.
class MaximumProfileTable : public Table,
                            public RefCounted<MaximumProfileTable> {
 public:
  // Builder for a Maximum Profile table - 'maxp'.
  class Builder : public TableBasedTableBuilder, public RefCounted<Builder> {
   public:
    // Constructor scope altered to public because C++ does not allow base
    // class to instantiate derived class with protected constructors.
    Builder(Header* header, WritableFontData* data);
    Builder(Header* header, ReadableFontData* data);
    virtual ~Builder();

    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);
    static CALLER_ATTACH Builder* CreateBuilder(Header* header,
                                                WritableFontData* data);

    int32_t TableVersion();
    void SetTableVersion(int32_t version);
    int32_t NumGlyphs();
    void SetNumGlyphs(int32_t num_glyphs);
    int32_t MaxPoints();
    void SetMaxPoints(int32_t max_points);
    int32_t MaxContours();
    void SetMaxContours(int32_t max_contours);
    int32_t MaxCompositePoints();
    void SetMaxCompositePoints(int32_t max_composite_points);
    int32_t MaxCompositeContours();
    void SetMaxCompositeContours(int32_t max_composite_contours);
    int32_t MaxZones();
    void SetMaxZones(int32_t max_zones);
    int32_t MaxTwilightPoints();
    void SetMaxTwilightPoints(int32_t max_twilight_points);
    int32_t MaxStorage();
    void SetMaxStorage(int32_t max_storage);
    int32_t MaxFunctionDefs();
    void SetMaxFunctionDefs(int32_t max_function_defs);
    int32_t MaxStackElements();
    void SetMaxStackElements(int32_t max_stack_elements);
    int32_t MaxSizeOfInstructions();
    void SetMaxSizeOfInstructions(int32_t max_size_of_instructions);
    int32_t MaxComponentElements();
    void SetMaxComponentElements(int32_t max_component_elements);
    int32_t MaxComponentDepth();
    void SetMaxComponentDepth(int32_t max_component_depth);
  };

  virtual ~MaximumProfileTable();
  int32_t TableVersion();
  int32_t NumGlyphs();
  int32_t MaxPoints();
  int32_t MaxContours();
  int32_t MaxCompositePoints();
  int32_t MaxCompositeContours();
  int32_t MaxZones();
  int32_t MaxTwilightPoints();
  int32_t MaxStorage();
  int32_t MaxFunctionDefs();
  int32_t MaxStackElements();
  int32_t MaxSizeOfInstructions();
  int32_t MaxComponentElements();
  int32_t MaxComponentDepth();

 private:
  struct Offset {
    enum {
      // version 0.5 and 1.0
      kVersion = 0,
      kNumGlyphs = 4,

      // version 1.0
      kMaxPoints = 6,
      kMaxContours = 8,
      kMaxCompositePoints = 10,
      kMaxCompositeContours = 12,
      kMaxZones = 14,
      kMaxTwilightPoints = 16,
      kMaxStorage = 18,
      kMaxFunctionDefs = 20,
      kMaxInstructionDefs = 22,
      kMaxStackElements = 24,
      kMaxSizeOfInstructions = 26,
      kMaxComponentElements = 28,
      kMaxComponentDepth = 30,
    };
  };

  MaximumProfileTable(Header* header, ReadableFontData* data);
};
typedef Ptr<MaximumProfileTable> MaximumProfileTablePtr;
typedef Ptr<MaximumProfileTable::Builder> MaximumProfileTableBuilderPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_MAXIMUM_PROFILE_TABLE_H_
