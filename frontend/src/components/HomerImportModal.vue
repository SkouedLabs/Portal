<template>
  <Modal title="Import from Homer" wide @close="$emit('close')">
    <!-- 1. Source -->
    <template v-if="step === 'select'">
      <p class="muted intro">
        Migrate an existing <a href="https://github.com/bastienwirtz/homer" target="_blank" rel="noopener noreferrer">Homer</a> dashboard.
        Easiest: select Homer's <code>assets</code> folder. Its <code>config.yml</code>, additional pages (<code>page2.yml</code>…)
        and the logos they use are imported together; images are uploaded to the portal (no internet needed afterwards).
      </p>
      <div class="sources">
        <label class="source">
          <i class="fa-solid fa-folder-open"></i>
          <strong>Select the assets folder</strong>
          <small>config.yml, pages and images</small>
          <input type="file" webkitdirectory multiple hidden @change="addFiles($event, true)" />
        </label>
        <label class="source">
          <i class="fa-solid fa-file-import"></i>
          <strong>Select files</strong>
          <small>.yml files, and optionally the images they reference</small>
          <input type="file" multiple accept=".yml,.yaml,image/*,.ico,.svg" hidden @change="addFiles($event, false)" />
        </label>
      </div>
      <p v-if="files.length" class="picked">
        <i class="fa-solid fa-check"></i> {{ ymlCount }} YAML file(s), {{ imageCount }} image(s) selected
        <button class="btn ghost sm" @click="files = []">Clear</button>
      </p>
      <details class="paste" :open="!!pasted">
        <summary>Or paste a config.yml</summary>
        <textarea v-model="pasted" class="input mono" rows="8" spellcheck="false" placeholder="title: &quot;My dashboard&quot;&#10;services:&#10;  - name: …"></textarea>
        <p class="hint muted">Local images referenced by a pasted configuration cannot be uploaded: they are removed (remote URLs are kept).</p>
      </details>
      <div v-if="error" class="alert error">{{ error }}</div>
    </template>

    <!-- 2. Review -->
    <template v-else-if="step === 'review'">
      <p class="muted intro">Check what will be created. Nothing is saved until you click "Import".</p>
      <div v-for="d in drafts" :key="d.key" class="draft" :class="{ off: !d.include }">
        <div class="draft-head">
          <label class="check"><input v-model="d.include" type="checkbox" :disabled="d.err" /></label>
          <div class="draft-file mono">{{ d.file }}<span v-if="d.page" class="badge">page {{ d.page }}</span></div>
          <span v-if="d.homer" class="stats muted">{{ preview(d).stats.sections }} section(s) · {{ preview(d).stats.items }} link(s) · {{ preview(d).stats.links }} nav link(s)</span>
        </div>
        <div v-if="d.include" class="row">
          <div class="field"><label>Title</label><input v-model="d.title" class="input sm" /></div>
          <div class="field">
            <label>URL slug</label>
            <input v-model="d.slug" class="input sm mono" :class="{ invalid: slugError(d) }" />
            <span v-if="slugError(d)" class="hint err">{{ slugError(d) }}</span>
          </div>
          <div class="field">
            <label>Visibility</label>
            <select v-model="d.visibility" class="input sm">
              <option value="restricted">Restricted</option>
              <option value="authenticated">All signed-in users</option>
            </select>
          </div>
        </div>
        <div v-if="d.include && d.refs.length" class="images">
          <i class="fa-regular fa-image"></i>
          {{ d.refs.filter((r) => r.file).length }} / {{ d.refs.length }} image(s) found
          <span v-if="d.refs.some((r) => !r.file)" class="muted">
            — missing: {{ d.refs.filter((r) => !r.file).map((r) => r.ref).slice(0, 4).join(', ') }}{{ d.refs.filter((r) => !r.file).length > 4 ? '…' : '' }}
          </span>
        </div>
        <details v-if="d.include && preview(d).warnings.length" class="warnings">
          <summary><i class="fa-solid fa-triangle-exclamation"></i> {{ preview(d).warnings.length }} point(s) not converted</summary>
          <ul>
            <li v-for="w in preview(d).warnings" :key="w">{{ w }}</li>
          </ul>
        </details>
        <p v-if="d.note" class="hint muted">{{ d.note }}</p>
      </div>
    </template>

    <!-- 3. Import / result -->
    <template v-else>
      <p v-if="step === 'importing'"><i class="fa-solid fa-spinner fa-spin"></i> {{ progress }}</p>
      <ul v-else class="results">
        <li v-for="r in results" :key="r.slug">
          <template v-if="r.ok">
            <i class="fa-solid fa-circle-check ok"></i>
            <strong>{{ r.title }}</strong> <span class="muted mono">/d/{{ r.slug }}</span>
            <span class="spacer"></span>
            <a :href="`/d/${r.slug}`" target="_blank" class="btn sm"><i class="fa-solid fa-up-right-from-square"></i> Open</a>
            <router-link :to="`/edit/${r.id}?from=admin`" class="btn sm"><i class="fa-solid fa-pen"></i> Edit</router-link>
          </template>
          <template v-else>
            <i class="fa-solid fa-circle-xmark bad"></i> <strong>{{ r.title }}</strong> — {{ r.error }}
          </template>
        </li>
      </ul>
      <p v-if="step === 'done'" class="muted small">
        {{ uploaded }} image(s) uploaded. New dashboards are <strong>restricted</strong> unless you chose otherwise: set their access rules in the list.
      </p>
    </template>

    <template #footer>
      <template v-if="step === 'select'">
        <button class="btn" @click="$emit('close')">Cancel</button>
        <button class="btn primary" :disabled="!ymlCount && !pasted.trim()" @click="analyse">
          <i class="fa-solid fa-magnifying-glass"></i> Analyse
        </button>
      </template>
      <template v-else-if="step === 'review'">
        <button class="btn" @click="step = 'select'">Back</button>
        <button class="btn primary" :disabled="!canImport" @click="runImport">
          <i class="fa-solid fa-file-import"></i> Import {{ drafts.filter((d) => d.include).length }} dashboard(s)
        </button>
      </template>
      <button v-else-if="step === 'done'" class="btn primary" @click="$emit('close')">Close</button>
    </template>
  </Modal>
