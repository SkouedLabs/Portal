<template>
  <div class="portal" :class="[`theme-${effectiveTheme}`, { preview }]" :style="cssVars">
    <div class="portal-bg" :style="bgStyle"></div>
    <div v-if="hasOverlay" class="portal-overlay" :style="{ opacity: cfg.background.overlay }"></div>

    <div class="portal-inner">
      <header v-if="cfg.show_header" class="portal-header">
        <div class="portal-container header-line">
          <div class="logo">
            <img v-if="logoSrc" :src="logoSrc" alt="" />
            <i v-else class="fa-solid fa-house-chimney"></i>
          </div>
          <div class="titles">
            <span class="headline">{{ dashboard.subtitle }}</span>
            <h1>{{ dashboard.title }}</h1>
          </div>
          <div class="header-actions"><slot name="actions" /></div>
        </div>
      </header>

      <nav class="portal-navbar">
        <div class="portal-container nav-line">
          <div class="nav-left">
            <div v-if="dashboards.length > 1" class="switcher" @keydown.escape="switcherOpen = false">
              <button class="nav-item" :aria-expanded="switcherOpen" @click="switcherOpen = !switcherOpen">
                <i class="fa-solid fa-table-cells-large"></i>
                <span>Dashboards</span>
                <i class="fa-solid fa-chevron-down small"></i>
              </button>
              <div v-if="switcherOpen" class="dropdown" @click="switcherOpen = false">
                <router-link
                  v-for="d in dashboards"
                  :key="d.id"
                  :to="`/d/${d.slug}`"
                  class="dropdown-item"
                  :class="{ active: d.slug === dashboard.slug }"
                >
                  <img v-if="d.logo" :src="d.logo" alt="" />
                  <i v-else class="fa-solid fa-table-columns"></i>
                  <span>{{ d.title }}</span>
                </router-link>
              </div>
            </div>
            <a
              v-for="(l, i) in cfg.links"
              :key="i"
              class="nav-item"
              :href="l.url || '#'"
              :target="l.target || '_self'"
              rel="noopener noreferrer"
              @click="onLink($event, l.name, l.url, 'navbar')"
              @auxclick="onLink($event, l.name, l.url, 'navbar')"
            >
              <i v-if="l.icon" :class="l.icon"></i>
              <span>{{ l.name }}</span>
            </a>
          </div>
          <div class="nav-right">
            <div class="search">
              <i class="fa-solid fa-magnifying-glass"></i>
              <input
                ref="searchInput"
                v-model="search"
                type="search"
                placeholder="Search…"
                aria-label="Search"
                @keydown.enter="openFirst"
                @keydown.escape="search = ''"
              />
            </div>
            <button class="nav-item icon" :title="layout === 'list' ? 'Column view' : 'List view'" @click="toggleLayout">
              <i :class="layout === 'list' ? 'fa-solid fa-table-columns' : 'fa-solid fa-list'"></i>
            </button>
            <button class="nav-item icon" title="Light / dark / auto theme" @click="cycleTheme">
              <i :class="themeIcon"></i>
            </button>
          </div>
        </div>
      </nav>

      <main class="portal-container portal-main">
        <article v-if="cfg.message.enabled && (cfg.message.title || cfg.message.content)" class="message" :class="cfg.message.style">
          <div v-if="cfg.message.title" class="message-header">
            <i v-if="cfg.message.icon" :class="cfg.message.icon"></i>
            <span>{{ cfg.message.title }}</span>
          </div>
          <div v-if="cfg.message.content" class="message-body">{{ cfg.message.content }}</div>
        </article>

        <div v-if="!filteredSections.length" class="no-results">
          <i class="fa-regular fa-folder-open"></i>
          <p>{{ search ? 'No results for this search.' : 'This dashboard is empty.' }}</p>
        </div>

        <div class="sections" :class="`layout-${layout}`" :style="gridStyle">
          <section v-for="s in filteredSections" :key="s.id || s.name" class="section">
            <h2 v-if="s.name" class="section-title">
              <i v-if="s.icon" :class="s.icon"></i>
              <span>{{ s.name }}</span>
            </h2>
            <div class="items">
              <a
                v-for="item in s.items"
                :key="item.id || item.name"
                class="card"
                :href="item.url || '#'"
                :target="item.target || '_self'"
                rel="noopener noreferrer"
                :style="item.background ? { background: item.background } : null"
                @click="onLink($event, item.name, item.url, s.name)"
                @auxclick="onLink($event, item.name, item.url, s.name)"
              >
                <div class="card-media">
                  <img v-if="item.logo" :src="item.logo" alt="" loading="lazy" />
                  <i v-else-if="item.icon" :class="item.icon"></i>
                  <span v-else class="letter">{{ (item.name || '?').charAt(0).toUpperCase() }}</span>
                </div>
                <div class="card-content">
                  <p class="card-title">{{ item.name }}</p>
                  <p v-if="item.subtitle" class="card-subtitle">{{ item.subtitle }}</p>
                </div>
                <span v-if="item.tag" class="tag" :class="item.tagstyle">#{{ item.tag }}</span>
                <span
                  v-if="item.status_check"
                  class="status-dot"
                  :class="`st-${statusOf(item).state}`"
                  :title="statusTitle(item)"
                  role="img"
                  :aria-label="statusTitle(item)"
                ></span>
              </a>
            </div>
          </section>
        </div>
      </main>

      <footer v-if="footerText" class="portal-footer">{{ footerText }}</footer>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import { prefersDark, state, storage } from '../store'
