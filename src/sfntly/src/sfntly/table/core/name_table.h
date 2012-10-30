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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_NAME_TABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_NAME_TABLE_H_

// Must include this before ICU to avoid stdint redefinition issue.
#include "sfntly/port/type.h"

#include <unicode/ucnv.h>
#include <unicode/ustring.h>

#include <map>
#include <utility>

#include "sfntly/port/java_iterator.h"
#include "sfntly/table/subtable_container_table.h"

namespace sfntly {

// The following code implements the name table defined in TTF/OTF spec, which
// can be found at http://www.microsoft.com/typography/otspec/name.htm.

// Name IDs defined in TTF/OTF spec.
struct NameId {
  enum {
    kUnknown = -1,
    kCopyrightNotice = 0,
    kFontFamilyName = 1,
    kFontSubfamilyName = 2,
    kUniqueFontIdentifier = 3,
    kFullFontName = 4,
    kVersionString = 5,
    kPostscriptName = 6,
    kTrademark = 7,
    kManufacturerName = 8,
    kDesigner = 9,
    kDescription = 10,
    kVendorURL = 11,
    kDesignerURL = 12,
    kLicenseDescription = 13,
    kLicenseInfoURL = 14,
    kReserved15 = 15,
    kPreferredFamily = 16,
    kPreferredSubfamily = 17,
    kCompatibleFullName = 18,
    kSampleText = 19,
    kPostscriptCID = 20,
    kWWSFamilyName = 21,
    kWWSSubfamilyName = 22
  };
};

// Unicode language IDs used in Name Records.
struct UnicodeLanguageId {
  enum {
    kUnknown = -1,
    kAll = 0
  };
};

// Macintosh Language IDs (platform ID = 1)
struct MacintoshLanguageId {
  enum {
    kUnknown = -1,
    kEnglish = 0,
    kFrench = 1,
    kGerman = 2,
    kItalian = 3,
    kDutch = 4,
    kSwedish = 5,
    kSpanish = 6,
    kDanish = 7,
    kPortuguese = 8,
    kNorwegian = 9,
    kHebrew = 10,
    kJapanese = 11,
    kArabic = 12,
    kFinnish = 13,
    kGreek = 14,
    kIcelandic = 15,
    kMaltese = 16,
    kTurkish = 17,
    kCroatian = 18,
    kChinese_Traditional = 19,
    kUrdu = 20,
    kHindi = 21,
    kThai = 22,
    kKorean = 23,
    kLithuanian = 24,
    kPolish = 25,
    kHungarian = 26,
    kEstonian = 27,
    kLatvian = 28,
    kSami = 29,
    kFaroese = 30,
    kFarsiPersian = 31,
    kRussian = 32,
    kChinese_Simplified = 33,
    kFlemish = 34,
    kIrishGaelic = 35,
    kAlbanian = 36,
    kRomanian = 37,
    kCzech = 38,
    kSlovak = 39,
    kSlovenian = 40,
    kYiddish = 41,
    kSerbian = 42,
    kMacedonian = 43,
    kBulgarian = 44,
    kUkrainian = 45,
    kByelorussian = 46,
    kUzbek = 47,
    kKazakh = 48,
    kAzerbaijani_Cyrillic = 49,
    kAzerbaijani_Arabic = 50,
    kArmenian = 51,
    kGeorgian = 52,
    kMoldavian = 53,
    kKirghiz = 54,
    kTajiki = 55,
    kTurkmen = 56,
    kMongolian_Mongolian = 57,
    kMongolian_Cyrillic = 58,
    kPashto = 59,
    kKurdish = 60,
    kKashmiri = 61,
    kSindhi = 62,
    kTibetan = 63,
    kNepali = 64,
    kSanskrit = 65,
    kMarathi = 66,
    kBengali = 67,
    kAssamese = 68,
    kGujarati = 69,
    kPunjabi = 70,
    kOriya = 71,
    kMalayalam = 72,
    kKannada = 73,
    kTamil = 74,
    kTelugu = 75,
    kSinhalese = 76,
    kBurmese = 77,
    kKhmer = 78,
    kLao = 79,
    kVietnamese = 80,
    kIndonesian = 81,
    kTagalong = 82,
    kMalay_Roman = 83,
    kMalay_Arabic = 84,
    kAmharic = 85,
    kTigrinya = 86,
    kGalla = 87,
    kSomali = 88,
    kSwahili = 89,
    kKinyarwandaRuanda = 90,
    kRundi = 91,
    kNyanjaChewa = 92,
    kMalagasy = 93,
    kEsperanto = 94,
    kWelsh = 128,
    kBasque = 129,
    kCatalan = 130,
    kLatin = 131,
    kQuenchua = 132,
    kGuarani = 133,
    kAymara = 134,
    kTatar = 135,
    kUighur = 136,
    kDzongkha = 137,
    kJavanese_Roman = 138,
    kSundanese_Roman = 139,
    kGalician = 140,
    kAfrikaans = 141,
    kBreton = 142,
    kInuktitut = 143,
    kScottishGaelic = 144,
    kManxGaelic = 145,
    kIrishGaelic_WithDotAbove = 146,
    kTongan = 147,
    kGreek_Polytonic = 148,
    kGreenlandic = 149,
    kAzerbaijani_Roman = 150
  };
};

// Windows Language IDs (platformID = 3)
struct WindowsLanguageId {
  enum {
    kUnknown = -1,
    kAfrikaans_SouthAfrica = 0x0436,
    kAlbanian_Albania = 0x041C,
    kAlsatian_France = 0x0484,
    kAmharic_Ethiopia = 0x045E,
    kArabic_Algeria = 0x1401,
    kArabic_Bahrain = 0x3C01,
    kArabic_Egypt = 0x0C01,
    kArabic_Iraq = 0x0801,
    kArabic_Jordan = 0x2C01,
    kArabic_Kuwait = 0x3401,
    kArabic_Lebanon = 0x3001,
    kArabic_Libya = 0x1001,
    kArabic_Morocco = 0x1801,
    kArabic_Oman = 0x2001,
    kArabic_Qatar = 0x4001,
    kArabic_SaudiArabia = 0x0401,
    kArabic_Syria = 0x2801,
    kArabic_Tunisia = 0x1C01,
    kArabic_UAE = 0x3801,
    kArabic_Yemen = 0x2401,
    kArmenian_Armenia = 0x042B,
    kAssamese_India = 0x044D,
    kAzeri_Cyrillic_Azerbaijan = 0x082C,
    kAzeri_Latin_Azerbaijan = 0x042C,
    kBashkir_Russia = 0x046D,
    kBasque_Basque = 0x042D,
    kBelarusian_Belarus = 0x0423,
    kBengali_Bangladesh = 0x0845,
    kBengali_India = 0x0445,
    kBosnian_Cyrillic_BosniaAndHerzegovina = 0x201A,
    kBosnian_Latin_BosniaAndHerzegovina = 0x141A,
    kBreton_France = 0x047E,
    kBulgarian_Bulgaria = 0x0402,
    kCatalan_Catalan = 0x0403,
    kChinese_HongKongSAR = 0x0C04,
    kChinese_MacaoSAR = 0x1404,
    kChinese_PeoplesRepublicOfChina = 0x0804,
    kChinese_Singapore = 0x1004,
    kChinese_Taiwan = 0x0404,
    kCorsican_France = 0x0483,
    kCroatian_Croatia = 0x041A,
    kCroatian_Latin_BosniaAndHerzegovina = 0x101A,
    kCzech_CzechRepublic = 0x0405,
    kDanish_Denmark = 0x0406,
    kDari_Afghanistan = 0x048C,
    kDivehi_Maldives = 0x0465,
    kDutch_Belgium = 0x0813,
    kDutch_Netherlands = 0x0413,
    kEnglish_Australia = 0x0C09,
    kEnglish_Belize = 0x2809,
    kEnglish_Canada = 0x1009,
    kEnglish_Caribbean = 0x2409,
    kEnglish_India = 0x4009,
    kEnglish_Ireland = 0x1809,
    kEnglish_Jamaica = 0x2009,
    kEnglish_Malaysia = 0x4409,
    kEnglish_NewZealand = 0x1409,
    kEnglish_RepublicOfThePhilippines = 0x3409,
    kEnglish_Singapore = 0x4809,
    kEnglish_SouthAfrica = 0x1C09,
    kEnglish_TrinidadAndTobago = 0x2C09,
    kEnglish_UnitedKingdom = 0x0809,
    kEnglish_UnitedStates = 0x0409,
    kEnglish_Zimbabwe = 0x3009,
    kEstonian_Estonia = 0x0425,
    kFaroese_FaroeIslands = 0x0438,
    kFilipino_Philippines = 0x0464,
    kFinnish_Finland = 0x040B,
    kFrench_Belgium = 0x080C,
    kFrench_Canada = 0x0C0C,
    kFrench_France = 0x040C,
    kFrench_Luxembourg = 0x140c,
    kFrench_PrincipalityOfMonoco = 0x180C,
    kFrench_Switzerland = 0x100C,
    kFrisian_Netherlands = 0x0462,
    kGalician_Galician = 0x0456,
    kGeorgian_Georgia = 0x0437,
    kGerman_Austria = 0x0C07,
    kGerman_Germany = 0x0407,
    kGerman_Liechtenstein = 0x1407,
    kGerman_Luxembourg = 0x1007,
    kGerman_Switzerland = 0x0807,
    kGreek_Greece = 0x0408,
    kGreenlandic_Greenland = 0x046F,
    kGujarati_India = 0x0447,
    kHausa_Latin_Nigeria = 0x0468,
    kHebrew_Israel = 0x040D,
    kHindi_India = 0x0439,
    kHungarian_Hungary = 0x040E,
    kIcelandic_Iceland = 0x040F,
    kIgbo_Nigeria = 0x0470,
    kIndonesian_Indonesia = 0x0421,
    kInuktitut_Canada = 0x045D,
    kInuktitut_Latin_Canada = 0x085D,
    kIrish_Ireland = 0x083C,
    kisiXhosa_SouthAfrica = 0x0434,
    kisiZulu_SouthAfrica = 0x0435,
    kItalian_Italy = 0x0410,
    kItalian_Switzerland = 0x0810,
    kJapanese_Japan = 0x0411,
    kKannada_India = 0x044B,
    kKazakh_Kazakhstan = 0x043F,
    kKhmer_Cambodia = 0x0453,
    kKiche_Guatemala = 0x0486,
    kKinyarwanda_Rwanda = 0x0487,
    kKiswahili_Kenya = 0x0441,
    kKonkani_India = 0x0457,
    kKorean_Korea = 0x0412,
    kKyrgyz_Kyrgyzstan = 0x0440,
    kLao_LaoPDR = 0x0454,
    kLatvian_Latvia = 0x0426,
    kLithuanian_Lithuania = 0x0427,
    kLowerSorbian_Germany = 0x082E,
    kLuxembourgish_Luxembourg = 0x046E,
    kMacedonian_FYROM_FormerYugoslavRepublicOfMacedonia = 0x042F,
    kMalay_BruneiDarussalam = 0x083E,
    kMalay_Malaysia = 0x043E,
    kMalayalam_India = 0x044C,
    kMaltese_Malta = 0x043A,
    kMaori_NewZealand = 0x0481,
    kMapudungun_Chile = 0x047A,
    kMarathi_India = 0x044E,
    kMohawk_Mohawk = 0x047C,
    kMongolian_Cyrillic_Mongolia = 0x0450,
    kMongolian_Traditional_PeoplesRepublicOfChina = 0x0850,
    kNepali_Nepal = 0x0461,
    kNorwegian_Bokmal_Norway = 0x0414,
    kNorwegian_Nynorsk_Norway = 0x0814,
    kOccitan_France = 0x0482,
    kOriya_India = 0x0448,
    kPashto_Afghanistan = 0x0463,
    kPolish_Poland = 0x0415,
    kPortuguese_Brazil = 0x0416,
    kPortuguese_Portugal = 0x0816,
    kPunjabi_India = 0x0446,
    kQuechua_Bolivia = 0x046B,
    kQuechua_Ecuador = 0x086B,
    kQuechua_Peru = 0x0C6B,
    kRomanian_Romania = 0x0418,
    kRomansh_Switzerland = 0x0417,
    kRussian_Russia = 0x0419,
    kSami_Inari_Finland = 0x243B,
    kSami_Lule_Norway = 0x103B,
    kSami_Lule_Sweden = 0x143B,
    kSami_Northern_Finland = 0x0C3B,
    kSami_Northern_Norway = 0x043B,
    kSami_Northern_Sweden = 0x083B,
    kSami_Skolt_Finland = 0x203B,
    kSami_Southern_Norway = 0x183B,
    kSami_Southern_Sweden = 0x1C3B,
    kSanskrit_India = 0x044F,
    kSerbian_Cyrillic_BosniaAndHerzegovina = 0x1C1A,
    kSerbian_Cyrillic_Serbia = 0x0C1A,
    kSerbian_Latin_BosniaAndHerzegovina = 0x181A,
    kSerbian_Latin_Serbia = 0x081A,
    kSesothoSaLeboa_SouthAfrica = 0x046C,
    kSetswana_SouthAfrica = 0x0432,
    kSinhala_SriLanka = 0x045B,
    kSlovak_Slovakia = 0x041B,
    kSlovenian_Slovenia = 0x0424,
    kSpanish_Argentina = 0x2C0A,
    kSpanish_Bolivia = 0x400A,
    kSpanish_Chile = 0x340A,
    kSpanish_Colombia = 0x240A,
    kSpanish_CostaRica = 0x140A,
    kSpanish_DominicanRepublic = 0x1C0A,
    kSpanish_Ecuador = 0x300A,
    kSpanish_ElSalvador = 0x440A,
    kSpanish_Guatemala = 0x100A,
    kSpanish_Honduras = 0x480A,
    kSpanish_Mexico = 0x080A,
    kSpanish_Nicaragua = 0x4C0A,
    kSpanish_Panama = 0x180A,
    kSpanish_Paraguay = 0x3C0A,
    kSpanish_Peru = 0x280A,
    kSpanish_PuertoRico = 0x500A,
    kSpanish_ModernSort_Spain = 0x0C0A,
    kSpanish_TraditionalSort_Spain = 0x040A,
    kSpanish_UnitedStates = 0x540A,
    kSpanish_Uruguay = 0x380A,
    kSpanish_Venezuela = 0x200A,
    kSweden_Finland = 0x081D,
    kSwedish_Sweden = 0x041D,
    kSyriac_Syria = 0x045A,
    kTajik_Cyrillic_Tajikistan = 0x0428,
    kTamazight_Latin_Algeria = 0x085F,
    kTamil_India = 0x0449,
    kTatar_Russia = 0x0444,
    kTelugu_India = 0x044A,
    kThai_Thailand = 0x041E,
    kTibetan_PRC = 0x0451,
    kTurkish_Turkey = 0x041F,
    kTurkmen_Turkmenistan = 0x0442,
    kUighur_PRC = 0x0480,
    kUkrainian_Ukraine = 0x0422,
    kUpperSorbian_Germany = 0x042E,
    kUrdu_IslamicRepublicOfPakistan = 0x0420,
    kUzbek_Cyrillic_Uzbekistan = 0x0843,
    kUzbek_Latin_Uzbekistan = 0x0443,
    kVietnamese_Vietnam = 0x042A,
    kWelsh_UnitedKingdom = 0x0452,
    kWolof_Senegal = 0x0448,
    kYakut_Russia = 0x0485,
    kYi_PRC = 0x0478,
    kYoruba_Nigeria = 0x046A
  };
};

class NameTable : public SubTableContainerTable, public RefCounted<NameTable> {
 public:
  // Unique identifier for a given name record.
  class NameEntryId {
   public:
    NameEntryId();  // C++ port only, must provide default constructor.
    NameEntryId(int32_t platform_id, int32_t encoding_id, int32_t language_id,
                int32_t name_id);
    NameEntryId(const NameEntryId&);
    // Make gcc -Wnon-virtual-dtor happy.
    virtual ~NameEntryId() {}

