<template>
  <n-card>
    <template #header>
      <n-h2>Transaction Manager</n-h2>
    </template>

    <n-tabs
      v-model:value="transactionType"
      type="line"
      animated
      @update:value="onTabChange"
      style="margin-bottom: 16px;"
    >
      <n-tab-pane v-for="tab in tabs" :key="tab" :name="tab" :tab="toSentenceCase(tab)" />
    </n-tabs>

    <n-space class="table-controls" justify="space-between">
      <n-space>
        <n-input class="search-filter" v-model:value="searchQuery" placeholder="Search" clearable />
        <n-date-picker
          class="date-filter"
          v-model:value="dateRange"
          type="daterange"
          clearable
          :default-value="defaultDateRange"
          style="max-width: 300px;"
        />
        <n-space class="export-buttons">
          <n-button @click="exportTransactions('excel')" type="primary" secondary :loading="exporting">
            <template #icon>
              <n-icon><DocumentTextOutline /></n-icon>
            </template>
            Excel
          </n-button>
          <n-button @click="exportTransactions('pdf')" type="primary" secondary :loading="exporting">
            <template #icon>
              <n-icon><DocumentTextOutline /></n-icon>
            </template>
            PDF
          </n-button>
        </n-space>
      </n-space>
      <PermissionWrapper resource="transaction" operation="write">
        <n-button type="primary" @click="openAddModal">Add {{ toSentenceCase(transactionType) }}</n-button>
      </PermissionWrapper>
    </n-space>

    <n-data-table 
      :columns="columns" 
      :data="transactions" 
      :loading="loading" 
      striped 
      :pagination="pagination"
      :remote="true"
      @update:sorter="handleSorterChange"
    />

    <n-modal
      v-model:show="modalVisible"
      :title="modalTitle"
      class="transaction-modal"
      preset="card"
      style="max-width: 90vw;"
    >
      <n-card class="modal-card">
        <n-space
          align="center"
          justify="space-between"
          style="margin-bottom: 12px"
          v-if="!editingId && ['payment', 'receipt', 'refund', 'wallet_transfer'].includes(transactionType)"
        >
          <div style="display: flex; align-items: center; gap: 8px;">
            <n-switch v-model:value="bulkAddMode" />
            <span>Bulk Add Mode</span>
          </div>
        </n-space>
        
        <n-form ref="formRef" :model="form" :rules="formRules">
          <div class="responsive-form-grid">
            <n-form-item label="Reference No">
              <n-skeleton v-if="refNoLoading" text :width="200" :sharp="false" />
              <n-input v-else v-model:value="form.ref_no" disabled />
            </n-form-item>

            <n-form-item label="Date" prop="transaction_date">
              <n-date-picker v-model:value="form.transaction_date" type="datetime" clearable />
            </n-form-item>

            <div v-if="transactionType === 'payment' || transactionType === 'receipt'" class="form-section">
              <PaymentFormSection 
                :form="form"
                :is-editing="isEditing"
                :transaction-type="transactionType"
                :entity-type-options="entityTypeOptions"
                :entity-options="entityOptions"
                :entities-loading="entitiesLoading"
                :selected-entity="selectedEntity"
                :particular-options="particularOptions"
                :particulars-loading="particularsLoading"
                :pay-type-options="payTypeOptions"
                :non-refund-mode-options="nonRefundModeOptions"
                :show-wallet-toggle="showWalletToggle"
                :wallet-toggle-disabled="walletToggleDisabled"
                :toggle-value="toggleValue"
                :toggle-label="toggleLabel"
                :new-particular-name="newParticularName"
                :should-show-create-particular="shouldShowCreateParticular"
                @entity-type-change="handleEntityTypeChange"
                @payment-type-change="handlePaymentTypeChange"
                @fetch-company-balance="fetchCompanyBalance"
                @toggle-value-change="handleToggleValueChange"
                @particular-search="handleParticularSearch"
                @particular-clear="handleParticularClear"
                @particular-value-update="handleParticularValueUpdate"
                @create-particular="handleCreateParticular"
              />
            </div>

            <div v-else-if="transactionType === 'refund'" class="form-section">
              <RefundFormSection 
                :form="form"
                :is-editing="isEditing"
                :entity-type-options="entityTypeOptions"
                :refund-direction-options="refundDirectionOptions"
                :company-mode-options="companyModeOptions"
                :from-entity-options="fromEntityOptions"
                :to-entity-options="toEntityOptions"
                :from-entities-loading="fromEntitiesLoading"
                :to-entities-loading="toEntitiesLoading"
                :selected-from-entity="selectedFromEntity"
                :selected-to-entity="selectedToEntity"
                :particular-options="particularOptions"
                :particulars-loading="particularsLoading"
                :company-refund-from-mode-options="companyRefundFromModeOptions"
                :mode-balance="modeBalance"
                :entity-options-ready="entityOptionsReady"
                :new-particular-name="newParticularName"
                :should-show-create-particular="shouldShowCreateParticular"
                @refund-entity-change="handleRefundEntityChange"
                @particular-search="handleParticularSearch"
                @particular-clear="handleParticularClear"
                @particular-value-update="handleParticularValueUpdate"
                @create-particular="handleCreateParticular"
              />
            </div>

            <div v-else-if="transactionType === 'wallet_transfer'" class="form-section">
              <WalletTransferFormSection 
                :form="form"
                :is-editing="isEditing"
                :entity-type-options="entityTypeOptions"
                :from-entity-options="fromEntityOptions"
                :to-entity-options="toEntityOptions"
                :from-entities-loading="fromEntitiesLoading"
                :to-entities-loading="toEntitiesLoading"
                :selected-from-entity="selectedFromEntity"
                :selected-to-entity="selectedToEntity"
                :particular-options="particularOptions"
                :particulars-loading="particularsLoading"
                :new-particular-name="newParticularName"
                :should-show-create-particular="shouldShowCreateParticular"
                @refund-entity-change="handleRefundEntityChange"
                @particular-search="handleParticularSearch"
                @particular-clear="handleParticularClear"
                @particular-value-update="handleParticularValueUpdate"
                @create-particular="handleCreateParticular"
              />
            </div>
            
            <n-form-item label="Amount" prop="amount" required>
              <n-input-number 
                v-model:value="form.amount" 
                :min="0" 
                :step="0.01" 
                clearable 
                style="width: 100%"
              />
            </n-form-item>

            <n-form-item label="Description" prop="description">
              <n-input v-model:value="form.description" type="textarea" />
            </n-form-item>
          </div>
        </n-form>
      </n-card>

        <template #footer>
          <div v-if="form.mode && modeBalance !== null && transactionType !== 'wallet_transfer'">
            <n-h5>Company Account</n-h5>
            <p>Mode: {{ form.mode }} — Balance: ₹{{ modeBalance.toFixed(2) }}</p>
          </div>
          <n-space justify="end">
            <n-button @click="closeModal">Cancel</n-button>
            <n-button type="primary" @click="validateAndSubmit">
              {{ editingId ? 'Update' : (bulkAddMode ? 'Save and Next' : 'Submit') }}
            </n-button>
          </n-space>
        </template>
    </n-modal>
    
    <n-modal v-model:show="showDeleteModal" :mask-closable="false" preset="dialog" title="Confirm Deletion">
      <n-alert type="warning">
        Are you sure you want to delete this transaction? This action cannot be undone.
      </n-alert>
      <template #action>
        <n-space>
          <n-button @click="showDeleteModal = false">Cancel</n-button>
          <n-button type="error" @click="deleteTransactionAndCloseModal">Delete</n-button>
        </n-space>
      </template>
    </n-modal>
    <AttachmentModal
      :show="attachmentModalVisible"
      :parent-type="attachmentParentType"
      :parent-id="attachmentParentId"
      @update:show="attachmentModalVisible = $event"
      @attachment-updated="fetchTransactions"
    />
    
    <EntityFormModal
      :show="entityModalVisible"
      :entity-type="entityToCreate"
      :form-data="{ name: defaultEntityName }"
      @update:show="handleEntityModalClose"
      @entity-created="handleEntityCreated"
    />
  </n-card>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick, watch, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import {
  useMessage, NButton, NSpace, NForm, NFormItem, NInput, NInputNumber, NDataTable, NModal,
  NCard, NTabs, NTabPane, NIcon, NDatePicker, NH2, NH3, NH5, NAlert, NSwitch, NP, NCheckbox, NSkeleton, NSelect
} from 'naive-ui'
import { DocumentTextOutline } from '@vicons/ionicons5'
import type { FormRules } from 'naive-ui'
import AttachmentModal from './AttachmentModal.vue'
import EntityFormModal from './EntityFormModal.vue'

