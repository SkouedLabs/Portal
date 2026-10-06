<template>
  <div class="account-page">
    <header class="account-bar">
      <router-link to="/" class="btn ghost sm"><i class="fa-solid fa-arrow-left"></i> Back to portal</router-link>
      <div style="flex: 1"></div>
      <UserMenu />
    </header>

    <main class="account-main">
      <div class="page-title">
        <h1>Security</h1>
        <p>{{ state.me?.display_name }} · {{ state.me?.username }} ({{ state.me?.source }})</p>
      </div>

      <div v-if="state.me?.source === 'oidc'" class="card-ui">
        <p class="muted">Your account signs in through single sign-on: two-step verification is managed by your identity provider.</p>
      </div>

      <template v-else-if="info">
        <div v-if="!info.methods.length" class="card-ui">
          <p class="muted">Two-step verification is disabled by the administrator.</p>
        </div>

        <template v-else>
          <div class="card-ui">
            <h2>
              <i class="fa-solid fa-shield-halved"></i> Two-step verification
              <span v-if="info.factors.length" class="badge ok">On</span>
              <span v-else class="badge warn">Off</span>
              <span v-if="info.enforced" class="badge brand">Required</span>
            </h2>
            <div v-if="info.factors.length" class="table-wrap">
              <table class="table">
                <thead><tr><th>Method</th><th>Added</th><th>Last used</th><th></th></tr></thead>
                <tbody>
                  <tr v-for="f in info.factors" :key="f.id">
                    <td>
                      <i :class="f.kind === 'totp' ? 'fa-solid fa-mobile-screen-button' : 'fa-solid fa-fingerprint'" class="kind"></i>
                      <strong>{{ f.name }}</strong>
                      <span class="muted small"> · {{ f.kind === 'totp' ? 'Authenticator app' : 'Security key' }}</span>
                    </td>
                    <td class="muted small">{{ fmt(f.created_at) }}</td>
                    <td class="muted small">{{ f.last_used_at ? fmt(f.last_used_at) : 'never' }}</td>
                    <td class="actions"><button class="btn ghost icon sm danger" title="Remove" @click="remove(f)"><i class="fa-solid fa-trash"></i></button></td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p v-else class="muted">Protect your account with a second factor in addition to your password.</p>

            <div style="margin-top: 16px">
              <button v-if="!adding" class="btn primary" @click="adding = true"><i class="fa-solid fa-plus"></i> Add a method</button>
              <div v-else class="adder">
                <MfaSetup :methods="info.methods" @finished="added" />
                <button class="btn ghost sm" style="margin-top: 10px" @click="adding = false">Cancel</button>
              </div>
            </div>
          </div>

          <div v-if="info.factors.length" class="card-ui">
            <h2><i class="fa-solid fa-life-ring"></i> Recovery codes</h2>
            <p class="muted">
              {{ info.recovery_remaining }} unused code(s) left. Use one if you lose your authenticator.
              Generating new codes invalidates the previous ones.
            </p>
            <div v-if="newCodes" class="codes-box">
              <ol class="codes mono"><li v-for="c in newCodes" :key="c">{{ c }}</li></ol>
              <button class="btn sm" @click="copy"><i class="fa-regular fa-copy"></i> Copy</button>
            </div>
            <button v-else class="btn" @click="regenerate"><i class="fa-solid fa-arrows-rotate"></i> Generate new codes</button>
          </div>
        </template>
      </template>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'
import MfaSetup from '../components/MfaSetup.vue'
import UserMenu from '../components/UserMenu.vue'
import { notify, state } from '../store'

const info = ref(null)
const adding = ref(false)
const newCodes = ref(null)
const fmt = (iso) => new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })

async function load() {
  if (state.me?.source === 'oidc') return
  try {
    info.value = await api.get('/api/account/mfa')
  } catch (e) {
    notify(e.message, 'error')
  }
}
onMounted(load)

async function added() {
  adding.value = false
  notify('Authentication method added')
  await load()
}
async function remove(f) {
  if (!confirm(`Remove "${f.name}"?`)) return
  try {
    await api.del(`/api/account/mfa/factors/${f.id}`)
    notify('Method removed')
    await load()
  } catch (e) {
    notify(e.message, 'error')
  }
}
async function regenerate() {
  if (!confirm('Generate new recovery codes? The current ones will stop working.')) return
  try {
    newCodes.value = (await api.post('/api/account/mfa/recovery-codes')).recovery_codes
    await load()
  } catch (e) {
    notify(e.message, 'error')
  }
}
function copy() {
  navigator.clipboard?.writeText(newCodes.value.join('\n')).then(() => notify('Copied'))
}
</script>

<style scoped>
.account-bar {
  display: flex;
  align-items: center;
  padding: 10px 24px;
  background: var(--ui-surface);
  border-bottom: 1px solid var(--ui-border);
}
.account-bar :deep(.avatar-btn) {
  background: var(--ui-surface-2);
  color: var(--ui-text);
}
.account-bar :deep(.avatar) {
  background: var(--brand);
  color: #fff;
}
.account-main {
  max-width: 820px;
  margin: 0 auto;
  padding: 28px 16px 48px;
}
.kind {
  color: var(--brand);
  margin-right: 8px;
  width: 16px;
}
.small {
  font-size: 0.82rem;
}
.adder {
  border: 1px solid var(--ui-border);
  border-radius: 10px;
  padding: 16px;
}
.codes {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px 20px;
  padding: 14px 14px 14px 34px;
  background: var(--ui-surface-2);
  border: 1px solid var(--ui-border);
  border-radius: 8px;
}
@media (max-width: 640px) {
  .account-bar {
    padding: 8px 16px;
  }
}
</style>
