# Security headers, included in the server block and in every location that sets its own
# headers (nginx does not inherit add_header into such locations).
# $hsts is empty in HTTP mode (the reverse proxy sends HSTS) and set in built-in TLS mode;
# nginx does not send a header whose value is empty.
add_header Strict-Transport-Security $hsts always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "same-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()" always;
add_header Cross-Origin-Opener-Policy "same-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'" always;
