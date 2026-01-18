#include <cstring>
#include <algorithm>
#include <optional>
#include <utility>
#include "mo_parser.h"

// Magic numbers for .mo files
constexpr uint32_t MO_MAGIC_LE = 0x950412de;
constexpr uint32_t MO_MAGIC_BE = 0xde120495;

MOParser::MOParser() : swap_bytes_(false), loaded_(false), data(NULL), sz(0), num_plurals_(2), plural_expr_("n != 1") { }

MOParser::~MOParser() {
    std::free((void*)data); data = NULL;
}

uint32_t MOParser::swap32(uint32_t value) const {
    return ((value & 0x000000FF) << 24) |
           ((value & 0x0000FF00) << 8) |
           ((value & 0x00FF0000) >> 8) |
           ((value & 0xFF000000) >> 24);
}

bool MOParser::needsSwap(uint32_t magic) const {
    return magic == MO_MAGIC_BE;
}

std::string MOParser::load(const char *data, size_t sz) {
    char *copy = (char*)std::malloc(sz);
    std::memcpy(copy, data, sz);
    this->data = copy;
    this->sz = sz;
    std::string err = "";
    err = parseHeader();
    if (err.size()) return err;
    err = parseStrings();
    if (err.size()) return err;
    loaded_ = true;
    return err;
}

std::string MOParser::parseHeader() {
    if (sz < sizeof(MOHeader)) return ".mo data too small (" + std::to_string(sz) + ")";

    // Read magic number to determine endianness
    uint32_t magic; std::memcpy(&magic, data, sizeof(uint32_t));

    if (magic != MO_MAGIC_LE && magic != MO_MAGIC_BE) {
        return ".mo data has unrecognised magic bytes";
    }

    swap_bytes_ = needsSwap(magic);

    // Read header
    std::memcpy(&header_, data, sizeof(MOHeader));

    // Swap bytes if needed
    if (swap_bytes_) {
        header_.magic = swap32(header_. magic);
        header_.revision = swap32(header_.revision);
        header_.num_strings = swap32(header_.num_strings);
        header_.offset_original = swap32(header_.offset_original);
        header_.offset_translation = swap32(header_.offset_translation);
        header_.hash_table_size = swap32(header_.hash_table_size);
        header_.hash_table_offset = swap32(header_.hash_table_offset);
    }

    return "";
}

std::string MOParser::parseStrings() {
    for (uint32_t i = 0; i < header_.num_strings; ++i) {
        // Read original string descriptor
        size_t orig_desc_offset = header_.offset_original + i * sizeof(StringDescriptor);
        if (orig_desc_offset + sizeof(StringDescriptor) > sz) return ".mo data too small for string descriptor";

        StringDescriptor orig_desc;
        std::memcpy(&orig_desc, data + orig_desc_offset, sizeof(StringDescriptor));

        if (swap_bytes_) {
            orig_desc.length = swap32(orig_desc.length);
            orig_desc.offset = swap32(orig_desc.offset);
        }

        // Read translation string descriptor
        size_t trans_desc_offset = header_.offset_translation + i * sizeof(StringDescriptor);
        if (trans_desc_offset + sizeof(StringDescriptor) > sz) return ".mo data too small for translation string descriptor";
        StringDescriptor trans_desc;
        std::memcpy(&trans_desc, data + trans_desc_offset, sizeof(StringDescriptor));

        if (swap_bytes_) {
            trans_desc.length = swap32(trans_desc.length);
            trans_desc.offset = swap32(trans_desc.offset);
        }

        // Read original string
        if (orig_desc.offset + orig_desc.length > sz) return ".mo data too small for msgid";
        std::string_view msgid(data + orig_desc.offset, orig_desc.length);

        // Read translation string
        if (trans_desc.offset + trans_desc.length > sz) return ".mo data too small for msg";
        std::string_view msgstr(data + trans_desc.offset, trans_desc.length);

        // First entry (empty msgid) contains metadata
        if (msgid.empty() && i == 0) {
            std::string err = parseMetadata(msgstr);
            if (err.size()) return err;
        } else translations_[msgid] = msgstr;
    }

    return "";
}

static std::string_view
trim(std::string_view str) {
    const char* whitespace = " \t\n\r\f\v";

    auto start = str.find_first_not_of(whitespace);
    if (start == std::string_view:: npos) {
        return std::string_view(); // All whitespace
    }

    auto end = str.find_last_not_of(whitespace);
    return str.substr(start, end - start + 1);
}

