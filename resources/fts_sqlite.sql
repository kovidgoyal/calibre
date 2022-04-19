CREATE TABLE fts_db.dirtied_formats ( id INTEGER PRIMARY KEY,
	book INTEGER NOT NULL,
	format TEXT NOT NULL COLLATE NOCASE,
    in_progress INTEGER NOT NULL DEFAULT FALSE,
    UNIQUE(book, format)
);

CREATE TABLE fts_db.books_text ( id INTEGER PRIMARY KEY,
	book INTEGER NOT NULL,
	timestamp REAL NOT NULL,
	format TEXT NOT NULL COLLATE NOCASE,
    format_hash TEXT NOT NULL COLLATE NOCASE,
    format_size INTEGER NOT NULL DEFAULT 0,
    searchable_text TEXT NOT NULL DEFAULT "",
    text_size INTEGER NOT NULL DEFAULT 0,
    text_hash TEXT NOT NULL COLLATE NOCASE DEFAULT "",
    err_msg TEXT DEFAULT "",
    UNIQUE(book, format)
);


CREATE VIRTUAL TABLE fts_db.books_fts USING fts5(searchable_text, content = 'fts_db.books_text', content_rowid = 'id', tokenize = 'calibre remove_diacritics 2');
CREATE VIRTUAL TABLE fts_db.books_fts_stemmed USING fts5(searchable_text, content = 'fts_db.books_text', content_rowid = 'id', tokenize = 'porter calibre remove_diacritics 2');

CREATE TRIGGER fts_db.books_fts_insert_trg AFTER INSERT ON fts_db.books_text 
BEGIN
    INSERT INTO books_fts(rowid, searchable_text) VALUES (NEW.id, NEW.searchable_text);
    INSERT INTO books_fts_stemmed(rowid, searchable_text) VALUES (NEW.id, NEW.searchable_text);
    DELETE FROM dirtied_formats WHERE book=NEW.book AND format=NEW.format;
END;

CREATE TRIGGER fts_db.books_fts_delete_trg AFTER DELETE ON fts_db.books_text 
BEGIN
    INSERT INTO books_fts(books_fts, rowid, searchable_text) VALUES('delete', OLD.id, OLD.searchable_text);
    INSERT INTO books_fts_stemmed(books_fts_stemmed, rowid, searchable_text) VALUES('delete', OLD.id, OLD.searchable_text);
END;

CREATE TRIGGER fts_db.books_fts_update_trg AFTER UPDATE ON fts_db.books_text 
BEGIN
    INSERT INTO books_fts(books_fts, rowid, searchable_text) VALUES('delete', OLD.id, OLD.searchable_text);
    INSERT INTO books_fts(rowid, searchable_text) VALUES (NEW.id, NEW.searchable_text);
    INSERT INTO books_fts_stemmed(books_fts_stemmed, rowid, searchable_text) VALUES('delete', OLD.id, OLD.searchable_text);
    INSERT INTO books_fts_stemmed(rowid, searchable_text) VALUES (NEW.id, NEW.searchable_text);
    DELETE FROM dirtied_formats WHERE book=NEW.book AND format=NEW.format;
END;

PRAGMA fts_db.user_version=1;
