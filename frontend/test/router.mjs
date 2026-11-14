// Routing: exercises the router the way src/router.js actually uses it —
// nested routes, a guard that redirects to a named route with a query, route params,
// the catch-all redirect, and resolve(). Run with jsdom so there is no browser needed.
import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!doctype html><html><body><div id="app"></div></body></html>', {
  url: 'http://localhost/',
  pretendToBeVisual: true,
})
// Vue's DOM runtime reaches for a good many browser globals (SVGElement, Element, Node...).
// Define rather than assign: Node 22 makes some of these getter-only on globalThis.
const define = (k, v) => Object.defineProperty(global, k, { value: v, configurable: true, writable: true })
define('window', dom.window)
for (const k of Object.getOwnPropertyNames(dom.window)) {
  if (k.startsWith('_') || k === 'window' || k === 'globalThis') continue
  try { if (global[k] === undefined) define(k, dom.window[k]) } catch { /* getter-only, skip */ }
}
for (const k of ['document', 'navigator', 'location', 'history']) define(k, dom.window[k])

const { createRouter, createWebHistory, RouterView } = await import('vue-router')
const { createApp, h, defineComponent } = await import('vue')

const Stub = (n) => defineComponent({ name: n, render: () => h('div', { class: n }, n) })
const Layout = defineComponent({ name: 'layout', render: () => h('div', { class: 'layout' }, [h(RouterView)]) })

const routes = [
  { path: '/login', name: 'login', component: Stub('login'), meta: { public: true } },
  { path: '/', name: 'home', component: Stub('home') },
  { path: '/d/:slug', name: 'dashboard', component: Stub('dash') },
  {
    path: '/admin',
    component: Layout,
    meta: { admin: true },
    children: [
      { path: '', name: 'admin', component: Stub('overview') },
      { path: 'users', name: 'admin-users', component: Stub('users') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

let signedIn = false
let isAdmin = false

// The real guard from src/router.js, verbatim in shape
router.beforeEach(async (to) => {
  if (to.meta.public) return true
  if (!signedIn) return { name: 'login', query: to.fullPath !== '/' ? { next: to.fullPath } : {} }
  if (to.matched.some((r) => r.meta.admin) && !isAdmin) return { name: 'home' }
  return true
})

const app = createApp({ render: () => h(RouterView) })
app.use(router)
await router.isReady()
app.mount('#app')

const html = () => document.getElementById('app').innerHTML
const fails = []
const check = (label, cond, got) => {
  if (cond) console.log(`  ok   ${label}`)
  else { console.log(`  FAIL ${label}  -> ${got}`); fails.push(label) }
}

// 1. anonymous visitor is sent to the sign-in page, with ?next=
await router.push('/d/intranet')
check('guard redirects anonymous to login', router.currentRoute.value.name === 'login', router.currentRoute.value.fullPath)
check('the wanted page is kept in ?next', router.currentRoute.value.query.next === '/d/intranet', JSON.stringify(router.currentRoute.value.query))
check('login renders', html().includes('login'), html())

// 2. signed in, a dashboard renders and its param is readable
signedIn = true
await router.push('/d/intranet')
check('dashboard route matches', router.currentRoute.value.name === 'dashboard', router.currentRoute.value.name)
check('route param is readable', router.currentRoute.value.params.slug === 'intranet', JSON.stringify(router.currentRoute.value.params))
check('dashboard renders', html().includes('dash'), html())

// 3. a non-admin is bounced off /admin, meta inherited through matched
await router.push('/admin/users')
check('non-admin bounced from /admin', router.currentRoute.value.name === 'home', router.currentRoute.value.name)

// 4. an admin gets the nested child inside its layout
isAdmin = true
await router.push('/admin/users')
check('admin reaches the nested child', router.currentRoute.value.name === 'admin-users', router.currentRoute.value.name)
check('child renders inside the layout', html().includes('layout') && html().includes('users'), html())

// 5. the empty child path
await router.push('/admin')
check('empty child path resolves', router.currentRoute.value.name === 'admin', router.currentRoute.value.name)

// 6. the catch-all redirect
await router.push('/nope/nowhere')
check('catch-all redirects home', router.currentRoute.value.path === '/', router.currentRoute.value.path)

// 7. resolve(), used to build hrefs
check('resolve() by name', router.resolve({ name: 'dashboard', params: { slug: 'x' } }).href === '/d/x',
  router.resolve({ name: 'dashboard', params: { slug: 'x' } }).href)

// 8. replace() does not grow the history
await router.replace({ name: 'home' })
check('replace() lands on home', router.currentRoute.value.name === 'home', router.currentRoute.value.name)

console.log(fails.length ? `\n${fails.length} FAILED` : '\nvue-router: all checks passed')
process.exit(fails.length ? 1 : 0)
