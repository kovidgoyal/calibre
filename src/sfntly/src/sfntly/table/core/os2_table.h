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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_OS2_TABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_OS2_TABLE_H_

#include "sfntly/port/refcount.h"
#include "sfntly/table/table.h"
#include "sfntly/table/table_based_table_builder.h"

namespace sfntly {

struct WeightClass {
  enum {
    kThin = 100,
    kExtraLight = 200,
    kUltraLight = 200,
    kLight = 300,
    kNormal = 400,
    kRegular = 400,
    kMedium = 500,
    kSemiBold = 600,
    kDemiBold = 600,
    kBold = 700,
    kExtraBold = 800,
    kUltraBold = 800,
    kBlack = 900,
    kHeavy = 900
  };
};

struct WidthClass {
  enum {
    kUltraCondensed = 1,
    kExtraCondensed = 2,
    kCondensed = 3,
    kSemiCondensed = 4,
    kMedium = 5,
    kNormal = 5,
    kSemiExpanded = 6,
    kExpanded = 7,
    kExtraExpanded = 8,
    kUltraExpanded = 9
  };
};

// Flags to indicate the embedding licensing rights for a font.
struct EmbeddingFlags {
  enum {
    kReserved0 = 1 << 0,
    kRestrictedLicenseEmbedding = 1 << 1,
    kPreviewAndPrintEmbedding = 1 << 2,
    kEditableEmbedding = 1 << 3,
    kReserved4 = 1 << 4,
    kReserved5 = 1 << 5,
    kReserved6 = 1 << 6,
    kReserved7 = 1 << 7,
    kNoSubsetting = 1 << 8,
    kBitmapEmbeddingOnly = 1 << 9,
    kReserved10 = 1 << 10,
    kReserved11 = 1 << 11,
    kReserved12 = 1 << 12,
    kReserved13 = 1 << 13,
    kReserved14 = 1 << 14,
    kReserved15 = 1 << 15
  };
};

struct UnicodeRange {
  enum {
    // Do NOT reorder. This enum relies on the ordering of the data matching the
    // ordinal numbers of the properties.
    kBasicLatin,
    kLatin1Supplement,
    kLatinExtendedA,
    kLatinExtendedB,
    kIPAExtensions,
    kSpacingModifierLetters,
    kCombiningDiacriticalMarks,
    kGreekAndCoptic,
    kCoptic,
    kCyrillic,
    kArmenian,
    kHebrew,
    kVai,
    kArabic,
    kNKo,
    kDevanagari,
    kBengali,
    kGurmukhi,
    kGujarati,
    kOriya,
    kTamil,
    kTelugu,
    kKannada,
    kMalayalam,
    kThai,
    kLao,
    kGeorgian,
    kBalinese,
    kHangulJamo,
    kLatinExtendedAdditional,
    kGreekExtended,
    kGeneralPunctuation,
    kSuperscriptsAndSubscripts,
    kCurrencySymbols,
    kNumberForms,
    kArrows,
    kMathematicalOperators,
    kMiscTechnical,
    kControlPictures,
    kOCR,
    kEnclosedAlphanumerics,
    kBoxDrawing,
    kBlockElements,
    kGeometricShapes,
    kMiscSymbols,
    kDingbats,
    kCJKSymbolsAndPunctuation,
    kHiragana,
    kKatakana,
    kBopomofo,
    kHangulCompatibilityJamo,
    kPhagspa,
    kEnclosedCJKLettersAndMonths,
    kCJKCompatibility,
    kHangulSyllables,
    kNonPlane0,
    kPhoenician,
    kCJKUnifiedIdeographs,
    kPrivateUseAreaPlane0,
    kCJKStrokes,
    kAlphabeticPresentationForms,
    kArabicPresentationFormsA,
    kCombiningHalfMarks,
    kVerticalForms,
    kSmallFormVariants,
    kArabicPresentationFormsB,
    kHalfwidthAndFullwidthForms,
    kSpecials,
    kTibetan,
    kSyriac,
    kThaana,
    kSinhala,
    kMyanmar,
    kEthiopic,
    kCherokee,
    kUnifiedCanadianAboriginalSyllabics,
    kOgham,
    kRunic,
    kKhmer,
    kMongolian,
    kBraillePatterns,
    kYiSyllables,
    kTagalog,
    kOldItalic,
    kGothic,
    kDeseret,
    kMusicalSymbols,
    kMathematicalAlphanumericSymbols,
    kPrivateUsePlane15And16,
    kVariationSelectors,
    kTags,
    kLimbu,
    kTaiLe,
    kNewTaiLue,
    kBuginese,
    kGlagolitic,
    kTifnagh,
    kYijingHexagramSymbols,
    kSylotiNagari,
    kLinearB,
    kAncientGreekNumbers,
    kUgaritic,
    kOldPersian,
    kShavian,
    kOsmanya,
    kCypriotSyllabary,
    kKharoshthi,
    kTaiXuanJingSymbols,
    kCuneiform,
    kCountingRodNumerals,
    kSudanese,
    kLepcha,
    kOlChiki,
    kSaurashtra,
    kKayahLi,
    kRejang,
    kCharm,
    kAncientSymbols,
    kPhaistosDisc,
    kCarian,
    kDominoTiles,
    kReserved123,
    kReserved124,
    kReserved125,
    kReserved126,
    kReserved127,
    kLast = kReserved127
  };

