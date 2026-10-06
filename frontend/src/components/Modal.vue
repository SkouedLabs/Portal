<template>
  <Teleport to="body">
    <div class="modal-backdrop" @mousedown.self="$emit('close')" @keydown.escape="$emit('close')">
      <div class="modal" :class="{ wide }" role="dialog" aria-modal="true" :aria-label="title">
        <header>
          <h3>{{ title }}</h3>
          <button class="btn ghost icon" aria-label="Close" @click="$emit('close')"><i class="fa-solid fa-xmark"></i></button>
        </header>
        <div class="body"><slot /></div>
        <footer v-if="$slots.footer"><slot name="footer" /></footer>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
defineProps({ title: { type: String, default: '' }, wide: { type: Boolean, default: false } })
defineEmits(['close'])
</script>
