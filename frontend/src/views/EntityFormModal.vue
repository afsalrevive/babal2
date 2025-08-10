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
        v-if="!editMode && ['customer', 'agent', 'partner', 'passenger','travel_location','particular', 'visa_type'].includes(entityType)"
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
            <template v-if="!editMode && ['wallet_balance', 'credit_limit', 'credit_used', 'credit_balance', 'allow_negative_wallet'].includes(key)">
              <PermissionWrapper resource="entity" operation="full">
                <n-form-item
                  :prop="key"
                  :label="toSentenceCase(key)"
                  :feedback="fieldErrors[key]"
                  :validation-status="fieldErrors[key] ? 'error' : undefined"
                >
                  <template v-if="typeof defaultVal === 'boolean'">
                    <n-switch v-model:value="currentForm[key]" />
                  </template>
                  <template v-else-if="key === 'date_of_birth' || key === 'passport_issue_date' || key === 'passport_expiry'">
                    <n-date-picker v-model:value="currentForm[key]" type="date" clearable :disabled="shouldDisableFieldInEdit(key)" />
                  </template>
                  <template v-else-if="key === 'salutation'">
                    <n-select v-model:value="currentForm[key]" :options="salutationOptions" placeholder="Select" :disabled="shouldDisableFieldInEdit(key)" filterable />
                  </template>
                  <template v-else-if="key === 'nationality' || key === 'country'">
                    <n-select v-model:value="currentForm[key]" :options="countryOptions" filterable placeholder="Select" :disabled="shouldDisableFieldInEdit(key)" />
                  </template>
                  <template v-else-if="typeof defaultVal === 'number'">
                    <n-input-number v-model:value="currentForm[key]" :disabled="shouldDisableFieldInEdit(key)" />
                  </template>
                  <template v-else>
                    <n-input v-model:value="currentForm[key]" :disabled="shouldDisableFieldInEdit(key)" />
                  </template>
                </n-form-item>
              </PermissionWrapper>
            </template>
            <template v-else>
              <n-form-item
                :prop="key"
                :label="toSentenceCase(key)"
                :feedback="fieldErrors[key]"
                :validation-status="fieldErrors[key] ? 'error' : undefined"
              >
                <template v-if="typeof defaultVal === 'boolean'">
                  <n-switch v-model:value="currentForm[key]" />
                </template>
                <template v-else-if="key === 'date_of_birth' || key === 'passport_issue_date' || key === 'passport_expiry'">
                  <n-date-picker v-model:value="currentForm[key]" type="date" clearable :disabled="shouldDisableFieldInEdit(key)" />
                </template>
                <template v-else-if="key === 'salutation'">
                  <n-select v-model:value="currentForm[key]" :options="salutationOptions" placeholder="Select" :disabled="shouldDisableFieldInEdit(key)" filterable />
                </template>
                <template v-else-if="key === 'nationality' || key === 'country'">
                  <n-select v-model:value="currentForm[key]" :options="countryOptions" filterable placeholder="Select" :disabled="shouldDisableFieldInEdit(key)" />
                </template>
                <template v-else-if="typeof defaultVal === 'number'">
                  <n-input-number v-model:value="currentForm[key]" :disabled="shouldDisableFieldInEdit(key)" />
                </template>
                <template v-else>
                  <n-input v-model:value="currentForm[key]" :disabled="shouldDisableFieldInEdit(key)" />
                </template>
              </n-form-item>
            </template>
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
      currentForm.value = prepareFormData(props.formData);
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
    if (props.editMode && shouldDisableFieldInEdit(key)) return

    if (key === 'name') {
      rules[key] = [{ required: true, message: `${toSentenceCase(key)} is required`, trigger: ['input', 'blur'] }]
    }
    
    if (key === 'passport_number' && entity === 'passenger') {
      rules[key] = [{ required: false, pattern: /^[A-Z0-9<]{6,20}$/, message: 'Invalid passport number format', trigger: ['blur'] }]
    }
  })
  return rules
})

const customFieldLabels: Record<string, string> = {
  customer_id: 'Customer',
  is_active: 'Active',
  travel_location: 'Travel Location',
  visa_type: 'Visa Type'
}

const defaultFieldsByEntity: Record<string, Record<string, any>> = {
  customer: { name: '', email: '', contact: '', wallet_balance: 0, credit_limit: 0, credit_used: 0, active: true },
  agent: { name: '', contact: '', email: '', wallet_balance: 0, credit_limit: 0, credit_balance: 0, active: true },
  partner: { name: '', contact: '', email: '', wallet_balance: 0, active: true, allow_negative_wallet: false },
  passenger: { name: '', contact: '', passport_number: '', salutation: '', address: '', city: '', state: '', country: '', zip_code: '', fathers_name: '', mothers_name: '', date_of_birth: null, passport_issue_date: null, passport_expiry: null, nationality: '', active: true },
  travel_location: { name: '', active: true },
  visa_type: { name: '', active: true },
  particular: { name: '', active: true }
}

const shouldDisableFieldInEdit = (key: string) => {
  if (!props.editMode) return false
  const entity = props.entityType
  if (entity === 'customer' && ['wallet_balance', 'credit_used'].includes(key)) return true
  if (entity === 'agent' && ['wallet_balance', 'credit_balance'].includes(key)) return true
  return false
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
    if (value !== null && value !== undefined) {
      payload[key] = value;
    }
  }

  const dateFields = ['date_of_birth', 'passport_issue_date', 'passport_expiry'];
  dateFields.forEach(field => {
    if (payload[field]) {
      payload[field] = new Date(payload[field]).toISOString().split('T')[0];
    }
  });

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
</style>