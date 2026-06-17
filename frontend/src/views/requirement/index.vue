<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">需求管理</span>
          <el-button v-if="userStore.hasPermission('requirement:create')" type="primary" :icon="Plus" @click="openDialog()">新增需求</el-button>
        </div>
      </template>

      <div class="search-bar">
        <el-select v-model="filters.project_id" placeholder="选择项目" clearable style="width:160px" @change="loadReqs">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-select v-model="filters.status" placeholder="状态筛选" clearable style="width:140px" @change="loadReqs">
          <el-option label="草稿" value="draft" />
          <el-option label="待处理" value="pending" />
          <el-option label="已接受" value="approved" />
          <el-option label="已拒绝" value="rejected" />
          <el-option label="开发中" value="developing" />
          <el-option label="已完成" value="closed" />
          <el-option label="已作废" value="voided" />
        </el-select>
        <el-select v-model="filters.priority" placeholder="优先级" clearable style="width:120px" @change="loadReqs">
          <el-option label="紧急" value="urgent" />
          <el-option label="高" value="high" />
          <el-option label="中" value="medium" />
          <el-option label="低" value="low" />
        </el-select>
        <el-input v-model="filters.keyword" placeholder="搜索需求标题" clearable style="width:200px" @keyup.enter="loadReqs" />
        <el-button type="primary" :icon="Search" @click="loadReqs">搜索</el-button>
      </div>

      <el-table :data="reqList" v-loading="loading" border stripe>
        <el-table-column prop="title" label="需求标题" min-width="200">
          <template #default="{ row }">
            <el-link type="primary" @click="$router.push(`/requirement/${row.id}`)">{{ row.title }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="所属项目" min-width="140">
          <template #default="{ row }">{{ row.project_name || row.project?.name || '-' }}</template>
        </el-table-column>
        <el-table-column label="优先级" width="90">
          <template #default="{ row }">
            <el-tag :type="priorityMap[row.priority]?.type" size="small">{{ priorityMap[row.priority]?.label || row.priority }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status]?.type" size="small">{{ statusMap[row.status]?.label || row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建人" width="100">
          <template #default="{ row }">{{ row.creator?.real_name || row.creator?.username || '-' }}</template>
        </el-table-column>
        <el-table-column prop="estimated_deadline" label="预计截止" width="120" />
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <div class="action-btns">
              <el-button type="primary" size="small" text @click="$router.push(`/requirement/${row.id}`)">查看</el-button>
              <el-button
                v-if="(row.status === 'draft' || row.status === 'rejected') && row.creator?.id === currentUserId"
                type="primary" size="small" text @click="openDialog(row)">编辑</el-button>
              <el-button
                v-if="(row.status === 'draft' || row.status === 'rejected') && row.creator?.id === currentUserId"
                type="warning" size="small" text @click="handleSubmit(row)">提交需求</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, prev, pager, next"
        style="margin-top:16px;justify-content:flex-end"
        @change="loadReqs"
      />
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingReq ? '编辑需求' : '新增需求'"
      width="850px"
      :close-on-click-modal="false"
    >
      <el-form ref="reqFormRef" :model="reqForm" :rules="reqRules" label-width="100px">
        <el-form-item label="所属项目" prop="project_id">
          <el-select v-model="reqForm.project_id" filterable placeholder="请选择项目" style="width:100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="需求标题" prop="title">
          <el-input v-model="reqForm.title" placeholder="请输入需求标题" />
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-radio-group v-model="reqForm.priority">
            <el-radio value="urgent">紧急</el-radio>
            <el-radio value="high">高</el-radio>
            <el-radio value="medium">中</el-radio>
            <el-radio value="low">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="需求描述">
          <RichEditor v-model="reqForm.description" />
        </el-form-item>
        <el-form-item label="附件">
          <el-upload
            :action="uploadUrl"
            :headers="uploadHeaders"
            :data="uploadData"
            v-model:file-list="fileList"
            :on-success="handleUploadSuccess"
            :on-remove="handleUploadRemove"
            :before-upload="beforeUpload"
            multiple
          >
            <el-button type="primary" plain>上传附件</el-button>
            <template #tip>
              <div class="el-upload__tip">支持任意格式文件，单个文件不超过 50MB</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleFormSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import RichEditor from '@/components/RichEditor.vue'
import { listRequirements, createRequirement, updateRequirement, submitRequirement } from '@/api/requirement'
import { listProjects } from '@/api/project'
import { listAttachments, deleteAttachment, bindAttachments } from '@/api/attachment'
import { useUserStore } from '@/store/user'

const userStore = useUserStore()
const currentUserId = userStore.userInfo?.id

const loading = ref(false)
const submitting = ref(false)
const reqList = ref([])
const projects = ref([])
const dialogVisible = ref(false)
const editingReq = ref(null)
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })
const filters = reactive({ project_id: '', status: '', priority: '', keyword: '' })
const reqFormRef = ref(null)

