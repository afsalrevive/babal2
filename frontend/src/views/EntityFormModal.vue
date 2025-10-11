<template>
  <n-modal
    v-model:show="modalVisible"
    :teleported="false"
    :title="editMode ? `Edit ${toSentenceCase(entityType)}` : `Add ${toSentenceCase(entityType)}`"
    preset="card"
    class="full-width-modal"
  >
    <n-card class="modal-card">
      <n-space
        align="center"
        justify="space-between"
        style="margin-bottom: 12px"
        v-if="!editMode && ['customer', 'agent', 'partner', 'passenger','travel_location','particular','ticket_type', 'visa_type'].includes(entityType)"
      >
        <div style="display: flex; align-items: center; gap: 8px;">
          <n-switch v-model:value="bulkAddMode" />
          <span>Bulk Add Mode</span>
        </div>
      </n-space>
      <n-form :model="currentForm" :rules="formRules" ref="formRef">
        <div class="responsive-form-grid">
          <template
            v-for="(defaultVal, key) in defaultFieldsByEntity[entityType]"
            :key="key"
          >
            <template v-if="!editMode && isCreditField(key) && !authStore.isAdmin"></template>
            
            <template v-else>
              <n-form-item
                :prop="key"
                :label="toSentenceCase(key)"
                :feedback="fieldErrors[key]"
                :validation-status="fieldErrors[key] ? 'error' : undefined"
              >
                <div :class="{'greyed-out': shouldBeGreyedOut(key)}">
                  <template v-if="typeof defaultVal === 'boolean'">
                    <n-switch v-model:value="currentForm[key]" :disabled="shouldDisableField(key)" />
                  </template>
                  <template v-else-if="key === 'date_of_birth' || key === 'passport_issue_date' || key === 'passport_expiry'">
                    <n-date-picker v-model:value="currentForm[key]" type="date" clearable :disabled="shouldDisableField(key)" />
                  </template>
                  <template v-else-if="key === 'salutation'">
                    <n-select v-model:value="currentForm[key]" :options="salutationOptions" placeholder="Select" :disabled="shouldDisableField(key)" filterable />
                  </template>
                  <template v-else-if="key === 'nationality' || key === 'country'">
                    <n-select v-model:value="currentForm[key]" :options="countryOptions" filterable placeholder="Select" :disabled="shouldDisableField(key)" />
                  </template>
                  <template v-else-if="typeof defaultVal === 'number'">
                    <n-input-number v-model:value="currentForm[key]" :disabled="shouldDisableField(key)" />
                  </template>
                  <template v-else>
                    <n-input v-model:value="currentForm[key]" :disabled="shouldDisableField(key)" />
                  </template>
                </div>
              </n-form-item>
            </template>
          </template>

          <template v-if="editMode && entityType === 'agent' && authStore.isAdmin">
            <n-form-item
              label="Enhance/Deduct Credit"
              prop="credit_limit_enhancement"
            >
              <n-input-number v-model:value="currentForm.credit_limit_enhancement" placeholder="Enter amount to adjust" />
            </n-form-item>

            <n-form-item v-if="newCreditLimit !== null" label="New Credit Limit">
              <n-input
                :value="newCreditLimit"
                disabled
                placeholder="Calculated automatically"
                style="color: #63e2b7;"
              />
            </n-form-item>
          </template>

        </div>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="closeModal">Cancel</n-button>
          <template v-if="editMode">
            <PermissionWrapper resource="entity" operation="modify">
              <n-button type="primary" @click="updateEntity()">Update</n-button>
            </PermissionWrapper>
          </template>
          <template v-else>
            <PermissionWrapper resource="entity" operation="write">
              <template v-if="!bulkAddMode">
                <n-button type="primary" @click="addEntity()">Add</n-button>
              </template>
              <template v-else>
                <n-button type="primary" @click="handleBulkAdd()">Save and Next</n-button>
              </template>
            </PermissionWrapper>
          </template>
        </n-space>
      </template>
    </n-card>
  </n-modal>
</template>

<script setup lang="ts">
import {
  ref,
  watch,
  computed,
  nextTick
} from 'vue'
import api from '@/api'
import {
  useMessage,
  NButton,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NSpace,
  NModal,
  NCard,
  NDatePicker,
  NSelect,
  NSwitch
} from 'naive-ui'
import type { FormInst, FormRules } from 'naive-ui'
import { countries } from 'countries-list'
import PermissionWrapper from '@/components/PermissionWrapper.vue'
import { useAuthStore } from '@/stores/auth'

