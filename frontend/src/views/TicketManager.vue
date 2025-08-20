<template>
  <n-card>
    <template #header>
      <n-h2>Ticket Manager</n-h2>
    </template>

    <n-tabs v-model:value="activeTab" type="line" animated @update:value="onTabChange">
      <n-tab-pane name="active" tab="Active Tickets" />
      <n-tab-pane name="cancelled" tab="Cancelled Tickets" />
    </n-tabs>

    <n-space justify="space-between" wrap class="table-controls">
      <n-space>
        <n-input
          v-model:value="searchQuery"
          placeholder="Search tickets"
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
      <PermissionWrapper resource="ticket" operation="write">
        <n-button type="primary" @click="openAddModal">Book Ticket</n-button>
      </PermissionWrapper>
    </n-space>

    <n-data-table
      :columns="activeTab === 'active' ? columnsBooked : columnsCancelled"
      :data="allTickets"
      :loading="loading"
      :pagination="pagination"
      :remote="true"
      striped
      style="margin-top: 16px;"
      @update:sorter="handleSorterChange"
      @update:page="handlePageChange"
      @update:page-size="handlePageSizeChange"
    />

    <n-modal v-model:show="modalVisible" class="full-width-modal">
      <n-card class="modal-card">
        <n-h2 class="modal-title">{{ editMode ? 'Edit Ticket' : 'Book Ticket' }}</n-h2>
        <BookingForm
          v-show="modalVisible"
          :edit-mode="editMode"
          :form-data="currentTicket"
          :reference-number="referenceNumber"
          :is-visa-management="false"
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
        <n-h2 class="modal-title">Cancel Ticket #{{ currentTicket.ref_no }}</n-h2>
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
          <n-divider v-if="currentTicket.agent_id" />
          <div class="recovery-section" v-if="currentTicket.agent_id">
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
            <PermissionWrapper resource="ticket" operation="modify">
              <n-button type="error" @click="confirmCancel">Confirm Cancellation</n-button>
            </PermissionWrapper>
          </n-space>
        </n-form>
      </n-card>
    </n-modal>
    
    <n-modal v-model:show="editCancelledModalVisible" class="transaction-modal">
      <n-card class="modal-card">
        <n-h2 class="modal-title">Edit Cancelled Ticket #{{ currentTicket.ref_no }}</n-h2>
        <n-form class="responsive-form-grid">
          <div class="refund-section">
            <n-h3>Customer Refund</n-h3>
            <n-form-item label="Refund Amount">
              <n-input-number v-model:value="currentTicket.customer_refund_amount" :min="0" />
            </n-form-item>
            <n-form-item label="Refund Mode">
              <n-select
                v-model:value="currentTicket.customer_refund_mode"
                :options="paymentModeOptions"
                placeholder="Select Refund Mode"
              />
            </n-form-item>
          </div>
          <n-divider v-if="currentTicket.agent_id" />
          <div class="recovery-section" v-if="currentTicket.agent_id">
            <n-h3>Agent Recovery</n-h3>
            <n-form-item label="Recovery Amount">
              <n-input-number v-model:value="currentTicket.agent_recovery_amount" :min="0" />
            </n-form-item>
            <n-form-item label="Recovery Mode">
              <n-select
                v-model:value="currentTicket.agent_recovery_mode"
                :options="paymentModeOptions"
                placeholder="Select Recovery Mode"
              />
            </n-form-item>
          </div>
          <n-space class="action-buttons" justify="end">
            <n-button @click="editCancelledModalVisible = false">Cancel</n-button>
            <PermissionWrapper resource="ticket" operation="modify">
              <n-button type="primary" @click="updateCancelledTicket">Update</n-button>
            </PermissionWrapper>
          </n-space>
        </n-form>
      </n-card>
    </n-modal>

    <n-modal v-model:show="showDeleteModal" :mask-closable="false" preset="dialog" title="Confirm Deletion">
      <n-alert type="warning">
        Are you sure you want to delete this ticket? This action cannot be undone.
      </n-alert>
      <template #action>
        <n-space>
          <n-button @click="showDeleteModal = false">Cancel</n-button>
          <n-button type="error" @click="deleteTicketAndCloseModal">Delete</n-button>
        </n-space>
      </template>
    </n-modal>
    <n-modal v-model:show="showCancelConfirmModal" :mask-closable="false" preset="dialog" title="Confirm Cancellation">
      <n-alert type="warning">
        Are you sure you want to cancel this ticket? This will create a refund/recovery transaction.
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
      :form-data="{ name: defaultEntityName, customer_id: currentTicket.customer_id }"
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
import { ref, computed, onMounted, h, reactive, watch, nextTick } from 'vue';
import { useMessage, NButton, NSpace, NForm, NFormItem, NInputNumber, NInput, NSelect, NDivider, NAlert, NModal, NCard, NH3, NIcon, NH2, NSwitch, NDataTable } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import api from '@/api';
import PermissionWrapper from '@/components/PermissionWrapper.vue';
import { DocumentTextOutline } from '@vicons/ionicons5';
import EntityFormModal from './EntityFormModal.vue';
import AttachmentModal from './AttachmentModal.vue';
import BookingForm from './BookingForm.vue';
import { debounce } from 'lodash';

