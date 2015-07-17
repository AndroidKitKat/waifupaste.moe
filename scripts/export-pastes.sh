#!/bin/sh

DB=${HOME}/.config/yldme/db

echo "SELECT name from YldMe WHERE type='paste';" | sqlite3 ${DB} | while read name; do
    echo "SELECT value FROM YldMe WHERE name='${name}';" | sqlite3 ${DB} > ${name}
done