// Import form sections
import PaymentFormSection from './PaymentFormSection.vue'
import RefundFormSection from './RefundFormSection.vue'
import WalletTransferFormSection from './WalletTransferFormSection.vue'

import PermissionWrapper from '@/components/PermissionWrapper.vue'

// ---- UTILITY FUNCTIONS ----
function debounce(fn: (...args: any[]) => void, delay: number) {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  return function(this: any, ...args: any[]) {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      fn.apply(this, args);
    }, delay);
  };
}

// ---- ROUTING AND STATE ----
const router = useRouter()
const route = useRoute()
const message = useMessage()
const tabs = ['payment', 'receipt', 'refund', 'wallet_transfer']
const transactionType = ref<'payment' | 'receipt' | 'refund' | 'wallet_transfer'>('payment')
const searchQuery = ref('')
const transactions = ref<any[]>([])
const loading = ref(false)
const exporting = ref(false)
const formRef = ref<any>(null)
const modalVisible = ref(false)
const defaultFields = ref<any>({})
const editingId = ref<number | null>(null)
const fieldErrors = ref<any>({})
const modeBalance = ref<number | null>(null)
const dateRange = ref<[number, number] | null>(null)
const entitiesLoading = ref(false)
const fromEntitiesLoading = ref(false)
const toEntitiesLoading = ref(false)
const particularsLoading = ref(false)
const entityOptions = ref<any[]>([])
const fromEntityOptions = ref<any[]>([])
const toEntityOptions = ref<any[]>([])
const particulars = ref<any[]>([])
const entityOptionsReady = ref(false)
const refNoLoading = ref(false)
const bulkAddMode = ref(false)

