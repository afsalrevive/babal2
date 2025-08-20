<template>
  <n-card>
    <template #header>
      <n-h2>Service Manager</n-h2>
    </template>

    <n-tabs v-model:value="activeTab" type="line" animated>
      <n-tab-pane name="active" tab="Active Services">
        <n-space justify="space-between" wrap class="table-controls">
          <n-space>
            <n-input
              v-model:value="searchQuery"
              placeholder="Search services"
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
          <PermissionWrapper resource="service" operation="write">
            <n-button type="primary" @click="openAddModal">Book Service</n-button>
          </PermissionWrapper>
        </n-space>

        <n-data-table
          :columns="columnsActive"
          :data="filteredActiveServices"
          :loading="loading"
          :pagination="pagination"
          striped
          style="margin-top: 16px;"
        />
      </n-tab-pane>
      <n-tab-pane name="cancelled" tab="Cancelled Services">
        <n-space>
          <n-input
            v-model:value="searchQuery"
            placeholder="Search services"
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
          :data="filteredCancelledServices"
          :loading="loading"
          :pagination="pagination"
          striped
          style="margin-top: 16px;"
        />
      </n-tab-pane>
    </n-tabs>

    <n-modal v-model:show="modalVisible" class="full-width-modal">
      <n-card class="modal-card">
        <n-h2 class="modal-title">{{ editMode ? 'Edit Service' : 'Book Service' }}</n-h2>
        <ServiceBookingForm
          v-if="modalVisible"
          :form-data="currentService"
          :edit-mode="editMode"
          :reference-number="referenceNumber"
          :bulk-add-mode="bulkAddMode"
          @update:bulkAddMode="bulkAddMode = $event"
          @record-booked="handleFormSuccess"
          @record-updated="handleFormSuccess"
          @cancel="modalVisible = false"
          @open-entity-modal="openEntityModal"
          @request-new-ref-no="fetchNewReferenceNumber"
          ref="bookingFormRef"
        />
      </n-card>
    </n-modal>

    <n-modal v-model:show="cancelModalVisible" class="transaction-modal">
      <n-card class="modal-card">
        <n-h2 class="modal-title">Cancel Service #{{ currentService.ref_no }}</n-h2>
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

          <n-space class="action-buttons" justify="end">
            <n-button @click="cancelModalVisible = false">Cancel</n-button>
            <PermissionWrapper resource="service" operation="modify">
              <n-button type="error" @click="confirmCancel">Confirm Cancellation</n-button>
            </PermissionWrapper>
          </n-space>
        </n-form>
      </n-card>
    </n-modal>

    <n-modal v-model:show="editCancelledModalVisible" class="transaction-modal">
      <n-card class="modal-card">
        <n-h2 class="modal-title">Edit Cancelled Service #{{ currentService.ref_no }}</n-h2>
        <n-form class="responsive-form-grid">
          <div class="refund-section">
            <n-h3>Customer Refund</n-h3>
            <n-form-item label="Refund Amount">
              <n-input-number v-model:value="currentService.customer_refund_amount" :min="0" />
            </n-form-item>

            <n-form-item label="Refund Mode">
              <n-select
                v-model:value="currentService.customer_refund_mode"
                :options="paymentModeOptions"
                placeholder="Select Refund Mode"
              />
            </n-form-item>
          </div>

          <n-space class="action-buttons" justify="end">
            <n-button @click="editCancelledModalVisible = false">Cancel</n-button>
            <PermissionWrapper resource="service" operation="modify">
              <n-button type="primary" @click="updateCancelledService">Update</n-button>
            </PermissionWrapper>
          </n-space>
        </n-form>
      </n-card>
    </n-modal>

    <n-modal v-model:show="showDeleteModal" :mask-closable="false" preset="dialog" title="Confirm Deletion">
      <n-alert type="warning">
        Are you sure you want to delete this service? This action cannot be undone.
      </n-alert>
      <template #action>
        <n-space>
          <n-button @click="showDeleteModal = false">Cancel</n-button>
          <n-button type="error" @click="deleteServiceAndCloseModal">Delete</n-button>
        </n-space>
      </template>
    </n-modal>

    <n-modal v-model:show="showCancelConfirmModal" :mask-closable="false" preset="dialog" title="Confirm Cancellation">
      <n-alert type="warning">
        Are you sure you want to cancel this service? This will create a refund transaction for the customer.
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
      :form-data="{ name: defaultEntityName }"
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
import { ref, computed, onMounted, h, watch, reactive, nextTick } from 'vue'
import { useMessage, NButton, NSpace, NModal, NAlert, NCard, NH2, NH3, NForm, NFormItem, NSelect, NInput, NDatePicker, NInputNumber, NTabs, NTabPane, NDataTable, NIcon } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import api from '@/api'
import PermissionWrapper from '@/components/PermissionWrapper.vue'
import { DocumentTextOutline } from '@vicons/ionicons5'
import AttachmentModal from './AttachmentModal.vue'
import ServiceBookingForm from './ServiceBookingForm.vue'
import EntityFormModal from './EntityFormModal.vue'

