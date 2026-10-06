<template>
  <div v-if="error" class="state">
    <div class="card-ui">
      <h2><i class="fa-solid fa-triangle-exclamation"></i> {{ error }}</h2>
      <router-link to="/" class="btn">Back to portal</router-link>
    </div>
  </div>
  <div v-else-if="!dashboard" class="state"><i class="fa-solid fa-spinner fa-spin"></i></div>
  <DashboardRender v-else :dashboard="dashboard" :dashboards="dashboards">
    <template #actions>
      <router-link v-if="dashboard.can_edit" :to="`/edit/${dashboard.id}`" class="hdr-btn" title="Edit this dashboard">
        <i class="fa-solid fa-pen"></i><span>Edit</span>
      </router-link>
      <UserMenu :edit-id="dashboard.can_edit ? dashboard.id : null" />
    </template>
  </DashboardRender>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import DashboardRender from '../components/DashboardRender.vue'
import UserMenu from '../components/UserMenu.vue'
import { state, storage } from '../store'

const route = useRoute()
const dashboard = ref(null)
const dashboards = ref([])
const error = ref('')

async function load(slug) {
  error.value = ''
  try {
    const [d, list] = await Promise.all([api.get(`/api/dashboards/${encodeURIComponent(slug)}`), api.get('/api/dashboards')])
    dashboard.value = d
    dashboards.value = list
    storage.set('last-dashboard', slug)
    document.title = `${d.title} · ${state.config?.branding?.portal_name || 'Portal-NG'}`
  } catch (e) {
    if (e.status !== 401) error.value = e.status === 404 ? 'Dashboard not found or access denied' : e.message
  }
}

watch(() => route.params.slug, (s) => s && load(s), { immediate: true })
</script>

<style scoped>
.state {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}
.hdr-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: inherit;
  text-decoration: none;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
  font-size: 0.9rem;
}
.hdr-btn:hover {
  background: rgba(255, 255, 255, 0.24);
}
@media (max-width: 720px) {
  .hdr-btn span {
    display: none;
  }
}
</style>
