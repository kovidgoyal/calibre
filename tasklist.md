# Enhanced Bookshelf View - Implementation Task List

This document breaks down the implementation tasks for the Enhanced Bookshelf View feature, organized by phase and referencing existing calibre code patterns.

## Overview

- **Target Version**: calibre 8.16.0+
- **Status**: Planning
- **Created**: 2025-11-24
- **Last Updated**: 2025-11-24

## Phase 1: Layout Integration and Core Bookshelf View (Week 1-2)

### 1.1 Layout System Integration

#### Task 1.1.1: Add bookshelf to Visibility dataclass
- **File**: `src/calibre/gui2/central.py`
- **Location**: Line ~317 (Visibility dataclass)
- **Action**: 
  - Add `bookshelf: bool = False` field to `Visibility` dataclass
  - Follow same pattern as `cover_browser` and `quick_view`
- **Reference**: See `cover_browser: bool = False` at line 321
- **Status**: ⬜ Not Started

#### Task 1.1.2: Create bookshelf_button in CentralContainer
- **File**: `src/calibre/gui2/central.py`
- **Location**: `CentralContainer.__init__` method (~line 369)
- **Action**:
  - Create `self.bookshelf_button = LayoutButton('bookshelf', 'bookshelf.png', _('Book Shelf'), self, 'Shift+Alt+S')`
  - Follow pattern of `cover_browser_button` at line 371
  - Create `bookshelf.png` icon (or use placeholder initially)
- **Reference**: `self.cover_browser_button = LayoutButton('cover_browser', 'cover_flow.png', _('Cover browser'), self, 'Shift+Alt+B')`
- **Status**: ⬜ Not Started

#### Task 1.1.3: Initialize bookshelf_button with GUI
- **File**: `src/calibre/gui2/central.py`
- **Location**: `initialize_with_gui` method (~line 411)
- **Action**:
  - Add `self.bookshelf_button.initialize_with_gui(gui)` after line 415
- **Reference**: See `self.cover_browser_button.initialize_with_gui(gui)` at line 415
- **Status**: ⬜ Not Started

#### Task 1.1.4: Add bookshelf to layout button order
- **File**: `src/calibre/gui2/init.py`
- **Location**: `LayoutMixin.place_layout_buttons` method (~line 525)
- **Action**:
  - Add `'bs'` (bookshelf) to `button_order` strings
  - Update both wide and narrow layouts
  - Add mapping in button lookup dict: `'bs': 'bookshelf'`
- **Reference**: See `'cb': 'cover_browser'` at line 538
- **Status**: ⬜ Not Started

#### Task 1.1.5: Implement mutual exclusivity logic
- **File**: `src/calibre/gui2/central.py`
- **Location**: `layout_button_toggled` method (~line 467)
- **Action**:
  - Check if bookshelf button was toggled
  - If bookshelf is being shown (`b.name == 'bookshelf'` and `b.isChecked()`):
    - Hide cover_browser: `self.set_visibility_of('cover_browser', False)`
    - Update cover_browser button state
- **Reference**: See `layout_button_toggled` method pattern
- **Status**: ⬜ Not Started

#### Task 1.1.6: Update button state methods
- **File**: `src/calibre/gui2/central.py`
- **Location**: `update_button_states_from_visibility` method (~line 549)
- **Action**:
  - Add `self.bookshelf_button.setChecked(self.is_visible.bookshelf)` in the try block
- **Reference**: See `self.cover_browser_button.setChecked(self.is_visible.cover_browser)` at line 555
- **Status**: ⬜ Not Started

#### Task 1.1.7: Add bookshelf widget container
- **File**: `src/calibre/gui2/central.py`
- **Location**: `CentralContainer.__init__` method (~line 361)
- **Action**:
  - Add `self.bookshelf = QWidget(self)` (or placeholder for development)
  - Follow pattern of `self.cover_browser = QWidget(self)` at line 364
- **Status**: ⬜ Not Started

### 1.2 BookshelfView Core Implementation