  int32_t range(int32_t bit);
  // UNIMPLEMENTED: EnumSet<UnicodeRange> asSet(long range1, long range2,
  //                                            long range3, long range4)
  //                long[] asArray(EnumSet<UnicodeRange> rangeSet)
};

struct FsSelection {
  enum {
    kITALIC = 1 << 0,
    kUNDERSCORE = 1 << 1,
    kNEGATIVE = 1 << 2,
    kOUTLINED = 1 << 3,
    kSTRIKEOUT = 1 << 4,
    kBOLD = 1 << 5,
    kREGULAR = 1 << 6,
    kUSE_TYPO_METRICS = 1 << 7,
    kWWS = 1 << 8,
    kOBLIQUE = 1 << 9
  };
  // UNIMPLEMENTED: EnumSet<FsSelection> asSet(long range1, long range2,
  //                                           long range3, long range4)
  //                long[] asArray(EnumSet<FsSelection> rangeSet)
};

// C++ port only: C++ does not support 64-bit enums until C++0x.  For better
// portability, we need to use static const int64_t instead.
struct CodePageRange {
  static const int64_t kLatin1_1252;
  static const int64_t kLatin2_1250;
  static const int64_t kCyrillic_1251;
  static const int64_t kGreek_1253;
  static const int64_t kTurkish_1254;
  static const int64_t kHebrew_1255;
  static const int64_t kArabic_1256;
  static const int64_t kWindowsBaltic_1257;
  static const int64_t kVietnamese_1258;
  static const int64_t kAlternateANSI9;
  static const int64_t kAlternateANSI10;
  static const int64_t kAlternateANSI11;
  static const int64_t kAlternateANSI12;
  static const int64_t kAlternateANSI13;
  static const int64_t kAlternateANSI14;
  static const int64_t kAlternateANSI15;
  static const int64_t kThai_874;
  static const int64_t kJapanJIS_932;
  static const int64_t kChineseSimplified_936;
  static const int64_t kKoreanWansung_949;
  static const int64_t kChineseTraditional_950;
  static const int64_t kKoreanJohab_1361;
  static const int64_t kAlternateANSI22;
  static const int64_t kAlternateANSI23;
  static const int64_t kAlternateANSI24;
  static const int64_t kAlternateANSI25;
  static const int64_t kAlternateANSI26;
  static const int64_t kAlternateANSI27;
  static const int64_t kAlternateANSI28;
  static const int64_t kMacintoshCharacterSet;
  static const int64_t kOEMCharacterSet;
  static const int64_t kSymbolCharacterSet;
  static const int64_t kReservedForOEM32;
  static const int64_t kReservedForOEM33;
  static const int64_t kReservedForOEM34;
  static const int64_t kReservedForOEM35;
  static const int64_t kReservedForOEM36;
  static const int64_t kReservedForOEM37;
  static const int64_t kReservedForOEM38;
  static const int64_t kReservedForOEM39;
  static const int64_t kReservedForOEM40;
  static const int64_t kReservedForOEM41;
  static const int64_t kReservedForOEM42;
  static const int64_t kReservedForOEM43;
  static const int64_t kReservedForOEM44;
  static const int64_t kReservedForOEM45;
  static const int64_t kReservedForOEM46;
  static const int64_t kReservedForOEM47;
  static const int64_t kIBMGreek_869;
  static const int64_t kMSDOSRussion_866;
  static const int64_t kMSDOSNordic_865;
  static const int64_t kArabic_864;
  static const int64_t kMSDOSCanadianFrench_863;
  static const int64_t kHebrew_862;
  static const int64_t kMSDOSIcelandic_861;
  static const int64_t kMSDOSPortugese_860;
  static const int64_t kIBMTurkish_857;
  static const int64_t kIBMCyrillic_855;
  static const int64_t kLatin2_852;
  static const int64_t kMSDOSBaltic_775;
  static const int64_t kGreek_737;
  static const int64_t kArabic_708;
  static const int64_t kLatin1_850;
  static const int64_t kUS_437;