    int32_t platform_id() const { return platform_id_; }
    int32_t encoding_id() const { return encoding_id_; }
    int32_t language_id() const { return language_id_; }
    int32_t name_id() const { return name_id_; }

    const NameEntryId& operator=(const NameEntryId& rhs) const;
    bool operator==(const NameEntryId& rhs) const;
    bool operator<(const NameEntryId& rhs) const;

    // UNIMPLEMENTED: int hashCode()
    //                String toString()

   private:
    mutable int32_t platform_id_;
    mutable int32_t encoding_id_;
    mutable int32_t language_id_;
    mutable int32_t name_id_;
  };

  class NameEntryBuilder;

  // Class to represent a name entry in the name table.
  class NameEntry : public RefCounted<NameEntry> {
   public:
    NameEntry();
    NameEntry(const NameEntryId& name_entry_id, const ByteVector& name_bytes);
    NameEntry(int32_t platform_id,
              int32_t encoding_id,
              int32_t language_id,
              int32_t name_id,
              const ByteVector& name_bytes);
    virtual ~NameEntry();

    NameEntryId& name_entry_id() { return name_entry_id_; }
    int32_t platform_id() const { return name_entry_id_.platform_id(); }
    int32_t encoding_id() const { return name_entry_id_.encoding_id(); }
    int32_t language_id() const { return name_entry_id_.language_id(); }
    int32_t name_id() const { return name_entry_id_.name_id(); }

