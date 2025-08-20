<template>
  <n-card>
    <template #header>
      <n-h2>Invoice Generator</n-h2>
    </template>

    <n-tabs v-model:value="activeEntityType" type="line" @update:value="loadInvoices">
      <n-tab-pane name="agent" tab="Agents" />
      <n-tab-pane name="customer" tab="Customers" />
      <n-tab-pane name="partner" tab="Partners" />
    </n-tabs>

    <n-grid :cols="1" :x-gap="16" :y-gap="16" responsive="screen">
      <n-gi>
        <n-space justify="space-between" align="center" wrap>
          <n-space wrap>
            <n-tabs v-model:value="selectedStatus" type="card" @update:value="loadInvoices">
              <n-tab-pane name="all" tab="All" />
              <n-tab-pane name="pending" tab="Pending" />
              <n-tab-pane name="paid" tab="Paid" />
              <n-tab-pane name="cancelled" tab="Cancelled" />
            </n-tabs>
            
            <n-date-picker
              v-model:value="dateRange"
              type="daterange"
              placeholder="Select Date Range"
              @update:value="loadInvoices"
              clearable
              class="date-picker"
            />
            
            <n-input
              v-model:value="searchQuery"
              placeholder="Search by Invoice #, Entity, or Date"
              @input="handleSearchInput"
              clearable
              class="search-input"
            />
          </n-space>
          
          <PermissionWrapper resource="invoice" operation="write">
            <n-button 
              type="primary" 
              @click="openGenerateModal" 
              class="compact-button"
            >
              Generate Invoice/Report
            </n-button>
          </PermissionWrapper>
        </n-space>
      </n-gi>
    </n-grid>

    <n-data-table 
      :columns="columns" 
      :data="filteredInvoices" 
      :pagination="pagination" 
      class="data-table" 
    />

    <n-modal 
      v-model:show="showGenerateModal"
      class="full-width-modal transaction-modal"
      title="Generate Invoice or Report"
      :bordered="false"
    >
      <n-card class="modal-card">
        <n-space vertical :size="24">
          <n-h2 class="modal-title">
            Generate Invoice or Report for 
            <span class="highlight-text">{{ activeEntityType.charAt(0).toUpperCase() + activeEntityType.slice(1) }}</span>
              &nbsp;
            <span class="highlight-text">{{ selectedEntityName }}</span>
          </n-h2>
          
          <n-space vertical :size="16" class="responsive-form-grid">
            <n-select
              v-if="!entitiesLoading"
              v-model:value="selectedEntityId"
              :options="entityOptions"
              placeholder="Select Entity"
              filterable
              size="large"
              class="entity-select"
            />
            <n-spin :show="entitiesLoading" size="large" v-if="entitiesLoading" />
            
            <n-date-picker
              v-model:value="periodRange"
              type="daterange"
              placeholder="Select Period"
              size="large"
              class="period-picker"
            />
          </n-space>
        </n-space>
        
        <template #footer>
          <n-space justify="end" class="table-controls">
            <n-button size="large" @click="showGenerateModal = false" class="cancel-btn compact-button">Cancel</n-button>

            <PermissionWrapper resource="invoice" operation="write">
              <n-button
                size="large"
                type="info"
                :disabled="!selectedEntityId || !periodRange"
                :loading="exportingReport"
                @click="exportReport('pdf')"
                class="export-btn compact-button"
              >
                Export PDF
              </n-button>
            </PermissionWrapper>

            <PermissionWrapper resource="invoice" operation="write">
              <n-button
                size="large"
                type="info"
                :disabled="!selectedEntityId || !periodRange"
                :loading="exportingReport"
                @click="exportReport('excel')"
                class="export-btn compact-button"
              >
                Export Excel
              </n-button>
            </PermissionWrapper>

            <PermissionWrapper resource="invoice" operation="modify">
              <n-button
                size="large"
                type="primary"
                :disabled="!selectedEntityId || !periodRange"
                :loading="generatingInvoice"
                @click="confirmGenerateInvoice"
                class="generate-btn compact-button"
              >
                Generate Invoice
              </n-button>
            </PermissionWrapper>
          </n-space>
        </template>
      </n-card>
    </n-modal>
  </n-card>
