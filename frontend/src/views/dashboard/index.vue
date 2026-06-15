<template>
  <div class="dashboard-page">
    <div class="page-header">
      <h2>工作台</h2>
      <el-select v-model="selectedProject" placeholder="全部项目" clearable @change="loadData" style="width:200px">
        <el-option label="全部项目" value="" />
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
    </div>

    <!-- Stat Cards -->
    <el-row :gutter="20" class="stat-row">
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon" style="background:#fff2e8;color:#fa8c16">
            <el-icon size="28"><Document /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ overviewData.requirements?.pending || 0 }}</div>
            <div class="stat-label">待处理需求</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon" style="background:#e6f7ff;color:#1890ff">
            <el-icon size="28"><List /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ (overviewData.tasks?.pending || 0) + (overviewData.tasks?.in_progress || 0) }}</div>
            <div class="stat-label">待处理任务</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon" style="background:#fff1f0;color:#f5222d">
            <el-icon size="28"><Warning /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ (overviewData.bugs?.pending || 0) + (overviewData.bugs?.assigned || 0) + (overviewData.bugs?.fixing || 0) }}</div>
            <div class="stat-label">待处理Bug</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon" style="background:#fff7e6;color:#faad14">
            <el-icon size="28"><Clock /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ overviewData.tasks?.overdue || 0 }}</div>
            <div class="stat-label">已超期任务</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Charts -->
    <el-row :gutter="20" class="chart-row">
      <el-col :span="8">
        <el-card>
          <template #header>需求状态分布</template>
          <div ref="reqChartRef" style="height:300px"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>任务状态分布</template>
          <div ref="taskChartRef" style="height:300px"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>Bug状态分布</template>
          <div ref="bugChartRef" style="height:300px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- My Todo -->
    <el-row :gutter="20" class="todo-row">
      <el-col :span="12" v-if="myTodo.pending_approvals && myTodo.pending_approvals.length">
        <el-card>
          <template #header>待我处理的需求</template>
          <el-table :data="myTodo.pending_approvals" size="small">
            <el-table-column prop="title" label="需求标题" min-width="150">
              <template #default="{ row }">
                <el-link type="primary" @click="$router.push(`/requirement/${row.id}`)">{{ row.title }}</el-link>
              </template>
            </el-table-column>
            <el-table-column prop="project_name" label="项目" width="120" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12" v-if="myTodo.my_tasks && myTodo.my_tasks.length">
        <el-card>
          <template #header>我的任务</template>
          <el-table :data="myTodo.my_tasks" size="small">
            <el-table-column prop="title" label="任务标题" min-width="150" />
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 'in_progress' ? 'warning' : 'info'" size="small">
                  {{ row.status === 'pending' ? '待处理' : row.status === 'in_progress' ? '进行中' : row.status }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { Document, List, Warning, Clock } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { listProjects } from '@/api/project'
import { getDashboardOverview, getMyTodo } from '@/api/dashboard'

const selectedProject = ref('')
const projects = ref([])
const myTodo = ref({})
const overviewData = ref({})

const reqChartRef = ref(null)
const taskChartRef = ref(null)
const bugChartRef = ref(null)

let reqChart = null
let taskChart = null
let bugChart = null

async function loadProjects() {
  try {
    const res = await listProjects({ page: 1, page_size: 100 })
    projects.value = res.items || res || []
  } catch (e) {
    projects.value = []
  }
}

async function loadData() {
  const params = selectedProject.value ? { project_id: selectedProject.value } : {}
  try {
    const [todo, overview] = await Promise.all([
      getMyTodo(params).catch(() => ({})),
      getDashboardOverview(params).catch(() => ({}))
    ])
    myTodo.value = todo || {}
    overviewData.value = overview || {}
    updateCharts()
  } catch (e) {
    // ignore
  }
}

function updateCharts() {
  const reqs = overviewData.value?.requirements || {}
  const tasks = overviewData.value?.tasks || {}
  const bugs = overviewData.value?.bugs || {}

  if (reqChart) {
    const reqData = [
      { name: '草稿', value: reqs.draft || 0 },
      { name: '待处理', value: reqs.pending || 0 },
      { name: '已接受', value: reqs.approved || 0 },
      { name: '已拒绝', value: reqs.rejected || 0 },
      { name: '开发中', value: reqs.developing || 0 },
      { name: '已完成', value: reqs.done || 0 },
    ].filter(d => d.value > 0)
    reqChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        data: reqData.length ? reqData : [{ name: '暂无数据', value: 0 }],
        label: { show: true, formatter: '{b}: {c}' }
      }]
    })
  }

  if (taskChart) {
    taskChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: ['待处理', '进行中', '已完成', '已超期'] },
      yAxis: { type: 'value' },
      series: [{
        type: 'bar',
        data: [tasks.pending || 0, tasks.in_progress || 0, tasks.done || 0, tasks.overdue || 0],
        itemStyle: { color: '#1890ff' }
      }]
    })
  }

  if (bugChart) {
    const bugData = [
      { name: '待处理', value: bugs.pending || 0 },
      { name: '已指派', value: bugs.assigned || 0 },
      { name: '修复中', value: bugs.fixing || 0 },
      { name: '已修复', value: bugs.verified || 0 },
      { name: '已拒绝', value: bugs.rejected || 0 },
    ].filter(d => d.value > 0)
    bugChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        data: bugData.length ? bugData : [{ name: '暂无数据', value: 0 }],
        label: { show: true, formatter: '{b}: {c}' }
      }]
    })
  }
}

onMounted(async () => {
  await loadProjects()
  await nextTick()
  if (reqChartRef.value) reqChart = echarts.init(reqChartRef.value)
  if (taskChartRef.value) taskChart = echarts.init(taskChartRef.value)
  if (bugChartRef.value) bugChart = echarts.init(bugChartRef.value)
  await loadData()

  window.addEventListener('resize', () => {
    reqChart?.resize()
    taskChart?.resize()
    bugChart?.resize()
  })
})
</script>

<style scoped>
.dashboard-page {
  min-height: 100%;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-header h2 {
  font-size: 20px;
  color: #333;
}
.stat-row {
  margin-bottom: 20px;
}
.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
}
.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #333;
}
.stat-label {
  font-size: 14px;
  color: #999;
  margin-top: 4px;
}
.chart-row {
  margin-top: 4px;
  margin-bottom: 20px;
}
.todo-row {
  margin-top: 4px;
}
</style>
