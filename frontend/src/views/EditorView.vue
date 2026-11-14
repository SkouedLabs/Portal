<template>
  <div class="editor-page">
    <header class="editor-bar">
      <router-link :to="backTo" class="btn ghost sm"><i class="fa-solid fa-arrow-left"></i> Back</router-link>
      <div class="bar-title">
        <strong>{{ form?.title || 'Dashboard' }}</strong>
        <span v-if="dirty" class="badge warn">Unsaved changes</span>
      </div>
      <div class="spacer"></div>
      <button class="btn sm mobile-only" @click="showPreview = !showPreview">
        <i :class="showPreview ? 'fa-solid fa-pen' : 'fa-solid fa-eye'"></i> {{ showPreview ? 'Edit' : 'Preview' }}
      </button>
      <router-link v-if="form" :to="`/d/${original.slug}`" class="btn sm" target="_blank"><i class="fa-solid fa-up-right-from-square"></i> Open</router-link>
      <button class="btn primary sm" :disabled="!dirty || saving" @click="save">
        <i :class="saving ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-floppy-disk'"></i> Save
      </button>
    </header>

    <div v-if="loadError" class="empty">{{ loadError }}</div>
    <div v-else-if="!form" class="empty"><i class="fa-solid fa-spinner fa-spin"></i></div>

    <div v-else class="editor-body" :class="{ 'show-preview': showPreview }">
      <aside class="editor-panel">
        <div class="tabs">
          <button v-for="t in tabs" :key="t.id" :class="{ active: tab === t.id }" @click="tab = t.id">
            <i :class="t.icon"></i> {{ t.label }}
          </button>
        </div>

        <!-- General -->
        <div v-show="tab === 'general'">
          <div class="field">
            <label>Title</label>
            <input v-model="form.title" class="input" maxlength="255" />
          </div>
          <div class="field">
            <label>Subtitle</label>
            <input v-model="form.subtitle" class="input" maxlength="255" />
          </div>
          <ImageField v-model="form.logo" label="Dashboard logo" hint="Leave empty to use the portal logo." />
          <template v-if="isAdmin">
            <div class="row">
              <div class="field">
                <label>URL slug</label>
                <input v-model="form.slug" class="input mono" />
                <span class="hint">/d/{{ form.slug }}</span>
              </div>
              <div class="field" style="flex: 0 0 110px">
                <label>Order</label>
                <input v-model.number="form.position" type="number" class="input" />
              </div>
            </div>
            <div class="field">
              <label>Visibility</label>
              <select v-model="form.visibility" class="input">
                <option value="authenticated">All signed-in users</option>
                <option value="restricted">Restricted (allowed groups / users)</option>
              </select>
            </div>
          </template>
          <div class="row">
            <div class="field">
              <label>Columns</label>
              <select v-model="form.config.columns" class="input">
                <option v-for="c in ['auto', '1', '2', '3', '4', '6', '12']" :key="c" :value="c">{{ c === 'auto' ? 'Automatic' : c }}</option>
              </select>
            </div>
            <div class="field">
              <label>Default layout</label>
              <select v-model="form.config.default_layout" class="input">
                <option value="columns">Columns</option>
                <option value="list">List</option>
              </select>
            </div>
            <div class="field">
              <label>Default theme</label>
              <select v-model="form.config.default_theme" class="input">
                <option value="auto">Automatic</option>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </select>
            </div>
          </div>
          <label class="switch">
            <input v-model="form.config.show_header" type="checkbox" /><span class="track"></span> Show header
          </label>
          <div class="field" style="margin-top: 14px; max-width: 260px">
            <label>Status check interval (seconds)</label>
            <input v-model.number="form.config.status_interval" type="number" min="15" max="3600" class="input" />
          </div>
          <div class="field" style="margin-top: 14px">
            <label>Footer</label>
            <textarea v-model="form.config.footer" class="input" rows="2" placeholder="Leave empty to use the portal footer"></textarea>
          </div>
        </div>

        <!-- Appearance -->
        <div v-show="tab === 'look'">
          <h3 class="sub">Background</h3>
          <div class="seg">
            <button v-for="b in bgTypes" :key="b.id" :class="{ active: form.config.background.type === b.id }" @click="form.config.background.type = b.id">
              <i :class="b.icon"></i> {{ b.label }}
            </button>
          </div>
          <ColorField v-if="form.config.background.type === 'color'" v-model="form.config.background.color" label="Colour" />
          <template v-if="form.config.background.type === 'gradient'">
            <div class="row">
              <ColorField v-model="form.config.background.gradient_from" label="From" />
              <ColorField v-model="form.config.background.gradient_to" label="To" />
            </div>
            <div class="field">
              <label>Angle: {{ form.config.background.gradient_angle }}°</label>
              <input v-model.number="form.config.background.gradient_angle" type="range" min="0" max="360" step="5" />
            </div>
          </template>
          <template v-if="form.config.background.type === 'image'">
            <ImageField v-model="form.config.background.image" label="Image" kind="background" hint="Any size: scaled to 2560 px and re-encoded to WebP on upload." />
            <div class="field">
              <label>Darken: {{ Math.round(form.config.background.overlay * 100) }}%</label>
              <input v-model.number="form.config.background.overlay" type="range" min="0" max="0.9" step="0.05" />
            </div>
            <div class="field">
              <label>Blur: {{ form.config.background.blur }} px</label>
              <input v-model.number="form.config.background.blur" type="range" min="0" max="20" step="1" />
            </div>
          </template>

          <h3 class="sub">Colours</h3>
          <div class="seg">
            <button :class="{ active: colorTheme === 'light' }" @click="colorTheme = 'light'"><i class="fa-solid fa-sun"></i> Light theme</button>
            <button :class="{ active: colorTheme === 'dark' }" @click="colorTheme = 'dark'"><i class="fa-solid fa-moon"></i> Dark theme</button>
          </div>
          <div class="colors-grid">
            <ColorField
              v-for="(label, key) in COLOR_LABELS"
              :key="colorTheme + key"
              v-model="form.config.colors[colorTheme][key]"
              :label="label"
              :placeholder="DEFAULT_COLORS[colorTheme][key]"
            />
          </div>
        </div>

        <!-- Message -->
        <div v-show="tab === 'message'">
          <label class="switch" style="margin-bottom: 14px">
            <input v-model="form.config.message.enabled" type="checkbox" /><span class="track"></span> Show a message
          </label>
          <div class="row">
            <div class="field">
              <label>Style</label>
              <select v-model="form.config.message.style" class="input">
                <option value="is-info">Information</option>
                <option value="is-success">Success</option>
                <option value="is-warning">Warning</option>
                <option value="is-danger">Danger</option>
                <option value="is-dark">Dark</option>
              </select>
            </div>
            <IconField v-model="form.config.message.icon" label="Icon" />
          </div>
          <div class="field">
            <label>Title</label>
            <input v-model="form.config.message.title" class="input" />
          </div>
          <div class="field">
            <label>Content</label>
            <textarea v-model="form.config.message.content" class="input" rows="4"></textarea>
          </div>
        </div>

        <!-- Links -->
        <div v-show="tab === 'links'">
          <p class="muted small">Links shown in the navigation bar.</p>
          <div v-for="(l, i) in form.config.links" :key="i" class="block">
            <div class="block-head">
              <i :class="l.icon || 'fa-solid fa-link'"></i>
              <strong>{{ l.name || 'New link' }}</strong>
              <div class="spacer"></div>
              <button class="btn ghost icon sm" :disabled="i === 0" @click="move(form.config.links, i, -1)"><i class="fa-solid fa-arrow-up"></i></button>
              <button class="btn ghost icon sm" :disabled="i === form.config.links.length - 1" @click="move(form.config.links, i, 1)"><i class="fa-solid fa-arrow-down"></i></button>
              <button class="btn ghost icon sm danger" @click="form.config.links.splice(i, 1)"><i class="fa-solid fa-trash"></i></button>
            </div>
            <div class="row">
              <div class="field"><label>Name</label><input v-model="l.name" class="input sm" /></div>
              <IconField v-model="l.icon" label="Icon" />
            </div>
            <div class="row">
              <div class="field"><label>URL</label><input v-model="l.url" class="input sm" /></div>
              <div class="field" style="flex: 0 0 140px">
                <label>Open in</label>
                <select v-model="l.target" class="input sm"><option value="_blank">New tab</option><option value="_self">Same tab</option></select>
              </div>
            </div>
          </div>
          <button class="btn" @click="form.config.links.push({ name: '', icon: '', url: 'https://', target: '_blank' })">
            <i class="fa-solid fa-plus"></i> Add a link
          </button>
        </div>

        <!-- Sections -->
        <div v-show="tab === 'sections'">
          <div v-for="(s, si) in form.config.sections" :key="s.id" class="block section-block">
            <div class="block-head">
              <button class="btn ghost icon sm" @click="toggle(s.id)">
                <i :class="open[s.id] ? 'fa-solid fa-chevron-down' : 'fa-solid fa-chevron-right'"></i>
              </button>
              <i v-if="s.icon" :class="s.icon"></i>
              <strong class="grow" @click="toggle(s.id)">{{ s.name || 'Untitled section' }}</strong>
              <span class="badge">{{ s.items.length }}</span>
              <button class="btn ghost icon sm" :disabled="si === 0" @click="move(form.config.sections, si, -1)"><i class="fa-solid fa-arrow-up"></i></button>
              <button class="btn ghost icon sm" :disabled="si === form.config.sections.length - 1" @click="move(form.config.sections, si, 1)"><i class="fa-solid fa-arrow-down"></i></button>
              <button class="btn ghost icon sm danger" @click="removeSection(si)"><i class="fa-solid fa-trash"></i></button>
            </div>
            <div v-if="open[s.id]" class="block-body">
              <div class="row">
                <div class="field"><label>Section name</label><input v-model="s.name" class="input sm" /></div>
                <IconField v-model="s.icon" label="Icon" />
              </div>

              <div v-for="(it, ii) in s.items" :key="it.id" class="item" :class="{ expanded: open[it.id] }">
                <div class="item-head" @click="toggle(it.id)">
                  <span class="item-icon">
                    <img v-if="it.logo" :src="it.logo" alt="" />
                    <i v-else :class="it.icon || 'fa-regular fa-square'"></i>
                  </span>
                  <span class="grow ellipsis">{{ it.name || 'New link' }} <span class="muted small">{{ it.url }}</span></span>
                  <button class="btn ghost icon sm" :disabled="ii === 0" @click.stop="move(s.items, ii, -1)"><i class="fa-solid fa-arrow-up"></i></button>
                  <button class="btn ghost icon sm" :disabled="ii === s.items.length - 1" @click.stop="move(s.items, ii, 1)"><i class="fa-solid fa-arrow-down"></i></button>
                  <button class="btn ghost icon sm" title="Duplicate" @click.stop="duplicateItem(s, ii)"><i class="fa-regular fa-copy"></i></button>
                  <button class="btn ghost icon sm danger" @click.stop="s.items.splice(ii, 1)"><i class="fa-solid fa-trash"></i></button>
                </div>
                <div v-if="open[it.id]" class="item-body">
                  <div class="row">
                    <div class="field"><label>Name</label><input v-model="it.name" class="input sm" /></div>
                    <div class="field"><label>Subtitle</label><input v-model="it.subtitle" class="input sm" /></div>
                  </div>
                  <div class="field"><label>URL</label><input v-model="it.url" class="input sm" placeholder="https://…" /></div>
                  <div class="row">
                    <IconField v-model="it.icon" label="Icon" />
                    <ImageField v-model="it.logo" label="Or logo (image)" />
                  </div>
                  <div class="row">
                    <div class="field"><label>Tag</label><input v-model="it.tag" class="input sm" /></div>
                    <div class="field">
                      <label>Tag style</label>
                      <select v-model="it.tagstyle" class="input sm">
                        <option value="">Default</option>
                        <option value="is-info">Info</option>
                        <option value="is-success">Success</option>
                        <option value="is-warning">Warning</option>
                        <option value="is-danger">Danger</option>
                        <option value="is-primary">Primary</option>
                      </select>
                    </div>
                  </div>
                  <div class="row">
                    <div class="field">
                      <label>Open in</label>
                      <select v-model="it.target" class="input sm"><option value="_blank">New tab</option><option value="_self">Same tab</option></select>
                    </div>
                    <div class="field"><label>Keywords (search)</label><input v-model="it.keywords" class="input sm" /></div>
                  </div>
                  <div class="status-box">
                    <label class="switch"><input v-model="it.status_check" type="checkbox" /><span class="track"></span> Check status</label>
                    <template v-if="it.status_check">
                      <div class="field" style="margin-top: 10px">
                        <label>Status URL (optional)</label>
                        <input v-model="it.status_url" class="input sm" :placeholder="it.url || 'https://…'" />
                        <span class="hint">Probed by the server. Leave empty to check the link URL. Green: 2xx/3xx, orange: 4xx, red: 5xx or unreachable.</span>
                      </div>
                      <label class="check"><input v-model="it.status_ignore_tls" type="checkbox" /> Ignore certificate errors</label>
                    </template>
                  </div>
                  <div class="row">
                    <ColorField v-model="it.background" label="Card background" />
                    <div v-if="form.config.sections.length > 1" class="field">
                      <label>Move to</label>
                      <select class="input sm" @change="moveItem(si, ii, +$event.target.value)">
                        <option value="-1">—</option>
                        <template v-for="(o, oi) in form.config.sections" :key="o.id">
                          <option v-if="oi !== si" :value="oi">{{ o.name || 'Section ' + (oi + 1) }}</option>
                        </template>
                      </select>
                    </div>
                  </div>
                </div>
              </div>
              <button class="btn sm" @click="addItem(s)"><i class="fa-solid fa-plus"></i> Add a link</button>
            </div>
          </div>
          <button class="btn" @click="addSection"><i class="fa-solid fa-plus"></i> Add a section</button>
        </div>

        <!-- YAML -->
        <div v-show="tab === 'yaml'">
          <p class="muted small">
            Import / export in Homer's <code>config.yml</code> format. Importing replaces the current content (not saved until you click "Save").
            To migrate a Homer dashboard <strong>with its local images</strong> and pages, use Admin › Dashboards › Import from Homer.
          </p>
          <div class="toolbar">
            <label class="btn sm"><i class="fa-solid fa-file-import"></i> Load a file<input type="file" accept=".yml,.yaml" hidden @change="loadYamlFile" /></label>
            <button class="btn sm" @click="yamlText = exportHomer(form)"><i class="fa-solid fa-arrows-rotate"></i> Generate from dashboard</button>
            <button class="btn sm" @click="downloadYaml"><i class="fa-solid fa-download"></i> Download</button>
          </div>
          <textarea v-model="yamlText" class="input mono yaml" spellcheck="false" placeholder="Paste a Homer config.yml here…"></textarea>
          <button class="btn primary" style="margin-top: 10px" :disabled="!yamlText.trim()" @click="applyYaml">
            <i class="fa-solid fa-file-import"></i> Apply YAML
          </button>
          <div v-if="yamlWarnings.length" class="alert info" style="margin-top: 12px">
            <strong>{{ yamlWarnings.length }} point(s) not converted:</strong>
            <ul class="yaml-warnings"><li v-for="w in yamlWarnings" :key="w">{{ w }}</li></ul>
          </div>
        </div>
      </aside>

      <section class="preview-pane">
        <div class="preview-frame">
          <DashboardRender :dashboard="previewDashboard" preview />
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import ColorField from '../components/ColorField.vue'
import DashboardRender from '../components/DashboardRender.vue'
import IconField from '../components/IconField.vue'
import ImageField from '../components/ImageField.vue'
import { convertHomer, exportHomer, parseHomer } from '../homerYaml'
import { notify, state } from '../store'
import { COLOR_LABELS, DEFAULT_COLORS, emptyConfig, uid } from '../theme'

