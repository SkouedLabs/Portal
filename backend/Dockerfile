# Alpine, for a 255 MB image instead of 364 MB. The reason the Debian image was here in the first
# place was OpenSSL 3.5 — hybrid TLS 1.3 X25519MLKEM768 for outgoing connections (LDAPS, OIDC
# provider, status checks) when the remote server supports it. Alpine 3.24 carries OpenSSL 3.5.9,
# newer than Debian trixie's 3.5.7, and was checked to negotiate X25519MLKEM768 against a server
# that offers it, so nothing is given up by being smaller. If a future base drops below OpenSSL
# 3.5, the post-quantum claim in docs/security.md goes with it.
FROM python:3.14-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

COPY requirements.txt .
# --only-binary: every dependency publishes a musllinux wheel, so nothing is compiled here and no
# build toolchain is ever installed. If that stops being true for one of them, the build fails
# loudly rather than quietly pulling in gcc and tripling the image.
RUN pip install --only-binary=:all: -r requirements.txt

# Stamped by the publish workflow from the git tag; "dev" for a build from a checkout.
ARG PORTAL_NG_VERSION=dev
ENV PORTAL_NG_VERSION=${PORTAL_NG_VERSION}

COPY app ./app

# busybox adduser rather than shadow's useradd: same uid, one less package in the image.
RUN addgroup -S -g 10001 portal \
    && adduser -S -D -H -u 10001 -G portal -h /srv portal \
    && mkdir -p /data/uploads && chown -R portal:portal /data
USER 10001:10001

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)"

# The backend is only reachable by nginx (internal network): its X-Forwarded-* headers are trusted.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
