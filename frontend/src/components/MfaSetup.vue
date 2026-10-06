<template>
  <div class="mfa-setup">
    <!-- Recovery codes, shown once after the first enrolment -->
    <div v-if="codes" class="codes-box">
      <h3><i class="fa-solid fa-key"></i> Save your recovery codes</h3>
      <p class="muted">Each code works once if you lose access to your authenticator. They will not be shown again.</p>
      <ol class="codes mono">
        <li v-for="c in codes" :key="c">{{ c }}</li>
      </ol>
      <div class="row-btns">
        <button class="btn sm" @click="copyCodes"><i class="fa-regular fa-copy"></i> Copy</button>
        <button class="btn sm" @click="downloadCodes"><i class="fa-solid fa-download"></i> Download</button>
        <div style="flex: 1"></div>
        <button class="btn primary" @click="done"><i class="fa-solid fa-check"></i> I saved them</button>
      </div>
    </div>

    <!-- Method choice -->
    <div v-else-if="!step" class="choices">
      <button v-if="methods.includes('totp')" class="choice" @click="startTotp">
        <i class="fa-solid fa-mobile-screen-button"></i>
        <span><strong>Authenticator app</strong><small>6-digit codes (FreeOTP, Aegis, Google / Microsoft Authenticator…)</small></span>
      </button>
      <button v-if="methods.includes('webauthn')" class="choice" :disabled="!webauthnOk" @click="startWebauthn">
        <i class="fa-solid fa-fingerprint"></i>
        <span>
          <strong>Security key or passkey</strong>
          <small>{{ webauthnOk ? 'YubiKey, Windows Hello, Touch ID, phone…' : 'Not available: requires HTTPS and a compatible browser' }}</small>
        </span>
      </button>
    </div>

    <!-- TOTP -->
    <div v-else-if="step === 'totp' && totp" class="totp">
      <img :src="totp.qr" alt="QR code to scan with your authenticator app" class="qr" />
      <div class="totp-side">
        <p>Scan the QR code with your authenticator app, then type the 6-digit code it shows.</p>
        <details>
          <summary class="muted">Can't scan? Enter the key manually</summary>
          <code class="secret">{{ totp.secret.match(/.{1,4}/g).join(' ') }}</code>
        </details>
        <div class="field" style="margin-top: 12px">
          <label>Name (optional)</label>
          <input v-model="name" class="input sm" placeholder="e.g. My phone" />
        </div>
        <div class="field">
          <label>Code</label>
          <input v-model="code" class="input code-input" inputmode="numeric" autocomplete="one-time-code" maxlength="7" placeholder="123456" @keydown.enter="finishTotp" />
        </div>
        <div class="row-btns">
          <button class="btn" @click="reset">Back</button>
          <button class="btn primary" :disabled="busy || code.replace(/\D/g, '').length !== 6" @click="finishTotp">
            <i :class="busy ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-check'"></i> Verify
          </button>
        </div>
      </div>
    </div>

    <!-- WebAuthn -->
    <div v-else-if="step === 'webauthn'" class="wa">
      <i class="fa-solid fa-fingerprint big"></i>
      <div class="field">
        <label>Name (optional)</label>
        <input v-model="name" class="input sm" placeholder="e.g. YubiKey 5" />
      </div>
      <div class="row-btns">
        <button class="btn" @click="reset">Back</button>
        <button class="btn primary" :disabled="busy" @click="finishWebauthn">
          <i :class="busy ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-fingerprint'"></i> Register the key
        </button>
      </div>
    </div>

    <div v-if="error" class="alert error" style="margin-top: 12px">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../api'
import { createCredential, webauthnSupported } from '../webauthn'

// enrolToken: forced enrolment at sign-in (no session yet)
const props = defineProps({ methods: { type: Array, default: () => ['totp', 'webauthn'] }, enrolToken: { type: String, default: '' } })
const emit = defineEmits(['enrolled', 'finished'])

const step = ref('')
const totp = ref(null)
const code = ref('')
const name = ref('')
const busy = ref(false)
const error = ref('')
const codes = ref(null)
const result = ref(null)
const webauthnOk = webauthnSupported()

const opts = () => (props.enrolToken ? { headers: { 'X-MFA-Token': props.enrolToken } } : {})

function reset() {
  step.value = ''
  totp.value = null
  code.value = ''
  error.value = ''
}

async function run(fn) {
  busy.value = true
  error.value = ''
  try {
    await fn()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

function enrolled(r) {
  result.value = r
  emit('enrolled', r)
  if (r.recovery_codes) codes.value = r.recovery_codes
  else done()
}

function done() {
  emit('finished', result.value)
  codes.value = null
  reset()
}

const startTotp = () =>
  run(async () => {
    totp.value = await api.post('/api/account/mfa/totp/begin', {}, opts())
    step.value = 'totp'
  })

const finishTotp = () =>
  run(async () => {
    const r = await api.post(
      '/api/account/mfa/totp/finish',
      { setup_token: totp.value.setup_token, code: code.value, name: name.value },
      opts(),
    )
    enrolled(r)
  })

function startWebauthn() {
  step.value = 'webauthn'
}

const finishWebauthn = () =>
  run(async () => {
    const begin = await api.post('/api/account/mfa/webauthn/begin', {}, opts())
    const credential = await createCredential(begin.options)
    const r = await api.post(
      '/api/account/mfa/webauthn/finish',
      { registration_token: begin.registration_token, credential, name: name.value },
      opts(),
    )
    enrolled(r)
  })

function copyCodes() {
  navigator.clipboard?.writeText(codes.value.join('\n'))
}
function downloadCodes() {
  const blob = new Blob([`Recovery codes\n\n${codes.value.join('\n')}\n`], { type: 'text/plain' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'recovery-codes.txt'
  a.click()
  URL.revokeObjectURL(a.href)
}
</script>

<style scoped>
.choices {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.choice {
  display: flex;
  align-items: center;
  gap: 14px;
  text-align: left;
  padding: 14px 16px;
  border: 1px solid var(--ui-border);
  border-radius: 10px;
  background: var(--ui-surface);
  color: var(--ui-text);
  font: inherit;
  cursor: pointer;
}
.choice:hover:not(:disabled) {
  border-color: var(--brand);
}
.choice:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.choice > i {
  font-size: 1.5rem;
  color: var(--brand);
  width: 28px;
  text-align: center;
}
.choice span {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.choice small {
  color: var(--ui-muted);
  font-size: 0.8rem;
}
.totp {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
}
.qr {
  width: 190px;
  height: 190px;
  border-radius: 8px;
  border: 1px solid var(--ui-border);
  background: #fff;
}
.totp-side {
  flex: 1 1 220px;
  min-width: 0;
}
.totp-side p {
  margin-top: 0;
}
.secret {
  display: block;
  margin-top: 8px;
  font-size: 0.9rem;
  word-break: break-all;
  user-select: all;
}
.code-input {
  font-size: 1.3rem;
  letter-spacing: 0.3em;
  text-align: center;
  font-family: var(--mono);
}
.row-btns {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.wa {
  text-align: center;
}
.wa .row-btns {
  justify-content: center;
}
.big {
  font-size: 2.6rem;
  color: var(--brand);
  margin-bottom: 14px;
}
.codes-box h3 {
  font-size: 1rem;
}
.codes {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px 20px;
  padding: 14px 14px 14px 34px;
  background: var(--ui-surface-2);
  border: 1px solid var(--ui-border);
  border-radius: 8px;
  font-size: 0.95rem;
}
</style>
