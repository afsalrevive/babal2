<template>
  <div>
    <n-form class="responsive-form-grid" :model="currentRecord" :rules="formRules" ref="formRef">
      <div class="header-with-bulk-switch" v-if="!editMode">
        <div style="display: flex; align-items: center; gap: 8px;">
          <n-switch v-model:value="localBulkAddMode" />
          <span>Bulk Add Mode</span>
        </div>
      </div>

      <n-form-item label="Reference No">
        <n-input :value="referenceNumber" disabled />
      </n-form-item>
      <n-form-item label="Date" path="date">
        <n-date-picker
          v-model:value="currentRecord.date"
          type="date"
          clearable
          :is-date-disabled="disableFutureDates"
        />
      </n-form-item>
      <n-form-item label="Customer" path="customer_id" class="wide-field">
        <n-space vertical>
          <n-select
            v-model:value="currentRecord.customer_id"
            :options="customerOptions"
            label-field="label"
            value-field="value"
            placeholder="Select Customer"
            filterable
          />
          <n-grid v-if="selectedCustomer" :cols="2" x-gap="12">
            <n-gi>
              <n-text type="info">Wallet: {{ selectedCustomer.wallet_balance }}</n-text>
            </n-gi>
            <n-gi>
              <n-text type="warning">Credit: {{ selectedCustomer.credit_used }}/{{ selectedCustomer.credit_limit }}</n-text>
            </n-gi>
          </n-grid>
        </n-space>
      </n-form-item>

      <n-form-item label="Passenger" path="passenger_id">
        <n-select
          v-model:value="currentRecord.passenger_id"
          :options="passengerOptions"
          label-field="label"
          value-field="value"
          placeholder="Select Passenger"
          :loading="passengersLoading"
          filterable
          clearable
          @clear="handlePassengerClear"
          @search="handlePassengerSearch"
          @update:value="handlePassengerValueUpdate"
        />
        <n-space v-if="shouldShowCreatePassenger" align="center" style="margin-top: 8px;">
          <n-button 
            type="primary" 
            :disabled="!newPassengerName" 
            @click="handleCreatePassenger"
            @mousedown.prevent
          >
            Create
          </n-button>
        </n-space>
        <n-button v-else-if="currentRecord.passenger_id" @click="showPassengerDetails" style="margin-top: 8px;">
            View Details
        </n-button>
      </n-form-item>

      <n-form-item label="Particular" path="particular_id">
        <n-select
          v-model:value="currentRecord.particular_id"
          :options="particularOptions"
          label-field="label"
          value-field="value"
          placeholder="Select Particular"
          filterable
          clearable
          @clear="handleParticularClear"
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
      
      <n-form-item v-if="isVisaManagement" label="Visa Type" path="visa_type_id">
        <n-select
          v-model:value="currentRecord.visa_type_id"
          :options="visaTypeOptions"
          label-field="label"
          value-field="value"
          placeholder="Select Visa Type"
          filterable
          clearable
          @clear="handleVisaTypeClear"
          @search="handleVisaTypeSearch"
          @update:value="handleVisaTypeValueUpdate"
        />
        <n-space v-if="shouldShowCreateVisaType" align="center" style="margin-top: 8px;">
          <n-button 
            type="primary" 
            :disabled="!newVisaTypeName" 
            @click="handleCreateVisaType"
            @mousedown.prevent
          >
            Create
          </n-button>
        </n-space>
      </n-form-item>
      
      <n-form-item v-else label="Ticket Type" path="ticket_type_id">
        <n-select
          v-model:value="currentRecord.ticket_type_id"
          :options="ticketTypeOptions"
          label-field="label"
          value-field="value"
          placeholder="Select Ticket Type"
          filterable
          clearable
          @clear="handleTicketTypeClear"
          @search="handleTicketTypeSearch"
          @update:value="handleTicketTypeValueUpdate"
        />
        <n-space v-if="shouldShowCreateTicketType" align="center" style="margin-top: 8px;">
          <n-button 
            type="primary" 
            :disabled="!newTicketTypeName" 
            @click="handleCreateTicketType"
            @mousedown.prevent
          >
            Create
          </n-button>
        </n-space>
      </n-form-item>

      <n-form-item label="Travel Location" path="travel_location_id">
        <n-select
          v-model:value="currentRecord.travel_location_id"
          :options="locationOptions"
          label-field="label"
          value-field="value"
          placeholder="Select Location"
          filterable
          clearable
          @clear="handleLocationClear"
          @search="handleLocationSearch"
          @update:value="handleLocationValueUpdate"
        />
        <n-space v-if="shouldShowCreateLocation" align="center" style="margin-top: 8px;">
          <n-button 
            type="primary" 
            :disabled="!newLocationName" 
            @click="handleCreateLocation"
            @mousedown.prevent
          >
            Create
          </n-button>
        </n-space>
      </n-form-item>
            <n-form-item label="Description" path="description" class="wide-field">
        <n-input
          v-model:value="currentRecord.description"
          type="textarea"
          placeholder="Enter a description"
        />
      </n-form-item>
      <n-form-item label="Agent" path="agent_id">
        <n-space vertical>
          <n-select
            v-model:value="currentRecord.agent_id"
            :options="agentOptions"
            label-field="label"
            value-field="value"
            placeholder="Select Agent"
            filterable
          />
          <n-grid v-if="selectedAgent" :cols="2" x-gap="12">
            <n-gi>
              <n-text type="info">Wallet: {{ selectedAgent.wallet_balance.toFixed(2) }}</n-text>
            </n-gi>
            <n-gi>
              <n-text type="warning">Credit: {{ selectedAgent.credit_used.toFixed(2) }}/{{ selectedAgent.credit_limit.toFixed(2) }}</n-text>
            </n-gi>
          </n-grid>
        </n-space>
      </n-form-item>
      <n-form-item label="Agent Paid" path="agent_paid">
        <n-input-number 
          v-model:value="currentRecord.agent_paid" 
          :min="0" 
        />
      </n-form-item>
      <n-form-item label="Agent Mode" path="agent_payment_mode"  class="wide-field">
        <n-select
          v-model:value="currentRecord.agent_payment_mode"
          :options="paymentModeOptions"
          placeholder="Select Payment Mode"
          :disabled="editMode"
        />
      </n-form-item>
      <n-form-item label="Profit in %">
        <n-input-number 
          v-model:value="profitPercentage" 
          :min="0" 
          :step="1"
          suffix="%"
        />
      </n-form-item>
      <n-form-item label="Customer Mode" path="customer_payment_mode" class="wide-field">
        <n-select
          v-model:value="currentRecord.customer_payment_mode"
          :options="paymentModeOptions"
          placeholder="Select Payment Mode"
          :disabled="editMode"
        />
      </n-form-item>
      <n-form-item label="Customer Charge" path="customer_charge">
        <n-input-number 
          v-model:value="currentRecord.customer_charge"
          :min="0" 
        />

        <template #feedback>
          <n-alert class="wide-field" v-if="profit !== null" title="Profit" type="info">
            {{ profit }}
          </n-alert>
        </template>
      </n-form-item>
      <n-space class="action-buttons" justify="end">
        <n-button @click="emits('cancel')">Cancel</n-button>
        <PermissionWrapper :resource="isVisaManagement ? 'visa' : 'ticket'" :operation="editMode ? 'modify' : 'write'">
          <n-button type="primary" @click="submitForm()">
            {{ editMode ? 'Update' : (localBulkAddMode ? 'Save and Next' : `Book ${isVisaManagement ? 'Visa' : 'Ticket'}`) }}
          </n-button>
        </PermissionWrapper>
      </n-space>
    </n-form>

    <n-modal v-model:show="showPassengerDetailsModal" preset="card" title="Passenger Details" class="full-width-modal">
      <n-card class="modal-card">
        <n-space vertical>
          <n-alert type="info" :title="`Details for ${selectedPassengerDetails.name}`">
            <n-grid cols="1 600:2" x-gap="12" y-gap="8">
              <n-gi><b>Name:</b> {{ selectedPassengerDetails.name }}</n-gi>
              <n-gi><b>Contact:</b> {{ selectedPassengerDetails.contact || 'N/A' }}</n-gi>
              <n-gi><b>Passport Number:</b> {{ selectedPassengerDetails.passport_number || 'N/A' }}</n-gi>
              <n-gi><b>Salutation:</b> {{ selectedPassengerDetails.salutation || 'N/A' }}</n-gi>
              <n-gi><b>Date of Birth:</b> {{ selectedPassengerDetails.date_of_birth ? new Date(selectedPassengerDetails.date_of_birth).toLocaleDateString() : 'N/A' }}</n-gi>
              <n-gi><b>Passport Issue Date:</b> {{ selectedPassengerDetails.passport_issue_date ? new Date(selectedPassengerDetails.passport_issue_date).toLocaleDateString() : 'N/A' }}</n-gi>
              <n-gi><b>Passport Expiry:</b> {{ selectedPassengerDetails.passport_expiry ? new Date(selectedPassengerDetails.passport_expiry).toLocaleDateString() : 'N/A' }}</n-gi>
              <n-gi><b>Nationality:</b> {{ selectedPassengerDetails.nationality || 'N/A' }}</n-gi>
              <n-gi><b>Address:</b> {{ selectedPassengerDetails.address || 'N/A' }}</n-gi>
              <n-gi><b>City:</b> {{ selectedPassengerDetails.city || 'N/A' }}</n-gi>
              <n-gi><b>State:</b> {{ selectedPassengerDetails.state || 'N/A' }}</n-gi>
              <n-gi><b>Country:</b> {{ selectedPassengerDetails.country || 'N/A' }}</n-gi>
              <n-gi><b>Zip Code:</b> {{ selectedPassengerDetails.zip_code || 'N/A' }}</n-gi>
              <n-gi><b>Father's Name:</b> {{ selectedPassengerDetails.fathers_name || 'N/A' }}</n-gi>
              <n-gi><b>Mother's Name:</b> {{ selectedPassengerDetails.mothers_name || 'N/A' }}</n-gi>
            </n-grid>
          </n-alert>
        </n-space>
        <template #footer>
          <n-space justify="space-between">
            <n-button @click="showPassengerDetailsModal = false">Close</n-button>
            <PermissionWrapper resource="entity" operation="read">
               <PassengerExport :passengers="[selectedPassengerDetails]" :selected-passenger-ids="[selectedPassengerDetails.id]" />
            </PermissionWrapper>
          </n-space>
        </template>
      </n-card>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue';