    // Get the bytes for name.  Returned pointer is the address of private
    // member of this class, do not attempt to delete.
    ByteVector* NameAsBytes();

    // C++ port only: get the length of NameAsBytes.
    int32_t NameBytesLength();

    // Returns the name in Unicode as UChar array.
    // Note: ICU UChar* convention requires caller to delete[] it.
    UChar* Name();
    bool operator==(const NameEntry& rhs) const;

    // UNIMPLEMENTED: String toString()
    //                int hashCode()

   private:
    void Init(int32_t platform_id, int32_t encoding_id, int32_t language_id,
              int32_t name_id, const ByteVector* name_bytes);

    NameEntryId name_entry_id_;
    int32_t length_;
    ByteVector name_bytes_;

    friend class NameEntryBuilder;
  };

  // Builder of a name entry.
  // C++ port: original Java hierarchy inherits from NameEntry.  In C++ port, we
  // opted not doing so to avoid ref count issues and nasty protected members.
  class NameEntryBuilder : public RefCounted<NameEntryBuilder> {
   public:
    NameEntryBuilder();
    NameEntryBuilder(const NameEntryId& name_entry_id,
                     const ByteVector& name_bytes);
    explicit NameEntryBuilder(const NameEntryId& name_entry_id);
    explicit NameEntryBuilder(NameEntry* entry);
    virtual ~NameEntryBuilder();

