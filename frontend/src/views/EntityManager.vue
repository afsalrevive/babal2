<template>
  <n-card>
    <template #header>
      <n-h2>Entity Manager</n-h2>
    </template>

    <n-tabs v-model:value="activeTab" type="line" animated @update:value="handleTabChange">
      <n-tab-pane
        v-for="entity in entityTypes"
        :key="entity"
        :name="entity"
        :tab="toSentenceCase(entity)"
      >
        <n-tabs
          v-if="['customer', 'agent', 'partner', 'passenger', 'travel_location', 'particular', 'visa_type'].includes(activeTab)"
          v-model:value="subTab"
          size="small"
          type="line"
          style="margin-bottom: 12px"
        >
          <n-tab-pane name="active" tab="Active" />
          <n-tab-pane name="inactive" tab="Inactive" />
        </n-tabs>

        <n-space justify="space-between" wrap>
          <n-input
            v-model:value="searchQuery"
            placeholder="Search by name/contact"
            clearable
            style="max-width: 300px;"
          />
          <n-space>
            <PassengerExport
              v-if="activeTab === 'passenger'"
              :passengers="filteredData"
              :selected-passenger-ids="selectedPassengerIds"
            />
            <PermissionWrapper resource="entity" operation="write">
              <n-button type="primary" @click="openAddModal">Add {{ toSentenceCase(activeTab) }}</n-button>
            </PermissionWrapper>
          </n-space>
        </n-space>

        <n-data-table
          :columns="columns"
          :data="filteredData"
          :loading="loading"
          striped
          style="margin-top: 16px;"
          :row-key="(row) => row.id"
          @update:checked-row-keys="handleCheck"
          :pagination="pagination"
        />
      </n-tab-pane>
    </n-tabs>

    <EntityFormModal 
      :show="formModalVisible"
      :entity-type="modalEntityType"
      :edit-mode="editMode"
      :form-data="currentFormData"
      @update:show="formModalVisible = $event"
      @entity-created="fetchData"
      @entity-updated="fetchData"
    />
    
    <AttachmentModal 
      :show="attachmentModalVisible"
      :parent-type="attachmentParentType"
      :parent-id="attachmentParentId"
      @update:show="attachmentModalVisible = $event"
      @attachment-updated="fetchData"
    />

    <n-modal v-model:show="showDeleteModal" :mask-closable="false" preset="dialog" title="Confirm Deletion">
      <n-alert type="warning">
        Are you sure you want to delete this {{ toSentenceCase(activeTab) }}? This action cannot be undone.
      </n-alert>
      <template #action>
        <n-space>
          <n-button @click="showDeleteModal = false">Cancel</n-button>
          <n-button type="error" @click="deleteEntityAndCloseModal">Delete</n-button>
        </n-space>
      </template>
    </n-modal>
  </n-card>
</template>

<script setup lang="ts">
import {
  ref,
  watch,
  onMounted,
  h,
  computed,
  reactive
} from 'vue';
import api from '@/api';
import {
  useMessage,
  NButton,
  NSpace,
  NDataTable,
  NCard,
  NTabs,
  NTabPane,
  NInput,
  NModal,
  NAlert,
  NH2
} from 'naive-ui';
import PermissionWrapper from '@/components/PermissionWrapper.vue';
import AttachmentModal from '@/views/AttachmentModal.vue';
import EntityFormModal from '@/views/EntityFormModal.vue';
import PassengerExport from '@/views/PassengerExport.vue';
import type { DataTableColumns } from 'naive-ui';

const message = useMessage();
const entityTypes = ['customer','passenger', 'agent', 'partner', 'travel_location', 'particular', 'visa_type'];
const activeTab = ref<'customer' | 'passenger' | 'agent' | 'partner' | 'travel_location' | 'visa_type' |'particular'>('customer');
const subTab = ref<'active' | 'inactive'>('active');
const searchQuery = ref('');
const data = ref<any[]>([]);
const columns = ref<any[]>([]);
const loading = ref(false);

const formModalVisible = ref(false);
const modalEntityType = ref('');
const editMode = ref(false);
const currentFormData = ref({});

const showDeleteModal = ref(false);
const entityToDeleteId = ref<number | null>(null);

const attachmentCounts = ref({});
const attachmentModalVisible = ref(false);
const attachmentParentType = ref('');
const attachmentParentId = ref(null);

const selectedPassengerIds = ref<number[]>([]);

// Pagination state
const pagination = reactive({
  page: 1,
  pageSize: 10,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (page: number) => { pagination.page = page; },
  onUpdatePageSize: (pageSize: number) => { pagination.pageSize = pageSize; pagination.page = 1; },
});