// Correct type definition for SortOrder
type SortOrder = 'ascend' | 'descend' | false;

const message = useMessage();
const bookingFormRef = ref<any>(null);

const entityModalVisible = ref(false);
const entityToCreate = ref('');
const defaultEntityName = ref('');

const activeTab = ref('active');
const searchQuery = ref('');
const allTickets = ref<any[]>([]);
const loading = ref(false);
const modalVisible = ref(false);
const cancelModalVisible = ref(false);
const editCancelledModalVisible = ref(false);
const editMode = ref(false);

const showDeleteModal = ref(false);
const showCancelConfirmModal = ref(false);
const ticketToDeleteId = ref<number | null>(null);
const ticketToCancel = ref<any>(null);

const dateRange = ref<[number, number] | null>(null);
const defaultDateRange = computed(() => {
  const end = Date.now();
  const start = end - 7 * 24 * 60 * 60 * 1000;
  return [start, end] as [number, number];
});

const attachmentModalVisible = ref(false);
const attachmentParentType = ref('');
const attachmentParentId = ref(null);

const ticketTypeOptions = ref<any[]>([]);

const currentTicket = ref<any>({
  id: null,
  customer_id: null,
  agent_id: null,
  travel_location_id: null,
  passenger_id: null,
  particular_id: null,
  ref_no: '',
  ticket_type_id: null, // New field for ticket type
  customer_charge: 0,
  agent_paid: 0,
  description: '',
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
  if (editMode.value && currentTicket.value.ref_no) {
    return currentTicket.value.ref_no;
  }
  return referencePlaceholder.value || 'Generating...';
});

const pagination = reactive({
  page: 1,
  pageSize: 20,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  itemCount: 0,
  onUpdatePage: (page: number) => {
    pagination.page = page;
    fetchData();
  },
  onUpdatePageSize: (pageSize: number) => {
    pagination.pageSize = pageSize;
    pagination.page = 1;
    fetchData();
  },
});

const sortKey = ref<string | null>(null);
const sortOrder = ref<SortOrder | false>(false);


const fetchData = async () => {
  loading.value = true;
  try {
    const params = {
      status: activeTab.value === 'active' ? 'booked' : 'cancelled',
      page: pagination.page,
      per_page: pagination.pageSize,
      search_query: searchQuery.value,
      start_date: dateRange.value?.[0] ? formatDateForAPI(dateRange.value[0]) : undefined,
      end_date: dateRange.value?.[1] ? formatDateForAPI(dateRange.value[1]) : undefined,
      sort_by: sortKey.value,
      sort_order: sortOrder.value,
    };
    
    const res = await api.get('/api/tickets', { params });
    allTickets.value = res.data.data;
    pagination.itemCount = res.data.total;
  } catch (e) {
    message.error('Failed to load tickets');
  } finally {
    loading.value = false;
  }
};

