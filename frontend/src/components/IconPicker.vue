<template>
  <Modal title="Choose an icon" wide @close="$emit('close')">
    <div class="picker-bar">
      <input ref="searchEl" v-model="q" class="input" placeholder="Search icons (e.g. server, mail, chart)…" />
      <div class="seg">
        <button v-for="s in STYLES" :key="s.id" :class="{ active: style === s.id }" @click="style = s.id">{{ s.label }}</button>
      </div>
    </div>
    <p class="muted small">
      {{ loading ? 'Loading…' : `${matches.length} icon(s)${matches.length > LIMIT ? ` — showing the first ${LIMIT}, refine your search` : ''}` }}
      · Font Awesome Free, bundled locally (works offline).
    </p>
    <div class="grid">
      <button
        v-for="i in shown"
        :key="i.cls"
        class="icon-btn"
        :class="{ current: i.cls === modelValue }"
        :title="`${i.label} — ${i.cls}`"
        @click="pick(i.cls)"
      >
        <i :class="i.cls"></i>
        <span>{{ i.name }}</span>
      </button>
    </div>
    <template #footer>
      <button v-if="modelValue" class="btn ghost" @click="pick('')"><i class="fa-solid fa-ban"></i> No icon</button>
      <div style="flex: 1"></div>
      <button class="btn" @click="$emit('close')">Cancel</button>
    </template>
  </Modal>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import Modal from './Modal.vue'

defineProps({ modelValue: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue', 'close'])

const LIMIT = 240
const STYLES = [
  { id: 's', label: 'Solid', prefix: 'fa-solid' },
  { id: 'r', label: 'Regular', prefix: 'fa-regular' },
  { id: 'b', label: 'Brands', prefix: 'fa-brands' },
]
const q = ref('')
const style = ref('s')
const icons = ref([])
const loading = ref(true)
const searchEl = ref(null)

onMounted(async () => {
  searchEl.value?.focus()
  // Lazy-loaded chunk: the index is only downloaded when the picker is opened.
  icons.value = (await import('virtual:fa-icons')).default
  loading.value = false
})

const matches = computed(() => {
  const term = q.value.trim().toLowerCase()
  const prefix = STYLES.find((s) => s.id === style.value).prefix
  return icons.value
    .filter(([name, label, styles, terms]) => styles.includes(style.value) && (!term || name.includes(term) || label.toLowerCase().includes(term) || terms.includes(term)))
    .map(([name, label]) => ({ name, label, cls: `${prefix} fa-${name}` }))
})
const shown = computed(() => matches.value.slice(0, LIMIT))

function pick(cls) {
  emit('update:modelValue', cls)
  emit('close')
}
</script>

<style scoped>
.picker-bar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}
.picker-bar .input {
  flex: 1 1 260px;
}
.seg {
  display: flex;
  gap: 4px;
  padding: 3px;
  border-radius: 9px;
  background: var(--ui-surface-2);
  border: 1px solid var(--ui-border);
}
.seg button {
  font: inherit;
  font-size: 0.85rem;
  border: none;
  background: none;
  color: var(--ui-muted);
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
}
.seg button.active {
  background: var(--ui-surface);
  color: var(--ui-text);
  font-weight: 600;
  box-shadow: var(--ui-shadow);
}
.small {
  font-size: 0.8rem;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
  gap: 6px;
  max-height: 52vh;
  overflow-y: auto;
  padding: 2px;
}
.icon-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 12px 4px 8px;
  border: 1px solid var(--ui-border);
  border-radius: 8px;
  background: var(--ui-surface);
  color: var(--ui-text);
  cursor: pointer;
  font: inherit;
}
.icon-btn i {
  font-size: 1.4rem;
  color: var(--brand);
}
.icon-btn span {
  font-size: 0.68rem;
  color: var(--ui-muted);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.icon-btn:hover,
.icon-btn.current {
  border-color: var(--brand);
  background: color-mix(in srgb, var(--brand) 8%, var(--ui-surface));
}
</style>