const props = defineProps({
  show: {
    type: Boolean,
    required: true
  },
  entityType: {
    type: String,
    required: true
  },
  editMode: {
    type: Boolean,
    default: false
  },
  formData: {
    type: Object,
    default: () => ({})
  }
})

const emits = defineEmits(['update:show', 'entity-created', 'entity-updated'])
const message = useMessage()
const formRef = ref<FormInst|null>(null)
const fieldErrors = ref<Record<string, string>>({})
const currentForm = ref<Record<string, any>>({})
const bulkAddMode = ref(false)

const authStore = useAuthStore()

const modalVisible = computed({
  get: () => props.show,
  set: (val) => emits('update:show', val)
})

const prepareFormData = (data: any) => {
  const preparedData = { ...data };
  const dateFields = ['date_of_birth', 'passport_issue_date', 'passport_expiry'];

  dateFields.forEach(field => {
    if (preparedData[field] && typeof preparedData[field] === 'string') {
      const date = new Date(preparedData[field]);
      if (!isNaN(date.getTime())) {
        preparedData[field] = date.getTime();
      } else {
        preparedData[field] = null;
      }
    }
  });
  return preparedData;
};

watch(() => props.show, (newVal) => {
  if (newVal) {
    if (props.editMode) {
      currentForm.value = { ...prepareFormData(props.formData), credit_limit_enhancement: 0 };
    } else {
      currentForm.value = {
        ...defaultFieldsByEntity[props.entityType],
        ...prepareFormData(props.formData)
      };
    }
    fieldErrors.value = {};
    nextTick(() => {
      formRef.value?.restoreValidation?.();
    });
  }
}, { immediate: true });


// Watch for changes in credit_limit for agents in add mode to update credit_balance
watch(() => currentForm.value.credit_limit, (newVal) => {
  if (!props.editMode && props.entityType === 'agent' && authStore.isAdmin) {
    currentForm.value.credit_balance = newVal;
  }
});

const newCreditLimit = computed(() => {
  if (props.editMode && props.entityType === 'agent' && authStore.isAdmin && currentForm.value.credit_limit_enhancement !== undefined) {
    const currentLimit = props.formData.credit_limit || 0;
    const enhancement = currentForm.value.credit_limit_enhancement || 0;
    const newLimit = currentLimit + enhancement;
    return String(Math.max(0, newLimit));
  }
  return '';
});


const closeModal = () => {
  modalVisible.value = false
}

const countryOptions = computed(() => {
  return Object.values(countries).map(c => ({
    label: c.name,
    value: c.name
  }))
})

const salutationOptions = [
  { label: 'Mr', value: 'Mr' },
  { label: 'Mrs', value: 'Mrs' },
  { label: 'Miss', value: 'Miss' },
  { label: 'Dr', value: 'Dr' },
  { label: 'Prof', value: 'Prof' },
]

const formRules = computed<FormRules>(() => {
  const entity = props.entityType
  if (!entity) return {}

  const rules: FormRules = {}
  Object.entries(defaultFieldsByEntity[entity]).forEach(([key, defaultValue]) => {
    if (typeof defaultValue === 'boolean') return
    if (shouldDisableField(key)) return // Use the updated helper function

    if (key === 'name' || (entity === 'passenger' && key === 'first_name')) {
      rules[key] = [{ required: true, message: `${toSentenceCase(key)} is required`, trigger: ['input', 'blur'] }]
    }
    
    if (key === 'passport_number' && entity === 'passenger') {
      rules[key] = [{ required: false, pattern: /^[A-Z0-9<]{6,20}$/, message: 'Invalid passport number format', trigger: ['blur'] }]
    }
  })
  if (props.editMode && entity === 'agent' && authStore.isAdmin) {
      rules.credit_limit_enhancement = [
        {
          validator: (rule, value) => {
            const currentLimit = props.formData.credit_limit;
            if (value && (currentLimit + value < 0)) {
              return new Error("Total credit limit cannot be negative.");
            }
            return true;
          },
          trigger: ['input', 'blur']
        }
      ]
  }
  return rules
})

const customFieldLabels: Record<string, string> = {
  customer_id: 'Customer',
  is_active: 'Active',
  travel_location: 'Travel Location',
  ticket_type: 'Ticket Type',
  visa_type: 'Visa Type'
}

