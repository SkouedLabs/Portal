<template>
  <div>
    <div class="page-title">
      <h1>Logs</h1>
      <div style="flex: 1"></div>
      <label class="check"><input v-model="live" type="checkbox" /> Auto-refresh (10 s)</label>
      <a class="btn" :href="`/api/admin/logs/export.csv?${query(false)}`"><i class="fa-solid fa-file-csv"></i> Export CSV</a>
      <p>Navigation (dashboards viewed, links opened), sign-ins and administration actions.</p>
    </div>

    <div class="card-ui filters">
      <div class="field">
        <label>Category</label>
        <select v-model="f.category" class="input sm" @change="reset">
          <option value="">All</option>
          <option value="navigation">Navigation</option>
          <option value="auth">Authentication</option>
          <option value="admin">Administration</option>
        </select>
      </div>
      <div class="field">
        <label>Event</label>
        <select v-model="f.event" class="input sm" @change="reset">
          <option value="">All</option>
          <option v-for="(v, k) in EVENTS" :key="k" :value="k">{{ v.label }}</option>
        </select>
      </div>
      <div class="field"><label>User</label><input v-model="f.user" class="input sm" @input="debounced" /></div>
      <div class="field"><label>Search</label><input v-model="f.q" class="input sm" placeholder="URL, label, dashboard, IP…" @input="debounced" /></div>
      <div class="field"><label>From</label><input v-model="f.since" type="datetime-local" class="input sm" @change="reset" /></div>
      <div class="field"><label>To</label><input v-model="f.until" type="datetime-local" class="input sm" @change="reset" /></div>
      <div class="field end"><button class="btn sm ghost" @click="clear"><i class="fa-solid fa-filter-circle-xmark"></i> Clear</button></div>
    </div>

    <div class="table-wrap" style="margin-top: 16px">
      <table class="table">
        <thead>
          <tr><th>Date</th><th>Event</th><th>User</th><th>Details</th><th>IP</th></tr>
        </thead>
        <tbody>
          <tr v-for="e in items" :key="e.id">
            <td class="nowrap small">{{ fmt(e.ts) }}</td>
            <td><span class="badge" :class="ev(e).cls"><i :class="ev(e).icon"></i> {{ ev(e).label }}</span></td>
            <td>
              <a v-if="e.username" href="#" @click.prevent="filterUser(e.username)">{{ e.username }}</a>
              <span v-else class="muted">—</span>
            </td>
            <td class="detail">
              <span v-if="e.dashboard_title" class="badge">{{ e.dashboard_title }}</span>
              <strong v-if="e.label">{{ e.label }}</strong>
              <a v-if="e.target && /^https?:/.test(e.target)" :href="e.target" target="_blank" rel="noopener noreferrer" class="target">{{ e.target }}</a>
              <span v-else-if="e.target" class="target muted">{{ e.target }}</span>
              <span v-if="e.details" class="muted small mono">{{ detailText(e.details) }}</span>
            </td>
            <td class="mono small nowrap" :title="e.user_agent">{{ e.ip }}</td>
          </tr>
          <tr v-if="!items.length"><td colspan="5" class="empty">{{ loading ? 'Loading…' : 'No events.' }}</td></tr>
        </tbody>
      </table>
    </div>

    <div class="pager">
      <span class="muted">{{ total.toLocaleString() }} event(s)</span>
      <div style="flex: 1"></div>
      <select v-model.number="pageSize" class="input sm" style="width: auto" @change="reset">
        <option :value="25">25</option><option :value="50">50</option><option :value="100">100</option><option :value="250">250</option>
      </select>
      <button class="btn sm" :disabled="page <= 1" @click="go(page - 1)"><i class="fa-solid fa-chevron-left"></i></button>
      <span class="small">Page {{ page }} / {{ pages }}</span>
      <button class="btn sm" :disabled="page >= pages" @click="go(page + 1)"><i class="fa-solid fa-chevron-right"></i></button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../../api'
import { notify } from '../../store'