const handleCheck = (rowKeys: number[]) => {
  if (activeTab.value === 'passenger') {
    selectedPassengerIds.value = rowKeys;
  }
};

const fetchAttachmentCounts = async () => {
  // Clear previous counts and check if there's data to process
  attachmentCounts.value = {};
  if (!data.value || data.value.length === 0) {
    return;
  }
  
  // Collect all entity IDs from the current data
  const parentIds = data.value.map(row => row.id);
  
  try {
    // Make a single API call to the new consolidated endpoint
    const res = await api.get(`/api/attachments/counts/${activeTab.value}`, {
      params: { parent_ids: parentIds }
    });
    
    // Update the attachment counts with the response data
    const counts = res.data || {};
    for (const id of parentIds) {
      attachmentCounts.value[id] = counts[id] || 0;
    }

  } catch (e: any) {
    console.error('Failed to fetch attachment counts:', e);
    message.error('Failed to load attachment counts');
  }
};

const openAttachmentsModal = (id: number) => {
  attachmentParentType.value = activeTab.value;
  attachmentParentId.value = id;
  attachmentModalVisible.value = true;
};

const toSentenceCase = (s: string) => {
  const customFieldLabels: Record<string, string> = {
    customer_id: 'Customer',
    is_active: 'Active',
    visa_type: 'Visa Type',
    travel_location: 'Travel Location',
  };
  return customFieldLabels[s] || s.replace(/_/g, ' ').replace(/\w\S*/g, (txt) =>
    txt.charAt(0).toUpperCase() + txt.slice(1).toLowerCase()
  );
};

const openAddModal = () => {
  modalEntityType.value = activeTab.value;
  editMode.value = false;
  currentFormData.value = {};
  formModalVisible.value = true;
};

function openEntityModal(type: string, defaultName = '') {
  modalEntityType.value = type as any;
  editMode.value = false;
  currentFormData.value = { name: defaultName };
  formModalVisible.value = true;
}

const updateEntityStatus = async (id: number, status: boolean) => {
  try {
    await api.patch(`/api/manage/${activeTab.value}`, { id, active: status });
    message.success(`Status updated`);
    await fetchData();
  } catch (e: any) {
    message.error(e.response?.data?.error || `Failed to update status`);
  }
};

const confirmDelete = (id: number) => {
  entityToDeleteId.value = id;
  showDeleteModal.value = true;
};

const deleteEntityAndCloseModal = async () => {
  if (entityToDeleteId.value) {
    await deleteEntity(entityToDeleteId.value);
  }
  showDeleteModal.value = false;
  entityToDeleteId.value = null;
};

const deleteEntity = async (id: number) => {
  try {
    await api.delete(`/api/manage/${activeTab.value}?id=${id}`);
    message.success(`${toSentenceCase(activeTab.value)} deleted`);
    await fetchData();
  } catch (e: any) {
    message.error(e.response?.data?.error || `Failed to delete ${activeTab.value}`);
  }
};

const defaultFieldsByEntity: Record<string, Record<string, any>> = {
  customer: { name: '', email: '', contact: '', wallet_balance: 0, credit_limit: 0, credit_used: 0, active: true },
  agent: { name: '', contact: '', email: '', wallet_balance: 0, credit_limit: 0, credit_balance: 0, active: true },
  partner: { name: '', contact: '', email: '', wallet_balance: 0, active: true, allow_negative_wallet: false },
  passenger: { name: '', contact: '', passport_number: '', salutation: '', address: '', city: '', state: '', country: '', zip_code: '', fathers_name: '', mothers_name: '', date_of_birth: null, passport_issue_date: null, passport_expiry: null, nationality: '', active: true },
  travel_location: { name: '', active: true },
  visa_type: { name: '', active: true },
  particular: { name: '', active: true }
};

const filteredData = computed(() => {
  let d = [...data.value];
  if (['customer', 'agent', 'partner', 'passenger', 'travel_location', 'particular', 'visa_type'].includes(activeTab.value)) {
    d = d.filter(row => row.active === (subTab.value === 'active'));
  }
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase();
    d = d.filter(row =>
      (row.name?.toLowerCase().includes(q) ||
      row.contact?.toLowerCase?.().includes(q) ||
      row.passport_number?.toLowerCase?.()?.includes(q) ||
      row.email?.toLowerCase?.()?.includes(q))
    );
  }
  return d;
});

