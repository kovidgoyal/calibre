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

#include "sfntly/table/core/os2_table.h"

namespace sfntly {
/******************************************************************************
 * Constants
 ******************************************************************************/
const int64_t CodePageRange::kLatin1_1252 = (int64_t)1 << 0;
const int64_t CodePageRange::kLatin2_1250 = (int64_t)1 << (int64_t)1;
const int64_t CodePageRange::kCyrillic_1251 = (int64_t)1 << 2;
const int64_t CodePageRange::kGreek_1253 = (int64_t)1 << 3;
const int64_t CodePageRange::kTurkish_1254 = (int64_t)1 << 4;
const int64_t CodePageRange::kHebrew_1255 = (int64_t)1 << 5;
const int64_t CodePageRange::kArabic_1256 = (int64_t)1 << 6;
const int64_t CodePageRange::kWindowsBaltic_1257 = (int64_t)1 << 7;
const int64_t CodePageRange::kVietnamese_1258 = (int64_t)1 << 8;
const int64_t CodePageRange::kAlternateANSI9 = (int64_t)1 << 9;
const int64_t CodePageRange::kAlternateANSI10 = (int64_t)1 << 10;
const int64_t CodePageRange::kAlternateANSI11 = (int64_t)1 << 11;
const int64_t CodePageRange::kAlternateANSI12 = (int64_t)1 << 12;
const int64_t CodePageRange::kAlternateANSI13 = (int64_t)1 << 13;
const int64_t CodePageRange::kAlternateANSI14 = (int64_t)1 << 14;
const int64_t CodePageRange::kAlternateANSI15 = (int64_t)1 << 15;
const int64_t CodePageRange::kThai_874 = (int64_t)1 << 16;
const int64_t CodePageRange::kJapanJIS_932 = (int64_t)1 << 17;
const int64_t CodePageRange::kChineseSimplified_936 = (int64_t)1 << 18;
const int64_t CodePageRange::kKoreanWansung_949 = (int64_t)1 << 19;
const int64_t CodePageRange::kChineseTraditional_950 = (int64_t)1 << 20;
const int64_t CodePageRange::kKoreanJohab_1361 = (int64_t)1 << 21;
const int64_t CodePageRange::kAlternateANSI22 = (int64_t)1 << 22;
const int64_t CodePageRange::kAlternateANSI23 = (int64_t)1 << 23;
const int64_t CodePageRange::kAlternateANSI24 = (int64_t)1 << 24;
const int64_t CodePageRange::kAlternateANSI25 = (int64_t)1 << 25;
const int64_t CodePageRange::kAlternateANSI26 = (int64_t)1 << 26;
const int64_t CodePageRange::kAlternateANSI27 = (int64_t)1 << 27;
const int64_t CodePageRange::kAlternateANSI28 = (int64_t)1 << 28;
const int64_t CodePageRange::kMacintoshCharacterSet = (int64_t)1 << 29;
const int64_t CodePageRange::kOEMCharacterSet = (int64_t)1 << 30;
const int64_t CodePageRange::kSymbolCharacterSet = (int64_t)1 << 31;
const int64_t CodePageRange::kReservedForOEM32 = (int64_t)1 << 32;
const int64_t CodePageRange::kReservedForOEM33 = (int64_t)1 << 33;
const int64_t CodePageRange::kReservedForOEM34 = (int64_t)1 << 34;
const int64_t CodePageRange::kReservedForOEM35 = (int64_t)1 << 35;
const int64_t CodePageRange::kReservedForOEM36 = (int64_t)1 << 36;
const int64_t CodePageRange::kReservedForOEM37 = (int64_t)1 << 37;
const int64_t CodePageRange::kReservedForOEM38 = (int64_t)1 << 38;
const int64_t CodePageRange::kReservedForOEM39 = (int64_t)1 << 39;
const int64_t CodePageRange::kReservedForOEM40 = (int64_t)1 << 40;
const int64_t CodePageRange::kReservedForOEM41 = (int64_t)1 << 41;
const int64_t CodePageRange::kReservedForOEM42 = (int64_t)1 << 42;
const int64_t CodePageRange::kReservedForOEM43 = (int64_t)1 << 43;
const int64_t CodePageRange::kReservedForOEM44 = (int64_t)1 << 44;
const int64_t CodePageRange::kReservedForOEM45 = (int64_t)1 << 45;
const int64_t CodePageRange::kReservedForOEM46 = (int64_t)1 << 46;
const int64_t CodePageRange::kReservedForOEM47 = (int64_t)1 << 47;
const int64_t CodePageRange::kIBMGreek_869 = (int64_t)1 << 48;
const int64_t CodePageRange::kMSDOSRussion_866 = (int64_t)1 << 49;
const int64_t CodePageRange::kMSDOSNordic_865 = (int64_t)1 << 50;
const int64_t CodePageRange::kArabic_864 = (int64_t)1 << 51;
const int64_t CodePageRange::kMSDOSCanadianFrench_863 = (int64_t)1 << 52;
const int64_t CodePageRange::kHebrew_862 = (int64_t)1 << 53;
const int64_t CodePageRange::kMSDOSIcelandic_861 = (int64_t)1 << 54;
const int64_t CodePageRange::kMSDOSPortugese_860 = (int64_t)1 << 55;
const int64_t CodePageRange::kIBMTurkish_857 = (int64_t)1 << 56;
const int64_t CodePageRange::kIBMCyrillic_855 = (int64_t)1 << 57;
const int64_t CodePageRange::kLatin2_852 = (int64_t)1 << 58;
const int64_t CodePageRange::kMSDOSBaltic_775 = (int64_t)1 << 59;
const int64_t CodePageRange::kGreek_737 = (int64_t)1 << 60;
const int64_t CodePageRange::kArabic_708 = (int64_t)1 << 61;
const int64_t CodePageRange::kLatin1_850 = (int64_t)1 << 62;
const int64_t CodePageRange::kUS_437 = (int64_t)1 << 63;

/******************************************************************************
 * struct UnicodeRange
 ******************************************************************************/
int32_t UnicodeRange::range(int32_t bit) {
  if (bit < 0 || bit > kLast) {
    return -1;
  }
  return bit;
}

/******************************************************************************
 * class OS2Table
 ******************************************************************************/
OS2Table::~OS2Table() {}

int32_t OS2Table::TableVersion() {
  return data_->ReadUShort(Offset::kVersion);
}

int32_t OS2Table::XAvgCharWidth() {
  return data_->ReadShort(Offset::kXAvgCharWidth);
}

int32_t OS2Table::UsWeightClass() {
  return data_->ReadUShort(Offset::kUsWeightClass);
}

int32_t OS2Table::UsWidthClass() {
  return data_->ReadUShort(Offset::kUsWidthClass);
}

int32_t OS2Table::FsType() {
  return data_->ReadUShort(Offset::kFsType);
}

int32_t OS2Table::YSubscriptXSize() {
  return data_->ReadShort(Offset::kYSubscriptXSize);
}

int32_t OS2Table::YSubscriptYSize() {
  return data_->ReadShort(Offset::kYSubscriptYSize);
}

int32_t OS2Table::YSubscriptXOffset() {
  return data_->ReadShort(Offset::kYSubscriptXOffset);
}

int32_t OS2Table::YSubscriptYOffset() {
  return data_->ReadShort(Offset::kYSubscriptYOffset);
}

int32_t OS2Table::YSuperscriptXSize() {
  return data_->ReadShort(Offset::kYSuperscriptXSize);
}

int32_t OS2Table::YSuperscriptYSize() {
  return data_->ReadShort(Offset::kYSuperscriptYSize);
}

int32_t OS2Table::YSuperscriptXOffset() {
  return data_->ReadShort(Offset::kYSuperscriptXOffset);
}

int32_t OS2Table::YSuperscriptYOffset() {
  return data_->ReadShort(Offset::kYSuperscriptYOffset);
}

int32_t OS2Table::YStrikeoutSize() {
  return data_->ReadShort(Offset::kYStrikeoutSize);
}

int32_t OS2Table::YStrikeoutPosition() {
  return data_->ReadShort(Offset::kYStrikeoutPosition);
}

int32_t OS2Table::SFamilyClass() {
  return data_->ReadShort(Offset::kSFamilyClass);
}

void OS2Table::Panose(ByteVector* value) {
  assert(value);
  value->clear();
  value->resize(10);
  data_->ReadBytes(Offset::kPanose, &((*value)[0]), 0, 10);
}

int64_t OS2Table::UlUnicodeRange1() {
  return data_->ReadULong(Offset::kUlUnicodeRange1);
}

int64_t OS2Table::UlUnicodeRange2() {
  return data_->ReadULong(Offset::kUlUnicodeRange2);
}

int64_t OS2Table::UlUnicodeRange3() {
  return data_->ReadULong(Offset::kUlUnicodeRange3);
}

int64_t OS2Table::UlUnicodeRange4() {
  return data_->ReadULong(Offset::kUlUnicodeRange4);
}

void OS2Table::AchVendId(ByteVector* b) {
  assert(b);
  b->clear();
  b->resize(4);
  data_->ReadBytes(Offset::kAchVendId, &((*b)[0]), 0, 4);
}

int32_t OS2Table::FsSelection() {
  return data_->ReadUShort(Offset::kFsSelection);
}

int32_t OS2Table::UsFirstCharIndex() {
  return data_->ReadUShort(Offset::kUsFirstCharIndex);
}

int32_t OS2Table::UsLastCharIndex() {
  return data_->ReadUShort(Offset::kUsLastCharIndex);
}

int32_t OS2Table::STypoAscender() {
  return data_->ReadShort(Offset::kSTypoAscender);
}

int32_t OS2Table::STypoDescender() {
  return data_->ReadShort(Offset::kSTypoDescender);
}

int32_t OS2Table::STypoLineGap() {
  return data_->ReadShort(Offset::kSTypoLineGap);
}

int32_t OS2Table::UsWinAscent() {
  return data_->ReadUShort(Offset::kUsWinAscent);
}

int32_t OS2Table::UsWinDescent() {
  return data_->ReadUShort(Offset::kUsWinDescent);
}

int64_t OS2Table::UlCodePageRange1() {
  return data_->ReadULong(Offset::kUlCodePageRange1);
}

int64_t OS2Table::UlCodePageRange2() {
  return data_->ReadULong(Offset::kUlCodePageRange2);
}

int32_t OS2Table::SxHeight() {
  return data_->ReadShort(Offset::kSxHeight);
}

int32_t OS2Table::SCapHeight() {
  return data_->ReadShort(Offset::kSCapHeight);
}

int32_t OS2Table::UsDefaultChar() {
  return data_->ReadUShort(Offset::kUsDefaultChar);
}

int32_t OS2Table::UsBreakChar() {
  return data_->ReadUShort(Offset::kUsBreakChar);
}

int32_t OS2Table::UsMaxContext() {
  return data_->ReadUShort(Offset::kUsMaxContext);
}

OS2Table::OS2Table(Header* header, ReadableFontData* data)
    : Table(header, data) {
}

/******************************************************************************
 * class OS2Table::Builder
 ******************************************************************************/
OS2Table::Builder::Builder(Header* header, WritableFontData* data)
    : TableBasedTableBuilder(header, data) {
}

OS2Table::Builder::Builder(Header* header, ReadableFontData* data)
    : TableBasedTableBuilder(header, data) {
}

OS2Table::Builder::~Builder() {}

CALLER_ATTACH FontDataTable* OS2Table::Builder::SubBuildTable(
    ReadableFontData* data) {
  FontDataTablePtr table = new OS2Table(header(), data);
  return table.Detach();
}

CALLER_ATTACH OS2Table::Builder*
    OS2Table::Builder::CreateBuilder(Header* header,
                                     WritableFontData* data) {
  Ptr<OS2Table::Builder> builder;
  builder = new OS2Table::Builder(header, data);
  return builder.Detach();
}

int32_t OS2Table::Builder::TableVersion() {
  return InternalReadData()->ReadUShort(Offset::kVersion);
}

void OS2Table::Builder::SetTableVersion(int32_t version) {
  InternalWriteData()->WriteUShort(Offset::kVersion, version);
}

int32_t OS2Table::Builder::XAvgCharWidth() {
  return InternalReadData()->ReadShort(Offset::kXAvgCharWidth);
}

void OS2Table::Builder::SetXAvgCharWidth(int32_t width) {
  InternalWriteData()->WriteShort(Offset::kXAvgCharWidth, width);
}

int32_t OS2Table::Builder::UsWeightClass() {
  return InternalReadData()->ReadUShort(Offset::kUsWeightClass);
}

void OS2Table::Builder::SetUsWeightClass(int32_t weight) {
  InternalWriteData()->WriteUShort(Offset::kUsWeightClass, weight);
}

int32_t OS2Table::Builder::UsWidthClass() {
  return InternalReadData()->ReadUShort(Offset::kUsWidthClass);
}

void OS2Table::Builder::SetUsWidthClass(int32_t width) {
  InternalWriteData()->WriteUShort(Offset::kUsWidthClass, width);
}

int32_t OS2Table::Builder::FsType() {
  return InternalReadData()->ReadUShort(Offset::kFsType);
}

void OS2Table::Builder::SetFsType(int32_t fs_type) {
  InternalWriteData()->WriteUShort(Offset::kFsType, fs_type);
}

int32_t OS2Table::Builder::YSubscriptXSize() {
  return InternalReadData()->ReadShort(Offset::kYSubscriptXSize);
}

void OS2Table::Builder::SetYSubscriptXSize(int32_t size) {
  InternalWriteData()->WriteShort(Offset::kYSubscriptXSize, size);
}

int32_t OS2Table::Builder::YSubscriptYSize() {
  return InternalReadData()->ReadShort(Offset::kYSubscriptYSize);
}

void OS2Table::Builder::SetYSubscriptYSize(int32_t size) {
  InternalWriteData()->WriteShort(Offset::kYSubscriptYSize, size);
}

int32_t OS2Table::Builder::YSubscriptXOffset() {
  return InternalReadData()->ReadShort(Offset::kYSubscriptXOffset);
}

void OS2Table::Builder::SetYSubscriptXOffset(int32_t offset) {
  InternalWriteData()->WriteShort(Offset::kYSubscriptXOffset, offset);
}

int32_t OS2Table::Builder::YSubscriptYOffset() {
  return InternalReadData()->ReadShort(Offset::kYSubscriptYOffset);
}

void OS2Table::Builder::SetYSubscriptYOffset(int32_t offset) {
  InternalWriteData()->WriteShort(Offset::kYSubscriptYOffset, offset);
}

int32_t OS2Table::Builder::YSuperscriptXSize() {
  return InternalReadData()->ReadShort(Offset::kYSuperscriptXSize);
}

void OS2Table::Builder::SetYSuperscriptXSize(int32_t size) {
  InternalWriteData()->WriteShort(Offset::kYSuperscriptXSize, size);
}

int32_t OS2Table::Builder::YSuperscriptYSize() {
  return InternalReadData()->ReadShort(Offset::kYSuperscriptYSize);
}

void OS2Table::Builder::SetYSuperscriptYSize(int32_t size) {
  InternalWriteData()->WriteShort(Offset::kYSuperscriptYSize, size);
}

int32_t OS2Table::Builder::YSuperscriptXOffset() {
  return InternalReadData()->ReadShort(Offset::kYSuperscriptXOffset);
}

void OS2Table::Builder::SetYSuperscriptXOffset(int32_t offset) {
  InternalWriteData()->WriteShort(Offset::kYSuperscriptXOffset, offset);
}

int32_t OS2Table::Builder::YSuperscriptYOffset() {
  return InternalReadData()->ReadShort(Offset::kYSuperscriptYOffset);
}

void OS2Table::Builder::SetYSuperscriptYOffset(int32_t offset) {
  InternalWriteData()->WriteShort(Offset::kYSuperscriptYOffset, offset);
}

int32_t OS2Table::Builder::YStrikeoutSize() {
  return InternalReadData()->ReadShort(Offset::kYStrikeoutSize);
}

void OS2Table::Builder::SetYStrikeoutSize(int32_t size) {
  InternalWriteData()->WriteShort(Offset::kYStrikeoutSize, size);
}

int32_t OS2Table::Builder::YStrikeoutPosition() {
  return InternalReadData()->ReadShort(Offset::kYStrikeoutPosition);
}

void OS2Table::Builder::SetYStrikeoutPosition(int32_t position) {
  InternalWriteData()->WriteShort(Offset::kYStrikeoutPosition, position);
}

int32_t OS2Table::Builder::SFamilyClass() {
  return InternalReadData()->ReadShort(Offset::kSFamilyClass);
}

void OS2Table::Builder::SetSFamilyClass(int32_t family) {
  InternalWriteData()->WriteShort(Offset::kSFamilyClass, family);
}

void OS2Table::Builder::Panose(ByteVector* value) {
  assert(value);
  value->clear();
  value->resize(Offset::kPanoseLength);
  InternalReadData()->ReadBytes(Offset::kPanose,
                                &((*value)[0]),
                                0,
                                Offset::kPanoseLength);
}

void OS2Table::Builder::SetPanose(ByteVector* panose) {
  assert(panose);
  if (panose->size() != Offset::kPanoseLength) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IllegalArgumentException("Panose bytes must be exactly 10 in length");
#endif
    return;
  }
  InternalWriteData()->WriteBytes(Offset::kPanose, panose);
}

