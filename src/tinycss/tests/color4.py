#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

from tinycss.color3 import COLOR_KEYWORDS
from tinycss.color3 import parse_color_string as parse_color3_string
from tinycss.color4 import parse_color_string
from tinycss.tests import BaseTest


class TestColor4(BaseTest):

    def test_color4_parsing(self):
        # Expected values are the 8-bit sRGB values Chromium renders for these colors
        for css_source, expected in [
            ('rebeccapurple', (102, 51, 153, 255)),
            ('RebeccaPurple', (102, 51, 153, 255)),
            ('#f008', (255, 0, 0, 136)),
            ('#ff000080', (255, 0, 0, 128)),
            ('#AbCdEf12', (171, 205, 239, 18)),  # exact, Chromium premultiplies the low alpha
            ('rgb(255 0 0 / 50%)', (255, 0, 0, 128)),
            ('rgb(100% 0 0)', (255, 0, 0, 255)),
            ('rgb(none 128 none)', (0, 128, 0, 255)),
            ('rgb(255, 0, 0, 50%)', (255, 0, 0, 128)),
            ('rgb(1e2 0 0)', (100, 0, 0, 255)),
            ('rgb(2.5e1, 1, 1)', (25, 1, 1, 255)),
            ('rgb(255/**/0/**/0)', (255, 0, 0, 255)),
            ('rgb(-10 300 0)', (0, 255, 0, 255)),
            ('hsl(0.5turn 50% 50%)', (64, 191, 191, 255)),
            ('hsl(3.14159rad 100% 50%)', (0, 255, 255, 255)),
            ('hsl(200grad 50% 50%)', (64, 191, 191, 255)),
            ('hsl(120 50 50)', (64, 191, 64, 255)),
            ('hsl(none 50% 50%)', (191, 64, 64, 255)),
            ('hsla(120 50% 50%)', (64, 191, 64, 255)),
            ('hsl(120 -50% 50%)', (128, 128, 128, 255)),
            ('hsl(120 150% 50%)', (0, 255, 0, 255)),
            ('hwb(120 20% 30%)', (51, 179, 51, 255)),
            ('hwb(120deg 60% 60%)', (128, 128, 128, 255)),
            ('hwb(90 20 30)', (115, 179, 51, 255)),
            ('lab(50% 40 59.5)', (191, 87, 0, 255)),
            ('lab(54.29 80.82 69.91)', (255, 0, 0, 255)),
            ('lab(100 0 0)', (255, 255, 255, 255)),
            ('lab(50 40% -20%)', (183, 80, 163, 255)),
            ('lch(54.29 106.84 40.85)', (255, 0, 0, 255)),
            ('lch(50% 50% 120deg)', (70, 134, 0, 255)),
            ('lch(70 45 none)', (245, 137, 173, 255)),
            ('lch(70 -10 30)', (171, 171, 171, 255)),
            ('oklab(0.628 0.2249 0.1258)', (255, 0, 0, 255)),
            ('oklab(62.8% 56% 31%)', (254, 6, 8, 255)),
            ('oklab(1 0 0)', (255, 255, 255, 255)),
            ('oklch(0.628 0.2577 29.23)', (255, 0, 0, 255)),
            ('oklch(70% 0.1 200)', (64, 177, 183, 255)),
            ('oklch(0.7 40% 0.25turn)', (197, 152, 0, 255)),
            ('color(srgb 100% 50% 0%)', (255, 128, 0, 255)),
            ('color(srgb-linear 0.5 0.2 0.1)', (188, 124, 89, 255)),
            ('color(display-p3 0.9175 0.2003 0.1386)', (255, 0, 0, 255)),
            ('color(a98-rgb 0.6 0.5 0.4)', (163, 128, 101, 255)),
            ('color(prophoto-rgb 0.5 0.4 0.3)', (171, 115, 90, 255)),
            ('color(rec2020 0.5 0.4 0.3)', (154, 112, 87, 255)),
            ('color(xyz 0.3 0.3 0.3)', (162, 145, 143, 255)),
            ('color(xyz-d65 0.2 0.3 0.4)', (0, 167, 164, 255)),
            ('color(xyz-d50 0.2 0.3 0.25)', (38, 167, 148, 255)),
            ('color(srgb none 0.5 none)', (0, 128, 0, 255)),
            ('COLOR(SRGB 1 0 0)', (255, 0, 0, 255)),
            ('OKLCH(0.7 0.1 200)', (64, 177, 183, 255)),
            (' red ', (255, 0, 0, 255)),
            ('red /* unterminated', (255, 0, 0, 255)),
            ('rgb(255 0 0', (255, 0, 0, 255)),
            ('currentColor', 'currentColor'),
            ('transparent', (0, 0, 0, 0)),
        ]:
            result = parse_color_string(css_source)
            if isinstance(expected, str):
                self.ae(result, expected)
                continue
            self.assertIsNotNone(result, css_source)
            got = tuple(round(x * 255) for x in result)
            for g, e in zip(got, expected):
                self.assertLessEqual(abs(g - e), 1, f'{css_source}: {got} != {expected}')

        for css_source in (
            '', '#', '#12', '#12345', '#1234567', '#ff0000f', '#ggg', 'canvas', 'red blue', 'rgb(255 0 0) x', 'rgb()', 'rgb(255 0)',
            'rgb(255 0 0 0)', 'rgb(255 0 0, 1)', 'rgb(255 0 0 /)', 'rgb(255 0 0 / 1 / 1)', 'rgb(255, 0, 0, none)', 'rgb(255, 0%, 0)',
            'rgb(var(--x))', 'rgb(calc(1) 0 0)', 'rgb(from red r g b)', 'rgb(1px 0 0)', 'hsl(120, 50, 50)', 'hsl(120% 50% 50%)',
            'hsl(120px 50% 50%)', 'hwb(120, 20%, 30%)', 'lab(50, 40, 59)', 'lab(50 40)', 'color(foo 1 0 0)', 'color(srgb 1 0)',
            'color(srgb, 1, 0, 0)', 'color(1 0 0)', 'cmyk(0 0 0 0)', 'r\\65 d', 'r\u00e9d',
        ):
            self.assertIsNone(parse_color_string(css_source), css_source)
        self.assertRaises(TypeError, parse_color_string, b'red')

    def test_color4_is_superset_of_color3(self):
        for css_source in list(COLOR_KEYWORDS) + [
            '#fff', '#CbA987', 'rgb(203, 169, 135)', 'rgb(0,51,255)', 'rgb(/* R */0, /* G */51, /* B */255)', 'rgb(10%, 20%, 30%)',
            'rgba(1, 2, 3, 0.5)', 'hsl(120, 50%, 50%)', 'hsla(-300, 100%, 37.5%, 0.2)', ' /**/red/**/ ',
        ]:
            c3, c4 = parse_color3_string(css_source), parse_color_string(css_source)
            if isinstance(c3, tuple) and isinstance(c4, tuple):
                for a, b in zip(c3, c4):
                    self.assertLess(abs(a - b), 1e-10, css_source)
            else:
                self.ae(c3, c4)
