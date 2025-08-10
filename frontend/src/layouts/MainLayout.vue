<template>
  <div class="full-viewport-container">
    <n-layout has-sider>
      <n-layout-sider
        v-if="auth.isLoggedIn"
        :collapsed="collapsed"
        collapse-mode="width"
        :width="220"
        :collapsed-width="64"
        bordered
        show-trigger="bar"
        :native-scrollbar="false"
        @update:collapsed="collapsed = $event"
        :style="{ backgroundColor: isDark ? 'var(--card-bg)' : 'var(--header-bg)' }"
      >
        <Navbar :collapsed="collapsed" @toggle="toggleCollapse" />
      </n-layout-sider>

      <n-layout>
        <n-layout-header v-if="auth.isLoggedIn" bordered class="header">
          <div class="header-content">
            <div class="left">
              <n-button
                v-if="showHamburger"
                quaternary
                size="large"
                circle
                @click="toggleCollapse"
              >
                <n-icon :component="MenuOutline" />
              </n-button>
              
              <n-button
                quaternary
                circle
                size="large"
                @click="$emit('toggle-theme')"
                class="theme-toggle-btn"
              >
                <n-icon v-if="isDark" :component="SunnyOutline" />
                <n-icon v-else :component="MoonOutline" />
              </n-button>
            </div>
            <div class="right">
              <n-dropdown trigger="click" :options="profileOptions" @select="handleProfileAction">
                <div class="profile-info clickable">
                  <n-avatar :size="40" :text="initials" round />
                  <div class="username">{{ userName }} ▼</div>
                </div>
              </n-dropdown>
            </div>
          </div>
        </n-layout-header>

        <n-layout-content class="content-with-scroll">
          <router-view />
        </n-layout-content>
      </n-layout>
    </n-layout>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  NLayout,
  NLayoutSider,
  NLayoutContent,
  NLayoutHeader,
  NButton,
  NIcon,
  NAvatar,
  NDropdown
} from 'naive-ui'
import { MenuOutline, SunnyOutline, MoonOutline } from '@vicons/ionicons5'
import Navbar from '@/components/Navbar.vue'

const auth = useAuthStore()
const router = useRouter()
const collapsed = ref(false)
const showHamburger = ref(false)

defineProps({
  isDark: Boolean
})
defineEmits(['toggle-theme'])

const initials = computed(() => {
  return auth.user?.full_name?.split(' ').map(s => s[0]).join('') || ''
})

const userName = computed(() =>
  auth.user?.full_name ? auth.user.full_name.charAt(0).toUpperCase() + auth.user.full_name.slice(1) : ''
)

const profileOptions = [
  { label: 'Profile', key: 'profile' },
  { label: 'Logout', key: 'logout' }
]

const handleProfileAction = (key: string) => {
  if (key === 'logout') {
    auth.logout()
    router.push('/login')
  } else if (key === 'profile') {
    router.push('/profile')
  }
}

const handleResize = () => {
  const isMobile = window.innerWidth < 768
  showHamburger.value = isMobile
  if (isMobile) collapsed.value = true
  else collapsed.value = false
}

onMounted(() => {
  handleResize()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
})

const toggleCollapse = () => {
  collapsed.value = !collapsed.value
}
</script>

<style scoped>
.full-viewport-container {
  height: 100vh;
  display: flex;
}

.header {
  height: 64px;
  padding: 0 24px;
  background-color: var(--header-bg);
  transition: background-color 0.3s;
}

.content-with-scroll {
  padding: 24px;
  background: var(--body-bg);
  overflow-y: auto;
  flex-grow: 1;
  transition: background-color 0.3s;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
}

.profile-info {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.username {
  margin-left: 12px;
  color: var(--text-color);
}

.theme-toggle-btn {
  margin-left: 12px;
}

.left {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>