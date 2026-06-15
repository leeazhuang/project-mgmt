<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <span class="title">操作日志</span>
      </template>

      <div class="search-bar">
        <el-select v-model="filters.module" placeholder="操作模块" clearable style="width:150px" @change="loadLogs">
          <el-option label="用户管理" value="user" />
          <el-option label="角色管理" value="role" />
          <el-option label="菜单管理" value="menu" />
          <el-option label="项目管理" value="project" />
          <el-option label="需求管理" value="requirement" />
          <el-option label="任务管理" value="task" />
          <el-option label="Bug管理" value="bug" />
          <el-option label="系统" value="system" />
        </el-select>
        <el-select v-model="filters.user_id" placeholder="操作用户" clearable style="width:160px" @change="loadLogs">
          <el-option v-for="u in userOptions" :key="u.id" :label="u.real_name || u.username" :value="u.id" />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="width:260px"
          @change="loadLogs"
        />
        <el-button type="primary" :icon="Search" @click="loadLogs">搜索</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>

      <el-table :data="logList" v-loading="loading" border stripe>
        <el-table-column type="expand" width="40">
          <template #default="{ row }">
            <div class="log-detail">
              <div class="log-detail-row"><span class="label">请求：</span>{{ row.after_data?.method }} {{ row.after_data?.path }}</div>
              <div class="log-detail-row" v-if="row.after_data?.query"><span class="label">Query参数：</span><pre>{{ formatJson(row.after_data.query) }}</pre></div>
              <div class="log-detail-row" v-if="row.after_data?.body"><span class="label">请求参数：</span><pre>{{ formatJson(row.after_data.body) }}</pre></div>
              <div class="log-detail-row" v-if="row.user_agent"><span class="label">浏览器：</span>{{ row.user_agent }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="操作时间" width="180" />
        <el-table-column label="操作用户" width="120">
          <template #default="{ row }">{{ row.user?.real_name || row.user?.username || row.username || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作模块" width="120">
          <template #default="{ row }">{{ moduleLabel[row.module] || row.module }}</template>
        </el-table-column>
        <el-table-column prop="action" label="操作类型" width="100">
          <template #default="{ row }">
            <el-tag :type="actionTagMap[row.action]" size="small">{{ actionLabel[row.action] || row.action }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="操作描述" min-width="250" show-overflow-tooltip />
        <el-table-column prop="ip_address" label="IP地址" width="130" />
        <el-table-column label="结果" width="80">
          <template #default="{ row }">
            <el-tag :type="row.success !== false ? 'success' : 'danger'" size="small">
              {{ row.success !== false ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        style="margin-top:16px;justify-content:flex-end"
        @change="loadLogs"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { getUserOptions } from '@/api/user'
import request from '@/utils/request'

const loading = ref(false)
const logList = ref([])
const userOptions = ref([])
const dateRange = ref([])
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })
const filters = reactive({ module: '', user_id: '' })

const actionTagMap = {
  create: 'success',
  update: 'warning',
  delete: 'danger',
  login: 'primary',
  logout: 'info',
  view: ''
}
const actionLabel = {
  create: '新增',
  update: '修改',
  delete: '删除',
  login: '登录',
  logout: '退出',
  view: '查看',
  submit: '提交',
  approve: '接受/拒绝'
}

const moduleLabel = {
  user: '用户管理',
  role: '角色管理',
  menu: '菜单管理',
  project: '项目管理',
  requirement: '需求管理',
  task: '任务管理',
  bug: 'Bug管理',
  comment: '评论',
  attachment: '附件',
  system: '系统'
}

function formatJson(obj) {
  try {
    return JSON.stringify(obj, null, 2)
  } catch (e) {
    return String(obj)
  }
}

async function loadLogs() {
  loading.value = true
  try {
    const params = {
      ...filters,
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (dateRange.value?.length === 2) {
      params.date_from = dateRange.value[0]
      params.date_to = dateRange.value[1]
    }
    const res = await request.get('/api/operation-logs', { params })
    logList.value = res.items || res || []
    pagination.total = res.total || logList.value.length
  } catch (e) {
    logList.value = []
  } finally {
    loading.value = false
  }
}

async function loadUsers() {
  try {
    const res = await getUserOptions()
    userOptions.value = res.items || res || []
  } catch (e) { userOptions.value = [] }
}

function resetFilters() {
  filters.module = ''
  filters.user_id = ''
  dateRange.value = []
  pagination.page = 1
  loadLogs()
}

onMounted(() => { loadLogs(); loadUsers() })
</script>

<style scoped>
.page-container { min-height: 100%; }
.title { font-size: 16px; font-weight: 600; }
.search-bar { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.log-detail { padding: 8px 16px; font-size: 13px; color: #555; }
.log-detail-row { margin-bottom: 6px; display: flex; }
.log-detail-row .label { font-weight: 600; flex-shrink: 0; width: 90px; }
.log-detail-row pre { margin: 0; background: #f7f8fa; padding: 8px; border-radius: 4px; max-height: 300px; overflow: auto; flex: 1; }
</style>