#### Task 1.2.1: Create BookshelfView class skeleton
- **File**: `src/calibre/gui2/library/bookshelf_view.py` (NEW FILE)
- **Action**:
  - Create new file
  - Import necessary Qt classes: `QAbstractScrollArea`, `QWidget`, `QPainter`, etc.
  - Create `BookshelfView` class inheriting from `QAbstractScrollArea`
  - Add basic structure: `__init__`, `paintEvent`, `resizeEvent`
  - Reference `GridView` class in `alternate_views.py` for patterns
- **Reference**: `src/calibre/gui2/library/alternate_views.py` - `GridView` class (line 777)
- **Status**: ⬜ Not Started

#### Task 1.2.2: Implement model integration
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Add `setModel(self, model)` method
  - Store model reference: `self._model = model`
  - Connect to model signals for data changes
  - Reference `GridView.setModel` pattern
- **Reference**: See how `GridView` uses model in `alternate_views.py`
- **Status**: ⬜ Not Started

#### Task 1.2.3: Implement sort interface methods
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Implement `sort_by_named_field(field, order, reset=True)`
  - Implement `reverse_sort()`
  - Implement `resort()`
  - Implement `intelligent_sort(field, ascending)`
  - Implement `multisort(sort_spec)`
  - All methods should delegate to `self._model` or handle sorting internally
- **Reference**: `src/calibre/gui2/library/views.py` - `BooksView` class methods:
  - `sort_by_named_field` (line 794)
  - `reverse_sort` (line 838)
  - `resort` (line 834)
  - `intelligent_sort` (line 782)
- **Status**: ⬜ Not Started

#### Task 1.2.4: Implement current_view integration
- **File**: `src/calibre/gui2/library/views.py` or `src/calibre/gui2/init.py`
- **Location**: Where `current_view()` is defined
- **Action**:
  - Ensure `gui.current_view()` returns bookshelf view when it's active
  - Check `AlternateViews.current_view` property
- **Reference**: Search for `def current_view` or `current_view()` usage
- **Status**: ⬜ Not Started

#### Task 1.2.5: Basic spine rendering (without covers)
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Implement `paintEvent` to draw book spines
  - Calculate spine width from page count: `max(25, min(55, pages / 8))`
  - Draw vertical rectangles for spines
  - Add title text (vertical, rotated)
  - Use default colors initially (cover colors in Phase 2)
- **Reference**: Look at `CoverDelegate.paint` in `alternate_views.py` for painting patterns
- **Status**: ⬜ Not Started

#### Task 1.2.6: Shelf background rendering
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Draw shelf background with wood gradient
  - Colors: `#4a3728` to `#3d2e20` (dark wood)
  - Add 3D depth effect with shadows/highlights
  - Draw shelf front edge
- **Status**: ⬜ Not Started

#### Task 1.2.7: Scroll functionality
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Implement `wheelEvent` for mouse wheel scrolling
  - Calculate scroll area size based on number of books
  - Update scrollbar ranges
  - Implement smooth scrolling
- **Reference**: `QAbstractScrollArea` documentation and `GridView` scroll patterns
- **Status**: ⬜ Not Started

#### Task 1.2.8: Book selection handling
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Implement `mousePressEvent` for book selection
  - Track selected books
  - Emit selection signals compatible with `AlternateViews`
  - Support multi-select (Ctrl+Click, Shift+Click)
- **Reference**: `GridView` selection handling in `alternate_views.py`
- **Status**: ⬜ Not Started

### 1.3 AlternateViews Integration

#### Task 1.3.1: Register bookshelf view with AlternateViews
- **File**: `src/calibre/gui2/library/views.py` or where `AlternateViews` is initialized
- **Location**: Where `GridView` is registered
- **Action**:
  - Create `BookshelfView` instance
  - Call `alternate_views.add_view('bookshelf', bookshelf_view)`
  - Ensure model is set
- **Reference**: Search for `alternate_views.add_view('cover_grid'` or similar
- **Status**: ⬜ Not Started

#### Task 1.3.2: Implement selection syncing
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Implement `set_current_row(row)` method
  - Implement `select_rows(rows)` method
  - Connect to `AlternateViews` sync signals
  - Ensure bidirectional sync with main view
- **Reference**: `AlternateViews.slave_selection_changed` and `main_selection_changed` methods
- **Status**: ⬜ Not Started

#### Task 1.3.3: Implement shown() method
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Add `shown()` method called when view becomes active
  - Refresh display if needed
  - Update scroll position
