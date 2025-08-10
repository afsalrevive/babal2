// src/api.ts
import axios from 'axios'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'
import { useMessage } from 'naive-ui'

const api = axios.create({
  baseURL: '',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true
})

// Store a reference to the message provider. This will be set in main.ts.
let messageProvider: ReturnType<typeof useMessage> | null = null;
export const setMessageProvider = (provider: ReturnType<typeof useMessage>) => {
  messageProvider = provider;
};

// ==================== REQUEST INTERCEPTOR ====================
api.interceptors.request.use(config => {
  const auth = useAuthStore()
  const currentRoute = router.currentRoute.value

  // Attach JWT token
  const token = localStorage.getItem('token')
  if (token) {
    config.headers!.Authorization = `Bearer ${token}`
  }

  // Skip header injection for public routes
  if (currentRoute.meta.public) {
    return config
  }

  const resourceRoute = currentRoute.matched.find(r => 
    r.meta?.resource && r.meta.showInNav !== false
  )

  if (resourceRoute?.meta.resource) {
    const resource = resourceRoute.meta.resource as string
    config.headers!['X-Resource'] = resource

    // Infer operation based on HTTP method
    const method = config.method?.toLowerCase()
    
    // Updated logic to infer new permission operations
    let operation: 'read' | 'write' | 'modify' | 'full' | undefined;
    if (method === 'delete') {
      operation = 'full';
    } else if (method === 'put' || method === 'patch') {
      operation = 'modify';
    } else if (method === 'post') {
      operation = 'write';
    } else if (method === 'get') {
      operation = 'read';
    } else {
      operation = 'read';
    }
    
    if (operation) {
      config.headers!['X-Operation'] = operation;
    }
  } else {
    console.debug('No nav-visible resource for:', currentRoute.path)
  }

  return config
})


// ==================== RESPONSE INTERCEPTOR ====================
let isRefreshing = false
api.interceptors.response.use(
  response => response,
  async error => {
    const auth = useAuthStore()
    
    // 1. Handle 401 Unauthorized
    if (error.response?.status === 401 && !isRefreshing) {
      isRefreshing = true
      auth.logout()
      localStorage.removeItem('token')
      if (!router.currentRoute.value.meta.public) {
        router.push({
          name: 'Login',
          query: {
            redirect: router.currentRoute.value.fullPath
          }
        })
      }
      setTimeout(() => isRefreshing = false, 2000)
    }

    // 2. Handle 403 Forbidden
    if (error.response?.status === 403) {
      const resource = error.config.headers['X-Resource']
      const operation = error.config.headers['X-Operation']

      if (resource && operation) {
        // Corrected logic: The front-end should only throw an error if the user
        // truly lacks permission. The previous check was flawed.
        if (!auth.hasPermission(resource, operation)) {
          console.error(`Missing ${resource}.${operation} permission`)
          if (messageProvider) {
            messageProvider.error(`You need ${operation} access for ${resource}`)
          }
        } else {
          // This case indicates a real backend issue, not a permission problem.
          console.error(`Unexpected 403: Backend denied access despite user having permission for ${resource}.${operation}`)
          if (messageProvider) {
            messageProvider.error(`Access to ${resource} denied unexpectedly.`)
          }
        }
      }
      return Promise.reject(error)
    }

    return Promise.reject(error)
  }
)

// 1️⃣ The shape we expect from GET /api/users/:id/permissions
export type PermissionOperation = 'read' | 'write' | 'modify' | 'full' | 'none'

export interface PermissionsResponse {
  overrides: Record<number, PermissionOperation>
  role_permissions: Record<number, PermissionOperation>
}

// 2️⃣ A typed helper for that endpoint
export function fetchUserPermissions(
  userId: number
): Promise<PermissionsResponse> {
  return api.get<PermissionsResponse>(`/api/users/${userId}/permissions`)
            .then(res => res.data)
}

export default api
