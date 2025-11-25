# Product Requirements Document: Enhanced Bookshelf View

## Overview

This document outlines the requirements for implementing an enhanced bookshelf view in calibre that displays books as spines on shelves. The bookshelf view will be accessible via the Layout menu (bottom right) and will be mutually exclusive with the Cover Browser (Cover Flow) view. The bookshelf view will provide an immersive, library-like browsing experience with advanced sorting and grouping capabilities. All controls use existing calibre UI elements - no custom toolbars or new UI components are required.

## Version Information

- **Feature Version**: 1.0.0
- **Target calibre Version**: 8.16.0+
- **Status**: Phase 2 Complete (Cover Integration)
- **Created**: 2025-11-24
- **Last Updated**: 2025-12-XX

## Background

Currently, calibre offers several view modes for browsing the library:
- **List View** (`BooksView`): Traditional table view with columns
- **Cover Grid** (`GridView`): Grid of book covers
- **Cover Flow** (`CoverFlowMixin`): 3D carousel of book covers

Users have requested an additional view that mimics a physical bookshelf, showing book spines arranged on shelves. This provides:
- A more immersive browsing experience
- Better visual organization when grouping by series/genre
- Quick identification through spine colors derived from covers
- Efficient use of screen space for large libraries

## Goals

1. Add a new bookshelf view mode that displays books as spines on shelves
2. Integrate bookshelf view into the Layout menu system
3. Implement mutual exclusivity: when Bookshelf is shown, Cover Browser is automatically hidden
4. Integrate with existing Sort dropdown menu for all sorting options
5. Support grouping by Series, Genre, and Time Period (via context menu)
6. Use only existing calibre UI controls - no custom toolbars or new UI components
7. Maintain consistency with existing calibre UI styling and architecture
8. Ensure performance with large libraries (1000+ books)

## Non-Goals

- Replacing existing view modes (this is additive)
- Changing the core library data model
- Modifying book metadata structure
- Creating a separate application or plugin (this is a builtin feature)

## Architecture

### Component Structure

```
src/calibre/gui2/library/
├── bookshelf_view.py          # Main BookshelfView class (QAbstractScrollArea)
├── bookshelf_delegate.py      # Custom painting for book spines
└── bookshelf_utils.py         # Helper functions (color extraction, grouping logic)
```

**Note**: No separate sorting toolbar needed - bookshelf view integrates with existing Sort dropdown menu (`SortByAction`).

### Integration Points

1. **AlternateViews System** (`src/calibre/gui2/library/alternate_views.py`)
   - Add bookshelf view to `AlternateViews` class
   - Register with key `'bookshelf'`
   - Ensure selection syncing with main view

2. **Layout System** (`src/calibre/gui2/central.py`)
   - Add `bookshelf` field to `Visibility` dataclass
   - Create `bookshelf_button` in `CentralContainer.__init__` similar to `cover_browser_button`
   - Add bookshelf button to layout button order
   - Implement mutual exclusivity: when bookshelf shows, cover_browser hides
   - Button appears in layout menu (accessed via "Layout" button in bottom right)
   - Keyboard shortcut: `Shift+Alt+S` (to be determined)

3. **Model Integration** (`src/calibre/gui2/library/models.py`)
   - Use existing `BooksModel` for data access
   - Leverage existing sorting methods (`sort_by_named_field`)
   - Access book metadata via `db.get_metadata()`

4. **Sort Integration** (`src/calibre/gui2/actions/sort.py`)
   - Bookshelf view must implement same interface as `BooksView` for sorting
   - Methods required: `sort_by_named_field()`, `reverse_sort()`, `resort()`, `intelligent_sort()`, `multisort()`
   - Bookshelf view must be returned by `gui.current_view()` when active
   - Existing `SortByAction` will automatically work with bookshelf view

## Functional Requirements

### FR1: Bookshelf View Display

**Priority**: P0 (Must Have)

The bookshelf view must display books as spines arranged horizontally on shelves.

**Requirements**:
- Books are rendered as vertical spines (rectangles)
- Spines are arranged left-to-right on horizontal shelves
- Multiple shelves are displayed vertically (scrollable)
- Each shelf has a visual appearance of a wooden bookshelf
- Books are positioned to sit on the shelf (not floating)

