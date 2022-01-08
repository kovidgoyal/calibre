#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys
from qt.core import (
    QWidget, QTimer, QStackedLayout, QLabel, QScrollArea, QVBoxLayout,
    QPainter, Qt, QPalette, QRect, QSize, QSizePolicy, pyqtSignal,
    QColor, QMenu, QApplication, QIcon, QUrl)

from calibre.constants import FAKE_HOST, FAKE_PROTOCOL
from calibre.gui2.tweak_book import editors, actions, tprefs
from calibre.gui2.tweak_book.editor.themes import get_theme, theme_color
from calibre.gui2.tweak_book.editor.text import default_font_family
from css_selectors import parse, SelectorError


lowest_specificity = (-sys.maxsize, 0, 0, 0, 0, 0)


class Heading(QWidget):  # {{{

    toggled = pyqtSignal(object)
    context_menu_requested = pyqtSignal(object, object)

    def __init__(self, text, expanded=True, parent=None):
        QWidget.__init__(self, parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.text = text
        self.expanded = expanded
        self.hovering = False
        self.do_layout()

    @property
    def lines_for_copy(self):
        return [self.text]

    def do_layout(self):
        try:
            f = self.parent().font()
        except AttributeError:
            return
        f.setBold(True)
        self.setFont(f)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            ev.accept()
            self.expanded ^= True
            self.toggled.emit(self)
            self.update()
        else:
            return QWidget.mousePressEvent(self, ev)

    @property
    def rendered_text(self):
        return ('▾' if self.expanded else '▸') + '\xa0' + self.text

    def sizeHint(self):
        fm = self.fontMetrics()
        sz = fm.boundingRect(self.rendered_text).size()
        return sz

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setClipRect(ev.rect())
        bg = self.palette().color(QPalette.ColorRole.AlternateBase)
        if self.hovering:
            bg = bg.lighter(115)
        p.fillRect(self.rect(), bg)
        try:
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter|Qt.TextFlag.TextSingleLine, self.rendered_text)
        finally:
            p.end()

    def enterEvent(self, ev):
        self.hovering = True
        self.update()
        return QWidget.enterEvent(self, ev)

    def leaveEvent(self, ev):
        self.hovering = False
        self.update()
        return QWidget.leaveEvent(self, ev)

    def contextMenuEvent(self, ev):
        self.context_menu_requested.emit(self, ev)
# }}}


