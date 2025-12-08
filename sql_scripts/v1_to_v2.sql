-- Migration from database version 1 to version 2
-- Adds tags and tag_link_map tables for tagging functionality

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

-- Update database version
UPDATE metadata SET value = '2.0.0' WHERE name = 'db_version';
