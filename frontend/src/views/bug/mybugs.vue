<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">我的Bug</span>
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
      </div>

      <el-table :data="bugList" v-loading="loading" border stripe>
        <el-table-column label="Bug标题" min-width="200">
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
        <el-table-column label="创建人" width="100">
          <template #default="{ row }">{{ row.creator?.real_name || row.creator?.username || '-' }}</template>
        </el-table-column>
        <el-table-column label="指派给" width="100">
          <template #default="{ row }">{{ row.assignee?.real_name || row.assignee?.username || '未指派' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <div class="action-btns">
              <el-button v-if="row.status === 'assigned'" type="primary" size="small" text @click="handleStartFix(row)">开始修复</el-button>
              <el-button v-if="row.status === 'fixing'" type="success" size="small" text @click="handleMarkFixed(row)">标记已解决</el-button>
              <el-button type="primary" size="small" text @click="$router.push(`/bug/${row.id}`)">详情</el-button>
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import BugCreateDialog from '@/components/BugCreateDialog.vue'
import { listBugs, startFix, markFixed } from '@/api/bug'
import { listProjects } from '@/api/project'
import { useUserStore } from '@/store/user'

const userStore = useUserStore()
const loading = ref(false)
const bugList = ref([])
const projects = ref([])
const dialogVisible = ref(false)
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const filters = reactive({ project_id: '', status: '' })

function openDialog() { dialogVisible.value = true }

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

async function loadBugs() {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      my: 1
    }
    if (filters.project_id) params.project_id = filters.project_id
    if (filters.status) params.status = filters.status
    const res = await listBugs(params)
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

async function handleStartFix(row) {
  try {
    await startFix(row.id)
    ElMessage.success('已开始修复')
    loadBugs()
  } catch (e) {}
}

async function handleMarkFixed(row) {
  try {
    await markFixed(row.id, {})
    ElMessage.success('已标记解决')
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