    virtual void SetName(const UChar* name);
    virtual void SetName(const ByteVector& name_bytes);
    virtual void SetName(const ByteVector& name_bytes,
                         int32_t offset,
                         int32_t length);

    // C++ port only. CALLER_ATTACH is not added because the lifetime shall be
    // controlled by this class, therefore the caller shall not increase the ref
    // count.
    NameEntry* name_entry() { return name_entry_; }

   private:
    void Init(int32_t platform_id, int32_t encoding_id, int32_t language_id,
              int32_t name_id, const ByteVector* name_bytes);

    Ptr<NameEntry> name_entry_;
  };
  typedef std::map<NameEntryId, Ptr<NameEntryBuilder> > NameEntryBuilderMap;

  // An interface for a filter to use with the name entry iterator. This allows
  // name entries to be iterated and only those acceptable to the filter will be
  // returned.
  class NameEntryFilter {
   public:
    virtual bool Accept(int32_t platform_id,
                        int32_t encoding_id,
                        int32_t language_id,
                        int32_t name_id) = 0;
    // Make gcc -Wnon-virtual-dtor happy.
    virtual ~NameEntryFilter() {}
  };

  // C++ port only: an in-place filter to mimic Java Iterator's filtering.
  class NameEntryFilterInPlace : public NameEntryFilter {
   public:
    NameEntryFilterInPlace(int32_t platform_id,
                           int32_t encoding_id,
                           int32_t language_id,
                           int32_t name_id);
    // Make gcc -Wnon-virtual-dtor happy.
    virtual ~NameEntryFilterInPlace() {}

