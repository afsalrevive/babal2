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
              style="min-width: 250px;"
            />
            
            <n-input
              v-model:value="searchQuery"
              placeholder="Search by Invoice #, Entity, or Date"
              @input="handleSearchInput"
              clearable
              style="min-width: 250px;"
            />
          </n-space>
          
          <n-button type="primary" @click="openGenerateModal">Generate Invoice</n-button>
        </n-space>
      </n-gi>
    </n-grid>

    <n-data-table 
      :columns="columns" 
      :data="filteredInvoices" 
      :pagination="pagination" 
      style="margin-top: 16px;" 
    />

    <n-modal 
      v-model:show="showGenerateModal"
      preset="card"
      :style="{
        width: '600px',
        maxHeight: '80vh',
        overflow: 'auto'
      }"
      title="Generate Invoice"
      :bordered="false"
      size="huge"
    >
      <n-card
        :style="{
          padding: '20px',
          height: '400px',
          display: 'flex',
          'flex-direction': 'column',
          'justify-content': 'space-between'
        }"
      >
        <n-space vertical :size="24">
          <n-h2 style="margin: 0">Generate Invoice</n-h2>
          
          <n-space vertical :size="16">
            <n-select
              v-if="!entitiesLoading"
              v-model:value="selectedEntityId"
              :options="entityOptions"
              placeholder="Select Entity"
              filterable
              size="large"
            />
            <n-spin :show="entitiesLoading" size="large" v-if="entitiesLoading" />
            
            <n-date-picker
              v-model:value="periodRange"
              type="daterange"
              placeholder="Select Period"
              size="large"
              style="width: 100%"
            />
          </n-space>
        </n-space>
        
        <template #footer>
          <n-space justify="end">
            <n-button size="large" @click="showGenerateModal = false">Cancel</n-button>
            <n-button
              size="large"
              type="primary"
              :disabled="!selectedEntityId || !periodRange"
              :loading="generatingInvoice"
              @click="generateInvoice"
            >
              Generate
            </n-button>
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
  NInput, NDataTable, NModal, NH2, NSpin, NTag, useMessage, NGrid, NGi 
} from 'naive-ui';
import api from '@/api';

const message = useMessage();
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
const entitiesLoading = ref(false);

// Get default date range (current month start to today)
function getDefaultDateRange() {
  const today = new Date();
  const firstDayOfMonth = new Date(today);
  firstDayOfMonth.setDate(1);
  firstDayOfMonth.setHours(0, 0, 0, 0);
  
  // Ensure today is at end of day
  const todayEnd = new Date(today);
  todayEnd.setHours(23, 59, 59, 999);
  
  return [firstDayOfMonth.getTime(), todayEnd.getTime()];
}

// Initialize date ranges
dateRange.value = getDefaultDateRange();
periodRange.value = getDefaultDateRange();

// Format date for display
function formatDateForDisplay(dateStr) {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
}

// Table columns with fixed slots
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
      return [
        h(NButton, { 
          size: 'small', 
          type: 'primary',
          onClick: () => downloadInvoice(row.id, row.invoice_number)
        }, 
        { default: () => 'Download' }
        ),
        
        h(NButton, {
          size: 'small',
          type: row.status === 'pending' ? 'success' : 'error',
          style: 'margin-left: 8px;',
          onClick: () => updateInvoiceStatus(row.id, row.status === 'pending' ? 'paid' : 'cancelled')
        }, 
        { default: () => row.status === 'pending' ? 'Mark Paid' : 'Cancel' }
        )
      ];
    }
  }
];

// Handle search input with debounce
let searchTimeout = null;
function handleSearchInput() {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(filterInvoices, 300);
}

// Filter invoices based on search query
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

// Load invoices
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

// Load entity list for dropdown
async function loadEntities() {
  entitiesLoading.value = true;
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

// Generate invoice
async function generateInvoice() {
  if (!selectedEntityId.value || !periodRange.value || periodRange.value.length !== 2) {
    message.error('Please select an entity and a valid date range');
    return;
  }
  
  generatingInvoice.value = true;
  try {
    // Convert timestamps to date strings
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
    
    const response = await api.post('/api/invoices', payload);
    
    message.success('Invoice generated successfully');
    showGenerateModal.value = false;
    loadInvoices();
  } catch (err) {
    console.error('Full error object:', err);
    
    let errorMsg = 'Unknown error occurred';
    if (err.response) {
      // Handle different error response formats
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
            // Not JSON, use as-is
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
    
    message.error(`Failed to generate invoice: ${errorMsg}`);
  } finally {
    generatingInvoice.value = false;
  }
}

// Download invoice
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

// Update invoice status
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

// Watch for changes
watch(activeEntityType, () => {
  loadInvoices();
});

watch(showGenerateModal, (newValue) => {
  if (newValue) {
    loadEntities();
  }
});

// Initialize
onMounted(() => {
  loadInvoices();
});
</script>

<style scoped>
.n-space--wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

@media (max-width: 768px) {
  .n-space--wrap {
    flex-direction: column;
    align-items: stretch !important;
  }
  
  .n-space--wrap > * {
    margin-bottom: 12px;
    width: 100%;
  }
  
  .n-date-picker, .n-input {
    width: 100% !important;
    min-width: unset !important;
  }
  
  .n-tabs {
    width: 100%;
  }
}
</style>