const priorityMap = {
  urgent: { label: '紧急', type: 'danger' },
  high: { label: '高', type: 'warning' },
  medium: { label: '中', type: '' },
  low: { label: '低', type: 'info' }
}
const statusMap = {
  draft: { label: '草稿', type: 'info' },
  pending: { label: '待处理', type: 'warning' },
  approved: { label: '已接受', type: 'success' },
  rejected: { label: '已拒绝', type: 'danger' },
  developing: { label: '开发中', type: '' },
  closed: { label: '已完成', type: 'success' },
  voided: { label: '已作废', type: 'danger' }
}

const fileList = ref([])
const uploadUrl = '/api/attachments'
const uploadHeaders = { Authorization: `Bearer ${localStorage.getItem('token')}` }
const uploadData = reactive({ target_id: 0, target_type: 'requirement' })

const reqForm = reactive({ project_id: null, title: '', priority: 'medium', description: '' })
const reqRules = {
  project_id: [{ required: true, message: '请选择项目', trigger: 'change' }],
  title: [{ required: true, message: '请输入需求标题', trigger: 'blur' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }]
}

async function loadReqs() {
  loading.value = true
  try {
    const res = await listRequirements({
      ...filters,
      page: pagination.page,
      page_size: pagination.pageSize
    })
    reqList.value = res.items || res || []
    pagination.total = res.total || reqList.value.length
  } catch (e) {
    reqList.value = []
  } finally {
    loading.value = false
  }
}

async function loadProjects() {
  try {
    const res = await listProjects({ page: 1, page_size: 100 })
    projects.value = res.items || res || []
  } catch (e) {
    projects.value = []
  }
}

function beforeUpload(file) {
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 50MB')
    return false
  }
  return true
}

function handleUploadSuccess(response, file) {
  const data = response?.data || response
  file.attachmentId = data?.id
}

function handleUploadRemove(file) {
  if (file.attachmentId) {
    deleteAttachment(file.attachmentId).catch(() => {})
  }
}

async function loadExistingAttachments(reqId) {
  try {
    const res = await listAttachments({ target_id: reqId, target_type: 'requirement' })
    const items = Array.isArray(res) ? res : (res.items || res || [])
    fileList.value = items.map(a => ({
      name: a.file_name,
      attachmentId: a.id,
      url: `/api/attachments/${a.id}/download?token=${localStorage.getItem('token')}`
    }))
  } catch (e) {
    fileList.value = []
  }
}

function openDialog(req = null) {
  editingReq.value = req
  if (req) {
    Object.assign(reqForm, {
      project_id: req.project?.id || req.project_id,
      title: req.title,
      priority: req.priority || 'medium',
      description: req.description || ''
    })
    uploadData.target_id = req.id
    loadExistingAttachments(req.id)
  } else {
    Object.assign(reqForm, { project_id: null, title: '', priority: 'medium', description: '' })
    uploadData.target_id = 0
    fileList.value = []
  }
  dialogVisible.value = true
}

async function handleFormSubmit() {
  const valid = await reqFormRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (editingReq.value) {
      await updateRequirement(editingReq.value.id, reqForm)
      ElMessage.success('更新成功')
    } else {
      const res = await createRequirement(reqForm)
      const newId = res?.id || res
      // 把临时上传（target_id=0）的附件关联到新需求
      const attachmentIds = fileList.value
        .map(f => f.attachmentId || f.response?.data?.id)
        .filter(Boolean)
      if (attachmentIds.length && newId) {
        await bindAttachments({
          attachment_ids: attachmentIds,
          target_id: newId,
          target_type: 'requirement'
        }).catch(() => {})
      }
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadReqs()
  } catch (e) {
  } finally {
    submitting.value = false
  }
}

async function handleSubmit(row) {
  await ElMessageBox.confirm('确定提交该需求吗？', '提示', {
    confirmButtonText: '确定', cancelButtonText: '取消', type: 'info'
  })
  try {
    await submitRequirement(row.id)
    ElMessage.success('提交成功')
    loadReqs()
  } catch (e) {}
}

onMounted(() => { loadReqs(); loadProjects() })
</script>

<style scoped>
.page-container { min-height: 100%; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-size: 16px; font-weight: 600; }
.search-bar { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.action-btns { display: flex; flex-wrap: nowrap; align-items: center; }
.action-btns .el-button { margin-left: 0; padding-left: 6px; padding-right: 6px; }
</style>