    virtual bool Accept(int32_t platform_id,
                        int32_t encoding_id,
                        int32_t language_id,
                        int32_t name_id);

   private:
    int32_t platform_id_;
    int32_t encoding_id_;
    int32_t language_id_;
    int32_t name_id_;
  };

  class NameEntryIterator : public RefIterator<NameEntry, NameTable> {
   public:
    // If filter is NULL, filter through all tables.
    explicit NameEntryIterator(NameTable* table);
    NameEntryIterator(NameTable* table, NameEntryFilter* filter);
    virtual ~NameEntryIterator() {}

    virtual bool HasNext();
    virtual CALLER_ATTACH NameEntry* Next();

   private:
    int32_t name_index_;
    NameEntryFilter* filter_;
  };

  // The builder to construct name table for outputting.
  class Builder : public SubTableContainerTable::Builder,
                  public RefCounted<Builder> {
   public:
    // Constructor scope altered to public because C++ does not allow base
    // class to instantiate derived class with protected constructors.
    Builder(Header* header, WritableFontData* data);
    Builder(Header* header, ReadableFontData* data);

    static CALLER_ATTACH Builder* CreateBuilder(Header* header,
                                                WritableFontData* data);

    // Revert the name builders for the name table to the last version that came
    // from data.
    void RevertNames();

    // Number of name entry builders contained.
    int32_t BuilderCount();

    // Note: For C++ port, clear() is not implemented.  The clear() function
    //       implies completely remove name entry builders, which is easy in
    //       Java but will take a lot of efforts in C++ to release the builders
    //       nicely and correctly.
    // TODO(arthurhsu): IMPLEMENT
    // Clear the name builders for the name table.
    // void clear();

    // Check the existance of a name entry builder by key.
    bool Has(int32_t platform_id, int32_t encoding_id, int32_t language_id,
             int32_t name_id);

    // Get name entry builder by key.
    CALLER_ATTACH NameEntryBuilder* NameBuilder(int32_t platform_id,
        int32_t encoding_id, int32_t language_id, int32_t name_id);

    // Remove name entry builder by key.
    bool Remove(int32_t platform_id, int32_t encoding_id, int32_t language_id,
                int32_t name_id);

    // FontDataTable::Builder API implementation
    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);
    virtual void SubDataSet();
    virtual int32_t SubDataSizeToSerialize();
    virtual bool SubReadyToSerialize();
    virtual int32_t SubSerialize(WritableFontData* new_data);

