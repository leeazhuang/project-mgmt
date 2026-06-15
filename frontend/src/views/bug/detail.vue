<template>
  <div class="page-container">
    <div class="page-header">
      <el-button :icon="ArrowLeft" @click="$router.back()">返回</el-button>
      <h2>Bug详情</h2>
    </div>

    <el-card v-loading="loading" class="bug-info-card">
      <div class="bug-header">
        <div class="bug-title-row">
          <h3>{{ bug.title }}</h3>
          <el-tag :type="statusMap[bug.status]?.type" size="large">{{ statusMap[bug.status]?.label || bug.status }}</el-tag>
        </div>
        <div class="bug-actions">
          <!-- 待处理 → 指派/拒绝（技术负责人） -->
          <template v-if="bug.status === 'pending' && isTechLeader">
            <el-button type="primary" @click="openAssignDialog">指派</el-button>
            <el-button type="danger" plain @click="handleReject">拒绝</el-button>
          </template>
          <!-- 已指派 → 开始修复（被分配人） -->
          <template v-if="bug.status === 'assigned' && isAssignee">
            <el-button type="primary" @click="handleStartFix">开始修复</el-button>
          </template>
          <!-- 修复中 → 标记已解决（被分配人），直接关闭 -->
          <template v-if="bug.status === 'fixing' && isAssignee">
            <el-button type="success" @click="handleMarkFixed">标记已解决</el-button>
          </template>
          <!-- 已修复 → 发起人可重开（问题未解决时） -->
          <template v-if="bug.status === 'verified' && isCreator">
            <el-button type="warning" @click="openReopenDialog">重开Bug</el-button>
          </template>
          <!-- 进行中状态下技术负责人可重新指派 -->
          <template v-if="['assigned','fixing'].includes(bug.status) && isTechLeader">
            <el-button type="warning" @click="openReassignDialog">重新指派</el-button>
          </template>
        </div>
      </div>

      <el-descriptions :column="3" border style="margin-top:16px">
        <el-descriptions-item label="所属项目">{{ bug.project?.name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="严重程度">
          <el-tag :type="severityMap[bug.severity]?.type" size="small">{{ severityMap[bug.severity]?.label || bug.severity }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="优先级">
          <el-tag :type="priorityMap[bug.priority]?.type" size="small">{{ priorityMap[bug.priority]?.label || bug.priority }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建人">{{ bug.creator?.real_name || bug.creator?.username || '-' }}</el-descriptions-item>
        <el-descriptions-item label="指派给">{{ bug.assignee?.real_name || bug.assignee?.username || '未指派' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ bug.created_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="环境信息">{{ bug.environment || '-' }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ bug.updated_at || '-' }}</el-descriptions-item>
        <el-descriptions-item v-if="bug.reject_reason" label="拒绝原因">
          <span style="color:#f56c6c">{{ bug.reject_reason }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <div class="desc-section">
        <div class="desc-label">Bug描述</div>
        <div class="desc-body">
          <div v-if="bug.description" class="rich-content" v-html="bug.description"></div>
          <span v-else style="color:#999">暂无描述</span>
        </div>
      </div>
    </el-card>

    <el-tabs v-model="activeTab" class="detail-tabs">
      <!-- 流转记录 -->
      <el-tab-pane label="流转记录" name="logs">
        <el-timeline v-if="bugLogs.length">
          <el-timeline-item
            v-for="log in bugLogs"
            :key="log.id"
            :timestamp="log.created_at"
            :type="logActionType[log.action] || 'info'"
          >
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
              <span style="font-weight:500">{{ log.operator?.real_name || log.operator?.username }}</span>
              <el-tag :type="logActionType[log.action] || 'info'" size="small">{{ logActionLabel[log.action] || log.action }}</el-tag>
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
            <div v-if="showMentionList" class="mention-dropdown">
              <div
                v-for="(m, idx) in filteredMembers"
                :key="m.user_id || m.id"
                class="mention-item"
                :class="{ active: idx === mentionIndex }"
                @mousedown.prevent="selectMention(m)"
              >
                <el-avatar :size="24">{{ (m.real_name || m.username || '?').charAt(0) }}</el-avatar>
                <span>{{ m.real_name || m.username }}</span>
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
          :data="{ target_type: 'bug', target_id: bugId }"
          :on-success="onUploadSuccess"
          :show-file-list="false"
        >
          <el-button type="primary" :icon="Upload">上传附件</el-button>
        </el-upload>
        <el-table :data="attachments" border stripe style="margin-top:12px">
          <el-table-column prop="file_name" label="文件名" min-width="200" />
          <el-table-column prop="file_size" label="大小" width="100">
            <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="上传时间" width="160" />
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button type="primary" size="small" text @click="downloadFile(row)">下载</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- Assign Dialog -->
    <el-dialog v-model="assignVisible" :title="assignDialogTitle" width="400px">
      <el-form label-width="80px">
        <el-form-item label="指派给">
          <el-select v-model="assignUserId" filterable placeholder="请选择项目成员" style="width:100%">
            <el-option v-for="m in projectMembers" :key="m.user_id || m.id" :label="m.real_name || m.username" :value="m.user_id || m.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAssign">确定</el-button>
      </template>
    </el-dialog>

    <!-- Reject Dialog -->
    <el-dialog v-model="rejectVisible" title="拒绝Bug" width="400px">
      <el-input v-model="rejectReason" type="textarea" rows="3" placeholder="请输入拒绝原因" />
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" @click="submitReject">确定拒绝</el-button>
      </template>
    </el-dialog>

    <!-- Reopen Dialog -->
    <el-dialog v-model="reopenVisible" title="重开Bug" width="400px">
      <el-input v-model="reopenReason" type="textarea" rows="3" placeholder="请输入重开原因（问题未解决的具体描述）" />
      <template #footer>
        <el-button @click="reopenVisible = false">取消</el-button>
        <el-button type="warning" @click="submitReopen">确定重开</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Upload } from '@element-plus/icons-vue'
import { getBug, assignBug, reassignBug, rejectBug, startFix, markFixed, reopenBug, getBugLogs } from '@/api/bug'
import { listComments, createComment } from '@/api/comment'
import { listAttachments, getDownloadUrl } from '@/api/attachment'
import { listMembers } from '@/api/project'
import { useUserStore } from '@/store/user'

const route = useRoute()
const bugId = route.params.id
const userStore = useUserStore()

const loading = ref(false)
const bug = ref({})
const bugLogs = ref([])
const comments = ref([])
const attachments = ref([])
const activeTab = ref('logs')
const newComment = ref('')
const assignVisible = ref(false)
const rejectVisible = ref(false)
const assignUserId = ref(null)
const rejectReason = ref('')
const isReassign = ref(false)
const projectMembers = ref([])
const commentInputRef = ref(null)
const showMentionList = ref(false)
const mentionIndex = ref(0)
const mentionSearch = ref('')

const uploadHeaders = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('token')}` }))

const currentUserId = computed(() => userStore.userInfo?.id)
const isCreator = computed(() => bug.value.creator?.id === currentUserId.value)
const isAssignee = computed(() => bug.value.assignee?.id === currentUserId.value)
function _isSuperAdmin() {
  const roles = userStore.userInfo?.roles || []
  return roles.includes('super_admin') || roles.some(r => r === 'super_admin' || r?.code === 'super_admin')
}
const isTechLeader = computed(() => {
  if (_isSuperAdmin()) return true
  const uid = currentUserId.value
  return uid === bug.value._project_tech_leader_id || uid === bug.value._project_owner_id
})

const assignDialogTitle = computed(() => isReassign.value ? '重新指派Bug' : '指派Bug')

const severityMap = {
  critical: { label: '严重', type: 'danger' },
  major: { label: '主要', type: 'warning' },
  minor: { label: '次要', type: '' },
  trivial: { label: '轻微', type: 'info' }
}
const priorityMap = {
  urgent: { label: '紧急', type: 'danger' },
  high: { label: '高', type: 'warning' },
  medium: { label: '中', type: '' },
  low: { label: '低', type: 'info' }
}
const statusMap = {
  pending: { label: '待处理', type: 'warning' },
  assigned: { label: '已指派', type: '' },
  fixing: { label: '修复中', type: 'primary' },
  verified: { label: '已修复', type: 'success' },
  rejected: { label: '已拒绝', type: 'danger' }
}
const logActionLabel = {
  create: '创建Bug', assign: '指派Bug', reject: '拒绝Bug',
  start_fix: '开始修复', fixed: '标记已修复',
  reopen: '重开Bug', reassign: '重新指派'
}
const logActionType = {
  create: 'primary', assign: '', reject: 'danger',
  start_fix: '', fixed: 'success',
  reopen: 'warning', reassign: 'warning'
}

async function loadBug() {
  loading.value = true
  try {
    const data = await getBug(bugId)
    const pid = data.project_id || data.project?.id
    if (pid) {
      try {
        const { getProject } = await import('@/api/project')
        const project = await getProject(pid)
        data._project_tech_leader_id = project.tech_leader?.id
        data._project_owner_id = project.owner?.id
      } catch (e) {}
    }
    bug.value = { ...data }
  } catch (e) {
  } finally {
    loading.value = false
  }
}

async function loadLogs() {
  try {
    const res = await getBugLogs(bugId)
    bugLogs.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) { bugLogs.value = [] }
}

async function loadComments() {
  try {
    const res = await listComments({ target_type: 'bug', target_id: bugId })
    comments.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) { comments.value = [] }
}

async function loadAttachments() {
  try {
    const res = await listAttachments({ target_type: 'bug', target_id: bugId })
    attachments.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) { attachments.value = [] }
}

async function loadProjectMembers() {
  const pid = bug.value.project?.id || bug.value.project_id
  if (!pid) return
  try {
    const res = await listMembers(pid)
    projectMembers.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) { projectMembers.value = [] }
}

function openAssignDialog() {
  isReassign.value = false
  assignUserId.value = null
  assignVisible.value = true
}

function openReassignDialog() {
  isReassign.value = true
  assignUserId.value = null
  assignVisible.value = true
}

async function submitAssign() {
  if (!assignUserId.value) { ElMessage.warning('请选择处理人'); return }
  try {
    if (isReassign.value) {
      await reassignBug(bugId, { assignee_id: assignUserId.value })
      ElMessage.success('重新指派成功')
    } else {
      await assignBug(bugId, { assignee_id: assignUserId.value })
      ElMessage.success('指派成功')
    }
    assignVisible.value = false
    loadBug()
    loadLogs()
  } catch (e) {}
}

function handleReject() {
  rejectReason.value = ''
  rejectVisible.value = true
}

async function submitReject() {
  try {
    await rejectBug(bugId, { reason: rejectReason.value })
    ElMessage.success('已拒绝')
    rejectVisible.value = false
    loadBug()
    loadLogs()
  } catch (e) {}
}

async function handleStartFix() {
  try {
    await startFix(bugId)
    ElMessage.success('已开始修复')
    loadBug()
    loadLogs()
  } catch (e) {}
}

async function handleMarkFixed() {
  try {
    await markFixed(bugId, {})
    ElMessage.success('已标记解决')
    loadBug()
    loadLogs()
  } catch (e) {}
}

const reopenVisible = ref(false)
const reopenReason = ref('')

function openReopenDialog() {
  reopenReason.value = ''
  reopenVisible.value = true
}

async function submitReopen() {
  if (!reopenReason.value.trim()) { ElMessage.warning('请输入重开原因'); return }
  try {
    await reopenBug(bugId, { reason: reopenReason.value })
    ElMessage.success('Bug已重开')
    reopenVisible.value = false
    loadBug()
    loadLogs()
  } catch (e) {}
}

// @mention
const filteredMembers = computed(() => {
  const keyword = mentionSearch.value.toLowerCase()
  return projectMembers.value.filter(m => {
    const name = (m.real_name || m.username || '').toLowerCase()
    return name.includes(keyword)
  }).slice(0, 10)
})

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
  if (e.key === 'ArrowDown') { e.preventDefault(); mentionIndex.value = Math.min(mentionIndex.value + 1, filteredMembers.value.length - 1) }
  else if (e.key === 'ArrowUp') { e.preventDefault(); mentionIndex.value = Math.max(mentionIndex.value - 1, 0) }
  else if (e.key === 'Enter' && filteredMembers.value.length) { e.preventDefault(); selectMention(filteredMembers.value[mentionIndex.value]) }
  else if (e.key === 'Escape') { showMentionList.value = false }
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
    newComment.value = beforeAt + '@' + (member.real_name || member.username) + ' ' + textAfter
  }
  showMentionList.value = false
  nextTick(() => textarea.focus())
}

function extractMentionIds(text) {
  const ids = []
  const matches = text.match(/@(\S+)/g) || []
  for (const m of matches) {
    const name = m.substring(1)
    const member = projectMembers.value.find(u => (u.real_name || u.username) === name)
    if (member) { const uid = member.user_id || member.id; if (!ids.includes(uid)) ids.push(uid) }
  }
  return ids
}

function renderMentions(content) {
  if (!content) return ''
  return content.replace(/@(\S+)/g, '<span class="mention-tag">@$1</span>')
}

async function submitComment() {
  if (!newComment.value.trim()) { ElMessage.warning('请输入评论内容'); return }
  try {
    await createComment({ target_type: 'bug', target_id: Number(bugId), content: newComment.value, mention_user_ids: extractMentionIds(newComment.value) })
    ElMessage.success('评论成功')
    newComment.value = ''
    loadComments()
  } catch (e) {}
}

function onUploadSuccess() { ElMessage.success('上传成功'); loadAttachments() }
function downloadFile(file) { window.open(getDownloadUrl(file.id), '_blank') }
function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

onMounted(async () => {
  await loadBug()
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
.bug-info-card { margin-bottom: 20px; }
.bug-header { display: flex; justify-content: space-between; align-items: flex-start; }
.bug-title-row { display: flex; align-items: center; gap: 12px; }
.bug-title-row h3 { font-size: 18px; color: #333; }
.bug-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.detail-tabs { background: #fff; border-radius: 4px; padding: 16px; }
/* @提及下拉向上弹出，el-tabs内容区默认overflow:hidden会裁剪下拉列表 */
.detail-tabs :deep(.el-tabs__content) { overflow: visible; }
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
.mention-dropdown { position: absolute; bottom: 100%; left: 0; width: 240px; max-height: 200px; overflow-y: auto; background: #fff; border: 1px solid #dcdfe6; border-radius: 4px; box-shadow: 0 2px 12px rgba(0,0,0,0.1); z-index: 2000; margin-bottom: 4px; }
.mention-item { display: flex; align-items: center; gap: 8px; padding: 8px 12px; cursor: pointer; font-size: 13px; }
.mention-item:hover, .mention-item.active { background: #f5f7fa; }
.mention-item.empty { color: #999; cursor: default; }
.desc-section { margin-top: 16px; background: #fff; border: 1px solid #ebeef5; border-radius: 4px; }
.desc-label { padding: 12px 16px; font-weight: 600; color: #333; background: #fafafa; border-bottom: 1px solid #ebeef5; }
.desc-body { padding: 16px; min-height: 60px; }
.rich-content { line-height: 1.8; word-break: break-word; }
.rich-content :deep(img) { max-width: 100%; height: auto; border-radius: 4px; }
.rich-content :deep(table) { border-collapse: collapse; width: 100%; }
.rich-content :deep(td), .rich-content :deep(th) { border: 1px solid #ddd; padding: 8px; }
</style>