const route = useRoute()
const router = useRouter()
const isAdmin = computed(() => !!state.me?.is_admin)
const backTo = computed(() => (route.query.from === 'admin' ? '/admin/dashboards' : original.value ? `/d/${original.value.slug}` : '/'))

const tabs = [
  { id: 'general', label: 'General', icon: 'fa-solid fa-sliders' },
  { id: 'look', label: 'Appearance', icon: 'fa-solid fa-palette' },
  { id: 'sections', label: 'Sections', icon: 'fa-solid fa-table-cells' },
  { id: 'links', label: 'Navigation', icon: 'fa-solid fa-link' },
  { id: 'message', label: 'Message', icon: 'fa-regular fa-message' },
  { id: 'yaml', label: 'YAML', icon: 'fa-solid fa-code' },
]
const bgTypes = [
  { id: 'default', label: 'Theme', icon: 'fa-solid fa-circle-half-stroke' },
  { id: 'color', label: 'Colour', icon: 'fa-solid fa-fill-drip' },
  { id: 'gradient', label: 'Gradient', icon: 'fa-solid fa-swatchbook' },
  { id: 'image', label: 'Image', icon: 'fa-regular fa-image' },
]

const tab = ref('sections')
const colorTheme = ref('light')
const form = ref(null)
const original = ref(null)
const snapshot = ref('')
const saving = ref(false)
const loadError = ref('')
const showPreview = ref(false)
const open = reactive({})
const yamlText = ref('')

