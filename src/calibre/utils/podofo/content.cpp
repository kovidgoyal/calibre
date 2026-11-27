/*
 * content.cpp
 * Copyright (C) 2026 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

// Statistics about what the content streams of pages draw, read without
// rendering them or decoding any images, used to find the scanned pages of
// searchable PDFs made by OCR programs, which have invisible text over them.

#include "global.h"
#include <array>
#include <vector>

using namespace pdf;

namespace {

// A PDF transformation matrix [a b c d e f]
typedef std::array<double, 6> TransformMatrix;

// The matrix that applies m and then n
static TransformMatrix
concat(const TransformMatrix &m, const TransformMatrix &n) {
    return {
        m[0] * n[0] + m[1] * n[2],
        m[0] * n[1] + m[1] * n[3],
        m[2] * n[0] + m[3] * n[2],
        m[2] * n[1] + m[3] * n[3],
        m[4] * n[0] + m[5] * n[2] + n[4],
        m[4] * n[1] + m[5] * n[3] + n[5]};
}

struct GraphicsState {
    TransformMatrix ctm = {1, 0, 0, 1, 0, 0};
    // The text rendering mode, set by Tr, 3 and 7 draw nothing
    int64_t render_mode = 0;
    // The number of bytes per character code of the current font, 2 for the
    // composite (Type0) fonts that OCR programs use
    unsigned bytes_per_code = 1;
};

struct PageStats {
    size_t visible_chars = 0, invisible_chars = 0;
    // The sum of the areas of the images drawn, in the units of the page
    double image_area = 0;
};

static unsigned
bytes_per_code(const PdfDictionary *resources, const PdfName &name) {
    if (!resources) return 1;
    const PdfObject *fonts_obj = resources->FindKey("Font");
    const PdfDictionary *fonts;
    if (!fonts_obj || !fonts_obj->TryGetDictionary(fonts)) return 1;
    const PdfObject *font_obj = fonts->FindKey(name.GetString());
    const PdfDictionary *font;
    if (!font_obj || !font_obj->TryGetDictionary(font)) return 1;
    const PdfObject *subtype = font->FindKey("Subtype");
    return subtype && subtype->IsName() && subtype->GetName() == "Type0" ? 2 : 1;
}

static size_t
string_chars(const PdfVariant &var, unsigned bytes_per_code) {
    if (var.IsString()) return var.GetString().GetRawData().size() / bytes_per_code;
    if (!var.IsArray()) return 0;
    size_t ans = 0;
    for (const auto &item : var.GetArray()) {
        if (item.IsString()) ans += item.GetString().GetRawData().size() / bytes_per_code;
    }
    return ans;
}

static double
area(const TransformMatrix &m) {
    // The area of the unit square, in which images are drawn, transformed by m
    double ans = m[0] * m[3] - m[1] * m[2];
    return ans < 0 ? -ans : ans;
}

static PageStats
page_stats(const PdfPage &page) {
    PageStats ans;
    std::vector<GraphicsState> states(1);
    std::vector<const PdfDictionary *> resources;
    const PdfResources *page_resources = static_cast<const PdfCanvas &>(page).GetResources();
    resources.push_back(page_resources ? &page_resources->GetDictionary() : nullptr);
    PdfContentReaderArgs args;
    args.Flags = PdfContentReaderFlags::SkipFetchInlineImages;
    PdfContentStreamReader reader(page, args);
    PdfContent content;
    while (reader.TryReadNext(content)) {
        GraphicsState &state = states.back();
        const PdfVariantStack &stack = content->Stack;
        switch (content.GetType()) {
            case PdfContentType::Operator:
                switch (content->Operator) {
                    case PdfOperator::q: states.push_back(state); break;
                    case PdfOperator::Q:
                        if (states.size() > 1) states.pop_back();
                        break;
                    case PdfOperator::cm:
                        if (stack.GetSize() >= 6) {
                            TransformMatrix m;
                            bool ok = true;
                            for (unsigned i = 0; i < 6; i++) {
                                // The operands are numbered from the last one
                                double val;
                                if (stack[5 - i].TryGetReal(val)) m[i] = val;
                                else ok = false;
                            }
                            if (ok) state.ctm = concat(m, state.ctm);
                        }
                        break;
                    case PdfOperator::Tr:
                        if (stack.GetSize() >= 1) {
                            int64_t mode;
                            if (stack[0].TryGetNumber(mode)) state.render_mode = mode;
                        }
                        break;
                    case PdfOperator::Tf:
                        if (stack.GetSize() >= 2 && stack[1].IsName()) state.bytes_per_code = bytes_per_code(resources.back(), stack[1].GetName());
                        break;
                    case PdfOperator::Tj:
                    case PdfOperator::TJ:
                    case PdfOperator::Quote:
                    case PdfOperator::DoubleQuote:
                        if (stack.GetSize() >= 1) {
                            size_t n = string_chars(stack[0], state.bytes_per_code);
                            if (state.render_mode == 3 || state.render_mode == 7) ans.invisible_chars += n;
                            else ans.visible_chars += n;
                        }
                        break;
                    default: break;
                }
                break;
            case PdfContentType::ImageDictionary: ans.image_area += area(state.ctm); break;
            case PdfContentType::DoXObject:
                if (content->XObject && content->XObject->GetType() == PdfXObjectType::Image) ans.image_area += area(state.ctm);
                break;
            case PdfContentType::BeginFormXObject: {
                // A form is drawn as if surrounded by q and Q, with its matrix
                // concatenated to the current one, and has its own resources
                GraphicsState form_state = state;
                const PdfXObjectForm *form = content->XObject ? dynamic_cast<const PdfXObjectForm *>(content->XObject.get()) : nullptr;
                const PdfDictionary *form_resources = resources.back();
                if (form) {
                    double m[6];
                    form->GetMatrix().ToArray(m);
                    form_state.ctm = concat({m[0], m[1], m[2], m[3], m[4], m[5]}, state.ctm);
                    if (form->GetResources()) form_resources = &form->GetResources()->GetDictionary();
                }
                states.push_back(form_state);
                resources.push_back(form_resources);
                break;
            }
            case PdfContentType::EndFormXObject:
                if (states.size() > 1) states.pop_back();
                if (resources.size() > 1) resources.pop_back();
                break;
            default: break;
        }
    }
    return ans;
}

static PyObject *
page_content_stats(PDFDoc *self, PyObject *args) {
    const PdfPageCollection &pages = self->doc->GetPages();
    unsigned count = pages.GetCount();
    pyunique_ptr ans(PyList_New(count));
    if (!ans) return NULL;
    for (unsigned i = 0; i < count; i++) {
        PyObject *item;
        try {
            const PdfPage &page = pages.GetPageAt(i);
            PageStats stats = page_stats(page);
            Rect rect = page.GetRect();
            double page_area = rect.Width * rect.Height;
            item = Py_BuildValue("nnd", (Py_ssize_t)stats.visible_chars, (Py_ssize_t)stats.invisible_chars, page_area > 0 ? stats.image_area / page_area : 0.0);
        } catch (const PdfError &) {
            // The page cannot be read, which the caller treats as not known
            item = Py_NewRef(Py_None);
        }
        if (!item) return NULL;
        PyList_SET_ITEM(ans.get(), i, item);
    }
    return ans.release();
}

} // namespace

PYWRAP(page_content_stats)