import { DEFAULT_COLORS, emptyConfig } from '../theme'

const props = defineProps({
  dashboard: { type: Object, required: true },
  dashboards: { type: Array, default: () => [] },
  preview: { type: Boolean, default: false },
})

const cfg = computed(() => {
  const base = emptyConfig()
  const c = props.dashboard.config || {}
  return {
    ...base,
    ...c,
    background: { ...base.background, ...(c.background || {}) },
    colors: { light: { ...(c.colors?.light || {}) }, dark: { ...(c.colors?.dark || {}) } },
    message: { ...base.message, ...(c.message || {}) },
    links: c.links || [],
    sections: c.sections || [],
  }
})

const search = ref('')
const searchInput = ref(null)
const switcherOpen = ref(false)
const themePref = ref(storage.get('theme', null))
const systemDark = ref(prefersDark())
const layoutKey = computed(() => `layout:${props.dashboard.id ?? 'preview'}`)
const layoutPref = ref(storage.get(layoutKey.value, null))
watch(layoutKey, (k) => (layoutPref.value = storage.get(k, null)))

const layout = computed(() => layoutPref.value || cfg.value.default_layout || 'columns')
const themeMode = computed(() => themePref.value || cfg.value.default_theme || 'auto')
const effectiveTheme = computed(() =>
  themeMode.value === 'auto' ? (systemDark.value ? 'dark' : 'light') : themeMode.value,
)
const themeIcon = computed(
  () => ({ light: 'fa-solid fa-sun', dark: 'fa-solid fa-moon', auto: 'fa-solid fa-circle-half-stroke' })[themeMode.value],
)

const logoSrc = computed(() => props.dashboard.logo || state.config?.branding?.logo || '')
const footerText = computed(() => cfg.value.footer || state.config?.branding?.footer || '')

const cssVars = computed(() => {
  const theme = effectiveTheme.value
  const merged = { ...DEFAULT_COLORS[theme] }
  for (const [k, v] of Object.entries(cfg.value.colors[theme] || {})) if (v) merged[k] = v
  const vars = {}
  for (const [k, v] of Object.entries(merged)) vars[`--${k.replaceAll('_', '-')}`] = v
  return vars
})

const hasOverlay = computed(() => cfg.value.background.type === 'image' && cfg.value.background.overlay > 0)

const bgStyle = computed(() => {
  const b = cfg.value.background
  switch (b.type) {
    case 'color':
      return { background: b.color || 'var(--background)' }
    case 'gradient':
      return {
        background: `linear-gradient(${b.gradient_angle || 135}deg, ${b.gradient_from || 'var(--highlight-primary)'}, ${b.gradient_to || 'var(--background)'})`,
      }
    case 'image':
      return b.image
        ? {
            backgroundImage: `url("${b.image}")`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            filter: b.blur ? `blur(${b.blur}px)` : null,
            inset: b.blur ? `-${b.blur * 2}px` : 0,
          }
        : { background: 'var(--background)' }
    default:
      return { background: 'var(--background)' }
  }
})

