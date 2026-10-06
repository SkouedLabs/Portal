<template>
  <div>
    <div class="page-title">
      <h1>Overview</h1>
      <div class="spacer" style="flex: 1"></div>
      <select v-model.number="days" class="input" style="width: auto" @change="load">
        <option :value="7">Last 7 days</option>
        <option :value="14">Last 14 days</option>
        <option :value="30">Last 30 days</option>
        <option :value="90">Last 90 days</option>
      </select>
    </div>

    <div v-if="stats" class="tiles">
      <div v-for="t in tiles" :key="t.label" class="tile card-ui">
        <span class="tile-label"><i :class="t.icon"></i> {{ t.label }}</span>
        <span class="tile-value" :class="t.cls">{{ t.value.toLocaleString() }}</span>
      </div>
    </div>

    <div v-if="stats" class="card-ui">
      <h2><i class="fa-solid fa-chart-column"></i> Daily activity</h2>
      <div class="legend">
        <span v-for="c in cats" :key="c.id"><i class="dot" :style="{ background: c.color }"></i>{{ c.label }}</span>
      </div>
      <div class="chart" role="img" :aria-label="`Activity over ${days} days`">
        <div v-for="d in chart" :key="d.day" class="col" :title="d.title">
          <div class="stack" :style="{ height: `${(d.total / maxDay) * 100}%` }">
            <div v-for="c in cats" :key="c.id" class="seg" :style="{ flexGrow: d[c.id] || 0, background: c.color }"></div>
          </div>
          <span class="day">{{ d.label }}</span>
        </div>
      </div>
    </div>

    <div v-if="stats" class="tops">
      <div v-for="t in tops" :key="t.title" class="card-ui">
        <h2><i :class="t.icon"></i> {{ t.title }}</h2>
        <ol v-if="t.rows.length" class="toplist">
          <li v-for="r in t.rows" :key="r.label">
            <span class="name">{{ r.label }}</span>
            <span class="bar"><span :style="{ width: `${(r.count / t.rows[0].count) * 100}%` }"></span></span>
            <span class="count">{{ r.count }}</span>
          </li>
        </ol>
        <p v-else class="muted">No data for this period.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../../api'
import { notify } from '../../store'

const days = ref(14)
const stats = ref(null)
const cats = [
  { id: 'navigation', label: 'Navigation', color: '#3b82f6' },
  { id: 'auth', label: 'Sign-ins', color: '#10b981' },
  { id: 'admin', label: 'Administration', color: '#f59e0b' },
]

async function load() {
  try {
    stats.value = await api.get(`/api/admin/stats?days=${days.value}`)
  } catch (e) {
    notify(e.message, 'error')
  }
}
onMounted(load)

const tiles = computed(() => {
  const t = stats.value.totals
  return [
    { label: 'Users', value: t.users, icon: 'fa-solid fa-user' },
    { label: 'Groups', value: t.groups, icon: 'fa-solid fa-users' },
    { label: 'Dashboards', value: t.dashboards, icon: 'fa-solid fa-table-columns' },
    { label: 'Active sessions', value: t.active_sessions, icon: 'fa-solid fa-signal' },
    { label: 'Sign-ins', value: t.logins, icon: 'fa-solid fa-right-to-bracket' },
    { label: 'Failed sign-ins', value: t.failed_logins, icon: 'fa-solid fa-user-lock', cls: t.failed_logins ? 'warn' : '' },
    { label: 'Dashboard views', value: t.views, icon: 'fa-solid fa-eye' },
    { label: 'Links opened', value: t.clicks, icon: 'fa-solid fa-arrow-pointer' },
  ]
})

const chart = computed(() => {
  const byDay = {}
  for (const r of stats.value.per_day) {
    byDay[r.day] ||= { total: 0 }
    byDay[r.day][r.category] = r.count
    byDay[r.day].total += r.count
  }
  const out = []
  const today = new Date()
  for (let i = days.value - 1; i >= 0; i--) {
    const d = new Date(today)
    d.setUTCDate(d.getUTCDate() - i)
    const key = d.toISOString().slice(0, 10)
    const v = byDay[key] || { total: 0 }
    out.push({
      day: key,
      ...v,
      label: days.value <= 31 || i % 7 === 0 ? `${d.getUTCDate()}/${d.getUTCMonth() + 1}` : '',
      title: `${key} — ${cats.map((c) => `${c.label}: ${v[c.id] || 0}`).join(', ')}`,
    })
  }
  return out
})
const maxDay = computed(() => Math.max(1, ...chart.value.map((d) => d.total)))

const tops = computed(() => [
  { title: 'Most used links', icon: 'fa-solid fa-arrow-pointer', rows: stats.value.top_links },
  { title: 'Most viewed dashboards', icon: 'fa-solid fa-table-columns', rows: stats.value.top_dashboards },
  { title: 'Most active users', icon: 'fa-solid fa-user', rows: stats.value.top_users },
])
</script>

<style scoped>
.tiles {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}
.tile {
  margin: 0 !important;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;
}
.tile-label {
  color: var(--ui-muted);
  font-size: 0.82rem;
}
.tile-label i {
  margin-right: 4px;
}
.tile-value {
  font-size: 1.7rem;
  font-weight: 700;
}
.tile-value.warn {
  color: var(--ui-warning);
}
.legend {
  display: flex;
  gap: 16px;
  font-size: 0.82rem;
  color: var(--ui-muted);
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 3px;
  margin-right: 6px;
}
.chart {
  display: flex;
  align-items: stretch;
  gap: 3px;
  height: 200px;
  padding-bottom: 22px;
}
.col {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  position: relative;
  min-width: 0;
}
.stack {
  display: flex;
  flex-direction: column-reverse;
  border-radius: 3px 3px 0 0;
  overflow: hidden;
  min-height: 1px;
  background: var(--ui-border);
}
.seg {
  flex-basis: 0;
  min-height: 0;
}
.day {
  position: absolute;
  bottom: -20px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 0.68rem;
  color: var(--ui-muted);
  white-space: nowrap;
}
.tops {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 18px;
  margin-top: 18px;
}
.tops .card-ui {
  margin: 0;
}
.toplist {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.toplist li {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) 1fr auto;
  gap: 10px;
  align-items: center;
  font-size: 0.9rem;
}
.name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bar {
  height: 8px;
  background: var(--ui-surface-2);
  border-radius: 4px;
  overflow: hidden;
}
.bar span {
  display: block;
  height: 100%;
  background: var(--brand);
  border-radius: 4px;
}
.count {
  font-variant-numeric: tabular-nums;
  color: var(--ui-muted);
  min-width: 30px;
  text-align: right;
}
</style>
