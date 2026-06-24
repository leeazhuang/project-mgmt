<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">任务管理</span>
          <div style="display:flex;gap:8px">
            <el-button v-if="canCreateTask" :icon="Grid" @click="$router.push('/task/board')">看板视图</el-button>
            <el-button v-if="userStore.hasPermission('task:mytasks')" :icon="User" @click="$router.push('/task/mytasks')">我的任务</el-button>
            <el-button v-if="canCreateTask && !isProductRole" type="primary" :icon="Plus" @click="openDialog()">新增任务</el-button>
          </div>
        </div>
      </template>

      <div class="search-bar">
        <el-select v-model="filters.project_id" placeholder="选择项目" clearable style="width:160px" @change="onProjectChange">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-select v-model="filters.status" placeholder="状态" clearable style="width:130px" @change="loadTasks">
          <el-option label="待处理" value="pending" />
          <el-option label="进行中" value="in_progress" />
          <el-option label="已完成" value="done" />
          <el-option label="已作废" value="voided" />
        </el-select>
        <el-select v-model="filters.assignee_id" placeholder="指派人" clearable style="width:140px" @change="loadTasks">
          <el-option v-for="u in userOptions" :key="u.id" :label="u.real_name || u.username" :value="u.id" />
        </el-select>
        <el-input v-model="filters.keyword" placeholder="搜索任务标题" clearable style="width:200px" @keyup.enter="loadTasks" />
        <el-button type="primary" :icon="Search" @click="loadTasks">搜索</el-button>
      </div>

      <el-table :data="taskList" v-loading="loading" border stripe>
        <el-table-column label="所属项目" width="140">
          <template #default="{ row }">{{ row.project_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="任务标题" min-width="200">
          <template #default="{ row }">
            <el-link type="primary" @click="$router.push(`/task/${row.id}`)">{{ row.title }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="所属需求" min-width="160">
          <template #default="{ row }">{{ row.requirement_title || '-' }}</template>
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
        <el-table-column label="指派给" min-width="130">
          <template #default="{ row }">
            <template v-if="row.assignees && row.assignees.length">
              <el-tag v-for="(a, i) in row.assignees" :key="a.user_id || a.display_tag || i" size="small" style="margin-right:2px"
                :type="a.status === 'done' ? 'success' : a.status === 'in_progress' ? 'warning' : 'info'">
                {{ assigneeLabel(a) }}
              </el-tag>
            </template>
            <span v-else>{{ row.assignee?.real_name || '未指派' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="planned_start_date" label="预计开始" width="120" />
        <el-table-column prop="start_date" label="实际开始" width="170" />
        <el-table-column label="截止日期" width="140">
          <template #default="{ row }">
            <span>{{ row.end_date || '-' }}</span>
            <el-tag v-if="isDelayed(row)" type="danger" size="small" style="margin-left:4px">已延期</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="estimated_hours" label="预估工时" width="100">
          <template #default="{ row }">{{ row.estimated_hours ? row.estimated_hours + 'h' : '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column v-if="!isProductRole" label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <div class="action-btns">
              <el-button v-if="getMyAssigneeStatus(row) === 'pending'" type="primary" size="small" text @click="changeMyStatus(row, 'in_progress')">开始</el-button>
              <el-button v-if="getMyAssigneeStatus(row) === 'in_progress'" type="success" size="small" text @click="changeMyStatus(row, 'done')">完成</el-button>
              <el-button type="primary" size="small" text @click="openLogDialog(row)">记录</el-button>
              <el-button v-if="row.status !== 'done' && row.status !== 'voided' && canEditTask(row)" type="warning" size="small" text @click="openDelayDialog(row)">延期</el-button>
              <el-button v-if="canEditTask(row) && row.status === 'pending'" type="primary" size="small" text @click="openDialog(row)">编辑</el-button>
              <el-button v-if="row.status !== 'voided' && row.status !== 'done' && canVoid(row)" type="danger" size="small" text @click="openVoidDialog(row)">作废</el-button>
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
        @change="loadTasks"
      />
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingTask ? '编辑任务' : '新增任务'"
      width="650px"
      :close-on-click-modal="false"
    >
      <el-form ref="taskFormRef" :model="taskForm" :rules="taskRules" label-width="100px">
        <template v-if="!editingTask">
          <el-form-item label="所属项目" prop="project_id">
            <el-select v-model="taskForm.project_id" filterable placeholder="请选择项目" style="width:100%" @change="loadRequirementsForProject">
              <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="所属需求" prop="requirement_id">
            <el-select v-model="taskForm.requirement_id" filterable placeholder="请选择需求（只显示已接受）" style="width:100%">
              <el-option v-for="r in requirementOptions" :key="r.id" :label="r.title" :value="r.id" />
            </el-select>
          </el-form-item>
        </template>
        <el-form-item label="任务标题" prop="title">
          <el-input v-model="taskForm.title" placeholder="请输入任务标题" />
        </el-form-item>
        <el-form-item label="任务描述">
          <RichEditor v-model="taskForm.description" />
        </el-form-item>
        <el-form-item label="附件">
          <el-upload
            v-if="editingTask"
            :action="`/api/attachments`"
            :headers="uploadHeaders"
            :data="{ target_type: 'task', target_id: editingTask.id }"
            :on-success="onUploadSuccess"
            :show-file-list="false"
            style="display:inline-block"
          >
            <el-button type="primary" size="small" :icon="Upload">上传附件</el-button>
          </el-upload>
          <el-upload
            v-else
            :action="`/api/attachments`"
            :headers="uploadHeaders"
            :data="{ target_type: 'task', target_id: 0 }"
            :on-success="onCreateUploadSuccess"
            :show-file-list="false"
            style="display:inline-block"
          >
            <el-button type="primary" size="small" :icon="Upload">上传附件</el-button>
          </el-upload>
          <div v-if="editAttachments.length" style="margin-top:8px">
            <div v-for="file in editAttachments" :key="file.id" style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
              <el-link type="primary" @click="downloadFile(file)">{{ file.file_name }}</el-link>
              <span style="color:#999;font-size:12px">{{ formatSize(file.file_size) }}</span>
              <el-button type="danger" size="small" text @click="handleDeleteAttachment(file)">删除</el-button>
            </div>
          </div>
          <div v-if="!editingTask && pendingAttachments.length" style="margin-top:8px">
            <div v-for="file in pendingAttachments" :key="file.id" style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
              <el-link type="primary">{{ file.file_name }}</el-link>
              <span style="color:#999;font-size:12px">{{ formatSize(file.file_size) }}</span>
              <el-button type="danger" size="small" text @click="removePendingAttachment(file)">移除</el-button>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-radio-group v-model="taskForm.priority">
            <el-radio value="urgent">紧急</el-radio>
            <el-radio value="high">高</el-radio>
            <el-radio value="medium">中</el-radio>
            <el-radio value="low">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="editingTask && taskForm.status !== 'voided'" label="状态">
          <el-select v-model="taskForm.status" style="width:100%">
            <el-option label="待处理" value="pending" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已完成" value="done" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editingTask && taskForm.status === 'voided'" label="状态">
          <el-tag type="danger">已作废</el-tag>
        </el-form-item>
        <el-form-item label="指派给" prop="assignee_sel">
          <el-select v-model="taskForm.assignee_sel" multiple filterable placeholder="请选择指派人（可多选，有标签的按标签选）" style="width:100%">
            <el-option v-for="o in assignOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="预计开始时间">
          <el-date-picker v-model="taskForm.planned_start_date" type="date" value-format="YYYY-MM-DD" placeholder="选择预计开始时间" style="width:100%" />
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker v-model="taskForm.end_date" type="date" value-format="YYYY-MM-DD" placeholder="选择截止日期" style="width:100%" />
        </el-form-item>
        <el-form-item label="预估工时">
          <el-input-number v-model="taskForm.estimated_hours" :min="0" :step="0.5" placeholder="预估小时数" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 流转记录 -->
    <el-dialog v-model="logDialogVisible" :title="'流转记录 - ' + logTaskTitle" width="600px">
      <el-timeline v-if="taskLogs.length">
        <el-timeline-item
          v-for="log in taskLogs"
          :key="log.id"
          :timestamp="log.created_at"
          :type="actionTypeMap[log.action] || 'info'"
        >
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            <span style="font-weight:500">{{ log.operator?.real_name || log.operator?.username }}</span>
            <el-tag :type="actionTypeMap[log.action] || 'info'" size="small">{{ actionLabelMap[log.action] || log.action }}</el-tag>
            <div v-if="log.remark" style="color:#666;font-size:13px;width:100%">{{ log.remark }}</div>
          </div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无流转记录" />
    </el-dialog>

    <!-- 作废 -->
    <el-dialog v-model="voidDialogVisible" title="任务作废" width="450px" :close-on-click-modal="false">
      <el-alert type="warning" :closable="false" style="margin-bottom:16px">
        作废后任务将不可编辑，请确认操作。
      </el-alert>
      <el-form label-width="80px">
        <el-form-item label="任务标题">
          <span>{{ voidingTask?.title }}</span>
        </el-form-item>
        <el-form-item label="作废原因">
          <el-input v-model="voidForm.reason" type="textarea" rows="3" placeholder="请说明作废原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="voidDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="voidSubmitting" @click="handleVoid">确定作废</el-button>
      </template>
    </el-dialog>

    <!-- 延期 -->
    <el-dialog v-model="delayDialogVisible" title="任务延期" width="450px" :close-on-click-modal="false">
      <el-form label-width="100px">
        <el-form-item label="当前截止日期">
          <span>{{ delayingTask?.end_date || '未设置' }}</span>
        </el-form-item>
        <el-form-item label="新截止日期" required>
          <el-date-picker v-model="delayForm.new_end_date" type="date" value-format="YYYY-MM-DD" placeholder="选择新截止日期" style="width:100%" />
        </el-form-item>
        <el-form-item label="延期原因">
          <el-input v-model="delayForm.reason" type="textarea" rows="3" placeholder="请说明延期原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="delayDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="delaySubmitting" @click="handleDelay">确定延期</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search, Grid, Clock, Timer, Upload, User } from '@element-plus/icons-vue'
import { listTasks, createTask, updateTask, getTaskLogs, delayTask, voidTask } from '@/api/task'
import { listProjects } from '@/api/project'
import { listRequirements } from '@/api/requirement'
import { getUserOptions } from '@/api/user'
import { listAttachments, deleteAttachment, getDownloadUrl, bindAttachments } from '@/api/attachment'
import { useUserStore } from '@/store/user'
import RichEditor from '@/components/RichEditor.vue'

const userStore = useUserStore()

// 产品角色：只读任务列表，不能看记录和编辑
const isProductRole = computed(() => {
  const roles = userStore.userInfo?.roles || []
  const hasProd = roles.includes('product') || roles.some(r => r === 'product' || r?.code === 'product')
  if (!hasProd) return false
  // 如果同时有超管或其他管理角色则不受限
  return !_isSuperAdmin()
})

function _isSuperAdmin() {
  const roles = userStore.userInfo?.roles || []
  return roles.includes('super_admin') || roles.some(r => r === 'super_admin' || r?.code === 'super_admin')
}

// 新增任务按钮：超管 / 任意项目的负责人或技术负责人都能看到（具体项目权限后端校验）
const canCreateTask = computed(() => {
  if (_isSuperAdmin()) return true
  // 只要用户在任何项目中是负责人或技术负责人，就显示按钮
  // 实际创建时后端会校验具体项目权限
  return projects.value.some(p => {
    const uid = userStore.userInfo?.id
    return p.owner?.id === uid || p.tech_leader?.id === uid
  })
})

// 编辑按钮：超管 / 该任务所在项目的负责人或技术负责人
function canEditTask(row) {
  if (_isSuperAdmin()) return true
  const uid = userStore.userInfo?.id
  return uid === row.project_owner_id || uid === row.project_tech_leader_id
}

const loading = ref(false)
const submitting = ref(false)
const taskList = ref([])
const projects = ref([])
const userOptions = ref([])
const requirementOptions = ref([])
const dialogVisible = ref(false)
const editingTask = ref(null)
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })
const filters = reactive({ project_id: '', status: '', assignee_id: '', keyword: '' })
const taskFormRef = ref(null)