   private:
    void Initialize(ReadableFontData* data);
    NameEntryBuilderMap* GetNameBuilders();

    // Note: callers should use the getter funtion provided above to ensure that
    // this is lazily initialized instead of accessing directly.
    NameEntryBuilderMap name_entry_map_;
  };

  /****************************************************************************
   * public methods of NameTable class
   ****************************************************************************/
  virtual ~NameTable();

  // Get the format used in the name table.
  virtual int32_t Format();

  // Get the number of names in the name table.
  virtual int32_t NameCount();

  // Get the platform id for the given name record.
  virtual int32_t PlatformId(int32_t index);

  // Get the encoding id for the given name record.
  // see MacintoshEncodingId, WindowsEncodingId, UnicodeEncodingId
  virtual int32_t EncodingId(int32_t index);

  // Get the language id for the given name record.
  virtual int32_t LanguageId(int32_t index);

  // Get the name id for given name record.
  virtual int32_t NameId(int32_t index);

  // Get the name as bytes for the specified name. If there is no entry for the
  // requested name, then empty vector is returned.
  virtual void NameAsBytes(int32_t index, ByteVector* b);
  virtual void NameAsBytes(int32_t platform_id, int32_t encoding_id,
                           int32_t language_id, int32_t name_id,
                           ByteVector* b);

