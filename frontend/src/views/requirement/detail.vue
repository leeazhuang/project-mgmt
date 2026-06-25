<template>
  <div class="page-container">
    <div class="page-header">
      <el-button :icon="ArrowLeft" @click="$router.back()">返回</el-button>
      <h2>需求详情</h2>
    </div>

    <el-card v-loading="loading" class="req-info-card">
      <div class="req-header">
        <div class="req-title">
          <h3>{{ req.title }}</h3>
          <el-tag :type="statusMap[req.status]?.type" size="large">{{ statusMap[req.status]?.label || req.status }}</el-tag>
        </div>
        <div class="req-actions">
          <!-- 草稿/已拒绝 → 提交需求（仅创建人） -->
          <template v-if="(req.status === 'draft' || req.status === 'rejected') && isCreator">
            <el-button type="primary" @click="handleSubmitReq">提交需求</el-button>
          </template>
          <!-- 待处理 → 接受/拒绝（项目负责人） -->
          <template v-if="req.status === 'pending' && isProjectOwner">
            <el-button type="success" @click="handleApprove(true)">接受需求</el-button>
            <el-button type="danger" @click="handleApprove(false)">拒绝需求</el-button>
          </template>
          <!-- 已通过/开发中 → 创建任务（项目负责人/技术负责人），需先设置预计截止时间 -->
          <template v-if="(req.status === 'approved' || req.status === 'developing') && (isTechLeader || isProjectOwner)">
            <el-tooltip v-if="!req.estimated_deadline" content="请先设置预计截止时间" placement="top">
              <el-button type="primary" disabled>创建任务</el-button>
            </el-tooltip>
            <el-button v-else type="primary" @click="openTaskDialog">创建任务</el-button>
          </template>
          <!-- 开发中 → 延期（项目负责人/技术负责人） -->
          <template v-if="req.status === 'developing' && (isProjectOwner || isTechLeader)">
            <el-button type="warning" plain @click="openDelayDialog">延期</el-button>
          </template>
          <!-- 开发中 → 标记完成（技术负责人） -->
          <template v-if="req.status === 'developing' && isTechLeader">
            <el-button type="success" @click="handleChangeStatus('closed', '确定标记为已完成？')">标记完成</el-button>
          </template>
          <!-- 已完成 → 重开（项目负责人/技术负责人） -->
          <template v-if="req.status === 'closed' && (isProjectOwner || isTechLeader)">
            <el-button type="warning" @click="handleChangeStatus('developing', '确定重新打开该需求？')">重新打开</el-button>
          </template>
          <!-- 任何时候 → 作废（项目负责人/技术负责人） -->
          <template v-if="req.status !== 'voided' && (isProjectOwner || isTechLeader)">
            <el-button type="danger" plain @click="openVoidDialog">作废需求</el-button>
          </template>
        </div>
      </div>

      <el-descriptions :column="3" border style="margin-top:16px">
        <el-descriptions-item label="所属项目">{{ req.project_name || req.project?.name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="优先级">
          <el-tag :type="priorityMap[req.priority]?.type" size="small">{{ priorityMap[req.priority]?.label || req.priority }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建人">{{ req.creator?.real_name || req.creator?.username || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ req.created_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ req.updated_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="预计截止时间">
          <template v-if="req.estimated_deadline">{{ req.estimated_deadline }}</template>
          <template v-else-if="isTechLeader && (req.status === 'approved' || req.status === 'developing')">
            <el-date-picker v-model="estimatedDeadline" type="date" value-format="YYYY-MM-DD" placeholder="设置截止时间" size="small" style="width:160px" />
            <el-button type="primary" size="small" style="margin-left:8px" @click="handleSetDeadline">确定</el-button>
          </template>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item v-if="req.reject_reason" label="拒绝原因">
          <span style="color:#f56c6c">{{ req.reject_reason }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 需求描述单独展示 -->
      <div class="desc-section">
        <div class="desc-label">需求描述</div>
        <div class="desc-body">
          <div v-if="req.description" class="rich-content" v-html="req.description"></div>
          <span v-else style="color:#999">暂无描述</span>
        </div>
      </div>
    </el-card>

    <el-tabs v-model="activeTab" class="detail-tabs">
      <!-- Flow Timeline -->
      <el-tab-pane label="流转记录" name="approval">
        <el-timeline v-if="approvalLogs.length">
          <el-timeline-item
            v-for="log in approvalLogs"
            :key="log.id"
            :timestamp="log.created_at"
            :type="['approve','approved','done','closed'].includes(log.action) ? 'success' : ['reject','rejected'].includes(log.action) ? 'danger' : ['reopen','developing'].includes(log.action) ? 'warning' : 'primary'"
          >
            <div class="timeline-content">
              <span class="operator">{{ log.operator?.real_name || log.operator?.username }}</span>
              <el-tag :type="['approve','approved','done','closed'].includes(log.action) ? 'success' : ['reject','rejected'].includes(log.action) ? 'danger' : ['reopen','developing'].includes(log.action) ? 'warning' : 'info'" size="small">
                {{ actionLabel[log.action] || log.action }}
              </el-tag>
              <div v-if="log.remark" class="remark">{{ log.remark }}</div>
            </div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无流转记录" />
      </el-tab-pane>

      <!-- Tasks Tab -->
      <el-tab-pane v-if="showTasksTab" label="关联任务" name="tasks">
        <el-table :data="tasks" border stripe>
          <el-table-column prop="title" label="任务标题" min-width="200" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="taskStatusMap[row.status]?.type" size="small">{{ taskStatusMap[row.status]?.label || row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="指派给" min-width="140">
            <template #default="{ row }">
              <template v-if="row.assignees && row.assignees.length">
                {{ row.assignees.map(a => a.user?.real_name || a.user?.username).filter(Boolean).join('、') }}
              </template>
              <template v-else>{{ row.assignee?.real_name || row.assignee?.username || '未指派' }}</template>
            </template>
          </el-table-column>
          <el-table-column label="预估工时" width="100">
            <template #default="{ row }">{{ row.estimated_hours || '-' }}h</template>
          </el-table-column>
          <el-table-column prop="end_date" label="截止日期" width="120" />
        </el-table>
      </el-tab-pane>

      <!-- Comments Tab -->
      <el-tab-pane label="评论" name="comments">
        <div class="comment-list">
          <div v-for="c in comments" :key="c.id" class="comment-item">
            <el-avatar :size="32">{{ (c.user?.real_name || c.user?.username || '?').charAt(0) }}</el-avatar>
            <div class="comment-body">
              <div class="comment-meta">
                <span class="commenter">{{ c.user?.real_name || c.user?.username }}</span>
                <span class="comment-time">{{ c.created_at }}</span>
              </div>
              <div class="comment-text" v-html="renderMentions(c.content)"></div>
              <div v-if="c.children && c.children.length" class="comment-replies">
                <div v-for="r in c.children" :key="r.id" class="comment-item reply-item">
                  <el-avatar :size="28">{{ (r.user?.real_name || r.user?.username || '?').charAt(0) }}</el-avatar>
                  <div class="comment-body">
                    <div class="comment-meta">
                      <span class="commenter">{{ r.user?.real_name || r.user?.username }}</span>
                      <span class="comment-time">{{ r.created_at }}</span>
                    </div>
                    <div class="comment-text" v-html="renderMentions(r.content)"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <el-empty v-if="!comments.length" description="暂无评论" />
        </div>
        <div class="comment-input">
          <div class="mention-input-wrapper">
            <el-input
              ref="commentInputRef"
              v-model="newComment"
              type="textarea"
              rows="3"
              placeholder="写下你的评论... 输入@可提及项目成员"
              @input="onCommentInput"
              @keydown="onCommentKeydown"
            />
            <div v-if="showMentionList" class="mention-dropdown">
              <div
                v-for="(m, idx) in filteredMembers"
                :key="m.key"
                class="mention-item"
                :class="{ active: idx === mentionIndex }"
                @mousedown.prevent="selectMention(m)"
              >
                <el-avatar :size="24">{{ (m.insert || '?').charAt(0) }}</el-avatar>
                <span>{{ m.label }}</span>
              </div>
              <div v-if="!filteredMembers.length" class="mention-item empty">无匹配成员</div>
            </div>
          </div>
          <div style="display:flex;justify-content:flex-end;margin-top:8px">
            <el-button type="primary" @click="submitComment">发表评论</el-button>
          </div>
        </div>
      </el-tab-pane>

      <!-- Attachments Tab -->
      <el-tab-pane label="附件" name="attachments">
        <el-upload
          :action="`/api/attachments`"
          :headers="uploadHeaders"
          :data="{ target_type: 'requirement', target_id: reqId }"
          :on-success="onUploadSuccess"
          :show-file-list="false"
        >
          <el-button type="primary" :icon="Upload">上传附件</el-button>
        </el-upload>
        <el-table :data="attachments" border stripe style="margin-top:12px" v-if="attachments.length">
          <el-table-column prop="file_name" label="文件名" min-width="200" />
          <el-table-column prop="file_size" label="大小" width="100">
            <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
          </el-table-column>
          <el-table-column label="上传人" width="100">
            <template #default="{ row }">{{ row.uploader?.real_name || '-' }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="上传时间" width="160" />
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button type="primary" size="small" text @click="downloadFile(row)">下载</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无附件" />
      </el-tab-pane>
    </el-tabs>

    <!-- Reject Dialog -->
    <el-dialog v-model="rejectVisible" title="拒绝需求" width="400px">
      <el-input v-model="rejectReason" type="textarea" rows="3" placeholder="请输入拒绝原因" />
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" @click="submitReject">确定拒绝</el-button>
      </template>
    </el-dialog>

    <!-- Void Dialog -->
    <el-dialog v-model="voidVisible" title="作废需求" width="450px">
      <el-alert type="warning" :closable="false" style="margin-bottom:16px">
        作废后需求及关联任务将全部作废，不可恢复。
      </el-alert>
      <el-input v-model="voidRemark" type="textarea" rows="3" placeholder="请输入作废原因（必填）" />
      <template #footer>
        <el-button @click="voidVisible = false">取消</el-button>
        <el-button type="danger" @click="submitVoid">确定作废</el-button>
      </template>
    </el-dialog>

    <!-- Delay Dialog -->
    <el-dialog v-model="delayVisible" title="需求延期" width="450px">
      <el-form label-width="110px">
        <el-form-item label="当前预计截止">{{ req.estimated_deadline || '未设置' }}</el-form-item>
        <el-form-item label="延期至" required>
          <el-date-picker v-model="delayDate" type="date" value-format="YYYY-MM-DD" placeholder="选择新的预计截止时间" style="width:100%" />
        </el-form-item>
        <el-form-item label="延期原因" required>
          <el-input v-model="delayReason" type="textarea" rows="3" placeholder="请输入延期原因（必填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="delayVisible = false">取消</el-button>
        <el-button type="primary" @click="submitDelay">确定延期</el-button>
      </template>
    </el-dialog>

    <!-- Create Task Dialog -->
    <el-dialog v-model="taskDialogVisible" title="创建任务" width="600px" :close-on-click-modal="false">
      <el-form ref="taskFormRef" :model="taskForm" :rules="taskRules" label-width="100px">
        <el-form-item label="任务标题" prop="title">
          <el-input v-model="taskForm.title" placeholder="请输入任务标题" />
        </el-form-item>
        <el-form-item label="任务描述">
          <RichEditor v-model="taskForm.description" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="taskForm.priority">
            <el-radio value="urgent">紧急</el-radio>
            <el-radio value="high">高</el-radio>
            <el-radio value="medium">中</el-radio>
            <el-radio value="low">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="指派给" prop="assignee_sel">
          <el-select v-model="taskForm.assignee_sel" multiple filterable placeholder="选择项目成员（可多选，有标签的按标签选）" style="width:100%">
            <el-option v-for="o in taskAssignOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="预估工时">
          <el-input-number v-model="taskForm.estimated_hours" :min="0" :step="0.5" />
          <span style="margin-left:8px">小时</span>
        </el-form-item>
        <el-form-item label="预计开始时间">
          <el-date-picker v-model="taskForm.planned_start_date" type="date" value-format="YYYY-MM-DD" placeholder="选择预计开始时间" style="width:100%" />
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker v-model="taskForm.end_date" type="date" value-format="YYYY-MM-DD" placeholder="选择截止日期" style="width:100%" />
        </el-form-item>
        <el-form-item label="附件">
          <el-upload
            :action="`/api/attachments`"
            :headers="taskUploadHeaders"
            :data="{ target_type: 'task', target_id: 0 }"
            :on-success="onTaskUploadSuccess"
            :show-file-list="false"
            style="display:inline-block"
          >
            <el-button type="primary" size="small" :icon="Upload">上传附件</el-button>
          </el-upload>
          <div v-if="taskPendingFiles.length" style="margin-top:8px">
            <div v-for="file in taskPendingFiles" :key="file.id" style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
              <el-link type="primary">{{ file.file_name }}</el-link>
              <el-button type="danger" size="small" text @click="removeTaskFile(file)">移除</el-button>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taskDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="taskSubmitting" @click="handleCreateTask">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Upload } from '@element-plus/icons-vue'
import RichEditor from '@/components/RichEditor.vue'
import { getRequirement, submitRequirement, approveRequirement, listRequirementLogs, changeRequirementStatus, setEstimatedDeadline, delayRequirement } from '@/api/requirement'
import { listTasks, createTask } from '@/api/task'
import { listComments, createComment } from '@/api/comment'
import { listAttachments, getDownloadUrl, bindAttachments, deleteAttachment } from '@/api/attachment'
import { listMembers } from '@/api/project'
import { useUserStore } from '@/store/user'

const route = useRoute()
const reqId = route.params.id
const userStore = useUserStore()
const currentUserId = userStore.userInfo?.id

const loading = ref(false)
const req = ref({})
const approvalLogs = ref([])
const tasks = ref([])
const comments = ref([])
const attachments = ref([])
const activeTab = ref('approval')
const newComment = ref('')
const rejectVisible = ref(false)
const rejectReason = ref('')
const projectMembers = ref([])

// Task dialog
const taskDialogVisible = ref(false)
const taskSubmitting = ref(false)
const taskFormRef = ref(null)
const taskForm = ref({
  title: '', description: '', priority: 'medium',
  assignee_sel: [], estimated_hours: 0, planned_start_date: '', end_date: ''
})
const taskRules = {
  title: [{ required: true, message: '请输入任务标题', trigger: 'blur' }],
  assignee_sel: [{ required: true, message: '请选择指派人', trigger: 'change', type: 'array', min: 1 }]
}

// 指派下拉：有标签的成员按标签拆成多个选项，无标签出真名；value 编码 "user_id::标签"
const taskAssignOptions = computed(() => {
  const opts = []
  for (const m of projectMembers.value) {
    const uid = m.user_id || m.id
    const name = m.real_name || m.username
    const tags = m.display_tags || []
    opts.push({ value: `${uid}::`, label: name })
    tags.forEach(t => opts.push({ value: `${uid}::${t}`, label: `${t}（${name}）` }))
  }
  return opts
})

function parseTaskSel(selList) {
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

const taskUploadHeaders = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('token')}` }))
const taskPendingFiles = ref([])

const estimatedDeadline = ref('')
const voidVisible = ref(false)
const voidRemark = ref('')
const delayVisible = ref(false)
const delayDate = ref('')
const delayReason = ref('')
const commentInputRef = ref(null)
const showMentionList = ref(false)
const mentionIndex = ref(0)
const mentionSearch = ref('')

const uploadHeaders = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('token')}` }))

// 判断当前用户是否是该项目的负责人
const isProjectOwner = computed(() => {
  if (userStore.hasPermission('super_admin_bypass')) return true
  const roles = userStore.userInfo?.roles || []
  if (roles.includes('super_admin') || roles.some(r => r === 'super_admin' || r?.code === 'super_admin')) return true
  return req.value._project_owner_id === currentUserId
})

// 判断当前用户是否是该项目的技术负责人
const isTechLeader = computed(() => {
  const roles = userStore.userInfo?.roles || []
  if (roles.includes('super_admin') || roles.some(r => r === 'super_admin' || r?.code === 'super_admin')) return true
  return req.value._project_tech_leader_id === currentUserId
})

// 判断是否是需求创建人
const isCreator = computed(() => {
  return req.value.creator?.id === currentUserId
})

// 关联任务 tab 在 approved / developing / done / closed 状态都显示
const showTasksTab = computed(() => {
  return ['approved', 'developing', 'done', 'closed'].includes(req.value.status)
})

const statusMap = {
  draft: { label: '草稿', type: 'info' },
  pending: { label: '待处理', type: 'warning' },
  approved: { label: '已接受', type: 'success' },
  rejected: { label: '已拒绝', type: 'danger' },
  developing: { label: '开发中', type: '' },
  closed: { label: '已完成', type: 'success' },
  voided: { label: '已作废', type: 'danger' }
}
const priorityMap = {
  urgent: { label: '紧急', type: 'danger' },
  high: { label: '高', type: 'warning' },
  medium: { label: '中', type: '' },
  low: { label: '低', type: 'info' }
}
const taskStatusMap = {
  pending: { label: '待处理', type: 'info' },
  in_progress: { label: '进行中', type: 'warning' },
  done: { label: '已完成', type: 'success' },
  voided: { label: '已作废', type: 'danger' }
}
const actionLabel = {
  submit: '提交需求', submitted: '提交需求',
  approve: '接受需求', approved: '接受需求',
  reject: '拒绝需求', rejected: '拒绝需求',
  created: '创建需求',
  assign_task: '分配任务',
  developing: '进入开发',
  done: '开发完成',
  closed: '验收关闭',
  reopen: '重新打开',
  voided: '作废需求',
  set_deadline: '设置预计截止时间',
  delay: '延期',
}

async function loadReq() {
  loading.value = true
  try {
    const data = await getRequirement(reqId)
    // 加载项目信息获取负责人和技术负责人 ID
    if (data.project_id) {
      try {
        const { getProject } = await import('@/api/project')
        const project = await getProject(data.project_id)
        data._project_owner_id = project.owner?.id
        data._project_tech_leader_id = project.tech_leader?.id
      } catch (e) {}
    }
    // 一次性赋值，确保响应式
    req.value = { ...data }
  } catch (e) {
  } finally {
    loading.value = false
  }
}

async function loadLogs() {
  try {
    const res = await listRequirementLogs(reqId)
    approvalLogs.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) {
    approvalLogs.value = []
  }
}

async function loadTasks() {
  try {
    const res = await listTasks({ requirement_id: reqId, page: 1, page_size: 100 })
    tasks.value = res.items || res || []
  } catch (e) {
    tasks.value = []
  }
}

async function loadComments() {
  try {
    const res = await listComments({ target_type: 'requirement', target_id: reqId })
    comments.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) {
    comments.value = []
  }
}

async function loadAttachments() {
  try {
    const res = await listAttachments({ target_type: 'requirement', target_id: reqId })
    attachments.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) {
    attachments.value = []
  }
}

async function loadProjectMembers() {
  if (!req.value.project_id) return
  try {
    const res = await listMembers(req.value.project_id)
    projectMembers.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) {
    projectMembers.value = []
  }
}

async function handleSetDeadline() {
  if (!estimatedDeadline.value) {
    ElMessage.warning('请选择预计截止时间')
    return
  }
  try {
    await setEstimatedDeadline(reqId, { estimated_deadline: estimatedDeadline.value })
    ElMessage.success('设置成功')
    loadReq()
    loadLogs()
  } catch (e) {}
}

async function handleSubmitReq() {
  try {
    await submitRequirement(reqId)
    ElMessage.success('已提交需求')
    loadReq()
    loadLogs()
  } catch (e) {}
}

async function handleApprove(pass) {
  if (!pass) {
    rejectVisible.value = true
    return
  }
  try {
    await approveRequirement(reqId, { action: 'approve' })
    ElMessage.success('已接受需求')
    loadReq()
    loadLogs()
  } catch (e) {}
}

async function submitReject() {
  try {
    await approveRequirement(reqId, { action: 'reject', remark: rejectReason.value })
    ElMessage.success('已拒绝')
    rejectVisible.value = false
    rejectReason.value = ''
    loadReq()
    loadLogs()
  } catch (e) {}
}

async function handleChangeStatus(newStatus, confirmMsg) {
  try {
    await ElMessageBox.confirm(confirmMsg, '提示', {
      confirmButtonText: '确定', cancelButtonText: '取消', type: 'info'
    })
  } catch (e) {
    return
  }
  try {
    await changeRequirementStatus(reqId, { status: newStatus })
    ElMessage.success('操作成功')
    loadReq()
    loadLogs()
  } catch (e) {}
}

function openVoidDialog() {
  voidRemark.value = ''
  voidVisible.value = true
}

async function submitVoid() {
  if (!voidRemark.value.trim()) {
    ElMessage.warning('请输入作废原因')
    return
  }
  try {
    await changeRequirementStatus(reqId, { status: 'voided', remark: voidRemark.value })
    ElMessage.success('需求已作废')
    voidVisible.value = false
    loadReq()
    loadLogs()
    loadTasks()
  } catch (e) {}
}

function openDelayDialog() {
  delayDate.value = ''
  delayReason.value = ''
  delayVisible.value = true
}

async function submitDelay() {
  if (!delayDate.value) {
    ElMessage.warning('请选择延期至的日期')
    return
  }
  if (!delayReason.value.trim()) {
    ElMessage.warning('请输入延期原因')
    return
  }
  try {
    await delayRequirement(reqId, { estimated_deadline: delayDate.value, reason: delayReason.value })
    ElMessage.success('延期成功')
    delayVisible.value = false
    loadReq()
    loadLogs()
  } catch (e) {}
}

function onTaskUploadSuccess(res) {
  const file = res?.data || res
  if (file?.id) taskPendingFiles.value.push(file)
  ElMessage.success('上传成功')
}

function removeTaskFile(file) {
  taskPendingFiles.value = taskPendingFiles.value.filter(f => f.id !== file.id)
  deleteAttachment(file.id).catch(() => {})
}

function openTaskDialog() {
  taskPendingFiles.value = []
  taskForm.value = {
    title: '', description: '', priority: 'medium',
    assignee_sel: [], estimated_hours: 0, planned_start_date: '', end_date: ''
  }
  loadProjectMembers()
  taskDialogVisible.value = true
}

async function handleCreateTask() {
  const valid = await taskFormRef.value?.validate().catch(() => false)
  if (!valid) return
  taskSubmitting.value = true
  try {
    const { ids, tags } = parseTaskSel(taskForm.value.assignee_sel)
    const newTask = await createTask({
      requirement_id: Number(reqId),
      title: taskForm.value.title,
      description: taskForm.value.description,
      priority: taskForm.value.priority,
      assignee_ids: ids,
      assignee_tags: tags,
      estimated_hours: taskForm.value.estimated_hours,
      planned_start_date: taskForm.value.planned_start_date || null,
      end_date: taskForm.value.end_date || null
    })
    if (taskPendingFiles.value.length && newTask?.id) {
      await bindAttachments({
        attachment_ids: taskPendingFiles.value.map(f => f.id),
        target_type: 'task', target_id: newTask.id
      }).catch(() => {})
      taskPendingFiles.value = []
    }
    ElMessage.success('任务创建成功')
    taskDialogVisible.value = false
    loadTasks()
    loadReq() // 刷新需求状态（可能从 approved 变为 developing）
  } catch (e) {
  } finally {
    taskSubmitting.value = false
  }
}

// @提及 —— 当前用户是否「仅看分配标签」角色
const isTagOnly = computed(() => !!userStore.userInfo?.tag_only_view)

// @候选：真名 + 各标签都作为可@对象（标签=增加的"模拟人"，不隐藏真名）。
// 仅看标签角色标签不带归属（看起来像独立的人）；其他角色标签显示「标签（真名）」便于识别。
const mentionCandidates = computed(() => {
  const list = []
  for (const m of projectMembers.value) {
    const uid = m.user_id || m.id
    const name = m.real_name || m.username
    if (name) list.push({ uid, insert: name, label: name, key: `${uid}::` })
    for (const t of (m.display_tags || [])) {
      list.push({ uid, insert: t, label: isTagOnly.value ? t : `${t}（${name}）`, key: `${uid}::${t}` })
    }
  }
  return list
})

const filteredMembers = computed(() => {
  const kw = mentionSearch.value.toLowerCase()
  return mentionCandidates.value.filter(c =>
    c.label.toLowerCase().includes(kw) || c.insert.toLowerCase().includes(kw)
  ).slice(0, 10)
})

// 标签 → 归属真名（展示时给「标签@」标注是谁）
function findTagOwner(handle) {
  for (const m of projectMembers.value) {
    if ((m.display_tags || []).includes(handle)) return m.real_name || m.username
  }
  return ''
}

function onCommentInput() {
  const textarea = commentInputRef.value?.$el?.querySelector('textarea') || commentInputRef.value?.textarea
  if (!textarea) return
  const cursorPos = textarea.selectionStart
  const textBefore = newComment.value.substring(0, cursorPos)
  const atMatch = textBefore.match(/@([^@\s]*)$/)
  if (atMatch) {
    mentionSearch.value = atMatch[1]
    showMentionList.value = true
    mentionIndex.value = 0
  } else {
    showMentionList.value = false
  }
}

function onCommentKeydown(e) {
  if (!showMentionList.value) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    mentionIndex.value = Math.min(mentionIndex.value + 1, filteredMembers.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    mentionIndex.value = Math.max(mentionIndex.value - 1, 0)
  } else if (e.key === 'Enter' && filteredMembers.value.length) {
    e.preventDefault()
    selectMention(filteredMembers.value[mentionIndex.value])
  } else if (e.key === 'Escape') {
    showMentionList.value = false
  }
}

function selectMention(member) {
  const textarea = commentInputRef.value?.$el?.querySelector('textarea') || commentInputRef.value?.textarea
  if (!textarea) return
  const cursorPos = textarea.selectionStart
  const textBefore = newComment.value.substring(0, cursorPos)
  const textAfter = newComment.value.substring(cursorPos)
  const atMatch = textBefore.match(/@([^@\s]*)$/)
  if (atMatch) {
    const beforeAt = textBefore.substring(0, atMatch.index)
    newComment.value = beforeAt + '@' + member.insert + ' ' + textAfter
  }
  showMentionList.value = false
  nextTick(() => textarea.focus())
}

function extractMentionIds(text) {
  const ids = []
  const matches = text.match(/@(\S+)/g) || []
  // 句柄(真名或标签) → uid
  const lookup = {}
  for (const m of projectMembers.value) {
    const uid = m.user_id || m.id
    const name = m.real_name || m.username
    if (name && !(name in lookup)) lookup[name] = uid
    for (const t of (m.display_tags || [])) if (t && !(t in lookup)) lookup[t] = uid
  }
  for (const mt of matches) {
    const uid = lookup[mt.substring(1)]
    if (uid && !ids.includes(uid)) ids.push(uid)
  }
  return ids
}

function renderMentions(content) {
  if (!content) return ''
  // 仅看标签角色：后端已把按标签分配的真名换成标签，这里保持原样
  // 其他角色：把「标签」@渲染成「标签（真名）」便于识别是谁
  return content.replace(/@(\S+)/g, (full, handle) => {
    let shown = handle
    if (!isTagOnly.value) {
      const owner = findTagOwner(handle)
      if (owner && owner !== handle) shown = `${handle}（${owner}）`
    }
    return `<span class="mention-tag">@${shown}</span>`
  })
}

async function submitComment() {
  if (!newComment.value.trim()) {
    ElMessage.warning('请输入评论内容')
    return
  }
  try {
    const mentionIds = extractMentionIds(newComment.value)
    await createComment({
      target_type: 'requirement',
      target_id: Number(reqId),
      content: newComment.value,
      mention_user_ids: mentionIds
    })
    ElMessage.success('评论成功')
    newComment.value = ''
    loadComments()
  } catch (e) {}
}

function onUploadSuccess() {
  ElMessage.success('上传成功')
  loadAttachments()
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

onMounted(async () => {
  await loadReq()
  loadLogs()
  loadTasks()
  loadComments()
  loadAttachments()
  loadProjectMembers()
})
</script>

<style scoped>
.page-container { min-height: 100%; }
.page-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.page-header h2 { font-size: 20px; color: #333; }
.req-info-card { margin-bottom: 20px; }
.req-header { display: flex; justify-content: space-between; align-items: flex-start; }
.req-title { display: flex; align-items: center; gap: 12px; }
.req-title h3 { font-size: 18px; color: #333; }
.req-actions { display: flex; gap: 8px; }
.detail-tabs { background: #fff; border-radius: 4px; padding: 16px; }
/* @提及下拉向上弹出，el-tabs内容区默认overflow:hidden会裁剪下拉列表 */
.detail-tabs :deep(.el-tabs__content) { overflow: visible; }
.timeline-content { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.operator { font-weight: 500; }
.remark { color: #666; font-size: 13px; margin-top: 4px; width: 100%; }
.comment-list { margin-bottom: 20px; }
.comment-item { display: flex; gap: 12px; margin-bottom: 16px; }
.comment-body { flex: 1; }
.comment-meta { display: flex; gap: 12px; margin-bottom: 4px; }
.commenter { font-weight: 500; }
.comment-time { color: #999; font-size: 12px; }
.comment-text { color: #333; }
.comment-input { border-top: 1px solid #f0f0f0; padding-top: 16px; }
.comment-text :deep(.mention-tag) { color: #409eff; font-weight: 500; }
.comment-replies { margin-top: 8px; padding-left: 12px; border-left: 2px solid #f0f0f0; }
.reply-item { margin-bottom: 12px; }
.mention-input-wrapper { position: relative; }
.mention-dropdown {
  position: absolute;
  bottom: 100%;
  left: 0;
  width: 240px;
  max-height: 200px;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
  z-index: 2000;
  margin-bottom: 4px;
}
.mention-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
}
.mention-item:hover, .mention-item.active { background: #f5f7fa; }
.mention-item.empty { color: #999; cursor: default; }
/* 需求描述独立区块 */
.desc-section { margin-top: 16px; background: #fff; border: 1px solid #ebeef5; border-radius: 4px; }
.desc-label { padding: 12px 16px; font-weight: 600; color: #333; background: #fafafa; border-bottom: 1px solid #ebeef5; }
.desc-body { padding: 16px; min-height: 60px; }
/* 富文本内容样式 */
.rich-content { line-height: 1.8; word-break: break-word; }
.rich-content :deep(img) { max-width: 100%; height: auto; border-radius: 4px; }
.rich-content :deep(table) { border-collapse: collapse; width: 100%; }
.rich-content :deep(td), .rich-content :deep(th) { border: 1px solid #ddd; padding: 8px; }
</style>
