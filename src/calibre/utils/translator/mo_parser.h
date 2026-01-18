/*
 * MoTranslator.h
 * Copyright (C) 2026 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once

#include <string>
#include <cstdint>
#include <unordered_map>
#include "plural_expression_parser.h"

typedef struct MOKey {
    std::string_view context, msgid, msgid_plural ;
    bool operator==(const MOKey& other) const = default;
} MOKey;

// Custom hasher as a separate struct
struct MoKeyHash {
    std::hash<std::string_view> h;
    size_t operator()(const MOKey& key) const {
        return h(key.msgid) ^ (h(key.msgid_plural) << 1) ^ (h(key.context) << 2);
    }
};

class MOParser {
public:
    MOParser();
    ~MOParser();

    // Load a . mo file
    std::string load(const char *data, size_t sz);

    std::string_view gettext(std::string_view msgid) const;
    std::string_view gettext(std::string_view context, std::string_view msgid) const;
    std::string_view gettext(std::string_view msgid, std::string_view msgid_plural, unsigned long n) const;
    std::string_view gettext(std::string_view context, std::string_view msgid, std::string_view msgid_plural, unsigned long n) const;

    // Check if file is loaded
    bool isLoaded() const { return loaded_; }

    // Get the number of strings in the catalog
    size_t size() const { return catalog.size(); }

    // Get plural expression string (for debugging)
    std::string getPluralExpression() const { return plural_expr_; }

    // Get number of plural forms
    unsigned getNumPlurals() const { return num_plurals_; }

    // Get plural message index
    unsigned long plural(int n) const { return plural_parser_.evaluate(n); }

    std::unordered_map<std::string, std::string_view> info;
private:
    struct MOHeader {
        uint32_t magic;
        uint32_t revision;
        uint32_t num_strings;
        uint32_t offset_original;
        uint32_t offset_translation;
        uint32_t hash_table_size;
        uint32_t hash_table_offset;
    };

    struct StringDescriptor {
        uint32_t length;
        uint32_t offset;
    };

    std::string parseHeader();
    std::string parseStrings();
    std::string parseMetadata(std::string_view header);
    std::string parsePluralForms(std::string_view line);

    uint32_t swap32(uint32_t value) const;
    bool needsSwap(uint32_t magic) const;

    MOHeader header_;
    bool swap_bytes_;
    bool loaded_;
    const char *data;
    size_t sz;

    // Map from msgid to translation(s)
    // For plural forms, translations are separated by null bytes
    std::unordered_map<MOKey, std::string_view, MoKeyHash> catalog;

    // Plural forms support
    unsigned num_plurals_;
    std::string plural_expr_;
    PluralExpressionParser plural_parser_;
};
