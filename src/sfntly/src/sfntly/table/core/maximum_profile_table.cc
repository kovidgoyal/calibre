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

#include "sfntly/table/core/maximum_profile_table.h"

namespace sfntly {
/******************************************************************************
 * MaximumProfileTable class
 ******************************************************************************/
MaximumProfileTable::~MaximumProfileTable() {}

int32_t MaximumProfileTable::TableVersion() {
  return data_->ReadFixed(Offset::kVersion);
}

int32_t MaximumProfileTable::NumGlyphs() {
  return data_->ReadUShort(Offset::kNumGlyphs);
}

int32_t MaximumProfileTable::MaxPoints() {
  return data_->ReadUShort(Offset::kMaxPoints);
}

int32_t MaximumProfileTable::MaxContours() {
  return data_->ReadUShort(Offset::kMaxContours);
}

int32_t MaximumProfileTable::MaxCompositePoints() {
  return data_->ReadUShort(Offset::kMaxCompositePoints);
}

int32_t MaximumProfileTable::MaxCompositeContours() {
  return data_->ReadUShort(Offset::kMaxCompositeContours);
}

int32_t MaximumProfileTable::MaxZones() {
  return data_->ReadUShort(Offset::kMaxZones);
}

int32_t MaximumProfileTable::MaxTwilightPoints() {
  return data_->ReadUShort(Offset::kMaxTwilightPoints);
}

int32_t MaximumProfileTable::MaxStorage() {
  return data_->ReadUShort(Offset::kMaxStorage);
}

int32_t MaximumProfileTable::MaxFunctionDefs() {
  return data_->ReadUShort(Offset::kMaxFunctionDefs);
}

int32_t MaximumProfileTable::MaxStackElements() {
  return data_->ReadUShort(Offset::kMaxStackElements);
}

int32_t MaximumProfileTable::MaxSizeOfInstructions() {
  return data_->ReadUShort(Offset::kMaxSizeOfInstructions);
}

int32_t MaximumProfileTable::MaxComponentElements() {
  return data_->ReadUShort(Offset::kMaxComponentElements);
}

int32_t MaximumProfileTable::MaxComponentDepth() {
  return data_->ReadUShort(Offset::kMaxComponentDepth);
}

MaximumProfileTable::MaximumProfileTable(Header* header,
                                         ReadableFontData* data)
    : Table(header, data) {
}

/******************************************************************************
 * MaximumProfileTable::Builder class
 ******************************************************************************/
MaximumProfileTable::Builder::Builder(Header* header, WritableFontData* data)
    : TableBasedTableBuilder(header, data) {
}

MaximumProfileTable::Builder::Builder(Header* header, ReadableFontData* data)
    : TableBasedTableBuilder(header, data) {
}

MaximumProfileTable::Builder::~Builder() {}

CALLER_ATTACH FontDataTable*
    MaximumProfileTable::Builder::SubBuildTable(ReadableFontData* data) {
  FontDataTablePtr table = new MaximumProfileTable(header(), data);
  return table.Detach();
}

CALLER_ATTACH MaximumProfileTable::Builder*
    MaximumProfileTable::Builder::CreateBuilder(Header* header,
                                                WritableFontData* data) {
  Ptr<MaximumProfileTable::Builder> builder;
  builder = new MaximumProfileTable::Builder(header, data);
  return builder.Detach();
}

int32_t MaximumProfileTable::Builder::TableVersion() {
  return InternalReadData()->ReadUShort(Offset::kVersion);
}

void MaximumProfileTable::Builder::SetTableVersion(int32_t version) {
  InternalWriteData()->WriteUShort(Offset::kVersion, version);
}

int32_t MaximumProfileTable::Builder::NumGlyphs() {
  return InternalReadData()->ReadUShort(Offset::kNumGlyphs);
}

void MaximumProfileTable::Builder::SetNumGlyphs(int32_t num_glyphs) {
  InternalWriteData()->WriteUShort(Offset::kNumGlyphs, num_glyphs);
}

int32_t MaximumProfileTable::Builder::MaxPoints() {
  return InternalReadData()->ReadUShort(Offset::kMaxPoints);
}

void MaximumProfileTable::Builder::SetMaxPoints(int32_t max_points) {
  InternalWriteData()->WriteUShort(Offset::kMaxPoints, max_points);
}

int32_t MaximumProfileTable::Builder::MaxContours() {
  return InternalReadData()->ReadUShort(Offset::kMaxContours);
}

void MaximumProfileTable::Builder::SetMaxContours(int32_t max_contours) {
  InternalWriteData()->WriteUShort(Offset::kMaxContours, max_contours);
}

int32_t MaximumProfileTable::Builder::MaxCompositePoints() {
  return InternalReadData()->ReadUShort(Offset::kMaxCompositePoints);
}

void MaximumProfileTable::Builder::SetMaxCompositePoints(
    int32_t max_composite_points) {
  InternalWriteData()->WriteUShort(Offset::kMaxCompositePoints,
                                   max_composite_points);
}

int32_t MaximumProfileTable::Builder::MaxCompositeContours() {
  return InternalReadData()->ReadUShort(Offset::kMaxCompositeContours);
}

void MaximumProfileTable::Builder::SetMaxCompositeContours(
    int32_t max_composite_contours) {
  InternalWriteData()->WriteUShort(Offset::kMaxCompositeContours,
      max_composite_contours);
}

int32_t MaximumProfileTable::Builder::MaxZones() {
  return InternalReadData()->ReadUShort(Offset::kMaxZones);
}

void MaximumProfileTable::Builder::SetMaxZones(int32_t max_zones) {
  InternalWriteData()->WriteUShort(Offset::kMaxZones, max_zones);
}

int32_t MaximumProfileTable::Builder::MaxTwilightPoints() {
  return InternalReadData()->ReadUShort(Offset::kMaxTwilightPoints);
}

void MaximumProfileTable::Builder::SetMaxTwilightPoints(
    int32_t max_twilight_points) {
  InternalWriteData()->WriteUShort(Offset::kMaxTwilightPoints,
                                   max_twilight_points);
}

int32_t MaximumProfileTable::Builder::MaxStorage() {
  return InternalReadData()->ReadUShort(Offset::kMaxStorage);
}

void MaximumProfileTable::Builder::SetMaxStorage(int32_t max_storage) {
  InternalWriteData()->WriteUShort(Offset::kMaxStorage, max_storage);
}

int32_t MaximumProfileTable::Builder::MaxFunctionDefs() {
  return InternalReadData()->ReadUShort(Offset::kMaxFunctionDefs);
}

void MaximumProfileTable::Builder::SetMaxFunctionDefs(
    int32_t max_function_defs) {
  InternalWriteData()->WriteUShort(Offset::kMaxFunctionDefs, max_function_defs);
}

int32_t MaximumProfileTable::Builder::MaxStackElements() {
  return InternalReadData()->ReadUShort(Offset::kMaxStackElements);
}

void MaximumProfileTable::Builder::SetMaxStackElements(
    int32_t max_stack_elements) {
  InternalWriteData()->WriteUShort(Offset::kMaxStackElements,
                                   max_stack_elements);
}

int32_t MaximumProfileTable::Builder::MaxSizeOfInstructions() {
  return InternalReadData()->ReadUShort(Offset::kMaxSizeOfInstructions);
}

void MaximumProfileTable::Builder::SetMaxSizeOfInstructions(
    int32_t max_size_of_instructions) {
  InternalWriteData()->WriteUShort(Offset::kMaxSizeOfInstructions,
                                   max_size_of_instructions);
}

int32_t MaximumProfileTable::Builder::MaxComponentElements() {
  return InternalReadData()->ReadUShort(Offset::kMaxComponentElements);
}

void MaximumProfileTable::Builder::SetMaxComponentElements(
    int32_t max_component_elements) {
  InternalWriteData()->WriteUShort(Offset::kMaxComponentElements,
                                   max_component_elements);
}

int32_t MaximumProfileTable::Builder::MaxComponentDepth() {
  return InternalReadData()->ReadUShort(Offset::kMaxComponentDepth);
}

void MaximumProfileTable::Builder::SetMaxComponentDepth(
    int32_t max_component_depth) {
  InternalWriteData()->WriteUShort(Offset::kMaxComponentDepth,
                                   max_component_depth);
}

}  // namespace sfntly
