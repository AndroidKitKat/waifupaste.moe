#!/bin/sh

DB=${HOME}/.config/yldme/db

sqlite3 ${DB} <<EOF
    CREATE TABLE IF NOT EXISTS YldMe_V2 (
        id      INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        ctime   INTEGER NOT NULL,
        mtime   INTEGER NOT NULL,
        hits    INTEGER NOT NULL DEFAULT 0,
        type    TEXT NOT NULL CHECK (type IN ('paste', 'url', 'image')) DEFAULT 'url',
        name    TEXT NOT NULL UNIQUE,
        value   TEXT NOT NULL UNIQUE
    );
    INSERT INTO YldMe_V2 SELECT * FROM YldMe;
    DROP TABLE YldMe;
    ALTER TABLE YldMe_V2 RENAME TO YldMe;
EOF

echo "SELECT name from YldMe WHERE type='paste';" | sqlite3 ${DB} | while read name; do
    echo "UPDATE YldMe SET value='$(sha1sum ../uploads/${name} | awk '{print $1}')' WHERE name='${name}';" | sqlite3 ${DB}
done