const gridStyle = computed(() => {
  if (layout.value === 'list') return null
  const c = cfg.value.columns
  return c === 'auto'
    ? { gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }
    : { '--cols': c }
})

const filteredSections = computed(() => {
  const q = search.value.trim().toLowerCase()
  const sections = cfg.value.sections.filter((s) => s.items?.length || s.name)
  if (!q) return sections.filter((s) => s.items?.length)
  return sections
    .map((s) => ({
      ...s,
      items: s.items.filter((i) =>
        [i.name, i.subtitle, i.tag, i.keywords, s.name].some((v) => v && v.toLowerCase().includes(q)),
      ),
    }))
    .filter((s) => s.items.length)
})

function onLink(event, label, url, section) {
  if (props.preview) {
    event.preventDefault()
    return
  }
  if (event.type === 'auxclick' && event.button !== 1) return
  if (!url) return
  api.logClick({ dashboard_id: props.dashboard.id, label: label || '', url, section: section || '' })
}

function openFirst() {
  const first = filteredSections.value[0]?.items[0]
  if (!first?.url || props.preview) return
  api.logClick({ dashboard_id: props.dashboard.id, label: first.name, url: first.url, section: 'search' })
  if (first.target === '_blank') window.open(first.url, '_blank', 'noopener,noreferrer')
  else window.location.href = first.url
}

function toggleLayout() {
  layoutPref.value = layout.value === 'list' ? 'columns' : 'list'
  storage.set(layoutKey.value, layoutPref.value)
}

function cycleTheme() {
  const order = ['light', 'dark', 'auto']
  themePref.value = order[(order.indexOf(themeMode.value) + 1) % order.length]
  storage.set('theme', themePref.value)
}

// --- Status checks (polled from the backend; not in preview) ---
const statuses = ref({})
let statusTimer = null
const hasChecks = computed(() => cfg.value.sections.some((s) => (s.items || []).some((i) => i.status_check)))

function statusOf(item) {
  return statuses.value[item.id || item.name] || { state: props.preview ? 'preview' : 'pending' }
}
function statusTitle(item) {
  const s = statusOf(item)
  if (s.state === 'preview') return 'Status check (shown on the dashboard)'
  if (s.state === 'pending') return 'Checking…'
  const label = { up: 'Online', warn: 'Reachable, client error', down: 'Offline' }[s.state] || s.state
  return [label, s.code ? `HTTP ${s.code}` : '', s.latency_ms != null ? `${s.latency_ms} ms` : '', s.error || ''].filter(Boolean).join(' · ')
}
async function pollStatus() {
  if (props.preview || !hasChecks.value || !props.dashboard.slug || document.hidden) return
  try {
    const r = await api.get(`/api/dashboards/${encodeURIComponent(props.dashboard.slug)}/status`, { silent: true })
    statuses.value = r.items || {}
  } catch {
    /* keep the last known state */
  }
}
function scheduleStatus() {
  clearInterval(statusTimer)
  statuses.value = {}
  if (props.preview || !hasChecks.value) return
  pollStatus()
  statusTimer = setInterval(pollStatus, Math.max(15, cfg.value.status_interval || 60) * 1000)
}
watch(() => props.dashboard.id, scheduleStatus)

let mq
function onMq(e) {
  systemDark.value = e.matches
}
function onKey(e) {
  if (props.preview) return
  const tag = document.activeElement?.tagName
  if (e.key === '/' && tag !== 'INPUT' && tag !== 'TEXTAREA') {
    e.preventDefault()
    searchInput.value?.focus()
  }
}
function onDocClick(e) {
  if (!e.target.closest?.('.switcher')) switcherOpen.value = false
}
onMounted(() => {
  mq = window.matchMedia?.('(prefers-color-scheme: dark)')
  mq?.addEventListener?.('change', onMq)
  document.addEventListener('keydown', onKey)
  document.addEventListener('click', onDocClick)
  scheduleStatus()
})
onBeforeUnmount(() => {
  mq?.removeEventListener?.('change', onMq)
  document.removeEventListener('keydown', onKey)
  document.removeEventListener('click', onDocClick)
  clearInterval(statusTimer)
})
</script>

