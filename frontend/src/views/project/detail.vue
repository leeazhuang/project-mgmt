<template>
  <div class="page-container">
    <div class="page-header">
      <el-button :icon="ArrowLeft" @click="$router.back()">返回</el-button>
      <h2>{{ project.name }}</h2>
    </div>

    <el-card v-loading="loading" class="project-info-card">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="项目名称">{{ project.name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusMap[project.status]?.type">{{ statusMap[project.status]?.label || project.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="负责人">{{ project.owner?.real_name || project.owner?.username || '-' }}</el-descriptions-item>
        <el-descriptions-item label="技术负责人">{{ project.tech_leader?.real_name || project.tech_leader?.username || '-' }}</el-descriptions-item>
        <el-descriptions-item label="开始日期">{{ project.start_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="结束日期">{{ project.end_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="描述" :span="3">{{ project.description || '暂无描述' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-tabs v-model="activeTab" class="project-tabs">
      <!-- Members Tab -->
      <el-tab-pane label="项目成员" name="members">
        <div class="tab-action" v-if="canManageMembers">
          <el-button type="primary" :icon="Plus" size="small" @click="openAddMember">添加成员</el-button>
        </div>
        <el-table :data="members" border stripe>
          <el-table-column prop="real_name" label="姓名" min-width="120" />
          <el-table-column prop="username" label="用户名" min-width="120" />
          <el-table-column label="项目角色" width="140">
            <template #default="{ row }">
              <el-tag v-if="row.user_id === project.owner?.id" type="warning" size="small">项目负责人</el-tag>
              <el-tag v-else-if="row.user_id === project.tech_leader?.id" type="success" size="small">技术负责人</el-tag>
              <el-tag v-else type="info" size="small">成员</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="joined_at" label="加入时间" width="160" />
          <el-table-column v-if="canManageMembers" label="操作" width="100">
            <template #default="{ row }">
              <el-button
                v-if="row.user_id !== project.owner?.id && row.user_id !== project.tech_leader?.id"
                type="danger" size="small" text
                @click="handleRemoveMember(row)"
              >移除</el-button>
              <span v-else style="color:#999;font-size:12px">不可移除</span>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Requirements Tab -->
      <el-tab-pane label="项目需求" name="requirements">
        <el-table :data="requirements" border stripe v-loading="reqLoading">
          <el-table-column prop="title" label="需求标题" min-width="200">
            <template #default="{ row }">
              <el-link type="primary" @click="$router.push(`/requirement/${row.id}`)">{{ row.title }}</el-link>
            </template>
          </el-table-column>
          <el-table-column label="优先级" width="90">
            <template #default="{ row }">
              <el-tag :type="priorityMap[row.priority]?.type" size="small">{{ priorityMap[row.priority]?.label || row.priority }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="reqStatusMap[row.status]?.type" size="small">{{ reqStatusMap[row.status]?.label || row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="160" />
        </el-table>
      </el-tab-pane>

      <!-- Tasks Tab -->
      <el-tab-pane label="项目任务" name="tasks">
        <el-table :data="tasks" border stripe v-loading="taskLoading">
          <el-table-column prop="title" label="任务标题" min-width="200" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="taskStatusMap[row.status]?.type" size="small">{{ taskStatusMap[row.status]?.label || row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="指派给" width="120">
            <template #default="{ row }">{{ row.assignee?.real_name || row.assignee?.username || '-' }}</template>
          </el-table-column>
          <el-table-column prop="end_date" label="截止日期" width="120" />
        </el-table>
      </el-tab-pane>

      <!-- Bugs Tab -->
      <el-tab-pane label="项目Bug" name="bugs">
        <el-table :data="bugs" border stripe v-loading="bugLoading">
          <el-table-column prop="title" label="Bug标题" min-width="200">
            <template #default="{ row }">
              <el-link type="primary" @click="$router.push(`/bug/${row.id}`)">{{ row.title }}</el-link>
            </template>
          </el-table-column>
          <el-table-column label="严重程度" width="100">
            <template #default="{ row }">
              <el-tag :type="severityMap[row.severity]?.type" size="small">{{ severityMap[row.severity]?.label || row.severity }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- Add Member Dialog -->
    <el-dialog v-model="addMemberVisible" title="添加成员" width="500px">
      <div v-if="availableUsers.length">
        <el-table :data="availableUsers" border stripe max-height="400" @selection-change="onSelectChange">
          <el-table-column type="selection" width="50" />
          <el-table-column prop="real_name" label="姓名" />
          <el-table-column prop="username" label="用户名" />
        </el-table>
      </div>
      <el-empty v-else description="所有用户都已在项目中" />
      <template #footer>
        <el-button @click="addMemberVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedMemberIds.length" @click="handleAddMembers">
          添加选中 ({{ selectedMemberIds.length }})
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Plus } from '@element-plus/icons-vue'
import { getProject, listMembers, addMembers, removeMember } from '@/api/project'
import { useUserStore } from '@/store/user'
import { listRequirements } from '@/api/requirement'
import { listTasks } from '@/api/task'
import { listBugs } from '@/api/bug'
import { getUserOptions } from '@/api/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const projectId = route.params.id
const currentUserId = userStore.userInfo?.id

function _isSuperAdmin() {
  const roles = userStore.userInfo?.roles || []
  return roles.includes('super_admin') || roles.some(r => r === 'super_admin' || r?.code === 'super_admin')
}

// 只有超管、项目负责人、技术负责人可以管理成员
const canManageMembers = computed(() => {
  if (userStore.hasPermission('_super_admin_')) return true
  const roles = userStore.userInfo?.roles || []
  if (roles.includes('super_admin') || roles.some(r => r?.code === 'super_admin')) return true
  return currentUserId === project.value.owner?.id || currentUserId === project.value.tech_leader?.id
})

const loading = ref(false)
const reqLoading = ref(false)
const taskLoading = ref(false)
const bugLoading = ref(false)
const project = ref({})
const members = ref([])
const requirements = ref([])
const tasks = ref([])
const bugs = ref([])
const userOptions = ref([])
const activeTab = ref('members')
const addMemberVisible = ref(false)
const selectedMemberIds = ref([])

// 过滤掉已在项目中的用户，只显示可添加的
const availableUsers = computed(() => {
  const existingIds = new Set(members.value.map(m => m.user_id))
  return userOptions.value.filter(u => !existingIds.has(u.id))
})

function openAddMember() {
  selectedMemberIds.value = []
  addMemberVisible.value = true
}

function onSelectChange(rows) {
  selectedMemberIds.value = rows.map(r => r.id)
}

const statusMap = {
  active: { label: '进行中', type: 'success' },
  completed: { label: '已完成', type: 'info' },
  archived: { label: '已归档', type: '' },
  planning: { label: '规划中', type: 'warning' }
}
const priorityMap = {
  urgent: { label: '紧急', type: 'danger' },
  high: { label: '高', type: 'warning' },
  medium: { label: '中', type: '' },
  low: { label: '低', type: 'info' }
}
const reqStatusMap = {
  draft: { label: '草稿', type: 'info' },
  pending: { label: '待处理', type: 'warning' },
  approved: { label: '已接受', type: 'success' },
  rejected: { label: '已拒绝', type: 'danger' }
}
const taskStatusMap = {
  pending: { label: '待处理', type: 'info' },
  in_progress: { label: '进行中', type: 'warning' },
  done: { label: '已完成', type: 'success' }
}
const severityMap = {
  critical: { label: '严重', type: 'danger' },
  major: { label: '主要', type: 'warning' },
  minor: { label: '次要', type: '' },
  trivial: { label: '轻微', type: 'info' }
}

async function loadProject() {
  loading.value = true
  try {
    project.value = await getProject(projectId)
    // 权限校验：只有超管、项目负责人、技术负责人可以查看详情
    if (!_isSuperAdmin()) {
      const uid = currentUserId
      const isOwner = uid === project.value.owner?.id
      const isTech = uid === project.value.tech_leader?.id
      const hasUpdate = userStore.hasPermission('project:update')
      if (!isOwner && !isTech && !hasUpdate) {
        ElMessage.error('没有查看该项目详情的权限')
        router.replace('/project')
        return
      }
    }
  } catch (e) {
  } finally {
    loading.value = false
  }
}

async function loadMembers() {
  try {
    const res = await listMembers(projectId)
    members.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) {
    members.value = []
  }
}

async function loadRequirements() {
  reqLoading.value = true
  try {
    const res = await listRequirements({ project_id: projectId, page: 1, page_size: 50 })
    requirements.value = res.items || res || []
  } catch (e) {
    requirements.value = []
  } finally {
    reqLoading.value = false
  }
}

async function loadTasks() {
  taskLoading.value = true
  try {
    const res = await listTasks({ project_id: projectId, page: 1, page_size: 50 })
    tasks.value = res.items || res || []
  } catch (e) {
    tasks.value = []
  } finally {
    taskLoading.value = false
  }
}

async function loadBugs() {
  bugLoading.value = true
  try {
    const res = await listBugs({ project_id: projectId, page: 1, page_size: 50 })
    bugs.value = res.items || res || []
  } catch (e) {
    bugs.value = []
  } finally {
    bugLoading.value = false
  }
}

async function loadUsers() {
  try {
    const res = await getUserOptions()
    userOptions.value = res.items || res || []
  } catch (e) {
    userOptions.value = []
  }
}

async function handleAddMembers() {
  if (!selectedMemberIds.value.length) {
    ElMessage.warning('请选择成员')
    return
  }
  try {
    await addMembers(projectId, { user_ids: selectedMemberIds.value })
    ElMessage.success('添加成功')
    addMemberVisible.value = false
    selectedMemberIds.value = []
    loadMembers()
  } catch (e) {}
}

async function handleRemoveMember(member) {
  await ElMessageBox.confirm(`确定移除成员 "${member.real_name || member.username}" 吗？`, '警告', {
    type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消'
  })
  try {
    await removeMember(projectId, member.user_id)
    ElMessage.success('移除成功')
    loadMembers()
  } catch (e) {}
}

onMounted(() => {
  loadProject()
  loadMembers()
  loadRequirements()
  loadTasks()
  loadBugs()
  loadUsers()
})
</script>

<style scoped>
.page-container { min-height: 100%; }
.page-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.page-header h2 { font-size: 20px; color: #333; }
.project-info-card { margin-bottom: 20px; }
.project-tabs { background: #fff; border-radius: 4px; padding: 16px; }
.tab-action { margin-bottom: 12px; }
</style>