- **Reference**: `GridView.shown()` if it exists, or check `AlternateViews.show_view`
- **Status**: ⬜ Not Started

#### Task 1.3.4: Implement set_database method
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Implement `set_database(db, stage=0)` method
  - Update model reference when database changes
- **Reference**: Check how other views handle database changes
- **Status**: ⬜ Not Started

### 1.4 Testing Phase 1

#### Task 1.4.1: Test layout menu integration
- **Action**:
  - Verify bookshelf button appears in layout menu
  - Test show/hide functionality
  - Verify mutual exclusivity with cover browser
- **Status**: ⬜ Not Started

#### Task 1.4.2: Test basic rendering
- **Action**:
  - Verify books render as spines
  - Test scrolling
  - Verify shelf background displays
- **Status**: ⬜ Not Started

#### Task 1.4.3: Test sort integration
- **Action**:
  - Test Sort dropdown works with bookshelf view
  - Verify all sort methods function
  - Test sort persistence
- **Status**: ⬜ Not Started

#### Task 1.4.4: Test selection syncing
- **Action**:
  - Verify selection syncs with main view
  - Test multi-select
  - Verify current book tracking
- **Status**: ⬜ Not Started

---

## Phase 2: Cover Integration (Week 2-3)

### 2.1 Cover Image Processing

#### Task 2.1.1: Create cover loading utility
- **File**: `src/calibre/gui2/library/bookshelf_utils.py` (NEW FILE)
- **Action**:
  - Create utility functions for loading cover images
  - Use existing cover cache if available
  - Reference `CoverCache` or `ThumbnailCache` from `caches.py`
- **Reference**: `src/calibre/gui2/library/caches.py` - `CoverCache` class
- **Status**: ✅ Completed

#### Task 2.1.2: Implement color extraction
- **File**: `src/calibre/gui2/library/bookshelf_utils.py`
- **Action**:
  - Implement function to extract dominant color from cover image
  - Use improved algorithm with saturation preference
  - Return color as QColor or hex string
  - Handle missing covers gracefully
  - Support both PIL and QImage paths
- **Status**: ✅ Completed

#### Task 2.1.3: Implement cover thumbnail generation
- **File**: `src/calibre/gui2/library/bookshelf_utils.py`
- **Action**:
  - Create function to generate small thumbnail (20px height)
  - Resize cover image maintaining aspect ratio
  - Cache thumbnails for performance
- **Reference**: Look at thumbnail handling in `alternate_views.py`
- **Status**: ✅ Completed (Note: Thumbnails removed from spines per user feedback)

### 2.2 Spine Visual Enhancement

#### Task 2.2.1: Apply cover colors to spines
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Use extracted dominant color as spine background
  - Apply gradient: darker edges, lighter center
  - Add vertical gradient for depth
  - Fallback to default color if cover missing
  - Ensure colors load during paint
- **Status**: ✅ Completed

#### Task 2.2.2: Add cover texture overlay
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Use left edge of cover image as texture overlay
  - Apply with opacity/mix blend mode
  - Make texture subtle (30% opacity)
- **Status**: ✅ Completed

#### Task 2.2.3: Add thumbnail to spine bottom
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Draw small cover thumbnail at bottom of spine
  - Size: 20px height, maintain aspect ratio
  - Position at bottom with small margin
- **Status**: ❌ Cancelled (Removed per user feedback - thumbnails not displayed on spines)

### 2.3 Hover Interactions

#### Task 2.3.1: Implement hover detection
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Implement `mouseMoveEvent` to track hover
  - Calculate which book is under cursor
  - Store hovered book ID
- **Status**: ✅ Completed

#### Task 2.3.2: Implement hover cover reveal
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - When book is hovered, show full cover popup
  - Position popup near hovered book
  - Animate cover reveal (slide out effect)
  - Hide on mouse leave
- **Reference**: Look at tooltip/popup patterns in calibre
- **Status**: ✅ Completed

#### Task 2.3.3: Add hover animation
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Animate spine when hovered (slight lift/scale)
  - Use QPropertyAnimation for smooth transitions
  - Duration: 200-300ms
  - Cubic-bezier easing
