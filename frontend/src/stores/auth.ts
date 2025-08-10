// src/stores/auth.ts
import { defineStore } from 'pinia'
import router from '@/router'
import api, { type PermissionOperation } from '@/api'
import { nextTick } from 'vue'
import { hasPermission } from '@/utils/permissions'
import { jwtDecode } from 'jwt-decode' 
interface JwtPayload {
  perms: PermissionOperation[]
  is_admin: boolean
  session_version: number
  sub: string 
}

interface User {
  id: number
  name: string
  full_name: string
  email: string
  perms: PermissionOperation[]
  is_admin: boolean
  session_version: number
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') as string | null,
    user: null as User | null,
    storedVersion: Number(localStorage.getItem('session_version')) || 0,
    initialized: false
  }),

  getters: {
    isLoggedIn: (state): boolean => !!state.token && !!state.user,
    isAdmin: (state): boolean => state.user?.is_admin || false,
    hasPermission: (state): ((resource: string, operation: 'read' | 'write' | 'modify' | 'full') => boolean) => {
      return (resource, operation) => {
        if (state.user?.is_admin) return true
        return hasPermission(state.user?.perms || [], resource, operation)
      }
    }
  },

  actions: {
    async init() {
      const token = localStorage.getItem('token')
      if (!token) {
        this.initialized = true
        return
      }

      try {
        this.token = token
        api.defaults.headers.common.Authorization = `Bearer ${token}`
        
        const decoded = this.decodeToken()
        await this.validateSession(decoded)

        // Get minimal user data from API
        const res = await api.get('/api/me')
        this.handleUserResponse(res.data.user, decoded)

      } catch (error) {
        console.error('Auth init failed:', error)
        this.logout()
      } finally {
        this.initialized = true
      }
    },

    async login(credentials: { name: string; password: string }) {
      const res = await api.post('/api/login', credentials)
      this.loginSuccess(res.data)
      await nextTick()
      router.push({ name: 'Dashboard' })
    },

    loginSuccess(data: { token: string; user: User }) {
      this.token = data.token
      const decoded = this.decodeToken()
      console.log('Final permissions:', [...new Set(decoded.perms)]) 
      this.handleUserResponse(data.user, decoded)
      this.persistSession(decoded)
    },

    async validateSession(decoded: JwtPayload): Promise<boolean> {
      const storedVersion = Number(localStorage.getItem('session_version')) || 0
      const jwtVersion = Number(decoded?.session_version) || 0;
      
      if (jwtVersion > storedVersion) {
        // Update local storage without logout
        localStorage.setItem('session_version', jwtVersion.toString())
        this.storedVersion = jwtVersion
      }
      return true
    },

    logout() {
      this.token = null
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('session_version')
      delete api.defaults.headers.common.Authorization
      router.push({ name: 'Login' })
    },

    // Changed from private method
    handleUserResponse(apiUser: User, decoded: JwtPayload) {
      this.user = {
        ...apiUser,
        perms: decoded.perms,
        is_admin: decoded.is_admin,
        session_version: decoded.session_version
      }
    },

    decodeToken(): JwtPayload {
      if (!this.token) throw new Error('No token available')
      return jwtDecode<JwtPayload>(this.token)
    },

    persistSession(decoded: JwtPayload) {
      localStorage.setItem('token', this.token!)
      localStorage.setItem('session_version', decoded.session_version.toString())
      api.defaults.headers.common.Authorization = `Bearer ${this.token}`
    }
  }
})
