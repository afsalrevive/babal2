<template>
  <n-modal v-model:show="showModal" :mask-closable="false">
    <n-card class="attachment-modal-card">
      <template #header>
        <div class="modal-header">
          <span>Manage Attachments</span>
          <n-button text @click="showModal = false">
            <n-icon>
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
                <path fill="currentColor" d="m12 10.586l4.95-4.95a1 1 0 0 1 1.414 1.414l-4.95 4.95l4.95 4.95a1 1 0 0 1-1.414 1.414l-4.95-4.95l-4.95 4.95a1 1 0 0 1-1.414-1.414l4.95-4.95l-4.95-4.95a1 1 0 0 1 1.414-1.414z" />
              </svg>
            </n-icon>
          </n-button>
        </div>
      </template>

      <n-space justify="space-between" class="modal-controls">
          <n-upload
            v-model:file-list="fileListRef"
            multiple
            :show-file-list="false"
            @change="handleUploadChange"
          >
            <n-button>Upload Files</n-button>
          </n-upload>
      </n-space>
      
      <n-list class="attachment-list" v-if="attachments.length > 0" bordered>
        <n-list-item v-for="attachment in attachments" :key="attachment.id" class="attachment-item">
          <span class="file-name">{{ attachment.file_name }}</span>
          <n-button-group class="action-buttons">
            <n-button size="small" @click="viewAttachment(attachment.id)">View</n-button>
            <n-button size="small" type="error" @click="confirmDelete(attachment.id)">Delete</n-button>
          </n-button-group>
        </n-list-item>
      </n-list>
      <n-empty v-else description="No attachments found." style="margin-top: 20px;" />

      <n-modal v-model:show="showDeleteModal" :mask-closable="false" preset="dialog" title="Confirm Deletion">
        <n-alert type="warning">
          Are you sure you want to delete this attachment? This action cannot be undone.
        </n-alert>
        <template #action>
          <n-space>
            <n-button @click="showDeleteModal = false">Cancel</n-button>
            <n-button type="error" @click="deleteAttachment">Delete</n-button>
          </n-space>
        </template>
      </n-modal>
    </n-card>
  </n-modal>
</template>

<script setup>
import { ref, watch } from 'vue';
import { useMessage, NModal, NCard, NUpload, NButton, NButtonGroup, NList, NListItem, NEmpty, NAlert, NSpace, NIcon } from 'naive-ui';
import api from '@/api';

const message = useMessage();

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  parentType: String,
  parentId: [Number, String]
});

const emit = defineEmits(['update:show', 'attachment-updated']);

const showModal = ref(props.show);
const attachments = ref([]);
const loading = ref(false);

const showDeleteModal = ref(false);
const attachmentToDeleteId = ref(null);

const fileListRef = ref([]);

const fetchAttachments = async () => {
  if (!props.parentType || !props.parentId) {
    attachments.value = [];
    return;
  }
  
  loading.value = true;
  try {
    const res = await api.get(`/api/attachments/${props.parentType}/${props.parentId}`);
    attachments.value = res.data;
  } catch (e) {
    message.error('Failed to load attachments.');
    attachments.value = [];
  } finally {
    loading.value = false;
  }
};

const handleUploadChange = async ({ fileList }) => {
  if (!fileList || fileList.length === 0) return;

  for (const fileItem of fileList) {
    const file = fileItem.file;
    if (!file) {
      message.error(`Skipping invalid file: ${fileItem.name}`);
      continue;
    }

    const formData = new FormData();
    formData.append('file', file);
    
    try {
      await api.post(`/api/attachments/${props.parentType}/${props.parentId}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      message.success(`File "${fileItem.name}" uploaded successfully!`);
    } catch (e) {
      message.error(`Upload failed for "${fileItem.name}".`);
    }
  }
  
  fileListRef.value = [];

  await fetchAttachments();
  emit('attachment-updated');
};

const viewAttachment = async (attachmentId) => {
  try {
    const res = await api.get(`/api/attachments/${attachmentId}`, {
      responseType: 'blob',
    });
    
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const link = document.createElement('a');
    link.href = url;
    
    const attachment = attachments.value.find(a => a.id === attachmentId);
    if (attachment) {
      link.setAttribute('download', attachment.file_name);
    }
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  } catch (e) {
    message.error('Failed to download attachment.');
  }
};

const confirmDelete = (id) => {
  attachmentToDeleteId.value = id;
  showDeleteModal.value = true;
};

const deleteAttachment = async () => {
  if (!attachmentToDeleteId.value) return;

  try {
    await api.delete(`/api/attachments/${attachmentToDeleteId.value}`);
    message.success('Attachment deleted successfully!');
    await fetchAttachments();
    emit('attachment-updated');
  } catch (e) {
    message.error('Deletion failed.');
  } finally {
    showDeleteModal.value = false;
    attachmentToDeleteId.value = null;
  }
};

watch(() => props.show, (newVal) => {
  showModal.value = newVal;
  if (newVal) {
    fetchAttachments();
  }
});

watch(showModal, (newVal) => {
  if (newVal !== props.show) {
    emit('update:show', newVal);
  }
});
</script>

<style scoped>
.attachment-modal-card {
  max-width: 600px;
  min-height: 400px;
  padding: 20px;
  display: flex;
  flex-direction: column;
}
.attachment-list {
  flex-grow: 1;
  margin-top: 16px;
  overflow-y: auto;
}
.attachment-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.file-name {
  flex-grow: 1; 
  margin-right: 16px; 
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-buttons {
  flex-shrink: 0; 
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.modal-controls {
  margin-bottom: 16px;
}

</style>