import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1', headers: { 'Content-Type': 'application/json' } })

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

// Plans
export const createPlan       = (userId, data) => api.post(`/plans/?user_id=${userId}`, data)
export const listPlans        = (userId)        => api.get(`/plans/user/${userId}`)
export const getPlan          = (id)            => api.get(`/plans/${id}`)
export const deletePlan       = (id)            => api.delete(`/plans/${id}`)
export const triggerGeneration= (planId)        => api.post(`/plans/${planId}/generate`)
export const getPlanStatus    = (planId)        => api.get(`/plans/${planId}/status`)
export const listPosts        = (planId)        => api.get(`/plans/${planId}/posts`)
export const approvePost      = (postId, approved) => api.patch(`/plans/posts/${postId}/approve`, { approved })

export default api
