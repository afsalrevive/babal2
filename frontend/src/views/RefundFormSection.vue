<template>
    <n-form-item label="Refund Direction" prop="refund_direction" required>
      <n-select
        v-model:value="form.refund_direction"
        :options="refundDirectionOptions"
        :disabled="isEditing"
      />
    </n-form-item>

    <template v-if="form.refund_direction === 'outgoing'">
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
          <n-grid v-if="selectedToEntity" :cols="2" x-gap="12" style="margin-top: 8px;">
            <n-gi>
              <n-text type="info">Wallet: ₹{{ selectedToEntity.wallet_balance?.toFixed(2) ?? 'N/A' }}</n-text>
            </n-gi>
            <n-gi>
              <n-text type="warning">
                <template v-if="form.to_entity_type === 'agent'">
                  Credit: ₹{{ selectedToEntity.credit_balance?.toFixed(2) ?? 'N/A' }}/₹{{ selectedToEntity.credit_limit?.toFixed(2) ?? 'N/A' }}
                </template>
                <template v-else-if="form.to_entity_type === 'customer'">
                  Credit: ₹{{ selectedToEntity.credit_used?.toFixed(2) ?? 'N/A' }}/₹{{ selectedToEntity.credit_limit?.toFixed(2) ?? 'N/A' }}
                </template>
                <template v-else>
                  Credit: N/A
                </template>
              </n-text>
            </n-gi>
          </n-grid>
        </n-space>
      </n-form-item>

      <n-form-item label="From Mode (Company)" prop="mode_for_from" required>
        <n-select
          v-model:value="form.mode_for_from"
          :options="companyRefundFromModeOptions"
          :disabled="isEditing"
          placeholder="Company pays via"
        />
      </n-form-item>

      <template v-if="form.mode_for_from && modeBalance !== null">
        <n-form-item label="Company Account">
          <n-p>Mode: {{ form.mode_for_from }} — Balance: ₹{{ modeBalance.toFixed(2) }}</n-p>
        </n-form-item>
      </template>

      <template v-if="form.to_entity_type">
        <template v-if="['customer', 'partner'].includes(form.to_entity_type)">
          <n-form-item
            v-if="['cash', 'online'].includes(form.mode_for_from)"
            label="Deduct from Entity Account?"
          >
            <n-switch v-model:value="form.deduct_from_account" :disabled="isEditing" />
          </n-form-item>

          <n-form-item
            v-if="form.mode_for_from === 'service_availed'"
            label="Credit to Entity Account?"
          >
            <n-switch v-model:value="form.credit_to_account" :disabled="isEditing" />
          </n-form-item>
        </template>

        <n-form-item
          v-if="form.to_entity_type === 'agent'"
          label="Credit Agent Account?"
        >
          <n-switch v-model:value="form.credit_to_account" :disabled="isEditing" />
        </n-form-item>

        <n-form-item v-if="form.to_entity_type === 'others'" label="Note">
          <n-alert type="info" :show-icon="false">
            Amount will be deducted directly from the selected company account.
          </n-alert>
        </n-form-item>
      </template>
    </template>

    <template v-else>
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
          <n-grid v-if="selectedFromEntity" :cols="2" x-gap="12" style="margin-top: 8px;">
            <n-gi>
              <n-text type="info">Wallet: ₹{{ selectedFromEntity.wallet_balance?.toFixed(2) ?? 'N/A' }}</n-text>
            </n-gi>
            <n-gi>
              <n-text type="warning">
                <template v-if="form.from_entity_type === 'agent'">
                  Credit: ₹{{ selectedFromEntity.credit_balance?.toFixed(2) ?? 'N/A' }}
                </template>
                <template v-else-if="form.from_entity_type === 'customer'">
                  Credit: ₹{{ selectedFromEntity.credit_used?.toFixed(2) ?? 'N/A' }}/₹{{ selectedFromEntity.credit_limit?.toFixed(2) ?? 'N/A' }}
                </template>
                <template v-else>
                  Credit: N/A
                </template>
              </n-text>
            </n-gi>
          </n-grid>
        </n-space>
      </n-form-item>

      <n-form-item
        v-if="form.from_entity_type && form.from_entity_type !== 'others'"
        label="From Mode (Entity)"
        prop="mode_for_from"
      >
        <n-select
          v-model:value="form.mode_for_from"
          :key="`mode-select-${form.from_entity_type}-${entityOptionsReady}`"
          :options="getEntityToCompanyFromModeOptions(form.from_entity_type)"
          :disabled="isEditing"
          :loading="!entityOptionsReady"
          placeholder="Entity pays via"
        />
      </n-form-item>

      <n-form-item
        v-if="form.from_entity_type === 'others' || form.mode_for_from === 'cash'"
        label="To Mode (Company)"
        prop="mode_for_to"
      >
        <n-select
          v-model:value="form.mode_for_to"
          :options="companyModeOptions"
          :disabled="isEditing"
          placeholder="Company receives via"
        />
      </n-form-item>
    </template>

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
    NFormItem, NSelect, NSpace, NGrid, NGi, NText, NSwitch, NP, NAlert, NButton
} from 'naive-ui'

const props = defineProps({
  form: {
    type: Object as PropType<any>,
    required: true
  },
  entityTypeOptions: {
    type: Array as PropType<any[]>,
    required: true
  },
  refundDirectionOptions: {
    type: Array as PropType<any[]>,
    required: true
  },
  companyModeOptions: {
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
  companyRefundFromModeOptions: {
    type: Array as PropType<any[]>,
    required: true
  },
  modeBalance: {
    type: Number,
    default: null
  },
  entityOptionsReady: {
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

const getEntityToCompanyFromModeOptions = (entityType: string) => {
  if (!entityType) return []
  if (['customer', 'partner', 'agent'].includes(entityType)) {
    return [{ label: 'Cash', value: 'cash' }, { label: 'Wallet', value: 'wallet' }]
  }
  return [{ label: 'Cash', value: 'cash' }, { label: 'Online', value: 'online' }]
}

defineEmits(['refund-entity-change', 'particular-search', 'particular-clear', 'particular-value-update', 'create-particular'])
</script>

<style scoped lang="scss">
@use '@/styles/theme' as *;
</style>