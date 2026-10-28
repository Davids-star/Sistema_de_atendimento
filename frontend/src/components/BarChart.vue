<script setup>
// Gráfico de barras simples (sem biblioteca externa).
// items: [{ label: '05/03', value: 123, tip: 'texto ao passar o mouse' }]
import { computed } from 'vue'

const props = defineProps({
  items: { type: Array, required: true },
  color: { type: String, default: 'primary' },
  height: { type: Number, default: 180 },
  format: { type: Function, default: (v) => String(v) },   // formata o valor máximo do eixo
})

const max = computed(() => Math.max(1, ...props.items.map((i) => i.value)))
// Mostra poucos rótulos no eixo para não embolar quando há muitos dias.
const labelEvery = computed(() => Math.max(1, Math.ceil(props.items.length / 8)))
</script>

<template>
  <div v-if="items.length" class="wrap">
    <div class="axis-max num">{{ format(max) }}</div>
    <div class="chart" :style="{ height: `${height}px` }" role="img">
      <div class="gridlines" aria-hidden="true"><i /><i /><i /></div>
      <div v-for="(item, i) in items" :key="i" class="col" :title="item.tip">
        <div class="bar-area">
          <div class="bar" :style="{ height: `${(item.value / max) * 100}%`, background: `rgb(var(--v-theme-${color}))` }"
               :class="{ empty: item.value === 0 }" />
        </div>
        <div class="label">{{ i % labelEvery === 0 ? item.label : '' }}</div>
      </div>
    </div>
  </div>
  <div v-else class="text-body-medium text-medium-emphasis text-center py-8">Sem dados no período.</div>
</template>

<style scoped>
.wrap { position: relative; }
.axis-max { font-size: 11px; color: rgba(var(--v-theme-on-surface), 0.5); margin-bottom: 4px; }
.chart { position: relative; display: flex; align-items: stretch; gap: 3px; }
.gridlines { position: absolute; left: 0; right: 0; top: 0; bottom: 18px; display: flex; flex-direction: column; justify-content: space-between; pointer-events: none; }
.gridlines i { display: block; border-top: 1px dashed rgba(var(--v-theme-on-surface), 0.1); }
.gridlines i:last-child { border-top-style: solid; }
.col { position: relative; flex: 1 1 0; min-width: 0; display: flex; flex-direction: column; }
.bar-area { flex: 1; display: flex; align-items: flex-end; }
.bar { width: 100%; min-height: 3px; border-radius: 5px 5px 2px 2px; opacity: 0.88; transition: opacity 0.12s, transform 0.12s; transform-origin: bottom; }
.bar.empty { opacity: 0.14; min-height: 2px; }
.col:hover .bar { opacity: 1; transform: scaleY(1.02); }
.label { height: 18px; padding-top: 4px; font-size: 11px; text-align: center; white-space: nowrap; overflow: visible;
         color: rgba(var(--v-theme-on-surface), 0.55); }
</style>
