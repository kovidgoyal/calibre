CREATE TEMP TRIGGER fts_db_book_deleted_trg AFTER DELETE ON main.books BEGIN
    DELETE FROM books_text WHERE book=OLD.id;
    DELETE FROM dirtied_formats WHERE book=OLD.id;
END;

CREATE TEMP TRIGGER fts_db_format_deleted_trg AFTER DELETE ON main.data BEGIN
    DELETE FROM books_text WHERE book=OLD.id AND format=OLD.format;
    DELETE FROM dirtied_formats WHERE book=OLD.id AND format=OLD.format;
END;

CREATE TEMP TRIGGER fts_db_format_added_trg AFTER INSERT ON main.data BEGIN
    INSERT INTO dirtied_formats(book, format) VALUES (NEW.book, NEW.format);
END;

CREATE TEMP TRIGGER fts_db_format_updated_trg AFTER UPDATE ON main.data BEGIN
    INSERT INTO dirtied_formats(book, format) VALUES (NEW.book, NEW.format);
END;