const dirty = computed(() => form.value && JSON.stringify(form.value) !== snapshot.value)
const previewDashboard = computed(() => ({ ...form.value, id: form.value?.id }))

function normalize(d) {
  const base = emptyConfig()
  const c = d.config || {}
  return {
    id: d.id,
    title: d.title,
    subtitle: d.subtitle || '',
    logo: d.logo || '',
    slug: d.slug,
    visibility: d.visibility,
    position: d.position || 0,
    config: {
      ...base,
      ...c,
      background: { ...base.background, ...(c.background || {}) },
      colors: { light: { ...base.colors.light, ...(c.colors?.light || {}) }, dark: { ...base.colors.dark, ...(c.colors?.dark || {}) } },
      message: { ...base.message, ...(c.message || {}) },
      links: (c.links || []).map((l) => ({ ...l })),
      sections: (c.sections || []).map((s) => ({ ...s, id: s.id || uid(), items: (s.items || []).map((i) => ({ ...i, id: i.id || uid() })) })),
    },
  }
}

async function load() {
  try {
    const d = await api.get(`/api/dashboards/id/${route.params.id}/edit`)
    original.value = d
    form.value = normalize(d)
    snapshot.value = JSON.stringify(form.value)
    if (form.value.config.sections[0]) open[form.value.config.sections[0].id] = true
  } catch (e) {
    loadError.value = e.status === 404 ? 'Dashboard not found or insufficient rights.' : e.message
  }
}

