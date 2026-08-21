import axios from 'axios'
import useStore from '../store'

const api = axios.create({ baseURL: '/api/v1', headers: { 'Content-Type': 'application/json' } })

export const apiRequestId = (error) =>
  error?.response?.headers?.['x-request-id'] || error?.response?.data?.request_id || null

export const apiErrorMessage = (error, fallback = 'حدث خطأ غير متوقع') => {
  const data = error?.response?.data
  const detail = data?.detail
  let message = fallback

  if (typeof detail === 'string' && detail.trim()) {
    message = detail
  } else if (Array.isArray(detail) && detail.length > 0) {
    message = detail.map((item) => {
      const location = (item.loc || []).filter((part) => part !== 'body').join('.')
      return `${location ? `${location}: ` : ''}${item.msg || 'قيمة غير صالحة'}`
    }).join('، ')
  } else if (typeof data?.message === 'string') {
    message = data.message
  } else if (error?.message) {
    message = error.message
  }

  const requestId = apiRequestId(error)
  return requestId ? `${message} — رقم التتبع: ${requestId}` : message
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('[SmartSocial API error]', {
      method: error?.config?.method,
      url: error?.config?.url,
      status: error?.response?.status,
      requestId: apiRequestId(error),
      detail: error?.response?.data?.detail || error?.message,
    })
    return Promise.reject(error)
  },
)

// أرفق رمز الجلسة تلقائياً على كل طلب
api.interceptors.request.use((config) => {
  const token = useStore.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// عند انتهاء الجلسة (401) سجّل الخروج تلقائياً
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && useStore.getState().token) {
      useStore.getState().logout()
    }
    return Promise.reject(err)
  }
)

// Auth
export const googleLogin = (credential) => api.post('/auth/google', { credential })
export const adminLogin  = (email, password) => api.post('/auth/admin-login', { email, password })
export const fetchMe     = () => api.get('/auth/me')
export const listAllUsers = () => api.get('/auth/users')

// Users
export const createUser = (data) => api.post('/users/', data)
export const getUser    = (id)   => api.get(`/users/${id}`)

// Brands
export const createBrand  = (userId, data) => api.post(`/brands/?user_id=${userId}`, data)
export const getBrand     = (id)            => api.get(`/brands/${id}`)
export const listBrands   = (userId)        => api.get(`/brands/user/${userId}`)
export const updateBrand  = (id, data)      => api.patch(`/brands/${id}`, data)

export const uploadBrandTemplate = (brandId, file) => {
  const form = new FormData(); form.append('file', file)
  return api.post(`/brands/${brandId}/template`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
}
export const addBrandExample = (brandId, data) => api.post(`/brands/${brandId}/examples`, data)
export const uploadDesignExample = (brandId, file) => {
  const form = new FormData(); form.append('file', file)
  return api.post(`/brands/${brandId}/examples/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
}
export const deleteExample    = (exId)    => api.delete(`/brands/examples/${exId}`)
export const listBrandExamples= (brandId) => api.get(`/brands/${brandId}/examples`)

// Products
export const createProduct      = (userId, data) => api.post(`/products/?user_id=${userId}`, data)
export const listProducts       = (userId)        => api.get(`/products/user/${userId}`)
export const deleteProduct      = (id)            => api.delete(`/products/${id}`)
export const uploadProductImage = (productId, file) => {
  const form = new FormData(); form.append('file', file)
  return api.post(`/products/${productId}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
}
export const bulkUploadProducts = (userId, file) => {
  const form = new FormData(); form.append('file', file)
  return api.post(`/products/bulk-upload?user_id=${userId}`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
}

// Plans
export const createPlan       = (userId, data) => api.post(`/plans/?user_id=${userId}`, data)
export const listPlans        = (userId)        => api.get(`/plans/user/${userId}`)
export const getPlan          = (id)            => api.get(`/plans/${id}`)
export const deletePlan       = (id)            => api.delete(`/plans/${id}`)
export const triggerGeneration= (planId)        => api.post(`/plans/${planId}/generate`)
export const regeneratePlan   = (planId)        => api.post(`/plans/${planId}/regenerate`)
export const getPlanStatus    = (planId)        => api.get(`/plans/${planId}/status`)
export const listPosts        = (planId)        => api.get(`/plans/${planId}/posts`)
export const approvePost      = (postId, approved) => api.patch(`/plans/posts/${postId}/approve`, { approved })

// Brand DNA + governed Adaptive Memory
export const getIntelligenceStatus = (brandId) => api.get(`/intelligence/brands/${brandId}/status`)
export const initializeIntelligence = (brandId, force = false) =>
  api.post(`/intelligence/brands/${brandId}/initialize?force=${force}`)
export const bootstrapBrandHistory = (brandId) => api.post(`/intelligence/brands/${brandId}/bootstrap-history`)
export const consolidateMemory = (brandId) => api.post(`/intelligence/brands/${brandId}/consolidate`)
export const generateMemoryPolicies = (brandId) => api.post(`/intelligence/brands/${brandId}/generate-policies`)
export const listMemoryPolicies = (brandId) => api.get(`/intelligence/brands/${brandId}/policies`)
export const activateMemoryPolicy = (policyId, approvedBy) =>
  api.post(`/intelligence/policies/${policyId}/activate`, { approved_by: approvedBy })
export const submitPostPerformance = (postId, data) =>
  api.post(`/intelligence/posts/${postId}/performance`, data)

// Chat (Orchestrator)
export const sendChatMessage = (data) => api.post('/chat/message', data)

// Scheduled posts
export const listScheduled  = (userId) => api.get(`/scheduled/user/${userId}`)
export const deleteScheduled = (id)     => api.delete(`/scheduled/${id}`)
export const updateScheduledTime = (id, scheduledAt) =>
  api.patch(`/scheduled/${id}/time`, { scheduled_at: scheduledAt })

// Events (المناسبات ضمن مدة الحملة)
export const listEvents = (start, days) =>
  api.get(`/events/`, { params: { start, days } })

// Monitoring — مراقبة استهلاك الموارد وتكلفة تنفيذ الوكلاء
export const getMonitoringOverview  = (period) => api.get('/monitoring/overview', { params: { period } })
export const getMonitoringAgents    = (period) => api.get('/monitoring/agents', { params: { period } })
export const getMonitoringCampaigns = (period, limit = 20) => api.get('/monitoring/campaigns', { params: { period, limit } })
export const getMonitoringErrors    = (period, limit = 20) => api.get('/monitoring/errors', { params: { period, limit } })

export default api