class Cell:  # {{{

    __slots__ = ('rect', 'text', 'right_align', 'color_role', 'override_color', 'swatch', 'is_overriden')

    SIDE_MARGIN = 5
    FLAGS = Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine | Qt.TextFlag.TextIncludeTrailingSpaces

    def __init__(self, text, rect, right_align=False, color_role=QPalette.ColorRole.WindowText, swatch=None, is_overriden=False):
        self.rect, self.text = rect, text
        self.right_align = right_align
        self.is_overriden = is_overriden
        self.color_role = color_role
        self.override_color = None
        self.swatch = swatch
        if swatch is not None:
            self.swatch = QColor(swatch[0], swatch[1], swatch[2], int(255 * swatch[3]))

    def draw(self, painter, width, palette):
        flags = self.FLAGS | (Qt.AlignmentFlag.AlignRight if self.right_align else Qt.AlignmentFlag.AlignLeft)
        rect = QRect(self.rect)
        if self.right_align:
            rect.setRight(width - self.SIDE_MARGIN)
        painter.setPen(palette.color(self.color_role) if self.override_color is None else self.override_color)
        br = painter.drawText(rect, flags, self.text)
        if self.swatch is not None:
            r = QRect(br.right() + self.SIDE_MARGIN // 2, br.top() + 2, br.height() - 4, br.height() - 4)
            painter.fillRect(r, self.swatch)
            br.setRight(r.right())
        if self.is_overriden:
            painter.setPen(palette.color(QPalette.ColorRole.WindowText))
            painter.drawLine(br.left(), br.top() + br.height() // 2, br.right(), br.top() + br.height() // 2)
# }}}


class Declaration(QWidget):

    hyperlink_activated = pyqtSignal(object)
    context_menu_requested = pyqtSignal(object, object)

    def __init__(self, html_name, data, is_first=False, parent=None):
        QWidget.__init__(self, parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.data = data
        self.is_first = is_first
        self.html_name = html_name
        self.lines_for_copy = []
        self.do_layout()
        self.setMouseTracking(True)

    def do_layout(self):
        fm = self.fontMetrics()
        bounding_rect = lambda text: fm.boundingRect(0, 0, 10000, 10000, Cell.FLAGS, text)
        line_spacing = 2
        side_margin = Cell.SIDE_MARGIN
        self.rows = []
        ypos = line_spacing + (1 if self.is_first else 0)
        if 'href' in self.data:
            name = self.data['href']
            if isinstance(name, list):
                name = self.html_name
            br1 = bounding_rect(name)
            sel = self.data['selector'] or ''
            if self.data['type'] == 'inline':
                sel = 'style=""'
            br2 = bounding_rect(sel)
            self.hyperlink_rect = QRect(side_margin, ypos, br1.width(), br1.height())
            self.rows.append([
                Cell(name, self.hyperlink_rect, color_role=QPalette.ColorRole.Link),
                Cell(sel, QRect(br1.right() + side_margin, ypos, br2.width(), br2.height()), right_align=True)
            ])
            ypos += max(br1.height(), br2.height()) + 2 * line_spacing
            self.lines_for_copy.append(name + ' ' + sel)

        for prop in self.data['properties']:
            text = prop.name + ':\xa0'
            br1 = bounding_rect(text)
            vtext = prop.value + '\xa0' + ('!' if prop.important else '') + prop.important
            br2 = bounding_rect(vtext)
            self.rows.append([
                Cell(text, QRect(side_margin, ypos, br1.width(), br1.height()), color_role=QPalette.ColorRole.LinkVisited, is_overriden=prop.is_overriden),
                Cell(vtext, QRect(br1.right() + side_margin, ypos, br2.width(), br2.height()), swatch=prop.color, is_overriden=prop.is_overriden)
            ])
            self.lines_for_copy.append(text + vtext)
            if prop.is_overriden:
                self.lines_for_copy[-1] += ' [overridden]'
            ypos += max(br1.height(), br2.height()) + line_spacing
        self.lines_for_copy.append('--------------------------\n')

        self.height_hint = ypos + line_spacing
        self.width_hint = max(row[-1].rect.right() + side_margin for row in self.rows) if self.rows else 0

    def sizeHint(self):
        return QSize(self.width_hint, self.height_hint)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setClipRect(ev.rect())
        palette = self.palette()
        p.setPen(palette.color(QPalette.ColorRole.WindowText))
        if not self.is_first:
            p.drawLine(0, 0, self.width(), 0)
        try:
            for row in self.rows:
                for cell in row:
                    p.save()
                    try:
                        cell.draw(p, self.width(), palette)
                    finally:
                        p.restore()

        finally:
            p.end()

    def mouseMoveEvent(self, ev):
        if hasattr(self, 'hyperlink_rect'):
            pos = ev.pos()
            hovering = self.hyperlink_rect.contains(pos)
            self.update_hover(hovering)
            cursor = Qt.CursorShape.ArrowCursor
            for r, row in enumerate(self.rows):
                for cell in row:
                    if cell.rect.contains(pos):
                        cursor = Qt.CursorShape.PointingHandCursor if cell.rect is self.hyperlink_rect else Qt.CursorShape.IBeamCursor
                    if r == 0:
                        break
                if cursor != Qt.CursorShape.ArrowCursor:
                    break
            self.setCursor(cursor)
        return QWidget.mouseMoveEvent(self, ev)

    def mousePressEvent(self, ev):
        if hasattr(self, 'hyperlink_rect') and ev.button() == Qt.MouseButton.LeftButton:
            pos = ev.pos()
            if self.hyperlink_rect.contains(pos):
                self.emit_hyperlink_activated()
        return QWidget.mousePressEvent(self, ev)

    def emit_hyperlink_activated(self):
        dt = self.data['type']
        data = {'type':dt, 'name':self.html_name, 'syntax':'html'}
        if dt == 'inline':  # style attribute
            data['sourceline_address'] = self.data['href']
        elif dt == 'elem':  # <style> tag
            data['sourceline_address'] = self.data['href']
            data['rule_address'] = self.data['rule_address']
        else:  # stylesheet
            data['name'] = self.data['href']
            data['rule_address'] = self.data['rule_address']
            data['syntax'] = 'css'
        self.hyperlink_activated.emit(data)

    def leaveEvent(self, ev):
        self.update_hover(False)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        return QWidget.leaveEvent(self, ev)

    def update_hover(self, hovering):
        cell = self.rows[0][0]
        if (hovering and cell.override_color is None) or (
                not hovering and cell.override_color is not None):
            cell.override_color = QColor(Qt.GlobalColor.red) if hovering else None
            self.update()

    def contextMenuEvent(self, ev):
        self.context_menu_requested.emit(self, ev)


class Box(QWidget):

    hyperlink_activated = pyqtSignal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        l.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(l)
        self.widgets = []

    def show_data(self, data):
        for w in self.widgets:
            self.layout().removeWidget(w)
            for x in ('toggled', 'hyperlink_activated', 'context_menu_requested'):
                if hasattr(w, x):
                    try:
                        getattr(w, x).disconnect()
                    except TypeError:
                        pass
            w.deleteLater()
        self.widgets = []
        for node in data['nodes']:
            node_name = node['name'] + ' @%s' % node['sourceline']
            if node['ancestor_specificity'] != 0:
                title = _('Inherited from %s') % node_name
            else:
                title = _('Matched CSS rules for %s') % node_name
            h = Heading(title, parent=self)
            h.toggled.connect(self.heading_toggled)
            self.widgets.append(h), self.layout().addWidget(h)
            for i, declaration in enumerate(node['css']):
                d = Declaration(data['html_name'], declaration, is_first=i == 0, parent=self)
                d.hyperlink_activated.connect(self.hyperlink_activated)
                self.widgets.append(d), self.layout().addWidget(d)

        h = Heading(_('Computed final style'), parent=self)
        h.toggled.connect(self.heading_toggled)
        self.widgets.append(h), self.layout().addWidget(h)
        ccss = data['computed_css']
        declaration = {'properties':[Property([k, ccss[k][0], '', ccss[k][1]]) for k in sorted(ccss)]}
        d = Declaration(None, declaration, is_first=True, parent=self)
        self.widgets.append(d), self.layout().addWidget(d)
        for w in self.widgets:
            w.context_menu_requested.connect(self.context_menu_requested)

    def heading_toggled(self, heading):
        for i, w in enumerate(self.widgets):
            if w is heading:
                for b in self.widgets[i + 1:]:
                    if isinstance(b, Heading):
                        break
                    b.setVisible(heading.expanded)
                break

    def relayout(self):
        for w in self.widgets:
            w.do_layout()
            w.updateGeometry()

    @property
    def lines_for_copy(self):
        ans = []
        for w in self.widgets:
            ans += w.lines_for_copy
        return ans

    def context_menu_requested(self, widget, ev):
        if isinstance(widget, Heading):
            start = widget
        else:
            found = False
            for w in reversed(self.widgets):
                if w is widget:
                    found = True
                elif found and isinstance(w, Heading):
                    start = w
                    break
            else:
                return
        found = False
        lines = []
        for w in self.widgets:
            if found and isinstance(w, Heading):
                break
            if w is start:
                found = True
            if found:
                lines += w.lines_for_copy
        if not lines:
            return
        block = '\n'.join(lines).replace('\xa0', ' ')
        heading = lines[0]
        m = QMenu(self)
        m.addAction(QIcon.ic('edit-copy.png'), _('Copy') + ' ' + heading.replace('\xa0', ' '), lambda : QApplication.instance().clipboard().setText(block))
        all_lines = []
        for w in self.widgets:
            all_lines += w.lines_for_copy
        all_text = '\n'.join(all_lines).replace('\xa0', ' ')
        m.addAction(QIcon.ic('edit-copy.png'), _('Copy everything'), lambda : QApplication.instance().clipboard().setText(all_text))
        m.exec(ev.globalPos())


class Property:

    __slots__ = 'name', 'value', 'important', 'color', 'specificity', 'is_overriden'

    def __init__(self, prop, specificity=()):
        self.name, self.value, self.important, self.color = prop
        self.specificity = tuple(specificity)
        self.is_overriden = False

    def __repr__(self):
        return '<Property name={} value={} important={} color={} specificity={} is_overriden={}>'.format(
            self.name, self.value, self.important, self.color, self.specificity, self.is_overriden)


class LiveCSS(QWidget):

    goto_declaration = pyqtSignal(object)

    def __init__(self, preview, parent=None):
        QWidget.__init__(self, parent)
        self.preview = preview
        preview.live_css_data.connect(self.got_live_css_data)
        self.preview_is_refreshing = False
        self.refresh_needed = False
        preview.refresh_starting.connect(self.preview_refresh_starting)
        preview.refreshed.connect(self.preview_refreshed)
        self.apply_theme()
        self.setAutoFillBackground(True)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_data)
        self.update_timer.setSingleShot(True)
        self.update_timer.setInterval(500)
        self.now_showing = (None, None, None)

        self.stack = s = QStackedLayout(self)
        self.setLayout(s)

        self.clear_label = la = QLabel('<h3>' + _(
            'No style information found') + '</h3><p>' + _(
                'Move the cursor inside a HTML tag to see what styles'
                ' apply to that tag.'))
        la.setWordWrap(True)
        la.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        s.addWidget(la)

        self.box = box = Box(self)
        box.hyperlink_activated.connect(self.goto_declaration, type=Qt.ConnectionType.QueuedConnection)
        self.scroll = sc = QScrollArea(self)
        sc.setWidget(box)
        sc.setWidgetResizable(True)
        s.addWidget(sc)

    def preview_refresh_starting(self):
        self.preview_is_refreshing = True

    def preview_refreshed(self):
        self.preview_is_refreshing = False
        self.refresh_needed = True
        self.start_update_timer()

    def apply_theme(self):
        f = self.font()
        f.setFamily(tprefs['editor_font_family'] or default_font_family())
        f.setPointSizeF(tprefs['editor_font_size'])
        self.setFont(f)
        theme = get_theme(tprefs['editor_theme'])
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, theme_color(theme, 'Normal', 'bg'))
        pal.setColor(QPalette.ColorRole.WindowText, theme_color(theme, 'Normal', 'fg'))
        pal.setColor(QPalette.ColorRole.AlternateBase, theme_color(theme, 'HighlightRegion', 'bg'))
        pal.setColor(QPalette.ColorRole.Link, theme_color(theme, 'Link', 'fg'))
        pal.setColor(QPalette.ColorRole.LinkVisited, theme_color(theme, 'Keyword', 'fg'))
        self.setPalette(pal)
        if hasattr(self, 'box'):
            self.box.relayout()
        self.update()

    def clear(self):
        self.stack.setCurrentIndex(0)

    def show_data(self, editor_name, sourceline, tags):
        if self.preview_is_refreshing:
            return
        if sourceline is None:
            self.clear()
        else:
            self.preview.request_live_css_data(editor_name, sourceline, tags)

    def got_live_css_data(self, result):
        maximum_specificities = {}
        for node in result['nodes']:
            for rule in node['css']:
                self.process_rule(rule, node['ancestor_specificity'], maximum_specificities)
        for node in result['nodes']:
            for rule in node['css']:
                for prop in rule['properties']:
                    if prop.specificity < maximum_specificities[prop.name]:
                        prop.is_overriden = True
        self.display_received_live_css_data(result)

    def display_received_live_css_data(self, data):
        editor_name = data['editor_name']
        sourceline = data['sourceline']
        tags = data['tags']
        if data is None or len(data['computed_css']) < 1:
            if editor_name == self.current_name and (editor_name, sourceline, tags) == self.now_showing:
                # Try again in a little while in case there was a transient
                # error in the web view
                self.start_update_timer()
                return
            self.clear()
            return
        self.now_showing = (editor_name, sourceline, tags)
        data['html_name'] = editor_name
        self.box.show_data(data)
        self.refresh_needed = False
        self.stack.setCurrentIndex(1)

    def process_rule(self, rule, ancestor_specificity, maximum_specificities):
        selector = rule['selector']
        sheet_index = rule['sheet_index']
        rule_address = rule['rule_address'] or ()
        if selector is not None:
            try:
                specificity = [0] + list(parse(selector)[0].specificity())
            except (AttributeError, TypeError, SelectorError):
                specificity = [0, 0, 0, 0]
        else:  # style attribute
            specificity = [1, 0, 0, 0]
        specificity.extend((sheet_index, tuple(rule_address)))
        properties = []
        for prop in rule['properties']:
            important = 1 if prop[-1] == 'important' else 0
            p = Property(prop, [ancestor_specificity] + [important] + specificity)
            properties.append(p)
            if p.specificity > maximum_specificities.get(p.name, lowest_specificity):
                maximum_specificities[p.name] = p.specificity
        rule['properties'] = properties

        href = rule['href']
        if hasattr(href, 'startswith') and href.startswith(f'{FAKE_PROTOCOL}://{FAKE_HOST}'):
            qurl = QUrl(href)
            name = qurl.path()[1:]
            if name:
                rule['href'] = name

    @property
    def current_name(self):
        return self.preview.current_name

    @property
    def is_visible(self):
        return self.isVisible()

    def showEvent(self, ev):
        self.update_timer.start()
        actions['auto-reload-preview'].setEnabled(True)
        return QWidget.showEvent(self, ev)

    def sync_to_editor(self):
        self.update_data()

    def update_data(self):
        if not self.is_visible or self.preview_is_refreshing:
            return
        editor_name = self.current_name
        ed = editors.get(editor_name, None)
        if self.update_timer.isActive() or (ed is None and editor_name is not None):
            return QTimer.singleShot(100, self.update_data)
        if ed is not None:
            sourceline, tags = ed.current_tag(for_position_sync=False)
            if self.refresh_needed or self.now_showing != (editor_name, sourceline, tags):
                self.show_data(editor_name, sourceline, tags)

    def start_update_timer(self):
        if self.is_visible:
            self.update_timer.start()

    def stop_update_timer(self):
        self.update_timer.stop()

    def navigate_to_declaration(self, data, editor):
        if data['type'] == 'inline':
            sourceline, tags = data['sourceline_address']
            editor.goto_sourceline(sourceline, tags, attribute='style')
        elif data['type'] == 'sheet':
            editor.goto_css_rule(data['rule_address'])
        elif data['type'] == 'elem':
            editor.goto_css_rule(data['rule_address'], sourceline_address=data['sourceline_address'])
