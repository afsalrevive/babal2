<template>
  <div>
    <div class="header-with-bulk-switch" v-if="!editMode">
      <div style="display: flex; align-items: center; gap: 8px;">
        <n-switch v-model:value="localBulkAddMode" />
        <span>Bulk Add Mode</span>
      </div>
    </div>
    <n-form class="responsive-form-grid" :model="form" :rules="formRules" ref="formRef">
      <n-form-item label="Reference No">
        <n-input :value="referenceNumber" disabled />
      </n-form-item>

      <n-form-item label="Date" path="date">
        <n-date-picker
          v-model:value="form.date"
          type="date"
          clearable
          :is-date-disabled="disableFutureDates"
        />
      </n-form-item>

      <n-form-item label="Customer" path="customer_id" class="wide-field">
        <n-space vertical>
          <n-select
            v-model:value="form.customer_id"
            :options="customerOptions"
            label-field="name"
            value-field="id"
            placeholder="Select Customer"
            filterable
          />
          <n-grid v-if="selectedCustomer" :cols="2" x-gap="12">
            <n-gi>
              <n-text type="info">Wallet: {{ selectedCustomer.wallet_balance.toFixed(2) }}</n-text>
            </n-gi>
            <n-gi>
              <n-text type="warning">Credit: {{ selectedCustomer.credit_used.toFixed(2) }}/{{ selectedCustomer.credit_limit.toFixed(2) }}</n-text>
            </n-gi>
          </n-grid>
        </n-space>
      </n-form-item>

      <n-form-item label="Particular" path="particular_id">
        <n-select
          v-model:value="form.particular_id"
          :options="particularOptions"
          label-field="name"
          value-field="id"
          placeholder="Select Particular"
          filterable
          @search="handleParticularSearch"
          @update:value="handleParticularValueUpdate"
        />
        <n-space v-if="shouldShowCreateParticular" align="center" style="margin-top: 8px;">
          <n-button 
            type="primary" 
            :disabled="!newParticularName" 
            @click="handleCreateParticular"
            @mousedown.prevent
          >
            Create
          </n-button>
        </n-space>
      </n-form-item>

      <n-form-item label="Description" path="description" class="wide-field">
        <n-input
          v-model:value="form.description"
          type="textarea"
          placeholder="Enter service details..."
        />
      </n-form-item>

      <n-form-item label="Customer Charge" path="customer_charge">
        <n-input-number
          v-model:value="form.customer_charge"
          :min="0"
        />
      </n-form-item>

      <n-form-item label="Payment Mode" path="customer_payment_mode" class="wide-field">
        <n-select
          v-model:value="form.customer_payment_mode"
          :options="paymentModeOptions"
          placeholder="Select Payment Mode"
          :disabled="editMode"
        />
      </n-form-item>

      <n-space class="action-buttons" justify="end">
        <n-button @click="$emit('cancel')">Cancel</n-button>
        <PermissionWrapper resource="service" :operation="editMode ? 'modify' : 'write'">
          <n-button type="primary" @click="submitForm()">
            {{ editMode ? 'Update' : (localBulkAddMode ? 'Save and Next' : 'Book Service') }}
          </n-button>
        </PermissionWrapper>
      </n-space>
    </n-form>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, reactive, nextTick } from 'vue';
import { useMessage, NButton, NSpace, NForm, NFormItem, NSelect, NGrid, NGi, NText, NInput, NDatePicker, NInputNumber, NSwitch } from 'naive-ui';
import type { FormRules } from 'naive-ui';
import api from '@/api';
import PermissionWrapper from '@/components/PermissionWrapper.vue';

const props = defineProps({
  formData: { type: Object, required: true },
  editMode: { type: Boolean, default: false },
  bulkAddMode: { type: Boolean, default: false },
  referenceNumber: { type: String, required: true },
});

const emits = defineEmits(['record-booked', 'record-updated', 'cancel', 'update:bulkAddMode', 'open-entity-modal']);
const message = useMessage();
const formRef = ref<any>(null);