</template>

<script setup>
import { computed, ref } from 'vue'
import { api } from '../api'
import { convertHomer, homerImageRefs, matchImageFile, mergeHomerPage, parseHomer } from '../homerYaml'
import Modal from './Modal.vue'

const props = defineProps({ existingSlugs: { type: Array, default: () => [] }, nextPosition: { type: Number, default: 0 } })
const emit = defineEmits(['close', 'imported'])

const YML = /\.ya?ml$/i
const IMG = /\.(png|jpe?g|gif|webp|svg|ico)$/i
const SLUG = /^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$/

const step = ref('select')
const files = ref([])
const pasted = ref('')
const error = ref('')
const drafts = ref([])
const results = ref([])
const progress = ref('')
const uploaded = ref(0)

const ymlCount = computed(() => files.value.filter((f) => YML.test(f.name)).length)
const imageCount = computed(() => files.value.filter((f) => IMG.test(f.name)).length)

function addFiles(e, folder) {
  const list = [...(e.target.files || [])].filter((f) => YML.test(f.name) || IMG.test(f.name))
  e.target.value = ''
  // A new folder replaces the previous selection; individual files are added
  files.value = folder ? list : [...files.value, ...list.filter((f) => !files.value.some((x) => x.name === f.name && x.size === f.size))]
  error.value = list.length ? '' : 'No YAML or image file in this selection.'
}

const slugify = (s) =>
  s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 64) || 'dashboard'

function uniqueSlug(base, taken) {
  let s = base
  let n = 2
  while (taken.has(s)) s = `${base.slice(0, 60)}-${n++}`
  taken.add(s)
  return s
}

function slugError(d) {
  if (!d.include) return ''
  if (!SLUG.test(d.slug)) return 'Lowercase letters, digits and dashes only'
  if (props.existingSlugs.includes(d.slug)) return 'Already used by an existing dashboard'
  if (drafts.value.some((o) => o !== d && o.include && o.slug === d.slug)) return 'Used twice in this import'
  return ''
}
// Homer page links (#page2) -> new dashboards, according to what is currently ticked
function pageLinksFor(chosen) {
  const links = Object.fromEntries(chosen.filter((d) => d.page).map((d) => [`#${d.page}`, `/d/${d.slug}`]))
  const main = chosen.find((d) => !d.page)
  if (main) links['#'] = `/d/${main.slug}`
  return links
}

// Live preview (counts and warnings) of a draft: follows the checkboxes and slugs
function preview(d) {
  if (!d.src) return { stats: { sections: 0, items: 0, links: 0 }, warnings: [] }
  const found = Object.fromEntries(d.refs.filter((r) => r.file).map((r) => [r.ref, '/pending']))
  const conv = convertHomer(d.src, { images: found, pageLinks: pageLinksFor(drafts.value.filter((x) => x.include)) })
  // Missing images are listed separately
  return { stats: conv.stats, warnings: conv.warnings.filter((w) => !w.includes('not found in the selected files')) }
}

const canImport = computed(() => drafts.value.some((d) => d.include) && drafts.value.every((d) => !slugError(d) && (!d.include || d.title.trim())))

