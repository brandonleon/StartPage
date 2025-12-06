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

INSERT INTO metadata (id, name, value) VALUES ('1', 'db_version', '2.0.0');

CREATE TABLE IF NOT EXISTS tags
(id VARCHAR(36) not null primary key,
 name TEXT not null unique,
 count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tag_link_map
(tag_id VARCHAR(36) not null,
 link_id VARCHAR(36) not null,
 PRIMARY KEY (tag_id, link_id),
 FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
 FOREIGN KEY (link_id) REFERENCES links(id) ON DELETE CASCADE
);
