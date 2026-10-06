import { createRouter, createWebHistory } from 'vue-router'
import { onUnauthorized } from './api'
import { loadMe, loadPublicConfig, state } from './store'

const routes = [
  { path: '/login', name: 'login', component: () => import('./views/LoginView.vue'), meta: { public: true } },
  { path: '/', name: 'home', component: () => import('./views/HomeView.vue') },
  { path: '/d/:slug', name: 'dashboard', component: () => import('./views/DashboardView.vue') },
  { path: '/edit/:id', name: 'editor', component: () => import('./views/EditorView.vue') },
  { path: '/account', name: 'account', component: () => import('./views/AccountView.vue') },
  {
    path: '/admin',
    component: () => import('./views/admin/AdminLayout.vue'),
    meta: { admin: true },
    children: [
      { path: '', name: 'admin', component: () => import('./views/admin/OverviewView.vue') },
      { path: 'dashboards', name: 'admin-dashboards', component: () => import('./views/admin/DashboardsView.vue') },
      { path: 'users', name: 'admin-users', component: () => import('./views/admin/UsersView.vue') },
      { path: 'groups', name: 'admin-groups', component: () => import('./views/admin/GroupsView.vue') },
      { path: 'auth', name: 'admin-auth', component: () => import('./views/admin/AuthView.vue') },
      { path: 'certificates', name: 'admin-certificates', component: () => import('./views/admin/CertificatesView.vue') },
      { path: 'branding', name: 'admin-branding', component: () => import('./views/admin/BrandingView.vue') },
      { path: 'logs', name: 'admin-logs', component: () => import('./views/admin/LogsView.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  if (!state.config) await loadPublicConfig().catch(() => {})
  if (!state.meLoaded) await loadMe()
  if (to.meta.public) return true
  if (!state.me) return { name: 'login', query: to.fullPath !== '/' ? { next: to.fullPath } : {} }
  if (to.matched.some((r) => r.meta.admin) && !state.me.is_admin) return { name: 'home' }
  return true
})

onUnauthorized(() => {
  state.me = null
  const current = router.currentRoute.value
  if (!current.meta.public) router.push({ name: 'login', query: { next: current.fullPath } })
})

export default router
