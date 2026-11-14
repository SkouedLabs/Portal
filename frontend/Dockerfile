# ---- Build ----
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY . .
RUN npm run build

# ---- Runtime ----
# Unprivileged nginx (uid 101, no root master process).
# Default: plain HTTP on 8080 behind your reverse proxy (nginx, Traefik…), which handles TLS.
# Optional: FRONTEND_TLS=true to terminate TLS here (OpenSSL >= 3.5: X25519MLKEM768).
FROM nginxinc/nginx-unprivileged:1.31-alpine

USER root
RUN apk add --no-cache openssl \
    && rm -f /etc/nginx/conf.d/default.conf \
    && mkdir -p /etc/nginx/certs /etc/nginx/portal \
    && chown 101:101 /etc/nginx/certs && chmod 700 /etc/nginx/certs
COPY docker/nginx-main.conf /etc/nginx/nginx.conf
COPY docker/headers.inc /etc/nginx/portal/headers.inc
COPY docker/templates/http.conf.template /etc/nginx/templates-http/default.conf.template
COPY docker/templates/app.inc.template   /etc/nginx/templates-http/app.inc.template
COPY docker/templates/tls.conf.template  /etc/nginx/templates-tls/default.conf.template
COPY docker/templates/app.inc.template   /etc/nginx/templates-tls/app.inc.template
COPY docker/10-portal.envsh /docker-entrypoint.d/10-portal.envsh
# Strip CRLF in case the repository was checked out on Windows
RUN sed -i 's/\r$//' /docker-entrypoint.d/10-portal.envsh /etc/nginx/nginx.conf /etc/nginx/portal/headers.inc \
        /etc/nginx/templates-http/* /etc/nginx/templates-tls/* \
    && chmod 755 /docker-entrypoint.d/10-portal.envsh
COPY --from=build /app/dist /usr/share/nginx/html
USER 101

# Only these variables are substituted in the templates (nginx $variables stay untouched).
# The rendered configuration goes to /tmp: the root filesystem can be mounted read-only.
ENV FRONTEND_TLS=false \
    BACKEND_HOST=backend \
    TRUSTED_PROXIES="127.0.0.1/32 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 ::1/128 fc00::/7" \
    HTTPS_PUBLIC_PORT=443 \
    NGINX_ENVSUBST_FILTER="^(BACKEND_HOST|HTTPS_PUBLIC_PORT)$" \
    NGINX_ENVSUBST_OUTPUT_DIR=/tmp/nginx/conf.d

EXPOSE 8080 8443
HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
