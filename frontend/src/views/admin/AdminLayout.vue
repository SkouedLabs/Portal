<template>
  <div class="admin" :class="{ 'nav-open': navOpen }">
    <aside class="sidebar">
      <div class="side-brand">
        <img v-if="branding.logo" :src="branding.logo" alt="" />
        <span v-else class="mark"><i class="fa-solid fa-house-chimney"></i></span>
        <div>
          <strong>{{ branding.portal_name }}</strong>
          <span>Administration</span>
        </div>
      </div>
      <nav @click="navOpen = false">
        <router-link v-for="l in links" :key="l.to" :to="l.to" class="nav-link" :class="{ exact: l.exact }">
          <i :class="l.icon"></i> {{ l.label }}
        </router-link>
      </nav>
      <div class="side-foot">
        <router-link to="/" class="nav-link"><i class="fa-solid fa-arrow-left"></i> Back to portal</router-link>
      </div>
    </aside>
    <div class="backdrop" @click="navOpen = false"></div>

    <div class="main">
      <header class="topbar">
        <button class="btn ghost icon burger" aria-label="Menu" @click="navOpen = !navOpen"><i class="fa-solid fa-bars"></i></button>
        <div class="spacer"></div>
        <div class="topbar-user"><UserMenu /></div>
      </header>
      <div class="content">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import UserMenu from '../../components/UserMenu.vue'
import { state } from '../../store'

const navOpen = ref(false)
const branding = computed(() => state.config?.branding || {})
const links = [
  { to: '/admin', label: 'Overview', icon: 'fa-solid fa-chart-line', exact: true },
  { to: '/admin/dashboards', label: 'Dashboards', icon: 'fa-solid fa-table-columns' },
  { to: '/admin/users', label: 'Users', icon: 'fa-solid fa-user' },
  { to: '/admin/groups', label: 'Groups', icon: 'fa-solid fa-users' },
  { to: '/admin/auth', label: 'Authentication', icon: 'fa-solid fa-key' },
  { to: '/admin/certificates', label: 'Certificates', icon: 'fa-solid fa-certificate' },
  { to: '/admin/branding', label: 'Branding', icon: 'fa-solid fa-palette' },
  { to: '/admin/logs', label: 'Logs', icon: 'fa-solid fa-list-check' },
]
</script>

<style scoped>
.admin {
  display: grid;
  grid-template-columns: 250px 1fr;
  min-height: 100vh;
}
.sidebar {
  background: #111827;
  color: #cbd5e1;
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 0;
  height: 100vh;
  padding: 16px 12px;
}
.side-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 20px;
}
.side-brand img,
.mark {
  width: 36px;
  height: 36px;
  object-fit: contain;
  border-radius: 8px;
  flex-shrink: 0;
}
.mark {
  background: var(--brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.side-brand strong {
  display: block;
  color: #fff;
  font-size: 0.98rem;
}
.side-brand span {
  font-size: 0.78rem;
  color: #94a3b8;
}
nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}
.nav-link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  color: #cbd5e1;
  text-decoration: none;
  font-size: 0.92rem;
}
.nav-link i {
  width: 18px;
  text-align: center;
  color: #94a3b8;
}
.nav-link:hover {
  background: #1f2937;
  color: #fff;
}
.nav-link.router-link-active:not(.exact),
.nav-link.exact.router-link-exact-active {
  background: color-mix(in srgb, var(--brand) 28%, #111827);
  color: #fff;
}
.nav-link.router-link-active:not(.exact) i,
.nav-link.exact.router-link-exact-active i {
  color: #fff;
}
.side-foot {
  border-top: 1px solid #1f2937;
  padding-top: 10px;
}
.main {
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.topbar {
  display: flex;
  align-items: center;
  padding: 10px 24px;
  background: var(--ui-surface);
  border-bottom: 1px solid var(--ui-border);
  position: sticky;
  top: 0;
  z-index: 20;
}
.topbar-user {
  color: var(--ui-text);
}
.topbar-user :deep(.avatar-btn) {
  background: var(--ui-surface-2);
}
.topbar-user :deep(.avatar) {
  background: var(--brand);
  color: #fff;
}
.spacer {
  flex: 1;
}
.burger,
.backdrop {
  display: none;
}
.content {
  padding: 26px 28px 48px;
  max-width: 1300px;
  width: 100%;
}

@media (max-width: 900px) {
  .admin {
    grid-template-columns: 1fr;
  }
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    width: 260px;
    z-index: 60;
    transform: translateX(-100%);
    transition: transform 0.2s;
  }
  .nav-open .sidebar {
    transform: none;
  }
  .nav-open .backdrop {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    z-index: 55;
  }
  .burger {
    display: inline-flex;
  }
  .topbar {
    padding: 8px 16px;
  }
  .content {
    padding: 18px 16px 40px;
  }
}
</style>
