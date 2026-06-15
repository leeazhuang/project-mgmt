<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">Bug列表</span>
          <el-button v-if="userStore.hasPermission('bug:create')" type="primary" :icon="Plus" @click="openDialog()">新增Bug</el-button>
        </div>
      </template>

      <div class="search-bar">
        <el-select v-model="filters.project_id" placeholder="选择项目" clearable style="width:160px" @change="loadBugs">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-select v-model="filters.status" placeholder="状态" clearable style="width:130px" @change="loadBugs">
          <el-option label="待处理" value="pending" />
          <el-option label="已指派" value="assigned" />
          <el-option label="修复中" value="fixing" />
          <el-option label="已修复" value="verified" />
          <el-option label="已拒绝" value="rejected" />
        </el-select>
        <el-select v-model="filters.severity" placeholder="严重程度" clearable style="width:130px" @change="loadBugs">
          <el-option label="严重" value="critical" />
          <el-option label="主要" value="major" />
          <el-option label="次要" value="minor" />
          <el-option label="轻微" value="trivial" />
        </el-select>
        <el-input v-model="filters.keyword" placeholder="搜索Bug标题" clearable style="width:200px" @keyup.enter="loadBugs" />
        <el-button type="primary" :icon="Search" @click="loadBugs">搜索</el-button>
      </div>

      <el-table :data="bugList" v-loading="loading" border stripe>
        <el-table-column prop="title" label="Bug标题" min-width="200">
          <template #default="{ row }">
            <el-link type="primary" @click="$router.push(`/bug/${row.id}`)">{{ row.title }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="所属项目" min-width="140">
          <template #default="{ row }">{{ row.project?.name || '-' }}</template>
        </el-table-column>
        <el-table-column label="严重程度" width="100">
          <template #default="{ row }">
            <el-tag :type="severityMap[row.severity]?.type" size="small">{{ severityMap[row.severity]?.label || row.severity }}</el-tag>
          </template>
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
        <el-table-column label="指派给" width="110">
          <template #default="{ row }">{{ row.assignee?.real_name || row.assignee?.username || '未指派' }}</template>
        </el-table-column>
        <el-table-column label="创建人" width="100">
          <template #default="{ row }">{{ row.creator?.real_name || row.creator?.username || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <div class="action-btns">
              <el-button type="primary" size="small" text @click="$router.push(`/bug/${row.id}`)">详情</el-button>
              <el-button v-if="row.status === 'pending' && canAssign(row)" type="primary" size="small" text @click="openListAssign(row)">指派</el-button>
              <el-button v-if="row.status === 'pending' && canAssign(row)" type="danger" size="small" text @click="openListReject(row)">拒绝</el-button>
              <el-button v-if="row.status === 'assigned' && isMyBug(row)" type="primary" size="small" text @click="handleListStartFix(row)">开始</el-button>
              <el-button v-if="row.status === 'fixing' && isMyBug(row)" type="success" size="small" text @click="handleListMarkFixed(row)">已解决</el-button>
              <el-button v-if="row.status === 'verified' && isMyCreated(row)" type="warning" size="small" text @click="openListReopen(row)">重开</el-button>
              <el-button v-if="['assigned','fixing'].includes(row.status) && canAssign(row)" type="warning" size="small" text @click="openListReassign(row)">重新指派</el-button>
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
        @change="loadBugs"
      />
    </el-card>

    <BugCreateDialog v-model="dialogVisible" :projects="projects" @created="loadBugs" />

    <!-- 列表指派Dialog -->
    <el-dialog v-model="listAssignVisible" :title="listAssignIsReassign ? '重新指派Bug' : '指派Bug'" width="400px">
      <el-form label-width="80px">
        <el-form-item label="指派给">
          <el-select v-model="listAssignUserId" filterable placeholder="请选择项目成员" style="width:100%">
            <el-option v-for="m in listProjectMembers" :key="m.user_id || m.id" :label="m.real_name || m.username" :value="m.user_id || m.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="listAssignVisible = false">取消</el-button>
        <el-button type="primary" @click="submitListAssign">确定</el-button>
      </template>
    </el-dialog>

    <!-- 列表拒绝Dialog -->
    <el-dialog v-model="listRejectVisible" title="拒绝Bug" width="400px">
      <el-input v-model="listRejectReason" type="textarea" rows="3" placeholder="请输入拒绝原因" />
      <template #footer>
        <el-button @click="listRejectVisible = false">取消</el-button>
        <el-button type="danger" @click="submitListReject">确定拒绝</el-button>
      </template>
    </el-dialog>

    <!-- 列表重开Dialog -->
    <el-dialog v-model="listReopenVisible" title="重开Bug" width="400px">
      <el-input v-model="listReopenReason" type="textarea" rows="3" placeholder="请输入重开原因（问题未解决的具体描述）" />
      <template #footer>
        <el-button @click="listReopenVisible = false">取消</el-button>
        <el-button type="warning" @click="submitListReopen">确定重开</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import BugCreateDialog from '@/components/BugCreateDialog.vue'
import { listBugs, assignBug, reassignBug, rejectBug, startFix, markFixed, reopenBug } from '@/api/bug'
import { listProjects, listMembers } from '@/api/project'
import { useUserStore } from '@/store/user'

const userStore = useUserStore()

const loading = ref(false)
const bugList = ref([])
const projects = ref([])
const dialogVisible = ref(false)
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })
const filters = reactive({ project_id: '', status: '', severity: '', keyword: '' })

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

