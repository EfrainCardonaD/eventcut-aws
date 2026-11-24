<script setup>
import { computed, ref, watch } from 'vue'
import { useCommunityStore } from '@/stores/community'

const props = defineProps({
  eventId: {
    type: String,
    default: '',
  },
  communityId: {
    type: String,
    default: '',
  },
  communityName: {
    type: String,
    default: '',
  },
  canFetchRequests: {
    type: Boolean,
    default: false,
  },
})

const communityStore = useCommunityStore()

const isLoading = ref(false)
const matchedRequest = ref(null)
const fetchError = ref(false)
const lastFetchedKey = ref('')

// ID de comunidad descubierto dinámicamente cuando no se proporciona como prop.
const discoveredCommunityId = ref(null)
const discoveredCommunityName = ref('')

const effectiveCommunityId = computed(() => {
  return props.communityId || discoveredCommunityId.value || null
})

const shouldFetch = computed(() => {
  return Boolean(props.canFetchRequests && props.eventId)
})

const fetchKey = computed(() => `${effectiveCommunityId.value || 'discover'}::${props.eventId}`)

/**
 * Busca la solicitud cuando ya conocemos el communityId.
 */
const fetchRequestStatus = async () => {
  if (!effectiveCommunityId.value || !props.eventId) return

  const key = fetchKey.value
  if (lastFetchedKey.value === key && matchedRequest.value !== null) return

  isLoading.value = true
  fetchError.value = false

  try {
    const result = await communityStore.fetchCommunityRequests(effectiveCommunityId.value, { limit: 50 })

    if (!result.success) {
      fetchError.value = true
      matchedRequest.value = null
      lastFetchedKey.value = ''
      return
    }

    const items = result.items || []
    const found = items.find(
      (req) => String(req.event?.id || '') === String(props.eventId),
    ) || null

    matchedRequest.value = found
    lastFetchedKey.value = key
  } catch {
    fetchError.value = true
    matchedRequest.value = null
    lastFetchedKey.value = ''
  } finally {
    isLoading.value = false
  }
}

/**
 * Descubre la comunidad asociada al evento cuando no se proporciona communityId.
 * Busca en las comunidades del usuario (cache + fetch).
 */
const discoverAndFetch = async () => {
  if (!props.eventId || !shouldFetch.value) return

  isLoading.value = true
  fetchError.value = false

  try {
    const result = await communityStore.discoverEventCommunityRequest(props.eventId)

    if (!result.success) {
      fetchError.value = true
      matchedRequest.value = null
      return
    }

    if (result.request) {
      matchedRequest.value = result.request
      discoveredCommunityId.value = result.communityId || null

      // Obtener nombre de la comunidad desde el store.
      const communities = [
        ...(communityStore.myList || []),
        ...(communityStore.mySubscribedList || []),
        ...(communityStore.activeList || []),
      ]
      const community = communities.find((c) => String(c.id) === String(result.communityId))
      discoveredCommunityName.value = community?.name || ''
      lastFetchedKey.value = fetchKey.value
    } else {
      matchedRequest.value = null
      discoveredCommunityId.value = null
      discoveredCommunityName.value = ''
      lastFetchedKey.value = fetchKey.value
    }
  } catch {
    fetchError.value = true
    matchedRequest.value = null
  } finally {
    isLoading.value = false
  }
}

const status = computed(() => matchedRequest.value?.status || null)
const rejectionReason = computed(() => matchedRequest.value?.rejection_reason || '')