</template>

<script setup>
import { ref, onMounted, h, watch, computed } from 'vue';
import { 
  NButton, NCard, NTabs, NTabPane, NSpace, NSelect, NDatePicker, 
  NInput, NDataTable, NModal, NH2, NSpin, NTag, useMessage, NGrid, NGi, useDialog
} from 'naive-ui';
import api from '@/api';
import PermissionWrapper from '@/components/PermissionWrapper.vue';
import { hasPermission } from '@/utils/permissions';
import { useAuthStore } from '@/stores/auth';

const message = useMessage();
const dialog = useDialog();
const authStore = useAuthStore();
const userPermissions = computed(() => authStore.user?.perms || []);

const activeEntityType = ref('agent');
const selectedStatus = ref('all');
const dateRange = ref(null);
const searchQuery = ref('');
const invoices = ref([]);
const filteredInvoices = ref([]);
const pagination = { pageSize: 10 };
const showGenerateModal = ref(false);
const selectedEntityId = ref(null);
const periodRange = ref(null);
const entityOptions = ref([]);
const generatingInvoice = ref(false);
const exportingReport = ref(false);
const entitiesLoading = ref(false);

const selectedEntityName = computed(() => {
  const selected = entityOptions.value.find(o => o.value === selectedEntityId.value);
  return selected ? selected.label : '';
});

function getDefaultDateRange() {
  const today = new Date();
  const firstDayOfMonth = new Date(today);
  firstDayOfMonth.setDate(1);
  firstDayOfMonth.setHours(0, 0, 0, 0);
  
  const todayEnd = new Date(today);
  todayEnd.setHours(23, 59, 59, 999);
  
  return [firstDayOfMonth.getTime(), todayEnd.getTime()];
}

dateRange.value = getDefaultDateRange();
periodRange.value = getDefaultDateRange();

function formatDateForDisplay(dateStr) {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
}

const columns = [
  { 
    title: 'Invoice #', 
    key: 'invoice_number',
    render: (row) => row.invoice_number || '-'
  },
  { 
    title: 'Entity Name', 
    key: 'entity_name',
    render: (row) => row.entity_name || '-'
  },
  { 
    title: 'Period Start', 
    key: 'period_start',
    render: (row) => formatDateForDisplay(row.period_start)
  },
  { 
    title: 'Period End', 
    key: 'period_end',
    render: (row) => formatDateForDisplay(row.period_end)
  },
  {
    title: 'Status',
    key: 'status',
    render(row) {
      const statusMap = {
        pending: { type: 'warning', text: 'Pending' },
        paid: { type: 'success', text: 'Paid' },
        cancelled: { type: 'error', text: 'Cancelled' }
      };
      
      const statusInfo = statusMap[row.status] || { type: 'default', text: row.status };
      return h(NTag, { type: statusInfo.type }, 
        { default: () => statusInfo.text }
      );
    }
  },
  { 
    title: 'Generated Date', 
    key: 'generated_date',
    render: (row) => formatDateForDisplay(row.generated_date)
  },
  {
    title: 'Actions',
    key: 'actions',
    render(row) {
      const buttons = [];

      // Download button visible for 'read' and above
      if (hasPermission(userPermissions.value, 'invoice', 'read')) {
        buttons.push(
          h(NButton, { 
            size: 'small', 
            type: 'primary',
            class: 'compact-button',
            onClick: () => downloadInvoice(row.id, row.invoice_number)
          }, 
          { default: () => 'Download' }
          )
        );
      }
      
      // Mark Paid/Cancel button visible for 'full' access
      if (hasPermission(userPermissions.value, 'invoice', 'full')) {
        buttons.push(
          h(NButton, {
            size: 'small',
            type: row.status === 'pending' ? 'success' : 'error',
            class: 'action-btn compact-button',
            onClick: () => confirmStatusUpdate(row.id, row.status)
          }, 
          { default: () => row.status === 'pending' ? 'Mark Paid' : 'Cancel' }
          )
        );
      }

      // Delete button visible for 'full' access
      if (hasPermission(userPermissions.value, 'invoice', 'full')) {
        buttons.push(
          h(NButton, {
            size: 'small',
            type: 'error',
            class: 'action-btn compact-button',
            onClick: () => deleteInvoice(row.id, row.invoice_number)
          }, 
          { default: () => 'Delete' }
          )
        );
      }

      return buttons;
    }
  }
];

