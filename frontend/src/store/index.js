import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const useStore = create(
  persist(
    (set) => ({
      // Current user (simple, no auth for MVP)
      user: null,
      setUser: (user) => set({ user }),

      // Active brand
      activeBrandId: null,
      setActiveBrandId: (id) => set({ activeBrandId: id }),
    }),
    { name: 'ai-marketing-os' }
  )
)

export default useStore
