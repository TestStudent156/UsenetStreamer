# Thin Home Assistant add-on wrapper around the published UsenetStreamer image.
# We build FROM the upstream image so a small run script can translate add-on
# options (/data/options.json) into the environment variables UsenetStreamer
# expects (ADDON_SHARED_SECRET, etc.). A bare `image:` reference can't inject env.
FROM ghcr.io/sanket9225/usenetstreamer:1.7.12

# jq parses /data/options.json in run.sh; the upstream image is alpine-based.
RUN apk add --no-cache jq

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD [ "/run.sh" ]
