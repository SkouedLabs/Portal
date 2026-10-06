<template>
  <div>
    <div class="page-title">
      <h1>Branding</h1>
      <p>Portal name, logo and look. Applied immediately to the sign-in page, the admin panel and dashboards without their own logo.</p>
    </div>

    <div v-if="b" class="layout">
      <div class="card-ui">
        <div class="field"><label>Portal name</label><input v-model="b.portal_name" class="input" maxlength="80" /></div>
        <div class="field"><label>Subtitle</label><input v-model="b.subtitle" class="input" maxlength="120" /></div>
        <ImageField v-model="b.logo" label="Logo" hint="Transparent SVG or PNG recommended." />
        <ImageField v-model="b.favicon" label="Favicon" hint="Defaults to the logo." />
        <ColorField v-model="b.primary_color" label="Primary colour" placeholder="#3367d6" />
        <h3 class="sub">Sign-in page background</h3>
        <div class="seg">
          <button v-for="t in BG_TYPES" :key="t.id" :class="{ active: (b.login_bg_type || 'default') === t.id }" @click="b.login_bg_type = t.id">
            <i :class="t.icon"></i> {{ t.label }}
          </button>
        </div>
        <ColorField v-if="b.login_bg_type === 'color'" v-model="b.login_bg_color" label="Colour" :placeholder="b.primary_color" />
        <template v-if="b.login_bg_type === 'gradient'">
          <div class="row">
            <ColorField v-model="b.login_bg_gradient_from" label="From" :placeholder="b.primary_color" />
            <ColorField v-model="b.login_bg_gradient_to" label="To" placeholder="#0b1020" />
          </div>
          <div class="field">
            <label>Angle: {{ b.login_bg_gradient_angle }}°</label>
            <input v-model.number="b.login_bg_gradient_angle" type="range" min="0" max="360" step="5" />
          </div>
        </template>
        <template v-if="b.login_bg_type === 'image'">
          <ImageField v-model="b.login_background" label="Image" hint="Large JPEG or WebP recommended (e.g. 1920×1080)." />
          <div class="row">
            <div class="field">
              <label>Darken: {{ Math.round((b.login_bg_overlay || 0) * 100) }}%</label>
              <input v-model.number="b.login_bg_overlay" type="range" min="0" max="0.9" step="0.05" />
            </div>
            <div class="field">
              <label>Blur: {{ b.login_bg_blur || 0 }} px</label>
              <input v-model.number="b.login_bg_blur" type="range" min="0" max="20" step="1" />
            </div>
          </div>
        </template>
        <h3 class="sub">Texts</h3>
        <div class="field">
          <label>Sign-in page message</label>
          <textarea v-model="b.login_message" class="input" rows="2"></textarea>
        </div>
        <div class="field">
          <label>Footer</label>
          <textarea v-model="b.footer" class="input" rows="2" placeholder="© My company"></textarea>
        </div>
        <div style="display: flex; justify-content: flex-end">
          <button class="btn primary" :disabled="saving" @click="save"><i class="fa-solid fa-floppy-disk"></i> Save</button>
        </div>
      </div>

      <div class="preview-col">
        <span class="label">Sign-in page preview</span>
        <div class="login-preview">
          <div class="pv-bg" :style="loginBg.style"></div>
          <div v-if="loginBg.overlay" class="pv-overlay" :style="{ opacity: loginBg.overlay }"></div>
          <div class="mini-card">
            <img v-if="b.logo" :src="b.logo" alt="" class="mini-logo" />
            <div v-else class="mini-mark" :style="{ background: b.primary_color || '#3367d6' }"><i class="fa-solid fa-house-chimney"></i></div>
            <strong>{{ b.portal_name || 'Portal-NG' }}</strong>
            <span class="muted">{{ b.subtitle }}</span>
            <div v-if="b.login_message" class="alert info mini-msg">{{ b.login_message }}</div>
            <div class="fake-input"></div>
            <div class="fake-input"></div>
            <div class="fake-btn" :style="{ background: b.primary_color || '#3367d6' }">Sign in</div>
          </div>
          <div v-if="b.footer" class="mini-footer">{{ b.footer }}</div>
        </div>
      </div>
    </div>

    <div v-if="status" class="card-ui" style="margin-top: 18px">
      <h2><i class="fa-solid fa-heart-pulse"></i> Status checks</h2>
      <p class="muted small">
        Links flagged "Check status" in the dashboard editor are probed by the backend (works for internal applications,
        uses the trusted CAs from the Certificates page). Results are cached to limit traffic.
      </p>
      <label class="switch"><input v-model="status.enabled" type="checkbox" /><span class="track"></span> Enable status checks</label>
      <div class="row" style="margin-top: 12px">
        <div class="field" style="max-width: 200px">
          <label>Timeout (seconds)</label>
          <input v-model.number="status.timeout_seconds" type="number" min="1" max="30" class="input" />
        </div>
        <div class="field" style="max-width: 200px">
          <label>Cache (seconds)</label>
          <input v-model.number="status.cache_seconds" type="number" min="0" max="3600" class="input" />
        </div>
      </div>
      <div style="display: flex; justify-content: flex-end">
        <button class="btn primary" @click="saveStatus"><i class="fa-solid fa-floppy-disk"></i> Save</button>
      </div>
    </div>

    <div v-if="logs" class="card-ui" style="margin-top: 18px">
      <h2><i class="fa-solid fa-list-check"></i> Logging</h2>
      <div class="row">
        <div class="field" style="max-width: 240px">
          <label>Retention (days)</label>
          <input v-model.number="logs.retention_days" type="number" min="1" max="3650" class="input" />
        </div>
        <div class="field" style="justify-content: flex-end; gap: 8px">
          <label class="check"><input v-model="logs.log_views" type="checkbox" /> Log dashboard views</label>
          <label class="check"><input v-model="logs.log_clicks" type="checkbox" /> Log link clicks</label>
        </div>
      </div>
      <div style="display: flex; justify-content: flex-end">
        <button class="btn primary" @click="saveLogs"><i class="fa-solid fa-floppy-disk"></i> Save</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../../api'
