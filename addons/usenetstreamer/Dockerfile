# Thin Home Assistant add-on wrapper around the published UsenetStreamer image.
# We build FROM the upstream image so a small run script can translate add-on
# options (/data/options.json) into the environment variables UsenetStreamer
# expects (ADDON_SHARED_SECRET, etc.). A bare `image:` reference can't inject env.
FROM ghcr.io/sanket9225/usenetstreamer:1.7.12

# jq parses /data/options.json in run.sh; the upstream image is alpine-based.
RUN apk add --no-cache jq

# run.sh lives in /usr/local/bin (a node-writable dir) and is owned by node
# so it can be invoked as the unprivileged runtime user.
COPY run.sh /usr/local/bin/run.sh
RUN chmod 0755 /usr/local/bin/run.sh \
 && chown node:node /usr/local/bin/run.sh

# Drop privileges: the upstream image's `node` user is the one that ships with
# node:22-alpine (uid 1000). Build steps above still run as root.
# /data is Supervisor-mounted at runtime — we deliberately do NOT create it
# in the image (some Supervisor versions reject pre-existing /data).
# The runtime entry script (run.sh) chowns /data/config for the node user.
USER node

CMD [ "/usr/local/bin/run.sh" ]
