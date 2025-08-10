// src/router/index.ts
import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { hasPermission } from '@/utils/permissions';
import { iconMap } from '@/utils/iconMap'
import Login from '@/views/Login.vue';
import Signup from '@/views/Signup.vue';
import Dashboard from '@/views/Dashboard.vue';
import UserManagement from '@/views/UserManagement.vue';
import Settings from '@/views/Settings.vue';
import NotFound from '@/views/NotFound.vue';
import EntityManager from '@/views/EntityManager.vue';
import TransactionPage from '@/views/TransactionPage.vue';
import TicketManager from '@/views/TicketManager.vue'
import ServiceManager from '@/views/ServiceManager.vue';
import VisaManager from '@/views/VisaManager.vue';
import FinancialReports from '@/views/FinancialReports.vue';
import InvoiceGenerator from '@/views/InvoiceGenerator.vue';

declare module 'vue-router' {
  interface RouteMeta {
    resource?: string
    operation?: 'read' | 'write' | 'modify' | 'full' 
    public?: boolean
    title?: string
    icon?: keyof typeof iconMap
    navOrder?: number
  }
}

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard,
    meta: {
      resource: 'Dashboard',
      operation: 'read',
      icon: 'dashboard',
      showInNav: true,
      navOrder: 1
    }
  },
  {
    path: '/dashboard',
    redirect: '/',
    meta: {
      resource: 'Dashboard',
      operation: 'read',
      showInNav: false 
    }
  },
  {
    path: '/users',
    name: 'UserManagement',
    component: UserManagement,
    meta: {
      resource: 'UserManagement',
      operation: 'read',
      title: 'User Management',
      icon: 'user',
      navOrder: 2
    }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: Settings,
    meta: {
      resource: 'Settings',
      operation: 'read',
      title: 'Settings',
      icon: 'settings',
      navOrder: 3
    }
  },
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: {
      public: true
    }
  },
  {
    path: '/signup',
    name: 'Signup',
    component: Signup,
    meta: {
      public: true
    }
  },
  {
    path: '/entity-manager/:entity?',
    name: 'EntityManager',
    component: EntityManager,
    props: (route) => ({ entity: route.params.entity || 'customer' }),
    meta: {
      resource: 'entity', 
      operation: 'read',
      title: 'Manage Entities',
      icon: 'entity',
      navOrder: 4 
    }
  },
    {
    path: '/transactions',
    name: 'TransactionPage',
    component: TransactionPage,
    meta: {
      resource: 'transaction',
      operation: 'read',
      title: 'Transactions',
      icon: 'transaction', // Make sure 'transaction' is defined in iconMap
      navOrder: 5
    }
  },
  {
    path: '/ticket-manager',
    name: 'TicketManager',
    component: TicketManager,
    meta: {
      resource: 'ticket',
      operation: 'read',
      title: 'Ticket Management',
      icon: 'ticket',
      navOrder: 6
    }
  },
  {
    path: '/visa-manager',
    name: 'VisaManager',
    component: VisaManager,
    meta: {
      resource: 'visa',
      operation: 'read',
      title: 'Visa Management',
      icon: 'visa',
      navOrder: 7
    }
  },
  {
    path: '/services',
    name: 'services',
    component: ServiceManager,
    meta: {
      resource: 'services',
      operation: 'read',
      title: 'Other Services',
      icon: 'services',
      navOrder: 8
    }
  },
{
  path: '/financial-reports',
  name: 'financial-reports',
  component: FinancialReports,
  meta: {
    resource: 'financialreports',
    operation: 'read',
    title: 'Financial Reports',
    icon: 'financialreports', 
    navOrder: 9
  }
},
{
  path: '/invoice-generator',
  name: 'invoice-generator',
  component: InvoiceGenerator,
  meta: {
    resource: 'invoice',
    operation: 'read',
    title: 'Invoice Generator',
    icon: 'invoice', 
    navOrder: 9
  }
},

  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: NotFound,
    meta: {
      public: true
    }
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

// Route guard
router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore();
  
  try {
    // Initialize auth if needed
    if (!auth.initialized && auth.token) {
      await auth.init();
    }

    // Public routes
    if (to.meta.public) return next();

    // Auth pages handling
    if (['Login', 'Signup'].includes(to.name as string)) {
      return auth.isLoggedIn ? next('/') : next();
    }

    // Require authentication
    if (!auth.isLoggedIn) return next({ name: 'Login' });

    // Session validation
    const decoded = auth.decodeToken();
    const valid = await auth.validateSession(decoded);
    if (!valid) {
      auth.logout();
      return next({ name: 'Login' });
    }

    // Permission check
    if (to.meta.resource && to.meta.operation) {
      const allowed = auth.isAdmin || hasPermission(
        auth.user?.perms || [],
        to.meta.resource.toLowerCase(),
        to.meta.operation as 'read' | 'write' | 'modify' | 'full' // Cast to new type
      );
      if (!allowed) return next({ name: 'NotFound' });
    }
    next();
  } catch (error) {
    console.error('Router guard error:', error);
    next({ name: 'NotFound' });
  }
});

export default router;