function openDialog() { dialogVisible.value = true }

async function loadBugs() {
  loading.value = true
  try {
    const res = await listBugs({ ...filters, page: pagination.page, page_size: pagination.pageSize })
    bugList.value = res.items || res || []
    pagination.total = res.total || bugList.value.length
  } catch (e) {
    bugList.value = []
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

// --- 列表操作相关 ---
const listAssignVisible = ref(false)
const listAssignBugId = ref(null)
const listAssignUserId = ref(null)
const listAssignIsReassign = ref(false)
const listRejectVisible = ref(false)
const listRejectBugId = ref(null)
const listRejectReason = ref('')
const listProjectMembers = ref([])

function _isSuperAdmin() {
  const roles = userStore.userInfo?.roles || []
  return roles.includes('super_admin') || roles.some(r => r === 'super_admin' || r?.code === 'super_admin')
}

function canAssign(row) {
  if (_isSuperAdmin()) return true
  const uid = userStore.userInfo?.id
  // 需要知道项目的tech_leader_id，这里用项目列表中匹配
  const proj = projects.value.find(p => p.id === row.project_id)
  return proj && (proj.tech_leader?.id === uid || proj.owner?.id === uid)
}

function isDeveloper() {
  const roles = userStore.userInfo?.roles || []
  return roles.includes('developer') || roles.some(r => r === 'developer' || r?.code === 'developer')
}

// 开始修复/标记已解决：仅"开发人员且该Bug指派给他"（或超管）
function isMyBug(row) {
  if (_isSuperAdmin()) return true
  return isDeveloper() && row.assignee?.id === userStore.userInfo?.id
}

function isMyCreated(row) {
  return row.creator?.id === userStore.userInfo?.id || _isSuperAdmin()
}

async function loadListMembers(projectId) {
  try {
    const res = await listMembers(projectId)
    listProjectMembers.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) { listProjectMembers.value = [] }
}

function openListAssign(row) {
  listAssignIsReassign.value = false
  listAssignBugId.value = row.id
  listAssignUserId.value = null
  loadListMembers(row.project_id)
  listAssignVisible.value = true
}

function openListReassign(row) {
  listAssignIsReassign.value = true
  listAssignBugId.value = row.id
  listAssignUserId.value = null
  loadListMembers(row.project_id)
  listAssignVisible.value = true
}

async function submitListAssign() {
  if (!listAssignUserId.value) { ElMessage.warning('请选择处理人'); return }
  try {
    if (listAssignIsReassign.value) {
      await reassignBug(listAssignBugId.value, { assignee_id: listAssignUserId.value })
      ElMessage.success('重新指派成功')
    } else {
      await assignBug(listAssignBugId.value, { assignee_id: listAssignUserId.value })
      ElMessage.success('指派成功')
    }
    listAssignVisible.value = false
    loadBugs()
  } catch (e) {}
}

function openListReject(row) {
  listRejectBugId.value = row.id
  listRejectReason.value = ''
  listRejectVisible.value = true
}

async function submitListReject() {
  try {
    await rejectBug(listRejectBugId.value, { reason: listRejectReason.value })
    ElMessage.success('已拒绝')
    listRejectVisible.value = false
    loadBugs()
  } catch (e) {}
}

async function handleListStartFix(row) {
  try { await startFix(row.id); ElMessage.success('已开始修复'); loadBugs() } catch (e) {}
}

async function handleListMarkFixed(row) {
  try { await markFixed(row.id, {}); ElMessage.success('已标记修复'); loadBugs() } catch (e) {}
}

const listReopenVisible = ref(false)
const listReopenBugId = ref(null)
const listReopenReason = ref('')

function openListReopen(row) {
  listReopenBugId.value = row.id
  listReopenReason.value = ''
  listReopenVisible.value = true
}

async function submitListReopen() {
  if (!listReopenReason.value.trim()) { ElMessage.warning('请输入重开原因'); return }
  try {
    await reopenBug(listReopenBugId.value, { reason: listReopenReason.value })
    ElMessage.success('Bug已重开')
    listReopenVisible.value = false
    loadBugs()
  } catch (e) {}
}

onMounted(() => { loadBugs(); loadProjects() })
</script>

<style scoped>
.page-container { min-height: 100%; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-size: 16px; font-weight: 600; }
.search-bar { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.action-btns { display: flex; flex-wrap: nowrap; align-items: center; gap: 0; }
</style>
