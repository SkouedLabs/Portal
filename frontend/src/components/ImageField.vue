<template>
  <div class="field">
    <label v-if="label">{{ label }}</label>
    <div class="image-field">
      <div class="thumb" :class="{ empty: !modelValue }">
        <img v-if="modelValue" :src="modelValue" alt="" />
        <i v-else class="fa-regular fa-image"></i>
      </div>
      <input
        class="input sm"
        :value="modelValue"
        placeholder="https://… or upload"
        @change="$emit('update:modelValue', $event.target.value.trim())"
      />
      <label class="btn sm" :class="{ disabled: busy }">
        <i :class="busy ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-upload'"></i>
        <input type="file" accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml,image/x-icon" hidden @change="upload" />
      </label>
      <button v-if="modelValue" class="btn sm ghost" title="Remove" @click="$emit('update:modelValue', '')">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>
    <span v-if="hint" class="hint">{{ hint }}</span>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../api'
import { notify } from '../store'

defineProps({ modelValue: { type: String, default: '' }, label: String, hint: String })
const emit = defineEmits(['update:modelValue'])
const busy = ref(false)

async function upload(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  busy.value = true
  try {
    const { url } = await api.upload(file)
    emit('update:modelValue', url)
  } catch (err) {
    notify(err.message, 'error')
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.image-field {
  display: flex;
  align-items: center;
  gap: 6px;
}
.thumb {
  width: 34px;
  height: 34px;
  border-radius: 6px;
  border: 1px solid var(--ui-border);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
  background: repeating-conic-gradient(#8881 0 25%, transparent 0 50%) 50% / 10px 10px;
  color: var(--ui-muted);
}
.thumb img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
.disabled {
  pointer-events: none;
  opacity: 0.6;
}
</style>
