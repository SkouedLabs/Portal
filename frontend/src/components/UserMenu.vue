<template>
  <div class="user-menu" @keydown.escape="open = false">
    <slot />
    <button class="avatar-btn" :aria-expanded="open" @click.stop="open = !open">
      <span class="avatar">{{ initials }}</span>
      <span class="name">{{ state.me?.display_name }}</span>
      <i class="fa-solid fa-chevron-down"></i>
    </button>
    <div v-if="open" class="menu" @click="open = false">
      <div class="who">
        <strong>{{ state.me?.display_name }}</strong>
        <span>{{ state.me?.username }} · {{ state.me?.source }}</span>
      </div>
      <router-link v-if="editId" :to="`/edit/${editId}`" class="mi"><i class="fa-solid fa-pen"></i> Edit this dashboard</router-link>
      <router-link v-if="state.me?.source !== 'oidc'" to="/account" class="mi"><i class="fa-solid fa-shield-halved"></i> Security</router-link>
      <router-link v-if="state.me?.is_admin" to="/admin" class="mi"><i class="fa-solid fa-gauge-high"></i> Administration</router-link>
      <router-link to="/" class="mi"><i class="fa-solid fa-house"></i> Portal</router-link>
      <button class="mi" @click="doLogout"><i class="fa-solid fa-right-from-bracket"></i> Sign out</button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { logout, state } from '../store'

defineProps({ editId: { type: [Number, String], default: null } })
const open = ref(false)
const router = useRouter()

const initials = computed(() =>
  (state.me?.display_name || state.me?.username || '?')
    .split(/[\s._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join(''),
)

async function doLogout() {
  await logout()
  router.push('/login')
}
const close = () => (open.value = false)
onMounted(() => document.addEventListener('click', close))
onBeforeUnmount(() => document.removeEventListener('click', close))
</script>

<style scoped>
.user-menu {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
}
.avatar-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.14);
  border: none;
  color: inherit;
  font: inherit;
  padding: 5px 10px 5px 5px;
  border-radius: 999px;
  cursor: pointer;
}
.avatar-btn:hover {
  background: rgba(255, 255, 255, 0.24);
}
.avatar-btn .fa-chevron-down {
  font-size: 0.7rem;
}
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.9);
  color: #1d2433;
  font-weight: 700;
  font-size: 0.82rem;
  display: flex;
  align-items: center;
  justify-content: center;
}
.name {
  font-size: 0.92rem;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.menu {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  min-width: 250px;
  background: var(--ui-surface);
  color: var(--ui-text);
  border: 1px solid var(--ui-border);
  border-radius: 10px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.22);
  padding: 6px;
  z-index: 50;
}
.who {
  padding: 8px 10px 10px;
  border-bottom: 1px solid var(--ui-border);
  margin-bottom: 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.who span {
  font-size: 0.8rem;
  color: var(--ui-muted);
}
.mi {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 10px;
  border-radius: 6px;
  color: inherit;
  text-decoration: none;
  background: none;
  border: none;
  font: inherit;
  font-size: 0.92rem;
  cursor: pointer;
  text-align: left;
}
.mi i {
  width: 16px;
  color: var(--ui-muted);
}
.mi:hover {
  background: var(--ui-surface-2);
}
@media (max-width: 720px) {
  .name {
    display: none;
  }
}
</style>
