#!/data/data/com.termux/files/usr/bin/sh

url=$(curl --silent --data-binary @- https://yld.me/paste < "$1" | sed -En 's|^(.*)/(.*)$|\1/raw/\2.jpg|p')

# Optional: Copy URL to clipboard
#termux-clipboard-set $url

# Optional: Toast URL
#termux-toast -s $url

# Optional: Share URL to another application
echo $url | termux-share -a send -c text/plain -t $url

# Optional: Kill termux
pkill -f com.termux