const message = useMessage()
const bookingFormRef = ref<any>(null)

// Data
const activeTab = ref('active')
const searchQuery = ref('')
const services = ref<any[]>([])
const loading = ref(false)
const modalVisible = ref(false)
const cancelModalVisible = ref(false)
const editCancelledModalVisible = ref(false)
const editMode = ref(false)

const showDeleteModal = ref(false);
const showCancelConfirmModal = ref(false);
const serviceToDeleteId = ref<number | null>(null);

const attachmentModalVisible = ref(false)
const attachmentParentType = ref('')
const attachmentParentId = ref(null)

const bulkAddMode = ref(false)

const openAttachmentsModal = (type, id) => {
  attachmentParentType.value = type
  attachmentParentId.value = id
  attachmentModalVisible.value = true
}

const entityModalVisible = ref(false);
const entityToCreate = ref('');
const defaultEntityName = ref('');

const dateRange = ref<[number, number] | null>(null)
const defaultDateRange = computed(() => {
  const end = Date.now()
  const start = end - 7 * 24 * 60 * 60 * 1000
  return [start, end] as [number, number]
})

onMounted(() => {
  dateRange.value = defaultDateRange.value
})

const paymentModeOptions = [
  { label: 'Cash', value: 'cash' },
  { label: 'Online', value: 'online' },
  { label: 'Wallet/Credit', value: 'wallet' },
]

const currentService = ref<any>({
  customer_id: null,
  particular_id: null,
  ref_no: '',
  customer_charge: 0,
  customer_payment_mode: null,
  date: Date.now()
})

const cancelData = ref({
  customer_refund_amount: 0,
  customer_refund_mode: 'cash'
})

const referencePlaceholder = ref('')
const referenceNumber = computed(() => {
  if (editMode.value && currentService.value.ref_no) {
    return currentService.value.ref_no
  }
  return referencePlaceholder.value || 'Generating...'
})

const filterServicesByDate = (servicesList: any[]) => {
  if (!dateRange.value) return servicesList;

  const [startTimestamp, endTimestamp] = dateRange.value;
  const startDate = new Date(startTimestamp);
  const endDate = new Date(endTimestamp);

  endDate.setHours(23, 59, 59, 999);

  return servicesList.filter(service => {
    if (!service.date) return false;
    const serviceDate = new Date(service.date);
    return serviceDate >= startDate && serviceDate <= endDate;
  });
};

const filterBySearchAndStatus = computed(() => {
    const search = searchQuery.value.toLowerCase()
    const filteredBySearch = services.value.filter(s =>
        s.ref_no?.toLowerCase().includes(search) ||
        s.customer_name?.toLowerCase().includes(search) ||
        s.particular_name?.toLowerCase().includes(search)
    )

    if (activeTab.value === 'active') {
        return filteredBySearch.filter(s => s.status === 'booked')
    } else {
        return filteredBySearch.filter(s => s.status === 'cancelled')
    }
});

const filteredActiveServices = computed(() => {
  return filterServicesByDate(filterBySearchAndStatus.value).filter(s => s.status === 'booked');
});

const filteredCancelledServices = computed(() => {
  return filterServicesByDate(filterBySearchAndStatus.value).filter(s => s.status === 'cancelled');
});


const pagination = reactive({
  page: 1,
  pageSize: 20,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (page: number) => { pagination.page = page; },
  onUpdatePageSize: (pageSize: number) => { pagination.pageSize = pageSize; pagination.page = 1; },
});


const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      start_date: dateRange.value?.[0] ? formatDateForAPI(dateRange.value[0]) : undefined,
      end_date: dateRange.value?.[1] ? formatDateForAPI(dateRange.value[1]) : undefined,
      status: activeTab.value === 'active' ? 'booked' : 'cancelled' 
    }

    const res = await api.get('/api/services', { params })
    services.value = res.data
  } catch (e) {
    handleApiError(e);
  } finally {
    loading.value = false
  }
}

const fetchNewReferenceNumber = async () => {
  referencePlaceholder.value = await generatePlaceholder();
};