const priorityMap = {
  urgent: { label: '紧急', type: 'danger' },
  high: { label: '高', type: 'warning' },
  medium: { label: '中', type: '' },
  low: { label: '低', type: 'info' }
}
const statusMap = {
  pending: { label: '待处理', type: 'info' },
  in_progress: { label: '进行中', type: 'warning' },
  done: { label: '已完成', type: 'success' },
  voided: { label: '已作废', type: 'danger' }
}

// 流转记录
const logDialogVisible = ref(false)
const taskLogs = ref([])
const logTaskTitle = ref('')
const actionLabelMap = {
  create: '创建任务', start: '开始任务', done: '完成任务',
  delay: '任务延期', reassign: '重新指派', reopen: '重新打开', update: '更新任务', void: '任务作废'
}
const actionTypeMap = {
  create: 'primary', start: '', done: 'success',
  delay: 'warning', reassign: 'info', reopen: 'warning', update: 'info', void: 'danger'
}

// 作废
const voidDialogVisible = ref(false)
const voidForm = reactive({ reason: '' })
const voidingTask = ref(null)
const voidSubmitting = ref(false)

// 延期
const delayDialogVisible = ref(false)
const delayForm = reactive({ new_end_date: '', reason: '' })
const delayingTask = ref(null)
const delaySubmitting = ref(false)