int64_t OS2Table::Builder::UlUnicodeRange1() {
  return InternalReadData()->ReadULong(Offset::kUlUnicodeRange1);
}

void OS2Table::Builder::SetUlUnicodeRange1(int64_t range) {
  InternalWriteData()->WriteULong(Offset::kUlUnicodeRange1, range);
}

int64_t OS2Table::Builder::UlUnicodeRange2() {
  return InternalReadData()->ReadULong(Offset::kUlUnicodeRange2);
}

void OS2Table::Builder::SetUlUnicodeRange2(int64_t range) {
  InternalWriteData()->WriteULong(Offset::kUlUnicodeRange2, range);
}

int64_t OS2Table::Builder::UlUnicodeRange3() {
  return InternalReadData()->ReadULong(Offset::kUlUnicodeRange3);
}

void OS2Table::Builder::SetUlUnicodeRange3(int64_t range) {
  InternalWriteData()->WriteULong(Offset::kUlUnicodeRange3, range);
}

int64_t OS2Table::Builder::UlUnicodeRange4() {
  return InternalReadData()->ReadULong(Offset::kUlUnicodeRange4);
}

void OS2Table::Builder::SetUlUnicodeRange4(int64_t range) {
  InternalWriteData()->WriteULong(Offset::kUlUnicodeRange4, range);
}