  // UNIMPLEMENTED: EnumSet<CodePageRange> asSet(long range1, long range2,
  //                                             long range3, long range4)
  //                long[] asArray(EnumSet<CodePageRange> rangeSet)
};

// An OS/2 table - 'OS/2'.
class OS2Table : public Table, public RefCounted<OS2Table> {
 public:
  // A builder for the OS/2 table = 'OS/2'.
  class Builder : public TableBasedTableBuilder, public RefCounted<Builder> {
   public:
    Builder(Header* header, WritableFontData* data);
    Builder(Header* header, ReadableFontData* data);
    virtual ~Builder();
    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);

    static CALLER_ATTACH Builder* CreateBuilder(Header* header,
                                                WritableFontData* data);

    int32_t TableVersion();
    void SetTableVersion(int32_t version);
    int32_t XAvgCharWidth();
    void SetXAvgCharWidth(int32_t width);
    int32_t UsWeightClass();
    void SetUsWeightClass(int32_t weight);
    int32_t UsWidthClass();
    void SetUsWidthClass(int32_t width);
    // UNIMPLEMENTED: EnumSet<EmbeddingFlags> fsType()
    //                void setFsType(EnumSeT<EmbeddingFlags> flagSet)
    int32_t FsType();
    void SetFsType(int32_t fs_type);
    int32_t YSubscriptXSize();
    void SetYSubscriptXSize(int32_t size);
    int32_t YSubscriptYSize();
    void SetYSubscriptYSize(int32_t size);
    int32_t YSubscriptXOffset();
    void SetYSubscriptXOffset(int32_t offset);
    int32_t YSubscriptYOffset();
    void SetYSubscriptYOffset(int32_t offset);
    int32_t YSuperscriptXSize();
    void SetYSuperscriptXSize(int32_t size);
    int32_t YSuperscriptYSize();
    void SetYSuperscriptYSize(int32_t size);
    int32_t YSuperscriptXOffset();
    void SetYSuperscriptXOffset(int32_t offset);
    int32_t YSuperscriptYOffset();
    void SetYSuperscriptYOffset(int32_t offset);
    int32_t YStrikeoutSize();
    void SetYStrikeoutSize(int32_t size);
    int32_t YStrikeoutPosition();
    void SetYStrikeoutPosition(int32_t position);
    int32_t SFamilyClass();
    void SetSFamilyClass(int32_t family);
    void Panose(ByteVector* value);
    void SetPanose(ByteVector* panose);
    int64_t UlUnicodeRange1();
    void SetUlUnicodeRange1(int64_t range);
    int64_t UlUnicodeRange2();
    void SetUlUnicodeRange2(int64_t range);
    int64_t UlUnicodeRange3();
    void SetUlUnicodeRange3(int64_t range);
    int64_t UlUnicodeRange4();
    void SetUlUnicodeRange4(int64_t range);
    // UNIMPLEMENTED: EnumSet<UnicodeRange> UlUnicodeRange()
    //                setUlUnicodeRange(EnumSet<UnicodeRange> rangeSet)
    void AchVendId(ByteVector* b);
    // This field is 4 bytes in length and only the first 4 bytes of the byte
    // array will be written. If the byte array is less than 4 bytes it will be
    // padded out with space characters (0x20).
    // @param b ach Vendor Id
    void SetAchVendId(ByteVector* b);
    // UNIMPLEMENTED: public EnumSet<FsSelection> fsSelection()
    int32_t FsSelection();
    void SetFsSelection(int32_t fs_selection);
    int32_t UsFirstCharIndex();
    void SetUsFirstCharIndex(int32_t first_index);
    int32_t UsLastCharIndex();
    void SetUsLastCharIndex(int32_t last_index);
    int32_t STypoAscender();
    void SetSTypoAscender(int32_t ascender);
    int32_t STypoDescender();
    void SetSTypoDescender(int32_t descender);
    int32_t STypoLineGap();
    void SetSTypoLineGap(int32_t line_gap);
    int32_t UsWinAscent();
    void SetUsWinAscent(int32_t ascent);
    int32_t UsWinDescent();
    void SetUsWinDescent(int32_t descent);
    int64_t UlCodePageRange1();
    void SetUlCodePageRange1(int64_t range);
    int64_t UlCodePageRange2();
    void SetUlCodePageRange2(int64_t range);
    // UNIMPLEMENTED: EnumSet<CodePageRange> ulCodePageRange()
    //                void setUlCodePageRange(EnumSet<CodePageRange> rangeSet)
    int32_t SxHeight();
    void SetSxHeight(int32_t height);
    int32_t SCapHeight();
    void SetSCapHeight(int32_t height);
    int32_t UsDefaultChar();
    void SetUsDefaultChar(int32_t default_char);
    int32_t UsBreakChar();
    void SetUsBreakChar(int32_t break_char);
    int32_t UsMaxContext();
    void SetUsMaxContext(int32_t max_context);
  };

