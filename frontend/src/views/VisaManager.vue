<template>
  <n-card>
    <template #header>
      <n-h2>Visa Management</n-h2>
    </template>

    <n-tabs v-model:value="activeTab" type="line" animated>
      <n-tab-pane name="active" tab="Active Visas">
        <n-space justify="space-between" wrap class="table-controls">
          <n-space>
            <n-input
              v-model:value="searchQuery"
              placeholder="Search visas"
              clearable
              style="max-width: 300px;"
            />
            <n-date-picker
              v-model:value="dateRange"
              type="daterange"
              clearable
              :default-value="defaultDateRange"
              style="max-width: 300px;"
            />
            <n-button @click="exportExcel" type="primary" secondary>
              <template #icon>
                <n-icon><DocumentTextOutline /></n-icon>
              </template>
              Excel
            </n-button>
            <n-button @click="exportPDF" type="primary" secondary>
              <template #icon>
                <n-icon><DocumentTextOutline /></n-icon>
              </template>
              PDF
            </n-button>
          </n-space>
          <PermissionWrapper resource="visa" operation="write">
            <n-button type="primary" @click="openAddModal">Book Visa</n-button>
          </PermissionWrapper>
        </n-space>

        <n-data-table
          :columns="columnsBooked"
          :data="filteredActiveVisas"
          :loading="loading"
          :pagination="pagination"
          striped
          style="margin-top: 16px;"
        />
      </n-tab-pane>
      <n-tab-pane name="cancelled" tab="Cancelled Visas">
        <n-space>
          <n-input
            v-model:value="searchQuery"
            placeholder="Search visas"
            clearable
            style="max-width: 300px;"
          />
          <n-date-picker
            v-model:value="dateRange"
            type="daterange"
            clearable
            :default-value="defaultDateRange"
            style="max-width: 300px;"
          />
          <n-button @click="exportExcel" type="primary" secondary>
            <template #icon>
              <n-icon><DocumentTextOutline /></n-icon>
            </template>
            Excel
          </n-button>
          <n-button @click="exportPDF" type="primary" secondary>
            <template #icon>
              <n-icon><DocumentTextOutline /></n-icon>
            </template>
            PDF
          </n-button>
        </n-space>
        <n-data-table
          :columns="columnsCancelled"
          :data="filteredCancelledVisas"
          :loading="loading"
          :pagination="pagination"
          striped
          style="margin-top: 16px;"
        />
      </n-tab-pane>
    </n-tabs>

    <n-modal v-model:show="modalVisible" class="full-width-modal">
      <n-card class="modal-card">
        <n-h2 class="modal-title">{{ editMode ? 'Edit Visa' : 'Book Visa' }}</n-h2>
        <BookingForm
          v-show="modalVisible"
          :edit-mode="editMode"
          :form-data="currentVisa"
          :reference-number="referenceNumber"
          :is-visa-management="true"
          :bulk-add-mode="bulkAddMode"
          @update:bulkAddMode="bulkAddMode = $event"
          @record-booked="handleFormSuccess"
          @record-updated="handleFormSuccess"
          @open-entity-modal="openEntityModal"
          @cancel="modalVisible = false"
          ref="bookingFormRef"
        />
      </n-card>
    </n-modal>

    <n-modal v-model:show="cancelModalVisible" class="transaction-modal">
      <n-card class="modal-card">
        <n-h2 class="modal-title">Cancel Visa #{{ currentVisa.ref_no }}</n-h2>
        <n-form class="responsive-form-grid">
          <div class="refund-section">
            <n-h3>Customer Refund</n-h3>
            <n-form-item label="Refund Amount">
              <n-input-number v-model:value="cancelData.customer_refund_amount" :min="0" />
            </n-form-item>
            <n-form-item label="Refund Mode">
              <n-select
                v-model:value="cancelData.customer_refund_mode"
                :options="paymentModeOptions"
                placeholder="Select Refund Mode"
              />
            </n-form-item>
          </div>
          <n-divider v-if="currentVisa.agent_id" />
          <div class="recovery-section" v-if="currentVisa.agent_id">
            <n-h3>Agent Recovery</n-h3>
            <n-form-item label="Recovery Amount">
              <n-input-number v-model:value="cancelData.agent_recovery_amount" :min="0" />
            </n-form-item>
            <n-form-item label="Recovery Mode">
              <n-select
                v-model:value="cancelData.agent_recovery_mode"
                :options="paymentModeOptions"
                placeholder="Select Recovery Mode"
              />
            </n-form-item>
          </div>
          <n-space class="action-buttons" justify="end">
            <n-button @click="cancelModalVisible = false">Cancel</n-button>
            <PermissionWrapper resource="visa" operation="modify">
              <n-button type="error" @click="confirmCancel">Confirm Cancellation</n-button>
            </PermissionWrapper>
          </n-space>
        </n-form>
      </n-card>
    </n-modal>
    
    <n-modal v-model:show="editCancelledModalVisible" class="transaction-modal">
      <n-card class="modal-card">
        <n-h2 class="modal-title">Edit Cancelled Visa #{{ currentVisa.ref_no }}</n-h2>
        <n-form class="responsive-form-grid">
          <div class="refund-section">
            <n-h3>Customer Refund</n-h3>
            <n-form-item label="Refund Amount">
              <n-input-number v-model:value="currentVisa.customer_refund_amount" :min="0" />
            </n-form-item>
            <n-form-item label="Refund Mode">
              <n-select
                v-model:value="currentVisa.customer_refund_mode"
                :options="paymentModeOptions"
                placeholder="Select Refund Mode"
              />
            </n-form-item>
          </div>
          <n-divider v-if="currentVisa.agent_id" />
          <div class="recovery-section" v-if="currentVisa.agent_id">
            <n-h3>Agent Recovery</n-h3>
            <n-form-item label="Recovery Amount">
              <n-input-number v-model:value="currentVisa.agent_recovery_amount" :min="0" />
            </n-form-item>
            <n-form-item label="Recovery Mode">
              <n-select
                v-model:value="currentVisa.agent_recovery_mode"
                :options="paymentModeOptions"
                placeholder="Select Recovery Mode"
              />
            </n-form-item>
          </div>
          <n-space class="action-buttons" justify="end">
            <n-button @click="editCancelledModalVisible = false">Cancel</n-button>
            <PermissionWrapper resource="visa" operation="modify">
              <n-button type="primary" @click="updateCancelledVisa">Update</n-button>
            </PermissionWrapper>
          </n-space>
        </n-form>
      </n-card>
    </n-modal>

    <n-modal v-model:show="showDeleteModal" :mask-closable="false" preset="dialog" title="Confirm Deletion">
      <n-alert type="warning">
        Are you sure you want to delete this visa? This action cannot be undone.
      </n-alert>
      <template #action>
        <n-space>
          <n-button @click="showDeleteModal = false">Cancel</n-button>
          <n-button type="error" @click="deleteVisaAndCloseModal">Delete</n-button>
        </n-space>
      </template>
    </n-modal>
    <n-modal v-model:show="showCancelConfirmModal" :mask-closable="false" preset="dialog" title="Confirm Cancellation">
      <n-alert type="warning">
        Are you sure you want to cancel this visa? This will create a refund/recovery transaction.
      </n-alert>
      <template #action>
        <n-space>
          <n-button @click="showCancelConfirmModal = false">Cancel</n-button>
          <n-button type="error" @click="handleConfirmCancel">Confirm</n-button>
        </n-space>
      </template>
    </n-modal>

    <EntityFormModal
      :show="entityModalVisible"
      :entity-type="entityToCreate"
      :form-data="{ name: defaultEntityName, customer_id: currentVisa.customer_id }"
      @update:show="handleEntityModalClose"
      @entity-created="handleEntityCreated"
    />

    <AttachmentModal
      :show="attachmentModalVisible"
      :parent-type="attachmentParentType"
      :parent-id="attachmentParentId"
      @update:show="attachmentModalVisible = $event"
      @attachment-updated="fetchData"
    />
  </n-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h, reactive, watch } from 'vue';
