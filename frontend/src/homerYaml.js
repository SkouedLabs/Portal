// Conversion between Homer's config.yml format and the Portal-NG model.
//
// Import pipeline (used by Admin › Dashboards › "Import from Homer" and the editor YAML tab):
//   parseHomer(text)                  -> raw Homer object
//   mergeHomerPage(config, page)      -> Homer "additional page" (page2.yml…) merged over config.yml
//   homerImageRefs(src)               -> local image paths referenced (logos, background image)
//   convertHomer(src, { images, pageLinks }) -> { title, subtitle, logo, config, warnings, stats }
// Values are validated with the same rules as the server, so a converted dashboard always saves:
// what cannot be converted is dropped and reported in `warnings`.
import yaml from 'js-yaml'
import { emptyConfig, uid } from './theme'

const COLOR_KEYS = {
  'highlight-primary': 'highlight_primary',
  'highlight-secondary': 'highlight_secondary',
  'highlight-hover': 'highlight_hover',
  background: 'background',
  'card-background': 'card_background',
  text: 'text',
  'text-header': 'text_header',
  'text-title': 'text_title',
  'text-subtitle': 'text_subtitle',
  link: 'link',
}
const COLUMNS = ['auto', '1', '2', '3', '4', '6', '12']
const TAG_STYLES = ['is-info', 'is-success', 'is-warning', 'is-danger', 'is-primary']
const MESSAGE_STYLES = { 'is-info': 'is-info', 'is-success': 'is-success', 'is-warning': 'is-warning', 'is-danger': 'is-danger',
  'is-dark': 'is-dark', 'is-primary': 'is-info', 'is-link': 'is-info', 'is-light': 'is-info' }
// Top-level Homer options with no equivalent (reported once)
const UNSUPPORTED_TOP = {
  stylesheet: 'custom stylesheets',
  proxy: 'proxy options of smart cards',
  externalConfig: 'external configuration',
  hotkey: 'custom search hotkey',
}

