CREATE TABLE authors (
    author_id serial PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    average_rating REAL NOT NULL,
    fans INTEGER NOT NULL,
    users_read INTEGER NOT NULL
);
