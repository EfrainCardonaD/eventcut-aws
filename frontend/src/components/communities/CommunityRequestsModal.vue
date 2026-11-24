<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useScrollLock } from '@vueuse/core'
import { storeToRefs } from 'pinia'
import { useCommunityStore } from '@/stores/community'
import Alert from '@/components/util/Alert.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  community: {
    type: Object,
    default: null,
  },
  initialStatus: {
    type: String,
    default: 'PENDING',
  },
})

const emit = defineEmits(['update:modelValue', 'updated'])

const communityStore = useCommunityStore()
const { error, lastTraceId, isUpdatingRequest } = storeToRefs(communityStore)

const toast = ref({ show: false, type: 'info', title: '', message: '' })
const localError = ref('')

const isBodyScrollLocked = useScrollLock(typeof document !== 'undefined' ? document.body : null)

const statusFilter = ref('PENDING')
const limit = ref(20)
const offset = ref(0)

const rejectModeRequestId = ref('')
const rejectionReason = ref('')

const communityId = computed(() => props.community?.id || '')

const requests = computed(() => communityStore.getCommunityRequests(communityId.value))
const total = computed(() => communityStore.getCommunityRequestsTotal(communityId.value))
const isLoading = computed(() => communityStore.isCommunityRequestsLoading(communityId.value))

const canLoadMore = computed(() => requests.value.length < total.value)

const showToast = (type, title, message) => {
  toast.value = { show: true, type, title, message }
}