// --- Same rules as the backend (backend/app/schemas.py) -----------------------
const FORBIDDEN_SCHEME = /^\s*(javascript|vbscript|data|file):/i
const CSS_UNSAFE = /["'()\\\s<>;{}]/
const COLOR_RE = /^(#[0-9a-fA-F]{3,8}|(rgb|rgba|hsl|hsla)\([0-9.,%\s/deg]+\)|[a-zA-Z]{3,30})$/
const ICON_RE = /^[a-z0-9 -]*$/

const str = (v) => (v === undefined || v === null ? '' : String(v)).trim()
const cut = (v, n = 255) => str(v).slice(0, n)
const stripHtml = (v) =>
  str(v)
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .trim()
const isRemote = (u) => /^https?:\/\//i.test(u)

export function parseHomer(text) {
  const src = yaml.load(text, { schema: yaml.JSON_SCHEMA })
  if (!src || typeof src !== 'object' || Array.isArray(src)) throw new Error('This file is not a Homer configuration (YAML object expected)')
  return src
}

/** Homer merges an additional page (assets/page2.yml) over config.yml: objects are merged, lists are replaced. */
export function mergeHomerPage(base, page) {
  const out = { ...base }
  for (const [k, v] of Object.entries(page || {})) {
    out[k] = v && typeof v === 'object' && !Array.isArray(v) && base[k] && typeof base[k] === 'object' && !Array.isArray(base[k])
      ? mergeHomerPage(base[k], v)
      : v
  }
  return out
}

const cssUrl = (v) => str(v).replace(/^url\(\s*["']?/i, '').replace(/["']?\s*\)$/, '')

/** Local (non http) image references of a Homer config: they must be uploaded to the portal. */
export function homerImageRefs(src) {
  const refs = new Set()
  const add = (v) => {
    const s = str(v)
    if (s && !isRemote(s) && !s.startsWith('data:')) refs.add(s)
  }
  add(src.logo)
  for (const t of ['light', 'dark']) add(cssUrl(src.colors?.[t]?.['background-image']))
  for (const s of src.services || []) for (const i of s?.items || []) add(i?.logo)
  return [...refs]
}

/** Find the uploaded file matching a Homer path ("assets/tools/x.png", "/logo.png", "x.png"). */
export function matchImageFile(ref, files) {
  const norm = (p) => p.replace(/\\/g, '/').replace(/^\.?\//, '').replace(/^\/+/, '').split('?')[0]
  const r = norm(ref)
  const paths = files.map((f) => ({ f, p: norm(f.webkitRelativePath || f.name) }))
  return (
    paths.find((x) => x.p === r)?.f ||
    paths.find((x) => x.p.endsWith('/' + r) || r.endsWith('/' + x.p))?.f ||
    (() => {
      const base = r.split('/').pop()
      const same = paths.filter((x) => x.p.split('/').pop() === base)
      return same.length === 1 ? same[0].f : null
    })()
  )
}

/**
 * @param src        parsed Homer object
 * @param images     { "<homer path>": "/api/uploads/…" } for uploaded local images
 * @param pageLinks  { "#page2": "/d/slug" } to rewrite Homer page links
 */
export function convertHomer(src, { images = {}, pageLinks = {} } = {}) {
  const warnings = []
  const warn = (w) => warnings.includes(w) || warnings.push(w)

  const image = (v, where) => {
    let s = str(v)
    if (!s) return ''
    if (!isRemote(s)) {
      if (images[s]) return images[s]
      warn(s.startsWith('data:') ? `${where}: embedded (data:) image not supported, removed` : `${where}: image "${s}" not found in the selected files, removed`)
      return ''
    }
    if (CSS_UNSAFE.test(s)) s = encodeURI(s).replace(/[()'"]/g, (c) => '%' + c.charCodeAt(0).toString(16).toUpperCase())
    if (CSS_UNSAFE.test(s) || s.length > 1024) {
      warn(`${where}: invalid image URL removed`)
      return ''
    }
    return s
  }
  const color = (v, where) => {
    const s = str(v)
    if (!s || COLOR_RE.test(s)) return s
    warn(`${where}: colour "${s}" not supported, ignored`)
    return ''
  }
  const icon = (v, where) => {
    const s = str(v)
    if (ICON_RE.test(s)) return s
    const lower = s.toLowerCase()
    if (ICON_RE.test(lower)) return lower
    warn(`${where}: icon "${s}" ignored`)
    return ''
  }
  const link = (v, where) => {
    let s = str(v)
    if (pageLinks[s]) return pageLinks[s]
    if (/^#page/i.test(s)) warn(`${where}: link to Homer page "${s}" kept as is (page not imported)`)
    if (FORBIDDEN_SCHEME.test(s) || [...s].some((c) => c.charCodeAt(0) < 32)) {
      warn(`${where}: forbidden URL "${s.slice(0, 40)}" removed`)
      return ''
    }
    return s.slice(0, 2048)
  }
  const target = (t) => (t === '_blank' || t === '_self' ? t : '_self')

  for (const [k, label] of Object.entries(UNSUPPORTED_TOP)) if (src[k]) warn(`Not supported, ignored: ${label} (${k})`)
  if (src.icon && !src.logo) warn('Header icon (icon) not supported: set a logo in the editor')

  const cfg = emptyConfig()
  const cols = str(src.columns || '3')
  cfg.columns = COLUMNS.includes(cols) ? cols : '3'
  if (!COLUMNS.includes(cols)) warn(`Columns "${cols}" not supported, using 3`)
  const colorTheme = src.defaults?.colorTheme || (src.theme === 'dark' ? 'dark' : '')
  if (['auto', 'light', 'dark'].includes(colorTheme)) cfg.default_theme = colorTheme
  if (src.defaults?.layout === 'list') cfg.default_layout = 'list'
  if (src.header === false) cfg.show_header = false
  if (typeof src.footer === 'string') cfg.footer = stripHtml(src.footer).slice(0, 4000)

  for (const theme of ['light', 'dark']) {
    for (const [k, v] of Object.entries(src.colors?.[theme] || {})) {
      if (COLOR_KEYS[k]) cfg.colors[theme][COLOR_KEYS[k]] = color(v, `Colours (${theme}) ${k}`)
      else if (k === 'background-image') {
        if (theme === 'light' || !cfg.background.image) {
          const img = image(cssUrl(v), 'Background image')
          if (img) cfg.background = { ...cfg.background, type: 'image', image: img }
        }
      } else if (k !== 'card-shadow') warn(`Colours (${theme}): "${k}" not supported, ignored`)
    }
  }

  if (src.message && (src.message.title || src.message.content)) {
    if (src.message.url) warn('Message: remote content (url) not supported, the static text is imported')
    cfg.message = {
      enabled: true,
      style: MESSAGE_STYLES[str(src.message.style)] || 'is-info',
      title: cut(stripHtml(src.message.title)),
      icon: icon(src.message.icon, 'Message'),
      content: stripHtml(src.message.content).slice(0, 4000),
    }
  } else if (src.message?.url) warn('Message: remote content (url) not supported, ignored')

  const links = (src.links || []).filter(Boolean)
  if (links.length > 30) warn(`Navigation: ${links.length} links, only the first 30 are kept`)
  cfg.links = links.slice(0, 30).map((l, i) => ({
    name: cut(l.name),
    icon: icon(l.icon, `Navigation link "${l.name || i + 1}"`),
    url: link(l.url, `Navigation link "${l.name || i + 1}"`),
    target: target(l.target),
  }))

  let items = 0
  const smart = new Map()
  let quick = 0
  const services = (src.services || []).filter(Boolean)
  if (services.length > 100) warn(`${services.length} sections, only the first 100 are kept`)
  cfg.sections = services.slice(0, 100).map((s) => {
    const list = (s.items || []).filter(Boolean)
    if (list.length > 300) warn(`Section "${s.name}": only the first 300 items are kept`)
    return {
      id: uid(),
      name: cut(s.name),
      icon: icon(s.icon, `Section "${s.name}"`),
      items: list.slice(0, 300).map((i) => {
        items++
        const where = `"${i.name || 'item'}"`
        const type = str(i.type)
        const isPing = ['ping', 'status'].includes(type.toLowerCase())
        if (type && !isPing) smart.set(type, (smart.get(type) || 0) + 1)
        if (Array.isArray(i.quick) && i.quick.length) quick++
        const endpoint = str(i.endpoint) || (isPing ? str(i.url) : '')
        return {
          id: uid(),
          name: cut(i.name),
          subtitle: cut(stripHtml(i.subtitle)),
          url: link(i.url, where),
          icon: icon(i.icon, where),
          logo: image(i.logo, where),
          tag: cut(i.tag),
          tagstyle: TAG_STYLES.includes(str(i.tagstyle)) ? str(i.tagstyle) : '',
          target: target(i.target),
          keywords: cut(i.keywords),
          background: color(i.background, where),
          // Homer's "Ping" / "Status" smart cards become a status check
          status_check: isPing,
          status_url: isPing && isRemote(endpoint) && endpoint !== str(i.url) ? endpoint.slice(0, 2048) : '',
          status_ignore_tls: false,
        }
      }),
    }
  })
  for (const [type, n] of smart) warn(`Smart card "${type}" (${n}) imported as a simple link`)
  if (quick) warn(`Quick links of ${quick} item(s) not supported, ignored`)

  return {
    title: cut(stripHtml(src.title)) || 'Imported dashboard',
    subtitle: cut(stripHtml(src.subtitle)),
    logo: image(src.logo, 'Logo'),
    config: cfg,
    warnings,
    stats: { sections: cfg.sections.length, items, links: cfg.links.length },
  }
}

export function exportHomer(d) {
  const c = d.config
  const rev = Object.fromEntries(Object.entries(COLOR_KEYS).map(([a, b]) => [b, a]))
  const colors = {}
  for (const theme of ['light', 'dark']) {
    const entries = Object.entries(c.colors?.[theme] || {}).filter(([, v]) => v)
    if (entries.length) colors[theme] = Object.fromEntries(entries.map(([k, v]) => [rev[k], v]))
  }
  if (c.background?.type === 'image' && c.background.image) {
    colors.light = { ...(colors.light || {}), 'background-image': `url('${c.background.image}')` }
  }
  const OWN = new Set(['id', 'status_check', 'status_url', 'status_ignore_tls'])
  const clean = (o) => Object.fromEntries(Object.entries(o).filter(([k, v]) => v !== '' && v !== null && v !== false && !OWN.has(k)))
  const item = (i) => ({
    ...clean(i),
    ...(i.status_check ? { type: 'Ping', ...(i.status_url ? { endpoint: i.status_url } : {}) } : {}),
  })
  const out = {
    title: d.title,
    subtitle: d.subtitle || undefined,
    logo: d.logo || undefined,
    header: c.show_header,
    footer: c.footer || false,
    columns: c.columns,
    defaults: { layout: c.default_layout, colorTheme: c.default_theme },
    colors: Object.keys(colors).length ? colors : undefined,
    message: c.message?.enabled ? clean({ ...c.message, enabled: '' }) : undefined,
    links: c.links?.length ? c.links.map(clean) : undefined,
    services: c.sections.map((s) => ({ ...clean({ name: s.name, icon: s.icon }), items: s.items.map(item) })),
  }
  return yaml.dump(JSON.parse(JSON.stringify(out)), { lineWidth: 120, noRefs: true })
}