  ~OS2Table();

  int32_t TableVersion();
  int32_t XAvgCharWidth();
  int32_t UsWeightClass();
  int32_t UsWidthClass();
  // UNIMPLEMENTED: public EnumSet<EmbeddingFlags> fsType()
  int32_t FsType();
  int32_t YSubscriptXSize();
  int32_t YSubscriptYSize();
  int32_t YSubscriptXOffset();
  int32_t YSubscriptYOffset();
  int32_t YSuperscriptXSize();
  int32_t YSuperscriptYSize();
  int32_t YSuperscriptXOffset();
  int32_t YSuperscriptYOffset();
  int32_t YStrikeoutSize();
  int32_t YStrikeoutPosition();
  int32_t SFamilyClass();
  void Panose(ByteVector* value);
  int64_t UlUnicodeRange1();
  int64_t UlUnicodeRange2();
  int64_t UlUnicodeRange3();
  int64_t UlUnicodeRange4();
  // UNIMPLEMENTED: public EnumSet<UnicodeRange> UlUnicodeRange()
  void AchVendId(ByteVector* b);
  // UNIMPLEMENTED: public EnumSet<FsSelection> fsSelection()
  int32_t FsSelection();
  int32_t UsFirstCharIndex();
  int32_t UsLastCharIndex();
  int32_t STypoAscender();
  int32_t STypoDescender();
  int32_t STypoLineGap();
  int32_t UsWinAscent();
  int32_t UsWinDescent();
  int64_t UlCodePageRange1();
  int64_t UlCodePageRange2();
  // UNIMPLEMENTED: public EnumSet<CodePageRange> ulCodePageRange()
  int32_t SxHeight();
  int32_t SCapHeight();
  int32_t UsDefaultChar();
  int32_t UsBreakChar();
  int32_t UsMaxContext();

 private:
  struct Offset {
    enum {
      kVersion = 0,
      kXAvgCharWidth = 2,
      kUsWeightClass = 4,
      kUsWidthClass = 6,
      kFsType = 8,
      kYSubscriptXSize = 10,
      kYSubscriptYSize = 12,
      kYSubscriptXOffset = 14,
      kYSubscriptYOffset = 16,
      kYSuperscriptXSize = 18,
      kYSuperscriptYSize = 20,
      kYSuperscriptXOffset = 22,
      kYSuperscriptYOffset = 24,
      kYStrikeoutSize = 26,
      kYStrikeoutPosition = 28,
      kSFamilyClass = 30,
      kPanose = 32,
      kPanoseLength = 10,  // Length of panose bytes.
      kUlUnicodeRange1 = 42,
      kUlUnicodeRange2 = 46,
      kUlUnicodeRange3 = 50,
      kUlUnicodeRange4 = 54,
      kAchVendId = 58,
      kAchVendIdLength = 4,  // Length of ach vend id bytes.
      kFsSelection = 62,
      kUsFirstCharIndex = 64,
      kUsLastCharIndex = 66,
      kSTypoAscender = 68,
      kSTypoDescender = 70,
      kSTypoLineGap = 72,
      kUsWinAscent = 74,
      kUsWinDescent = 76,
      kUlCodePageRange1 = 78,
      kUlCodePageRange2 = 82,
      kSxHeight = 86,
      kSCapHeight = 88,
      kUsDefaultChar = 90,
      kUsBreakChar = 92,
      kUsMaxContext = 94
    };
  };

  OS2Table(Header* header, ReadableFontData* data);
};
typedef Ptr<OS2Table> OS2TablePtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_OS2_TABLE_H_
