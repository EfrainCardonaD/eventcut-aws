<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  searchQuery: {
    type: String,
    default: '',
  },
  communities: {
    type: Array,
    default: () => [],
  },
  selectedCommunityId: {
    type: [String, Number],
    default: '',
  },
  title: {
    type: String,
    default: 'Seleccionar comunidad',
  },
  subtitle: {
    type: String,
    default: 'Busca por nombre y elige una comunidad.',
  },
})

const emit = defineEmits(['update:modelValue', 'update:searchQuery', 'pick'])

const selectedId = computed(() => String(props.selectedCommunityId || ''))

const onClose = () => {
  emit('update:modelValue', false)
}

const onPick = (communityId) => {
  emit('pick', communityId || '')
}

const searchModel = computed({
  get: () => props.searchQuery,
  set: (value) => emit('update:searchQuery', String(value || '')),
})
</script>

<template>
  <Transition
    appear
    enter-active-class="transition duration-150 ease-out"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition duration-100 ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div v-if="modelValue" class="absolute inset-0 z-20 flex items-center justify-center bg-slate-950/50 p-3 backdrop-blur-sm">
      <div class="w-full max-w-xl rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-2xl backdrop-blur-md dark:border-slate-800 dark:bg-slate-900/85">
        <div class="mb-3 flex items-center justify-between gap-3">
          <div>
            <p class="text-base font-extrabold text-slate-900 dark:text-slate-100">{{ title }}</p>
            <p class="text-xs text-slate-500 dark:text-slate-400">{{ subtitle }}</p>
          </div>
          <button type="button" class="rounded-full p-1.5 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800" @click="onClose">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>

        <input
          v-model="searchModel"
          type="text"
          placeholder="Buscar comunidad por nombre"
          class="w-full rounded-xl border border-slate-300 bg-slate-100 px-3 py-2 text-sm outline-none transition focus:border-tertiary-500 dark:border-slate-700 dark:bg-slate-950"
        />

        <div class="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
          <button
            type="button"
            class="w-full rounded-xl border border-dashed px-3 py-2 text-left text-xs font-semibold transition"
            :class="!selectedId ? 'border-tertiary-400 bg-tertiary-50 text-tertiary-700 dark:border-tertiary-500/60 dark:bg-tertiary-900/20 dark:text-tertiary-300' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800'"
            @click="onPick('')"
          >
            Sin comunidad
          </button>

          <button
            v-for="community in communities"
            :key="String(community.id)"
            type="button"
            class="w-full rounded-xl border px-3 py-2 text-left transition"
            :class="selectedId === String(community.id) ? 'border-tertiary-400 bg-tertiary-50 dark:border-tertiary-500/60 dark:bg-tertiary-900/20' : 'border-slate-200 bg-slate-50 hover:border-slate-300 hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700 dark:hover:bg-slate-800'"
            @click="onPick(community.id)"
          >
            <span class="flex items-start justify-between gap-2">
              <span class="truncate text-sm font-bold text-slate-900 dark:text-slate-100">{{ community.name }}</span>
              <span class="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                {{ community.events_count ?? community.approved_events_count ?? 0 }}
              </span>
            </span>
            <span class="mt-0.5 block truncate text-[11px] text-slate-500 dark:text-slate-400">{{ community.contact_email || 'Sin contacto publico' }}</span>
          </button>

          <p v-if="!communities.length" class="rounded-xl border border-dashed border-slate-300 p-3 text-center text-xs text-slate-500 dark:border-slate-700 dark:text-slate-400">
            No hay resultados para "{{ searchQuery }}".
          </p>
        </div>

        <div class="mt-3 flex justify-end">
          <button
            type="button"
            class="rounded-full border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
            @click="onClose"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