const form = reactive({
  customer_id: props.formData.customer_id ?? null,
  particular_id: props.formData.particular_id ?? null,
  ref_no: props.formData.ref_no ?? '',
  customer_charge: props.formData.customer_charge ?? 0,
  customer_payment_mode: props.formData.customer_payment_mode ?? 'cash',
  date: props.formData.date ? new Date(props.formData.date).getTime() : Date.now(),
  description: props.formData.description ?? '',
});
const customerOptions = ref<any[]>([]);
const particularOptions = ref<any[]>([]);
const newParticularName = ref('');

const localBulkAddMode = computed({
  get: () => props.bulkAddMode,
  set: (val) => emits('update:bulkAddMode', val),
});

const paymentModeOptions = [
  { label: 'Cash', value: 'cash' },
  { label: 'Online', value: 'online' },
  { label: 'Wallet', value: 'wallet' },
];

const selectedCustomer = computed(() => {
  if (!form.customer_id) return null;
  return customerOptions.value.find(c => c.id === form.customer_id);
});

const formRules = ref<FormRules>({
  customer_id: {
    required: true,
    validator: (rule: any, value: any) => (value !== null && value !== undefined),
    message: 'Customer is required',
    trigger: ['change', 'blur']
  },
  customer_charge: {
    required: true,
    validator: (rule: any, value: any) => (typeof value === 'number' && value >= 0),
    message: 'Customer charge must be a positive number',
    trigger: ['blur']
  },
  customer_payment_mode: {
    required: true,
    message: 'Payment mode is required',
    trigger: ['change']
  },
  date: {
    required: true,
    validator: (_rule: any, value: any) => !!value,
    message: 'Date is required',
    trigger: ['change', 'blur']
  }
});

const disableFutureDates = (timestamp: number) => {
  return timestamp > Date.now();
};

const shouldShowCreateParticular = computed(() => !!newParticularName.value && !particularOptions.value.some(p => (p?.name || '').toLowerCase() === newParticularName.value.toLowerCase()));

const fetchOptions = async () => {
  try {
    const [customers, particulars] = await Promise.all([
      api.get('/api/manage/customer'),
      api.get('/api/manage/particular'),
    ]);
    customerOptions.value = customers.data.map((c: any) => ({
      name: c.name,
      id: c.id,
      wallet_balance: c.wallet_balance,
      credit_used: c.credit_used,
      credit_limit: c.credit_limit,
    }));
    particularOptions.value = particulars.data.map((p: any) => ({
      name: p.name,
      id: p.id,
    }));
  } catch (e) {
    handleApiError(e);
  }
};

const handleParticularSearch = (query: string) => {
  if (query && query.trim() !== '') {
    const existingParticular = particularOptions.value.find(p => (p?.name || '').toLowerCase() === query.toLowerCase());
    newParticularName.value = existingParticular ? '' : query;
  } else {
    newParticularName.value = '';
  }
};

const handleParticularValueUpdate = (value: number | null) => {
    form.particular_id = value;
    newParticularName.value = '';
};

const handleCreateParticular = () => {
    emits('open-entity-modal', 'particular', newParticularName.value);
};

const submitForm = async () => {
  try {
    await formRef.value?.validate();

    const selectedDate = new Date(form.date);
    const formattedDate = `${selectedDate.getFullYear()}-${(selectedDate.getMonth() + 1).toString().padStart(2, '0')}-${selectedDate.getDate().toString().padStart(2, '0')}`;

    const payload = {
      ...form,
      date: formattedDate,
    };

    if (props.editMode) {
      await api.patch('/api/services', payload);
      message.success('Service updated successfully');
      emits('record-updated');
    } else {
      const response = await api.post('/api/services', payload);
      message.success(`Service booked! Reference: ${response.data.ref_no}`);
      emits('record-booked', { ...payload, ...response.data });
    }
  } catch (e) {
    handleApiError(e);
  }
};

const handleApiError = (e: any) => {
  if (e.response) {
    const errorMsg = e.response.data?.error || 'Operation failed';
    message.error(errorMsg);
  } else {
    message.error('Request error: ' + e.message);
  }
};

watch(() => props.formData, (newVal) => {
  if (newVal) {
    Object.assign(form, {
      ...newVal,
      date: newVal.date ? new Date(newVal.date).getTime() : Date.now()
    });
  }
}, { deep: true });

onMounted(() => {
  fetchOptions();
});

defineExpose({
  fetchOptions,
  form,
});
</script>

<style scoped lang="scss">
@use '@/styles/theme' as *;
</style>