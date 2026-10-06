<template>
  <div>
    <div class="page-title">
      <h1>Users</h1>
      <div style="flex: 1"></div>
      <button v-if="externalSources.length" class="btn" @click="openDeclare"><i class="fa-solid fa-circle-plus"></i> Declare {{ externalSources.map((s) => s.toUpperCase()).join(' / ') }} account</button>
      <button class="btn primary" @click="openCreate"><i class="fa-solid fa-user-plus"></i> Local account</button>
      <p>
        LDAP and OIDC accounts are created automatically on first sign-in. Declare one beforehand to grant it dashboards right away.
        <strong>Dashboards</strong> shows what a user can really view or edit, and why.
      </p>
    </div>

    <div class="toolbar">
      <input v-model="q" class="input" placeholder="Search (name, username, email)…" style="max-width: 360px" @input="debouncedLoad" />
      <select v-model="source" class="input" style="width: auto">
        <option value="">All sources</option>
        <option value="local">Local</option>
        <option value="ldap">LDAP</option>
        <option value="oidc">OIDC</option>
      </select>
    </div>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr><th>User</th><th>Source</th><th>Groups</th><th>Role</th><th>Last sign-in</th><th class="actions"></th></tr>
        </thead>
        <tbody>
          <tr v-for="u in filtered" :key="u.id" :class="{ inactive: !u.is_active }">
            <td>
              <strong>{{ u.display_name || u.username }}</strong>
              <div class="muted small">{{ u.username }}<template v-if="u.email"> · {{ u.email }}</template></div>
            </td>
            <td><span class="badge" :class="`src-${u.source}`">{{ u.source }}</span></td>
            <td class="groups">
              <span v-for="g in u.groups.slice(0, 4)" :key="g.id" class="badge" :class="{ brand: g.is_admin }">{{ g.name }}</span>
              <span v-if="u.groups.length > 4" class="badge">+{{ u.groups.length - 4 }}</span>
            </td>
            <td>
              <span v-if="u.is_superadmin" class="badge danger"><i class="fa-solid fa-crown"></i> Super-admin</span>
              <span v-else-if="u.is_admin" class="badge brand"><i class="fa-solid fa-shield-halved"></i> Admin</span>
              <span v-if="!u.is_active" class="badge warn">Disabled</span>
              <span v-if="u.mfa_factors" class="badge ok" :title="`${u.mfa_factors} two-step method(s)`"><i class="fa-solid fa-shield-halved"></i> MFA</span>
            </td>
            <td class="muted small">
              <span v-if="u.pending" class="badge warn" title="Declared by an administrator, linked at the first sign-in">not signed in yet</span>
              <template v-else>{{ fmt(u.last_login_at) }}</template>
            </td>
            <td class="actions">
              <button class="btn ghost icon sm" title="Dashboards" @click="rightsFor = u"><i class="fa-solid fa-table-columns"></i></button>
              <button class="btn ghost icon sm" title="Edit" @click="openEdit(u)"><i class="fa-solid fa-pen"></i></button>
              <button v-if="u.mfa_factors" class="btn ghost icon sm" title="Reset two-step verification" @click="resetMfa(u)"><i class="fa-solid fa-shield-halved"></i></button>
              <button class="btn ghost icon sm" title="Sign out everywhere" @click="revoke(u)"><i class="fa-solid fa-right-from-bracket"></i></button>
              <button class="btn ghost icon sm danger" title="Delete" :disabled="u.id === state.me.id" @click="remove(u)"><i class="fa-solid fa-trash"></i></button>
            </td>
          </tr>
          <tr v-if="!filtered.length"><td colspan="6" class="empty">No users.</td></tr>
        </tbody>
      </table>
    </div>

    <Modal v-if="declaring" title="Declare a directory account" @close="declaring = null">
      <p class="muted" style="margin-top: 0">The account is linked to the person at their first sign-in, with the rights granted in the meantime.</p>
      <div class="row">
        <div class="field">
          <label>Source</label>
          <select v-model="declaring.source" class="input">
            <option v-for="s in externalSources" :key="s" :value="s">{{ s.toUpperCase() }}</option>
          </select>
        </div>
        <div class="field">
          <label>Username</label>
          <input v-model="declaring.username" class="input" autocomplete="off" autofocus />
        </div>
      </div>
      <span class="hint">
        <template v-if="declaring.source === 'ldap'">The value of the LDAP username attribute (e.g. uid or sAMAccountName).</template>
        <template v-else>The value of the OIDC username claim configured in Authentication. Use a claim users cannot change themselves.</template>
      </span>
      <div class="row">
        <div class="field"><label>Display name</label><input v-model="declaring.display_name" class="input" /></div>
        <div class="field"><label>Email</label><input v-model="declaring.email" class="input" type="email" /></div>
      </div>
      <template #footer>
        <button class="btn" @click="declaring = null">Cancel</button>
        <button class="btn primary" :disabled="!declaring.username.trim()" @click="declare">Declare</button>
      </template>
    </Modal>

    <PrincipalAccessModal
      v-if="rightsFor"
      kind="users"
      :principal="{ id: rightsFor.id, label: rightsFor.display_name || rightsFor.username, source: rightsFor.source, is_admin: rightsFor.is_admin }"
      @close="rightsFor = null"
    />

    <Modal v-if="editing" :title="editing.id ? `Edit ${editing.username}` : 'New local account'" @close="editing = null">
      <template v-if="!editing.id">
        <div class="field">
          <label>Username</label>
          <input v-model="editing.username" class="input" autocomplete="off" />
        </div>
      </template>
      <div class="row">
        <div class="field"><label>Display name</label><input v-model="editing.display_name" class="input" /></div>
        <div class="field"><label>Email</label><input v-model="editing.email" class="input" type="email" /></div>
      </div>
      <div v-if="editing.source === 'local'" class="field">
        <label>{{ editing.id ? 'New password (leave empty to keep)' : 'Password' }}</label>
        <input v-model="editing.password" class="input" type="password" autocomplete="new-password" minlength="12" />
        <span class="hint">At least 12 characters. Hashed with Argon2id.</span>
      </div>
      <div class="field">
        <label>Local groups</label>
        <div class="checks">
          <label v-for="g in localGroups" :key="g.id" class="check">
            <input v-model="editing.local_group_ids" type="checkbox" :value="g.id" /> {{ g.name }}
            <span v-if="g.is_admin" class="badge brand">admin</span>
          </label>
          <span v-if="!localGroups.length" class="hint">No local groups. LDAP/OIDC groups are synchronised automatically.</span>
        </div>
      </div>
      <div v-if="editing.id && editing.externalGroups.length" class="field">
        <label>Synchronised groups ({{ editing.source }})</label>
        <div><span v-for="g in editing.externalGroups" :key="g.id" class="badge" style="margin: 0 4px 4px 0">{{ g.name }}</span></div>
      </div>
      <div class="row">
        <label class="switch"><input v-model="editing.is_active" type="checkbox" /><span class="track"></span> Account active</label>
        <label v-if="state.me.is_superadmin" class="switch" :title="'Permanent administrator access, independent of groups'">
          <input v-model="editing.is_superadmin" type="checkbox" /><span class="track"></span> Super-admin
        </label>
      </div>
      <template #footer>
        <button class="btn" @click="editing = null">Cancel</button>
        <button class="btn primary" @click="saveUser"><i class="fa-solid fa-floppy-disk"></i> Save</button>
      </template>
    </Modal>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../../api'