// State for custom delete confirmation modal
const showDeleteModal = ref(false);
const transactionToDeleteId = ref<number | null>(null);

const attachmentModalVisible = ref(false)
const attachmentParentType = ref('')
const attachmentParentId = ref(null)

// NEW: State for on-the-fly entity creation
const entityModalVisible = ref(false);
const entityToCreate = ref('');
const defaultEntityName = ref('');
const newParticularName = ref('');

const openAttachmentsModal = (type: string, id: number) => {
  attachmentParentType.value = type
  attachmentParentId.value = id
  attachmentModalVisible.value = true
}

// Pagination
const pagination = reactive({
  page: 1,
  pageSize: 20,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  itemCount: 0, // Will be set from server response
  onChange: (page: number) => {
    pagination.page = page
    fetchTransactions() // Refetch when page changes
  },
  onUpdatePageSize: (pageSize: number) => {
    pagination.pageSize = pageSize
    pagination.page = 1
    fetchTransactions() // Refetch when page size changes
  }
})

const sortKey = ref<string | null>(null)
const sortOrder = ref<'ascend' | 'descend' | null>(null)

const handleSorterChange = (sorter: any) => {
  if (sorter) {
    if (Array.isArray(sorter)) {
      // Handle multi-column sorting if needed
    } else {
      sortKey.value = sorter.columnKey
      sortOrder.value = sorter.order
    }
  } else {
    sortKey.value = null
    sortOrder.value = null
  }
  pagination.page = 1 // Reset to first page
  fetchTransactions()
}

// ---- CONSTANTS ----
const defaultDateRange = computed(() => {
  const end = Date.now()
  const start = end - 7 * 24 * 60 * 60 * 1000
  return [start, end] as [number, number]
})
const entityTypeOptions = [
  { label: 'Customer', value: 'customer' }, { label: 'Agent', value: 'agent' },
  { label: 'Partner', value: 'partner' }, { label: 'Others', value: 'others' }
]
const refundDirectionOptions = [
  { label: 'Company → Entity', value: 'outgoing' }, { label: 'Entity → Company', value: 'incoming' }
]
const companyModeOptions = [
  { label: 'Cash', value: 'cash' }, { label: 'Online', value: 'online' }
]
const nonRefundModeOptions = companyModeOptions

const onTabChange = async (type: string) => {
  if (tabs.includes(type)) {
    transactionType.value = type as any
    router.push({ name: 'TransactionPage', query: { type } })
    await fetchSchema()
    await fetchTransactions()
  }
}

// ---- FORM MODEL & UTILITIES ----
const defaultFormState = () => ({
  ref_no: 'Loading reference...', // Default placeholder
  transaction_date: Date.now(), 
  amount: null,
  entity_type: null, 
  entity_id: null, 
  pay_type: null, 
  mode: null,
  description: '', 
  particular_id: null,
  refund_direction: null, 
  to_entity_type: null, 
  to_entity_id: null,
  from_entity_type: null, 
  from_entity_id: null,
  mode_for_from: null, 
  mode_for_to: null,
  deduct_from_account: false, 
  credit_to_account: false
})
const form = reactive(defaultFormState())
const resetForm = () => Object.assign(form, defaultFormState())

function toSentenceCase(str: string) {
  return str.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}


// ---- COMPUTED PROPERTIES ----
const selectedEntity = computed(() => entityOptions.value.find((e: any) => e.value === form.entity_id))
const selectedFromEntity = computed(() => fromEntityOptions.value.find((e: any) => e.value === form.from_entity_id))
const selectedToEntity = computed(() => toEntityOptions.value.find((e: any) => e.value === form.to_entity_id))
const isEditing = computed(() => editingId.value !== null)

const modalTitle = computed(() => `${editingId.value ? 'Edit' : 'Add'} ${toSentenceCase(transactionType.value)}`)
const particularOptions = computed(() => particulars.value.map((p: any) => ({ label: p.name, value: p.id })))
// NEW: Computed property for the create particular button
const shouldShowCreateParticular = computed(() => !!newParticularName.value && !particulars.value.some(p => p.name.toLowerCase() === newParticularName.value.toLowerCase()));

const companyRefundFromModeOptions = computed(() => {
  const base = [...companyModeOptions]
  if (['customer', 'partner'].includes(form.to_entity_type as string)) {
    base.push({ label: 'Service Availed', value: 'service_availed' })
  }
  return base
})

const payTypeOptions = computed(() => {
  let types: string[] = []
  const entityType = form.entity_type || 'customer'
  if (transactionType.value === 'payment') {
    if (['customer', 'partner'].includes(entityType as string)) types = ['cash_withdrawal', 'other_expense']
    else if (entityType === 'agent') types = ['cash_deposit', 'other_expense']
    else if (entityType === 'others') types = ['other_expense']
  } else if (transactionType.value === 'receipt') {
    if (['customer', 'partner'].includes(entityType as string)) types = ['cash_deposit', 'other_receipt']
    else types = ['other_receipt']
  } else if (transactionType.value === 'refund') types = ['refund']
  return types.map(val => ({ label: toSentenceCase(val), value: val }))
})