async function save() {
  saving.value = true
  try {
    const f = form.value
    const payload = { title: f.title, subtitle: f.subtitle, logo: f.logo, config: f.config }
    const saved = isAdmin.value
      ? await api.put(`/api/admin/dashboards/${f.id}`, { ...payload, slug: f.slug, visibility: f.visibility, position: f.position })
      : await api.put(`/api/dashboards/id/${f.id}/content`, payload)
    original.value = saved
    form.value = normalize(saved)
    snapshot.value = JSON.stringify(form.value)
    notify('Dashboard saved')
  } catch (e) {
    notify(e.message, 'error')
  } finally {
    saving.value = false
  }
}

function toggle(id) {
  open[id] = !open[id]
}
function move(list, i, delta) {
  const j = i + delta
  if (j < 0 || j >= list.length) return
  const [x] = list.splice(i, 1)
  list.splice(j, 0, x)
}
function addSection() {
  const s = { id: uid(), name: 'New section', icon: '', items: [] }
  form.value.config.sections.push(s)
  open[s.id] = true
}
function removeSection(i) {
  const s = form.value.config.sections[i]
  if (s.items.length && !confirm(`Delete section "${s.name}" and its ${s.items.length} link(s)?`)) return
  form.value.config.sections.splice(i, 1)
}
function addItem(s) {
  const it = { id: uid(), name: '', subtitle: '', url: 'https://', icon: 'fa-solid fa-link', logo: '', tag: '', tagstyle: '', target: '_blank', keywords: '', background: '', status_check: false, status_url: '', status_ignore_tls: false }
  s.items.push(it)
  open[it.id] = true
}
function duplicateItem(s, i) {
  s.items.splice(i + 1, 0, { ...s.items[i], id: uid(), name: `${s.items[i].name} (copy)` })
}
function moveItem(si, ii, to) {
  if (to < 0) return
  const [it] = form.value.config.sections[si].items.splice(ii, 1)
  form.value.config.sections[to].items.push(it)
  open[form.value.config.sections[to].id] = true
}

