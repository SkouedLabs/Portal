<template>
  <div>
    <div class="page-title">
      <h1>Groups</h1>
      <div style="flex: 1"></div>
      <button v-if="ldapEnabled" class="btn" :disabled="syncing" @click="sync">
        <i :class="syncing ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-arrows-rotate'"></i> Synchronise LDAP
      </button>
      <button v-if="externalSources.length" class="btn" @click="openDeclare"><i class="fa-solid fa-circle-plus"></i> Declare {{ externalSources.map((s) => s.toUpperCase()).join(' / ') }} group</button>
      <button class="btn primary" @click="creating = { name: '', description: '', is_admin: false }"><i class="fa-solid fa-plus"></i> Local group</button>
      <p>
        LDAP groups are synchronised at sign-in and with the button above; OIDC groups come from the configured claim.
        Turn on <strong>Administrator</strong> to give Portal-NG administrator rights to every member of a group.
        Use <strong>Dashboards</strong> to choose which dashboards a group can view or edit; a directory group can be declared before anyone from it signs in.
      </p>
    </div>

    <div class="toolbar">
      <input v-model="q" class="input" placeholder="Filter…" style="max-width: 300px" />
      <select v-model="source" class="input" style="width: auto">
        <option value="">All sources</option>
        <option value="local">Local</option>
        <option value="ldap">LDAP</option>
        <option value="oidc">OIDC</option>
      </select>
      <label class="check"><input v-model="adminOnly" type="checkbox" /> Administrators only</label>
    </div>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr><th>Group</th><th>Source</th><th>Members</th><th>Dashboards</th><th>Administrator</th><th>Synchronised</th><th class="actions"></th></tr>
        </thead>
        <tbody>
          <tr v-for="g in filtered" :key="g.id">
            <td>
              <strong>{{ g.name }}</strong>
              <div v-if="g.description" class="muted small">{{ g.description }}</div>
              <div v-if="g.source !== 'local'" class="muted small mono ext">{{ g.external_id }}</div>
            </td>
            <td><span class="badge" :class="`src-${g.source}`">{{ g.source }}</span></td>
            <td>{{ g.members }}</td>
            <td>
              <button class="btn sm" @click="rightsFor = g"><i class="fa-solid fa-table-columns"></i> {{ g.rules }} rule(s)</button>
            </td>
            <td>
              <label class="switch" :title="g.is_admin ? 'Remove admin rights' : 'Grant admin rights'">
                <input type="checkbox" :checked="g.is_admin" @change="toggleAdmin(g, $event)" /><span class="track"></span>
              </label>
            </td>
            <td class="muted small">
              <template v-if="g.synced_at">{{ new Date(g.synced_at).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' }) }}</template>
              <span v-else-if="g.source !== 'local'" class="badge warn" title="Declared by an administrator: no member has signed in or been synchronised yet">declared</span>
              <template v-else>—</template>
            </td>
            <td class="actions">
              <button class="btn ghost icon sm" title="Edit" @click="editing = { ...g }"><i class="fa-solid fa-pen"></i></button>
              <button class="btn ghost icon sm danger" title="Delete" @click="remove(g)"><i class="fa-solid fa-trash"></i></button>
            </td>
          </tr>
          <tr v-if="!filtered.length"><td colspan="7" class="empty">No groups.</td></tr>
        </tbody>
      </table>
    </div>

    <Modal v-if="creating" title="New local group" @close="creating = null">
      <div class="field"><label>Name</label><input v-model="creating.name" class="input" autofocus /></div>
      <div class="field"><label>Description</label><input v-model="creating.description" class="input" /></div>
      <label class="switch"><input v-model="creating.is_admin" type="checkbox" /><span class="track"></span> Portal-NG administrators</label>
      <template #footer>
        <button class="btn" @click="creating = null">Cancel</button>
        <button class="btn primary" :disabled="!creating.name" @click="create">Create</button>
      </template>
    </Modal>

    <Modal v-if="declaring" title="Declare a directory group" @close="declaring = null">
      <p class="muted" style="margin-top: 0">
        Declare an LDAP or OIDC group to grant it dashboards now. Its members get those rights when they sign in.
      </p>
      <div class="field">
        <label>Source</label>
        <select v-model="declaring.source" class="input">
          <option v-for="s in externalSources" :key="s" :value="s">{{ s.toUpperCase() }}</option>
        </select>
      </div>
      <div class="field">
        <label>{{ declaring.source === 'ldap' ? 'Distinguished name (DN)' : 'Value in the groups claim' }}</label>
        <input v-model="declaring.external_id" class="input mono" :placeholder="declaring.source === 'ldap' ? 'cn=staff,ou=groups,dc=example,dc=com' : '/portal/staff'" autofocus />
        <span class="hint">
          <template v-if="declaring.source === 'ldap'">The exact DN, as returned by the group search. A synchronisation lists them all.</template>
          <template v-else>Exactly as the identity provider sends it (case-sensitive), e.g. a Keycloak group path or an Entra ID group object id.</template>
        </span>
      </div>
      <div class="field">
        <label>Display name (optional)</label>
        <input v-model="declaring.name" class="input" />
        <span class="hint">Replaced by the directory name at the next synchronisation or sign-in.</span>
      </div>
      <template #footer>
        <button class="btn" @click="declaring = null">Cancel</button>
        <button class="btn primary" :disabled="!declaring.external_id.trim()" @click="declare">Declare</button>
      </template>
    </Modal>

    <PrincipalAccessModal
      v-if="rightsFor"
      kind="groups"
      :principal="{ id: rightsFor.id, label: rightsFor.name, source: rightsFor.source, is_admin: rightsFor.is_admin }"
      @saved="load"
      @close="rightsFor = null"
    />

    <Modal v-if="editing" :title="`Edit ${editing.name}`" @close="editing = null">
      <div class="field">
        <label>Name</label>
        <input v-model="editing.name" class="input" :disabled="editing.source !== 'local'" />
        <span v-if="editing.source !== 'local'" class="hint">The name comes from the directory ({{ editing.source }}).</span>
      </div>
      <div class="field"><label>Description</label><input v-model="editing.description" class="input" /></div>
      <template #footer>
        <button class="btn" @click="editing = null">Cancel</button>
        <button class="btn primary" @click="saveEdit">Save</button>
      </template>
    </Modal>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../../api'
import Modal from '../../components/Modal.vue'
import PrincipalAccessModal from '../../components/PrincipalAccessModal.vue'
import { loadMe, notify, state } from '../../store'

const groups = ref([])
const q = ref('')
const source = ref('')
const adminOnly = ref(false)
const creating = ref(null)
const editing = ref(null)
const syncing = ref(false)
const declaring = ref(null)
const rightsFor = ref(null)
const ldapEnabled = computed(() => state.config?.login?.ldap)
const externalSources = computed(() => ['ldap', 'oidc'].filter((s) => state.config?.login?.[s]))

const filtered = computed(() => {
  const term = q.value.toLowerCase()
  return groups.value.filter(
    (g) =>
      (!source.value || g.source === source.value) &&
      (!adminOnly.value || g.is_admin) &&
      (!term || `${g.name} ${g.external_id} ${g.description || ''}`.toLowerCase().includes(term)),
  )
})

async function load() {
  try {
    groups.value = await api.get('/api/admin/groups')
  } catch (e) {
    notify(e.message, 'error')
  }
}
onMounted(load)

async function toggleAdmin(g, ev) {
  const value = ev.target.checked
  if (value && !confirm(`Give Portal-NG administrator rights to the ${g.members} member(s) of "${g.name}"?`)) {
    ev.target.checked = false
    return
  }
  try {
    await api.put(`/api/admin/groups/${g.id}`, { is_admin: value })
    g.is_admin = value
    notify(value ? `"${g.name}" is now an administrator group` : `Admin rights removed from "${g.name}"`)
    await loadMe()
  } catch (e) {
    ev.target.checked = !value
    notify(e.message, 'error')
  }
}
function openDeclare() {
  declaring.value = { source: externalSources.value[0], external_id: '', name: '' }
}
async function declare() {
  try {
    const g = await api.post('/api/admin/groups/external', declaring.value)
    declaring.value = null
    await load()
    rightsFor.value = g
  } catch (e) {
    notify(e.message, 'error')
  }
}
async function create() {
  try {
    await api.post('/api/admin/groups', creating.value)
    creating.value = null
    await load()
  } catch (e) {
    notify(e.message, 'error')
  }
}
async function saveEdit() {
  const e = editing.value
  try {
    await api.put(`/api/admin/groups/${e.id}`, { description: e.description, ...(e.source === 'local' ? { name: e.name } : {}) })
    editing.value = null
    await load()
  } catch (err) {
    notify(err.message, 'error')
  }
}
async function remove(g) {
  const rules = g.rules ? ` Its ${g.rules} dashboard rule(s) will be lost, even if the group comes back.` : ''
  const warn = g.source !== 'local' ? ' It is recreated at the next synchronisation or sign-in of a member, without rights.' : ''
  if (!confirm(`Delete group "${g.name}"?${rules}${warn}`)) return
  try {
    await api.del(`/api/admin/groups/${g.id}`)
    await load()
  } catch (e) {
    notify(e.message, 'error')
  }
}
async function sync() {
  syncing.value = true
  try {
    const r = await api.post('/api/admin/ldap/sync')
    notify(`${r.groups} group(s) synchronised, ${r.removed} removed, ${r.users_updated} user(s) updated`)
    if (r.kept?.length) {
      notify(`Not found in the directory but kept because they carry rights: ${r.kept.join(', ')}. Delete them by hand if they are gone for good.`, 'error', 10000)
    }
    await load()
  } catch (e) {
    notify(e.message, 'error')
  } finally {
    syncing.value = false
  }
}
</script>

<style scoped>
.small {
  font-size: 0.8rem;
}
.ext {
  max-width: 420px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
