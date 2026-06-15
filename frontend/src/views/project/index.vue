<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">项目管理</span>
          <el-button v-if="userStore.hasPermission('project:create')" type="primary" :icon="Plus" @click="openDialog()">新建项目</el-button>
        </div>
      </template>

      <div class="search-bar">
        <el-input v-model="searchKeyword" placeholder="搜索项目名称" clearable style="width:250px" @keyup.enter="loadProjects" />
        <el-button type="primary" :icon="Search" @click="loadProjects">搜索</el-button>
        <el-button @click="() => { searchKeyword = ''; loadProjects() }">重置</el-button>
      </div>

      <el-table :data="projectList" v-loading="loading" border stripe>
        <el-table-column prop="name" label="项目名称" min-width="160">
          <template #default="{ row }">
            <el-link v-if="canViewDetail(row)" type="primary" @click="$router.push(`/project/${row.id}`)">{{ row.name }}</el-link>
            <span v-else>{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="负责人" min-width="100">
          <template #default="{ row }">{{ row.owner?.real_name || row.owner?.username || '-' }}</template>
        </el-table-column>
        <el-table-column label="技术负责人" min-width="100">
          <template #default="{ row }">{{ row.tech_leader?.real_name || row.tech_leader?.username || '-' }}</template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="120" />
        <el-table-column prop="end_date" label="结束日期" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status]?.type" size="small">{{ statusMap[row.status]?.label || row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canViewDetail(row)" type="primary" size="small" text @click="$router.push(`/project/${row.id}`)">详情</el-button>
            <el-button v-if="userStore.hasPermission('project:update')" type="primary" size="small" text @click="openDialog(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, prev, pager, next"
        style="margin-top:16px;justify-content:flex-end"
        @change="loadProjects"
      />
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingProject ? '编辑项目' : '新建项目'"
      width="650px"
      :close-on-click-modal="false"
    >
      <el-form ref="projectFormRef" :model="projectForm" :rules="projectRules" label-width="110px">
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="projectForm.name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="projectForm.description" type="textarea" rows="3" placeholder="请输入项目描述" />
        </el-form-item>
        <el-form-item label="负责人" prop="owner_id">
          <el-select v-model="projectForm.owner_id" filterable placeholder="请选择负责人" style="width:100%">
            <el-option v-for="u in userOptions" :key="u.id" :label="u.real_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="技术负责人" prop="tech_leader_id">
          <el-select v-model="projectForm.tech_leader_id" filterable placeholder="请选择技术负责人" clearable style="width:100%">
            <el-option v-for="u in userOptions" :key="u.id" :label="u.real_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期" prop="start_date">
          <el-date-picker v-model="projectForm.start_date" type="date" value-format="YYYY-MM-DD" placeholder="选择开始日期" style="width:100%" />
        </el-form-item>
        <el-form-item label="结束日期" prop="end_date">
          <el-date-picker v-model="projectForm.end_date" type="date" value-format="YYYY-MM-DD" placeholder="选择结束日期" style="width:100%" />
        </el-form-item>
        <el-form-item label="项目成员">
          <el-select v-model="projectForm.member_ids" multiple filterable placeholder="请选择项目成员" style="width:100%">
            <el-option v-for="u in userOptions" :key="u.id" :label="u.real_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { listProjects, createProject, updateProject, listMembers } from '@/api/project'
import { getUserOptions } from '@/api/user'
import { useUserStore } from '@/store/user'

const userStore = useUserStore()

// 只有超管、项目负责人、技术负责人可以查看项目详情
function canViewDetail(row) {
  const roles = userStore.userInfo?.roles || []
  const isSuperAdmin = roles.includes('super_admin') || roles.some(r => r === 'super_admin' || r?.code === 'super_admin')
  if (isSuperAdmin) return true
  if (userStore.hasPermission('project:update')) return true
  const uid = userStore.userInfo?.id
  return uid === row.owner?.id || uid === row.tech_leader?.id
}

const loading = ref(false)
const submitting = ref(false)
const projectList = ref([])
const userOptions = ref([])
const dialogVisible = ref(false)
const editingProject = ref(null)
const searchKeyword = ref('')
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })
const projectFormRef = ref(null)

const statusMap = {
  active: { label: '进行中', type: 'success' },
  completed: { label: '已完成', type: 'info' },
  archived: { label: '已归档', type: '' },
  planning: { label: '规划中', type: 'warning' }
}

const projectForm = reactive({
  name: '', description: '', owner_id: null, tech_leader_id: null,
  start_date: '', end_date: '', member_ids: []
})

const projectRules = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  owner_id: [{ required: true, message: '请选择负责人', trigger: 'change' }]
}

async function loadProjects() {
  loading.value = true
  try {
    const res = await listProjects({ keyword: searchKeyword.value, page: pagination.page, page_size: pagination.pageSize })
    projectList.value = res.items || res || []
    pagination.total = res.total || projectList.value.length
  } catch (e) {
    projectList.value = []
  } finally {
    loading.value = false
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

async function openDialog(project = null) {
  editingProject.value = project
  if (project) {
    // 加载项目成员列表用于回显
    let memberIds = []
    try {
      const members = await listMembers(project.id)
      const memberList = Array.isArray(members) ? members : (members.items || [])
      memberIds = memberList.map(m => m.user_id)
    } catch (e) {
      memberIds = []
    }
    Object.assign(projectForm, {
      name: project.name,
      description: project.description || '',
      owner_id: project.owner?.id || project.owner_id,
      tech_leader_id: project.tech_leader?.id || project.tech_leader_id,
      start_date: project.start_date || '',
      end_date: project.end_date || '',
      member_ids: memberIds
    })
  } else {
    Object.assign(projectForm, { name: '', description: '', owner_id: null, tech_leader_id: null, start_date: '', end_date: '', member_ids: [] })
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await projectFormRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (editingProject.value) {
      await updateProject(editingProject.value.id, projectForm)
      ElMessage.success('更新成功')
    } else {
      await createProject(projectForm)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadProjects()
  } catch (e) {
  } finally {
    submitting.value = false
  }
}

onMounted(() => { loadProjects(); loadUsers() })
</script>

<style scoped>
.page-container { min-height: 100%; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-size: 16px; font-weight: 600; }
.search-bar { display: flex; gap: 8px; margin-bottom: 16px; }
</style>
