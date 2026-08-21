import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const CHAT_GREETING = {
  role: 'agent',
  text: 'مرحباً! 👋 أنا مساعدك التسويقي لفيسبوك. اطلب مني كتابة منشور، تصميم صورة، مراجعة نص، أو إنشاء خطة محتوى.',
}

const uid = () =>
  (typeof crypto !== 'undefined' && crypto.randomUUID)
    ? crypto.randomUUID()
    : `c_${Date.now()}_${Math.floor(Math.random() * 1e6)}`

const makeConversation = () => ({
  id: uid(),
  title: 'محادثة جديدة',
  messages: [CHAT_GREETING],
  sessionId: null,
  createdAt: Date.now(),
})

const titleFrom = (messages) => {
  const firstUser = messages.find((m) => m.role === 'user')
  if (!firstUser) return 'محادثة جديدة'
  return firstUser.text.slice(0, 30) + (firstUser.text.length > 30 ? '…' : '')
}

const useStore = create(
  persist(
    (set, get) => {
      const initial = makeConversation()
      return {
        // ── Auth ────────────────────────────────────────────────────────────
        user: null,
        token: null,
        setUser: (user) => set({ user }),

        // تسجيل الدخول: يخزّن المستخدم والرمز
        login: ({ user, token }) => set({ user, token }),

        // تسجيل الخروج: يمسح الجلسة ويعيد ضبط المحادثات
        logout: () => {
          const c = makeConversation()
          set({ user: null, token: null, activeBrandId: null,
                conversations: [c], activeId: c.id })
        },

        isAuthenticated: () => !!get().token && !!get().user,
        isAdmin: () => get().user?.role === 'super_admin',

        // Active brand
        activeBrandId: null,
        setActiveBrandId: (id) => set({ activeBrandId: id }),

        // ── Chat: سجل محادثات متعدد (المحادثات القديمة لا تختفي) ──────────────
        conversations: [initial],
        activeId: initial.id,

        newConversation: () =>
          set((s) => {
            const c = makeConversation()
            return { conversations: [c, ...s.conversations], activeId: c.id }
          }),

        switchConversation: (id) => set({ activeId: id }),

        deleteConversation: (id) =>
          set((s) => {
            const rest = s.conversations.filter((c) => c.id !== id)
            if (rest.length === 0) {
              const c = makeConversation()
              return { conversations: [c], activeId: c.id }
            }
            const activeId = s.activeId === id ? rest[0].id : s.activeId
            return { conversations: rest, activeId }
          }),

        // تحديث رسائل المحادثة النشطة (يقبل دالة أو قيمة) + تحديث العنوان
        updateActiveMessages: (updater) =>
          set((s) => ({
            conversations: s.conversations.map((c) => {
              if (c.id !== s.activeId) return c
              const messages =
                typeof updater === 'function' ? updater(c.messages) : updater
              return { ...c, messages, title: titleFrom(messages) }
            }),
          })),

        setActiveSessionId: (sid) =>
          set((s) => ({
            conversations: s.conversations.map((c) =>
              c.id === s.activeId ? { ...c, sessionId: sid } : c
            ),
          })),

        getActiveConversation: () => {
          const s = get()
          return s.conversations.find((c) => c.id === s.activeId) || s.conversations[0]
        },
      }
    },
    {
      name: 'ai-marketing-os',
      // نُبقي فقط ما يستحق الحفظ
      partialize: (s) => ({
        user: s.user,
        token: s.token,
        activeBrandId: s.activeBrandId,
        conversations: s.conversations,
        activeId: s.activeId,
      }),
    }
  )
)

export default useStore