<style scoped>
.portal {
  position: relative;
  min-height: 100%;
  color: var(--text);
  isolation: isolate;
  overflow: hidden;
}
.portal:not(.preview) {
  min-height: 100vh;
}
.portal-bg {
  position: absolute;
  inset: 0;
  z-index: -2;
}
.portal:not(.preview) .portal-bg {
  position: fixed;
}
.portal-overlay {
  position: fixed;
  inset: 0;
  z-index: -1;
  background: #000;
}
.portal.preview .portal-overlay {
  position: absolute;
}
.portal-inner {
  display: flex;
  flex-direction: column;
  min-height: inherit;
}
.portal-container {
  width: 100%;
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 24px;
}

/* Header */
.portal-header {
  background: var(--highlight-primary);
  color: var(--text-header);
}
.header-line {
  display: flex;
  align-items: center;
  gap: 18px;
  min-height: 100px;
}
.logo {
  width: 54px;
  height: 54px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 2.2rem;
}
.logo img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
.titles {
  flex: 1;
  min-width: 0;
}
.headline {
  font-size: 0.85rem;
  opacity: 0.85;
  display: block;
}
.titles h1 {
  margin: 0;
  font-size: 1.9rem;
  font-weight: 600;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Navigation */
.portal-navbar {
  background: var(--highlight-secondary);
  color: var(--text-header);
  position: relative;
  z-index: 5;
}
.nav-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 52px;
  flex-wrap: wrap;
}
.nav-left,
.nav-right {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-wrap: wrap;
}
.nav-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-header);
  background: none;
  border: none;
  font: inherit;
  font-size: 0.95rem;
  padding: 9px 12px;
  border-radius: 6px;
  cursor: pointer;
  text-decoration: none;
}
.nav-item:hover,
.nav-item[aria-expanded='true'] {
  background: var(--highlight-hover);
}
.nav-item .small {
  font-size: 0.7rem;
}
.switcher {
  position: relative;
}
.dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  min-width: 240px;
  max-height: 60vh;
  overflow-y: auto;
  background: var(--card-background);
  color: var(--text);
  border-radius: 8px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
  padding: 6px;
}
.dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: 6px;
  color: inherit;
  text-decoration: none;
}
.dropdown-item img {
  width: 20px;
  height: 20px;
  object-fit: contain;
}
.dropdown-item i {
  width: 20px;
  text-align: center;
  color: var(--highlight-primary);
}
.dropdown-item:hover {
  background: color-mix(in srgb, var(--highlight-hover) 18%, transparent);
}
.dropdown-item.active {
  font-weight: 700;
}
.search {
  position: relative;
  display: flex;
  align-items: center;
  margin-right: 4px;
}
.search i {
  position: absolute;
  left: 11px;
  font-size: 0.85rem;
  opacity: 0.8;
  pointer-events: none;
}
.search input {
  font: inherit;
  font-size: 0.92rem;
  width: 220px;
  padding: 7px 10px 7px 32px;
  border-radius: 6px;
  border: 1px solid transparent;
  background: rgba(255, 255, 255, 0.18);
  color: var(--text-header);
  outline: none;
}
.search input::placeholder {
  color: var(--text-header);
  opacity: 0.75;
}
.search input:focus {
  background: rgba(255, 255, 255, 0.28);
  border-color: rgba(255, 255, 255, 0.5);
}