const EVENTS = {
  view_dashboard: { label: 'Dashboard viewed', icon: 'fa-solid fa-eye', cls: 'brand' },
  click_link: { label: 'Link opened', icon: 'fa-solid fa-arrow-pointer', cls: 'brand' },
  login: { label: 'Sign-in', icon: 'fa-solid fa-right-to-bracket', cls: 'ok' },
  logout: { label: 'Sign-out', icon: 'fa-solid fa-right-from-bracket', cls: '' },
  login_failed: { label: 'Failed sign-in', icon: 'fa-solid fa-user-lock', cls: 'danger' },
  login_throttled: { label: 'Sign-in throttled', icon: 'fa-solid fa-ban', cls: 'danger' },
  ldap_error: { label: 'LDAP error', icon: 'fa-solid fa-triangle-exclamation', cls: 'danger' },
  dashboard_edit: { label: 'Dashboard edited', icon: 'fa-solid fa-pen', cls: 'warn' },
  dashboard_create: { label: 'Dashboard created', icon: 'fa-solid fa-plus', cls: 'warn' },
  dashboard_update: { label: 'Dashboard updated', icon: 'fa-solid fa-pen', cls: 'warn' },
  dashboard_delete: { label: 'Dashboard deleted', icon: 'fa-solid fa-trash', cls: 'warn' },
  dashboard_access: { label: 'Permissions changed', icon: 'fa-solid fa-user-shield', cls: 'warn' },
  settings_update: { label: 'Settings changed', icon: 'fa-solid fa-gear', cls: 'warn' },
  user_create: { label: 'User created', icon: 'fa-solid fa-user-plus', cls: 'warn' },
  user_update: { label: 'User updated', icon: 'fa-solid fa-user-pen', cls: 'warn' },
  user_delete: { label: 'User deleted', icon: 'fa-solid fa-user-minus', cls: 'warn' },
  user_sessions_revoked: { label: 'Sessions revoked', icon: 'fa-solid fa-user-slash', cls: 'warn' },
  group_create: { label: 'Group created', icon: 'fa-solid fa-users', cls: 'warn' },
  group_update: { label: 'Group updated', icon: 'fa-solid fa-users', cls: 'warn' },
  group_delete: { label: 'Group deleted', icon: 'fa-solid fa-users-slash', cls: 'warn' },
  ldap_sync: { label: 'LDAP sync', icon: 'fa-solid fa-arrows-rotate', cls: 'warn' },
  upload: { label: 'File uploaded', icon: 'fa-solid fa-upload', cls: 'warn' },
  mfa_failed: { label: 'Wrong 2FA code', icon: 'fa-solid fa-shield-halved', cls: 'danger' },
  mfa_enrolled: { label: '2FA method added', icon: 'fa-solid fa-shield-halved', cls: 'ok' },
  mfa_removed: { label: '2FA method removed', icon: 'fa-solid fa-shield-halved', cls: 'warn' },
  mfa_recovery_used: { label: 'Recovery code used', icon: 'fa-solid fa-life-ring', cls: 'warn' },
  mfa_recovery_regenerated: { label: 'Recovery codes renewed', icon: 'fa-solid fa-life-ring', cls: '' },
  mfa_reset: { label: '2FA reset by admin', icon: 'fa-solid fa-shield-halved', cls: 'warn' },
  ca_add: { label: 'CA added', icon: 'fa-solid fa-certificate', cls: 'warn' },
  ca_delete: { label: 'CA removed', icon: 'fa-solid fa-certificate', cls: 'warn' },
}

const f = reactive({ category: '', event: '', user: '', q: '', since: '', until: '' })
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const loading = ref(false)
const live = ref(false)
const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const ev = (e) => EVENTS[e.event] || { label: e.event, icon: 'fa-solid fa-circle', cls: '' }
const fmt = (iso) => new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'medium' })
const detailText = (d) =>
  Object.entries(d)
    .map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v) : v}`)
    .join(' ')
    .slice(0, 160)

function query(withPage = true) {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(f)) {
    if (!v) continue
    p.set(k, k === 'since' || k === 'until' ? new Date(v).toISOString() : v)
  }
  if (withPage) {
    p.set('page', page.value)
    p.set('page_size', pageSize.value)
  }
  return p.toString()
}

async function load() {
  loading.value = true
  try {
    const r = await api.get(`/api/admin/logs?${query()}`)
    items.value = r.items
    total.value = r.total
  } catch (e) {
    notify(e.message, 'error')
  } finally {
    loading.value = false
  }
}
function reset() {
  page.value = 1
  load()
}
let t
function debounced() {
  clearTimeout(t)
  t = setTimeout(reset, 300)
}
function go(p) {
  page.value = p
  load()
}
function clear() {
  Object.assign(f, { category: '', event: '', user: '', q: '', since: '', until: '' })
  reset()
}
function filterUser(u) {
  f.user = u
  reset()
}

let timer
watch(live, (v) => {
  clearInterval(timer)
  if (v) timer = setInterval(load, 10000)
})
onMounted(load)
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.filters {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 0 12px;
  padding-bottom: 6px;
}
.end {
  justify-content: flex-end;
}
.nowrap {
  white-space: nowrap;
}
.small {
  font-size: 0.8rem;
}
.detail {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
  align-items: center;
  max-width: 560px;
}
.target {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 340px;
  font-size: 0.85rem;
}
.pager {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  flex-wrap: wrap;
}
</style>