const formatDateTime = (value) => {
  if (!value) return 'No disponible'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'No disponible'
  return date.toLocaleString('es-MX', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const toStatusStyles = (status) => {
  switch (String(status || '').toUpperCase()) {
    case 'APPROVED':
      return 'bg-success-100 text-success-700 dark:bg-success-900/30 dark:text-success-300'
    case 'REJECTED':
      return 'bg-error-100 text-error-700 dark:bg-error-900/30 dark:text-error-300'
    case 'PENDING':
    default:
      return 'bg-warning-100 text-warning-700 dark:bg-warning-900/30 dark:text-warning-300'
  }
}

const closeModal = () => {
  if (isUpdatingRequest.value) return
  emit('update:modelValue', false)
}

const resetLocalState = () => {
  localError.value = ''
  rejectModeRequestId.value = ''
  rejectionReason.value = ''
  offset.value = 0
  statusFilter.value = props.initialStatus || 'PENDING'
}

const fetchRequests = async ({ append = false } = {}) => {
  if (!communityId.value) return

  localError.value = ''

  const status = String(statusFilter.value || '').toUpperCase()
  const statusParam = status === 'ALL' ? undefined : status

  const result = await communityStore.fetchCommunityRequests(communityId.value, {
    status: statusParam,
    limit: limit.value,
    offset: offset.value,
    append,
  })

  if (!result.success) {
    localError.value = result.error || 'No se pudieron cargar las solicitudes.'
  }
}

const refreshPendingCount = async () => {
  if (!communityId.value) return
  await communityStore.fetchPendingRequestsCount(communityId.value)
}

const onStatusChange = async (next) => {
  statusFilter.value = next
  offset.value = 0
  await fetchRequests({ append: false })
}

const onLoadMore = async () => {
  if (!canLoadMore.value || isLoading.value) return
  offset.value += limit.value
  await fetchRequests({ append: true })
}

const onApprove = async (request) => {
  if (!communityId.value || !request?.request_id) return

  localError.value = ''
  const result = await communityStore.updateCommunityRequest(communityId.value, request.request_id, {
    action: 'APPROVE',
  })

  if (!result.success) {
    localError.value = result.error || 'No se pudo aprobar la solicitud.'
    return
  }

  showToast('success', 'Solicitud aprobada', result.message || 'La solicitud fue aprobada correctamente.')
  await refreshPendingCount()
  await fetchRequests({ append: false })
  emit('updated', {
    communityId: communityId.value,
    action: 'APPROVE',
    requestId: request.request_id,
  })
}

const onStartReject = (request) => {
  if (isUpdatingRequest.value) return
  localError.value = ''
  rejectModeRequestId.value = String(request?.request_id || '')
  rejectionReason.value = ''
}

const onCancelReject = () => {
  rejectModeRequestId.value = ''
  rejectionReason.value = ''
  localError.value = ''
}

const onConfirmReject = async () => {
  if (!communityId.value || !rejectModeRequestId.value) return

  const requestId = rejectModeRequestId.value

  const reason = rejectionReason.value.trim()
  if (!reason) {
    localError.value = 'Debes escribir el motivo de rechazo para continuar.'
    return
  }

  localError.value = ''
  const result = await communityStore.updateCommunityRequest(communityId.value, requestId, {
    action: 'REJECT',
    rejection_reason: reason,
  })

  if (!result.success) {
    localError.value = result.error || 'No se pudo rechazar la solicitud.'
    return
  }

  showToast('success', 'Solicitud rechazada', result.message || 'La solicitud fue rechazada correctamente.')
  rejectModeRequestId.value = ''
  rejectionReason.value = ''
  await refreshPendingCount()
  await fetchRequests({ append: false })
  emit('updated', {
    communityId: communityId.value,
    action: 'REJECT',
    requestId,
  })
}

watch(
  () => props.modelValue,
  async (isOpen) => {
    isBodyScrollLocked.value = Boolean(isOpen)

    if (!isOpen) {
      return
    }

    resetLocalState()
    await nextTick()
    await refreshPendingCount()
    await fetchRequests({ append: false })
  },
  { immediate: true },
)

watch(
  () => props.community?.id,
  async () => {
    if (!props.modelValue) return
    resetLocalState()
    await refreshPendingCount()
    await fetchRequests({ append: false })
  },
)

onBeforeUnmount(() => {
  isBodyScrollLocked.value = false
})
</script>

<template>
  <Transition
    appear
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition duration-150 ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="modelValue"
      class="fixed inset-0 z-[90] flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm"
      @click.self="closeModal"
    >
      <div class="mx-auto flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white/90 shadow-2xl dark:border-slate-800 dark:bg-slate-900/90">
        <header class="flex items-start justify-between gap-3 border-b border-slate-200 p-6 dark:border-slate-800">
          <div>
            <p class="text-xs font-bold uppercase tracking-[0.2em] text-primary-600 dark:text-primary-400">Moderación</p>
            <h3 class="mt-1 font-headline text-xl font-black text-slate-900 dark:text-slate-100">
              Solicitudes de eventos
            </h3>
            <p class="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Comunidad: <span class="font-semibold">{{ community?.name || 'No disponible' }}</span>
            </p>
          </div>

          <button
            type="button"
            class="rounded-full p-2 text-slate-500 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 dark:hover:bg-slate-800"
            :disabled="isUpdatingRequest"
            @click="closeModal"
          >
            <span class="material-symbols-outlined">close</span>
          </button>
        </header>

        <div class="flex-1 overflow-y-auto p-6">
          <Alert
            v-model="toast.show"
            toast
            position="top-right"
            :type="toast.type"
            :title="toast.title"
            :message="toast.message"
            :duration="4200"
          />

          <div v-if="localError" class="mb-4 rounded-2xl border border-error-200 bg-error-50 p-3 text-sm text-error-700 dark:border-error-900/30 dark:bg-error-900/10 dark:text-error-300">
            {{ localError }}
            <span v-if="lastTraceId" class="ml-2 text-[11px] text-error-500 dark:text-error-400">(Trace: {{ lastTraceId }})</span>
          </div>

          <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div class="inline-flex rounded-full border border-slate-200 bg-slate-50 p-1 dark:border-slate-800 dark:bg-slate-950/40">
              <button
                type="button"
                class="rounded-full px-3 py-1 text-xs font-bold transition"
                :class="statusFilter === 'PENDING' ? 'bg-white text-slate-900 dark:bg-slate-800 dark:text-slate-100' : 'text-slate-500 dark:text-slate-400'"
                @click="onStatusChange('PENDING')"
              >
                Pendientes
              </button>
              <button
                type="button"
                class="rounded-full px-3 py-1 text-xs font-bold transition"
                :class="statusFilter === 'APPROVED' ? 'bg-white text-slate-900 dark:bg-slate-800 dark:text-slate-100' : 'text-slate-500 dark:text-slate-400'"
                @click="onStatusChange('APPROVED')"
              >
                Aprobadas
              </button>
              <button
                type="button"
                class="rounded-full px-3 py-1 text-xs font-bold transition"
                :class="statusFilter === 'REJECTED' ? 'bg-white text-slate-900 dark:bg-slate-800 dark:text-slate-100' : 'text-slate-500 dark:text-slate-400'"
                @click="onStatusChange('REJECTED')"
              >
                Rechazadas
              </button>
              <button
                type="button"
                class="rounded-full px-3 py-1 text-xs font-bold transition"
                :class="statusFilter === 'ALL' ? 'bg-white text-slate-900 dark:bg-slate-800 dark:text-slate-100' : 'text-slate-500 dark:text-slate-400'"
                @click="onStatusChange('ALL')"
              >
                Todas
              </button>
            </div>

            <div class="flex items-center gap-2">
              <span class="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                {{ requests.length }} / {{ total }}
              </span>
            </div>
          </div>

          <div v-if="isLoading && requests.length === 0" class="rounded-2xl border border-dashed border-slate-300 p-4 text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
            Cargando solicitudes...
          </div>

          <div v-else-if="requests.length === 0" class="rounded-2xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
            No hay solicitudes para mostrar.
          </div>

          <div v-else class="space-y-3">
            <article
              v-for="request in requests"
              :key="request.request_id"
              class="rounded-2xl border border-slate-200 bg-slate-50 p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950/40"
            >
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div class="min-w-0">
                  <h4 class="truncate text-sm font-black text-slate-900 dark:text-slate-100">
                    {{ request.event?.title || 'Evento sin título' }}
                  </h4>
                  <p class="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    <span class="font-semibold">Inicio:</span> {{ formatDateTime(request.event?.start_datetime) }}
                    <span class="mx-2 text-slate-300 dark:text-slate-700">•</span>
                    <span class="font-semibold">Solicitado:</span> {{ formatDateTime(request.created_at) }}
                  </p>
                  <p class="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    <span class="font-semibold">Solicitante:</span>
                    {{ request.event?.owner_display_name || 'No disponible' }}
                    <span v-if="request.requested_by" class="ml-1 text-[11px] text-slate-400">({{ request.requested_by }})</span>
                  </p>
                </div>

                <div class="flex items-center gap-2">
                  <span class="rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider" :class="toStatusStyles(request.status)">
                    {{ request.status }}
                  </span>
                </div>
              </div>

              <div v-if="request.reviewed_at" class="mt-3 rounded-xl bg-slate-100 p-3 text-xs text-slate-600 dark:bg-slate-900/40 dark:text-slate-300">
                <p>
                  <span class="font-semibold">Revisada:</span> {{ formatDateTime(request.reviewed_at) }}
                  <span v-if="request.reviewed_by" class="ml-1 text-[11px] text-slate-400">({{ request.reviewed_by }})</span>
                </p>
                <p v-if="request.rejection_reason" class="mt-2 rounded-lg bg-error-50 p-2 text-xs text-error-700 dark:bg-error-900/10 dark:text-error-300">
                  <span class="font-semibold">Motivo de rechazo:</span> {{ request.rejection_reason }}
                </p>
              </div>

              <div v-if="String(request.status).toUpperCase() === 'PENDING'" class="mt-4">
                <div v-if="rejectModeRequestId === String(request.request_id)" class="rounded-2xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
                  <label class="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Motivo de rechazo
                    <textarea
                      v-model="rejectionReason"
                      rows="3"
                      class="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200"
                      placeholder="Ej: No cumple los criterios de la comunidad"
                      :disabled="isUpdatingRequest"
                    ></textarea>
                  </label>

                  <div class="mt-3 flex flex-wrap items-center justify-end gap-2">
                    <button
                      type="button"
                      class="rounded-xl border border-slate-300 px-3 py-2 text-xs font-bold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                      :disabled="isUpdatingRequest"
                      @click="onCancelReject"
                    >
                      Cancelar
                    </button>
                    <button
                      type="button"
                      class="rounded-xl bg-error-600 px-3 py-2 text-xs font-bold text-white transition hover:bg-error-700 disabled:cursor-not-allowed disabled:opacity-60"
                      :disabled="isUpdatingRequest"
                      @click="onConfirmReject"
                    >
                      {{ isUpdatingRequest ? 'Enviando...' : 'Confirmar rechazo' }}
                    </button>
                  </div>
                </div>

                <div v-else class="flex flex-wrap items-center justify-end gap-2">
                  <button
                    type="button"
                    class="rounded-xl border border-slate-300 px-3 py-2 text-xs font-bold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                    :disabled="isUpdatingRequest || communityStore.isRequestUpdating(request.request_id)"
                    @click="onStartReject(request)"
                  >
                    Rechazar
                  </button>
                  <button
                    type="button"
                    class="rounded-xl bg-success-600 px-3 py-2 text-xs font-bold text-white transition hover:bg-success-700 disabled:cursor-not-allowed disabled:opacity-60"
                    :disabled="isUpdatingRequest || communityStore.isRequestUpdating(request.request_id)"
                    @click="onApprove(request)"
                  >
                    {{ isUpdatingRequest ? 'Aprobando...' : 'Aprobar' }}
                  </button>
                </div>
              </div>
            </article>
          </div>

          <div v-if="canLoadMore" class="mt-5 flex justify-center">
            <button
              type="button"
              class="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:hover:bg-slate-800"
              :disabled="isLoading"
              @click="onLoadMore"
            >
              {{ isLoading ? 'Cargando...' : 'Cargar más' }}
            </button>
          </div>

          <Alert
            v-if="error"
            :model-value="Boolean(error)"
            toast
            position="bottom-right"
            type="error"
            title="Error"
            :message="error"
            :dismissible="false"
            :duration="0"
          />
        </div>

        <footer class="border-t border-slate-200 p-4 dark:border-slate-800">
          <div class="flex items-center justify-end">
            <button
              type="button"
              class="rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
              :disabled="isUpdatingRequest"
              @click="closeModal"
            >
              Cerrar
            </button>
          </div>
        </footer>
      </div>
    </div>
  </Transition>
</template>

