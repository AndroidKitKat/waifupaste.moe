#!/bin/sh

for style in $(pygmentize -L styles | grep \* | tr -d -c '[:alpha:]\n'); do
    pygmentize -S $style -f html > $style.css
done
