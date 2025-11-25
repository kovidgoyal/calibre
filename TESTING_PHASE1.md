# Testing Phase 1: Enhanced Bookshelf View

## Prerequisites

1. **Create the bookshelf icon** (temporary placeholder):
   - The code references `bookshelf.png` but it doesn't exist yet
   - For now, you can copy an existing icon as a placeholder:
   ```bash
   cp resources/images/grid.png resources/images/bookshelf.png
   ```
   - Or create a proper icon later (16x16 or 24x24 pixels)

2. **Ensure you have a calibre library with books** for testing

## Running calibre in Development Mode

### Option 1: Run from source (recommended)
```bash
cd /Users/andychuong/Documents/GauntletAI/Week\ 7/calibre
python3 -c "from calibre.gui_launch import calibre; calibre(['calibre'])"
```

### Option 2: Use calibre-debug (if installed)
```bash
calibre-debug --gui
```

### Option 3: Run the develop function
```bash
python3 -c "from calibre.gui2.central import develop; develop()"
```

## Testing Checklist

### 1. Layout Menu Integration

**Test Steps:**
1. Launch calibre
2. Look at the bottom-right corner of the main window
3. Click the "Layout" button (or look for layout buttons if they're expanded)
4. Look for "Book Shelf" button

**Expected Results:**
- ✅ "Book Shelf" button appears in the layout menu
- ✅ Button shows "Show Book Shelf" when hidden
- ✅ Button shows "Hide Book Shelf" when visible
- ✅ Button has keyboard shortcut `Shift+Alt+S` (if configured)

**If button doesn't appear:**
- Check console for import errors
- Verify `bookshelf.png` exists (or use placeholder)
- Check that `init.py` was updated correctly

### 2. Mutual Exclusivity with Cover Browser

**Test Steps:**
1. Show Cover Browser (if not already visible)
2. Click "Show Book Shelf" button
3. Observe Cover Browser state

**Expected Results:**
- ✅ When Bookshelf is shown, Cover Browser automatically hides
- ✅ Cover Browser button state updates to "Show Cover Browser"
- ✅ When Bookshelf is hidden, Cover Browser state doesn't automatically change

### 3. Bookshelf View Display

**Test Steps:**
1. Click "Show Book Shelf" button
2. Observe the main library area

**Expected Results:**
- ✅ Bookshelf view replaces the book list view
- ✅ Books are displayed as vertical spines (rectangles)
- ✅ Spines are arranged horizontally on shelves
- ✅ Shelf background shows dark wood gradient
- ✅ Each spine shows book title (rotated vertically)
- ✅ Spines have default brown color (#8B4513) for now

**If view doesn't appear:**
- Check console for errors
- Verify `BookshelfView` was registered in `init.py`
- Check that `alternate_views.show_view('bookshelf')` is being called

### 4. Scrolling

**Test Steps:**
1. With bookshelf view visible
2. Use mouse wheel to scroll
3. Use scrollbar to scroll

**Expected Results:**
- ✅ Scrolling works smoothly
- ✅ Scrollbar appears when content exceeds viewport
- ✅ Books remain visible during scroll

### 5. Book Selection

**Test Steps:**
1. Click on a book spine
2. Try Ctrl+Click to select multiple books
3. Try Shift+Click for range selection
4. Double-click a book spine

**Expected Results:**
- ✅ Single click selects a book (spine highlighted)
- ✅ Selected spine shows yellow border/glow
- ✅ Ctrl+Click toggles selection
- ✅ Shift+Click selects range
- ✅ Double-click opens book in viewer
- ✅ Selection syncs with main library view (if visible)

### 6. Sort Integration

**Test Steps:**
1. With bookshelf view visible
2. Click the "Sort" button in the search bar (top toolbar)
3. Try different sort options (Title, Author, Date, etc.)
4. Try "Reverse current sort" (Shift+F5)
5. Try "Re-apply current sort" (F5)

**Expected Results:**
- ✅ Sort dropdown menu is visible and functional
- ✅ All sort options work (Title, Author, Series, Tags, Date, etc.)
- ✅ Books reorder according to sort
- ✅ Reverse sort works
- ✅ Re-apply sort works
- ✅ Multi-column sorting works (if tested)

**If sorting doesn't work:**
- Check console for errors in sort methods
- Verify `BookshelfView` implements all sort interface methods
- Check that `gui.current_view()` returns bookshelf view when active

### 7. Selection Syncing

**Test Steps:**
1. Show both main library view and bookshelf view (toggle between them)
2. Select a book in main view
3. Switch to bookshelf view
4. Select a different book in bookshelf view
5. Switch back to main view

**Expected Results:**
- ✅ Selection in main view syncs to bookshelf view
- ✅ Selection in bookshelf view syncs to main view
- ✅ Current book is preserved when switching views

### 8. Keyboard Navigation

**Test Steps:**
1. With bookshelf view visible and focused
2. Use arrow keys to navigate
3. Press Enter to open book
4. Press Space to toggle selection

**Expected Results:**
- ✅ Arrow keys navigate between books
- ✅ Enter opens selected book
- ✅ Keyboard navigation works smoothly

### 9. Context Menu

**Test Steps:**
1. Right-click on a book spine in bookshelf view

**Expected Results:**
- ✅ Context menu appears (same as other views)
- ✅ Menu options work correctly

## Common Issues and Solutions

### Issue: Bookshelf button doesn't appear
**Solution:**
- Check that `bookshelf.png` exists (create placeholder if needed)
- Verify `init.py` button_order includes 'bs'
- Check console for import errors

### Issue: Bookshelf view doesn't show
**Solution:**
- Verify `BookshelfView` is imported in `init.py`
- Check that `alternate_views.add_view('bookshelf', ...)` is called
- Look for errors in console when toggling button

### Issue: Selection doesn't sync
**Solution:**
- Verify `selectionModel()` method exists in `BookshelfView`
- Check that `AlternateViews` connected signals properly
- Ensure `set_current_row()` and `select_rows()` update selection model

### Issue: Sorting doesn't work
**Solution:**
- Verify all sort methods are implemented
- Check that `gui.current_view()` returns bookshelf view
- Ensure model is properly set on bookshelf view

### Issue: Books don't render
**Solution:**
- Check that model is set: `bookshelf_view.setModel(model)`
- Verify `paintEvent` is being called
- Check console for painting errors
- Ensure viewport widget is properly set up

## Debugging Tips

1. **Enable debug output:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Check console output** for Python errors

3. **Verify model connection:**
   - Bookshelf view should have same model as main view
   - Check `bookshelf_view.model()` returns valid model

4. **Test with small library first** (10-20 books) before testing with large library

5. **Check Qt signals:**
   - Verify selection model signals are connected
   - Check that model signals trigger updates

## Next Steps After Testing

If all tests pass:
- ✅ Phase 1 is complete
- Proceed to Phase 2: Cover Integration

If issues are found:
- Note the specific issue
- Check console for error messages
- Verify code matches existing calibre patterns
- Fix issues and re-test

## Notes

- The bookshelf icon (`bookshelf.png`) needs to be created or a placeholder used
- Cover colors and thumbnails are not implemented yet (Phase 2)
- Grouping functionality is not implemented yet (Phase 3)
- Performance optimizations come in Phase 4


