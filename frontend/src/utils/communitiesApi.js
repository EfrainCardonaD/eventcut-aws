import { createApiClient } from '@/utils/apiFactory'

const rawCommunitiesBaseUrl = import.meta.env.VITE_COMMUNITIES_API_BASE_URL || import.meta.env.VITE_EVENTS_API_BASE_URL
const shouldUseDevProxy = import.meta.env.DEV && String(import.meta.env.VITE_USE_DEV_PROXY || 'true') !== 'false'
const communitiesBaseUrl = shouldUseDevProxy
  ? ''
  : rawCommunitiesBaseUrl
    ? String(rawCommunitiesBaseUrl).replace(/\/$/, '')
    : ''

const communitiesApi = createApiClient(communitiesBaseUrl, {
  withCredentials: false,
  headers: {
    Accept: 'application/json',
  },
})

export default communitiesApi

