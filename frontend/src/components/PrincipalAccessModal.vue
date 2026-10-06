<template>
  <Modal :title="`Dashboards — ${principal.label}`" wide @close="$emit('close')">
    <p class="muted intro">
      <template v-if="kind === 'groups'">Rights granted to every member of this {{ principal.source }} group.</template>
      <template v-else>
        Rights granted directly to this account. The last column shows what the user really gets, including rights inherited from groups.
      </template>
      <span v-if="principal.is_admin" class="badge brand"><i class="fa-solid fa-shield-halved"></i> Administrator: full access to every dashboard</span>
    </p>

    <div class="toolbar">
      <input v-model="q" class="input" placeholder="Filter dashboards…" style="max-width: 280px" />
      <label class="check"><input v-model="onlyGranted" type="checkbox" /> With access only</label>
    </div>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>Dashboard</th>
            <th>Visibility</th>
            <th>{{ kind === 'groups' ? 'Group right' : 'Direct right' }}</th>
            <th v-if="kind === 'users'">Effective access</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in shown" :key="d.id">
            <td>
              <strong>{{ d.title }}</strong>
              <div class="muted mono small">/d/{{ d.slug }}</div>
            </td>
            <td>
              <span v-if="d.visibility === 'authenticated'" class="badge ok"><i class="fa-solid fa-globe"></i> Everyone</span>
              <span v-else class="badge brand"><i class="fa-solid fa-lock"></i> Restricted</span>
            </td>
            <td>
              <select v-model="perm[d.id]" class="input sm" style="width: auto">
                <option value="">None</option>
                <option value="view">View</option>
                <option value="edit">View + edit</option>
              </select>
            </td>
            <td v-if="kind === 'users'">
              <template v-for="e in [effective(d)]" :key="d.id">
                <span v-if="e.edit" class="badge ok"><i class="fa-solid fa-pen"></i> Edit</span>
                <span v-else-if="e.view" class="badge"><i class="fa-solid fa-eye"></i> View</span>
                <span v-else class="badge danger"><i class="fa-solid fa-ban"></i> No access</span>
                <div v-if="e.reasons.length" class="muted small">{{ e.reasons.join(' · ') }}</div>
              </template>
            </td>
          </tr>
          <tr v-if="!shown.length"><td :colspan="kind === 'users' ? 4 : 3" class="empty">No dashboards.</td></tr>
        </tbody>
      </table>
    </div>

    <template #footer>
      <button class="btn" @click="$emit('close')">Cancel</button>
      <button class="btn primary" :disabled="saving || !loaded" @click="save"><i class="fa-solid fa-floppy-disk"></i> Save</button>
    </template>
  </Modal>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api'
import { notify } from '../store'
import Modal from './Modal.vue'

// kind: "groups" | "users"; principal: { id, label, source, is_admin }
const props = defineProps({ kind: { type: String, required: true }, principal: { type: Object, required: true } })
const emit = defineEmits(['close', 'saved'])

const dashboards = ref([])
const perm = reactive({})
const inherited = reactive({}) // dashboard_id -> reasons not coming from a direct user rule
const q = ref('')
const onlyGranted = ref(false)
const saving = ref(false)
const loaded = ref(false)

onMounted(async () => {
  try {
    const [dash, rules, eff] = await Promise.all([
      api.get('/api/admin/dashboards'),
      api.get(`/api/admin/${props.kind}/${props.principal.id}/access`),
      props.kind === 'users' ? api.get(`/api/admin/users/${props.principal.id}/effective-access`) : Promise.resolve([]),
    ])
    dashboards.value = dash
    for (const d of dash) perm[d.id] = ''
    for (const r of rules) perm[r.dashboard_id] = r.can_edit ? 'edit' : 'view'
    for (const e of eff) inherited[e.dashboard_id] = e.reasons.filter((x) => x.kind !== 'user')
    loaded.value = true
  } catch (e) {
    notify(e.message, 'error')
  }
})

const shown = computed(() => {
  const term = q.value.trim().toLowerCase()
  return dashboards.value.filter(
    (d) =>
      (!term || `${d.title} ${d.slug}`.toLowerCase().includes(term)) &&
      (!onlyGranted.value || perm[d.id] || (props.kind === 'users' && effective(d).view)),
  )
})

// Effective access, recomputed live from the inherited reasons and the direct right being edited
function effective(d) {
  const reasons = []
  let view = false
  let edit = false
  for (const r of inherited[d.id] || []) {
    view = true
    edit ||= r.can_edit
    if (r.kind === 'admin') reasons.push('administrator')
    else if (r.kind === 'everyone') reasons.push('everyone')
    else reasons.push(`group ${r.group}${r.can_edit ? ' (edit)' : ''}`)
  }
  if (perm[d.id]) {
    view = true
    edit ||= perm[d.id] === 'edit'
    reasons.push(`direct${perm[d.id] === 'edit' ? ' (edit)' : ''}`)
  }
  return { view, edit, reasons }
}

async function save() {
  saving.value = true
  try {
    const body = Object.entries(perm)
      .filter(([, p]) => p)
      .map(([id, p]) => ({ dashboard_id: +id, can_edit: p === 'edit' }))
    await api.put(`/api/admin/${props.kind}/${props.principal.id}/access`, body)
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
.intro {
  margin-top: 0;
  font-size: 0.9rem;
}
.intro .badge {
  margin-left: 6px;
}
.small {
  font-size: 0.8rem;
}
</style>