void OS2Table::Builder::AchVendId(ByteVector* b) {
  assert(b);
  b->clear();
  b->resize(4);
  InternalReadData()->ReadBytes(Offset::kAchVendId, &((*b)[0]), 0, 4);
}

void OS2Table::Builder::SetAchVendId(ByteVector* b) {
  assert(b);
  assert(b->size());
  InternalWriteData()->WriteBytesPad(Offset::kAchVendId,
                                     b,
                                     0,
                                     std::min<size_t>(
                                         (size_t)Offset::kAchVendIdLength,
                                         b->size()),
                                     static_cast<byte_t>(' '));
}

int32_t OS2Table::Builder::FsSelection() {
  return InternalReadData()->ReadUShort(Offset::kFsSelection);
}

void OS2Table::Builder::SetFsSelection(int32_t fs_selection) {
  InternalWriteData()->WriteUShort(Offset::kFsSelection, fs_selection);
}

int32_t OS2Table::Builder::UsFirstCharIndex() {
  return InternalReadData()->ReadUShort(Offset::kUsFirstCharIndex);
}

void OS2Table::Builder::SetUsFirstCharIndex(int32_t first_index) {
  InternalWriteData()->WriteUShort(Offset::kUsFirstCharIndex, first_index);
}

int32_t OS2Table::Builder::UsLastCharIndex() {
  return InternalReadData()->ReadUShort(Offset::kUsLastCharIndex);
}

