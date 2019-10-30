FROM	    alpine:latest
MAINTAINER  Peter Bui <pbui@yld.bx612.space>

RUN	    apk update && \
	    apk add python3 \
		    py3-markdown \
		    py3-tornado \
		    py3-pygments \
		    py3-yaml \
		    file

RUN	    wget -O - https://gitlab.com/pbui/yldme/-/archive/master/yldme-master.tar.gz | tar xzvf -

EXPOSE	    9515
ENTRYPOINT  ["/yldme-master/yldme.py", "--config-dir=/var/lib/yldme", "--address=0.0.0.0"]
