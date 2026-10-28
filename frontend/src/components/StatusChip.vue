<script setup>
defineProps({ status: { type: String, required: true } })
const META = {
  pending: { label: 'Pendente', color: 'warning' },
  confirmed: { label: 'Confirmado', color: 'success' },
  completed: { label: 'Concluído', color: 'primary' },
  no_show: { label: 'Não veio', color: 'error' },
  cancelled: { label: 'Cancelado', color: undefined },
}
</script>

<template>
  <v-chip size="small" variant="tonal" :color="META[status]?.color">{{ META[status]?.label ?? status }}</v-chip>
</template>