const showWalletToggle = computed(() => {
  // For payments and receipts, show the toggle if it's 'other_expense' or 'other_receipt'
  if (transactionType.value === 'payment' || transactionType.value === 'receipt') {
    const isAgent = form.entity_type === 'agent'
    const isOtherExpense = form.pay_type === 'other_expense'
    const isOtherReceipt = form.pay_type === 'other_receipt'

    if (isAgent) {
      return (transactionType.value === 'payment' && isOtherExpense) || (transactionType.value === 'receipt' && isOtherReceipt)
    } else {
      // For customers/partners, only show for other_expense and other_receipt
      return isOtherExpense || isOtherReceipt
    }
  }
  return false
})

const walletToggleDisabled = computed(() => (
  // The toggle should be disabled for agent's cash deposits, as it's a fixed logic
  transactionType.value === 'payment' && form.entity_type === 'agent' && form.pay_type === 'cash_deposit'
))

const toggleValue = computed(() => {
  // Correctly map the checkbox value to the form's state
  if (transactionType.value === 'payment') {
    // Payment: credit agent, deduct others
    return form.entity_type === 'agent' ? form.credit_to_account : form.deduct_from_account
  }
  // Receipt: deduct agent, credit others
  return form.entity_type === 'agent' ? form.deduct_from_account : form.credit_to_account
})

const toggleLabel = computed(() => {
  // Correctly set the label based on the action
  if (transactionType.value === 'payment') {
    return form.entity_type === 'agent' ? 'Credit to wallet/credit?' : 'Deduct from wallet/credit?'
  }
  return form.entity_type === 'agent' ? 'Deduct from wallet/credit?' : 'Credit to wallet/credit?'
})

// ---- FORM RULES ----
const formRules = computed<FormRules>(() => {
  const rules: any = {
    transaction_date: [{ required: true, message: 'Date is required' }],
    amount: [{
      required: true,
      validator: (rule: any, value: any) => {
        if (value === null || value === undefined || value === '') return new Error('Amount is required')
        if (isNaN(Number(value))) return new Error('Amount must be a number')
        if (Number(value) <= 0) return new Error('Amount must be > 0')
        return true
      }, trigger: ['input', 'blur', 'change']
    }]
  }
  
  // Payment/Receipt specific rules
  if (transactionType.value === 'payment' || transactionType.value === 'receipt') {
    rules.entity_type = [{ required: true, message: 'Entity type required' }]
    rules.pay_type = [{ required: true, message: 'Payment type required' }]
    rules.mode = [{ required: true, message: 'Mode required' }]
    rules.particular_id = [{ required: true, message: 'Particular is required', validator: (_rule: any, value: any) => !!value, trigger: ['change', 'blur'] }];

    if (form.entity_type !== 'others') {
      rules.entity_id = [{ required: true, message: 'Entity required' }]
    }
  }
  
  // Refund specific rules
  if (transactionType.value === 'refund') {
    rules.refund_direction = [{ required: true, message: 'Refund direction required' }]
    rules.particular_id = [{ required: true, message: 'Particular is required', validator: (_rule: any, value: any) => !!value, trigger: ['change', 'blur'] }];

    if (form.refund_direction === 'incoming') {
      rules.from_entity_type = [{ required: true, message: 'From Entity Type required' }]
      if (form.from_entity_type !== 'others') {
        rules.from_entity_id = [{ required: true, message: 'From Entity required' }]
        rules.mode_for_from = [{ required: true, message: 'From Mode required' }]
      }
      if (form.from_entity_type === 'others' || form.mode_for_from === 'cash') {
        rules.mode_for_to = [{ required: true, message: 'To Mode required' }]
      }
    } else {
      rules.to_entity_type = [{ required: true, message: 'To Entity Type required' }]
      rules.mode_for_from = [{ required: true, message: 'From Mode required' }]
      if (form.to_entity_type !== 'others') {
        rules.to_entity_id = [{ required: true, message: 'To Entity required' }]
      }
    }
  }
  
  // Wallet transfer specific rules
  if (transactionType.value === 'wallet_transfer') {
    rules.from_entity_type = [{ required: true, message: 'From Entity Type required' }]
    rules.to_entity_type = [{ required: true, message: 'To Entity Type required' }]
    rules.particular_id = [{ required: true, message: 'Particular is required', validator: (_rule: any, value: any) => !!value, trigger: ['change', 'blur'] }];

    if (form.from_entity_type !== 'others') {
      rules.from_entity_id = [{ required: true, message: 'From Entity required' }]
    }
    if (form.to_entity_type !== 'others') {
      rules.to_entity_id = [{ required: true, message: 'To Entity required' }]
    }
  }
  
  return rules
})