import { useMessage, NButton, NSpace, NForm, NFormItem, NInputNumber, NInput, NSelect, NGrid, NGi, NText, NDatePicker, NModal, NCard, NH2, NH3, NDivider, NAlert, NDataTable, NIcon, NSwitch } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import api from '@/api';
import PermissionWrapper from '@/components/PermissionWrapper.vue';
import { DocumentTextOutline } from '@vicons/ionicons5';
import EntityFormModal from './EntityFormModal.vue';
import AttachmentModal from './AttachmentModal.vue';
import BookingForm from './BookingForm.vue';

const message = useMessage();
const bookingFormRef = ref<any>(null);

const entityModalVisible = ref(false);
const entityToCreate = ref('');
const defaultEntityName = ref('');

const activeTab = ref('active');
const searchQuery = ref('');
const allVisas = ref<any[]>([]); // New reactive variable to hold all visas
const loading = ref(false);
const modalVisible = ref(false);
const cancelModalVisible = ref(false);
const editCancelledModalVisible = ref(false);
const editMode = ref(false);

const showDeleteModal = ref(false);
const showCancelConfirmModal = ref(false);
const visaToDeleteId = ref<number | null>(null);
const visaToCancel = ref<any>(null);

const dateRange = ref<[number, number] | null>(null);
const defaultDateRange = computed(() => {
  const end = Date.now();
  const start = end - 7 * 24 * 60 * 60 * 1000;
  return [start, end] as [number, number];
});

