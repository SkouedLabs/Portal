<template>
  <div>
    <div class="page-title">
      <h1>Certificates</h1>
      <div style="flex: 1"></div>
      <button class="btn primary" @click="openAdd"><i class="fa-solid fa-plus"></i> Add a CA</button>
      <p>
        Root or intermediate certificate authorities trusted in addition to the system store — for example your internal PKI.
        They are used for every outgoing TLS connection: LDAPS / StartTLS, the OpenID Connect provider and the status checks.
      </p>
    </div>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr><th>Authority</th><th>Valid until</th><th>SHA-256 fingerprint</th><th>Added</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="c in cas" :key="c.id">
            <td>
              <strong>{{ c.name }}</strong>
              <span v-if="c.self_signed" class="badge brand">root</span>
              <span v-else class="badge">intermediate</span>
              <div class="muted small mono dn" :title="c.subject">{{ c.subject }}</div>
              <div v-if="!c.self_signed" class="muted small mono dn" :title="c.issuer">issued by {{ c.issuer }}</div>
            </td>
            <td>
              <span :class="expiryClass(c)">{{ fmtDate(c.not_after) }}</span>
              <div class="muted small">{{ expiryText(c) }}</div>
            </td>
            <td class="mono small fp" :title="c.fingerprint_sha256">{{ c.fingerprint_sha256 }}</td>
            <td class="muted small">{{ fmtDate(c.created_at) }}<br />{{ c.created_by }}</td>
            <td class="actions"><button class="btn ghost icon sm danger" title="Remove" @click="remove(c)"><i class="fa-solid fa-trash"></i></button></td>
          </tr>
          <tr v-if="!cas.length"><td colspan="5" class="empty">No custom CA: only the system trust store is used.</td></tr>
        </tbody>
      </table>
    </div>

    <div class="card-ui" style="margin-top: 18px">
      <h2><i class="fa-solid fa-plug-circle-check"></i> Test a TLS connection</h2>
      <p class="muted small">Checks that a server's certificate is trusted with the current store (system + the CAs above).</p>
      <div class="toolbar">
        <input v-model="testUrl" class="input" style="max-width: 420px" placeholder="https://intranet.corp.local or ldaps://dc01.corp.local" @keydown.enter="test" />
        <button class="btn" :disabled="!testUrl || testing" @click="test">
          <i :class="testing ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-play'"></i> Test
        </button>
      </div>
      <div v-if="result" class="alert" :class="result.ok ? 'ok' : 'error'">
        <template v-if="result.ok">
          Trusted — {{ result.host }}:{{ result.port }}, {{ result.protocol }}, {{ result.cipher }}<br />
          Subject: {{ result.subject?.commonName }} · Issuer: {{ result.issuer?.commonName }} · Expires: {{ result.not_after }}
        </template>
        <template v-else>{{ result.host }}:{{ result.port }} — {{ result.error }}</template>
      </div>
    </div>

    <Modal v-if="adding" title="Add a certificate authority" @close="adding = null">
      <div class="field">
        <label>Name (optional)</label>
        <input v-model="adding.name" class="input" placeholder="Defaults to the certificate common name" />
      </div>
      <div class="field">
        <label>Certificate file</label>
        <input type="file" accept=".pem,.crt,.cer,.der,.ca-bundle" class="input" @change="adding.file = $event.target.files[0] || null" />
        <span class="hint">PEM (one or several certificates) or DER.</span>
      </div>
      <div class="field">
        <label>Or paste PEM</label>
        <textarea v-model="adding.pem" class="input mono" rows="8" placeholder="-----BEGIN CERTIFICATE-----"></textarea>
      </div>
      <template #footer>
        <button class="btn" @click="adding = null">Cancel</button>
        <button class="btn primary" :disabled="busy || (!adding.file && !adding.pem.trim())" @click="save">
          <i :class="busy ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-floppy-disk'"></i> Add
        </button>
      </template>
    </Modal>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../../api'
import Modal from '../../components/Modal.vue'
import { notify } from '../../store'

const cas = ref([])
const adding = ref(null)
const busy = ref(false)
const testUrl = ref('')
const testing = ref(false)
const result = ref(null)

const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { dateStyle: 'medium' }) : '')
const daysLeft = (c) => Math.floor((new Date(c.not_after) - Date.now()) / 86400000)
const expiryClass = (c) => (c.expired ? 'bad' : daysLeft(c) < 60 ? 'warn' : '')
const expiryText = (c) => (c.expired ? 'expired' : `${daysLeft(c)} day(s) left`)

async function load() {
  try {
    cas.value = await api.get('/api/admin/cas')
  } catch (e) {
    notify(e.message, 'error')
  }
}
onMounted(load)

function openAdd() {
  adding.value = { name: '', pem: '', file: null }
}

async function save() {
  busy.value = true
  try {
    const fd = new FormData()
    fd.append('name', adding.value.name)
    if (adding.value.file) fd.append('file', adding.value.file)
    else fd.append('pem', adding.value.pem)
    const r = await api.post('/api/admin/cas', fd)
    notify(`${r.added.length} CA(s) added${r.skipped.length ? ` — skipped: ${r.skipped.join('; ')}` : ''}`)
    adding.value = null
    await load()
  } catch (e) {
    notify(e.message, 'error')
  } finally {
    busy.value = false
  }
}

async function remove(c) {
  if (!confirm(`Stop trusting "${c.name}"? Connections to servers signed by this CA will fail.`)) return
  try {
    await api.del(`/api/admin/cas/${c.id}`)
    notify('CA removed')
    await load()
  } catch (e) {
    notify(e.message, 'error')
  }
}

async function test() {
  testing.value = true
  result.value = null
  try {
    result.value = await api.post('/api/admin/cas/test', { url: testUrl.value.trim() })
  } catch (e) {
    result.value = { ok: false, error: e.message }
  } finally {
    testing.value = false
  }
}
</script>

<style scoped>
.small {
  font-size: 0.78rem;
}
.dn {
  max-width: 420px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fp {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bad {
  color: var(--ui-danger);
  font-weight: 600;
}
.warn {
  color: var(--ui-warning);
  font-weight: 600;
}
.badge {
  margin-left: 6px;
}
</style>
