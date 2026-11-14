// Homer import/export: parses a realistic config.yml, converts it the way the importer does, exports it back,
// and re-parses the result — under js-yaml 5 with the named-import migration.
import { convertHomer, exportHomer, homerImageRefs, parseHomer } from '../src/homerYaml.js'

const CONFIG = `
title: "Company portal"
subtitle: "Tools"
logo: "assets/logo.png"
header: true
footer: '<p>internal</p>'
colors:
  light:
    highlight-primary: "#3367d6"
    background: "#f5f5f5"
    background-image: "url('assets/bg.jpg')"
  dark:
    highlight-primary: "#3367d6"
message:
  style: "is-info"
  title: "Heads up"
  content: "Maintenance on Sunday"
links:
  - name: "Intranet"
    icon: "fas fa-building"
    url: "https://intranet.example.com"
services:
  - name: "Infrastructure"
    icon: "fas fa-server"
    items:
      - name: "Grafana"
        subtitle: "Dashboards"
        logo: "assets/tools/grafana.png"
        tag: "obs"
        url: "https://grafana.example.com"
        target: "_blank"
      - name: "Proxmox"
        subtitle: "Virtualisation"
        icon: "fas fa-hard-drive"
        url: "https://pve.example.com"
        type: "Ping"
  - name: "Support"
    items:
      - name: "Tickets"
        url: "https://tickets.example.com"
`

const fails = []
const check = (label, cond, got) => {
  if (cond) console.log(`  ok   ${label}`)
  else { console.log(`  FAIL ${label}  -> ${got}`); fails.push(label) }
}

// 1. parse
const src = parseHomer(CONFIG)
check('parses the config', src && src.title === 'Company portal', JSON.stringify(src).slice(0, 120))
check('services are read', Array.isArray(src.services) && src.services.length === 2, src.services?.length)

// 2. the local image references the importer uploads, with their kind
const refs = homerImageRefs(src)
const byRef = Object.fromEntries(refs.map((r) => [r.ref, r.kind]))
check('finds the local images', refs.length === 3, JSON.stringify(refs))
check('the logo is an icon', byRef['assets/logo.png'] === 'icon', byRef['assets/logo.png'])
check('the page background is a background', byRef['assets/bg.jpg'] === 'background', byRef['assets/bg.jpg'])
check('a card logo is an icon', byRef['assets/tools/grafana.png'] === 'icon', byRef['assets/tools/grafana.png'])

// 3. convert
const d = convertHomer(src, { images: { 'assets/logo.png': '/api/uploads/a.webp', 'assets/bg.jpg': '/api/uploads/b.webp' } })
check('converts to a dashboard', !!d && !!d.config, typeof d)
check('keeps the title', d.title === 'Company portal', d.title)
check('keeps both sections', d.config.sections.length === 2, d.config.sections.length)
check('keeps the cards', d.config.sections[0].items.length === 2, d.config.sections[0].items.length)
check('uploaded logo is substituted', d.logo === '/api/uploads/a.webp', d.logo)
check('background image is substituted', d.config.background.image === '/api/uploads/b.webp', JSON.stringify(d.config.background))
check('a Ping card becomes a status check',
  JSON.stringify(d.config.sections[0].items).includes('status') || d.config.sections[0].items[1].status === true,
  JSON.stringify(d.config.sections[0].items[1]))
check('the message is kept', d.config.message.title === 'Heads up', JSON.stringify(d.config.message))

// 4. export back to Homer YAML, then re-parse it: this is the dump() path
const out = exportHomer(d)
check('exports non-empty YAML', typeof out === 'string' && out.length > 100, out?.length)
check('export has no YAML anchors (noRefs)', !out.includes('&ref_') && !out.includes('*ref_'), out.slice(0, 200))

const again = parseHomer(out)
check('the export re-parses', !!again, typeof again)
check('round-trip keeps the title', again.title === 'Company portal', again.title)
check('round-trip keeps the sections', (again.services || []).length === 2, (again.services || []).length)
check('round-trip keeps the cards',
  (again.services?.[0]?.items || []).length === 2, JSON.stringify(again.services?.[0]?.items || []).slice(0, 160))

console.log(fails.length ? `\n${fails.length} FAILED` : '\nhomerYaml under js-yaml 5: all checks passed')
process.exit(fails.length ? 1 : 0)