const handleSorterChange = (sorter: { columnKey: string, order: SortOrder } | null) => {
  sortKey.value = sorter?.columnKey ?? null;
  sortOrder.value = sorter?.order ?? false;
  pagination.page = 1;
  fetchData();
};

const handlePageChange = (page: number) => {
    pagination.page = page;
    fetchData();
};

const handlePageSizeChange = (pageSize: number) => {
    pagination.pageSize = pageSize;
    pagination.page = 1;
    fetchData();
};

const onTabChange = (tabName: string) => {
  activeTab.value = tabName;
  pagination.page = 1;
  fetchData();
};

const baseColumns: DataTableColumns<any> = [
  { title: 'Ref No', key: 'ref_no', sorter: true, sortOrder: sortKey.value === 'ref_no' ? sortOrder.value : false },
  {
    title: 'Date',
    key: 'date',
    render: (row) => row.date ? new Date(row.date).toLocaleDateString() : 'N/A',
    sorter: true,
    sortOrder: sortKey.value === 'date' ? sortOrder.value : false
  },
  { title: 'Customer', key: 'customer_name', sorter: true, sortOrder: sortKey.value === 'customer_name' ? sortOrder.value : false },
  { title: 'Passenger', key: 'passenger_name', sorter: true, sortOrder: sortKey.value === 'passenger_name' ? sortOrder.value : false },
  { title: 'Ticket Type', key: 'ticket_type_name', sorter: true, sortOrder: sortKey.value === 'ticket_type_name' ? sortOrder.value : false },
  { title: 'Agent', key: 'agent_name', sorter: true, sortOrder: sortKey.value === 'agent_name' ? sortOrder.value : false },
  { title: 'Paid to Agent', key: 'agent_paid', sorter: true, sortOrder: sortKey.value === 'agent_paid' ? sortOrder.value : false },
  { title: 'Customer Charge', key: 'customer_charge', sorter: true, sortOrder: sortKey.value === 'customer_charge' ? sortOrder.value : false },
  { title: 'Profit', key: 'profit', sorter: true, sortOrder: sortKey.value === 'profit' ? sortOrder.value : false, render: row => row.profit?.toFixed(2) },
  { title: 'Description', key: 'description' }
];

