<template>
  <div class="login-page">
    <div class="login-bg" :style="bg.style"></div>
    <div v-if="bg.overlay" class="login-overlay" :style="{ opacity: bg.overlay }"></div>

    <div class="login-card" :class="{ wide: step === 'enroll' }">
      <div class="brand">
        <img v-if="branding.logo" :src="branding.logo" alt="" class="logo" />
        <div v-else class="logo-fallback"><i class="fa-solid fa-house-chimney"></i></div>
        <h1>{{ branding.portal_name }}</h1>
        <p v-if="branding.subtitle && step === 'password'" class="muted">{{ branding.subtitle }}</p>
      </div>

      <div v-if="branding.login_message && step === 'password'" class="alert info">{{ branding.login_message }}</div>
      <div v-if="error" class="alert error" role="alert">{{ error }}</div>

      <!-- Step 1: password -->
      <template v-if="step === 'password'">
        <form v-if="showForm" @submit.prevent="submit">
          <div class="field">
            <label for="u">Username</label>
            <input id="u" v-model="username" class="input" autocomplete="username" autofocus required />
          </div>
          <div class="field">
            <label for="p">Password</label>
            <input id="p" v-model="password" class="input" type="password" autocomplete="current-password" required />
          </div>
          <button class="btn primary full" :disabled="busy">
            <i :class="busy ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-right-to-bracket'"></i>
            Sign in
          </button>
        </form>

        <template v-if="login.oidc">
          <div v-if="showForm" class="divider"><span>or</span></div>
          <a class="btn full sso" :href="ssoUrl"><i class="fa-solid fa-key"></i> {{ login.oidc_label }}</a>
        </template>

        <p v-if="!showForm && !login.oidc" class="muted center">No sign-in method is enabled.</p>
      </template>

      <!-- Step 2: second factor -->
      <template v-else-if="step === 'verify'">
        <p class="center step-title"><i class="fa-solid fa-shield-halved"></i> Two-step verification</p>
        <div v-if="mfa.methods.length > 1" class="seg">
          <button v-if="mfa.methods.includes('webauthn')" :class="{ active: method === 'webauthn' }" @click="method = 'webauthn'">
            <i class="fa-solid fa-fingerprint"></i> Security key
          </button>
          <button v-if="mfa.methods.includes('totp')" :class="{ active: method === 'totp' }" @click="method = 'totp'">
            <i class="fa-solid fa-mobile-screen-button"></i> App code
          </button>
          <button v-if="mfa.methods.includes('recovery')" :class="{ active: method === 'recovery' }" @click="method = 'recovery'">
            <i class="fa-solid fa-life-ring"></i> Recovery
          </button>
        </div>

        <div v-if="method === 'webauthn'" class="center">
          <p class="muted">Use your security key or passkey to continue.</p>
          <button class="btn primary full" :disabled="busy" @click="verifyWebauthn">
            <i :class="busy ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-fingerprint'"></i> Use my security key
          </button>
        </div>
        <form v-else @submit.prevent="verifyCode">
          <div class="field">
            <label for="c">{{ method === 'totp' ? 'Code from your authenticator app' : 'Recovery code' }}</label>
            <input
              id="c"
              ref="codeEl"
              v-model="code"
              class="input code-input"
              :inputmode="method === 'totp' ? 'numeric' : 'text'"
              autocomplete="one-time-code"
              :placeholder="method === 'totp' ? '123456' : 'XXXX-XXXX-XXXX-XXXX'"
              required
            />
          </div>
          <button class="btn primary full" :disabled="busy">
            <i :class="busy ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-check'"></i> Verify
          </button>
        </form>
        <button class="btn ghost full back" @click="restart"><i class="fa-solid fa-arrow-left"></i> Use another account</button>
      </template>

      <!-- Forced enrolment -->
      <template v-else-if="step === 'enroll'">
        <p class="center step-title"><i class="fa-solid fa-shield-halved"></i> Set up two-step verification</p>
        <p class="muted center small">Your administrator requires a second factor for your account. Choose a method to continue.</p>
        <MfaSetup :methods="mfa.methods" :enrol-token="mfa.token" @finished="enrolled" />
        <button class="btn ghost full back" @click="restart"><i class="fa-solid fa-arrow-left"></i> Cancel</button>
      </template>
    </div>
    <footer v-if="branding.footer" class="login-footer">{{ branding.footer }}</footer>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import MfaSetup from '../components/MfaSetup.vue'
import { loadMe, state } from '../store'
import { loginBackground } from '../theme'
import { getAssertion, webauthnSupported } from '../webauthn'

const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const code = ref('')
const codeEl = ref(null)
const busy = ref(false)
const error = ref(route.query.error || '')
const step = ref('password')
const mfa = ref({ token: '', methods: [] })
const method = ref('totp')

const branding = computed(() => state.config?.branding || { portal_name: 'Portal-NG' })
const login = computed(() => state.config?.login || {})
const bg = computed(() => loginBackground(branding.value))
const showForm = computed(() => login.value.local || login.value.ldap)
const next = computed(() => {
  const n = route.query.next
  return typeof n === 'string' && n.startsWith('/') && !n.startsWith('//') ? n : '/'
})
const ssoUrl = computed(() => `/api/auth/oidc/login?next=${encodeURIComponent(next.value)}`)