/* Content */
.portal-main {
  flex: 1;
  padding-top: 26px;
  padding-bottom: 36px;
}
.message {
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 26px;
  background: var(--card-background);
  box-shadow: 0 0 9px rgba(0, 0, 0, 0.1);
  --msg: #3e8ed0;
}
.message.is-success { --msg: #48c78e; }
.message.is-warning { --msg: #e6a700; }
.message.is-danger { --msg: #f14668; }
.message.is-dark { --msg: #363636; }
.message-header {
  background: var(--msg);
  color: #fff;
  font-weight: 700;
  padding: 10px 16px;
  display: flex;
  gap: 10px;
  align-items: center;
}
.message-body {
  padding: 14px 16px;
  border-left: 4px solid var(--msg);
  white-space: pre-line;
  color: var(--text);
}

.sections.layout-columns {
  display: grid;
  grid-template-columns: repeat(var(--cols, 3), minmax(0, 1fr));
  gap: 22px 26px;
  align-items: start;
}
.sections.layout-list .section + .section {
  margin-top: 26px;
}
.sections.layout-list .items {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}
.section-title {
  font-size: 1.2rem;
  font-weight: 600;
  margin: 0 0 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text);
}
.portal:has(.portal-bg[style*='url']) .section-title,
.portal:has(.portal-bg[style*='gradient']) .section-title {
  text-shadow: 0 1px 6px rgba(0, 0, 0, 0.35);
}
.items {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 18px;
  min-height: 84px;
  background: var(--card-background);
  border-radius: 6px;
  box-shadow: 0 0 9px rgba(0, 0, 0, 0.12);
  color: var(--text);
  text-decoration: none;
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}
.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.18);
}
.card:focus-visible {
  outline: 3px solid var(--highlight-hover);
  outline-offset: 2px;
}
.card-media {
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.9rem;
  color: var(--highlight-primary);
}
.card-media img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
.letter {
  width: 46px;
  height: 46px;
  border-radius: 10px;
  background: var(--highlight-secondary);
  color: #fff;
  font-weight: 700;
  font-size: 1.3rem;
  display: flex;
  align-items: center;
  justify-content: center;
}
.card-content {
  min-width: 0;
  flex: 1;
}
.card-title {
  margin: 0;
  font-size: 1.12rem;
  font-weight: 600;
  color: var(--text-title);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-subtitle {
  margin: 3px 0 0;
  font-size: 0.88rem;
  color: var(--text-subtitle);
  opacity: 0.85;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tag {
  position: absolute;
  right: 0;
  bottom: 12px;
  font-size: 0.72rem;
  color: #fff;
  background: var(--highlight-secondary);
  padding: 2px 8px 2px 10px;
  border-radius: 8px 0 0 8px;
}
.tag.is-info { background: #3e8ed0; }
.tag.is-success { background: #48c78e; }
.tag.is-warning { background: #e6a700; }
.tag.is-danger { background: #f14668; }
.tag.is-primary { background: var(--highlight-primary); }

.status-dot {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #9ca3af;
  box-shadow: 0 0 0 2px var(--card-background);
}
.status-dot.st-up { background: #22c55e; }
.status-dot.st-warn { background: #f59e0b; }
.status-dot.st-down { background: #ef4444; animation: pulse 1.6s ease-in-out infinite; }
.status-dot.st-pending { background: #9ca3af; animation: pulse 1.6s ease-in-out infinite; }
@keyframes pulse {
  50% { opacity: 0.35; }
}
@media (prefers-reduced-motion: reduce) {
  .status-dot { animation: none !important; }
}

.no-results {
  text-align: center;
  opacity: 0.75;
  padding: 50px 0;
}
.no-results i {
  font-size: 2.4rem;
  margin-bottom: 10px;
}
.portal-footer {
  text-align: center;
  font-size: 0.85rem;
  padding: 18px;
  background: color-mix(in srgb, var(--card-background) 70%, transparent);
  color: var(--text);
  white-space: pre-line;
}

@media (max-width: 1100px) {
  .sections.layout-columns {
    grid-template-columns: repeat(min(var(--cols, 3), 2), minmax(0, 1fr));
  }
}
@media (max-width: 720px) {
  .portal-container {
    padding: 0 16px;
  }
  .sections.layout-columns {
    grid-template-columns: minmax(0, 1fr) !important;
  }
  .header-line {
    min-height: 76px;
    gap: 12px;
  }
  .logo {
    width: 40px;
    height: 40px;
    font-size: 1.6rem;
  }
  .titles h1 {
    font-size: 1.35rem;
  }
  .nav-right,
  .search,
  .search input {
    flex: 1;
    width: 100%;
  }
  .nav-line {
    padding-bottom: 8px;
  }
}

/* The editor preview is rendered in a narrow pane */
.portal.preview .sections.layout-columns {
  grid-template-columns: repeat(min(var(--cols, 3), 2), minmax(0, 1fr));
}
</style>