**Spine Characteristics**:
- **Width**: Calculated from page count (min: 25px, max: 55px)
  - Formula: `width = max(25, min(55, pages / 8))`
- **Height**: Fixed at 150px (configurable via tweaks)
- **Background**: Dominant color extracted from book cover with improved algorithm
- **Texture**: Subtle overlay using left edge of cover image (30% opacity)
- **Title**: Displayed vertically on spine (rotated text)
- **Note**: Cover thumbnails on spines were removed per user feedback

**Visual Styling**:
- Shelf background: Dark wood gradient (`#4a3728` to `#3d2e20`)
- Shelf depth: 3D appearance with shadow and highlight
- Background: Dark theme (`#0d0d18`)
- Text color: Light gray (`#eee`)

### FR2: Cover Integration

**Priority**: P0 (Must Have)

Book spines must visually reflect the book's cover.

**Requirements**:
- Extract dominant color from cover image for spine background using improved algorithm
- Algorithm prefers more saturated/vibrant colors over gray/brown tones
- Apply subtle texture overlay using left edge of cover (30% opacity)
- Fallback to default brown (`#8B4513`) if cover unavailable
- **Note**: Cover thumbnails on spines were removed per user feedback

**Color Extraction**:
- Use PIL/Pillow if available for accurate color extraction
- Resize cover to 50×50px for performance
- Find most common color in image
- Apply as gradient background on spine

### FR3: Hover Interactions

**Priority**: P0 (Must Have)

Hovering over a book spine must reveal the full cover.

**Requirements**:
- On mouse hover over spine:
  - Show full book cover as popup above spine
  - Cover size: 100px width (proportional height)
  - Smooth animation (translate + scale)
  - Spine remains visible behind cover
  - Cover has shadow for depth
- On mouse leave:
  - Smoothly hide cover popup
  - Return spine to normal state
- Animation duration: 200-300ms
- Use cubic-bezier easing for smooth motion

### FR4: Layout Menu Integration

**Priority**: P0 (Must Have)

Bookshelf view must be accessible via the layout menu.

**Requirements**:
- Add "Book Shelf" button to layout menu (accessed via "Layout" button in bottom right)
- Button icon: `bookshelf.png` (to be created)
- Button label: "Book Shelf"
- Button shows "Show" or "Hide" state based on visibility
- Button state persists across sessions (via `gprefs` in `Visibility` dataclass)
- When bookshelf is set to "Show":
  - Cover Browser automatically goes to "Hide" (mutual exclusivity)
  - Bookshelf view becomes visible
- When bookshelf is set to "Hide":
  - Bookshelf view is hidden
  - Cover Browser state is not automatically changed
- Keyboard shortcut: `Shift+Alt+S` (to be confirmed, may conflict with existing shortcuts)
- Button appears in layout menu alongside other layout controls:
  - Search bar
  - Tag browser
  - Cover browser
  - Cover grid
  - Quickview
  - Book details

### FR5: Mutual Exclusivity with Cover Browser

**Priority**: P0 (Must Have)

Bookshelf view and Cover Browser must be mutually exclusive.

**Requirements**:
- When Bookshelf is set to "Show" (via layout menu):
  - Cover Browser automatically goes to "Hide"
  - Cover Browser button state updates to reflect hidden state
  - No user confirmation required
- When Bookshelf is set to "Hide":
  - Cover Browser state is not automatically changed
  - User can manually show Cover Browser if desired
- Implementation in `layout_button_toggled()` method:
  - Check if bookshelf button was toggled
  - If bookshelf is being shown, automatically hide cover_browser
  - Update both button states accordingly

**Note**: Direct toggle between Cover Browser and Bookshelf (single action to switch) is deferred to a future release (see TODO section).

### FR6: Sorting Integration

**Priority**: P0 (Must Have)

Bookshelf view must integrate with the existing Sort dropdown menu.

**Requirements**:
- Use the existing "Sort" button/dropdown menu in the search bar (top toolbar)
- Sort button is visible when bookshelf view is active (same as other library views)
- Sort menu automatically works with bookshelf view when it's the current view
- All standard sort options available:
  - Title, Authors, Date, Published, Series, Tags, Rating, etc.
  - Custom columns (if configured)
  - Multi-column sorting
  - Saved sort configurations