const formatDateForAPI = (timestamp: number) => {
  const date = new Date(timestamp);
  return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}`;
}

const toSentenceCase = (str: string | null | undefined) => {
  if (!str) return '';
  return str.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
};

const generatePlaceholder = async () => {
  try {
    const { data } = await api.get('/api/services?action=next_ref_no');
    return data.ref_no;
  } catch (e) {
    message.error('Failed to generate reference number.');
    return 'Error...';
  }
};

const openAddModal = async () => {
  referencePlaceholder.value = await generatePlaceholder();
  currentService.value = {
    customer_id: null,
    particular_id: null,
    ref_no: '',
    customer_charge: 0,
    customer_payment_mode: null,
    date: Date.now(),
    description: ''
  };

  modalVisible.value = true;
  editMode.value = false;
  bulkAddMode.value = false;
};

const handleFormSuccess = async (isBulkAdd: boolean) => {
  if (!isBulkAdd) {
    modalVisible.value = false;
  }
  fetchData();
};

const editService = (service: any) => {
  currentService.value = {
    ...service,
    date: service.date ? new Date(service.date).getTime() : Date.now()
  };

  editMode.value = true;
  modalVisible.value = true;
}

const deleteService = async (serviceId: number) => {
  try {
    await api.delete(`/api/services?id=${serviceId}`)
    message.success('Service deleted successfully')
    await fetchData()
  } catch (e) {
    handleApiError(e)
  }
}

const openCancelModal = (service: any) => {
  currentService.value = { ...service }
  cancelData.value = {
    customer_refund_amount: service.customer_charge,
    customer_refund_mode: service.customer_payment_mode || 'cash'
  }
  cancelModalVisible.value = true
}

const editCancelledService = (service: any) => {
  currentService.value = {
    ...service,
    date: service.date ? new Date(service.date).getTime() : null
  };
  editCancelledModalVisible.value = true;
}

const updateCancelledService = async () => {
  try {
    const payload = {
      id: currentService.value.id,
      customer_refund_amount: currentService.value.customer_refund_amount,
      customer_refund_mode: currentService.value.customer_refund_mode
    };

    await api.patch('/api/services', payload)
    message.success('Cancelled service updated successfully')
    editCancelledModalVisible.value = false
    await fetchData()
  } catch (e) {
    handleApiError(e)
  }
}

const confirmCancel = async () => {
  if (!currentService.value?.id) {
    message.error('Service ID is missing')
    return
  }

  const payload = {
    service_id: currentService.value.id,
    customer_refund_amount: cancelData.value.customer_refund_amount,
    customer_refund_mode: cancelData.value.customer_refund_mode
  }

  try {
    await api.post('/api/services', payload, {
      params: { action: 'cancel' }
    })
    message.success('Service cancelled successfully')
    cancelModalVisible.value = false
    await fetchData()
  } catch (e) {
    handleApiError(e)
  }
}

const handleApiError = (e: any) => {
  if (e.response) {
    const errorMsg = e.response.data?.error || 'Operation failed'
    message.error(errorMsg)
  } else {
    message.error('Request error: ' + e.message)
  }
}

const handleConfirmDelete = (id: number) => {
  serviceToDeleteId.value = id
  showDeleteModal.value = true
}

const deleteServiceAndCloseModal = async () => {
  if (serviceToDeleteId.value !== null) {
    await deleteService(serviceToDeleteId.value)
  }
  showDeleteModal.value = false
  serviceToDeleteId.value = null
}

const handleConfirmCancel = () => {
  confirmCancel()
  showCancelConfirmModal.value = false
}

const openEntityModal = async (type: string, defaultName: string) => {
  entityToCreate.value = type;
  defaultEntityName.value = defaultName;
  entityModalVisible.value = true;
};

const handleEntityCreated = async (event: any) => {
  const { type, data } = event;
  
  if (bookingFormRef.value && bookingFormRef.value.form) {
    if (type === 'particular') {
      bookingFormRef.value.form.particular_id = data.id;
    }
  }

  await bookingFormRef.value?.fetchOptions();

  entityModalVisible.value = false;
};

const handleEntityModalClose = (val: boolean) => {
  entityModalVisible.value = val;
};

// Table columns
const baseColumns: DataTableColumns<any> = [
  { title: 'Ref No', key: 'ref_no', sorter: (a, b) => a.ref_no.localeCompare(b.ref_no) },
  { title: 'Date', key: 'date', render: (row) => row.date ? new Date(row.date).toLocaleDateString() : 'N/A' },
  { title: 'Customer', key: 'customer_name', sorter: (a, b) => a.customer_name.localeCompare(b.customer_name) },
  { title: 'Particular', key: 'particular_name', sorter: (a, b) => a.particular_name.localeCompare(b.particular_name) },
  { title: 'Charge', key: 'customer_charge', sorter: (a, b) => a.customer_charge - b.customer_charge },
  {
    title: 'Payment Mode',
    key: 'customer_payment_mode',
    render: (row) => toSentenceCase(row.customer_payment_mode)
  }
]

const columnsActive = ref<DataTableColumns<any>>([
  ...baseColumns,
  {
    title: 'Actions',
    key: 'actions',
    render(row) {
      if (row.status !== 'booked') return null;
      return h(NSpace, { size: 'small' }, () => [
        h(PermissionWrapper, { resource: 'service', operation: 'modify' }, {
          default: () => h(NButton, { size: 'small', onClick: () => editService(row) }, { default: () => 'Edit' })
        }),
        h(PermissionWrapper, { resource: 'service', operation: 'full' }, {
          default: () => h(NButton, { size: 'small', type: 'error', onClick: () => handleConfirmDelete(row.id) }, { default: () => 'Delete' })
        }),
        h(PermissionWrapper, { resource: 'service', operation: 'modify' }, {
          default: () => h(NButton, { size: 'small', type: 'warning', onClick: () => openCancelModal(row) }, { default: () => 'Cancel' })
        }),
      ])
    }
  },
  {
    title: 'Attachments',
    key: 'attachments',
    width: 120,
    render(row) {
      return h(PermissionWrapper, { resource: 'service', operation: 'read' }, {
        default: () => h(NButton, {
          size: 'small',
          onClick: () => openAttachmentsModal('service', row.id)
        }, { default: () => `Manage` })
      })
    }
  }
])

const columnsCancelled = ref<DataTableColumns<any>>([
  ...baseColumns,
  { title: 'Refund Amount', key: 'customer_refund_amount' },
  {
    title: 'Refund Mode',
    key: 'customer_refund_mode',
    render: (row) => toSentenceCase(row.customer_refund_mode)
  },
  {
    title: 'Actions',
    key: 'actions',
    render(row) {
      if (row.status !== 'cancelled') return null;
      return h(NSpace, { size: 'small' }, () => [
        h(PermissionWrapper, { resource: 'service', operation: 'modify' }, {
          default: () => h(NButton, {
            size: 'small',
            onClick: () => editCancelledService(row)
          }, { default: () => 'Edit Refund' })
        }),
        h(PermissionWrapper, { resource: 'service', operation: 'full' }, {
          default: () => h(NButton, {
            size: 'small',
            type: 'error',
            onClick: () => handleConfirmDelete(row.id)
          }, { default: () => 'Delete' })
        })
      ])
    }
  },
  {
    title: 'Attachments',
    key: 'attachments',
    width: 120,
    render(row) {
      return h(PermissionWrapper, { resource: 'service', operation: 'read' }, {
        default: () => h(NButton, {
          size: 'small',
          onClick: () => openAttachmentsModal('service', row.id)
        }, { default: () => `Manage` })
      })
    }
  },
])

const exportExcel = async () => {
  try {
    const params = {
      start_date: dateRange.value?.[0] ? formatDateForAPI(dateRange.value[0]) : undefined,
      end_date: dateRange.value?.[1] ? formatDateForAPI(dateRange.value[1]) : undefined,
      status: activeTab.value === 'active' ? 'booked' : 'cancelled',
      export: 'excel',
      search_query: searchQuery.value
    }

    const response = await api.get('/api/services', {
      params,
      responseType: 'blob'
    })

    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    const statusType = activeTab.value === 'active' ? 'Active' : 'Cancelled'
    link.href = url
    link.setAttribute('download', `${statusType}_Services_${new Date().toISOString().slice(0,10)}.xlsx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } catch (e) {
    message.error('Excel export failed')
  }
}

const exportPDF = async () => {
  try {
    const params = {
      start_date: dateRange.value?.[0] ? formatDateForAPI(dateRange.value[0]) : undefined,
      end_date: dateRange.value?.[1] ? formatDateForAPI(dateRange.value[1]) : undefined,
      status: activeTab.value === 'active' ? 'booked' : 'cancelled',
      export: 'pdf',
      search_query: searchQuery.value
    }

    const response = await api.get('/api/services', {
      params,
      responseType: 'blob'
    })

    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    const statusType = activeTab.value === 'active' ? 'Active' : 'Cancelled'
    link.href = url
    link.setAttribute('download', `${statusType}_Services_${new Date().toISOString().slice(0,10)}.pdf`)
    document.body.appendChild(link)
    link.click()
  } catch (e) {
    message.error('PDF export failed')
  }
}

watch([searchQuery, dateRange, activeTab], () => {
  fetchData();
});

// Lifecycle
onMounted(async () => {
  await fetchData()
})
</script>

<style scoped lang="scss">
@use '@/styles/theme' as *;
.responsive-form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.modal-card {
  max-width: 800px;
  width: 100%;
}

.wide-field {
  grid-column: 1 / -1;
}

.action-buttons {
  margin-top: 24px;
}
</style>