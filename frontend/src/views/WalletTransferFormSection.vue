<template>
    <n-form-item label="From Entity Type" prop="from_entity_type" required>
      <n-select 
        v-model:value="form.from_entity_type" 
        :options="entityTypeOptions"
        :disabled="isEditing"
        @update:value="$emit('refund-entity-change', $event, 'from')"
      />
    </n-form-item>

    <n-form-item 
      v-if="form.from_entity_type && form.from_entity_type !== 'others'"
      label="From Entity Name"
      prop="from_entity_id"
    >
      <n-space vertical>
        <n-select
          v-model:value="form.from_entity_id"
          :options="fromEntityOptions"
          :loading="fromEntitiesLoading"
          :disabled="isEditing"
          filterable
          placeholder="Select entity"
        />
        <n-grid v-if="selectedFromEntity" :cols="1" style="margin-top: 8px;">
          <n-gi>
            <n-text type="info">Balance: ₹{{ selectedFromEntity.wallet_balance.toFixed(2) ?? 'N/A' }}</n-text>
          </n-gi>
        </n-grid>
      </n-space>
    </n-form-item>

    <n-form-item label="To Entity Type" prop="to_entity_type" required>
      <n-select 
        v-model:value="form.to_entity_type" 
        :options="entityTypeOptions"
        :disabled="isEditing"
        @update:value="$emit('refund-entity-change', $event, 'to')"
      />
    </n-form-item>

    <n-form-item 
      v-if="form.to_entity_type && form.to_entity_type !== 'others'"
      label="To Entity Name"
      prop="to_entity_id"
    >
      <n-space vertical>
        <n-select
          v-model:value="form.to_entity_id"
          :options="toEntityOptions"
          :loading="toEntitiesLoading"
          :disabled="isEditing"
          filterable
          placeholder="Select entity"
        />
        <n-grid v-if="selectedToEntity" :cols="1" style="margin-top: 8px;">
          <n-gi>
            <n-text type="info">Balance: ₹{{ selectedToEntity.wallet_balance.toFixed(2) ?? 'N/A' }}</n-text>
          </n-gi>
        </n-grid>
      </n-space>
    </n-form-item>

    <n-form-item label="Particular" prop="particular_id">
      <n-select 
        v-model:value="form.particular_id" 
        :options="particularOptions" 
        :loading="particularsLoading" 
        filterable 
        clearable 
        @search="$emit('particular-search', $event)"
        @clear="$emit('particular-clear')"
        @update:value="$emit('particular-value-update', $event)"
      />
      <n-space v-if="shouldShowCreateParticular" align="center" style="margin-top: 8px;">
        <n-button 
          type="primary" 
          :disabled="!newParticularName" 
          @click="$emit('create-particular')"
          @mousedown.prevent
        >
          Create
        </n-button>
      </n-space>
    </n-form-item>
</template>

<script setup lang="ts">
import type { PropType } from 'vue'
import {
    NFormItem, NSelect, NSpace, NGrid, NGi, NText, NButton
} from 'naive-ui'

defineProps({
  form: {
    type: Object as PropType<any>,
    required: true
  },
  entityTypeOptions: {
    type: Array as PropType<any[]>,
    required: true
  },
  fromEntityOptions: {
    type: Array as PropType<any[]>,
    required: true
  },
  toEntityOptions: {
    type: Array as PropType<any[]>,
    required: true
  },
  fromEntitiesLoading: {
    type: Boolean,
    required: true
  },
  toEntitiesLoading: {
    type: Boolean,
    required: true
  },
  selectedFromEntity: {
    type: Object as PropType<any>,
    default: null
  },
  selectedToEntity: {
    type: Object as PropType<any>,
    default: null
  },
    particularOptions: {
    type: Array as PropType<any[]>,
    required: true
  },
  particularsLoading: {
    type: Boolean,
    required: true
  },
  isEditing: {
    type: Boolean,
    required: true
  },
  // NEW PROPS FOR ON-THE-FLY PARTICULAR CREATION
  newParticularName: {
    type: String,
    required: true
  },
  shouldShowCreateParticular: {
    type: Boolean,
    required: true
  }
})

defineEmits(['refund-entity-change', 'particular-search', 'particular-clear', 'particular-value-update', 'create-particular'])
</script>

<style scoped lang="scss">
@use '@/styles/theme' as *;
</style>