void OS2Table::Builder::SetUsLastCharIndex(int32_t last_index) {
  InternalWriteData()->WriteUShort(Offset::kUsLastCharIndex, last_index);
}

int32_t OS2Table::Builder::STypoAscender() {
  return InternalReadData()->ReadShort(Offset::kSTypoAscender);
}

void OS2Table::Builder::SetSTypoAscender(int32_t ascender) {
  InternalWriteData()->WriteShort(Offset::kSTypoAscender, ascender);
}

int32_t OS2Table::Builder::STypoDescender() {
  return InternalReadData()->ReadShort(Offset::kSTypoDescender);
}

void OS2Table::Builder::SetSTypoDescender(int32_t descender) {
  InternalWriteData()->WriteShort(Offset::kSTypoDescender, descender);
}

int32_t OS2Table::Builder::STypoLineGap() {
  return InternalReadData()->ReadShort(Offset::kSTypoLineGap);
}

void OS2Table::Builder::SetSTypoLineGap(int32_t line_gap) {
  InternalWriteData()->WriteShort(Offset::kSTypoLineGap, line_gap);
}

int32_t OS2Table::Builder::UsWinAscent() {
  return InternalReadData()->ReadUShort(Offset::kUsWinAscent);
}

void OS2Table::Builder::SetUsWinAscent(int32_t ascent) {
  InternalWriteData()->WriteUShort(Offset::kUsWinAscent, ascent);
}