// ---- API CALL HELPERS ----
const fetchCompanyBalance = async (mode: string) => {
  try {
    const { data } = await api.get(`/api/company_balance/${mode}`)
    modeBalance.value = data.balance
  } catch { modeBalance.value = null }
}

const loadEntities = async (type: string, context: 'default' | 'from' | 'to' = 'default') => {
  if (!type || type === 'others') { 
    if (context === 'default') entityOptions.value = []
    else if (context === 'from') fromEntityOptions.value = []
    else if (context === 'to') toEntityOptions.value = []
    return 
  }
  
  const loaders = {
    default: { loading: entitiesLoading, options: entityOptions },
    from: { loading: fromEntitiesLoading, options: fromEntityOptions },
    to: { loading: toEntitiesLoading, options: toEntityOptions }
  }
  
  const loader = loaders[context]
  loader.loading.value = true

  try {
    const res = await api.get(`/api/manage/${type}`)
    const options = res.data.map((e: any) => ({
      label: e.name, 
      value: e.id, 
      wallet_balance: e.wallet_balance,
      credit_limit: e.credit_limit, 
      credit_used: e.credit_used, 
      credit_balance: e.credit_balance
    }))
    
    loader.options.value = options
  } catch { 
    message.error('Failed to load entities') 
  } finally { 
    loader.loading.value = false
  }
}

const loadParticulars = async () => {
  particularsLoading.value = true
  try {
    const res = await api.get('/api/manage/particular')
    particulars.value = res.data || []
  } catch { 
    message.error('Failed to load particulars') 
  } finally { 
    particularsLoading.value = false 
  }
}

const fetchSchema = async () => {
  refNoLoading.value = true;
  try {
    const { data } = await api.get(`/api/transactions/${transactionType.value}?mode=form`);
    
    // Store and update ref_no
    defaultFields.value = {
      ...defaultFields.value,
      ref_no: data.ref_no || null
    };
    form.ref_no = data.ref_no || 'Loading reference...';
  } catch (e: any) {
    message.error(e?.response?.data?.error || 'Failed to load form schema');
    defaultFields.value = { ...defaultFields.value, ref_no: null };
    form.ref_no = 'Failed to load reference';
  } finally {
    refNoLoading.value = false;
  }
};


const fetchTransactions = async () => {
  loading.value = true
  try {
    const params: any = {
      transaction_type: transactionType.value,
      page: pagination.page,
      per_page: pagination.pageSize,
      search_query: searchQuery.value,
    }

    // Add date filters if set
    if (dateRange.value?.[0] && dateRange.value?.[1]) {
      const startDate = new Date(dateRange.value[0]);
      const endDate = new Date(dateRange.value[1]);

      // Manually format dates to YYYY-MM-DD without a timezone offset
      const formatDate = (date) => {
        const year = date.getFullYear();
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const day = date.getDate().toString().padStart(2, '0');
        return `${year}-${month}-${day}`;
      };

      params.start_date = formatDate(startDate);
      params.end_date = formatDate(endDate);
    }
    
    // Add sorting parameters
    if (sortKey.value && sortOrder.value) {
      params.sort_by = sortKey.value
      params.sort_order = sortOrder.value === 'ascend' ? 'asc' : 'desc'
    }

    const res = await api.get(`/api/transactions/${transactionType.value}`, { params })
    transactions.value = res.data.transactions || []
    pagination.itemCount = res.data.total // Total records from server
  } catch (e: any) {
    message.error(e?.response?.data?.error || 'Failed to fetch transactions')
    transactions.value = []
    pagination.itemCount = 0
  } finally { 
    loading.value = false 
  }
}

// ---- FORM HANDLERS ----
const handleEntityTypeChange = async (value: string) => {
  form.entity_type = value
  form.entity_id = null
  form.pay_type = null
  form.mode = null
  if (value !== 'others') await loadEntities(value, 'default')
  else entityOptions.value = []
}

const handleRefundEntityChange = async (value: string, dir: 'from' | 'to') => {
  const prefix = dir === 'to' ? 'to_' : 'from_'
  form[`${prefix}entity_type`] = value
  form[`${prefix}entity_id`] = null
  form.credit_to_account = false
  form.deduct_from_account = false
  form.mode_for_from = null
  form.mode_for_to = null
  if (value !== 'others') await loadEntities(value, dir)
  else if (dir === 'from') fromEntityOptions.value = []
  else if (dir === 'to') toEntityOptions.value = []
}

const handlePaymentTypeChange = (value: string) => {
  if (value === 'cash_withdrawal' && form.entity_type === 'agent') {
    message.warning('Cash withdrawal not available for agents')
    form.pay_type = null
  }
}

const handleToggleValueChange = (value: boolean) => {
    if (transactionType.value === 'payment') {
        // This is for payments to all entities
        if (form.entity_type === 'agent') {
            form.credit_to_account = value;
            form.deduct_from_account = false; // Ensure the other flag is false
        } else { // Customer/Partner
            form.deduct_from_account = value;
            form.credit_to_account = false; // Ensure the other flag is false
        }
    } else if (transactionType.value === 'receipt') {
        // This is for receipts from all entities
        if (form.entity_type === 'agent') {
            form.deduct_from_account = value;
            form.credit_to_account = false; // Ensure the other flag is false
        } else { // Customer/Partner
            form.credit_to_account = value;
            form.deduct_from_account = false; // Ensure the other flag is false
        }
    }
};