const defaultFieldsByEntity: Record<string, Record<string, any>> = {
  customer: { name: '', email: '', contact: '', credit_limit: 0, credit_used: 0, active: true },
  agent: { name: '', contact: '', email: '', credit_limit: 0, credit_balance: 0, active: true },
  partner: { name: '', contact: '', email: '', active: true, allow_negative_wallet: false },
  passenger: { salutation: '', first_name: '', middle_name: '', last_name: '', contact: '', passport_number: '', address: '', city: '', state: '', country: '', zip_code: '', fathers_name: '', mothers_name: '', date_of_birth: null, passport_issue_date: null, passport_expiry: null, nationality: '', active: true },
  travel_location: { name: '', active: true },
  ticket_type: { name: '', active: true},
  visa_type: { name: '', active: true },
  particular: { name: '', active: true }
}

const isCreditField = (key: string) => {
  return ['wallet_balance', 'credit_limit', 'credit_used', 'credit_balance', 'allow_negative_wallet'].includes(key);
}

const shouldBeGreyedOut = (key: string) => {
  // Always grey out wallet balance, it's handled by transactions
  if (key === 'wallet_balance') {
    return true;
  }

  // Grey out credit-related fields for non-admins, but show them
  if (isCreditField(key) && !authStore.isAdmin) {
    return true;
  }
  
  // Grey out customer credit_used and agent credit_balance in add/edit mode
  if (props.entityType === 'customer' && key === 'credit_used') return true;
  if (props.entityType === 'agent' && key === 'credit_balance') return true;

  // Do not grey out credit_limit for agents in add mode (it's the only credit field they can enter)
  if (props.entityType === 'agent' && key === 'credit_limit' && !props.editMode && authStore.isAdmin) return false;

  return false;
}

const shouldDisableField = (key: string) => {
  if (props.editMode) {
    // Disable credit limit field for agents in edit mode
    if (props.entityType === 'agent' && key === 'credit_limit') return true;
  }
  return shouldBeGreyedOut(key);
}

const toSentenceCase = (s: string) => {
  return customFieldLabels[s] || s.replace(/_/g, ' ').replace(/\w\S*/g, (txt) =>
    txt.charAt(0).toUpperCase() + txt.slice(1).toLowerCase()
  )
}

const processPayload = () => {
  const payload: Record<string, any> = {};
  for (const key in currentForm.value) {
    const value = currentForm.value[key];
    if (value !== null && value !== undefined && !shouldDisableField(key)) {
      payload[key] = value;
    }
  }

  const dateFields = ['date_of_birth', 'passport_issue_date', 'passport_expiry'];
  dateFields.forEach(field => {
    if (payload[field]) {
      payload[field] = new Date(payload[field]).toISOString().split('T')[0];
    }
  });

  // Handle agent credit enhancement only for admins in edit mode
  if (props.editMode && props.entityType === 'agent' && authStore.isAdmin && currentForm.value.credit_limit_enhancement !== undefined) {
    payload.credit_limit = (props.formData.credit_limit || 0) + currentForm.value.credit_limit_enhancement;
  }
  
  delete payload.credit_limit_enhancement;
  delete payload.wallet_balance; // Ensure wallet_balance is never sent in the payload

  return payload;
};

const addEntity = async () => {
  try {
    await formRef.value?.validate()
    const payload = processPayload()
    const response = await api.post(`/api/manage/${props.entityType}`, payload)
    message.success(`${toSentenceCase(props.entityType)} added`)
    emits('entity-created', { type: props.entityType, data: response.data })
    if (!bulkAddMode.value) {
      closeModal()
    } else {
      currentForm.value = { ...defaultFieldsByEntity[props.entityType] }
      nextTick(() => formRef.value?.restoreValidation?.())
    }
  } catch (e: any) {
    handleApiError(e)
  }
}

const updateEntity = async () => {
  try {
    await formRef.value?.validate()
    const payload = processPayload()
    await api.patch(`/api/manage/${props.entityType}`, payload)
    message.success(`${toSentenceCase(props.entityType)} updated`)
    emits('entity-updated', { type: props.entityType, data: payload })
    closeModal()
  } catch (e: any) {
    handleApiError(e)
  }
}

const handleBulkAdd = async () => {
  await addEntity()
}

const handleApiError = (e: any) => {
  console.error('API Error:', e);
  fieldErrors.value = {};

  if (e?.response?.data?.field_errors) {
    fieldErrors.value = e.response.data.field_errors;
    message.error('Please fix the form errors.');
    return;
  }
  
  if (e?.response?.data?.message) {
    message.error(e.response.data.message);
    return;
  }

  const errorMsg = e?.response?.data?.error || e?.message || 'Unexpected error occurred. Please try again.';
  message.error(errorMsg);
}
</script>

<style scoped lang="scss">
@use '@/styles/theme' as *;
.greyed-out {
  pointer-events: none;
  opacity: 0.6;
  filter: grayscale(1);
}
</style>