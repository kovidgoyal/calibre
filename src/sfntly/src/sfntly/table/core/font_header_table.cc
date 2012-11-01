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

#include "sfntly/table/core/font_header_table.h"

namespace sfntly {
/******************************************************************************
 * FontHeaderTable class
 ******************************************************************************/
FontHeaderTable::~FontHeaderTable() {}

int32_t FontHeaderTable::TableVersion() {
  return data_->ReadFixed(Offset::kTableVersion);
}

int32_t FontHeaderTable::FontRevision() {
  return data_->ReadFixed(Offset::kFontRevision);
}

int64_t FontHeaderTable::ChecksumAdjustment() {
  return data_->ReadULong(Offset::kCheckSumAdjustment);
}

int64_t FontHeaderTable::MagicNumber() {
  return data_->ReadULong(Offset::kMagicNumber);
}

int32_t FontHeaderTable::FlagsAsInt() {
  return data_->ReadUShort(Offset::kFlags);
}

int32_t FontHeaderTable::UnitsPerEm() {
  return data_->ReadUShort(Offset::kUnitsPerEm);
}

int64_t FontHeaderTable::Created() {
  return data_->ReadDateTimeAsLong(Offset::kCreated);
}

int64_t FontHeaderTable::Modified() {
  return data_->ReadDateTimeAsLong(Offset::kModified);
}

int32_t FontHeaderTable::XMin() {
  return data_->ReadUShort(Offset::kXMin);
}

int32_t FontHeaderTable::YMin() {
  return data_->ReadUShort(Offset::kYMin);
}

int32_t FontHeaderTable::XMax() {
  return data_->ReadUShort(Offset::kXMax);
}

int32_t FontHeaderTable::YMax() {
  return data_->ReadUShort(Offset::kYMax);
}

int32_t FontHeaderTable::MacStyleAsInt() {
  return data_->ReadUShort(Offset::kMacStyle);
}

int32_t FontHeaderTable::LowestRecPPEM() {
  return data_->ReadUShort(Offset::kLowestRecPPEM);
}

int32_t FontHeaderTable::FontDirectionHint() {
  return data_->ReadShort(Offset::kFontDirectionHint);
}

int32_t FontHeaderTable::IndexToLocFormat() {
  return data_->ReadShort(Offset::kIndexToLocFormat);
}

int32_t FontHeaderTable::GlyphDataFormat() {
  return data_->ReadShort(Offset::kGlyphDataFormat);
}

FontHeaderTable::FontHeaderTable(Header* header, ReadableFontData* data)
    : Table(header, data) {
  IntegerList checksum_ranges;
  checksum_ranges.push_back(0);
  checksum_ranges.push_back(Offset::kCheckSumAdjustment);
  checksum_ranges.push_back(Offset::kMagicNumber);
  data_->SetCheckSumRanges(checksum_ranges);
}

/******************************************************************************
 * FontHeaderTable::Builder class
 ******************************************************************************/
FontHeaderTable::Builder::Builder(Header* header, WritableFontData* data)
    : TableBasedTableBuilder(header, data) {
}

FontHeaderTable::Builder::Builder(Header* header, ReadableFontData* data)
    : TableBasedTableBuilder(header, data) {
}

FontHeaderTable::Builder::~Builder() {}

CALLER_ATTACH FontDataTable* FontHeaderTable::Builder::SubBuildTable(
    ReadableFontData* data) {
  FontDataTablePtr table = new FontHeaderTable(header(), data);
  return table.Detach();
}

int32_t FontHeaderTable::Builder::TableVersion() {
  return down_cast<FontHeaderTable*>(GetTable())->TableVersion();
}

void FontHeaderTable::Builder::SetTableVersion(int32_t version) {
  InternalWriteData()->WriteFixed(Offset::kTableVersion, version);
}

int32_t FontHeaderTable::Builder::FontRevision() {
  return down_cast<FontHeaderTable*>(GetTable())->FontRevision();
}

void FontHeaderTable::Builder::SetFontRevision(int32_t revision) {
  InternalWriteData()->WriteFixed(Offset::kFontRevision, revision);
}

int64_t FontHeaderTable::Builder::ChecksumAdjustment() {
  return down_cast<FontHeaderTable*>(GetTable())->ChecksumAdjustment();
}

void FontHeaderTable::Builder::SetChecksumAdjustment(int64_t adjustment) {
  InternalWriteData()->WriteULong(Offset::kCheckSumAdjustment, adjustment);
}

int64_t FontHeaderTable::Builder::MagicNumber() {
  return down_cast<FontHeaderTable*>(GetTable())->MagicNumber();
}

void FontHeaderTable::Builder::SetMagicNumber(int64_t magic_number) {
  InternalWriteData()->WriteULong(Offset::kMagicNumber, magic_number);
}

int32_t FontHeaderTable::Builder::FlagsAsInt() {
  return down_cast<FontHeaderTable*>(GetTable())->FlagsAsInt();
}

void FontHeaderTable::Builder::SetFlagsAsInt(int32_t flags) {
  InternalWriteData()->WriteUShort(Offset::kFlags, flags);
}

int32_t FontHeaderTable::Builder::UnitsPerEm() {
  return down_cast<FontHeaderTable*>(GetTable())->UnitsPerEm();
}

void FontHeaderTable::Builder::SetUnitsPerEm(int32_t units) {
  InternalWriteData()->WriteUShort(Offset::kUnitsPerEm, units);
}

int64_t FontHeaderTable::Builder::Created() {
  return down_cast<FontHeaderTable*>(GetTable())->Created();
}

void FontHeaderTable::Builder::SetCreated(int64_t date) {
  InternalWriteData()->WriteDateTime(Offset::kCreated, date);
}

int64_t FontHeaderTable::Builder::Modified() {
  return down_cast<FontHeaderTable*>(GetTable())->Modified();
}

void FontHeaderTable::Builder::SetModified(int64_t date) {
  InternalWriteData()->WriteDateTime(Offset::kModified, date);
}

int32_t FontHeaderTable::Builder::XMin() {
  return down_cast<FontHeaderTable*>(GetTable())->XMin();
}

void FontHeaderTable::Builder::SetXMin(int32_t xmin) {
  InternalWriteData()->WriteShort(Offset::kXMin, xmin);
}

int32_t FontHeaderTable::Builder::YMin() {
  return down_cast<FontHeaderTable*>(GetTable())->YMin();
}

void FontHeaderTable::Builder::SetYMin(int32_t ymin) {
  InternalWriteData()->WriteShort(Offset::kYMin, ymin);
}

int32_t FontHeaderTable::Builder::XMax() {
  return down_cast<FontHeaderTable*>(GetTable())->XMax();
}

void FontHeaderTable::Builder::SetXMax(int32_t xmax) {
  InternalWriteData()->WriteShort(Offset::kXMax, xmax);
}

int32_t FontHeaderTable::Builder::YMax() {
  return down_cast<FontHeaderTable*>(GetTable())->YMax();
}

void FontHeaderTable::Builder::SetYMax(int32_t ymax) {
  InternalWriteData()->WriteShort(Offset::kYMax, ymax);
}

int32_t FontHeaderTable::Builder::MacStyleAsInt() {
  return down_cast<FontHeaderTable*>(GetTable())->MacStyleAsInt();
}

void FontHeaderTable::Builder::SetMacStyleAsInt(int32_t style) {
  InternalWriteData()->WriteUShort(Offset::kMacStyle, style);
}

int32_t FontHeaderTable::Builder::LowestRecPPEM() {
  return down_cast<FontHeaderTable*>(GetTable())->LowestRecPPEM();
}

void FontHeaderTable::Builder::SetLowestRecPPEM(int32_t size) {
  InternalWriteData()->WriteUShort(Offset::kLowestRecPPEM, size);
}

int32_t FontHeaderTable::Builder::FontDirectionHint() {
  return down_cast<FontHeaderTable*>(GetTable())->FontDirectionHint();
}

void FontHeaderTable::Builder::SetFontDirectionHint(int32_t hint) {
  InternalWriteData()->WriteShort(Offset::kFontDirectionHint, hint);
}

int32_t FontHeaderTable::Builder::IndexToLocFormat() {
  return down_cast<FontHeaderTable*>(GetTable())->IndexToLocFormat();
}

void FontHeaderTable::Builder::SetIndexToLocFormat(int32_t format) {
  InternalWriteData()->WriteShort(Offset::kIndexToLocFormat, format);
}

int32_t FontHeaderTable::Builder::GlyphDataFormat() {
  return down_cast<FontHeaderTable*>(GetTable())->GlyphDataFormat();
}

void FontHeaderTable::Builder::SetGlyphDataFormat(int32_t format) {
  InternalWriteData()->WriteShort(Offset::kGlyphDataFormat, format);
}

CALLER_ATTACH FontHeaderTable::Builder*
    FontHeaderTable::Builder::CreateBuilder(Header* header,
                                            WritableFontData* data) {
  Ptr<FontHeaderTable::Builder> builder;
  builder = new FontHeaderTable::Builder(header, data);
  return builder.Detach();
}

}  // namespace sfntly
