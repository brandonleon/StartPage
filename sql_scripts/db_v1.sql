CREATE TABLE IF NOT EXISTS links
(id VARCHAR(36) not null primary key,
 name TEXT not null unique,
 url TEXT not null unique,
 rank FLOAT,
 accessed integer
);

CREATE TABLE IF NOT EXISTS config
(id VARCHAR(36) not null primary key,
 name TEXT not null unique,
 value TEXT not null
);

INSERT INTO config (id, name, value) VALUES ('1', 'batch', '20');

CREATE TABLE IF NOT EXISTS metadata
(id VARCHAR(36) not null primary key,
 name TEXT not null unique,
 value TEXT not null
);

INSERT INTO metadata (id, name, value) VALUES ('1', 'db_version', '1.0.0');