import { useMessage, NButton, NSpace, NForm, NFormItem, NInputNumber, NInput, NSelect, NGrid, NGi, NText, NDatePicker, NAlert, NModal, NCard, NSwitch } from 'naive-ui';
import type { FormInst, FormRules } from 'naive-ui';
import api from '@/api';
import PermissionWrapper from '@/components/PermissionWrapper.vue';
import PassengerExport from './PassengerExport.vue';

type SelectOption = { label: string; value: string | number; [key: string]: any; };

const props = defineProps({
  editMode: { type: Boolean, default: false },
  formData: { type: Object, default: () => ({}) },
  referenceNumber: { type: String, required: true },
  isVisaManagement: { type: Boolean, default: false },
  bulkAddMode: { type: Boolean, default: false },
});

const emits = defineEmits(['record-booked', 'record-updated', 'open-entity-modal', 'cancel', 'update:bulkAddMode']);

const message = useMessage();
const formRef = ref<FormInst | null>(null);

const currentRecord = ref<any>({});
const passengersLoading = ref(false);
const newPassengerName = ref('');
const newParticularName = ref('');
const newLocationName = ref('');
const newVisaTypeName = ref('');
const newTicketTypeName = ref('');

const localBulkAddMode = computed({
  get: () => props.bulkAddMode,
  set: (val) => emits('update:bulkAddMode', val)
});

