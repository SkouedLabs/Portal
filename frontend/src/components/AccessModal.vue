<template>
  <Modal :title="`Access — ${dashboard.title}`" wide @close="$emit('close')">
    <div class="field">
      <label>Who can see this dashboard</label>
      <div class="seg">
        <button :class="{ active: visibility === 'restricted' }" @click="visibility = 'restricted'"><i class="fa-solid fa-lock"></i> Listed groups and users</button>
        <button :class="{ active: visibility === 'authenticated' }" @click="visibility = 'authenticated'"><i class="fa-solid fa-globe"></i> All signed-in users</button>
      </div>
      <span class="hint">
        <template v-if="visibility === 'authenticated'">Everyone signed in can view it. Add rules below to grant <strong>edit</strong> rights.</template>
        <template v-else>Only the groups and users below can view it. Administrators always have full access.</template>
      </span>
    </div>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr><th>Group / user</th><th>Source</th><th>Permission</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in rules" :key="r.kind + (r.group_id || r.user_id)">
            <td>
              <i :class="r.kind === 'group' ? 'fa-solid fa-users' : 'fa-solid fa-user'" class="muted"></i>
              {{ r.label }}
              <span v-if="r.detail" class="muted small-inline">{{ r.detail }}</span>
            </td>
            <td><span class="badge" :class="`src-${r.source}`">{{ r.source }}</span></td>
            <td>
              <select v-model="r.can_edit" class="input sm" style="width: auto">
                <option :value="false">View</option>
                <option :value="true">View + edit</option>
              </select>
              <span v-if="visibility === 'authenticated' && !r.can_edit" class="badge warn" title="Everyone can already view this dashboard">no effect</span>
            </td>
            <td class="actions"><button class="btn ghost icon sm danger" title="Remove" @click="rules.splice(i, 1)"><i class="fa-solid fa-trash"></i></button></td>
          </tr>
          <tr v-if="!rules.length">
            <td colspan="4" class="empty">{{ visibility === 'restricted' ? 'No rules: only administrators can see this dashboard.' : 'No rules.' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="adder">
      <div class="adder-bar">
        <div class="seg">
          <button :class="{ active: kind === 'group' }" @click="kind = 'group'"><i class="fa-solid fa-users"></i> Group</button>
          <button :class="{ active: kind === 'user' }" @click="kind = 'user'"><i class="fa-solid fa-user"></i> User</button>
        </div>
        <select v-model="source" class="input" style="width: auto">
          <option value="">All sources</option>
          <option value="local">Local</option>
          <option value="ldap">LDAP</option>
          <option value="oidc">OIDC</option>
        </select>
        <input v-model="q" class="input" :placeholder="kind === 'group' ? 'Search for a group (name, DN, claim value)…' : 'Search for a user…'" />
      </div>
      <div class="candidates">
        <button v-for="c in candidates" :key="c.id" class="cand" @click="add(c)">
          <span>{{ c.label }} <span v-if="c.detail" class="muted">{{ c.detail }}</span></span>
          <span v-if="c.pending" class="badge warn" title="Declared by an administrator, has not signed in yet">not signed in yet</span>
          <span class="badge" :class="`src-${c.source}`">{{ c.source }}</span>
          <i class="fa-solid fa-plus"></i>
        </button>
        <template v-for="d in declarable" :key="d.source">
          <button class="cand declare" :disabled="declaring" @click="declare(d)">
            <span><i class="fa-solid fa-circle-plus"></i> {{ d.text }}</span>
            <span class="badge" :class="`src-${d.source}`">{{ d.source }}</span>
          </button>
        </template>
        <p v-if="!candidates.length && !declarable.length" class="muted small">
          No results.
          <template v-if="externalSources.length">
            {{ kind === 'group' ? 'Type the exact LDAP DN or OIDC claim value' : 'Type the exact username' }} to add one that has not signed in yet.
          </template>
        </p>
      </div>
      <p v-if="externalSources.length" class="hint">
        <template v-if="kind === 'group'">
          LDAP and OIDC groups appear here once synchronised or once a member signs in. You can also declare one in advance:
          <span v-if="loginCfg.ldap">LDAP by its DN (<span class="mono">cn=staff,ou=groups,dc=example,dc=com</span>)</span><span v-if="loginCfg.ldap && loginCfg.oidc">, </span>
          <span v-if="loginCfg.oidc">OIDC by the exact value sent in the groups claim</span>.
        </template>
        <template v-else>
          LDAP and OIDC accounts appear after their first sign-in. You can also declare one in advance by its username; it is linked at the first sign-in.
        </template>
      </p>
    </div>

    <template #footer>
      <button class="btn" @click="$emit('close')">Cancel</button>
      <button class="btn primary" :disabled="saving" @click="save"><i class="fa-solid fa-floppy-disk"></i> Save</button>
    </template>
  </Modal>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { notify, state } from '../store'
import Modal from './Modal.vue'

const props = defineProps({ dashboard: { type: Object, required: true } })
const emit = defineEmits(['close', 'saved'])

const visibility = ref(props.dashboard.visibility)
const rules = ref([])
const groups = ref([])
const users = ref([])
const kind = ref('group')
const source = ref('')
const q = ref('')
const saving = ref(false)
const declaring = ref(false)

const loginCfg = computed(() => state.config?.login || {})
const externalSources = computed(() => ['ldap', 'oidc'].filter((s) => loginCfg.value[s]))

onMounted(async () => {
  try {
    const [r, g, u] = await Promise.all([
      api.get(`/api/admin/dashboards/${props.dashboard.id}/access`),
      api.get('/api/admin/groups'),
      api.get('/api/admin/users'),
    ])
    groups.value = g
    users.value = u
    rules.value = r.map((x) => ({ ...x, detail: describe(x) }))
  } catch (e) {
    notify(e.message, 'error')
  }
})

const groupCand = (g) => ({ id: g.id, label: g.name, detail: `${g.members} member(s)`, source: g.source, hay: `${g.name} ${g.external_id} ${g.description || ''}` })
const userCand = (u) => ({
  id: u.id,
  label: u.display_name && u.display_name !== u.username ? `${u.display_name} (${u.username})` : u.username,
  source: u.source,
  pending: u.pending,
  hay: `${u.username} ${u.display_name} ${u.email}`,
})

function describe(rule) {
  if (rule.kind !== 'group') return ''
  const g = groups.value.find((x) => x.id === rule.group_id)
  return g ? `${g.members} member(s)` : ''
}

const candidates = computed(() => {
  const term = q.value.trim().toLowerCase()
  const list = kind.value === 'group' ? groups.value.map(groupCand) : users.value.map(userCand)
  const taken = new Set(rules.value.filter((r) => r.kind === kind.value).map((r) => r.group_id || r.user_id))
  return list
    .filter((c) => !taken.has(c.id) && (!source.value || c.source === source.value) && (!term || c.hay.toLowerCase().includes(term)))
    .slice(0, 50)
})

// Offer to declare an LDAP / OIDC group or account that is not known yet
const declarable = computed(() => {
  const term = q.value.trim()
  if (!term) return []
  const low = term.toLowerCase()
  return externalSources.value
    .filter((s) => !source.value || source.value === s)
    .filter((s) => {
      if (kind.value === 'group') {
        if (s === 'ldap' && !term.includes('=')) return false
        return !groups.value.some((g) => g.source === s && (s === 'ldap' ? g.external_id === low : g.external_id === term))
      }
      return !/\s/.test(term) && !users.value.some((u) => u.source === s && u.username.toLowerCase() === low)
    })
    .map((s) => ({
      source: s,
      term,
      text: kind.value === 'group' ? `Declare ${s.toUpperCase()} group "${term}"` : `Declare ${s.toUpperCase()} account "${term}" (not signed in yet)`,
    }))
})

function add(c) {
  rules.value.push({
    kind: kind.value,
    group_id: kind.value === 'group' ? c.id : null,
    user_id: kind.value === 'user' ? c.id : null,
    label: c.label,
    detail: c.detail || '',
    source: c.source,
    can_edit: visibility.value === 'authenticated',
  })
  q.value = ''
}

async function declare(d) {
  declaring.value = true
  try {
    if (kind.value === 'group') {
      const g = await api.post('/api/admin/groups/external', { source: d.source, external_id: d.term })
      groups.value.push(g)
      add(groupCand(g))
    } else {
      const u = await api.post('/api/admin/users/external', { source: d.source, username: d.term })
      users.value.push(u)
      add(userCand(u))
    }
  } catch (e) {
    notify(e.message, 'error')
  } finally {
    declaring.value = false
  }
}

async function save() {
  saving.value = true
  try {
    if (visibility.value !== props.dashboard.visibility) {
      await api.patch(`/api/admin/dashboards/${props.dashboard.id}`, { visibility: visibility.value })
    }
    await api.put(
      `/api/admin/dashboards/${props.dashboard.id}/access`,
      rules.value.map((r) => ({ group_id: r.group_id, user_id: r.user_id, can_edit: r.can_edit })),
    )
    notify('Permissions saved')
    emit('saved')
    emit('close')
  } catch (e) {
    notify(e.message, 'error')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.adder {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.adder-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.adder-bar input {
  flex: 1;
  min-width: 200px;
}
.seg {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 3px;
  border-radius: 9px;
  background: var(--ui-surface-2);
  border: 1px solid var(--ui-border);
  width: fit-content;
}
.seg button {
  font: inherit;
  font-size: 0.85rem;
  border: none;
  background: none;
  color: var(--ui-muted);
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
}
.seg button.active {
  background: var(--ui-surface);
  color: var(--ui-text);
  font-weight: 600;
  box-shadow: var(--ui-shadow);
}
.candidates {
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid var(--ui-border);
  border-radius: 8px;
  padding: 4px;
}
.cand {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  background: none;
  font: inherit;
  font-size: 0.9rem;
  color: var(--ui-text);
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
}
.cand > span:first-child {
  flex: 1;
}
.cand > i,
.cand.declare i {
  color: var(--brand);
}
.cand.declare {
  font-weight: 600;
}
.cand:hover {
  background: var(--ui-surface-2);
}
.small {
  font-size: 0.85rem;
  padding: 8px;
  margin: 0;
}
.small-inline {
  font-size: 0.8rem;
  margin-left: 6px;
}
td .badge.warn {
  margin-left: 6px;
}
</style>