const attachmentModalVisible = ref(false);
const attachmentParentType = ref('');
const attachmentParentId = ref(null);


const currentVisa = ref<any>({
  id: null,
  customer_id: null,
  agent_id: null,
  travel_location_id: null,
  passenger_id: null,
  particular_id: null,
  ref_no: '',
  visa_type_id: null,
  customer_charge: 0,
  agent_paid: 0,
  customer_payment_mode: 'cash',
  agent_payment_mode: 'cash',
  date: Date.now(),
});

const bulkAddMode = ref(false);

const cancelData = ref({
  customer_refund_amount: 0,
  customer_refund_mode: 'cash',
  agent_recovery_amount: 0,
  agent_recovery_mode: 'cash',
});

const paymentModeOptions = [
  { label: 'Cash', value: 'cash' },
  { label: 'Online', value: 'online' },
  { label: 'Wallet', value: 'wallet' },
];

const referencePlaceholder = ref('');
const referenceNumber = computed(() => {
  if (editMode.value && currentVisa.value.ref_no) {
    return currentVisa.value.ref_no;
  }
  return referencePlaceholder.value || 'Generating...';
});

const filterVisasByDate = (visasList: any[]) => {
  if (!dateRange.value) return visasList;
  const [startTimestamp, endTimestamp] = dateRange.value;
  const startDate = new Date(startTimestamp);
  const endDate = new Date(endTimestamp);
  endDate.setHours(23, 59, 59, 999);
  return visasList.filter(visa => {
    if (!visa.date) return false;
    const visaDate = new Date(visa.date);
    return visaDate >= startDate && visaDate <= endDate;
  });
};

// New computed property for filtering based on search query
const filteredBySearch = computed(() => {
  const search = searchQuery.value.toLowerCase();
  return allVisas.value.filter(v => 
    v.ref_no?.toLowerCase().includes(search) ||
    (v.agent_name && v.agent_name.toLowerCase().includes(search)) || 
    (v.customer_name?.toLowerCase().includes(search))
  );
});

// Computed properties for active and cancelled visas, now filtered by date range and search
const filteredActiveVisas = computed(() => {
    return filterVisasByDate(filteredBySearch.value.filter(v => v.status === 'booked'));
});

const filteredCancelledVisas = computed(() => {
    return filterVisasByDate(filteredBySearch.value.filter(v => v.status === 'cancelled'));
});


// Pagination is now a simple reactive object for client-side pagination
const pagination = reactive({
  page: 1,
  pageSize: 20,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (page: number) => { pagination.page = page; },
  onUpdatePageSize: (pageSize: number) => { pagination.pageSize = pageSize; pagination.page = 1; },
});

