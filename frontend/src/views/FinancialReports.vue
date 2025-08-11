<template>
  <n-card>
    <template #header>
      <n-h2>Financial Reports</n-h2>
    </template>
    <n-space vertical>
      <n-space align="center" justify="space-between" class="report-controls">
        <n-date-picker
          v-model:value="dateRange"
          type="daterange"
          clearable
          style="max-width: 300px;"
        />
        <n-button-group>
            <n-button type="primary" @click="fetchCompanyBalanceReport" :loading="loading">
                <template #icon><n-icon><RefreshOutline /></n-icon></template>
                Refresh
            </n-button>
            <n-button @click="exportReport('excel')" type="primary" secondary :loading="loading">
                <template #icon><n-icon><DocumentTextOutline /></n-icon></template>
                Excel
            </n-button>
            <n-button @click="exportReport('pdf')" type="primary" secondary :loading="loading">
                <template #icon><n-icon><DocumentTextOutline /></n-icon></template>
                PDF
            </n-button>
        </n-button-group>
      </n-space>

      <n-divider />

      <n-tabs v-model:value="activeTab" type="line" animated @update:value="fetchCompanyBalanceReport">
        <n-tab-pane name="cash" tab="Cash">
          <n-alert title="Current Balance" type="info" style="margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <n-h3 style="margin: 0;">Opening Balance: {{ startingBalance.toFixed(2) }}</n-h3>
              <n-h3 style="margin: 0;">Ending Balance: {{ endingBalance.toFixed(2) }}</n-h3>
            </div>
          </n-alert>

          <n-data-table
            :columns="columns"
            :data="entries"
            :loading="loading"
            :pagination="pagination"
            striped
          />
        </n-tab-pane>
        <n-tab-pane name="online" tab="Online">
          <n-alert title="Current Balance" type="info" style="margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <n-h3 style="margin: 0;">Opening Balance: {{ startingBalance.toFixed(2) }}</n-h3>
              <n-h3 style="margin: 0;">Ending Balance: {{ endingBalance.toFixed(2) }}</n-h3>
            </div>
          </n-alert>
          <n-data-table
            :columns="columns"
            :data="entries"
            :loading="loading"
            :pagination="pagination"
            striped
          />
        </n-tab-pane>
      </n-tabs>
    </n-space>
  </n-card>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, h, watch } from 'vue';
import { useMessage, NCard, NH2, NH3, NSpace, NDatePicker, NButton, NIcon, NDivider, NTabs, NTabPane, NDataTable, NAlert, NButtonGroup } from 'naive-ui';
import { RefreshOutline, DocumentTextOutline } from '@vicons/ionicons5';
import type { DataTableColumns } from 'naive-ui';
import api from '@/api';

const message = useMessage();
const loading = ref(false);

const activeTab = ref('cash');
const dateRange = ref<[number, number] | null>(null);

const entries = ref([]);
const startingBalance = ref(0);
const endingBalance = ref(0);


const columns: DataTableColumns = [
  { 
    title: "Ref No", 
    key: "Ref No",
    sorter: (a, b) => a["Ref No"] > b["Ref No"] ? 1 : -1
  },
  { 
    title: "Date", 
    key: "Date",
    sorter: (a, b) => new Date(a["Date"]).getTime() - new Date(b["Date"]).getTime()
  },
  { title: "Transaction Type", key: "Transaction Type" },
  { title: "Action", key: "Action" },
  { 
      title: "Credit amount", 
      key: "Credit amount", 
      render: (row) => h('span', {}, { default: () => row['Credit amount'] > 0 ? `${row['Credit amount'].toFixed(2)}` : '-' }) 
  },
  { 
      title: "Debited amount", 
      key: "Debited amount", 
      render: (row) => h('span', {}, { default: () => row['Debited amount'] > 0 ? `${row['Debited amount'].toFixed(2)}` : '-' }) 
  },
  { title: "Balance", key: "Balance", render: (row) => h('span', {}, { default: () => row['Balance'].toFixed(2) }) }
];

const pagination = reactive({
  page: 1,
  pageSize: 10,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (page: number) => { pagination.page = page; },
  onUpdatePageSize: (pageSize: number) => { pagination.pageSize = pageSize; pagination.page = 1; },
});

const formatDateForAPI = (timestamp: number) => {
  // FIX: Use local date components to prevent timezone issues
  const date = new Date(timestamp);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const fetchCompanyBalanceReport = async () => {
  if (!dateRange.value) {
    message.warning('Please select a date range.');
    return;
  }
  loading.value = true;
  try {
    const params = {
        start_date: formatDateForAPI(dateRange.value[0]),
        end_date: formatDateForAPI(dateRange.value[1]),
    };
    const response = await api.get(`/api/reports/company_balance/${activeTab.value}`, { params });
    entries.value = response.data.entries;
    startingBalance.value = response.data.starting_balance;
    endingBalance.value = response.data.ending_balance;
  } catch (e: any) {
    message.error('Failed to fetch report: ' + (e.response?.data?.error || e.message));
  } finally {
    loading.value = false;
  }
};

const exportReport = async (format: 'excel' | 'pdf') => {
    if (!dateRange.value) {
        message.warning('Please select a date range.');
        return;
    }
    loading.value = true;
    try {
        const params = {
            start_date: formatDateForAPI(dateRange.value[0]),
            end_date: formatDateForAPI(dateRange.value[1]),
            export: format
        };
        const response = await api.get(`/api/reports/company_balance/${activeTab.value}`, {
            params,
            responseType: 'blob',
        });
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        
        // --- FIX START ---
        // Dynamically set the file extension and download attribute
        const extension = format === 'excel' ? 'xlsx' : 'pdf';
        const filename = `${activeTab.value}_report_${new Date().toISOString().slice(0, 10)}.${extension}`;
        
        link.setAttribute('download', filename);
        // --- FIX END ---
        
        document.body.appendChild(link);
        link.click();
        link.remove();
        message.success(`Report exported successfully!`);
    } catch (e: any) {
        message.error('Failed to export report: ' + (e.response?.data?.error || e.message));
    } finally {
        loading.value = false;
    }
};

watch(dateRange, () => {
  if (dateRange.value) {
    fetchCompanyBalanceReport();
  }
});

onMounted(() => {
  const end = Date.now();
  const start = end - 30 * 24 * 60 * 60 * 1000;
  dateRange.value = [start, end];
});
</script>

<style scoped>
.report-controls {
  width: 100%;
}
</style>