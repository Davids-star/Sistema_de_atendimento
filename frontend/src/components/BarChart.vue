<script setup>
// Gráfico de barras simples (sem biblioteca externa).
// items: [{ label: '05/03', value: 123, tip: 'texto ao passar o mouse' }]
import { computed } from 'vue'

const props = defineProps({
  items: { type: Array, required: true },
  color: { type: String, default: 'primary' },
  height: { type: Number, default: 160 },
})

const max = computed(() => Math.max(1, ...props.items.map((i) => i.value)))
// Mostra poucos rótulos no eixo para não embolar quando há muitos dias.
const labelEvery = computed(() => Math.max(1, Math.ceil(props.items.length / 8)))
</script>

<template>
  <div v-if="items.length" class="chart" :style="{ height: `${height}px` }" role="img">
    <div v-for="(item, i) in items" :key="i" class="col" :title="item.tip">
      <div class="bar-area">
        <div class="bar" :style="{ height: `${(item.value / max) * 100}%`, background: `rgb(var(--v-theme-${color}))` }"
             :class="{ empty: item.value === 0 }" />
      </div>
      <div class="label">{{ i % labelEvery === 0 ? item.label : '' }}</div>
    </div>
  </div>
  <div v-else class="text-body-medium text-medium-emphasis text-center py-8">Sem dados no período.</div>
</template>

<style scoped>
.chart { display: flex; align-items: stretch; gap: 2px; }
.col { flex: 1 1 0; min-width: 0; display: flex; flex-direction: column; }
.bar-area { flex: 1; display: flex; align-items: flex-end; }
.bar { width: 100%; min-height: 3px; border-radius: 3px 3px 0 0; opacity: 0.9; }
.bar.empty { opacity: 0.15; }
.col:hover .bar { opacity: 1; }
.label { height: 18px; font-size: 11px; text-align: center; white-space: nowrap; overflow: visible;
         color: rgba(var(--v-theme-on-surface), 0.6); }
</style>