const baseColumns: DataTableColumns<any> = [
  { title: 'Ref No', key: 'ref_no', sorter: (a, b) => a.ref_no.localeCompare(b.ref_no) },
  { title: 'Date', key: 'date', render: (row) => row.date ? new Date(row.date).toLocaleDateString() : 'N/A' },
  { title: 'Customer', key: 'customer_name', sorter: (a, b) => a.customer_name.localeCompare(b.customer_name) },
  { title: 'Agent', key: 'agent_name', sorter: (a, b) => (a.agent_name || '').localeCompare(b.agent_name || '') },
  { title: 'Visa Type', key: 'visa_type', sorter: (a, b) => (a.visa_type || '').localeCompare(b.visa_type || '') },
  { title: 'Charge', key: 'customer_charge', sorter: (a, b) => a.customer_charge - b.customer_charge },
  { title: 'Paid to Agent', key: 'agent_paid', sorter: (a, b) => a.agent_paid - b.agent_paid },
  { title: 'Profit', key: 'profit', sorter: (a, b) => a.profit - b.profit, render: row => row.profit?.toFixed(2) },
];

const columnsBooked = ref<DataTableColumns<any>>([
  ...baseColumns,
  {
    title: 'Actions',
    key: 'actions',
    render(row) {
      if (row.status !== 'booked') return null;
      return h(NSpace, { size: 'small' }, () => [
        h(PermissionWrapper, { resource: 'visa', operation: 'modify' }, {
          default: () => h(NButton, { size: 'small', onClick: () => editVisa(row) }, { default: () => 'Edit' })
        }),
        h(PermissionWrapper, { resource: 'visa', operation: 'full' }, {
          default: () => h(NButton, { size: 'small', type: 'error', onClick: () => confirmDeleteVisa(row.id, 'delete') }, { default: () => 'Delete' })
        }),
        h(PermissionWrapper, { resource: 'visa', operation: 'modify' }, {
          default: () => h(NButton, { size: 'small', type: 'warning', onClick: () => confirmCancelVisa(row) }, { default: () => 'Cancel' })
        }),
      ]);
    },
  },
  {
    title: 'Attachments',
    key: 'attachments',
    render(row) {
      return h(PermissionWrapper, { resource: 'visa', operation: 'read' }, {
        default: () => h(NButton, {
          size: 'small',
          onClick: () => openAttachmentsModal('visa', row.id),
        }, { default: () => `Manage`}),
      });
    },
  },
]);

const columnsCancelled = ref<DataTableColumns<any>>([
  ...baseColumns,
  { title: 'Paid to Customer', key: 'customer_refund_amount' },
  { title: 'Refund Mode', key: 'customer_refund_mode' },
  { title: 'Recovered from Agent', key: 'agent_recovery_amount' },
  { title: 'Recovery Mode', key: 'agent_recovery_mode' },
  {
    title: 'Actions',
    key: 'actions',
    render(row) {
      if (row.status !== 'cancelled') return null;
      return h(NSpace, { size: 'small' }, () => [
        h(PermissionWrapper, { resource: 'visa', operation: 'modify' }, {
          default: () => h(NButton, { size: 'small', onClick: () => editCancelledVisa(row) }, { default: () => 'Edit Refund' }),
        }),
        h(PermissionWrapper, { resource: 'visa', operation: 'full' }, {
          default: () => h(NButton, { size: 'small', type: 'error', onClick: () => confirmDeleteVisa(row.id, 'delete_cancelled') }, { default: () => 'Delete' }),
        }),
      ]);
    },
  },
  {
    title: 'Attachments',
    key: 'attachments',
    render(row) {
      return h(PermissionWrapper, { resource: 'visa', operation: 'read' }, {
        default: () => h(NButton, {
          size: 'small',
          onClick: () => openAttachmentsModal('visa', row.id),
        }, { default: () => `Manage` }),
      });
    },
  },
]);

const fetchData = async () => {
  loading.value = true;
  try {
    const params = {
      status: 'all',
      // We are no longer applying filters here, they are applied on the client side
      // The API call returns all visas
    };
    const res = await api.get('/api/visas', { params });
    allVisas.value = res.data;
  } catch (e) {
    message.error('Failed to load visas');
  } finally {
    loading.value = false;
  }
};

