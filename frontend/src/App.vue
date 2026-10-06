<template>
  <router-view />
  <div class="toasts" aria-live="polite">
    <div v-for="t in state.toasts" :key="t.id" class="toast" :class="`toast-${t.type}`">
      <i :class="t.type === 'error' ? 'fa-solid fa-circle-exclamation' : 'fa-solid fa-circle-check'"></i>
      <span>{{ t.message }}</span>
    </div>
  </div>
</template>

<script setup>
import { state } from './store'
</script>