int32_t OS2Table::Builder::UsWinDescent() {
  return InternalReadData()->ReadUShort(Offset::kUsWinDescent);
}

void OS2Table::Builder::SetUsWinDescent(int32_t descent) {
  InternalWriteData()->WriteUShort(Offset::kUsWinDescent, descent);
}

int64_t OS2Table::Builder::UlCodePageRange1() {
  return InternalReadData()->ReadULong(Offset::kUlCodePageRange1);
}

void OS2Table::Builder::SetUlCodePageRange1(int64_t range) {
  InternalWriteData()->WriteULong(Offset::kUlCodePageRange1, range);
}

int64_t OS2Table::Builder::UlCodePageRange2() {
  return InternalReadData()->ReadULong(Offset::kUlCodePageRange2);
}

void OS2Table::Builder::SetUlCodePageRange2(int64_t range) {
  InternalWriteData()->WriteULong(Offset::kUlCodePageRange2, range);
}

int32_t OS2Table::Builder::SxHeight() {
  return InternalReadData()->ReadShort(Offset::kSxHeight);
}

void OS2Table::Builder::SetSxHeight(int32_t height) {
  InternalWriteData()->WriteShort(Offset::kSxHeight, height);
}

int32_t OS2Table::Builder::SCapHeight() {
  return InternalReadData()->ReadShort(Offset::kSCapHeight);
}

void OS2Table::Builder::SetSCapHeight(int32_t height) {
  InternalWriteData()->WriteShort(Offset::kSCapHeight, height);
}

int32_t OS2Table::Builder::UsDefaultChar() {
  return InternalReadData()->ReadUShort(Offset::kUsDefaultChar);
}

void OS2Table::Builder::SetUsDefaultChar(int32_t default_char) {
  InternalWriteData()->WriteUShort(Offset::kUsDefaultChar, default_char);
}

int32_t OS2Table::Builder::UsBreakChar() {
  return InternalReadData()->ReadUShort(Offset::kUsBreakChar);
}

void OS2Table::Builder::SetUsBreakChar(int32_t break_char) {
  InternalWriteData()->WriteUShort(Offset::kUsBreakChar, break_char);
}

int32_t OS2Table::Builder::UsMaxContext() {
  return InternalReadData()->ReadUShort(Offset::kUsMaxContext);
}

void OS2Table::Builder::SetUsMaxContext(int32_t max_context) {
  InternalWriteData()->WriteUShort(Offset::kUsMaxContext, max_context);
}

}  // namespace sfntly
