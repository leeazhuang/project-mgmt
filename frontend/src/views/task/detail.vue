<template>
  <div class="page-container">
    <div class="page-header">
      <el-button :icon="ArrowLeft" @click="$router.back()">返回</el-button>
      <h2>任务详情</h2>
    </div>

    <el-card v-loading="loading" class="task-info-card">
      <div class="task-header">
        <div class="task-title-row">
          <h3>{{ task.title }}</h3>
          <el-tag :type="statusMap[task.status]?.type" size="large">{{ statusMap[task.status]?.label || task.status }}</el-tag>
        </div>
        <div class="task-actions">
          <el-button v-if="myAssigneeStatus === 'pending'" type="primary" @click="changeMyStatus('in_progress')">开始任务</el-button>
          <el-button v-if="myAssigneeStatus === 'in_progress'" type="success" @click="changeMyStatus('done')">完成任务</el-button>
          <el-button v-if="canEditTask" type="primary" @click="openEditDialog">编辑任务</el-button>
          <el-button v-if="canReassign" type="warning" @click="openReassignDialog">重新指派</el-button>
        </div>
      </div>

      <el-descriptions :column="3" border style="margin-top:16px">
        <el-descriptions-item label="所属需求">{{ task.requirement_title || '-' }}</el-descriptions-item>
        <el-descriptions-item label="优先级">
          <el-tag :type="priorityMap[task.priority]?.type" size="small">{{ priorityMap[task.priority]?.label || task.priority }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="指派给">
          <template v-if="task.assignees && task.assignees.length">
            <el-tag v-for="(a, i) in task.assignees" :key="a.user_id || a.display_tag || i" size="small" style="margin-right:4px"
              :type="a.status === 'done' ? 'success' : a.status === 'in_progress' ? 'warning' : 'info'">
              {{ assigneeLabel(a) }}
              <span style="font-size:11px;margin-left:2px">({{ {pending:'待开始',in_progress:'进行中',done:'已完成'}[a.status] }})</span>
            </el-tag>
          </template>
          <span v-else>{{ task.assignee?.real_name || '未指派' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ task.created_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="预计开始">{{ task.planned_start_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="实际开始">{{ task.start_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="截止日期">
          <span>{{ task.end_date || '-' }}</span>
          <el-tag v-if="isDelayed(task)" type="danger" size="small" style="margin-left:4px">已延期</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="预估工时">{{ task.estimated_hours ? task.estimated_hours + 'h' : '-' }}</el-descriptions-item>
        <el-descriptions-item label="实际工时">{{ task.actual_hours ? task.actual_hours + 'h' : '-' }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ task.completed_at || '-' }}</el-descriptions-item>
      </el-descriptions>

      <div class="desc-section">
        <div class="desc-label">任务描述</div>
        <div class="desc-body">
          <div v-if="task.description" class="rich-content" v-html="task.description"></div>
          <span v-else style="color:#999">暂无描述</span>
        </div>
      </div>
    </el-card>

    <el-tabs v-model="activeTab" class="detail-tabs">
      <!-- 流转记录（仅看标签角色：后端已把真名脱敏成标签） -->
      <el-tab-pane label="流转记录" name="logs">
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
      </el-tab-pane>

      <!-- 评论 -->
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
            <!-- @提及下拉 -->
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

      <!-- 附件 -->
      <el-tab-pane label="附件" name="attachments">
        <el-upload
          :action="`/api/attachments`"
          :headers="uploadHeaders"
          :data="{ target_type: 'task', target_id: taskId }"
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

    <!-- 编辑任务Dialog -->
    <el-dialog v-model="editDialogVisible" title="编辑任务" width="700px" :close-on-click-modal="false">
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="100px">
        <el-form-item label="任务标题" prop="title">
          <el-input v-model="editForm.title" placeholder="请输入任务标题" />
        </el-form-item>
        <el-form-item label="任务描述">
          <RichEditor v-model="editForm.description" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="editForm.priority">
            <el-radio value="urgent">紧急</el-radio>
            <el-radio value="high">高</el-radio>
            <el-radio value="medium">中</el-radio>
            <el-radio value="low">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="指派给">
          <el-select v-model="editForm.assignee_sel" multiple filterable placeholder="请选择（可多选，有标签的按标签选）" style="width:100%">
            <el-option v-for="o in assignOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="预计开始时间">
          <el-date-picker v-model="editForm.planned_start_date" type="date" value-format="YYYY-MM-DD" placeholder="选择预计开始时间" style="width:100%" />
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker v-model="editForm.end_date" type="date" value-format="YYYY-MM-DD" placeholder="选择截止日期" style="width:100%" />
        </el-form-item>
        <el-form-item label="预估工时">
          <el-input-number v-model="editForm.estimated_hours" :min="0" :step="0.5" />
          <span style="margin-left:8px">小时</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="handleEditSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 重新指派Dialog -->
    <el-dialog v-model="reassignVisible" title="重新指派任务" width="400px">
      <el-alert type="warning" :closable="false" style="margin-bottom:16px">
        重新指派后任务状态将回到待处理，被分配人需重新操作。
      </el-alert>
      <el-form label-width="80px">
        <el-form-item label="指派给">
          <el-select v-model="reassignSel" multiple filterable placeholder="请选择项目成员（可多选，有标签的按标签选）" style="width:100%">
            <el-option v-for="o in assignOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reassignVisible = false">取消</el-button>
        <el-button type="primary" @click="handleReassign">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Upload } from '@element-plus/icons-vue'
import { getTask, updateTask, getTaskLogs } from '@/api/task'
import { listComments, createComment } from '@/api/comment'
import { listAttachments, getDownloadUrl } from '@/api/attachment'
import { listMembers } from '@/api/project'
import { useUserStore } from '@/store/user'
import RichEditor from '@/components/RichEditor.vue'

const route = useRoute()
const router = useRouter()
const taskId = route.params.id
const userStore = useUserStore()
const currentUserId = userStore.userInfo?.id

const loading = ref(false)
const task = ref({})
const taskLogs = ref([])
const comments = ref([])
const attachments = ref([])
const projectMembers = ref([])
const activeTab = ref('comments')
const newComment = ref('')
const commentInputRef = ref(null)

// 编辑
const editDialogVisible = ref(false)
const editSubmitting = ref(false)
const editFormRef = ref(null)
const editForm = ref({
  title: '', description: '', priority: 'medium', status: 'pending',
  assignee_sel: [], planned_start_date: '', end_date: '', estimated_hours: null
})
const editRules = { title: [{ required: true, message: '请输入任务标题', trigger: 'blur' }] }

// 重新指派
const reassignVisible = ref(false)
const reassignSel = ref([])

// 指派下拉：有标签的成员按标签拆成多个选项，无标签出真名；value 编码 "user_id::标签"
const assignOptions = computed(() => {
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

function assigneeLabel(a) {
  const tag = a.display_tag
  const name = a.user?.real_name || a.user?.username
  if (tag) return name ? `${tag}（${name}）` : tag
  return name || '未指派'
}

// @提及
const showMentionList = ref(false)
const mentionIndex = ref(0)
const mentionSearch = ref('')

const uploadHeaders = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('token')}` }))

const statusMap = {
  pending: { label: '待处理', type: 'info' },
  in_progress: { label: '进行中', type: 'warning' },
  done: { label: '已完成', type: 'success' },
  voided: { label: '已作废', type: 'danger' }
}
const priorityMap = {
  urgent: { label: '紧急', type: 'danger' },
  high: { label: '高', type: 'warning' },
  medium: { label: '中', type: '' },
  low: { label: '低', type: 'info' }
}
const actionLabelMap = {
  create: '创建任务', start: '开始任务', done: '完成任务',
  delay: '任务延期', reassign: '重新指派', reopen: '重新打开', update: '更新任务', void: '任务作废'
}
const actionTypeMap = {
  create: 'primary', start: '', done: 'success',
  delay: 'warning', reassign: 'info', reopen: 'warning', update: 'info', void: 'danger'
}

function _isSuperAdmin() {
  const roles = userStore.userInfo?.roles || []
  return roles.includes('super_admin') || roles.some(r => r === 'super_admin' || r?.code === 'super_admin')
}

// 任务待处理时，项目负责人/技术负责人可编辑；进行中/已完成不可编辑
const canEditTask = computed(() => {
  if (task.value.status !== 'pending') return false
  if (_isSuperAdmin()) return true
  const uid = currentUserId
  return uid === task.value.project_owner_id || uid === task.value.project_tech_leader_id
})

// 待开始或进行中时，负责人/技术负责人可重新指派（已完成/已作废不能再指派）
const canReassign = computed(() => {
  if (!['in_progress', 'pending'].includes(task.value.status)) return false
  if (_isSuperAdmin()) return true
  const uid = currentUserId
  return uid === task.value.project_owner_id || uid === task.value.project_tech_leader_id
})

// 当前用户在任务中的个人状态
const myAssigneeStatus = computed(() => {
  const uid = currentUserId
  if (task.value.assignees && task.value.assignees.length) {
    const mine = task.value.assignees.find(a => a.user_id === uid || a.user?.id === uid)
    return mine ? mine.status : null
  }
  if (task.value.assignee?.id === uid) return task.value.status
  return null
})

async function changeMyStatus(newStatus) {
  try {
    await updateTask(taskId, { status: newStatus })
    ElMessage.success(newStatus === 'in_progress' ? '已开始' : '已完成')
    loadTask()
    loadLogs()
  } catch (e) {}
}

function isDelayed(row) {
  if (row.status === 'done' || row.status === 'voided') return false
  if (!row.end_date) return false
  return new Date(row.end_date) < new Date(new Date().toISOString().split('T')[0])
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

function onCommentInput(val) {
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

// 从评论内容中提取被@的用户ID
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

async function loadTask() {
  loading.value = true
  try {
    const data = await getTask(taskId)
    // 获取项目信息
    if (data.project_id) {
      try {
        const { getProject } = await import('@/api/project')
        const project = await getProject(data.project_id)
        data.project_owner_id = project.owner?.id
        data.project_tech_leader_id = project.tech_leader?.id
        data.project_name = project.name
      } catch (e) {}
    }
    task.value = { ...data }
  } catch (e) {
  } finally {
    loading.value = false
  }
}

async function loadLogs() {
  try {
    const res = await getTaskLogs(taskId)
    taskLogs.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) { taskLogs.value = [] }
}

async function loadComments() {
  try {
    const res = await listComments({ target_type: 'task', target_id: taskId })
    comments.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) { comments.value = [] }
}

async function loadAttachments() {
  try {
    const res = await listAttachments({ target_type: 'task', target_id: taskId })
    attachments.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) { attachments.value = [] }
}

async function loadProjectMembers() {
  if (!task.value.project_id) return
  try {
    const res = await listMembers(task.value.project_id)
    projectMembers.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) { projectMembers.value = [] }
}

async function submitComment() {
  if (!newComment.value.trim()) {
    ElMessage.warning('请输入评论内容')
    return
  }
  try {
    const mentionIds = extractMentionIds(newComment.value)
    await createComment({
      target_type: 'task',
      target_id: Number(taskId),
      content: newComment.value,
      mention_user_ids: mentionIds
    })
    ElMessage.success('评论成功')
    newComment.value = ''
    loadComments()
  } catch (e) {}
}

function openEditDialog() {
  editForm.value = {
    title: task.value.title || '',
    description: task.value.description || '',
    priority: task.value.priority || 'medium',
    status: task.value.status || 'pending',
    assignee_sel: (task.value.assignees || [])
      .filter(a => a.user_id)
      .map(a => `${a.user_id}::${a.display_tag || ''}`),
    planned_start_date: task.value.planned_start_date || '',
    end_date: task.value.end_date || '',
    estimated_hours: task.value.estimated_hours || null
  }
  loadProjectMembers()
  editDialogVisible.value = true
}

async function handleEditSubmit() {
  const valid = await editFormRef.value?.validate().catch(() => false)
  if (!valid) return
  editSubmitting.value = true
  try {
    const { ids, tags } = parseSelList(editForm.value.assignee_sel)
    await updateTask(taskId, {
      title: editForm.value.title,
      description: editForm.value.description,
      priority: editForm.value.priority,
      assignee_ids: ids,
      assignee_tags: tags,
      planned_start_date: editForm.value.planned_start_date || null,
      end_date: editForm.value.end_date || null,
      estimated_hours: editForm.value.estimated_hours
    })
    ElMessage.success('更新成功')
    editDialogVisible.value = false
    loadTask()
    loadLogs()
  } catch (e) {
  } finally {
    editSubmitting.value = false
  }
}

function openReassignDialog() {
  reassignSel.value = (task.value.assignees || [])
    .filter(a => a.user_id)
    .map(a => `${a.user_id}::${a.display_tag || ''}`)
  loadProjectMembers()
  reassignVisible.value = true
}

async function handleReassign() {
  if (!reassignSel.value.length) { ElMessage.warning('请选择指派人'); return }
  const { ids, tags } = parseSelList(reassignSel.value)
  try {
    await updateTask(taskId, { assignee_ids: ids, assignee_tags: tags })
    ElMessage.success('重新指派成功')
    reassignVisible.value = false
    loadTask()
    loadLogs()
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
  await loadTask()
  loadLogs()
  loadComments()
  loadAttachments()
  loadProjectMembers()
})
</script>

<style scoped>
.page-container { min-height: 100%; }
.page-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.page-header h2 { font-size: 20px; color: #333; }
.task-info-card { margin-bottom: 20px; }
.task-header { display: flex; justify-content: space-between; align-items: flex-start; }
.task-title-row { display: flex; align-items: center; gap: 12px; }
.task-title-row h3 { font-size: 18px; color: #333; }
.task-actions { display: flex; gap: 8px; }
.detail-tabs { background: #fff; border-radius: 4px; padding: 16px; }
/* @提及下拉向上弹出，el-tabs内容区默认overflow:hidden会裁剪下拉列表 */
.detail-tabs :deep(.el-tabs__content) { overflow: visible; }

.desc-section { margin-top: 16px; background: #fff; border: 1px solid #ebeef5; border-radius: 4px; }
.desc-label { padding: 12px 16px; font-weight: 600; color: #333; background: #fafafa; border-bottom: 1px solid #ebeef5; }
.desc-body { padding: 16px; min-height: 60px; }
.rich-content { line-height: 1.8; word-break: break-word; }
.rich-content :deep(img) { max-width: 100%; height: auto; border-radius: 4px; }

.comment-list { margin-bottom: 20px; }
.comment-item { display: flex; gap: 12px; margin-bottom: 16px; }
.comment-body { flex: 1; }
.comment-meta { display: flex; gap: 12px; margin-bottom: 4px; }
.commenter { font-weight: 500; }
.comment-time { color: #999; font-size: 12px; }
.comment-text { color: #333; line-height: 1.6; }
.comment-text :deep(.mention-tag) { color: #409eff; font-weight: 500; }
.comment-replies { margin-top: 8px; padding-left: 12px; border-left: 2px solid #f0f0f0; }
.reply-item { margin-bottom: 12px; }
.comment-input { border-top: 1px solid #f0f0f0; padding-top: 16px; }

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
</style>