import Modal from '../../components/Modal.vue'
import PrincipalAccessModal from '../../components/PrincipalAccessModal.vue'
import { notify, state } from '../../store'

const users = ref([])
const groups = ref([])
const q = ref('')
const source = ref('')
const editing = ref(null)
const declaring = ref(null)
const rightsFor = ref(null)
const externalSources = computed(() => ['ldap', 'oidc'].filter((s) => state.config?.login?.[s]))

const filtered = computed(() => users.value.filter((u) => !source.value || u.source === source.value))
const localGroups = computed(() => groups.value.filter((g) => g.source === 'local'))
const fmt = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' }) : 'never')

async function load() {
  try {
    users.value = await api.get(`/api/admin/users?q=${encodeURIComponent(q.value)}`)
  } catch (e) {
    notify(e.message, 'error')
  }
}
let t
function debouncedLoad() {
  clearTimeout(t)
  t = setTimeout(load, 250)
}
onMounted(async () => {
  await load()
  groups.value = await api.get('/api/admin/groups').catch(() => [])
})

function openCreate() {
  editing.value = { source: 'local', username: '', display_name: '', email: '', password: '', is_active: true, is_superadmin: false, local_group_ids: [], externalGroups: [] }
}
function openEdit(u) {
  editing.value = {
    ...u,
    password: '',
    local_group_ids: u.groups.filter((g) => g.source === 'local').map((g) => g.id),
    externalGroups: u.groups.filter((g) => g.source !== 'local'),
  }
}

function openDeclare() {
  declaring.value = { source: externalSources.value[0], username: '', display_name: '', email: '' }
}
async function declare() {
  try {
    const u = await api.post('/api/admin/users/external', declaring.value)
    declaring.value = null
    await load()
    rightsFor.value = u
  } catch (e) {
    notify(e.message, 'error')
  }
}

async function saveUser() {
  const e = editing.value
  try {
    if (!e.id) {
      await api.post('/api/admin/users', {
        username: e.username, password: e.password, display_name: e.display_name, email: e.email,
        is_superadmin: e.is_superadmin, group_ids: e.local_group_ids,
      })
    } else {
      const payload = {
        display_name: e.display_name, email: e.email, is_active: e.is_active, local_group_ids: e.local_group_ids,
      }
      const orig = users.value.find((u) => u.id === e.id)
      if (orig.is_superadmin !== e.is_superadmin) payload.is_superadmin = e.is_superadmin
      if (e.password) payload.password = e.password
      await api.put(`/api/admin/users/${e.id}`, payload)
    }
    notify('User saved')
    editing.value = null
    await load()
  } catch (err) {
    notify(err.message, 'error')
  }
}

async function resetMfa(u) {
  if (!confirm(`Remove every two-step method and recovery code of ${u.username}? They will be asked to set it up again if it is required.`)) return
  try {
    await api.post(`/api/admin/users/${u.id}/mfa/reset`)
    notify(`Two-step verification reset for ${u.username}`)
    await load()
  } catch (e) {
    notify(e.message, 'error')
  }
}

async function revoke(u) {
  try {
    await api.post(`/api/admin/users/${u.id}/logout`)
    notify(`Sessions of ${u.username} closed`)
  } catch (e) {
    notify(e.message, 'error')
  }
}
async function remove(u) {
  if (!confirm(`Delete ${u.username}? An external account is recreated on its next sign-in — disable it instead to block access.`)) return
  try {
    await api.del(`/api/admin/users/${u.id}`)
    notify('User deleted')
    await load()
  } catch (e) {
    notify(e.message, 'error')
  }
}
</script>

<style scoped>
.small {
  font-size: 0.8rem;
}
.groups {
  max-width: 320px;
}
.groups .badge {
  margin: 2px 4px 2px 0;
}
tr.inactive td {
  opacity: 0.6;
}
.checks {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
}
.row .switch {
  margin: 4px 18px 4px 0;
}
</style>