async function analyse() {
  error.value = ''
  try {
    const sources = []
    for (const f of files.value.filter((x) => YML.test(x.name))) {
      sources.push({ file: f.webkitRelativePath || f.name, name: f.name.replace(YML, ''), text: await f.text() })
    }
    if (pasted.value.trim()) sources.push({ file: 'pasted config.yml', name: 'config', text: pasted.value })
    const parsed = []
    for (const s of sources) {
      try {
        parsed.push({ ...s, src: parseHomer(s.text) })
      } catch (e) {
        parsed.push({ ...s, err: e.message })
      }
    }
    // Main configuration: config.yml (Homer's), otherwise the first file
    const main = parsed.find((p) => !p.err && p.name.toLowerCase() === 'config') || parsed.find((p) => !p.err)
    if (!main) throw new Error(parsed[0]?.err || 'No readable YAML file')
    const images = files.value.filter((f) => IMG.test(f.name))
    const taken = new Set(props.existingSlugs)

    drafts.value = parsed.map((p) => {
      if (p.err) return { key: p.file, file: p.file, include: false, err: true, homer: false, title: p.name, slug: 'x', visibility: 'restricted', refs: [], note: `Not imported: ${p.err}` }
      const isPage = p !== main
      const src = isPage ? mergeHomerPage(main.src, p.src) : p.src
      const refs = homerImageRefs(src).map((ref) => ({ ref, file: matchImageFile(ref, images) }))
      const conv = convertHomer(src)
      const looksHomer = Array.isArray(p.src.services) || Array.isArray(p.src.links)
      const title = isPage && p.src.title === undefined ? `${conv.title} — ${p.name}` : conv.title
      return {
        key: p.file,
        file: p.file,
        page: isPage ? p.name : '',
        homer: looksHomer,
        src,
        refs,
        include: looksHomer || !isPage,
        title,
        slug: uniqueSlug(slugify(isPage ? `${slugify(conv.title)}-${p.name}` : conv.title), taken),
        visibility: 'restricted',
        note: looksHomer ? '' : 'No "services" or "links": probably not a Homer page, unticked.',
      }
    })
    step.value = 'review'
  } catch (e) {
    error.value = e.message
  }
}

async function runImport() {
  step.value = 'importing'
  const chosen = drafts.value.filter((d) => d.include)
  // 1. Upload each referenced image once
  const urlOf = new Map()
  const needed = [...new Set(chosen.flatMap((d) => d.refs.filter((r) => r.file).map((r) => r.file)))]
  uploaded.value = 0
  for (const [i, f] of needed.entries()) {
    progress.value = `Uploading images… ${i + 1} / ${needed.length}`
    try {
      urlOf.set(f, (await api.upload(f)).url)
      uploaded.value++
    } catch {
      /* reported below as a missing image */
    }
  }
  // 2. Homer page links (#page2) point to the new dashboards
  const pageLinks = pageLinksFor(chosen)

  // 3. Create the dashboards
  results.value = []
  for (const [i, d] of chosen.entries()) {
    progress.value = `Creating "${d.title}"… ${i + 1} / ${chosen.length}`
    const images = Object.fromEntries(d.refs.filter((r) => urlOf.has(r.file)).map((r) => [r.ref, urlOf.get(r.file)]))
    const conv = convertHomer(d.src, { images, pageLinks })
    try {
      const created = await api.post('/api/admin/dashboards', {
        slug: d.slug,
        title: d.title.trim(),
        subtitle: conv.subtitle,
        logo: conv.logo,
        visibility: d.visibility,
        position: props.nextPosition + i,
        config: conv.config,
      })
      results.value.push({ ok: true, id: created.id, slug: d.slug, title: d.title })
    } catch (e) {
      results.value.push({ ok: false, slug: d.slug, title: d.title, error: e.message })
    }
  }
  step.value = 'done'
  emit('imported', results.value)
}
</script>

<style scoped>
.intro {
  margin-top: 0;
  font-size: 0.9rem;
}
.sources {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.source {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 20px 12px;
  border: 1px dashed var(--ui-border);
  border-radius: 10px;
  cursor: pointer;
  text-align: center;
}
.source:hover {
  border-color: var(--brand);
  background: color-mix(in srgb, var(--brand) 5%, transparent);
}
.source i {
  font-size: 1.6rem;
  color: var(--brand);
}
.source small {
  color: var(--ui-muted);
  font-size: 0.8rem;
}
.picked {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ui-success);
  font-size: 0.9rem;
}
.paste {
  margin-top: 14px;
}
.paste summary {
  cursor: pointer;
  color: var(--ui-muted);
  font-size: 0.9rem;
  margin-bottom: 8px;
}
.draft {
  border: 1px solid var(--ui-border);
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 12px;
}
.draft.off {
  opacity: 0.65;
}
.draft-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.draft-file {
  font-size: 0.85rem;
  display: flex;
  gap: 8px;
  align-items: center;
}
.stats {
  margin-left: auto;
  font-size: 0.8rem;
}
.draft .row {
  margin-top: 10px;
}
.draft .field {
  margin-bottom: 8px;
}
.invalid {
  border-color: var(--ui-danger);
}
.err {
  color: var(--ui-danger);
}
.images {
  font-size: 0.85rem;
  margin: 2px 0 6px;
}
.warnings summary {
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--ui-warning);
}
.warnings ul {
  margin: 6px 0 0;
  padding-left: 22px;
  font-size: 0.82rem;
  color: var(--ui-muted);
}
.results {
  list-style: none;
  padding: 0;
  margin: 0;
}
.results li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--ui-border);
  flex-wrap: wrap;
}
.spacer {
  flex: 1;
}
.ok {
  color: var(--ui-success);
}
.bad {
  color: var(--ui-danger);
}
.small {
  font-size: 0.85rem;
}
@media (max-width: 640px) {
  .sources {
    grid-template-columns: 1fr;
  }
}
</style>