const customerOptions = ref<SelectOption[]>([]);
const passengerOptions = ref<SelectOption[]>([]);
const locationOptions = ref<SelectOption[]>([]);
const agentOptions = ref<SelectOption[]>([]);
const particularOptions = ref<SelectOption[]>([]);
const ticketTypeOptions = ref<SelectOption[]>([]);
const visaTypeOptions = ref<SelectOption[]>([]);
const allPassengers = ref<any[]>([]);

const showPassengerDetailsModal = ref(false);
const selectedPassengerDetails = ref<any>({});
const preventUpdate = ref(false);

const paymentModeOptions: SelectOption[] = [
  { label: 'Cash', value: 'cash' },
  { label: 'Online', value: 'online' },
  { label: 'Wallet', value: 'wallet' },
];

const profitPercentage = ref(10);

const formRules = computed<FormRules>(() => {
  const rules: FormRules = {
    customer_id: { required: true, message: 'Customer is required', validator: (rule, value) => value !== null && value !== undefined, trigger: ['change', 'blur'] },
    passenger_id: { required: true, message: 'Passenger is required', validator: (rule, value) => value !== null && value !== undefined, trigger: ['change', 'blur'] },
    customer_charge: { required: true, validator: (rule: any, value: number) => value !== null && value !== undefined && value >= 0, message: 'Customer charge must be a positive number', trigger: ['blur', 'input'] },
    customer_payment_mode: { required: true, message: 'Payment mode is required', trigger: ['change'] },
    date: { required: true, validator: (_rule: any, value: any) => !!value, message: 'Date is required', trigger: ['change', 'blur'] },
    agent_id: { required: true, message: 'Agent is required', validator: (rule, value) => value !== null && value !== undefined, trigger: ['change', 'blur'] },
    agent_payment_mode: { required: true, message: 'Agent Mode is required', trigger: ['change'] },
  };
  
  if (props.isVisaManagement) {
    rules.visa_type_id = { required: true, message: 'Visa Type is required',validator: (rule, value) => !!value, trigger: ['change', 'blur'] };
  } else {
     rules.ticket_type_id = { required: true, message: 'Ticket Type is required',validator: (rule, value) => !!value, trigger: ['change', 'blur'] };
  }
  
  return rules;
});

