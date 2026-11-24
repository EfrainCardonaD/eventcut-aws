import { defineStore } from 'pinia'
import communitiesApi from '@/utils/communitiesApi'
import { getApiMessage, getApiPayload, mapApiCodeToUxAction, toApiErrorResult } from '@/utils/apiFactory'
import { updateCommunityWithSignedImageUpload } from '@/utils/communityImageFactory'

const normalizeSocialLinks = (links) => {
  if (!links || typeof links !== 'object' || Array.isArray(links)) return null

  const normalized = {
    whatsapp: typeof links.whatsapp === 'string' ? links.whatsapp.trim() : '',
    facebook: typeof links.facebook === 'string' ? links.facebook.trim() : '',
    instagram: typeof links.instagram === 'string' ? links.instagram.trim() : '',
  }

  const hasAny = Object.values(normalized).some(Boolean)
  return hasAny ? normalized : null
}

const normalizeImageUrl = (source) => {
  if (!source || typeof source !== 'object') return null
  const candidates = [source.image_url, source.imageUrl, source.image, source.cover_url, source.coverUrl]
  const first = candidates.find((value) => typeof value === 'string' && value.trim())
  return first ? first.trim() : null
}

const toNullableNumber = (value) => {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

const normalizeCommunity = (rawCommunity) => {
  const imageUrl = normalizeImageUrl(rawCommunity)
  return {
    ...rawCommunity,
    social_links: normalizeSocialLinks(rawCommunity?.social_links),
    image_url: imageUrl,
    category_id: toNullableNumber(rawCommunity?.category_id),
    events_count: Number(rawCommunity?.events_count || 0),
  }
}

const normalizeEvent = (rawEvent) => {
  const imageUrl = normalizeImageUrl(rawEvent)
  const description =
    rawEvent?.description ??
    rawEvent?.description_html ??
    rawEvent?.descriptionHtml ??
    rawEvent?.content ??
    rawEvent?.body ??
    rawEvent?.details ??
    ''

  return {
    ...rawEvent,
    social_links: normalizeSocialLinks(rawEvent?.social_links),
    image_url: imageUrl,
    description: typeof description === 'string' ? description : '',
    community_id: rawEvent?.community_id || rawEvent?.communityId || null,
    community_name: rawEvent?.community_name || rawEvent?.communityName || rawEvent?.community?.name || null,
    category_id: rawEvent?.category_id ? Number(rawEvent.category_id) : null,
    score: Number(rawEvent?.score || 0),
  }
}

const toStoreErrorResult = (error, fallbackMessage) => {
  const baseResult = toApiErrorResult(error, fallbackMessage)
  const ux = mapApiCodeToUxAction(baseResult.code)

  if (!ux && baseResult.status === 422) {
    return {
      ...baseResult,
      uxAction: 'SHOW_FIELD_ERRORS',
      uxMessage: 'Corrige los campos marcados e intenta nuevamente.',
    }
  }

  if (!ux) return baseResult

  return {
    ...baseResult,
    uxAction: ux.action,
    uxMessage: ux.message,
  }
}

export const useCommunityStore = defineStore('community', {
  state: () => ({
    activeList: [],
    activeTotal: 0,
    selectedCommunityId: '',
    myList: [],
    myTotal: 0,
    mySubscribedList: [],
    mySubscribedTotal: 0,
    detail: null,
    events: [],
    // Legacy (mantener por compatibilidad): ultima lista de solicitudes cargada.
    requests: [],
    requestsTotal: 0,

    // Nuevo: cache por comunidad.
    requestsByCommunityId: {},
    requestsTotalByCommunityId: {},
    pendingRequestsCountByCommunityId: {},
    isLoadingList: false,
    isLoadingMyList: false,
    isLoadingMySubscribedList: false,
    isLoadingDetail: false,
    isLoadingEvents: false,
    // Legacy: loading del ultimo fetch.
    isLoadingRequests: false,
    isSavingCommunity: false,
    isUpdatingCommunity: false,
    isDeletingCommunity: false,
    isSendingRequest: false,
    // Legacy: updating del ultimo PATCH.
    isUpdatingRequest: false,
    loadingRequestCommunityIds: [],
    updatingRequestIds: [],
    subscribingCommunityIds: [],
    error: null,
    lastTraceId: null,
  }),

  getters: {
    selectedCommunity(state) {
      if (!state.selectedCommunityId) return null
      return state.activeList.find((item) => item.id === state.selectedCommunityId) || null
    },
    isSubscribed(state) {
      const subscribedIds = new Set((state.mySubscribedList || []).map((item) => item.id))
      return (communityId) => Boolean(communityId && subscribedIds.has(communityId))
    },
    isSubscriptionUpdating(state) {
      const pendingIds = new Set(state.subscribingCommunityIds || [])
      return (communityId) => Boolean(communityId && pendingIds.has(communityId))
    },

    getCommunityRequests(state) {
      return (communityId) => {
        const key = communityId ? String(communityId) : ''
        return Array.isArray(state.requestsByCommunityId?.[key]) ? state.requestsByCommunityId[key] : []
      }
    },

    getCommunityRequestsTotal(state) {
      return (communityId) => {
        const key = communityId ? String(communityId) : ''
        const value = state.requestsTotalByCommunityId?.[key]
        return Number.isFinite(Number(value)) ? Number(value) : 0
      }
    },

    getPendingRequestsCount(state) {
      return (communityId) => {
        const key = communityId ? String(communityId) : ''
        const value = state.pendingRequestsCountByCommunityId?.[key]
        return Number.isFinite(Number(value)) ? Number(value) : 0
      }
    },

    isCommunityRequestsLoading(state) {
      const pendingIds = new Set(state.loadingRequestCommunityIds || [])
      return (communityId) => Boolean(communityId && pendingIds.has(String(communityId)))
    },

    isRequestUpdating(state) {
      const pendingIds = new Set(state.updatingRequestIds || [])
      return (requestId) => Boolean(requestId && pendingIds.has(String(requestId)))
    },
  },

  actions: {
    async requestWithPathFallback(requestFn, path) {
      try {
        return await requestFn(path)
      } catch (error) {
        const status = Number(error?.response?.status || 0)
        const normalizedPath = String(path || '')
        const canFallback = status === 404 && normalizedPath.startsWith('/api/v1/')
        if (!canFallback) throw error

        const fallbackPath = normalizedPath.replace('/api/v1/', '/v1/')
        return await requestFn(fallbackPath)
      }
    },

    setSelectedCommunityId(communityId) {
      this.selectedCommunityId = communityId || ''
    },

    async fetchActiveCommunities(params = {}) {
      this.isLoadingList = true
      this.error = null

      try {
        const response = await communitiesApi.get('/api/v1/communities', {
          params: {
            search: params.search || undefined,
            category_id: toNullableNumber(params.category_id) || undefined,
            limit: Number(params.limit || 20),
            offset: Number(params.offset || 0),
          },
        })

        const payload = getApiPayload(response)
        const items = Array.isArray(payload?.items) ? payload.items : []
        this.activeList = items.map(normalizeCommunity)
        this.activeTotal = Number(payload?.total || this.activeList.length)

        if (!this.selectedCommunityId && this.activeList[0]?.id) {
          this.selectedCommunityId = this.activeList[0].id
        }

        return { success: true }
      } catch (error) {
        const result = toStoreErrorResult(error, 'No se pudieron cargar las comunidades.')
        this.error = result.error
        this.lastTraceId = result.traceId || null
        return result
      } finally {
        this.isLoadingList = false
      }
    },

    async fetchMyCommunities(params = {}) {
      this.isLoadingMyList = true
      this.error = null

      try {
        const response = await communitiesApi.get('/api/v1/communities/my', {
          params: {
            limit: Number(params.limit || 20),
            offset: Number(params.offset || 0),
          },
        })

        const payload = getApiPayload(response)
        const items = Array.isArray(payload?.items) ? payload.items : []
        this.myList = items.map(normalizeCommunity)
        this.myTotal = Number(payload?.total || this.myList.length)
        return { success: true }
      } catch (error) {
        const result = toStoreErrorResult(error, 'No se pudieron cargar tus comunidades.')
        this.error = result.error
        this.lastTraceId = result.traceId || null
        return result
      } finally {
        this.isLoadingMyList = false
      }
    },

    async fetchMySubscribedCommunities(params = {}) {
      this.isLoadingMySubscribedList = true
      this.error = null

      try {
        const response = await communitiesApi.get('/api/v1/communities/my/subscriptions', {
          params: {
            limit: Number(params.limit || 20),
            offset: Number(params.offset || 0),
          },
        })

        const payload = getApiPayload(response)
        const items = Array.isArray(payload?.items) ? payload.items : []
        this.mySubscribedList = items.map(normalizeCommunity)
        this.mySubscribedTotal = Number(payload?.total || this.mySubscribedList.length)
        return { success: true }
      } catch (error) {
        const result = toStoreErrorResult(error, 'No se pudieron cargar tus suscripciones.')
        this.error = result.error
        this.lastTraceId = result.traceId || null
        return result
      } finally {
        this.isLoadingMySubscribedList = false
      }
    },

    async fetchCommunityDetail(communityId) {
      if (!communityId) return { success: false, error: 'Comunidad invalida.' }
      this.isLoadingDetail = true
      this.error = null

      try {
        const response = await communitiesApi.get(`/api/v1/communities/${communityId}`)
        this.detail = normalizeCommunity(getApiPayload(response))
        return { success: true }
      } catch (error) {
        const result = toStoreErrorResult(error, 'No se pudo obtener el detalle de la comunidad.')
        this.error = result.error
        this.lastTraceId = result.traceId || null
        return result
      } finally {
        this.isLoadingDetail = false
      }
    },

    async fetchCommunityEvents(communityId, params = {}) {
      if (!communityId) {
        this.events = []
        return { success: true }
      }

      this.isLoadingEvents = true
      this.error = null

      try {
        const response = await communitiesApi.get(`/api/v1/communities/${communityId}/events`, {
          params: {
            from: params.from || undefined,
            to: params.to || undefined,
            limit: Number(params.limit || 50),
            offset: Number(params.offset || 0),
          },
        })

        const payload = getApiPayload(response)
        const items = Array.isArray(payload?.items) ? payload.items : []
        this.events = items.map(normalizeEvent)
        return { success: true }
      } catch (error) {
        const result = toStoreErrorResult(error, 'No se pudieron cargar los eventos de la comunidad.')
        this.error = result.error
        this.lastTraceId = result.traceId || null
        this.events = []
        return result
      } finally {
        this.isLoadingEvents = false
      }
    },

    async createCommunity(payload) {
      this.isSavingCommunity = true
      this.error = null

      try {
        const response = await communitiesApi.post('/api/v1/communities', payload)
        const created = normalizeCommunity(getApiPayload(response))

        this.myList = [created, ...this.myList.filter((item) => item.id !== created.id)]
        this.myTotal = this.myList.length

        return {
          success: true,
          message: getApiMessage(response) || 'Comunidad enviada a revision',
          community: created,
        }
      } catch (error) {
        const result = toStoreErrorResult(error, 'No se pudo crear la comunidad.')
        this.error = result.error
        this.lastTraceId = result.traceId || null
        return result
      } finally {
        this.isSavingCommunity = false
      }
    },

    async updateCommunity(communityId, payload) {
      if (!communityId) return { success: false, error: 'Comunidad invalida.' }
      this.isUpdatingCommunity = true
      this.error = null

      try {
        const { response, updatedCommunity } = await updateCommunityWithSignedImageUpload(communityId, payload || {})
        const updatedPayload = updatedCommunity || getApiPayload(response)
        const fallbackPayload = { ...(payload || {}) }
        delete fallbackPayload.imageFile
        delete fallbackPayload.imageAction
        const fallbackCommunity = {
          id: communityId,
          ...fallbackPayload,
        }
        const updated = normalizeCommunity(updatedPayload?.id ? updatedPayload : fallbackCommunity)

        const mergeById = (item) => {
          if (item.id !== communityId) return item
          return normalizeCommunity({ ...item, ...updated })
        }

        this.activeList = this.activeList.map(mergeById)
        this.myList = this.myList.map(mergeById)
        this.mySubscribedList = this.mySubscribedList.map(mergeById)

        if (this.detail?.id === communityId) {
          this.detail = normalizeCommunity({ ...this.detail, ...updated })
        }

        return {
          success: true,
          message: getApiMessage(response) || 'Comunidad actualizada.',
          community: updated,
        }
      } catch (error) {
        const result = toStoreErrorResult(error, 'No se pudo actualizar la comunidad.')
        this.error = result.error
        this.lastTraceId = result.traceId || null
        return result
      } finally {
        this.isUpdatingCommunity = false
      }
    },

    async updateCommunityCategory(communityId, categoryId) {
      if (!communityId) return { success: false, error: 'Comunidad invalida.' }

      const parsedCategoryId = toNullableNumber(categoryId)
      if (!parsedCategoryId) return { success: false, error: 'Categoria invalida.' }

      const result = await this.updateCommunity(communityId, { category_id: parsedCategoryId })
      if (!result.success) {
        return {
          ...result,
          error: result.error || 'No se pudo actualizar la categoria de la comunidad.',
        }
      }

      return {
        ...result,
        message: result.message || 'Categoria actualizada.',
      }
    },

    async deleteCommunity(communityId) {
      if (!communityId) return { success: false, error: 'Comunidad invalida.' }

      this.isDeletingCommunity = true
      this.error = null

      try {
        await communitiesApi.delete(`/api/v1/communities/${communityId}`)

        this.activeList = this.activeList.filter((item) => item.id !== communityId)
        this.myList = this.myList.filter((item) => item.id !== communityId)
        this.mySubscribedList = this.mySubscribedList.filter((item) => item.id !== communityId)
        this.activeTotal = this.activeList.length
        this.myTotal = this.myList.length
        this.mySubscribedTotal = this.mySubscribedList.length

        if (this.selectedCommunityId === communityId) {
          this.selectedCommunityId = this.activeList[0]?.id || ''
        }

        if (this.detail?.id === communityId) {
          this.detail = null
          this.events = []
        }

        return {
          success: true,
          message: 'Comunidad eliminada.',
        }
      } catch (error) {
        const result = toStoreErrorResult(error, 'No se pudo eliminar la comunidad.')
        this.error = result.error
        this.lastTraceId = result.traceId || null
        return result
      } finally {
        this.isDeletingCommunity = false
      }
    },

    async subscribeToCommunity(communityId) {
      if (!communityId) return { success: false, error: 'Comunidad invalida.' }
      this.error = null

      if (!this.subscribingCommunityIds.includes(communityId)) {
        this.subscribingCommunityIds = [...this.subscribingCommunityIds, communityId]
      }

      try {
        const response = await communitiesApi.post(`/api/v1/communities/${communityId}/subscribe`)

        const foundInActive = this.activeList.find((item) => item.id === communityId)
        if (foundInActive && !this.mySubscribedList.some((item) => item.id === communityId)) {
          this.mySubscribedList = [foundInActive, ...this.mySubscribedList]
        }
        this.mySubscribedTotal = this.mySubscribedList.length

        return {
          success: true,
          message: getApiMessage(response) || 'Suscripcion registrada.',
          data: getApiPayload(response),
        }
      } catch (error) {
        const result = toStoreErrorResult(error, 'No se pudo registrar la suscripcion.')
        this.error = result.error
        this.lastTraceId = result.traceId || null
        return result
      } finally {
        this.subscribingCommunityIds = this.subscribingCommunityIds.filter((id) => id !== communityId)
      }
    },

    async unsubscribeFromCommunity(communityId) {
      if (!communityId) return { success: false, error: 'Comunidad invalida.' }
      this.error = null

      if (!this.subscribingCommunityIds.includes(communityId)) {
        this.subscribingCommunityIds = [...this.subscribingCommunityIds, communityId]
      }

      try {
        await communitiesApi.delete(`/api/v1/communities/${communityId}/subscribe`)
        this.mySubscribedList = this.mySubscribedList.filter((item) => item.id !== communityId)
        this.mySubscribedTotal = this.mySubscribedList.length
        return {
          success: true,
          message: 'Suscripcion eliminada.',
        }
      } catch (error) {
        const result = toStoreErrorResult(error, 'No se pudo eliminar la suscripcion.')
        this.error = result.error
        this.lastTraceId = result.traceId || null
        return result
      } finally {
        this.subscribingCommunityIds = this.subscribingCommunityIds.filter((id) => id !== communityId)
      }
    },

    async requestEventJoin(communityId, eventId) {
      if (!communityId || !eventId) {
        return { success: false, error: 'Datos incompletos para enviar la solicitud.' }
      }

      this.isSendingRequest = true
      this.error = null

      try {
        const response = await this.requestWithPathFallback(
          (path) => communitiesApi.post(path),
          `/api/v1/communities/${communityId}/events/${eventId}/request`,
        )

        return {
          success: true,
          message: getApiMessage(response) || 'Solicitud enviada al dueno de la comunidad.',
          data: getApiPayload(response),
        }
      } catch (error) {
        const result = toStoreErrorResult(error, 'No se pudo enviar la solicitud del evento.')
        this.error = result.error
        this.lastTraceId = result.traceId || null
        return result
      } finally {
        this.isSendingRequest = false
      }
    },

    normalizeCommunityRequest(rawRequest) {
      if (!rawRequest || typeof rawRequest !== 'object') return null

      const event = rawRequest.event && typeof rawRequest.event === 'object' ? rawRequest.event : null
      const ownerFirstName = event?.owner_first_name || event?.ownerFirstName || ''
      const ownerLastName = event?.owner_last_name || event?.ownerLastName || ''
      const ownerDisplayName = `${ownerFirstName} ${ownerLastName}`.trim() || event?.owner_display_name || event?.ownerDisplayName || null

      return {
        ...rawRequest,
        request_id: rawRequest.request_id || rawRequest.requestId || rawRequest.id,
        status: rawRequest.status || 'PENDING',
        rejection_reason: rawRequest.rejection_reason ?? rawRequest.rejectionReason ?? null,
        created_at: rawRequest.created_at || rawRequest.createdAt || null,
        reviewed_at: rawRequest.reviewed_at || rawRequest.reviewedAt || null,
        reviewed_by: rawRequest.reviewed_by || rawRequest.reviewedBy || null,
        requested_by: rawRequest.requested_by || rawRequest.requestedBy || null,
        event: event
          ? {
              ...event,
              id: event.id || event.event_id || event.eventId,
              owner_display_name: ownerDisplayName,
            }
          : null,
      }
    },

    async fetchCommunityRequests(communityId, params = {}) {
      if (!communityId) {
        return { success: false, error: 'Comunidad invalida.' }
      }

      const key = String(communityId)
      this.error = null
      this.isLoadingRequests = true

      if (!this.loadingRequestCommunityIds.includes(key)) {
        this.loadingRequestCommunityIds = [...this.loadingRequestCommunityIds, key]
      }

      try {
        const response = await this.requestWithPathFallback(
          (path) =>
            communitiesApi.get(path, {
              params: {
                status: params.status || undefined,
                limit: Number(params.limit || 20),
                offset: Number(params.offset || 0),
              },
            }),
          `/api/v1/communities/${communityId}/requests`,
        )

        const payload = getApiPayload(response)
        const items = Array.isArray(payload?.items) ? payload.items : []
        const normalized = items
          .map((item) => this.normalizeCommunityRequest(item))
          .filter(Boolean)

        const total = Number(payload?.total || normalized.length)
        const shouldAppend = Boolean(params.append)

        const existing = Array.isArray(this.requestsByCommunityId[key]) ? this.requestsByCommunityId[key] : []
        const merged = shouldAppend
          ? [...existing, ...normalized]
          : normalized

        // Deduplicar por request_id (por si el backend devuelve overlaps al paginar).
        const seen = new Set()
        const unique = merged.filter((item) => {
          const rid = String(item.request_id || '')
          if (!rid) return true
          if (seen.has(rid)) return false
          seen.add(rid)
          return true
        })

        this.requestsByCommunityId = {
          ...(this.requestsByCommunityId || {}),
          [key]: unique,
        }
        this.requestsTotalByCommunityId = {
          ...(this.requestsTotalByCommunityId || {}),
          [key]: total,
        }

        // Legacy
        this.requests = unique
        this.requestsTotal = total

        return { success: true, items: unique, total }
      } catch (error) {
        const result = toStoreErrorResult(error, 'No se pudieron cargar las solicitudes de la comunidad.')
        this.error = result.error
        this.lastTraceId = result.traceId || null
        return result
      } finally {
        this.isLoadingRequests = false
        this.loadingRequestCommunityIds = (this.loadingRequestCommunityIds || []).filter((id) => id !== key)
      }
    },

    async fetchPendingRequestsCount(communityId) {
      if (!communityId) return { success: false, error: 'Comunidad invalida.' }

      const key = String(communityId)
      this.error = null

      try {
        const response = await this.requestWithPathFallback(
          (path) =>
            communitiesApi.get(path, {
              params: {
                status: 'PENDING',
                limit: 1,
                offset: 0,
              },
            }),
          `/api/v1/communities/${communityId}/requests`,
        )

        const payload = getApiPayload(response)
        const total = Number(payload?.total || 0)
        this.pendingRequestsCountByCommunityId = {
          ...(this.pendingRequestsCountByCommunityId || {}),
          [key]: total,
        }
        return { success: true, total }
      } catch (error) {
        const result = toStoreErrorResult(error, 'No se pudo obtener el conteo de solicitudes pendientes.')
        this.error = result.error
        this.lastTraceId = result.traceId || null
        return result
      }
    },

    async updateCommunityRequest(communityId, requestId, payload) {
      if (!communityId || !requestId) {
        return { success: false, error: 'Datos incompletos para actualizar la solicitud.' }
      }

      const rid = String(requestId)
      this.error = null
      this.isUpdatingRequest = true
      if (!this.updatingRequestIds.includes(rid)) {
        this.updatingRequestIds = [...this.updatingRequestIds, rid]
      }

      try {
        const response = await this.requestWithPathFallback(
          (path) => communitiesApi.patch(path, payload || {}),
          `/api/v1/communities/${communityId}/requests/${requestId}`,
        )

        const updated = this.normalizeCommunityRequest(getApiPayload(response))
        const key = String(communityId)

        if (updated?.request_id) {
          const current = Array.isArray(this.requestsByCommunityId?.[key]) ? this.requestsByCommunityId[key] : []
          if (current.length) {
            const next = current.map((item) => (String(item.request_id) === String(updated.request_id) ? { ...item, ...updated } : item))
            this.requestsByCommunityId = {
              ...(this.requestsByCommunityId || {}),
              [key]: next,
            }
            // Legacy
            this.requests = next
          }
        }

        return {
          success: true,
          message: getApiMessage(response) || 'Solicitud actualizada.',
          data: updated,
        }
      } catch (error) {
        const result = toStoreErrorResult(error, 'No se pudo actualizar la solicitud.')
        this.error = result.error
        this.lastTraceId = result.traceId || null
        return result
      } finally {
        this.isUpdatingRequest = false
        this.updatingRequestIds = (this.updatingRequestIds || []).filter((id) => id !== rid)
      }
    },

    /**
     * Busca en datos cacheados locales si alguna comunidad tiene una solicitud
     * que involucre el evento dado. No hace llamadas al API.
     */
    findCachedRequestByEventId(eventId) {
      if (!eventId) return null
      const targetId = String(eventId)

      for (const [communityId, requests] of Object.entries(this.requestsByCommunityId || {})) {
        if (!Array.isArray(requests)) continue
        const found = requests.find((req) => String(req.event?.id || '') === targetId)
        if (found) {
          return { communityId, request: found }
        }
      }

      return null
    },

    /**
     * Descubre la solicitud comunitaria de un evento consultando las comunidades
     * del usuario (owner y suscritas). Primero revisa cache local, luego hace
     * fetch si es necesario. Pensado para llamarse cuando el evento no tiene
     * community_id explícito.
     */
    async discoverEventCommunityRequest(eventId) {
      if (!eventId) return { success: false, error: 'Evento invalido.' }

      // 1. Revisar cache local primero (instantáneo, sin API calls).
      const cached = this.findCachedRequestByEventId(eventId)
      if (cached) {
        return {
          success: true,
          communityId: cached.communityId,
          request: cached.request,
        }
      }

      // 2. Obtener comunidades del usuario (las que posee + las suscritas).
      try {
        if (!this.myList.length) {
          await this.fetchMyCommunities({ limit: 50 })
        }

        const communityIds = [
          ...new Set([
            ...this.myList.map((c) => c.id),
            ...this.mySubscribedList.map((c) => c.id),
          ].filter(Boolean)),
        ]

        if (!communityIds.length) {
          return { success: true, communityId: null, request: null }
        }

        // 3. Consultar solicitudes por cada comunidad (en paralelo, máximo 5).
        const batchSize = 5
        for (let i = 0; i < communityIds.length; i += batchSize) {
          const batch = communityIds.slice(i, i + batchSize)

          await Promise.all(
            batch.map(async (cid) => {
              const key = String(cid)
              // Skip si ya tenemos datos cacheados para esta comunidad.
              if (Array.isArray(this.requestsByCommunityId?.[key]) && this.requestsByCommunityId[key].length > 0) return
              await this.fetchCommunityRequests(cid, { limit: 50 })
            }),
          )

          // Check después de cada batch para no hacer llamadas innecesarias.
          const found = this.findCachedRequestByEventId(eventId)
          if (found) {
            return {
              success: true,
              communityId: found.communityId,
              request: found.request,
            }
          }
        }

        return { success: true, communityId: null, request: null }
      } catch {
        return { success: false, error: 'No se pudo descubrir la solicitud del evento.' }
      }
    },
  },
})