import ColorField from '../../components/ColorField.vue'
import ImageField from '../../components/ImageField.vue'
import { loadPublicConfig, notify } from '../../store'
import { loginBackground } from '../../theme'

const b = ref(null)
const logs = ref(null)
const status = ref(null)
const saving = ref(false)

onMounted(async () => {
  try {
    ;[b.value, logs.value, status.value] = await Promise.all([
      api.get('/api/admin/settings/branding'),
      api.get('/api/admin/settings/logs'),
      api.get('/api/admin/settings/status'),
    ])
  } catch (e) {
    notify(e.message, 'error')
  }
})

const BG_TYPES = [
  { id: 'default', label: 'Default', icon: 'fa-solid fa-wand-magic-sparkles' },
  { id: 'color', label: 'Colour', icon: 'fa-solid fa-fill-drip' },
  { id: 'gradient', label: 'Gradient', icon: 'fa-solid fa-swatchbook' },
  { id: 'image', label: 'Image', icon: 'fa-regular fa-image' },
]
const loginBg = computed(() => loginBackground(b.value))

async function save() {
  saving.value = true
  try {
    b.value = await api.put('/api/admin/settings/branding', b.value)
    await loadPublicConfig()
    notify('Branding saved')
  } catch (e) {
    notify(e.message, 'error')
  } finally {
    saving.value = false
  }
}
async function saveStatus() {
  try {
    status.value = await api.put('/api/admin/settings/status', status.value)
    notify('Status check settings saved')
  } catch (e) {
    notify(e.message, 'error')
  }
}
async function saveLogs() {
  try {
    logs.value = await api.put('/api/admin/settings/logs', logs.value)
    notify('Logging settings saved')
  } catch (e) {
    notify(e.message, 'error')
  }
}
</script>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 380px);
  gap: 18px;
  align-items: start;
}
.layout .card-ui {
  margin: 0;
}
.preview-col {
  position: sticky;
  top: 80px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.login-preview {
  position: relative;
  overflow: hidden;
  isolation: isolate;
  border-radius: 12px;
  background-size: cover;
  background-position: center;
  padding: 36px 24px 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-height: 380px;
  justify-content: center;
}
.mini-card {
  background: var(--ui-surface);
  border-radius: 12px;
  padding: 22px;
  width: 100%;
  max-width: 270px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.3);
  text-align: center;
}
.mini-logo {
  max-height: 46px;
  max-width: 140px;
  object-fit: contain;
}
.mini-mark {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
}
.mini-card .muted {
  font-size: 0.8rem;
}
.mini-msg {
  font-size: 0.75rem;
  margin: 6px 0 0;
  padding: 6px 8px;
  width: 100%;
}
.fake-input {
  height: 28px;
  width: 100%;
  border: 1px solid var(--ui-border);
  border-radius: 6px;
  margin-top: 6px;
}
.fake-btn {
  width: 100%;
  color: #fff;
  font-size: 0.8rem;
  font-weight: 600;
  padding: 7px;
  border-radius: 6px;
  margin-top: 8px;
}
.mini-footer {
  color: #fff;
  font-size: 0.75rem;
  margin-top: 12px;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.5);
}
.pv-bg,
.pv-overlay {
  position: absolute;
  inset: 0;
  z-index: -2;
}
.pv-overlay {
  z-index: -1;
  background: #000;
}
.sub {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--ui-muted);
  margin: 20px 0 10px;
  padding-top: 14px;
  border-top: 1px solid var(--ui-border);
}
.seg {
  display: flex;
  gap: 4px;
  padding: 3px;
  border-radius: 9px;
  background: var(--ui-surface-2);
  border: 1px solid var(--ui-border);
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.seg button {
  flex: 1;
  font: inherit;
  font-size: 0.85rem;
  border: none;
  background: none;
  color: var(--ui-muted);
  padding: 7px 8px;
  border-radius: 6px;
  cursor: pointer;
  white-space: nowrap;
}
.seg button.active {
  background: var(--ui-surface);
  color: var(--ui-text);
  font-weight: 600;
  box-shadow: var(--ui-shadow);
}
.small {
  font-size: 0.85rem;
}
input[type='range'] {
  accent-color: var(--brand);
}
@media (max-width: 1000px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .preview-col {
    position: static;
  }
}
</style>
