<template>
  <!-- Maintain existing template structure -->
  <div v-if="hasAccess">
    <slot />
  </div>
  <div v-else-if="showFallback">
    <slot name="fallback">
      <div class="permission-fallback">
        <n-icon :component="LockClosedOutline" />
        <n-text depth="3">
          {{ computedFallbackText }}
        </n-text>
      </div>
    </slot>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { LockClosedOutline } from '@vicons/ionicons5'
import type { PropType } from 'vue'
import { hasPermission } from '@/utils/permissions' // Import the central permission checker

const props = defineProps({
  resource: {
    type: String,
    required: true
  },
  operation: {
    type: String as PropType<'read' | 'write' | 'modify' | 'full'>,
    validator: (v: string) => ['read', 'write', 'modify', 'full'].includes(v),
    required: true
  },
  showFallback: {
    type: Boolean,
    default: true
  },
  fallbackText: {
    type: String,
    default: ''
  },
  inheritFromParent: {
    type: Boolean,
    default: false
  }
})

const auth = useAuthStore()
const normalizedResource = computed(() => props.resource.toLowerCase())

const hasAccess = computed(() => {
  if (auth.isAdmin) return true
  
  const operation = props.operation;
  const resource = normalizedResource.value;
  
  return hasPermission(auth.user?.perms || [], resource, operation)
})

const computedFallbackText = computed(() => {
  if (props.fallbackText) return props.fallbackText
  return ''
})

</script>

<style scoped>
.permission-fallback {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 4px;
  background: var(--warning-soft);
}
</style>