- Sort menu shows current sort column with checkmark icon
- Standard sort actions work:
  - "Re-apply current sort" (F5)
  - "Reverse current sort" (Shift+F5)
  - "Sort on multiple columns"
  - "Select sortable columns"

**Implementation**:
- Bookshelf view must implement the same interface methods as `BooksView`:
  - `sort_by_named_field(field, order, reset=True)` - Sort by a specific field
  - `reverse_sort()` - Reverse the current sort order
  - `resort()` - Re-apply the current sort
  - `intelligent_sort(field, ascending)` - Smart sort (toggles if already sorted)
  - `multisort(sort_spec)` - Sort on multiple columns
- Bookshelf view must be returned by `gui.current_view()` when active
- Sort action (`SortByAction`) automatically detects bookshelf view and works with it
- No separate sorting toolbar needed - uses existing Sort dropdown

### FR7: Grouping

**Priority**: P1 (Should Have)

Bookshelf view must support grouping books by category.

**Group Options**:
1. **None** - No grouping (default)
2. **Series** - Group books by series name
3. **Genre** - Group books by first tag
4. **Time Period** - Group by publication decade

**Requirements**:
- Group controls accessible via context menu (right-click on bookshelf view)
- Grouping state stored in `gprefs` (persists across sessions)
- When grouped:
  - Books are visually separated by group dividers
  - Group labels displayed vertically on left side of each group
  - Books within groups maintain sort order
  - Groups are sorted by group name
- Visual dividers:
  - Vertical line between groups
  - Group label (rotated text)
  - Subtle background color change
- "No Series" / "No Genre" groups for ungrouped books

### FR8: Selection and Navigation

**Priority**: P0 (Must Have)

Bookshelf view must support book selection and navigation.

**Requirements**:
- Click on spine to select book
- Selected spine highlighted (border or glow effect)
- Selection synced with main library view
- Double-click to open book in viewer
- Keyboard navigation:
  - Arrow keys to navigate between books
  - Enter to open selected book
  - Space to toggle selection
- Context menu on right-click (same as other views)

### FR9: Performance

**Priority**: P0 (Must Have)

Bookshelf view must perform well with large libraries.