let searchTimeout = null;
function handleSearchInput() {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(filterInvoices, 300);
}

function filterInvoices() {
  if (!searchQuery.value) {
    filteredInvoices.value = [...invoices.value];
    return;
  }
  
  const query = searchQuery.value.toLowerCase();
  
  filteredInvoices.value = invoices.value.filter(invoice => {
    return (
      (invoice.invoice_number && invoice.invoice_number.toLowerCase().includes(query)) ||
      (invoice.entity_name && invoice.entity_name.toLowerCase().includes(query)) ||
      (invoice.period_start && formatDateForDisplay(invoice.period_start).toLowerCase().includes(query)) ||
      (invoice.period_end && formatDateForDisplay(invoice.period_end).toLowerCase().includes(query)) ||
      (invoice.generated_date && formatDateForDisplay(invoice.generated_date).toLowerCase().includes(query))
    );
  });
}

async function loadInvoices() {
  try {
    const response = await api.get('/api/invoices', {
      params: {
        entity_type: activeEntityType.value,
        status: selectedStatus.value === 'all' ? undefined : selectedStatus.value,
        start_date: dateRange.value?.[0] ? new Date(dateRange.value[0]).toISOString().split('T')[0] : undefined,
        end_date: dateRange.value?.[1] ? new Date(dateRange.value[1]).toISOString().split('T')[0] : undefined
      }
    });
    
    invoices.value = Array.isArray(response.data) ? response.data : [];
    filterInvoices();
  } catch (err) {
    console.error('Error loading invoices:', err);
    message.error('Failed to load invoices');
  }
}

async function loadEntities() {
  entitiesLoading.value = true;
  selectedEntityId.value = null;
  entityOptions.value = [];
  try {
    const res = await api.get(`/api/manage/${activeEntityType.value}`);
    if (res.data && Array.isArray(res.data)) {
      entityOptions.value = res.data.map(e => ({
        label: e.name,
        value: e.id
      }));
    } else {
      console.error('API response is not an array:', res.data);
      message.error('Failed to load entities: Invalid data format');
    }
  } catch (err) {
    console.error('Error loading entities:', err);
    entityOptions.value = [];
    if (err.response) {
      message.error(`Failed to load entities: ${err.response.data?.message || 'Server error'}`);
    } else {
      message.error('Failed to load entities. Check network connection');
    }
  } finally {
    entitiesLoading.value = false;
  }
}

function openGenerateModal() {
  selectedEntityId.value = null;
  periodRange.value = getDefaultDateRange();
  loadEntities();
  showGenerateModal.value = true;
}

function confirmGenerateInvoice() {
  if (!selectedEntityId.value || !periodRange.value || periodRange.value.length !== 2) {
    message.error('Please select an entity and a valid date range');
    return;
  }

  const selectedEntity = entityOptions.value.find(o => o.value === selectedEntityId.value);
  const entityName = selectedEntity ? selectedEntity.label : 'Unknown Entity';
  
  const formattedPeriodStart = formatDateForDisplay(new Date(periodRange.value[0]));
  const formattedPeriodEnd = formatDateForDisplay(new Date(periodRange.value[1]));

  dialog.warning({
    title: 'Confirm Invoice Generation',
    content: `Do you want to continue to generate an invoice for ${entityName} for the period from ${formattedPeriodStart} to ${formattedPeriodEnd}?`,
    positiveText: 'Generate Invoice',
    negativeText: 'Cancel',
    onPositiveClick: () => {
      generateInvoice();
    }
  });
}