const selectedCustomer = computed(() => {
  if (!currentRecord.value.customer_id) return null;
  return customerOptions.value.find(c => c.value === currentRecord.value.customer_id);
});

const selectedAgent = computed(() => {
  if (!currentRecord.value.agent_id) return null;
  return agentOptions.value.find(a => a.value === currentRecord.value.agent_id);
});

const profit = computed(() => {
  if (currentRecord.value.customer_charge === null || currentRecord.value.agent_paid === null) 
    return null;
  
  const calcProfit = currentRecord.value.customer_charge - currentRecord.value.agent_paid;
  return roundToTwo(calcProfit).toFixed(2);
});

const shouldShowCreatePassenger = computed(() => !!newPassengerName.value && !passengerOptions.value.some(p => (p?.label || '').toLowerCase() === newPassengerName.value.toLowerCase()));
const shouldShowCreateParticular = computed(() => !!newParticularName.value && !particularOptions.value.some(p => (p?.label || '').toLowerCase() === newParticularName.value.toLowerCase()));
const shouldShowCreateLocation = computed(() => !!newLocationName.value && !locationOptions.value.some(l => (l?.label || '').toLowerCase() === newLocationName.value.toLowerCase()));
const shouldShowCreateVisaType = computed(() => props.isVisaManagement && !!newVisaTypeName.value && !visaTypeOptions.value.some((vt: any) => (vt?.label || '').toLowerCase() === newVisaTypeName.value.toLowerCase()));
const shouldShowCreateTicketType = computed(() => !props.isVisaManagement && !!newTicketTypeName.value && !ticketTypeOptions.value.some((tt: any) => (tt?.label || '').toLowerCase() === newTicketTypeName.value.toLowerCase()));

const disableFutureDates = (timestamp: number) => timestamp > Date.now();

watch(() => props.formData, (newVal) => {
  if (newVal) {
    currentRecord.value = { ...newVal, date: newVal.date ? new Date(newVal.date).getTime() : Date.now() };
    if (newVal.agent_paid && newVal.customer_charge) {
      profitPercentage.value = Math.round(((newVal.customer_charge / newVal.agent_paid) - 1) * 100);
    } else {
      profitPercentage.value = 10;
    }
    nextTick(() => formRef.value?.restoreValidation());
  }
}, { immediate: true });

const fetchOptions = async () => {
  passengersLoading.value = true;
  try {
    const [customers, locations, agents, particulars, passengers, ticketTypes, visaTypes] = await Promise.all([
      api.get('/api/manage/customer'),
      api.get('/api/manage/travel_location'),
      api.get('/api/manage/agent'),
      api.get('/api/manage/particular'),
      api.get('/api/manage/passenger'),
      api.get('/api/manage/ticket_type'),
      api.get('/api/manage/visa_type'),
    ]);
    
    customerOptions.value = customers.data.map((c: any) => ({ label: c.name, value: c.id, wallet_balance: c.wallet_balance, credit_used: c.credit_used, credit_limit: c.credit_limit }));
    locationOptions.value = locations.data.map((l: any) => ({ label: l.name, value: l.id }));
    agentOptions.value = agents.data.map((a: any) => ({ label: a.name, value: a.id, wallet_balance: a.wallet_balance, credit_used: a.credit_limit - a.credit_balance, credit_limit: a.credit_limit }));
    particularOptions.value = particulars.data.map((p: any) => ({ label: p.name, value: p.id }));
    allPassengers.value = passengers.data.map((p: any) => ({...p, label: p.name, value: p.id}));
    passengerOptions.value = allPassengers.value.map((p: any) => ({ label: p.name, value: p.id }));
    ticketTypeOptions.value = ticketTypes.data.map((tt: any) => ({ label: tt.name, value: tt.id }));
    visaTypeOptions.value = visaTypes.data.map((vt: any) => ({ label: vt.name, value: vt.id }));

    
  } catch (e: any) {
    message.error('Failed to load options: ' + (e.response?.data?.error || e.message));
  } finally {
    passengersLoading.value = false;
  }
};