- **Reference**: `QPropertyAnimation` usage in `alternate_views.py` (line 42)
- **Status**: ✅ Completed (Hover effect implemented with color lightening)

### 2.4 Performance Optimization

#### Task 2.4.1: Implement lazy cover loading
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Only load covers for visible books
  - Load covers during paint with timer delay
  - Update display as covers load
- **Reference**: `GridView` render thread pattern in `alternate_views.py`
- **Status**: ✅ Completed

#### Task 2.4.2: Implement cover caching
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Cache extracted colors
  - Cache generated thumbnails
  - Use existing `ThumbnailCache` if possible
- **Reference**: `ThumbnailCache` in `alternate_views.py` (line 810)
- **Status**: ✅ Completed

### 2.5 Testing Phase 2

#### Task 2.5.1: Test cover integration
- **Action**:
  - Verify spines show cover colors
  - Test thumbnail display
  - Verify texture overlay
- **Status**: ⬜ Not Started

#### Task 2.5.2: Test hover interactions
- **Action**:
  - Test hover cover reveal
  - Verify animations smooth
  - Test with missing covers
- **Status**: ⬜ Not Started

#### Task 2.5.3: Performance testing
- **Action**:
  - Test with 100+ books
  - Measure render time
  - Verify smooth scrolling
- **Status**: ⬜ Not Started

---

## Phase 3: Sorting Integration and Grouping (Week 3-4)

### 3.1 Sort Integration Verification

#### Task 3.1.1: Verify Sort dropdown integration
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Test all sort methods work correctly
  - Verify sort state persists
  - Test multi-column sorting
  - Test saved sorts
- **Reference**: `src/calibre/gui2/actions/sort.py` - `SortByAction`
- **Status**: ⬜ Not Started

#### Task 3.1.2: Fix any sort integration issues
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Debug and fix any sort-related bugs
  - Ensure sort indicators work
  - Verify reverse sort works
- **Status**: ⬜ Not Started

### 3.2 Grouping Implementation

#### Task 3.2.1: Implement grouping logic
- **File**: `src/calibre/gui2/library/bookshelf_utils.py`
- **Action**:
  - Create function to group books by:
    - Series (use `series` field)
    - Genre (use first tag from `tags`)
    - Time Period (group `pubdate` by decade)
  - Return grouped book lists with group labels
- **Status**: ⬜ Not Started

#### Task 3.2.2: Store grouping preference
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Store grouping mode in `gprefs`
  - Key: `'bookshelf_grouping_mode'` (values: 'none', 'series', 'genre', 'time_period')
  - Load preference on init
- **Reference**: See how other preferences are stored in `gprefs`
- **Status**: ⬜ Not Started

#### Task 3.2.3: Implement group rendering
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Draw visual dividers between groups
  - Add group labels (rotated text on left)
  - Add subtle background color change for groups
  - Handle "No Series" / "No Genre" groups
- **Status**: ⬜ Not Started

#### Task 3.2.4: Implement context menu for grouping
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Implement `contextMenuEvent` method
  - Add menu items:
    - "Group by: None"
    - "Group by: Series"
    - "Group by: Genre"
    - "Group by: Time Period"
  - Update grouping mode on selection
  - Refresh display
- **Reference**: Look at context menu patterns in other views
- **Status**: ⬜ Not Started

#### Task 3.2.5: Maintain sort within groups
- **File**: `src/calibre/gui2/library/bookshelf_utils.py`
- **Action**:
  - Ensure books within groups maintain sort order
  - Sort groups by group name
  - Apply current sort to books in each group
- **Status**: ⬜ Not Started

### 3.3 Testing Phase 3

#### Task 3.3.1: Test grouping functionality
- **Action**:
  - Test all grouping modes
  - Verify visual dividers display
  - Test group labels
  - Verify sort works within groups
- **Status**: ⬜ Not Started

#### Task 3.3.2: Test context menu
- **Action**:
  - Verify context menu appears on right-click
  - Test all grouping options
  - Verify preference persistence
- **Status**: ⬜ Not Started

---

## Phase 4: Polish and Optimization (Week 4-5)

### 4.1 Performance Optimization

#### Task 4.1.1: Profile performance bottlenecks
- **Action**:
  - Use profiling tools to identify slow areas
  - Measure render time with 1000+ books
  - Identify memory usage issues
