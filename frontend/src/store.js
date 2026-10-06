import { reactive } from 'vue'
import { api, setCsrf } from './api'

export const state = reactive({
  config: null, // public configuration (branding + sign-in methods)
  me: null,
  meLoaded: false,
  toasts: [],
})

let toastId = 0
export function notify(message, type = 'success', timeout = 4000) {
  const id = ++toastId
  state.toasts.push({ id, message, type })
  setTimeout(() => {
    const i = state.toasts.findIndex((t) => t.id === id)
    if (i >= 0) state.toasts.splice(i, 1)
  }, type === 'error' ? 8000 : timeout)
}

export function applyBranding() {
  const b = state.config?.branding
  if (!b) return
  document.title = b.portal_name || 'Portal-NG'
  const fav = document.getElementById('favicon')
  if (fav) fav.href = b.favicon || b.logo || '/favicon.svg'
  document.documentElement.style.setProperty('--brand', b.primary_color || '#3367d6')
}

export async function loadPublicConfig() {
  state.config = await api.get('/api/public/config')
  applyBranding()
}

export async function loadMe() {
  try {
    // Probe first: avoids a 401 (red in the browser console) on the sign-in page
    const probe = await api.get('/api/auth/session', { silent: true })
    if (!probe.authenticated) throw new Error('anonymous')
    state.me = await api.get('/api/auth/me', { silent: true })
    setCsrf(state.me.csrf_token)
  } catch {
    state.me = null
    setCsrf(null)
  }
  state.meLoaded = true
}

export async function logout() {
  try {
    await api.post('/api/auth/logout')
  } finally {
    state.me = null
    setCsrf(null)
  }
}

export function prefersDark() {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches
}

export const storage = {
  get(key, fallback = null) {
    try {
      const v = localStorage.getItem(`portal-ng:${key}`)
      return v === null ? fallback : JSON.parse(v)
    } catch {
      return fallback
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(`portal-ng:${key}`, JSON.stringify(value))
    } catch {
      /* storage unavailable */
    }
  },
}