const handlePassengerSearch = (query: string) => {
  if (query && query.trim() !== '') {
    currentRecord.value.passenger_id = null;
    const existingPassenger = passengerOptions.value.find(p => (p?.label || '').toLowerCase() === query.toLowerCase());
    newPassengerName.value = existingPassenger ? '' : query;
  } else {
    newPassengerName.value = '';
  }
};
const handleParticularSearch = (query: string) => {
  if (query && query.trim() !== '') {
    currentRecord.value.particular_id = null;
    const existingParticular = particularOptions.value.find(p => (p?.label || '').toLowerCase() === query.toLowerCase());
    newParticularName.value = existingParticular ? '' : query;
  } else {
    newParticularName.value = '';
  }
};
const handleLocationSearch = (query: string) => {
  if (query && query.trim() !== '') {
    currentRecord.value.travel_location_id = null;
    const existingLocation = locationOptions.value.find(l => (l?.label || '').toLowerCase() === query.toLowerCase());
    newLocationName.value = existingLocation ? '' : query;
  } else {
    newLocationName.value = '';
  }
};

const handleVisaTypeSearch = (query: string) => {
  if (query && query.trim() !== '') {
    currentRecord.value.visa_type_id = null;
    const existingVisaType = visaTypeOptions.value.find((vt: any) => (vt?.label || '').toLowerCase() === query.toLowerCase());
    newVisaTypeName.value = existingVisaType ? '' : query;
  } else {
    newVisaTypeName.value = '';
  }
};

const handleTicketTypeSearch = (query: string) => {
  if (query && query.trim() !== '') {
    currentRecord.value.ticket_type_id = null;
    const existingTicketType = ticketTypeOptions.value.find((tt: any) => (tt?.label || '').toLowerCase() === query.toLowerCase());
    newTicketTypeName.value = existingTicketType ? '' : query;
  } else {
    newTicketTypeName.value = '';
  }
};

const handlePassengerClear = () => { newPassengerName.value = ''; currentRecord.value.passenger_id = null; };
const handleParticularClear = () => { newParticularName.value = ''; currentRecord.value.particular_id = null; };
const handleLocationClear = () => { newLocationName.value = ''; currentRecord.value.travel_location_id = null; };
const handleVisaTypeClear = () => { newVisaTypeName.value = ''; currentRecord.value.visa_type_id = null; };
const handleTicketTypeClear = () => { newTicketTypeName.value = ''; currentRecord.value.ticket_type_id = null; };

const handlePassengerValueUpdate = (value: number | null) => {
    currentRecord.value.passenger_id = value;
    newPassengerName.value = '';
    nextTick(() => {
        formRef.value?.restoreValidation();
    });
};

const handleParticularValueUpdate = (value: number | null) => { currentRecord.value.particular_id = value; newParticularName.value = ''; };
const handleLocationValueUpdate = (value: number | null) => { currentRecord.value.travel_location_id = value; newLocationName.value = ''; };
const handleVisaTypeValueUpdate = (value: number | null) => { currentRecord.value.visa_type_id = value; newVisaTypeName.value = ''; };
const handleTicketTypeValueUpdate = (value: number | null) => { currentRecord.value.ticket_type_id = value; newTicketTypeName.value = ''; };


const handleCreatePassenger = () => { emits('open-entity-modal', 'passenger', newPassengerName.value); };
const handleCreateParticular = () => { emits('open-entity-modal', 'particular', newParticularName.value); };
const handleCreateLocation = () => { emits('open-entity-modal', 'travel_location', newLocationName.value); };
const handleCreateVisaType = () => { emits('open-entity-modal', 'visa_type', newVisaTypeName.value); };
const handleCreateTicketType = () => { emits('open-entity-modal', 'ticket_type', newTicketTypeName.value); };

