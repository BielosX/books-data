CREATE TABLE books (
    book_id serial PRIMARY KEY,
    author_id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(255) NOT NULL,
    rating REAL,
    published DATE
);