// NEW: On-the-fly entity creation handlers
const openEntityModal = (type: string, defaultName: string) => {
  entityToCreate.value = type;
  defaultEntityName.value = defaultName;
  entityModalVisible.value = true;
};

const handleParticularSearch = (query: string) => {
  const existingParticular = particulars.value.find(p => p.name.toLowerCase() === query.toLowerCase());
  // CRITICAL FIX: If a new query is typed and it's not an exact match, clear the selected ID to allow a new item to be created.
  if (query.trim() !== '' && !existingParticular) {
    form.particular_id = null; // This is the key change
    newParticularName.value = query;
  } else {
    newParticularName.value = '';
  }
};

const handleParticularClear = () => {
  newParticularName.value = '';
  form.particular_id = null;
};

const handleParticularValueUpdate = (value: number | null) => {
  form.particular_id = value;
  // This line is key to resetting the create button state after a selection is made
  if (value !== null) {
      newParticularName.value = '';
  }
};

const handleCreateParticular = () => {
  openEntityModal('particular', newParticularName.value);
};

const handleEntityCreated = async (event: { type: string, data: any }) => {
  const { type, data } = event;
  if (type === 'particular') {
    await loadParticulars();
    form.particular_id = data.id;
  }
  entityModalVisible.value = false;
};

const handleEntityModalClose = (val: boolean) => {
  entityModalVisible.value = val;
};

// ---- MODAL & SUBMIT ----
const openAddModal = async (row: any = null) => {
  
  editingId.value = row?.id || null;
  fieldErrors.value = {};
  bulkAddMode.value = false;
  resetForm();
  // NEW: Reset particular state
  newParticularName.value = '';

  if (row) {
    // Edit an existing transaction
    Object.assign(form, row, row.extra_data || {});
    if (row.timestamp) form.transaction_date = row.timestamp;
    else if (row.date) form.transaction_date = +new Date(row.date);
    

    if (transactionType.value === 'refund') {
      const entType = form.refund_direction === 'incoming' ? form.from_entity_type : form.to_entity_type;
      if (entType && entType !== 'others') {
        if (form.refund_direction === 'incoming') await loadEntities(entType, 'from');
        else await loadEntities(entType, 'to');
      }
      entityOptionsReady.value = true;
    }
    
    await fetchSchema();

    if (transactionType.value === 'wallet_transfer') {
      if (form.from_entity_type && form.from_entity_type !== 'others')
        await loadEntities(form.from_entity_type, 'from');
      if (form.to_entity_type && form.to_entity_type !== 'others')
        await loadEntities(form.to_entity_type, 'to');
    } else if (form.entity_type && form.entity_type !== 'others') {
      await loadEntities(form.entity_type, 'default');
    }

    entityOptionsReady.value = true;
  }
  modalVisible.value = true;
};

const closeModal = () => { 
  modalVisible.value = false
  resetForm()
  editingId.value = null 
  bulkAddMode.value = false
}

const getRefundEntityDetails = () => {
  const incoming = form.refund_direction === 'incoming'
  const entType = incoming ? form.from_entity_type : form.to_entity_type
  const entId = entType === 'others' ? null : (incoming ? form.from_entity_id : form.to_entity_id)
  return { entity_type: entType, entity_id: entId }
}

const validateAndSubmit = async () => {
  try {
    await formRef.value?.validate();
    
    // Ensure that form.amount is a valid positive number before proceeding
    if (form.amount == null || isNaN(Number(form.amount)) || Number(form.amount) <= 0) {
      message.error('Amount must be a positive number');
      return;
    }
 
    await submitTransaction();
  } catch (errors) {
    // Validation errors are caught here and stop the submission.
    message.error('Please fill in all required fields.');
  }
};

const submitTransaction = async () => {
  try {
    await formRef.value?.validate();

    const payload: any = {
      ...form,
      transaction_type: transactionType.value,
      pay_type: transactionType.value === 'refund' ? 'refund' : form.pay_type,
      credit_to_account: !!form.credit_to_account,
      deduct_from_account: !!form.deduct_from_account
    };

    if (transactionType.value === 'refund') {
      Object.assign(payload, getRefundEntityDetails());
      payload.mode = payload.refund_direction === 'incoming' ? payload.mode_for_to : payload.mode_for_from;
    }

    if (editingId.value) {
      await api.put(`/api/transactions/${editingId.value}`, payload);
      message.success('Transaction updated');
    } else {
      await api.post(`/api/transactions/${transactionType.value}`, payload);
      message.success('Transaction added');
    }

    if (bulkAddMode.value && !editingId.value) {
      // For bulk add, clear fields and fetch a new ref_no to keep the form ready.
      const fieldsToReset = ['amount', 'description', 'entity_id', 'particular_id', 'transaction_date'];
      fieldsToReset.forEach(field => {
        form[field] = null;
      });
      // Set the date to the current time for the next transaction.
      form.transaction_date = Date.now();
      // Fetch a fresh reference number from the backend to ensure it's incremented correctly.
      await fetchSchema();
      message.info('Form cleared for next entry.');
      // Restore validation state to clear any visual errors from the previous submission.
      nextTick(() => formRef.value?.restoreValidation?.());
    } else {
      // For single add or editing, close the modal and reset all state.
      modalVisible.value = false;
      editingId.value = null;
      bulkAddMode.value = false;
    }
    // Fetch the updated list of transactions to reflect the new or edited entry.
    await fetchTransactions();
  } catch (e: any) {
    if (e?.response?.data?.field_errors) {
      fieldErrors.value = e.response.data.field_errors;
    } else {
      message.error(e?.response?.data?.error || 'Failed to submit transaction');
    }
  }
};