- **Status**: ⬜ Not Started

#### Task 4.1.2: Optimize rendering
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Implement viewport culling (only render visible books)
  - Optimize paint operations
  - Reduce unnecessary redraws
- **Status**: ⬜ Not Started

#### Task 4.1.3: Optimize cover loading
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Improve lazy loading strategy
  - Optimize thumbnail generation
  - Improve caching strategy
- **Status**: ⬜ Not Started

### 4.2 Animation Refinements

#### Task 4.2.1: Polish hover animations
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Fine-tune animation timing
  - Ensure smooth transitions
  - Test on different systems
- **Status**: ⬜ Not Started

#### Task 4.2.2: Add scroll animations
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Implement smooth scrolling
  - Add momentum scrolling if desired
- **Status**: ⬜ Not Started

### 4.3 Error Handling

#### Task 4.3.1: Add error handling for missing covers
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Handle missing cover images gracefully
  - Show default placeholder
  - Use default colors
- **Status**: ⬜ Not Started

#### Task 4.3.2: Add error handling for missing metadata
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Handle missing page counts
  - Handle missing titles/authors
  - Show appropriate defaults
- **Status**: ⬜ Not Started

#### Task 4.3.3: Add error handling for large libraries
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Handle memory issues with 5000+ books
  - Implement pagination or virtualization if needed
  - Show loading indicators
- **Status**: ⬜ Not Started

### 4.4 Configuration Options

#### Task 4.4.1: Add tweaks for customization
- **File**: `src/calibre/customize/tweaks.py` or similar
- **Action**:
  - Add tweak for spine height (default: 150px)
  - Add tweak for min/max spine width
  - Add tweak for shelf appearance
- **Reference**: Look at existing tweaks in calibre
- **Status**: ⬜ Not Started

#### Task 4.4.2: Store user preferences
- **File**: `src/calibre/gui2/library/bookshelf_view.py`
- **Action**:
  - Store scroll position in `gprefs`
  - Store grouping preference
  - Store any view-specific settings
- **Status**: ⬜ Not Started

### 4.5 Documentation

#### Task 4.5.1: Add code comments
- **Files**: All new files
- **Action**:
  - Add docstrings to all classes and methods
  - Add inline comments for complex logic
  - Follow calibre code style
- **Status**: ⬜ Not Started

#### Task 4.5.2: Update user manual (if needed)
- **File**: `manual/gui.rst` or similar
- **Action**:
  - Document bookshelf view feature
  - Add screenshots if possible
  - Document keyboard shortcuts
- **Status**: ⬜ Not Started

### 4.6 Final Testing

#### Task 4.6.1: Comprehensive testing
- **Action**:
  - Test with various library sizes (100, 500, 1000, 5000 books)
  - Test with missing covers
  - Test with missing metadata
  - Test on different platforms (Windows, macOS, Linux)
- **Status**: ⬜ Not Started

#### Task 4.6.2: User acceptance testing
- **Action**:
  - Test with real user libraries
  - Gather feedback
  - Fix any issues found
- **Status**: ⬜ Not Started

---

## Additional Tasks

### Icon Creation

#### Task A.1: Create bookshelf icon
- **File**: `resources/images/bookshelf.png` (or appropriate location)
- **Action**:
  - Create icon for bookshelf button
  - Follow calibre icon style
  - Size: 16x16 or 24x24 pixels
- **Status**: ⬜ Not Started

### Changelog Entry

#### Task A.2: Add changelog entry
- **File**: `Changelog.txt`
- **Action**:
  - Add entry for version 8.16.0
  - Follow existing changelog format
  - Include ticket ID if available
- **Reference**: See PRD changelog section for format
- **Status**: ⬜ Not Started

---

## Notes

- All tasks should follow calibre's existing code patterns and style
- Use existing utilities and classes where possible
- Test incrementally after each major task
- Reference existing code in `alternate_views.py`, `views.py`, `central.py` for patterns
- No custom toolbars - use existing UI controls only
- All settings stored in `gprefs` following calibre conventions

---

## Task Status Legend

- ⬜ Not Started
- 🟡 In Progress
- ✅ Completed
- ❌ Blocked
- 🔄 On Hold