const paginatedData = computed(() => {
  const start = (pagination.page - 1) * pagination.pageSize;
  const end = start + pagination.pageSize;
  return filteredData.value.slice(start, end);
});


const fetchData = async () => {
  loading.value = true;
  try {
    const res = await api.get(`/api/manage/${activeTab.value}`);
    data.value = res.data;
    
    // Reset pagination to page 1 on new data fetch
    pagination.page = 1;
    
    await fetchAttachmentCounts();
    
    let keys = Object.keys(defaultFieldsByEntity[activeTab.value]);
    const hiddenFields = ['address', 'fathers_name', 'mothers_name', 'passport_issue_date', 'passport_expiry'];
    keys = keys.filter(k => !hiddenFields.includes(k));

    const baseColumns: DataTableColumns = keys.map(key => {
      const column: any = {
        title: toSentenceCase(key),
        key,
        sortable: false
      };
      if (key === 'name') {
        column.sortable = true;
        column.sorter = (a: any, b: any) => a.name.localeCompare(b.name);
      } else if (['wallet_balance','credit_used', 'credit_limit', 'credit_balance'].includes(key)) {
        column.sortable = true;
        column.sorter = (a: any, b: any) => (a[key] ?? 0) - (b[key] ?? 0);
      }
      if (key.endsWith('_date') || key === 'date_of_birth' || key === 'passport_expiry') {
        column.render = (row: any) => {
          const dateStr = row[key];
          if (!dateStr) return 'N/A';
          try {
            const date = new Date(dateStr);
            return isNaN(date.getTime()) ? 'Invalid Date' : date.toLocaleDateString();
          } catch (e) {
            return 'Invalid Date';
          }
        };
      }
      if (key === 'passport_expiry') {
        column.title = 'Passport Expiry';
        column.render = (row: any) => {
          if (!row.passport_expiry) return 'N/A';
          const date = new Date(row.passport_expiry);
          const today = new Date();
          const diffDays = Math.ceil((date.getTime() - today.getTime()) / (1000 * 3600 * 24));
          return h('span', { style: { color: diffDays < 90 ? 'red' : 'inherit', fontWeight: diffDays < 90 ? 'bold' : 'normal' } }, date.toLocaleDateString());
        };
      }
      return column;
    });

    columns.value = [
      {
        type: 'selection',
        disabled: (row: any) => activeTab.value !== 'passenger',
      },
      ...baseColumns,
      {
        title: 'Actions',
        key: 'actions',
        render(row: any) {
          return h(NSpace, { size: 12 }, {
            default: () => [
              h(PermissionWrapper, { resource: 'entity', operation: 'modify' }, {
                default: () => h(NButton, {
                    size: 'small',
                    onClick: () => {
                      modalEntityType.value = activeTab.value;
                      editMode.value = true;
                      currentFormData.value = { ...row };
                      formModalVisible.value = true;
                    }
                  }, { default: () => 'Edit' })
              }),
              h(PermissionWrapper, { resource: 'entity', operation: 'full' }, {
                default: () => h(NButton, { 
                  size: 'small', 
                  type: 'error', 
                  onClick: () => { 
                    confirmDelete(row.id);
                  } 
                }, { default: () => 'Delete' })
              }),
              h(PermissionWrapper, { resource: 'entity', operation: 'modify' }, {
                default: () => h(NButton, { size: 'small', type: row.active ? 'warning' : 'success', onClick: () => { updateEntityStatus(row.id, !row.active); } }, { default: () => row.active ? 'Deactivate' : 'Activate' })
              })
            ]
          });
        }
      },
      {
        title: 'Attachments',
        key: 'attachments',
        render(row: any) {
          const count = attachmentCounts.value[row.id] || 0;
          return h(PermissionWrapper, { resource: 'entity', operation: 'read' }, {
            default: () => h(NButton, {
              size: 'small',
              onClick: () => openAttachmentsModal(row.id)
            }, { default: () => `Manage (${count})` })
          });
        }
      }
    ];
  } catch (e: any) {
    message.error(e.response?.data?.error || `Failed to load ${activeTab.value}`);
  } finally {
    loading.value = false;
  }
};

const handleTabChange = () => {
  searchQuery.value = '';
  selectedPassengerIds.value = [];
  pagination.page = 1;
  fetchData();
};

const handleSearchChange = () => {
  pagination.page = 1;
};

watch(searchQuery, handleSearchChange);
watch(subTab, handleSearchChange);
watch(activeTab, handleTabChange);

onMounted(() => {
  fetchData();
});

defineExpose({ openEntityModal });
</script>

<style scoped lang="scss">
@use '@/styles/theme' as *;
</style>