static std::string
to_ascii_lower(std::string_view sv) {
    std::string result;
    result.resize(sv.size());
    std::transform(sv.begin(), sv.end(), result.begin(),
                   [](unsigned char c) { return std::tolower(c); });
    return result;
}

static std::optional<std::pair<std::string_view, std::string_view>>
parse_key_value(std::string_view input) {
    auto pos = input.find(':');
    if (pos == std::string_view::npos) return std::nullopt;
    std::string_view key = trim(input.substr(0, pos));
    std::string_view value = trim(input.substr(pos + 1));
    return std::make_pair(key, value);
}

std::string
MOParser::parsePluralForms(std::string_view plural_forms_line) {
    // Extract nplurals
    size_t nplurals_pos = plural_forms_line.find("nplurals=");
    if (nplurals_pos != std::string::npos) {
        nplurals_pos += 9; // strlen("nplurals=")
        num_plurals_ = std::atoi(plural_forms_line.data() + nplurals_pos);
    }

    // Extract plural expression
    size_t plural_pos = plural_forms_line.find("plural=");
    if (plural_pos != std::string::npos) {
        plural_pos += 7; // strlen("plural=")
        size_t semicolon = plural_forms_line.find(';', plural_pos);
        if (semicolon == std::string::npos) semicolon = plural_forms_line.size();
        plural_expr_ = trim(plural_forms_line.substr(plural_pos, semicolon - plural_pos));
        // Parse the expression
        if (!plural_parser_.parse(plural_expr_)) {
            return std::string("failed to parse plural forms expresion: " + plural_expr_);
        }
    } else {
        // No plural expression, use default
        plural_parser_.parse(plural_expr_);
    }
    return "";
}

std::string
MOParser::parseMetadata(std::string_view header) {
    size_t pos = 0, start = 0;
    bool found_plural_forms = false;
    while (pos < header.size()) {
        if (header[pos] == '\n') {
            std::string_view line = header.substr(start, pos-start);
            start = pos + 1;
            if (auto result = parse_key_value(line)) {
                auto [key, value] = *result;
                auto lkey = to_ascii_lower(key);
                info[lkey] = value;
                if (lkey == "plural-forms") {
                    std::string err = parsePluralForms(value);
                    if (err.size()) return err;
                    found_plural_forms = true;
                } else if (lkey == "content-type") {
                    size_t ctpos = value.find("charset=");
                    if (ctpos != std::string::npos) {
                        std::string charset = to_ascii_lower(value.substr(
                                    ctpos + sizeof("charset"), value.size() - ctpos - sizeof("charset")));
                        if (charset != "utf8" && charset != "utf-8") {
                            return "unsupported charset in .mo file: " + std::string(charset);
                        }
                    }
                }
            }
        }
        pos++;
    }
    if (!found_plural_forms) plural_parser_.parse(plural_expr_);
    return "";
}

std::string_view
MOParser::gettext(std::string_view msgid) const {
    auto it = translations_.find(msgid);
    if (it != translations_.end() && ! it->second.empty()) {
        // Return first translation (before any null byte)
        size_t null_pos = it->second.find('\0');
        return (null_pos != std::string::npos) ? it->second.substr(0, null_pos) : it->second;
    }
    return std::string_view(NULL, 0);
}

std::string_view
MOParser::ngettext(std::string_view msgid, std::string_view msgid_plural, unsigned long n) const {
    // Create composite key for plural forms (msgid\0msgid_plural)
    std::string key = std::string(msgid) + '\0' + std::string(msgid_plural);

    auto it = translations_.find(key);
    if (it != translations_.end() && !it->second.empty()) {
        // Determine which plural form to use
        unsigned long plural_index = plural(n);

        // Ensure index is within bounds
        if (plural_index >= static_cast<unsigned long>(num_plurals_)) plural_index = num_plurals_ - 1;

        // Split translation by null bytes
        size_t start = 0;
        size_t pos;

        while ((pos = it->second.find('\0', start)) != std::string::npos) {
            std::string_view q = it->second.substr(start, pos - start);
            if (plural_index < 1) return q;
            start = pos + 1;
            plural_index--;
        }
    }
    return std::string_view(NULL, 0);
}
