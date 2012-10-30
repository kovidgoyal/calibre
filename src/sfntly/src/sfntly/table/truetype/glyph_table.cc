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

#include "sfntly/table/truetype/glyph_table.h"

#include <stdlib.h>

#include "sfntly/port/exception_type.h"

namespace sfntly {
/******************************************************************************
 * Constants
 ******************************************************************************/
const int32_t GlyphTable::SimpleGlyph::kFLAG_ONCURVE = 1;
const int32_t GlyphTable::SimpleGlyph::kFLAG_XSHORT = 1 << 1;
const int32_t GlyphTable::SimpleGlyph::kFLAG_YSHORT = 1 << 2;
const int32_t GlyphTable::SimpleGlyph::kFLAG_REPEAT = 1 << 3;
const int32_t GlyphTable::SimpleGlyph::kFLAG_XREPEATSIGN = 1 << 4;
const int32_t GlyphTable::SimpleGlyph::kFLAG_YREPEATSIGN = 1 << 5;

const int32_t GlyphTable::CompositeGlyph::kFLAG_ARG_1_AND_2_ARE_WORDS = 1 << 0;
const int32_t GlyphTable::CompositeGlyph::kFLAG_ARGS_ARE_XY_VALUES = 1 << 1;
const int32_t GlyphTable::CompositeGlyph::kFLAG_ROUND_XY_TO_GRID = 1 << 2;
const int32_t GlyphTable::CompositeGlyph::kFLAG_WE_HAVE_A_SCALE = 1 << 3;
const int32_t GlyphTable::CompositeGlyph::kFLAG_RESERVED = 1 << 4;
const int32_t GlyphTable::CompositeGlyph::kFLAG_MORE_COMPONENTS = 1 << 5;
const int32_t GlyphTable::CompositeGlyph::kFLAG_WE_HAVE_AN_X_AND_Y_SCALE = 1 << 6;
const int32_t GlyphTable::CompositeGlyph::kFLAG_WE_HAVE_A_TWO_BY_TWO = 1 << 7;
const int32_t GlyphTable::CompositeGlyph::kFLAG_WE_HAVE_INSTRUCTIONS = 1 << 8;
const int32_t GlyphTable::CompositeGlyph::kFLAG_USE_MY_METRICS = 1 << 9;
const int32_t GlyphTable::CompositeGlyph::kFLAG_OVERLAP_COMPOUND = 1 << 10;
const int32_t GlyphTable::CompositeGlyph::kFLAG_SCALED_COMPONENT_OFFSET = 1 << 11;
const int32_t GlyphTable::CompositeGlyph::kFLAG_UNSCALED_COMPONENT_OFFSET = 1 << 12;

/******************************************************************************
 * GlyphTable class
 ******************************************************************************/
GlyphTable::~GlyphTable() {
}

GlyphTable::Glyph* GlyphTable::GetGlyph(int32_t offset, int32_t length) {
  return GlyphTable::Glyph::GetGlyph(this, this->data_, offset, length);
}

GlyphTable::GlyphTable(Header* header, ReadableFontData* data)
    : SubTableContainerTable(header, data) {
}

/******************************************************************************
 * GlyphTable::Builder class
 ******************************************************************************/
GlyphTable::Builder::Builder(Header* header, ReadableFontData* data)
    : SubTableContainerTable::Builder(header, data) {
}

GlyphTable::Builder::~Builder() {
}

void GlyphTable::Builder::SetLoca(const IntegerList& loca) {
  loca_ = loca;
  set_model_changed(false);
  glyph_builders_.clear();
}

void GlyphTable::Builder::GenerateLocaList(IntegerList* locas) {
  assert(locas);
  GlyphBuilderList* glyph_builders = GetGlyphBuilders();
  locas->push_back(0);
  if (glyph_builders->size() == 0) {
    locas->push_back(0);
  } else {
    int32_t total = 0;
    for (GlyphBuilderList::iterator b = glyph_builders->begin(),
                                    b_end = glyph_builders->end();
                                    b != b_end; ++b) {
      int32_t size = (*b)->SubDataSizeToSerialize();
      locas->push_back(total + size);
      total += size;
    }
  }
}

CALLER_ATTACH GlyphTable::Builder*
    GlyphTable::Builder::CreateBuilder(Header* header, WritableFontData* data) {
  Ptr<GlyphTable::Builder> builder;
  builder = new GlyphTable::Builder(header, data);
  return builder.Detach();
}

GlyphTable::GlyphBuilderList* GlyphTable::Builder::GlyphBuilders() {
  return GetGlyphBuilders();
}

void GlyphTable::Builder::SetGlyphBuilders(GlyphBuilderList* glyph_builders) {
  glyph_builders_ = *glyph_builders;
  set_model_changed();
}

CALLER_ATTACH GlyphTable::Glyph::Builder*
    GlyphTable::Builder::GlyphBuilder(ReadableFontData* data) {
  return Glyph::Builder::GetBuilder(this, data);
}

CALLER_ATTACH FontDataTable*
    GlyphTable::Builder::SubBuildTable(ReadableFontData* data) {
  FontDataTablePtr table = new GlyphTable(header(), data);
  return table.Detach();
}

void GlyphTable::Builder::SubDataSet() {
  glyph_builders_.clear();
  set_model_changed(false);
}

int32_t GlyphTable::Builder::SubDataSizeToSerialize() {
  if (glyph_builders_.empty())
    return 0;

  bool variable = false;
  int32_t size = 0;

  // Calculate size of each table.
  for (GlyphBuilderList::iterator b = glyph_builders_.begin(),
                                  end = glyph_builders_.end(); b != end; ++b) {
      int32_t glyph_size = (*b)->SubDataSizeToSerialize();
      size += abs(glyph_size);
      variable |= glyph_size <= 0;
  }
  return variable ? -size : size;
}

bool GlyphTable::Builder::SubReadyToSerialize() {
  return !glyph_builders_.empty();
}

int32_t GlyphTable::Builder::SubSerialize(WritableFontData* new_data) {
  int32_t size = 0;
  for (GlyphBuilderList::iterator b = glyph_builders_.begin(),
                                  end = glyph_builders_.end(); b != end; ++b) {
    FontDataPtr data;
    data.Attach(new_data->Slice(size));
    size += (*b)->SubSerialize(down_cast<WritableFontData*>(data.p_));
  }
  return size;
}

void GlyphTable::Builder::Initialize(ReadableFontData* data,
                                     const IntegerList& loca) {
  if (data != NULL) {
    if (loca_.empty()) {
      return;
    }
    int32_t loca_value;
    int32_t last_loca_value = loca[0];
    for (size_t i = 1; i < loca.size(); ++i) {
      loca_value = loca[i];
      GlyphBuilderPtr builder;
      builder.Attach(
        Glyph::Builder::GetBuilder(this,
                                   data,
                                   last_loca_value /*offset*/,
                                   loca_value - last_loca_value /*length*/));
      glyph_builders_.push_back(builder);
      last_loca_value = loca_value;
    }
  }
}

GlyphTable::GlyphBuilderList* GlyphTable::Builder::GetGlyphBuilders() {
  if (glyph_builders_.empty()) {
    if (InternalReadData() && !loca_.empty()) {
#if !defined (SFNTLY_NO_EXCEPTION)
      throw IllegalStateException(
          "Loca values not set - unable to parse glyph data.");
#endif
      return NULL;
    }
    Initialize(InternalReadData(), loca_);
    set_model_changed();
  }
  return &glyph_builders_;
}

void GlyphTable::Builder::Revert() {
  glyph_builders_.clear();
  set_model_changed(false);
}

/******************************************************************************
 * GlyphTable::Glyph class
 ******************************************************************************/
GlyphTable::Glyph::~Glyph() {}

CALLER_ATTACH GlyphTable::Glyph*
    GlyphTable::Glyph::GetGlyph(GlyphTable* table,
                                ReadableFontData* data,
                                int32_t offset,
                                int32_t length) {
  UNREFERENCED_PARAMETER(table);
  int32_t type = GlyphType(data, offset, length);
  GlyphPtr glyph;

  ReadableFontDataPtr sliced_data;
  sliced_data.Attach(down_cast<ReadableFontData*>(data->Slice(offset, length)));
  if (type == GlyphType::kSimple) {
    glyph = new SimpleGlyph(sliced_data);
  } else {
    glyph = new CompositeGlyph(sliced_data);
  }
  return glyph.Detach();
}

int32_t GlyphTable::Glyph::Padding() {
  Initialize();
  return SubTable::Padding();
}

int32_t GlyphTable::Glyph::GlyphType() {
  return glyph_type_;
}

int32_t GlyphTable::Glyph::NumberOfContours() {
  return number_of_contours_;
}

int32_t GlyphTable::Glyph::XMin() {
  return data_->ReadShort(Offset::kXMin);
}

int32_t GlyphTable::Glyph::XMax() {
  return data_->ReadShort(Offset::kXMax);
}

int32_t GlyphTable::Glyph::YMin() {
  return data_->ReadShort(Offset::kYMin);
}

int32_t GlyphTable::Glyph::YMax() {
  return data_->ReadShort(Offset::kYMax);
}

GlyphTable::Glyph::Glyph(ReadableFontData* data, int32_t glyph_type)
    : SubTable(data),
      glyph_type_(glyph_type) {
  if (data_->Length() == 0) {
    number_of_contours_ = 0;
  } else {
    // -1 if composite
    number_of_contours_ = data_->ReadShort(Offset::kNumberOfContours);
  }
}

int32_t GlyphTable::Glyph::GlyphType(ReadableFontData* data,
                                     int32_t offset,
                                     int32_t length) {
  if (length == 0) {
    return GlyphType::kSimple;
  }
  int32_t number_of_contours = data->ReadShort(offset);
  if (number_of_contours >= 0) {
    return GlyphType::kSimple;
  }
  return GlyphType::kComposite;
}

/******************************************************************************
 * GlyphTable::Glyph::Builder class
 ******************************************************************************/
GlyphTable::Glyph::Builder::~Builder() {
}

GlyphTable::Glyph::Builder::Builder(WritableFontData* data)
    : SubTable::Builder(data) {
}

GlyphTable::Glyph::Builder::Builder(ReadableFontData* data)
    : SubTable::Builder(data) {
}

CALLER_ATTACH GlyphTable::Glyph::Builder*
    GlyphTable::Glyph::Builder::GetBuilder(
        GlyphTable::Builder* table_builder,
        ReadableFontData* data) {
  return GetBuilder(table_builder, data, 0, data->Length());
}

CALLER_ATTACH GlyphTable::Glyph::Builder*
    GlyphTable::Glyph::Builder::GetBuilder(
        GlyphTable::Builder* table_builder,
        ReadableFontData* data,
        int32_t offset,
        int32_t length) {
  UNREFERENCED_PARAMETER(table_builder);
  int32_t type = Glyph::GlyphType(data, offset, length);
  GlyphBuilderPtr builder;
  ReadableFontDataPtr sliced_data;
  sliced_data.Attach(down_cast<ReadableFontData*>(data->Slice(offset, length)));
  if (type == GlyphType::kSimple) {
    builder = new SimpleGlyph::SimpleGlyphBuilder(sliced_data);
  } else {
    builder = new CompositeGlyph::CompositeGlyphBuilder(sliced_data);
  }
  return builder.Detach();
}

void GlyphTable::Glyph::Builder::SubDataSet() {
  // NOP
}

int32_t GlyphTable::Glyph::Builder::SubDataSizeToSerialize() {
  return InternalReadData()->Length();
}

bool GlyphTable::Glyph::Builder::SubReadyToSerialize() {
  return true;
}

int32_t GlyphTable::Glyph::Builder::SubSerialize(WritableFontData* new_data) {
  return InternalReadData()->CopyTo(new_data);
}

/******************************************************************************
 * GlyphTable::SimpleGlyph
 ******************************************************************************/
GlyphTable::SimpleGlyph::SimpleGlyph(ReadableFontData* data)
    : GlyphTable::Glyph(data, GlyphType::kSimple), initialized_(false) {
}

GlyphTable::SimpleGlyph::~SimpleGlyph() {
}

int32_t GlyphTable::SimpleGlyph::InstructionSize() {
  Initialize();
  return instruction_size_;
}

CALLER_ATTACH ReadableFontData* GlyphTable::SimpleGlyph::Instructions() {
  Initialize();
  return down_cast<ReadableFontData*>(
             data_->Slice(instructions_offset_, InstructionSize()));
}

int32_t GlyphTable::SimpleGlyph::NumberOfPoints(int32_t contour) {
  Initialize();
  if (contour >= NumberOfContours()) {
    return 0;
  }
  return contour_index_[contour + 1] - contour_index_[contour];
}

int32_t GlyphTable::SimpleGlyph::XCoordinate(int32_t contour, int32_t point) {
  Initialize();
  return x_coordinates_[contour_index_[contour] + point];
}

int32_t GlyphTable::SimpleGlyph::YCoordinate(int32_t contour, int32_t point) {
  Initialize();
  return y_coordinates_[contour_index_[contour] + point];
}

bool GlyphTable::SimpleGlyph::OnCurve(int32_t contour, int32_t point) {
  Initialize();
  return on_curve_[contour_index_[contour] + point];
}

void GlyphTable::SimpleGlyph::Initialize() {
  AutoLock lock(initialization_lock_);
  if (initialized_) {
    return;
  }

  if (ReadFontData()->Length() == 0) {
    instruction_size_ = 0;
    number_of_points_ = 0;
    instructions_offset_ = 0;
    flags_offset_ = 0;
    x_coordinates_offset_ = 0;
    y_coordinates_offset_ = 0;
    return;
  }

  instruction_size_ = data_->ReadUShort(Offset::kSimpleEndPtsOfCountours +
      NumberOfContours() * DataSize::kUSHORT);
  instructions_offset_ = Offset::kSimpleEndPtsOfCountours +
      (NumberOfContours() + 1) * DataSize::kUSHORT;
  flags_offset_ = instructions_offset_ + instruction_size_ * DataSize::kBYTE;
  number_of_points_ = ContourEndPoint(NumberOfContours() - 1) + 1;
  x_coordinates_.resize(number_of_points_);
  y_coordinates_.resize(number_of_points_);
  on_curve_.resize(number_of_points_);
  ParseData(false);
  x_coordinates_offset_ = flags_offset_ + flag_byte_count_ * DataSize::kBYTE;
  y_coordinates_offset_ = x_coordinates_offset_ + x_byte_count_ *
      DataSize::kBYTE;
  contour_index_.resize(NumberOfContours() + 1);
  contour_index_[0] = 0;
  for (uint32_t contour = 0; contour < contour_index_.size() - 1; ++contour) {
    contour_index_[contour + 1] = ContourEndPoint(contour) + 1;
  }
  ParseData(true);
  int32_t non_padded_data_length =
    5 * DataSize::kSHORT +
    (NumberOfContours() * DataSize::kUSHORT) +
    DataSize::kUSHORT +
    (instruction_size_ * DataSize::kBYTE) +
    (flag_byte_count_ * DataSize::kBYTE) +
    (x_byte_count_ * DataSize::kBYTE) +
    (y_byte_count_ * DataSize::kBYTE);
  set_padding(DataLength() - non_padded_data_length);
  initialized_ = true;
}

void GlyphTable::SimpleGlyph::ParseData(bool fill_arrays) {
  int32_t flag = 0;
  int32_t flag_repeat = 0;
  int32_t flag_index = 0;
  int32_t x_byte_index = 0;
  int32_t y_byte_index = 0;

  for (int32_t point_index = 0; point_index < number_of_points_;
       ++point_index) {
    // get the flag for the current point
    if (flag_repeat == 0) {
      flag = FlagAsInt(flag_index++);
      if ((flag & kFLAG_REPEAT) == kFLAG_REPEAT) {
        flag_repeat = FlagAsInt(flag_index++);
      }
    } else {
      flag_repeat--;
    }

    // on the curve?
    if (fill_arrays) {
      on_curve_[point_index] = ((flag & kFLAG_ONCURVE) == kFLAG_ONCURVE);
    }
    // get the x coordinate
    if ((flag & kFLAG_XSHORT) == kFLAG_XSHORT) {
      // single byte x coord value
      if (fill_arrays) {
        x_coordinates_[point_index] =
            data_->ReadUByte(x_coordinates_offset_ + x_byte_index);
        x_coordinates_[point_index] *=
            ((flag & kFLAG_XREPEATSIGN) == kFLAG_XREPEATSIGN) ? 1 : -1;
      }
      x_byte_index++;
    } else {
      // double byte coord value
      if (!((flag & kFLAG_XREPEATSIGN) == kFLAG_XREPEATSIGN)) {
        if (fill_arrays) {
          x_coordinates_[point_index] =
            data_->ReadShort(x_coordinates_offset_ + x_byte_index);
        }
        x_byte_index += 2;
      }
    }
    if (fill_arrays && point_index > 0) {
      x_coordinates_[point_index] += x_coordinates_[point_index - 1];
    }

    // get the y coordinate
    if ((flag & kFLAG_YSHORT) == kFLAG_YSHORT) {
      if (fill_arrays) {
        y_coordinates_[point_index] =
          data_->ReadUByte(y_coordinates_offset_ + y_byte_index);
        y_coordinates_[point_index] *=
          ((flag & kFLAG_YREPEATSIGN) == kFLAG_YREPEATSIGN) ? 1 : -1;
      }
      y_byte_index++;
    } else {
      if (!((flag & kFLAG_YREPEATSIGN) == kFLAG_YREPEATSIGN)) {
        if (fill_arrays) {
          y_coordinates_[point_index] =
            data_->ReadShort(y_coordinates_offset_ + y_byte_index);
        }
        y_byte_index += 2;
      }
    }
    if (fill_arrays && point_index > 0) {
      y_coordinates_[point_index] += y_coordinates_[point_index - 1];
    }
  }
  flag_byte_count_ = flag_index;
  x_byte_count_ = x_byte_index;
  y_byte_count_ = y_byte_index;
}

int32_t GlyphTable::SimpleGlyph::FlagAsInt(int32_t index) {
  return data_->ReadUByte(flags_offset_ + index * DataSize::kBYTE);
}

int32_t GlyphTable::SimpleGlyph::ContourEndPoint(int32_t contour) {
  return data_->ReadUShort(contour * DataSize::kUSHORT +
                           Offset::kSimpleEndPtsOfCountours);
}

/******************************************************************************
 * GlyphTable::SimpleGlyph::Builder
 ******************************************************************************/
GlyphTable::SimpleGlyph::SimpleGlyphBuilder::~SimpleGlyphBuilder() {
}

GlyphTable::SimpleGlyph::SimpleGlyphBuilder::SimpleGlyphBuilder(
    WritableFontData* data)
    : Glyph::Builder(data) {
}

GlyphTable::SimpleGlyph::SimpleGlyphBuilder::SimpleGlyphBuilder(
    ReadableFontData* data)
    : Glyph::Builder(data) {
}

CALLER_ATTACH FontDataTable*
    GlyphTable::SimpleGlyph::SimpleGlyphBuilder::SubBuildTable(
        ReadableFontData* data) {
  FontDataTablePtr table = new SimpleGlyph(data);
  return table.Detach();
}

/******************************************************************************
 * GlyphTable::CompositeGlyph
 ******************************************************************************/
GlyphTable::CompositeGlyph::CompositeGlyph(ReadableFontData* data)
    : GlyphTable::Glyph(data, GlyphType::kComposite),
      instruction_size_(0),
      instructions_offset_(0),
      initialized_(false) {
  Initialize();
}

GlyphTable::CompositeGlyph::~CompositeGlyph() {
}

int32_t GlyphTable::CompositeGlyph::Flags(int32_t contour) {
  return data_->ReadUShort(contour_index_[contour]);
}

int32_t GlyphTable::CompositeGlyph::NumGlyphs() {
  return contour_index_.size();
}

int32_t GlyphTable::CompositeGlyph::GlyphIndex(int32_t contour) {
  return data_->ReadUShort(DataSize::kUSHORT + contour_index_[contour]);
}

int32_t GlyphTable::CompositeGlyph::Argument1(int32_t contour) {
  int32_t index = 2 * DataSize::kUSHORT + contour_index_[contour];
  int32_t contour_flags = Flags(contour);
  if ((contour_flags & kFLAG_ARG_1_AND_2_ARE_WORDS) ==
                       kFLAG_ARG_1_AND_2_ARE_WORDS) {
    return data_->ReadUShort(index);
  }
  return data_->ReadByte(index);
}

int32_t GlyphTable::CompositeGlyph::Argument2(int32_t contour) {
  int32_t index = 2 * DataSize::kUSHORT + contour_index_[contour];
  int32_t contour_flags = Flags(contour);
  if ((contour_flags & kFLAG_ARG_1_AND_2_ARE_WORDS) ==
                       kFLAG_ARG_1_AND_2_ARE_WORDS) {
    return data_->ReadUShort(index + DataSize::kUSHORT);
  }
  return data_->ReadByte(index + DataSize::kUSHORT);
}

int32_t GlyphTable::CompositeGlyph::TransformationSize(int32_t contour) {
  int32_t contour_flags = Flags(contour);
  if ((contour_flags & kFLAG_WE_HAVE_A_SCALE) == kFLAG_WE_HAVE_A_SCALE) {
      return DataSize::kF2DOT14;
    } else if ((contour_flags & kFLAG_WE_HAVE_AN_X_AND_Y_SCALE) ==
                                kFLAG_WE_HAVE_AN_X_AND_Y_SCALE) {
      return 2 * DataSize::kF2DOT14;
    } else if ((contour_flags & kFLAG_WE_HAVE_A_TWO_BY_TWO) ==
                                kFLAG_WE_HAVE_A_TWO_BY_TWO) {
      return 4 * DataSize::kF2DOT14;
    }
    return 0;
}

void GlyphTable::CompositeGlyph::Transformation(int32_t contour,
                                                ByteVector* transformation) {
  int32_t contour_flags = Flags(contour);
  int32_t index = contour_index_[contour] + 2 * DataSize::kUSHORT;
  if ((contour_flags & kFLAG_ARG_1_AND_2_ARE_WORDS) ==
                       kFLAG_ARG_1_AND_2_ARE_WORDS) {
    index += 2 * DataSize::kSHORT;
  } else {
    index += 2 * DataSize::kBYTE;
  }
  int32_t tsize = TransformationSize(contour);
  transformation->resize(tsize);
  data_->ReadBytes(index, &((*transformation)[0]), 0, tsize);
}

int32_t GlyphTable::CompositeGlyph::InstructionSize() {
  return instruction_size_;
}

CALLER_ATTACH ReadableFontData* GlyphTable::CompositeGlyph::Instructions() {
  return down_cast<ReadableFontData*>(
             data_->Slice(instructions_offset_, InstructionSize()));
}

void GlyphTable::CompositeGlyph::Initialize() {
  AutoLock lock(initialization_lock_);
  if (initialized_) {
    return;
  }

  int32_t index = 5 * DataSize::kUSHORT;
  int32_t flags = kFLAG_MORE_COMPONENTS;

  while ((flags & kFLAG_MORE_COMPONENTS) == kFLAG_MORE_COMPONENTS) {
    contour_index_.push_back(index);
    flags = data_->ReadUShort(index);
    index += 2 * DataSize::kUSHORT;  // flags and glyphIndex
    if ((flags & kFLAG_ARG_1_AND_2_ARE_WORDS) == kFLAG_ARG_1_AND_2_ARE_WORDS) {
      index += 2 * DataSize::kSHORT;
    } else {
      index += 2 * DataSize::kBYTE;
    }
    if ((flags & kFLAG_WE_HAVE_A_SCALE) == kFLAG_WE_HAVE_A_SCALE) {
      index += DataSize::kF2DOT14;
    } else if ((flags & kFLAG_WE_HAVE_AN_X_AND_Y_SCALE) ==
                        kFLAG_WE_HAVE_AN_X_AND_Y_SCALE) {
      index += 2 * DataSize::kF2DOT14;
    } else if ((flags & kFLAG_WE_HAVE_A_TWO_BY_TWO) ==
                        kFLAG_WE_HAVE_A_TWO_BY_TWO) {
      index += 4 * DataSize::kF2DOT14;
    }
    int32_t non_padded_data_length = index;
    if ((flags & kFLAG_WE_HAVE_INSTRUCTIONS) == kFLAG_WE_HAVE_INSTRUCTIONS) {
      instruction_size_ = data_->ReadUShort(index);
      index += DataSize::kUSHORT;
      instructions_offset_ = index;
      non_padded_data_length = index + (instruction_size_ * DataSize::kBYTE);
    }
    set_padding(DataLength() - non_padded_data_length);
  }

  initialized_ = true;
}

/******************************************************************************
 * GlyphTable::CompositeGlyph::Builder
 ******************************************************************************/
GlyphTable::CompositeGlyph::CompositeGlyphBuilder::~CompositeGlyphBuilder() {
}

GlyphTable::CompositeGlyph::CompositeGlyphBuilder::CompositeGlyphBuilder(
    WritableFontData* data)
    : Glyph::Builder(data) {
}

GlyphTable::CompositeGlyph::CompositeGlyphBuilder::CompositeGlyphBuilder(
    ReadableFontData* data)
    : Glyph::Builder(data) {
}

CALLER_ATTACH FontDataTable*
    GlyphTable::CompositeGlyph::CompositeGlyphBuilder::SubBuildTable(
        ReadableFontData* data) {
  FontDataTablePtr table = new CompositeGlyph(data);
  return table.Detach();
}

}  // namespace sfntly
