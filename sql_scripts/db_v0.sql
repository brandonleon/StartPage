CREATE TABLE links (
	id VARCHAR(36) NOT NULL,
	name VARCHAR(64) NOT NULL,
	url TEXT NOT NULL,
	clicks INTEGER,
	PRIMARY KEY (id),
	UNIQUE (name),
	UNIQUE (url)
);
CREATE TABLE clicks (
	id VARCHAR(36) NOT NULL,
	"LinkId" VARCHAR(36),
	datetime DATETIME,
	PRIMARY KEY (id),
	FOREIGN KEY("LinkId") REFERENCES links (id)
);