const showPassengerDetails = () => {
  const passengerId = currentRecord.value.passenger_id;
  if (passengerId) {
    const passenger = allPassengers.value.find(p => p.value === passengerId);
    if (passenger) {
      selectedPassengerDetails.value = passenger;
      showPassengerDetailsModal.value = true;
    }
  }
};

const processPayload = () => {
  const formattedDate = currentRecord.value.date ? new Date(currentRecord.value.date).toLocaleDateString('fr-CA').split('T')[0] : null;
  
  const payload = { 
    ...currentRecord.value,
    customer_id: currentRecord.value.customer_id ? Number(currentRecord.value.customer_id) : null,
    agent_id: currentRecord.value.agent_id ? Number(currentRecord.value.agent_id) : null,
    travel_location_id: currentRecord.value.travel_location_id ? Number(currentRecord.value.travel_location_id) : null,
    passenger_id: currentRecord.value.passenger_id ? Number(currentRecord.value.passenger_id) : null,
    particular_id: currentRecord.value.particular_id ? Number(currentRecord.value.particular_id) : null,
    customer_charge: roundToTwo(Number(currentRecord.value.customer_charge)),
    agent_paid: roundToTwo(Number(currentRecord.value.agent_paid || 0)),
    description: currentRecord.value.description,
    date: formattedDate
  };

  if (!props.isVisaManagement) {
    delete payload.visa_type_id;
  } else {
    delete payload.ticket_type_id;
  }
  return payload;
};

const submitForm = async () => {
  try {
    await formRef.value?.validate();
    const payload = processPayload();
    const endpoint = props.isVisaManagement ? '/api/visas' : '/api/tickets';
    if (props.editMode) {
      await api.patch(endpoint, payload);
      message.success(`${props.isVisaManagement ? 'Visa' : 'Ticket'} updated successfully`);
      emits('record-updated', payload);
    } else {
      await api.post(endpoint, payload);
      message.success(`${props.isVisaManagement ? 'Visa' : 'Ticket'} booked!`);
      if (localBulkAddMode.value) {
        const fieldsToReset = ['passenger_id', 'customer_id', 'agent_id', 'customer_paid','agent_paid'];
        fieldsToReset.forEach(key => {
          currentRecord.value[key] = null;
        });
        currentRecord.value.ref_no = '';
        nextTick(() => formRef.value?.restoreValidation());
      } else {
        emits('record-booked', payload);
      }
    }
  } catch (e: any) {
    handleApiError(e);
  }
};

const handleApiError = (e: any) => {
  console.error('API Error:', e);
  const errorMsg = e.response?.data?.error || e.response?.data?.message || 'Operation failed';
  if (e.response?.data?.field_errors) {
    message.error('Please fix the form errors');
  } else {
    message.error(errorMsg);
  }
};

const roundToTwo = (num: number) => {
  return Math.round((num + Number.EPSILON) * 100) / 100;
};

watch(profitPercentage, (newPercentage) => {
  if (preventUpdate.value) return;
  preventUpdate.value = true;
  
  if (currentRecord.value.agent_paid !== null && currentRecord.value.agent_paid !== undefined) {
    const newCharge = currentRecord.value.agent_paid * (1 + newPercentage / 100);
    currentRecord.value.customer_charge = Math.round(newCharge / 5) * 5;
  }
  
  nextTick(() => { preventUpdate.value = false; });
});

watch(() => currentRecord.value.customer_charge, (newCharge) => {
  if (preventUpdate.value) return;
  preventUpdate.value = true;
  
  if (currentRecord.value.agent_paid !== null && currentRecord.value.agent_paid !== undefined && currentRecord.value.agent_paid !== 0) {
    const newPercentage = ((newCharge / currentRecord.value.agent_paid) - 1) * 100;
    profitPercentage.value = roundToTwo(newPercentage);
  }
  
  nextTick(() => { preventUpdate.value = false; });
});

watch(() => currentRecord.value.agent_paid, (newAgentPaid) => {
  if (preventUpdate.value) return;
  preventUpdate.value = true;
  
  if (newAgentPaid !== null && newAgentPaid !== undefined) {
    const newCharge = newAgentPaid * (1 + profitPercentage.value / 100);
    currentRecord.value.customer_charge = Math.round(newCharge / 5) * 5;
  }
  
  nextTick(() => { preventUpdate.value = false; });
});

onMounted(() => {
  fetchOptions();
});

defineExpose({
  fetchOptions,
  currentRecord,
  formRef,
  allPassengers,
});
</script>

<style scoped lang="scss">
@use '@/styles/theme' as *;
</style>