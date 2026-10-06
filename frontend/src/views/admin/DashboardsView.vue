<template>
  <div>
    <div class="page-title">
      <h1>Dashboards</h1>
      <div style="flex: 1"></div>
      <button class="btn" @click="importing = true"><i class="fa-solid fa-file-import"></i> Import from Homer</button>
      <button class="btn primary" @click="openCreate"><i class="fa-solid fa-plus"></i> New dashboard</button>
      <p>Create dashboards and decide who can view and who can edit them.</p>
    </div>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>Order</th>
            <th>Dashboard</th>
            <th>Visibility</th>
            <th>Access rules</th>
            <th>Updated</th>
            <th class="actions">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in dashboards" :key="d.id">
            <td style="width: 70px"><input class="input sm" type="number" :value="d.position" style="width: 64px" @change="patch(d, { position: +$event.target.value })" /></td>
            <td>
              <div class="dash-name">
                <img v-if="d.logo" :src="d.logo" alt="" />
                <i v-else class="fa-solid fa-table-columns"></i>
                <div>
                  <strong>{{ d.title }}</strong>
                  <div class="muted mono">/d/{{ d.slug }} · {{ d.sections }} section(s)</div>
                </div>
              </div>
            </td>
            <td>
              <select class="input sm" style="width: auto" :value="d.visibility" @change="changeVisibility(d, $event)">
                <option value="restricted">Restricted</option>
                <option value="authenticated">Everyone</option>
              </select>
            </td>
            <td class="access">
              <button class="access-summary" title="Manage access" @click="openAccess(d)">
                <span v-for="a in d.access.slice(0, 4)" :key="a.kind + a.id" class="badge" :class="a.can_edit ? 'brand' : `src-${a.source}`">
                  <i :class="a.kind === 'group' ? 'fa-solid fa-users' : 'fa-solid fa-user'"></i> {{ a.label }}
                  <i v-if="a.can_edit" class="fa-solid fa-pen" title="Can edit"></i>
                </span>
                <span v-if="d.access.length > 4" class="badge">+{{ d.access.length - 4 }}</span>
                <span v-if="!d.access.length" class="muted small">{{ d.visibility === 'restricted' ? 'Administrators only' : 'No editor' }}</span>
                <i class="fa-solid fa-user-shield edit-icon"></i>
              </button>
            </td>
            <td class="muted small">{{ fmt(d.updated_at) }}<br />{{ d.updated_by }}</td>
            <td class="actions">
              <a :href="`/d/${d.slug}`" target="_blank" class="btn ghost icon sm" title="Open"><i class="fa-solid fa-up-right-from-square"></i></a>
              <router-link :to="`/edit/${d.id}?from=admin`" class="btn ghost icon sm" title="Edit"><i class="fa-solid fa-pen"></i></router-link>
              <button class="btn ghost icon sm" title="Duplicate" @click="duplicate(d)"><i class="fa-regular fa-copy"></i></button>
              <button class="btn ghost icon sm danger" title="Delete" @click="remove(d)"><i class="fa-solid fa-trash"></i></button>
            </td>
          </tr>
          <tr v-if="!dashboards.length">
            <td colspan="6" class="empty">No dashboards.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Creation -->
    <Modal v-if="creating" title="New dashboard" @close="creating = null">
      <div class="field">
        <label>Title</label>
        <input v-model="creating.title" class="input" autofocus @input="autoSlug" />
      </div>
      <div class="field">
        <label>URL slug</label>
        <input v-model="creating.slug" class="input mono" @input="slugTouched = true" />
        <span class="hint">Lowercase letters, digits and dashes — /d/{{ creating.slug }}</span>
      </div>
      <div class="field">
        <label>Visibility</label>
        <select v-model="creating.visibility" class="input">
          <option value="restricted">Restricted (according to access rules)</option>
          <option value="authenticated">All signed-in users</option>
        </select>
      </div>
      <template #footer>
        <button class="btn" @click="creating = null">Cancel</button>
        <button class="btn primary" :disabled="!creating.title || !creating.slug" @click="create">Create and edit</button>
      </template>
    </Modal>

    <HomerImportModal
      v-if="importing"
      :existing-slugs="dashboards.map((d) => d.slug)"
      :next-position="dashboards.length"
      @imported="load"
      @close="importing = false"
    />
    <AccessModal v-if="accessFor" :dashboard="accessFor" @close="accessFor = null" @saved="load" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../../api'
import AccessModal from '../../components/AccessModal.vue'
import HomerImportModal from '../../components/HomerImportModal.vue'
import Modal from '../../components/Modal.vue'
import { notify } from '../../store'
import { emptyConfig } from '../../theme'

const router = useRouter()
const dashboards = ref([])
const creating = ref(null)
const slugTouched = ref(false)
const accessFor = ref(null)
const importing = ref(false)

const fmt = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' }) : '')

async function load() {
  try {
    dashboards.value = await api.get('/api/admin/dashboards')
  } catch (e) {
    notify(e.message, 'error')
  }
}
onMounted(load)

function openCreate() {
  slugTouched.value = false
  creating.value = { title: '', slug: '', visibility: 'restricted' }
}
function autoSlug() {
  if (slugTouched.value) return
  creating.value.slug = creating.value.title
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64)
}
async function create() {
  try {
    const d = await api.post('/api/admin/dashboards', {
      ...creating.value,
      subtitle: '',
      logo: '',
      position: dashboards.value.length,
      config: emptyConfig(),
    })
    creating.value = null
    router.push(`/edit/${d.id}?from=admin`)
  } catch (e) {
    notify(e.message, 'error')
  }
}
async function patch(d, values) {
  try {
    await api.patch(`/api/admin/dashboards/${d.id}`, values)
  } catch (e) {
    notify(e.message, 'error')
  }
  await load()
}
async function duplicate(d) {
  try {
    await api.post(`/api/admin/dashboards/${d.id}/duplicate`)
    notify('Dashboard duplicated (restricted visibility, no access rules)')
    await load()
  } catch (e) {
    notify(e.message, 'error')
  }
}
async function remove(d) {
  if (!confirm(`Permanently delete "${d.title}"?`)) return
  try {
    await api.del(`/api/admin/dashboards/${d.id}`)
    notify('Dashboard deleted')
    await load()
  } catch (e) {
    notify(e.message, 'error')
  }
}
async function changeVisibility(d, ev) {
  const value = ev.target.value
  if (value === 'authenticated' && !confirm(`Make "${d.title}" visible to every signed-in user?`)) {
    ev.target.value = d.visibility
    return
  }
  await patch(d, { visibility: value })
}
function openAccess(d) {
  accessFor.value = d
}
</script>

<style scoped>
.dash-name {
  display: flex;
  align-items: center;
  gap: 12px;
}
.dash-name img,
.dash-name > i {
  width: 30px;
  height: 30px;
  object-fit: contain;
  color: var(--brand);
  font-size: 1.2rem;
  display: flex;
  align-items: center;
  justify-content: center;
}
.small {
  font-size: 0.8rem;
}
.access {
  max-width: 380px;
}
.access-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  border: 1px dashed transparent;
  background: none;
  font: inherit;
  color: inherit;
  padding: 4px 6px;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
}
.access-summary:hover {
  border-color: var(--ui-border);
  background: var(--ui-surface-2);
}
.access-summary .edit-icon {
  color: var(--ui-muted);
  margin-left: 4px;
}
</style>
