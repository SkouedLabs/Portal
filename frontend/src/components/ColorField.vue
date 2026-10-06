<template>
  <div class="field">
    <label v-if="label">{{ label }}</label>
    <div class="color-field">
      <input type="color" class="swatch" :value="hex" :title="label" @input="$emit('update:modelValue', $event.target.value)" />
      <input
        class="input sm"
        :value="modelValue"
        :placeholder="placeholder || 'default'"
        @change="$emit('update:modelValue', $event.target.value.trim())"
      />
      <button v-if="modelValue" class="btn sm ghost icon" title="Reset" @click="$emit('update:modelValue', '')">
        <i class="fa-solid fa-rotate-left"></i>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ modelValue: { type: String, default: '' }, label: String, placeholder: String })
defineEmits(['update:modelValue'])

function toHex(v) {
  if (/^#[0-9a-f]{6}$/i.test(v)) return v
  if (/^#[0-9a-f]{3}$/i.test(v)) return '#' + [...v.slice(1)].map((c) => c + c).join('')
  return null
}
const hex = computed(() => toHex(props.modelValue) || toHex(props.placeholder || '') || '#000000')
</script>

<style scoped>
.color-field {
  display: flex;
  align-items: center;
  gap: 6px;
}
.swatch {
  width: 34px;
  height: 32px;
  padding: 2px;
  border: 1px solid var(--ui-border);
  border-radius: 6px;
  background: var(--ui-surface);
  cursor: pointer;
  flex-shrink: 0;
}
</style>