const uploadHeaders = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('token')}` }))
const editAttachments = ref([])
const pendingAttachments = ref([])

function isDelayed(row) {
  if (row.status === 'done' || row.status === 'voided') return false
  if (!row.end_date) return false
  return new Date(row.end_date) < new Date(new Date().toISOString().split('T')[0])
}

const taskForm = reactive({
  project_id: null, requirement_id: null, title: '', description: '', priority: 'medium',
  status: 'pending', assignee_sel: [], planned_start_date: '', end_date: '', estimated_hours: null
})

const taskRules = {
  project_id: [{ required: true, message: '请选择项目', trigger: 'change' }],
  requirement_id: [{ required: true, message: '请选择需求', trigger: 'change' }],
  title: [{ required: true, message: '请输入任务标题', trigger: 'blur' }],
  assignee_sel: [{ required: true, message: '请选择指派人', trigger: 'change', type: 'array', min: 1 }]
}

// 指派下拉：有标签的成员按标签拆成多个选项，无标签出真名；value 编码 "user_id::标签"
const assignOptions = computed(() => {
  const opts = []
  for (const u of userOptions.value) {
    const tags = u.display_tags || []
    const name = u.real_name || u.username
    // 始终保留真名选项（即便打了标签也能按真名选）；标签选项 label 带上真名
    opts.push({ value: `${u.id}::`, label: name })
    tags.forEach(t => opts.push({ value: `${u.id}::${t}`, label: `${t}（${name}）` }))
  }
  return opts
})

// 把 ["uid::tag", ...] 拆成 { ids:[uid], tags:{uid:tag} }，同一人多标签取最后一个
function parseSelList(selList) {
  const ids = []
  const tags = {}
  for (const sel of selList || []) {
    const idx = sel.indexOf('::')
    const uid = Number(idx < 0 ? sel : sel.slice(0, idx))
    const tag = idx < 0 ? '' : sel.slice(idx + 2)
    if (!uid) continue
    if (!ids.includes(uid)) ids.push(uid)
    if (tag) tags[uid] = tag
  }
  return { ids, tags }
}

// 指派给展示：有标签快照→标签(真名)，受限角色后端不返回真名则只显示标签
function assigneeLabel(a) {
  const tag = a.display_tag
  const name = a.user?.real_name || a.user?.username
  if (tag) return name ? `${tag}（${name}）` : tag
  return name || '未指派'
}

async function loadTasks() {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize }
    if (filters.project_id) params.project_id = filters.project_id
    if (filters.status) params.status = filters.status
    if (filters.assignee_id) params.assignee_id = filters.assignee_id
    const res = await listTasks(params)
    taskList.value = res.items || res || []
    pagination.total = res.total || taskList.value.length
  } catch (e) {
    taskList.value = []
  } finally {
    loading.value = false
  }
}

async function loadProjects() {
  try {
    const res = await listProjects({ page: 1, page_size: 100 })
    projects.value = res.items || res || []
  } catch (e) { projects.value = [] }
}

async function loadUsers() {
  try {
    const res = await getUserOptions()
    userOptions.value = res.items || res || []
  } catch (e) { userOptions.value = [] }
}

async function loadRequirementsForProject() {
  if (!taskForm.project_id) { requirementOptions.value = []; return }
  try {
    const res = await listRequirements({ project_id: taskForm.project_id, status: 'approved,developing', page: 1, page_size: 100 })
    requirementOptions.value = res.items || res || []
  } catch (e) { requirementOptions.value = [] }
}

function onProjectChange() {
  filters.project_id = filters.project_id
  loadTasks()
}

async function loadEditAttachments(taskId) {
  try {
    const res = await listAttachments({ target_type: 'task', target_id: taskId })
    editAttachments.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) { editAttachments.value = [] }
}

function onUploadSuccess() {
  ElMessage.success('上传成功')
  if (editingTask.value) loadEditAttachments(editingTask.value.id)
}

function onCreateUploadSuccess(res) {
  ElMessage.success('上传成功')
  const file = res?.data || res
  if (file?.id) {
    pendingAttachments.value.push(file)
  }
}

function removePendingAttachment(file) {
  pendingAttachments.value = pendingAttachments.value.filter(f => f.id !== file.id)
  deleteAttachment(file.id).catch(() => {})
}

async function handleDeleteAttachment(file) {
  try {
    await deleteAttachment(file.id)
    ElMessage.success('删除成功')
    if (editingTask.value) loadEditAttachments(editingTask.value.id)
  } catch (e) {}
}

function downloadFile(file) {
  window.open(getDownloadUrl(file.id), '_blank')
}

function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

function openDialog(task = null) {
  editingTask.value = task
  editAttachments.value = []
  pendingAttachments.value = []
  if (task) {
    loadEditAttachments(task.id)
    Object.assign(taskForm, {
      project_id: task.project_id,
      requirement_id: task.requirement_id,
      title: task.title, description: task.description || '',
      priority: task.priority || 'medium', status: task.status || 'pending',
      assignee_sel: (task.assignees || [])
        .filter(a => a.user_id)
        .map(a => `${a.user_id}::${a.display_tag || ''}`),
      planned_start_date: task.planned_start_date || '', end_date: task.end_date || '',
      estimated_hours: task.estimated_hours || null
    })
  } else {
    Object.assign(taskForm, {
      project_id: null, requirement_id: null, title: '', description: '',
      priority: 'medium', status: 'pending', assignee_sel: [],
      planned_start_date: '', end_date: '', estimated_hours: null
    })
    requirementOptions.value = []
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await taskFormRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const { ids: assigneeIds, tags: assigneeTags } = parseSelList(taskForm.assignee_sel)
    if (editingTask.value) {
      const updateData = {
        title: taskForm.title,
        description: taskForm.description,
        priority: taskForm.priority,
        assignee_ids: assigneeIds,
        assignee_tags: assigneeTags,
        planned_start_date: taskForm.planned_start_date || null,
        end_date: taskForm.end_date || null,
        estimated_hours: taskForm.estimated_hours
      }
      await updateTask(editingTask.value.id, updateData)
      ElMessage.success('更新成功')
    } else {
      const createData = {
        requirement_id: taskForm.requirement_id,
        title: taskForm.title,
        description: taskForm.description,
        priority: taskForm.priority,
        assignee_ids: assigneeIds,
        assignee_tags: assigneeTags,
        planned_start_date: taskForm.planned_start_date || null,
        end_date: taskForm.end_date || null,
        estimated_hours: taskForm.estimated_hours || 0
      }
      const newTask = await createTask(createData)
      // 绑定新增时上传的附件
      if (pendingAttachments.value.length && newTask?.id) {
        try {
          await bindAttachments({
            attachment_ids: pendingAttachments.value.map(f => f.id),
            target_type: 'task',
            target_id: newTask.id
          })
        } catch (e) {}
        pendingAttachments.value = []
      }
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadTasks()
  } catch (e) {
  } finally {
    submitting.value = false
  }
}

async function openLogDialog(task) {
  logTaskTitle.value = task.title
  logDialogVisible.value = true
  try {
    const res = await getTaskLogs(task.id)
    taskLogs.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) {
    taskLogs.value = []
  }
}

function openDelayDialog(task) {
  delayingTask.value = task
  delayForm.new_end_date = task.end_date || ''
  delayForm.reason = ''
  delayDialogVisible.value = true
}

async function handleDelay() {
  if (!delayForm.new_end_date) {
    ElMessage.warning('请选择新的截止日期')
    return
  }
  delaySubmitting.value = true
  try {
    await delayTask(delayingTask.value.id, {
      new_end_date: delayForm.new_end_date,
      reason: delayForm.reason
    })
    ElMessage.success('延期成功')
    delayDialogVisible.value = false
    loadTasks()
  } catch (e) {
  } finally {
    delaySubmitting.value = false
  }
}

// 获取当前用户在任务中的个人状态（多人任务用子表，单人用主表）
function getMyAssigneeStatus(row) {
  const uid = userStore.userInfo?.id
  if (row.assignees && row.assignees.length) {
    const mine = row.assignees.find(a => a.user_id === uid || a.user?.id === uid)
    return mine ? mine.status : null
  }
  if (row.assignee?.id === uid) return row.status
  return null
}

async function changeMyStatus(row, newStatus) {
  try {
    await updateTask(row.id, { status: newStatus })
    ElMessage.success(newStatus === 'in_progress' ? '已开始' : '已完成')
    loadTasks()
  } catch (e) {}
}

function canVoid(row) {
  const roles = userStore.userInfo?.roles || []
  const isSuperAdmin = roles.includes('super_admin') || roles.some(r => r === 'super_admin' || r?.code === 'super_admin')
  if (isSuperAdmin) return true
  const uid = userStore.userInfo?.id
  return uid === row.project_owner_id || uid === row.project_tech_leader_id
}

function openVoidDialog(task) {
  voidingTask.value = task
  voidForm.reason = ''
  voidDialogVisible.value = true
}

async function handleVoid() {
  voidSubmitting.value = true
  try {
    await voidTask(voidingTask.value.id, { reason: voidForm.reason })
    ElMessage.success('任务已作废')
    voidDialogVisible.value = false
    loadTasks()
  } catch (e) {
  } finally {
    voidSubmitting.value = false
  }
}

onMounted(() => { loadTasks(); loadProjects(); loadUsers() })
</script>

<style scoped>
.page-container { min-height: 100%; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-size: 16px; font-weight: 600; }
.search-bar { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.action-btns { display: flex; flex-wrap: nowrap; align-items: center; gap: 0; }
</style>