  // Get the name as a UChar* for the given name record. If there is no
  // encoding conversion available for the name record then a best attempt
  // UChar* will be returned.
  // Note: ICU UChar* convention requires caller to delete[] it.
  virtual UChar* Name(int32_t index);

  // Get the name as a UChar* for the specified name. If there is no entry for
  // the requested name then NULL is returned. If there is no encoding
  // conversion available for the name then a best attempt UChar* will be
  // returned.
  // Note: ICU UChar* convention requires caller to delete[] it.
  virtual UChar* Name(int32_t platform_id, int32_t encoding_id,
                      int32_t language_id, int32_t name_id);

  // Note: These functions are renamed in C++ port.  Their original Java name is
  // nameEntry().
  virtual CALLER_ATTACH NameEntry* GetNameEntry(int32_t index);
  virtual CALLER_ATTACH NameEntry* GetNameEntry(int32_t platform_id,
      int32_t encoding_id, int32_t language_id, int32_t name_id);

  // Note: Not implemented in C++ port due to complexity and low usage.
  // virtual void names(std::set<NameEntryPtr>*);

  // Get the iterator to iterate through all name entries.
  virtual CALLER_ATTACH NameEntryIterator* Iterator();
  virtual CALLER_ATTACH NameEntryIterator* Iterator(NameEntryFilter* filter);

 private:
  struct Offset {
    enum {
      kFormat = 0,
      kCount = 2,
      kStringOffset = 4,
      kNameRecordStart = 6,

      // Format 1 - offset from the end of the name records
      kLangTagCount = 0,
      kLangTagRecord = 2,

      kNameRecordSize = 12,
      // Name Records
      kNameRecordPlatformId = 0,
      kNameRecordEncodingId = 2,
      kNameRecordLanguageId = 4,
      kNameRecordNameId = 6,
      kNameRecordStringLength = 8,
      kNameRecordStringOffset = 10
    };
  };

  // The table shall be constructed using Builder, no direct instantiation.
  NameTable(Header* header, ReadableFontData* data);

  // Get the offset to the string data in the name table.
  int32_t StringOffset();

  // Get the offset for the given name record.
  int32_t OffsetForNameRecord(int32_t index);

  // Get the length of the string data for the given name record.
  int32_t NameLength(int32_t index);

  // Get the offset of the string data for the given name record.
  int32_t NameOffset(int32_t index);

  // Note: string literals are returned.  Caller shall not attempt to manipulate
  // the returned pointer.
  static const char* GetEncodingName(int32_t platform_id, int32_t encoding_id);

  // Note: ICU UConverter* convention requires caller to ucnv_close() it.
  static UConverter* GetCharset(int32_t platform_id, int32_t encoding_id);

  // Note: Output will be stored in ByteVector* b.  Original data in b will be
  // erased and replaced with converted name bytes.
  static void ConvertToNameBytes(const UChar* name, int32_t platform_id,
                                 int32_t encoding_id, ByteVector* b);

  // Note: ICU UChar* convention requires caller to delete[] it.
  static UChar* ConvertFromNameBytes(ByteVector* name_bytes,
                                     int32_t platform_id, int32_t encoding_id);
};  // class NameTable
typedef Ptr<NameTable> NameTablePtr;
typedef Ptr<NameTable::NameEntry> NameEntryPtr;
typedef Ptr<NameTable::Builder> NameTableBuilderPtr;
typedef Ptr<NameTable::NameEntryBuilder> NameEntryBuilderPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_NAME_TABLE_H_