async function generateInvoice() {
  generatingInvoice.value = true;
  try {
    const formatDate = (ts) => {
      const date = new Date(ts);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    };
    
    const payload = {
      entity_type: activeEntityType.value,
      entity_id: selectedEntityId.value,
      period_start: formatDate(periodRange.value[0]),
      period_end: formatDate(periodRange.value[1])
    };
    
    await api.post('/api/invoices', payload);
    
    message.success('Invoice generated and saved successfully');
    showGenerateModal.value = false;
    loadInvoices();
  } catch (err) {
    console.error('Full error object:', err);
    
    let errorMsg = 'Unknown error occurred';
    if (err.response) {
      if (typeof err.response.data === 'string') {
        errorMsg = err.response.data;
      } else if (err.response.data?.message) {
        errorMsg = err.response.data.message;
      } else if (err.response.data?.error) {
        errorMsg = err.response.data.error;
      } else if (err.response.data instanceof Blob) {
        try {
          const text = await err.response.data.text();
          errorMsg = text;
          try {
            const json = JSON.parse(text);
            errorMsg = json.message || json.error || text;
          } catch {
          }
        } catch (blobErr) {
          errorMsg = 'Failed to parse error response';
        }
      } else {
        errorMsg = 'Server error occurred';
      }
    } else if (err.request) {
      errorMsg = 'No response from server. Check network connection.';
    } else {
      errorMsg = err.message || 'Unknown error occurred';
    }

    dialog.error({
      title: 'Failed to Generate Invoice',
      content: errorMsg,
      positiveText: 'OK',
    });
  } finally {
    generatingInvoice.value = false;
  }
}