**Requirements**:
- Smooth scrolling with 1000+ books
- Lazy loading of cover images (only visible spines)
- Efficient color extraction (cache results)
- Thumbnail generation on-demand
- Viewport-based rendering (only render visible items)
- Memory efficient (don't load all covers at once)

**Performance Targets**:
- Initial render: < 500ms for 1000 books
- Scroll FPS: 60fps on modern hardware
- Memory usage: < 200MB for 1000 books
- Cover loading: Progressive (visible items first)

## Technical Requirements

### TR1: Code Style

**Requirements**:
- Follow calibre code style conventions:
  - Python 3.8+ syntax
  - Single quotes for strings
  - PEP 8 compliance (enforced by ruff)
  - Type hints where appropriate
  - Docstrings for all public methods
- File headers:
  ```python
  #!/usr/bin/env python
  # License: GPLv3 Copyright: 2025, [Author] <email>
  ```
- Class documentation:
  ```python
  class BookshelfView(QAbstractScrollArea):
      '''
      Enhanced bookshelf view displaying books as spines on shelves.
      
      This view provides an immersive browsing experience with sorting
      and grouping capabilities.
      '''
  ```

### TR2: Dependencies

**Requirements**:
- Use existing calibre dependencies only
- Optional: PIL/Pillow for color extraction (with fallback)
- No new external dependencies
- Qt6/PyQt6 for UI components

### TR3: Internationalization

**Requirements**:
- All user-facing strings must be translatable
- Use `gettext` for translations:
  ```python
  from calibre.utils.localization import gettext as _
  ```
- Translation keys:
  - "Bookshelf view"
  - "Sort by Title"
  - "Group by Series"
  - etc.

### TR4: Configuration

**Requirements**:
- Store preferences in `gprefs`:
  - `'bookshelf_view_visible'`: Boolean
  - `'bookshelf_sort_by'`: String
  - `'bookshelf_group_by'`: String
  - `'bookshelf_spine_height'`: Integer (default: 150)
- Add tweaks for customization:
  - `'bookshelf_spine_min_width'`: Integer (default: 25)
  - `'bookshelf_spine_max_width'`: Integer (default: 55)
  - `'bookshelf_thumbnail_size'`: Integer (default: 20)

### TR5: Error Handling

**Requirements**:
- Graceful degradation if cover unavailable
- Handle missing metadata gracefully
- Log errors but don't crash
- Show placeholder for missing covers
- Fallback to default colors if extraction fails

## User Experience

### UX1: Visual Design

**Requirements**:
- Maintain dark theme consistency
- Shelf appearance: Realistic wood texture
- Spine colors: Vibrant but not overwhelming
- Smooth animations: 200-300ms transitions
- Clear visual hierarchy: Selected items stand out
- Readable text: Adequate contrast on spines

### UX2: Accessibility

**Requirements**:
- Keyboard navigation support
- Screen reader compatibility (Qt accessibility)
- High contrast mode support
- Tooltips for all interactive elements
- Clear focus indicators

### UX3: Discoverability

**Requirements**:
- Layout menu button clearly labeled
- Existing controls (Sort dropdown, context menus) work as expected
- Keyboard shortcuts documented
- Help text available
- Consistent with existing calibre UI patterns

## Implementation Phases

### Phase 1: Layout Integration and Core Bookshelf View (Week 1-2)

**Deliverables**:
- Add `bookshelf` field to `Visibility` dataclass in `central.py`
- Create `bookshelf_button` in `CentralContainer.__init__`
- Add bookshelf button to layout button order
- Implement mutual exclusivity logic (bookshelf shows → cover_browser hides)
- `BookshelfView` class skeleton
- Implement sort interface methods: `sort_by_named_field()`, `reverse_sort()`, `resort()`, `intelligent_sort()`, `multisort()`
- Ensure `gui.current_view()` returns bookshelf view when active
- Basic spine rendering (without covers)
- Shelf background rendering
- Scroll functionality
- Integration with `AlternateViews`

**Acceptance Criteria**:
- Bookshelf button appears in layout menu
- Clicking "Show Book Shelf" hides Cover Browser automatically
- Bookshelf view displays and can be toggled via layout menu
- Books render as spines on shelves
- Scrolling works smoothly
- Selection syncing with main view works
- Sort dropdown menu works with bookshelf view (all sort options functional)

### Phase 2: Cover Integration (Week 2-3)

**Deliverables**:
- Color extraction from covers
- Spine background coloring
- Cover thumbnail on spine
- Texture overlay implementation
- Hover cover reveal

**Acceptance Criteria**:
- Spines show cover-derived colors
- Thumbnails visible at bottom of spines
- Hover shows full cover popup
- Performance acceptable with 100+ books

### Phase 3: Sorting Integration and Grouping (Week 3-4)

**Deliverables**:
- Verify Sort dropdown integration works correctly
- Test all sort options with bookshelf view
- Implement grouping logic
- Visual group dividers
- Group labels
- Group controls via context menu (right-click on bookshelf view)

**Acceptance Criteria**:
- Sort dropdown menu fully functional with bookshelf view
- All sort options (Title, Author, Series, Tags, Date, etc.) work correctly
- Multi-column sorting works
- Saved sorts work
- Grouping displays properly
- Visual dividers clear
- Group controls accessible via context menu
- Group state persists in `gprefs`

### Phase 4: Polish and Optimization (Week 4-5)

**Deliverables**:
- Performance optimization
- Animation refinements
- Error handling improvements
- Configuration options
- Documentation

**Acceptance Criteria**:
- Performance targets met
- Smooth animations
- Robust error handling
- User preferences saved
- Code documented

## Testing Requirements

### Unit Tests

**Requirements**:
- Test color extraction function
- Test grouping logic
- Test sort mapping
- Test spine width calculation
- Test thumbnail generation

### Integration Tests

**Requirements**:
- Test layout menu integration (bookshelf button appears and functions)
- Test mutual exclusivity (bookshelf shows → cover_browser hides)
- Test selection syncing
- Test with various library sizes
- Test with missing covers
- Test with missing metadata

### Performance Tests

**Requirements**:
- Benchmark with 100, 500, 1000, 5000 books
- Measure render time
- Measure scroll FPS
- Measure memory usage
- Profile bottleneck areas

### User Acceptance Tests

**Requirements**:
- Test with real user libraries
- Gather feedback on visual design
- Test accessibility features
- Verify keyboard shortcuts
- Test on different screen sizes

## Changelog Entry

When this feature is released, add to `Changelog.txt`:

```yaml
{{{ 8.16.0 2025-12-XX

:: new features

- [TICKET_ID] Library view: Add enhanced bookshelf view mode showing books as spines on shelves. Accessible via Layout menu (bottom right). Bookshelf view integrates with existing Sort dropdown menu for all sorting options (Title, Author, Series, Tags, Date, etc.). Supports optional grouping by Series, Genre, or Time Period. Book spines display cover-derived colors and thumbnails, with hover to reveal full covers. Bookshelf and Cover Browser are mutually exclusive - showing Bookshelf automatically hides Cover Browser.

}}}
```

## Open Questions

1. **Cover Color Extraction**: Should we use a more sophisticated algorithm (k-means clustering) or is simple dominant color sufficient?
2. **Shelf Appearance**: Should shelf appearance be customizable (different wood types)?
3. **Grouping UI**: Should grouping be a toggle or dropdown with multiple options?
4. **Thumbnail Size**: Should thumbnail size be user-configurable?
5. **Animation Preferences**: Should animation speed be configurable for users with motion sensitivity?
6. **Keyboard Shortcut**: What keyboard shortcut should be used for bookshelf toggle? (`Shift+Alt+S` is proposed but may conflict)

## Future Enhancements (TODO)

### TODO1: Toggle Between Cover Browser and Bookshelf

**Status**: Deferred to Future Release

**Description**: 
Implement a direct toggle mechanism that allows users to switch between Cover Browser (Cover Flow) and Bookshelf view with a single action, rather than manually showing/hiding each view separately.

**Requirements**:
- Add toggle action that switches between Cover Browser and Bookshelf
- When toggling:
  - If Cover Browser is visible, hide it and show Bookshelf
  - If Bookshelf is visible, hide it and show Cover Browser
  - If neither is visible, show Bookshelf (default)
- Keyboard shortcut: `Alt+Shift+B` (or similar)
- Toggle state indicator in UI
- Preserve book selection during toggle
- Optionally preserve scroll position

**Rationale for Deferral**:
- Initial implementation focuses on adding bookshelf as a layout option
- Mutual exclusivity (bookshelf shows → cover browser hides) provides basic functionality
- Direct toggle can be added in a future release after user feedback

## Risks and Mitigations

### Risk 1: Performance with Large Libraries

**Mitigation**:
- Implement viewport-based rendering
- Lazy load covers
- Cache color extraction results
- Profile and optimize bottlenecks

### Risk 2: Cover Color Extraction Accuracy

**Mitigation**:
- Provide fallback to default colors
- Allow manual override (future enhancement)
- Test with various cover styles

### Risk 3: UI Complexity

**Mitigation**:
- Use existing calibre UI controls only (no custom toolbars)
- Follow existing calibre UI patterns
- Provide tooltips and help text
- Make grouping optional (default: off)
- Group controls via context menu (standard calibre pattern)

### Risk 4: Memory Usage

**Mitigation**:
- Only load visible covers
- Implement cover cache with size limits
- Monitor memory usage during testing
- Add memory usage warnings if needed

## Success Metrics

1. **Adoption**: 20%+ of users try bookshelf view within first month
2. **Performance**: 95% of users report smooth scrolling with 1000+ books
3. **Usability**: Average time to find book < 30 seconds
4. **Stability**: Zero crashes related to bookshelf view
5. **Feedback**: 4+ star rating in user feedback

## References

- Existing view implementations:
  - `src/calibre/gui2/library/alternate_views.py` - GridView
  - `src/calibre/gui2/cover_flow.py` - CoverFlowMixin
  - `src/calibre/gui2/library/views.py` - BooksView (reference for sort interface methods)
- UI components:
  - `src/calibre/gui2/central.py` - Layout buttons and CentralContainer
  - `src/calibre/gui2/init.py` - GridViewButton (reference for button patterns)
  - `src/calibre/gui2/library/models.py` - BooksModel
- Sort integration:
  - `src/calibre/gui2/actions/sort.py` - SortByAction (existing sort dropdown)
  - `src/calibre/gui2/layout.py` - SearchBar with sort button
- Documentation:
  - `manual/develop.rst` - Development guide
  - `manual/gui.rst` - GUI documentation



