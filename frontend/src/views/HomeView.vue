<template>
  <div class="home">
    <div v-if="loading" class="empty"><i class="fa-solid fa-spinner fa-spin"></i></div>
    <div v-else class="card-ui none">
      <i class="fa-regular fa-folder-open big"></i>
      <h2>No dashboard available</h2>
      <p class="muted">No dashboard has been assigned to you yet. Please contact your administrator.</p>
      <div class="actions">
        <router-link v-if="state.me?.is_admin" to="/admin/dashboards" class="btn primary">
          <i class="fa-solid fa-plus"></i> Create a dashboard
        </router-link>
        <button class="btn" @click="doLogout"><i class="fa-solid fa-right-from-bracket"></i> Sign out</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { logout, state, storage } from '../store'

const router = useRouter()
const loading = ref(true)

onMounted(async () => {
  try {
    const list = await api.get('/api/dashboards')
    if (list.length) {
      const last = storage.get('last-dashboard')
      const target = list.find((d) => d.slug === last) || list[0]
      return router.replace(`/d/${target.slug}`)
    }
  } finally {
    loading.value = false
  }
})

async function doLogout() {
  await logout()
  router.push('/login')
}
</script>

<style scoped>
.home {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}
.none {
  max-width: 460px;
  text-align: center;
}
.big {
  font-size: 2.6rem;
  color: var(--ui-muted);
  margin-bottom: 14px;
}
.actions {
  display: flex;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 18px;
}
</style>
