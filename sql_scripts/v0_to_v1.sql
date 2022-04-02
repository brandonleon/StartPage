ALTER TABLE 'links' RENAME TO 'links_old';
CREATE TABLE IF NOT EXISTS links
(id VARCHAR(36) not null primary key,
 name TEXT not null unique,
 url TEXT not null unique,
 rank FLOAT,
 accessed INTEGER
);
INSERT INTO links (id, name, url, rank, accessed) SELECT id, name, url, clicks, strftime('%s', 'now') as accessed FROM links_old;
DROP TABLE links_old;
DROP TABLE clicks;

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

INSERT INTO metadata (id, name, value) VALUES ('1', 'db_version', '1.0.0-alpha.0');