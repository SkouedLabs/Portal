let csrfToken = null
let unauthorizedHandler = null

export function setCsrf(token) {
  csrfToken = token
}

export function onUnauthorized(fn) {
  unauthorizedHandler = fn
}

function errorMessage(data, status) {
  const d = data?.detail
  if (Array.isArray(d)) {
    return d.map((e) => `${(e.loc || []).filter((x) => x !== 'body').join('.')} : ${e.msg}`).join('\n')
  }
  return d || `Error ${status}`
}

async function request(method, url, body, opts = {}) {
  const headers = { ...(opts.headers || {}) }
  const isForm = body instanceof FormData
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json'
  if (method !== 'GET' && csrfToken) headers['X-CSRF-Token'] = csrfToken
  const res = await fetch(url, {
    method,
    headers,
    credentials: 'same-origin',
    keepalive: opts.keepalive || false,
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  })
  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const err = new Error(errorMessage(data, res.status))
    err.status = res.status
    if (res.status === 401 && !opts.silent && unauthorizedHandler) unauthorizedHandler()
    throw err
  }
  return data
}

export const api = {
  get: (url, opts) => request('GET', url, undefined, opts),
  post: (url, body, opts) => request('POST', url, body ?? {}, opts),
  put: (url, body, opts) => request('PUT', url, body, opts),
  patch: (url, body, opts) => request('PATCH', url, body, opts),
  del: (url, opts) => request('DELETE', url, undefined, opts),
  upload(file, kind = '') {
    const fd = new FormData()
    fd.append('file', file)
    // Lets the server bound the image to the size it will be drawn at ("icon" / "background")
    if (kind) fd.append('kind', kind)
    return request('POST', '/api/uploads', fd)
  },
  logClick(payload) {
    // keepalive: the request survives navigation to the clicked link
    return request('POST', '/api/logs/click', payload, { keepalive: true, silent: true }).catch(() => {})
  },
}