const yamlWarnings = ref([])

function applyYaml() {
  try {
    const src = parseHomer(yamlText.value)
    // Images already uploaded to the portal (/api/uploads/…) are kept: e.g. a re-imported export
    const local = {}
    for (const v of [src.logo, ...(src.services || []).flatMap((s) => (s?.items || []).map((i) => i?.logo))]) {
      if (typeof v === 'string' && v.startsWith('/api/uploads/')) local[v] = v
    }
    const imported = convertHomer(src, { images: local })
    form.value.title = imported.title || form.value.title
    form.value.subtitle = imported.subtitle
    form.value.logo = imported.logo
    form.value.config = normalize({ config: imported.config }).config
    yamlWarnings.value = imported.warnings
    notify(imported.warnings.length ? `YAML imported with ${imported.warnings.length} warning(s) — see below` : 'YAML imported — check the preview, then save')
    if (!imported.warnings.length) tab.value = 'sections'
  } catch (e) {
    yamlWarnings.value = []
    notify(`Invalid YAML: ${e.message}`, 'error')
  }
}
async function loadYamlFile(e) {
  const f = e.target.files?.[0]
  e.target.value = ''
  if (f) yamlText.value = await f.text()
}
function downloadYaml() {
  const blob = new Blob([exportHomer(form.value)], { type: 'text/yaml' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${form.value.slug || 'dashboard'}.yml`
  a.click()
  URL.revokeObjectURL(a.href)
}

function beforeUnload(e) {
  if (dirty.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}
onBeforeRouteLeave(() => (dirty.value ? confirm('Leave without saving your changes?') : true))
onMounted(() => {
  load()
  window.addEventListener('beforeunload', beforeUnload)
})
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
</script>

<style scoped>
.editor-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
}
.editor-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: var(--ui-surface);
  border-bottom: 1px solid var(--ui-border);
  flex-wrap: wrap;
}
.bar-title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.spacer {
  flex: 1;
}
.editor-body {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(380px, 520px) 1fr;
  min-height: 0;
}
.editor-panel {
  overflow-y: auto;
  padding: 0 18px 40px;
  background: var(--ui-surface);
  border-right: 1px solid var(--ui-border);
}
.editor-panel .tabs {
  position: sticky;
  top: 0;
  background: var(--ui-surface);
  z-index: 2;
  margin: 0 -18px 16px;
  padding: 0 10px;
}
.preview-pane {
  overflow-y: auto;
  padding: 18px;
  background: var(--ui-bg);
}
.preview-frame {
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.15);
  min-height: calc(100% - 4px);
  display: flex;
}
.preview-frame > * {
  flex: 1;
}
.sub {
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--ui-muted);
  margin: 18px 0 10px;
}
.sub:first-child {
  margin-top: 0;
}
.seg {
  display: flex;
  gap: 4px;
  padding: 3px;
  border-radius: 9px;
  background: var(--ui-surface-2);
  border: 1px solid var(--ui-border);
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.seg button {
  flex: 1;
  font: inherit;
  font-size: 0.85rem;
  border: none;
  background: none;
  color: var(--ui-muted);
  padding: 7px 8px;
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
.colors-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 12px;
}
.block {
  border: 1px solid var(--ui-border);
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 12px;
  background: var(--ui-surface);
}
.block-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.block-head .spacer,
.grow {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}
.block-head + .row,
.block-body {
  margin-top: 12px;
}
.item {
  border: 1px solid var(--ui-border);
  border-radius: 8px;
  margin-bottom: 8px;
  background: var(--ui-surface-2);
}
.item-head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  cursor: pointer;
}
.item-icon {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--brand);
  flex-shrink: 0;
}
.item-icon img {
  max-width: 100%;
  max-height: 100%;
}
.item-body {
  padding: 4px 12px 2px;
  border-top: 1px solid var(--ui-border);
  background: var(--ui-surface);
  border-radius: 0 0 8px 8px;
  padding-top: 12px;
}
.ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.small {
  font-size: 0.82rem;
}
.yaml {
  min-height: 340px;
  font-size: 0.82rem;
  white-space: pre;
}
.mobile-only {
  display: none;
}
.yaml-warnings {
  margin: 6px 0 0;
  padding-left: 20px;
  font-size: 0.85rem;
}
.status-box {
  border: 1px dashed var(--ui-border);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 14px;
}
input[type='range'] {
  accent-color: var(--brand);
}

@media (max-width: 900px) {
  .editor-body {
    grid-template-columns: 1fr;
  }
  .preview-pane {
    display: none;
  }
  .editor-body.show-preview .preview-pane {
    display: block;
    padding: 0;
  }
  .editor-body.show-preview .editor-panel {
    display: none;
  }
  .mobile-only {
    display: inline-flex;
  }
  .colors-grid {
    grid-template-columns: 1fr;
  }
}
</style>
