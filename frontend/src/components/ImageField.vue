<template>
  <div class="field">
    <label v-if="label">{{ label }}</label>
    <div class="image-field">
      <div class="thumb" :class="{ empty: !modelValue }">
        <img v-if="modelValue" :src="modelValue" alt="" decoding="async" />
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
    <span v-if="saved" class="hint saved"><i class="fa-solid fa-feather"></i> {{ saved }}</span>
    <span v-else-if="hint" class="hint">{{ hint }}</span>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../api'
import { notify } from '../store'

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: String,
  hint: String,
  // What the image is for. The server bounds and re-encodes it accordingly: "icon" for a logo,
  // a favicon or a card, "background" for a full-page image.
  kind: { type: String, default: 'icon' },
})
const emit = defineEmits(['update:modelValue'])
const busy = ref(false)
const saved = ref('')

const kb = (n) => (n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`)

async function upload(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  busy.value = true
  saved.value = ''
  try {
    const { url, bytes, format } = await api.upload(file, props.kind)
    emit('update:modelValue', url)
    // Say what was stored rather than what was sent: a 3 MB photograph becoming a 180 KB WebP is
    // the difference between a page that paints at once and one that does not.
    if (bytes && bytes < file.size * 0.9) {
      saved.value = `Compressed: ${kb(file.size)} → ${kb(bytes)} ${String(format).toUpperCase()}`
    } else if (bytes) {
      saved.value = `Stored: ${kb(bytes)} ${String(format).toUpperCase()}`
    }
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
.hint.saved {
  color: var(--ui-ok, #2a9d5c);
}
</style>