// Function to show the custom delete confirmation modal
const confirmDelete = (id: number) => {
  transactionToDeleteId.value = id;
  showDeleteModal.value = true;
};

// Function to perform the deletion and close the modal
const deleteTransactionAndCloseModal = async () => {
  if (transactionToDeleteId.value) {
    await handleDelete(transactionToDeleteId.value);
  }
  showDeleteModal.value = false;
  transactionToDeleteId.value = null;
};

// Function to handle the actual API call for deleting a transaction
const handleDelete = async (id: number) => {
  try { 
    await api.delete(`/api/transactions/${id}`)
    message.success('Transaction deleted')
    await fetchTransactions() 
  } catch (e: any) { 
    message.error(e?.response?.data?.error || 'Failed to delete transaction') 
  }
}

// Unified export function
const exportTransactions = async (format: 'excel' | 'pdf') => {
  exporting.value = true
  try {
    const params: any = { 
      export: format,
      search_query: searchQuery.value,
      transaction_type: transactionType.value,
    }
    
    if (dateRange.value) {
      const [start, end] = dateRange.value
      params.start_date = new Date(start).toISOString().split('T')[0]
      params.end_date = new Date(end).toISOString().split('T')[0]
    }
    
    const response = await api.get(`/api/transactions/${transactionType.value}`, { 
      params, 
      responseType: 'blob' 
    })
    
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url

    const extension = format === 'excel' ? 'xlsx' : 'pdf'
    link.setAttribute('download', `${transactionType.value}_transactions_${new Date().toISOString().slice(0,10)}.${extension}`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } catch (e: any) {
    let errorMsg = e?.response?.data?.error || e.message
    if (e.response?.data instanceof Blob) {
      const text = await e.response.data.text()
      try {
        const json = JSON.parse(text)
        errorMsg = json.error || text
      } catch {
        errorMsg = text
      }
    }
    message.error(`${format.toUpperCase()} export failed: ${errorMsg}`)
  } finally {
    exporting.value = false
  }
}

// ---- DATA-TABLE ----
const columns = computed(() => {
  const baseColumns = [
    { 
      title: 'Ref No', 
      key: 'ref_no',
      sorter: true,
      sortOrder: sortKey.value === 'ref_no' ? sortOrder.value : undefined
    },
    { 
      title: 'Date', 
      key: 'date', 
      render: (row: any) => new Date(row.date).toLocaleDateString(),
      sorter: true,
      sortOrder: sortKey.value === 'date' ? sortOrder.value : undefined
    },
  ]
  
  if (transactionType.value === 'refund') {
    baseColumns.push({
      title: 'Direction',
      key: 'refund_direction',
      render: (row: any) => row.refund_direction ? toSentenceCase(row.refund_direction) : '',
      sorter: true,
      sortOrder: sortKey.value === 'refund_direction' ? sortOrder.value : undefined
    })
  }
  
  if (transactionType.value === 'wallet_transfer') {
    baseColumns.push(
      {
        title: 'Transfer Direction',
        key: 'transfer_direction',
        render: (row: any) => {
          const fromType = row.from_entity_type || row.extra_data?.from_entity_type || ''
          const toType = row.to_entity_type || row.extra_data?.to_entity_type || ''
          return `${toSentenceCase(fromType)} → ${toSentenceCase(toType)}`
        },
        sorter: false // Probably not sortable due to complex render
        ,
        sortOrder: 'ascend'
      },
      { 
        title: 'From Entity', 
        key: 'from_entity_name',
        render: (row: any) => row.from_entity_name || row.extra_data?.from_entity_name || '-',
        sorter: true,
        sortOrder: sortKey.value === 'from_entity_name' ? sortOrder.value : undefined
      },
      { 
        title: 'To Entity', 
        key: 'to_entity_name',
        render: (row: any) => row.to_entity_name || row.extra_data?.to_entity_name || '-',
        sorter: true,
        sortOrder: sortKey.value === 'to_entity_name' ? sortOrder.value : undefined
      }
    )
  } else {
    baseColumns.push(
      { 
        title: 'Entity Type', 
        key: 'entity_type', 
        render: (row: any) => toSentenceCase(row.entity_type || ''),
        sorter: true,
        sortOrder: sortKey.value === 'entity_type' ? sortOrder.value : undefined
      },
      { 
        title: 'Entity Name', 
        key: 'entity_name',
        sorter: true,
        sortOrder: sortKey.value === 'entity_name' ? sortOrder.value : undefined
      }
    )
  }

  baseColumns.push(
    { 
      title: 'Particular', 
      key: 'particular_name',
      sorter: true,
      sortOrder: sortKey.value === 'particular_name' ? sortOrder.value : undefined
    }
  )
  
  if (transactionType.value !== 'wallet_transfer') {
    baseColumns.push(
      {
        title: 'Payment Type',
        key: 'pay_type',
        render: (row: any) => row.pay_type ? toSentenceCase(row.pay_type) : '',
        sorter: true,
        sortOrder: sortKey.value === 'pay_type' ? sortOrder.value : undefined
      },
      { 
        title: 'Mode', 
        key: 'mode', 
        render: (row: any) => toSentenceCase(row.mode || ''),
        sorter: true,
        sortOrder: sortKey.value === 'mode' ? sortOrder.value : undefined
      }
    )
  }
  
  baseColumns.push(
    { 
      title: 'Amount', 
      key: 'amount',
      sorter: true,
      sortOrder: sortKey.value === 'amount' ? sortOrder.value : undefined
    }
  )

  const actions = {
    title: 'Actions',
    key: 'actions',
    render: (row: any) =>
      h(NSpace, { size: 8 }, () => [
        h(PermissionWrapper, { resource: 'transaction', operation: 'modify' }, {
          default: () => h(NButton, { 
            size: 'small', 
            type: 'primary', 
            onClick: () => openAddModal(row) 
          }, { default: () => 'Edit' })
        }),
        h(PermissionWrapper, { resource: 'transaction', operation: 'full' }, {
          default: () => h(NButton, { 
            size: 'small', 
            type: 'error', 
            onClick: () => confirmDelete(row.id) 
          }, { default: () => 'Delete' })
        })
      ])
  }
  
  const attachmentColumn = {
    title: 'Attachments',
    key: 'attachments',
    width: 120,
    render(row: any) {
      return h(PermissionWrapper, { resource: 'transaction', operation: 'read' }, {
        default: () => h(NButton, {
          size: 'small',
          onClick: () => openAttachmentsModal('transaction', row.id)
        }, { default: () => `Manage` })
      })
    }
  }
  
  return [...baseColumns, attachmentColumn, actions]
})

// ---- WATCHERS ----
watch(() => route.query.type, async (type) => {
  if (typeof type === 'string' && tabs.includes(type)) {
    transactionType.value = type as any
    pagination.page = 1
    await fetchSchema()
    await fetchTransactions()
  }
}, { immediate: true })

watch(() => form.refund_direction, (newDir) => {
  if (transactionType.value === 'refund') {
    form.mode_for_from = null
    form.mode_for_to = null
    form.credit_to_account = false
    form.deduct_from_account = false
    if (newDir === 'incoming' && form.from_entity_type) loadEntities(form.from_entity_type, 'from')
    else if (newDir === 'outgoing' && form.to_entity_type) loadEntities(form.to_entity_type, 'to')
  }
})

watch(() => [form.from_entity_type, form.to_entity_type], () => {
  if (transactionType.value === 'refund') {
    nextTick(() => { 
      if (form.refund_direction === 'incoming' && form.mode_for_from) 
        form.mode_for_from = form.mode_for_from 
    })
  }
})

// Combined watcher for filtering with debounce
const debouncedFetchTransactions = debounce(fetchTransactions, 500);
watch([searchQuery, dateRange], () => {
  pagination.page = 1
  debouncedFetchTransactions() // Trigger server fetch with debounce
}, { deep: true })

watch(() => transactionType.value, () => {
  pagination.page = 1
  sortKey.value = null
  sortOrder.value = null
  fetchTransactions()
})

// ---- LIFECYCLE ----
onMounted(async () => {
  dateRange.value = defaultDateRange.value
  const typeParam = route.query.type as string
  transactionType.value = tabs.includes(typeParam) ? typeParam as any : 'payment'
  
  // Use Promise.all for concurrent initial fetches
  await Promise.all([
    fetchSchema(),
    fetchTransactions(),
    loadParticulars(),
  ])
  
  if (form.entity_type && form.entity_type !== 'others') {
    await loadEntities(form.entity_type, 'default')
  }
})
</script>

<style scoped lang="scss">
@use '@/styles/theme' as *;

.responsive-form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
  align-items: start;
  
  .full-width {
    grid-column: 1 / -1;
  }
}

.form-section {
  display: contents;
}

.n-form-item {
  margin-bottom: 0;
}

.table-controls {
  margin-bottom: 20px;
}

.export-buttons {
  margin-left: 12px;
  
  .n-button {
    margin-right: 8px;
  }
}

.search-filter, .date-filter {
  max-width: 200px;
}

.modal-card {
  padding: 20px;
  
  .n-h3 {
    margin-top: 0;
  }
}
</style>