async function signedIn() {
  password.value = ''
  await loadMe()
  router.replace(next.value)
}

function restart() {
  step.value = 'password'
  mfa.value = { token: '', methods: [] }
  code.value = ''
  password.value = ''
  error.value = ''
}

async function guard(fn) {
  busy.value = true
  error.value = ''
  try {
    await fn()
  } catch (e) {
    error.value = e.message
    // Challenge expired or too many attempts: back to the password step
    if (e.status === 401 && step.value !== 'password' && /expired|sign in again|start again/i.test(e.message)) {
      const msg = e.message
      restart()
      error.value = msg
    }
  } finally {
    busy.value = false
  }
}

const submit = () =>
  guard(async () => {
    const r = await api.post('/api/auth/login', { username: username.value, password: password.value }, { silent: true })
    if (!r.mfa) return signedIn()
    password.value = ''
    mfa.value = { token: r.token, methods: r.methods }
    if (r.mfa === 'enroll') {
      step.value = 'enroll'
      return
    }
    step.value = 'verify'
    method.value = r.methods.includes('webauthn') && webauthnSupported() ? 'webauthn' : r.methods.includes('totp') ? 'totp' : 'recovery'
    if (method.value === 'webauthn') verifyWebauthn()
  })

const verifyCode = () =>
  guard(async () => {
    await api.post('/api/auth/mfa/verify', { token: mfa.value.token, method: method.value, code: code.value }, { silent: true })
    await signedIn()
  })

const verifyWebauthn = () =>
  guard(async () => {
    const options = await api.post('/api/auth/mfa/webauthn/options', { token: mfa.value.token }, { silent: true })
    const credential = await getAssertion(options)
    await api.post('/api/auth/mfa/webauthn/verify', { token: mfa.value.token, credential }, { silent: true })
    await signedIn()
  })

function enrolled(r) {
  if (r?.signed_in) signedIn()
}

watch(method, async (m) => {
  code.value = ''
  error.value = ''
  if (m !== 'webauthn') {
    await nextTick()
    codeEl.value?.focus()
  }
})

onMounted(() => {
  if (state.me) return router.replace(next.value)
  if (login.value.oidc_auto_redirect && !route.query.error && route.query.local !== '1') {
    window.location.href = ssoUrl.value
  }
})
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
  isolation: isolate;
  overflow: hidden;
}
.login-bg {
  position: fixed;
  inset: 0;
  z-index: -2;
  background-size: cover;
  background-position: center;
}
.login-overlay {
  position: fixed;
  inset: 0;
  z-index: -1;
  background: #000;
}
.login-card {
  width: 100%;
  max-width: 400px;
  background: var(--ui-surface);
  border-radius: 14px;
  padding: 32px 28px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.3);
}
.login-card.wide {
  max-width: 560px;
}
.brand {
  text-align: center;
  margin-bottom: 22px;
}
.logo {
  max-height: 72px;
  max-width: 200px;
  object-fit: contain;
  margin-bottom: 12px;
}
.logo-fallback {
  width: 64px;
  height: 64px;
  margin: 0 auto 12px;
  border-radius: 16px;
  background: var(--brand);
  color: #fff;
  font-size: 1.8rem;
  display: flex;
  align-items: center;
  justify-content: center;
}
.brand h1 {
  font-size: 1.45rem;
  margin: 0 0 4px;
}
.brand p {
  margin: 0;
}
.full {
  width: 100%;
  padding: 11px;
}
.back {
  margin-top: 10px;
  font-weight: 500;
}
.sso {
  font-size: 0.95rem;
}
.divider {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--ui-muted);
  font-size: 0.8rem;
  margin: 18px 0;
}
.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--ui-border);
}
.center {
  text-align: center;
}
.small {
  font-size: 0.85rem;
}
.step-title {
  font-weight: 600;
  margin: 0 0 14px;
}
.step-title i {
  color: var(--brand);
  margin-right: 4px;
}
.seg {
  display: flex;
  gap: 4px;
  padding: 3px;
  border-radius: 9px;
  background: var(--ui-surface-2);
  border: 1px solid var(--ui-border);
  margin-bottom: 16px;
}
.seg button {
  flex: 1;
  font: inherit;
  font-size: 0.8rem;
  border: none;
  background: none;
  color: var(--ui-muted);
  padding: 7px 4px;
  border-radius: 6px;
  cursor: pointer;
  white-space: nowrap;
}
.seg button.active {
  background: var(--ui-surface);
  color: var(--ui-text);
  font-weight: 600;
  box-shadow: var(--ui-shadow);
}
.code-input {
  font-size: 1.2rem;
  letter-spacing: 0.2em;
  text-align: center;
  font-family: var(--mono);
}
.login-footer {
  margin-top: 20px;
  color: #fff;
  font-size: 0.85rem;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.5);
  text-align: center;
  white-space: pre-line;
}
</style>