const formatDateForAPI = (timestamp: number) => new Date(timestamp).toISOString().split('T')[0];

const exportExcel = async () => {
  try {
    const params = {
      start_date: dateRange.value?.[0] ? formatDateForAPI(dateRange.value[0]) : undefined,
      end_date: dateRange.value?.[1] ? formatDateForAPI(dateRange.value[1]) : undefined,
      status: activeTab.value === 'active' ? 'booked' : 'cancelled',
      export: 'excel',
      search_query: searchQuery.value,
    };
    const response = await api.get('/api/visas', {
      params,
      responseType: 'blob',
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    const statusType = activeTab.value === 'active' ? 'Active' : 'Cancelled';
    link.setAttribute('download', `${statusType}_Visas_${new Date().toISOString().slice(0, 10)}.xlsx`);
    document.body.appendChild(link);
    link.click();
  } catch (e: any) {
    handleApiError(e);
    message.error('Excel export failed');
  }
};

const exportPDF = async () => {
  try {
    const params = {
      start_date: dateRange.value?.[0] ? formatDateForAPI(dateRange.value[0]) : undefined,
      end_date: dateRange.value?.[1] ? formatDateForAPI(dateRange.value[1]) : undefined,
      status: activeTab.value === 'active' ? 'booked' : 'cancelled',
      export: 'pdf',
      search_query: searchQuery.value,
    };
    const response = await api.get('/api/visas', {
      params,
      responseType: 'blob',
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    const statusType = activeTab.value === 'active' ? 'Active' : 'Cancelled';
    link.setAttribute('download', `${statusType}_Visas_${new Date().toISOString().slice(0, 10)}.pdf`);
    document.body.appendChild(link);
    link.click();
  } catch (e: any) {
    handleApiError(e);
    message.error('PDF export failed');
  }
};

const openAttachmentsModal = (type: string, id: number) => {
  attachmentParentType.value = type;
  attachmentParentId.value = id;
  attachmentModalVisible.value = true;
};


const generatePlaceholder = () => {
  const year = new Date().getFullYear();
  const yearVisas = (allVisas.value || []).filter(v => v.ref_no && v.ref_no.startsWith(`${year}/V/`));
  if (yearVisas.length === 0) return `${year}/V/00001`;
  const lastNum = yearVisas.reduce((max, visa) => {
    const parts = visa.ref_no.split('/');
    if (parts.length < 3) return max;
    const num = parseInt(parts[2]) || 0;
    return Math.max(max, num);
  }, 0);
  return `${year}/V/${(lastNum + 1).toString().padStart(5, '0')}`;
};

const confirmCancelVisa = (row: any) => {
  visaToCancel.value = row;
  showCancelConfirmModal.value = true;
};

const handleConfirmCancel = () => {
  showCancelConfirmModal.value = false;
  if (visaToCancel.value) {
    openCancelModal(visaToCancel.value);
  }
};

const openCancelModal = (visa: any) => {
  currentVisa.value = { ...visa };
  cancelData.value = { customer_refund_amount: visa.customer_charge, customer_refund_mode: visa.customer_payment_mode || 'wallet', agent_recovery_amount: visa.agent_paid, agent_recovery_mode: visa.agent_payment_mode || 'wallet' };
  cancelModalVisible.value = true;
};

const editCancelledVisa = (visa: any) => {
  currentVisa.value = { ...visa, date: visa.date ? new Date(visa.date).getTime() : null };
  editCancelledModalVisible.value = true;
};

const updateCancelledVisa = async () => {
  try {
    const payload = {
      id: currentVisa.value.id,
      customer_refund_amount: currentVisa.value.customer_refund_amount,
      customer_refund_mode: currentVisa.value.customer_refund_mode,
      agent_recovery_amount: currentVisa.value.agent_recovery_amount,
      agent_recovery_mode: currentVisa.value.agent_recovery_mode,
    };
    await api.patch('/api/visas', payload);
    message.success('Cancelled visa updated successfully');
    editCancelledModalVisible.value = false;
    await fetchData();
  } catch (e: any) {
    handleApiError(e);
  }
};

const confirmDeleteVisa = (id: number, action: string) => {
  visaToDeleteId.value = id;
  visaToCancel.value = { action };
  showDeleteModal.value = true;
};

const deleteVisaAndCloseModal = async () => {
  if (visaToDeleteId.value !== null && visaToCancel.value?.action) {
    try {
      await api.delete(`/api/visas?id=${visaToDeleteId.value}&action=${visaToCancel.value.action}`);
      message.success(`Visa ${visaToCancel.value.action === 'delete_cancelled' ? 'deleted with reversal' : 'deleted'} successfully`);
      await fetchData();
    } catch (e: any) {
      handleApiError(e);
    }
  }
  showDeleteModal.value = false;
  visaToDeleteId.value = null;
  visaToCancel.value = null;
};

const confirmCancel = async () => {
  if (!visaToCancel.value?.id) {
    message.error('Visa ID is missing. Cannot proceed with cancellation.')
    console.error('Missing visa ID in currentVisa:', visaToCancel.value)
    return
  }
  const payload = {
    visa_id: visaToCancel.value.id,
    customer_refund_amount: cancelData.value.customer_refund_amount ?? 0,
    customer_refund_mode: cancelData.value.customer_refund_mode ?? 'cash',
    agent_recovery_amount: cancelData.value.agent_recovery_amount ?? 0,
    agent_recovery_mode: cancelData.value.agent_recovery_mode ?? 'cash'
  }
  try {
    await api.post('/api/visas', payload, { params: { action: 'cancel' } });
    message.success('Visa cancelled successfully')
    cancelModalVisible.value = false
    await fetchData()
  } catch (e) {
    handleApiError(e)
  }
}

const handleApiError = (e: any) => {
  console.error('Full API Error:', e);
  const errorMsg = e.response?.data?.error || e.response?.data?.message || 'Operation failed';
  if (e.response?.data?.field_errors) {
    message.error('Please fix the form errors');
  } else {
    message.error(errorMsg);
  }
};

const openAddModal = () => {
  referencePlaceholder.value = generatePlaceholder();
  currentVisa.value = {
    id: null,
    customer_id: null,
    agent_id: null,
    travel_location_id: null,
    passenger_id: null,
    particular_id: null,
    ref_no: '',
    visa_type_id: null,
    customer_charge: 0,
    agent_paid: 0,
    customer_payment_mode: 'wallet',
    agent_payment_mode: 'wallet',
    date: Date.now(),
  };
  editMode.value = false;
  bulkAddMode.value = false;
  modalVisible.value = true;
};

const editVisa = (visa: any) => {
  currentVisa.value = { ...visa };
  editMode.value = true;
  modalVisible.value = true;
};

const handleFormSuccess = () => {
  if (!bulkAddMode.value) {
    modalVisible.value = false;
  }
  fetchData();
};

const openEntityModal = async (type: string, defaultName: string) => {
  entityToCreate.value = type;
  defaultEntityName.value = defaultName;
  entityModalVisible.value = true;
};

const handleEntityCreated = async (event: any) => {
  const { type, data } = event;
  await bookingFormRef.value?.fetchOptions();
  
  if (bookingFormRef.value && bookingFormRef.value.currentRecord) {
    if (type === 'passenger') {
      bookingFormRef.value.currentRecord.passenger_id = data.id;
    } else if (type === 'particular') {
      bookingFormRef.value.currentRecord.particular_id = data.id;
    } else if (type === 'travel_location') {
      bookingFormRef.value.currentRecord.travel_location_id = data.id;
    }
  }
  
  entityModalVisible.value = false;
};

const handleEntityModalClose = (val: boolean) => {
  entityModalVisible.value = val;
};

// Use a single watch to handle all data fetching triggers
watch([activeTab, searchQuery, dateRange], () => {
  // Reset pagination to page 1 whenever filters change
  pagination.page = 1;
  fetchData();
}, { deep: true, immediate: true });

onMounted(async () => {
  dateRange.value = defaultDateRange.value;
});
</script>