async function exportReport(exportType) {
  if (!selectedEntityId.value || !periodRange.value || periodRange.value.length !== 2) {
    message.error('Please select an entity and a valid date range');
    return;
  }
  
  exportingReport.value = true;
  try {
    const formatDate = (ts) => {
      const date = new Date(ts);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    };

    const payload = {
      entity_type: activeEntityType.value,
      entity_id: selectedEntityId.value,
      period_start: formatDate(periodRange.value[0]),
      period_end: formatDate(periodRange.value[1]),
      export_type: exportType
    };
    
    const res = await api.post('/api/invoices/export', payload, { responseType: 'blob' });
    
    const mimeTypeMap = {
      'pdf': 'application/pdf',
      'excel': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    };
    
    const blob = new Blob([res.data], { type: mimeTypeMap[exportType] });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const extension = exportType === 'pdf' ? '.pdf' : '.xlsx';
    a.download = `report_${activeEntityType.value}_${payload.period_start}_to_${payload.period_end}${extension}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    
    message.success(`${exportType.toUpperCase()} report exported successfully`);
  } catch (err) {
    console.error('Error exporting report:', err);
    let errorMsg = 'Failed to export report';
    if (err.response) {
      if (err.response.data instanceof Blob) {
        try {
          const text = await err.response.data.text();
          errorMsg = text;
        } catch {
          errorMsg = 'Invalid file content';
        }
      } else {
        errorMsg = err.response.data?.message || err.response.data?.error || 'Server error';
      }
    }
    message.error(`${errorMsg}`);
  } finally {
    exportingReport.value = false;
  }
}

async function downloadInvoice(id, invoiceNumber) {
  try {
    const res = await api.get(`/api/invoices/${id}/download`, { responseType: 'blob' });
    
    const blob = new Blob([res.data], { type: 'application/pdf' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${invoiceNumber}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    console.error('Error downloading invoice:', err);
    
    let errorMsg = 'Failed to download invoice';
    if (err.response) {
      if (err.response.data instanceof Blob) {
        try {
          const text = await err.response.data.text();
          errorMsg = text;
        } catch {
          errorMsg = 'Invalid PDF content';
        }
      } else {
        errorMsg = err.response.data?.message || err.response.data?.error || 'Server error';
      }
    }
    
    message.error(`${errorMsg}`);
  }
}

function confirmStatusUpdate(id, currentStatus) {
  const newStatus = currentStatus === 'pending' ? 'paid' : 'cancelled';
  const actionText = newStatus === 'paid' ? 'mark as Paid' : 'cancel';
  const confirmationContent = `Are you sure you want to ${actionText} this invoice?`;

  dialog.warning({
    title: 'Confirm Status Change',
    content: confirmationContent,
    positiveText: 'Confirm',
    negativeText: 'Cancel',
    onPositiveClick: () => {
      updateInvoiceStatus(id, newStatus);
    }
  });
}

async function updateInvoiceStatus(id, status) {
  try {
    await api.patch(`/api/invoices/${id}/status`, { status });
    message.success(`Invoice status updated to ${status}`);
    loadInvoices();
  } catch (err) {
    console.error('Error updating status:', err);
    
    let errorMsg = 'Failed to update status';
    if (err.response) {
      errorMsg = err.response.data?.message || err.response.data?.error || 'Server error';
    }
    
    message.error(`${errorMsg}`);
  }
}

function deleteInvoice(id, invoiceNumber) {
  dialog.warning({
    title: 'Confirm Deletion',
    content: `Are you sure you want to delete invoice "${invoiceNumber}"? This action cannot be undone.`,
    positiveText: 'Delete',
    negativeText: 'Cancel',
    onPositiveClick: async () => {
      try {
        await api.delete(`/api/invoices/${id}`);
        message.success('Invoice deleted successfully');
        loadInvoices();
      } catch (err) {
        console.error('Error deleting invoice:', err);
        let errorMsg = 'Failed to delete invoice';
        if (err.response) {
          errorMsg = err.response.data?.message || err.response.data?.error || 'Server error';
        }
        message.error(`${errorMsg}`);
      }
    }
  });
}

watch(activeEntityType, () => {
  loadInvoices();
});

watch(showGenerateModal, (newValue) => {
  if (newValue) {
    loadEntities();
  }
});

onMounted(() => {
  loadInvoices();
});
</script>

<style scoped lang="scss">
@use '@/styles/theme' as *;

// Use existing global styles for modal
.full-width-modal {
  @extend .full-width-modal;
}

.transaction-modal {
  @extend .transaction-modal;
}

.modal-card {
  @extend .modal-card;
}

// Use existing global styles for buttons
.compact-button {
  @extend .compact-button;
  min-width: 180px; // increase as needed
  padding-left: 16px;
  padding-right: 16px;
}

// Use existing global styles for table controls
.table-controls {
  @extend .table-controls;
}

// Use existing global styles for responsive form grid
.responsive-form-grid {
  @extend .responsive-form-grid;
}

// Additional component-specific styles
.date-picker,
.search-input {
  min-width: 250px;
}

.data-table {
  margin-top: 16px;
  
  :deep(.n-data-table-th) {
    background-color: var(--card-bg);
    font-weight: 600;
  }
}

.action-btn {
  margin-left: 8px;
}

// Modal title style
.modal-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text-color);
}

// Differentiating the "Generate Invoice" button
.generate-btn {
  background-color: #00ba38; // A distinct color
  border-color: #00ba63;
  font-weight: bold;
  letter-spacing: 0.5px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;

  &:hover {
    background-color: #007bb5;
    transform: translateY(-2px);
    box-shadow: 0 6px 8px rgba(0, 0, 0, 0.15);
  }

  &.n-button--disabled {
    background-color: #ccc !important;
    border-color: #ccc !important;
    box-shadow: none;
    cursor: not-allowed;
  }
}

// Style for highlighted text in the modal title
.highlight-text {
  color: #a4af3f; // A distinct blue color
  font-weight: 800;
  font-family: 'Georgia', serif;
}

// Responsive adjustments
@media (max-width: 768px) {
  .date-picker,
  .search-input {
    min-width: 100%;
    margin-bottom: 12px;
  }
  
  .n-space--wrap {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>