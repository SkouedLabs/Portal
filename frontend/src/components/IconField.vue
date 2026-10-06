<template>
  <div class="field">
    <label v-if="label">{{ label }}</label>
    <div class="icon-field">
      <button type="button" class="preview" title="Browse icons" @click="open = true">
        <i :class="modelValue || 'fa-solid fa-icons'" :style="modelValue ? null : { opacity: 0.35 }"></i>
      </button>
      <input
        class="input sm"
        :value="modelValue"
        placeholder="fa-solid fa-house"
        @change="$emit('update:modelValue', $event.target.value.trim())"
      />
      <button type="button" class="btn sm" title="Browse icons" @click="open = true"><i class="fa-solid fa-magnifying-glass"></i></button>
    </div>
    <IconPicker v-if="open" :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" @close="open = false" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import IconPicker from './IconPicker.vue'

defineProps({ modelValue: { type: String, default: '' }, label: String })
defineEmits(['update:modelValue'])
const open = ref(false)
</script>

<style scoped>
.icon-field {
  display: flex;
  gap: 6px;
  align-items: center;
}
.preview {
  width: 34px;
  height: 32px;
  border: 1px solid var(--ui-border);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--brand);
  background: var(--ui-surface);
  cursor: pointer;
}
</style>
