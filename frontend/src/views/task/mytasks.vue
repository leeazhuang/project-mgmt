<template>
  <div class="page-container">
    <div class="board-header">
      <h2>我的任务</h2>
      <div class="board-filters">
        <el-select v-model="selectedProject" placeholder="选择项目" clearable style="width:200px" @change="loadMyTasks">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </div>
    </div>

    <div class="kanban-board" v-loading="loading">
      <div class="kanban-column" v-for="col in columns" :key="col.status">
        <div class="column-header" :style="{ borderTopColor: col.color }">
          <span class="column-title">{{ col.label }}</span>
          <el-badge :value="col.tasks.length" :max="99" class="column-count" />
        </div>
        <div class="column-body">
          <div
            v-for="task in col.tasks"
            :key="task.id"
            class="task-card"
            @click="goDetail(task)"
          >
            <div class="task-card-header">
              <el-tag :type="priorityMap[task.priority]?.type" size="small">{{ priorityMap[task.priority]?.label || task.priority }}</el-tag>
            </div>
            <div class="task-project" v-if="task.project_name"><span style="color:#999">项目：</span>{{ task.project_name }}</div>
            <div class="task-req" v-if="task.requirement_title"><span style="color:#999">需求：</span>{{ task.requirement_title }}</div>
            <div class="task-title"><span style="color:#999">任务：</span>{{ task.title }}</div>
            <div class="task-meta">
              <span v-if="task.end_date" class="task-due">
                <el-icon><Calendar /></el-icon>
                <span>预计完成：</span>{{ task.end_date }}
                <el-tag v-if="isDelayed(task)" type="danger" size="small" style="margin-left:2px">已延期</el-tag>
              </span>
            </div>
            <div class="task-time"><span>创建时间：</span>{{ task.created_at }}</div>
            <div class="task-actions" @click.stop>
              <el-button
                v-if="getMyStatus(task) === 'pending'"
                type="primary" size="small" plain
                @click="changeStatus(task, 'in_progress')"
              >开始</el-button>
              <el-button
                v-if="getMyStatus(task) === 'in_progress'"
                type="success" size="small" plain
                @click="changeStatus(task, 'done')"
              >完成</el-button>
            </div>
          </div>
          <div v-if="!col.tasks.length" class="empty-column">
            <el-icon><DocumentAdd /></el-icon>
            <span>暂无任务</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Calendar, DocumentAdd } from '@element-plus/icons-vue'
import { getBoard, updateTask } from '@/api/task'
import { listProjects } from '@/api/project'
import { useUserStore } from '@/store/user'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const selectedProject = ref('')
const projects = ref([])
const boardData = ref({ pending: [], in_progress: [], done: [] })

const priorityMap = {
  urgent: { label: '紧急', type: 'danger' },
  high: { label: '高', type: 'warning' },
  medium: { label: '中', type: '' },
  low: { label: '低', type: 'info' }
}

// 获取当前用户在某任务中的个人状态
function getMyStatus(task) {
  const uid = userStore.userInfo?.id
  if (task.assignees && task.assignees.length) {
    const mine = task.assignees.find(a => a.user_id === uid || a.user?.id === uid)
    if (mine) return mine.status
  }
  if (task.assignee?.id === uid) return task.status
  return null
}

// 按个人子表状态分列，不是按主任务状态
const columns = computed(() => {
  const allTasks = [
    ...(boardData.value.pending || []),
    ...(boardData.value.in_progress || []),
    ...(boardData.value.done || []),
  ]
  const pending = [], inProgress = [], done = []
  const seen = new Set()
  for (const t of allTasks) {
    if (seen.has(t.id)) continue
    seen.add(t.id)
    const myStatus = getMyStatus(t)
    if (!myStatus) continue
    if (myStatus === 'done') done.push(t)
    else if (myStatus === 'in_progress') inProgress.push(t)
    else pending.push(t)
  }
  return [
    { status: 'pending', label: '待处理', color: '#909399', tasks: pending },
    { status: 'in_progress', label: '进行中', color: '#e6a23c', tasks: inProgress },
    { status: 'done', label: '已完成', color: '#67c23a', tasks: done },
  ]
})

function isDelayed(task) {
  if (task.status === 'done' || task.status === 'voided') return false
  if (!task.end_date) return false
  return new Date(task.end_date) < new Date(new Date().toISOString().split('T')[0])
}

function goDetail(task) {
  router.push(`/task/${task.id}`)
}

async function changeStatus(task, newStatus) {
  try {
    await updateTask(task.id, { status: newStatus })
    ElMessage.success('状态已更新')
    loadMyTasks()
  } catch (e) {}
}

async function loadMyTasks() {
  loading.value = true
  try {
    const params = {}
    if (selectedProject.value) params.project_id = selectedProject.value
    const res = await getBoard(params)
    boardData.value = {
      pending: res.pending || [],
      in_progress: res.in_progress || [],
      done: res.done || []
    }
  } catch (e) {
    boardData.value = { pending: [], in_progress: [], done: [] }
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

onMounted(() => { loadMyTasks(); loadProjects() })
</script>

<style scoped>
.page-container { min-height: 100%; }
.board-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.board-header h2 { font-size: 20px; color: #333; }
.board-filters { display: flex; gap: 12px; align-items: center; }
.kanban-board {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  min-height: 500px;
}
.kanban-column {
  flex: 1;
  min-width: 280px;
  background: #f4f5f7;
  border-radius: 8px;
  overflow: hidden;
}
.column-header {
  padding: 12px 16px;
  background: #fff;
  border-top: 3px solid #ccc;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.column-title { font-weight: 600; color: #333; }
.column-body { padding: 8px; min-height: 400px; }
.task-card {
  background: #fff;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  transition: box-shadow 0.2s;
  cursor: pointer;
}
.task-card:hover { box-shadow: 0 3px 8px rgba(0,0,0,0.15); }
.task-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.task-title { font-size: 14px; color: #333; margin-bottom: 4px; line-height: 1.4; }
.task-req { font-size: 12px; color: #333; margin-bottom: 4px; }
.task-time { font-size: 11px; color: #bbb; margin-bottom: 8px; }
.task-meta { display: flex; justify-content: space-between; font-size: 12px; color: #666; margin-bottom: 8px; }
.task-due { display: flex; align-items: center; gap: 3px; }
.task-actions { display: flex; justify-content: flex-end; }
.empty-column {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 0;
  color: #ccc;
  gap: 8px;
  font-size: 13px;
}
</style>