const columnsBooked = ref<DataTableColumns<any>>([
  ...baseColumns,
  {
    title: 'Actions',
    key: 'actions',
    render(row) {
      if (row.status !== 'booked') return null;
      return h(NSpace, { size: 'small' }, () => [
        h(PermissionWrapper, { resource: 'ticket', operation: 'modify' }, {
          default: () => h(NButton, { size: 'small', onClick: () => editTicket(row) }, { default: () => 'Edit' })
        }),
        h(PermissionWrapper, { resource: 'ticket', operation: 'full' }, {
          default: () => h(NButton, { size: 'small', type: 'error', onClick: () => confirmDeleteTicket(row.id, 'delete') }, { default: () => 'Delete' })
        }),
        h(PermissionWrapper, { resource: 'ticket', operation: 'modify' }, {
          default: () => h(NButton, { size: 'small', type: 'warning', onClick: () => confirmCancelTicket(row) }, { default: () => 'Cancel' })
        }),
      ]);
    },
  },
  {
    title: 'Attachments',
    key: 'attachments',
    render(row) {
      return h(PermissionWrapper, { resource: 'ticket', operation: 'read' }, {
        default: () => h(NButton, {
          size: 'small',
          onClick: () => openAttachmentsModal('ticket', row.id),
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
        h(PermissionWrapper, { resource: 'ticket', operation: 'modify' }, {
          default: () => h(NButton, { size: 'small', onClick: () => editCancelledTicket(row) }, { default: () => 'Edit Refund' }),
        }),
        h(PermissionWrapper, { resource: 'ticket', operation: 'full' }, {
          default: () => h(NButton, { size: 'small', type: 'error', onClick: () => confirmDeleteTicket(row.id, 'delete_cancelled') }, { default: () => 'Delete' }),
        }),
      ]);
    },
  },
  {
    title: 'Attachments',
    key: 'attachments',
    render(row) {
      return h(PermissionWrapper, { resource: 'ticket', operation: 'read' }, {
        default: () => h(NButton, {
          size: 'small',
          onClick: () => openAttachmentsModal('ticket', row.id),
        }, { default: () => `Manage` }),
      });
    },
  },
]);

const fetchTicketTypeOptions = async () => {
  try {
    const res = await api.get('/api/manage/ticket_type');
    ticketTypeOptions.value = res.data.map((tt: any) => ({
      label: tt.name,
      value: tt.id
    }));
  } catch (e) {
    message.error('Failed to load ticket types');
  }
};

const debouncedFetchData = debounce(fetchData, 500);

const formatDateForAPI = (timestamp: number) => {
  const date = new Date(timestamp);
  return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}`;
};

const exportExcel = async () => {
  try {
    const params = {
      start_date: dateRange.value?.[0] ? formatDateForAPI(dateRange.value[0]) : undefined,
      end_date: dateRange.value?.[1] ? formatDateForAPI(dateRange.value[1]) : undefined,
      status: activeTab.value === 'active' ? 'booked' : 'cancelled',
      export: 'excel',
      search_query: searchQuery.value,
    };
    
    if (pagination.itemCount === 0) {
        message.info('No data available to export.');
        return;
    }

    const response = await api.get('/api/tickets', {
      params,
      responseType: 'blob',
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    const statusType = activeTab.value === 'active' ? 'Active' : 'Cancelled';
    link.setAttribute('download', `${statusType}_Tickets_${new Date().toISOString().slice(0, 10)}.xlsx`);
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
    
    if (pagination.itemCount === 0) {
        message.info('No data available to export.');
        return;
    }

    const response = await api.get('/api/tickets', {
      params,
      responseType: 'blob',
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    const statusType = activeTab.value === 'active' ? 'Active' : 'Cancelled';
    link.setAttribute('download', `${statusType}_Tickets_${new Date().toISOString().slice(0, 10)}.pdf`);
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


const generatePlaceholder = async () => {
  try {
    const { data } = await api.get('/api/tickets/next_ref_no');
    return data.ref_no;
  } catch (e) {
    message.error('Failed to generate reference number.');
    return 'Error...';
  }
};

const confirmCancelTicket = (row: any) => {
  ticketToCancel.value = row;
  showCancelConfirmModal.value = true;
};

const handleConfirmCancel = () => {
  showCancelConfirmModal.value = false;
  if (ticketToCancel.value) {
    openCancelModal(ticketToCancel.value);
  }
};

const openCancelModal = (ticket: any) => {
  currentTicket.value = { ...ticket };
  cancelData.value = { customer_refund_amount: ticket.customer_charge, customer_refund_mode: ticket.customer_payment_mode || 'wallet', agent_recovery_amount: ticket.agent_paid, agent_recovery_mode: ticket.agent_payment_mode || 'wallet' };
  cancelModalVisible.value = true;
};

const editCancelledTicket = (ticket: any) => {
  currentTicket.value = { ...ticket, date: ticket.date ? new Date(ticket.date).getTime() : null };
  editCancelledModalVisible.value = true;
};

const updateCancelledTicket = async () => {
  try {
    const payload = {
      id: currentTicket.value.id,
      customer_refund_amount: currentTicket.value.customer_refund_amount,
      customer_refund_mode: currentTicket.value.customer_refund_mode,
      agent_recovery_amount: currentTicket.value.agent_recovery_amount,
      agent_recovery_mode: currentTicket.value.agent_recovery_mode,
    };
    await api.patch('/api/tickets', payload);
    message.success('Cancelled ticket updated successfully');
    editCancelledModalVisible.value = false;
    await fetchData();
  } catch (e: any) {
    handleApiError(e);
  }
};

const confirmDeleteTicket = (id: number, action: string) => {
  ticketToDeleteId.value = id;
  ticketToCancel.value = { action };
  showDeleteModal.value = true;
};

const deleteTicketAndCloseModal = async () => {
  if (ticketToDeleteId.value !== null && ticketToCancel.value?.action) {
    try {
      await api.delete(`/api/tickets?id=${ticketToDeleteId.value}&action=${ticketToCancel.value.action}`);
      message.success(`Ticket ${ticketToCancel.value.action === 'delete_cancelled' ? 'deleted with reversal' : 'deleted'} successfully`);
      await fetchData();
    } catch (e: any) {
      handleApiError(e);
    }
  }
  showDeleteModal.value = false;
  ticketToDeleteId.value = null;
  ticketToCancel.value = null;
};

const confirmCancel = async () => {
  if (!ticketToCancel.value?.id) {
    message.error('Ticket ID is missing. Cannot proceed with cancellation.')
    console.error('Missing ticket ID in currentTicket:', ticketToCancel.value)
    return
  }
  const payload = {
    ticket_id: ticketToCancel.value.id,
    customer_refund_amount: cancelData.value.customer_refund_amount ?? 0,
    customer_refund_mode: cancelData.value.customer_refund_mode ?? 'cash',
    agent_recovery_amount: cancelData.value.agent_recovery_amount ?? 0,
    agent_recovery_mode: cancelData.value.agent_recovery_mode ?? 'cash'
  }
  try {
    await api.post('/api/tickets', payload, { params: { action: 'cancel' } });
    message.success('Ticket cancelled successfully')
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

const openAddModal = async () => {
  referencePlaceholder.value = await generatePlaceholder();
  currentTicket.value = {
    id: null,
    customer_id: null,
    agent_id: null,
    travel_location_id: null,
    passenger_id: null,
    particular_id: null,
    ref_no: '',
    ticket_type_id: null,
    customer_charge: 0,
    agent_paid: 0,
    description: '',
    customer_payment_mode: 'wallet',
    agent_payment_mode: 'wallet',
    date: Date.now(),
  };
  editMode.value = false;
  bulkAddMode.value = false;
  modalVisible.value = true;
  await nextTick();
  bookingFormRef.value?.fetchOptions();
};

const editTicket = (ticket: any) => {
  currentTicket.value = { ...ticket, date: ticket.date ? new Date(ticket.date).getTime() : null };
  editMode.value = true;
  modalVisible.value = true;
  nextTick(() => {
    bookingFormRef.value?.fetchOptions();
  });
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
  
  // Directly set the ID and let the child component fetch its own options
  if (bookingFormRef.value && bookingFormRef.value.currentRecord) {
    if (type === 'passenger') {
      bookingFormRef.value.currentRecord.passenger_id = data.id;
    } else if (type === 'particular') {
      bookingFormRef.value.currentRecord.particular_id = data.id;
    } else if (type === 'travel_location') {
      bookingFormRef.value.currentRecord.travel_location_id = data.id;
    } else if (type === 'ticket_type') {
      bookingFormRef.value.currentRecord.ticket_type_id = data.id;
    }
  }

  // Tell the child component to re-fetch its options
  await bookingFormRef.value?.fetchOptions();

  entityModalVisible.value = false;
};

const handleEntityModalClose = (val: boolean) => {
  entityModalVisible.value = val;
};

watch([activeTab, dateRange], () => {
  pagination.page = 1;
  fetchData();
}, { deep: true });

watch(searchQuery, () => {
  pagination.page = 1;
  debouncedFetchData();
});

onMounted(async () => {
  dateRange.value = defaultDateRange.value;
  fetchTicketTypeOptions();
  fetchData();
});
</script>