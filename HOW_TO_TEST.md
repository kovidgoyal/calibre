# How to Test the Bookshelf View Feature

## Quick Start (Official Method)

Following the official calibre development instructions:

### Step 1: Run the development script

From the calibre source directory, run:

```bash
cd /Users/andychuong/Documents/GauntletAI/Week\ 7/calibre
./calibre-develop.sh
```

This script:
- Sets `CALIBRE_DEVELOP_FROM` to point to your `src` directory
- Runs `calibre-debug -g` which loads code from your source directory

### Alternative: Manual setup

If you prefer to run it manually:

```bash
cd /Users/andychuong/Documents/GauntletAI/Week\ 7/calibre
export CALIBRE_DEVELOP_FROM="/Users/andychuong/Documents/GauntletAI/Week 7/calibre/src"
/Applications/calibre.app/Contents/MacOS/calibre-debug -g
```

Or if you have calibre-debug in your PATH:

```bash
export CALIBRE_DEVELOP_FROM="/Users/andychuong/Documents/GauntletAI/Week 7/calibre/src"
calibre-debug -g
```

## What to Test

Once calibre is running:

1. **Find the Layout Menu**:
   - Look at the bottom-right corner of the main window
   - Click the "Layout" button (or look for expanded layout buttons)
   - You should see a "Book Shelf" button

2. **Show Bookshelf View**:
   - Click "Show Book Shelf" (or use `Shift+Alt+S` if configured)
   - The main library view should switch to show books as spines on shelves
   - Cover Browser should automatically hide (mutual exclusivity)

3. **Test Basic Features**:
   - **Scrolling**: Use mouse wheel to scroll through books
   - **Selection**: Click on book spines to select them
   - **Double-click**: Double-click a spine to open the book
   - **Sorting**: Use the Sort dropdown (top toolbar) - all sort options should work

4. **Test Mutual Exclusivity**:
   - With bookshelf visible, try to show Cover Browser
   - Cover Browser should remain hidden
   - Hide bookshelf, then show Cover Browser - it should work

## Troubleshooting

### If calibre doesn't start:
- Check that you have a calibre library set up
- Check console/terminal for error messages
- Verify Python path is set correctly if running from source

### If bookshelf button doesn't appear:
- Check that `resources/images/bookshelf.png` exists (we created a placeholder)
- Look for import errors in the console
- Verify the code changes were saved

### If bookshelf view doesn't show:
- Check console for errors when clicking the button
- Verify `BookshelfView` was registered in `init.py`
- Check that `alternate_views.show_view('bookshelf')` is being called

### If sorting doesn't work:
- Verify `gui.current_view()` returns bookshelf view when active
- Check that all sort methods are implemented in `BookshelfView`
- Look for errors in console when using sort menu

## Expected Behavior

- Bookshelf view shows books as vertical spines (rectangles) on shelves
- Spines are arranged horizontally, left to right
- Shelf has dark wood gradient background
- Each spine shows book title (rotated vertically)
- Spines have default brown color (cover colors come in Phase 2)
- Selection highlights spines with yellow border
- Scrolling works smoothly
- All sort options work via Sort dropdown menu

## Next Steps

If everything works:
- ✅ Phase 1 is complete!
- Proceed to Phase 2: Cover Integration

If you find issues:
- Note the specific problem
- Check console for error messages
- Report the issue with error details