const reviewedAtLabel = computed(() => {
  const raw = matchedRequest.value?.reviewed_at
  if (!raw) return ''
  const parsed = new Date(raw)
  if (Number.isNaN(parsed.getTime())) return ''
  return new Intl.DateTimeFormat('es-MX', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(parsed)
})

const createdAtLabel = computed(() => {
  const raw = matchedRequest.value?.created_at
  if (!raw) return ''
  const parsed = new Date(raw)
  if (Number.isNaN(parsed.getTime())) return ''
  return new Intl.DateTimeFormat('es-MX', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(parsed)
})

const displayCommunityName = computed(() => {
  return props.communityName || discoveredCommunityName.value || 'la comunidad'
})

const statusConfig = computed(() => {
  if (!status.value) {
    if (!effectiveCommunityId.value) return null
    return {
      icon: 'info',
      label: `No se ha enviado solicitud a ${displayCommunityName.value}`,
      colorClasses: 'border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400',
      iconColor: 'text-slate-400 dark:text-slate-500',
    }
  }

  if (status.value === 'PENDING') {
    return {
      icon: 'schedule',
      label: 'Solicitud pendiente de revisión',
      colorClasses: 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300',
      iconColor: 'text-amber-500 dark:text-amber-400',
    }
  }

  if (status.value === 'APPROVED') {
    return {
      icon: 'check_circle',
      label: `Evento aprobado en ${displayCommunityName.value}`,
      colorClasses: 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-300',
      iconColor: 'text-emerald-500 dark:text-emerald-400',
    }
  }

  if (status.value === 'REJECTED') {
    return {
      icon: 'cancel',
      label: 'Solicitud rechazada',
      colorClasses: 'border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-300',
      iconColor: 'text-rose-500 dark:text-rose-400',
    }
  }

  return {
    icon: 'help',
    label: `Estado desconocido: ${status.value}`,
    colorClasses: 'border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400',
    iconColor: 'text-slate-400 dark:text-slate-500',
  }
})

const shouldRender = computed(() => {
  // Renderizar si: hay statusConfig (se encontró algo) o estamos cargando
  return shouldFetch.value && !fetchError.value && (isLoading.value || statusConfig.value !== null)
})

// Fetch cuando cambian las props relevantes
watch(
  () => [props.canFetchRequests, props.communityId, props.eventId],
  () => {
    if (!shouldFetch.value) {
      matchedRequest.value = null
      lastFetchedKey.value = ''
      discoveredCommunityId.value = null
      discoveredCommunityName.value = ''
      return
    }

    if (props.communityId) {
      // Ruta directa: ya conocemos la comunidad.
      fetchRequestStatus()
    } else {
      // Ruta discovery: buscar en las comunidades del usuario.
      discoverAndFetch()
    }
  },
  { immediate: true },
)
</script>

<template>
  <div v-if="shouldRender" class="w-full">
    <!-- Loading state -->
    <div
      v-if="isLoading && !matchedRequest"
      class="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400"
    >
      <span class="material-symbols-outlined animate-spin text-sm">progress_activity</span>
      Consultando estado de solicitud...
    </div>

    <!-- Status badge -->
    <div
      v-else-if="statusConfig"
      class="flex items-start gap-2.5 rounded-xl border px-3 py-2.5 text-xs transition-colors"
      :class="statusConfig.colorClasses"
    >
      <span
        class="material-symbols-outlined mt-px shrink-0 text-base"
        :class="[statusConfig.iconColor, status === 'APPROVED' ? 'icon-filled' : '']"
      >
        {{ statusConfig.icon }}
      </span>

      <div class="min-w-0 flex-1 space-y-0.5">
        <p class="font-semibold leading-snug">{{ statusConfig.label }}</p>

        <!-- PENDING: mostrar fecha de solicitud -->
        <p v-if="status === 'PENDING' && createdAtLabel" class="text-[11px] opacity-75">
          Enviada el {{ createdAtLabel }}
        </p>

        <!-- APPROVED: mostrar fecha de revisión -->
        <p v-if="status === 'APPROVED' && reviewedAtLabel" class="text-[11px] opacity-75">
          Aprobada el {{ reviewedAtLabel }}
        </p>

        <!-- REJECTED: mostrar motivo -->
        <template v-if="status === 'REJECTED'">
          <p v-if="rejectionReason" class="leading-snug opacity-90">
            <span class="font-bold">Motivo:</span> {{ rejectionReason }}
          </p>
          <p v-if="reviewedAtLabel" class="text-[11px] opacity-75">
            Rechazada el {{ reviewedAtLabel }}
          </p>
        </template>

        <!-- Sin solicitud: hint -->
        <p v-if="!status" class="text-[11px] opacity-75">
          Selecciona una comunidad y guarda para enviar la solicitud.
        </p>
      </div>
    </div>
  </div>
</template>
