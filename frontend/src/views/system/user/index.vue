<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">用户管理</span>
          <el-button v-if="userStore.hasPermission('user:create')" type="primary" :icon="Plus" @click="openDialog()">新增用户</el-button>
        </div>
      </template>

      <!-- Search Bar -->
      <div class="search-bar">
        <el-input
          v-model="searchForm.keyword"
          placeholder="搜索用户名/姓名"
          clearable
          style="width:250px"
          @clear="loadUsers"
          @keyup.enter="loadUsers"
        />
        <el-button type="primary" :icon="Search" @click="loadUsers">搜索</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </div>

      <!-- Table -->
      <el-table :data="userList" v-loading="loading" border stripe style="width:100%">
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="real_name" label="姓名" width="100" />
        <el-table-column label="展示标签" min-width="120">
          <template #default="{ row }">
            <el-tag v-for="t in (row.display_tags || [])" :key="t" size="small" type="info" style="margin-right:4px">{{ t }}</el-tag>
            <span v-if="!(row.display_tags && row.display_tags.length)" style="color:#999">-</span>
          </template>
        </el-table-column>
        <el-table-column label="角色" min-width="140">
          <template #default="{ row }">
            <el-tag
              v-for="role in (row.roles || [])"
              :key="role.id"
              size="small"
              style="margin-right:4px"
            >{{ role.name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="微信群" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.wx_room_name">{{ row.wx_room_name }}</span>
            <span v-else-if="row.wx_room_id">{{ row.wx_room_id }}</span>
            <span v-else style="color:#999">未绑定</span>
          </template>
        </el-table-column>
        <el-table-column label="群成员" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag v-if="row.wx_user_id" type="success" size="small">{{ row.wx_user_name || row.wx_user_id }}</el-tag>
            <el-tag v-else-if="row.wx_room_id" type="warning" size="small">不艾特</el-tag>
            <span v-else style="color:#999">未绑定</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_enabled ? 'success' : 'danger'" size="small">
              {{ row.is_enabled ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <div class="action-btns">
              <el-button v-if="userStore.hasPermission('user:update')" type="primary" size="small" text @click="openDialog(row)">编辑</el-button>
              <el-button v-if="userStore.hasPermission('user:update')" type="warning" size="small" text @click="handleResetPassword(row)">重置密码</el-button>
              <el-button v-if="userStore.hasPermission('user:delete')" type="danger" size="small" text @click="handleDelete(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        style="margin-top:16px;justify-content:flex-end"
        @change="loadUsers"
      />
    </el-card>

    <!-- Create/Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingUser ? '编辑用户' : '新增用户'"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="userFormRef"
        :model="userForm"
        :rules="userRules"
        label-width="100px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="userForm.username" placeholder="请输入用户名" :disabled="!!editingUser" />
        </el-form-item>
        <el-form-item label="姓名" prop="real_name">
          <el-input v-model="userForm.real_name" placeholder="请输入真实姓名" />
        </el-form-item>
        <el-form-item v-if="!editingUser" label="密码" prop="password">
          <el-input v-model="userForm.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-form-item label="角色" prop="role_ids">
          <el-select v-model="userForm.role_ids" multiple placeholder="请选择角色" style="width:100%">
            <el-option v-for="role in roleOptions" :key="role.id" :label="role.name" :value="role.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="展示标签">
          <el-select
            v-model="userForm.display_tags"
            multiple
            filterable
            allow-create
            default-first-option
            :reserve-keyword="false"
            placeholder="输入标签后回车（可多个）；分配任务/Bug时可按标签代称展示"
            style="width:100%"
          >
            <el-option v-for="t in userForm.display_tags" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="微信群" prop="wx_room_id">
          <el-select
            v-model="userForm.wx_room_id"
            placeholder="选择通知微信群"
            clearable
            filterable
            style="width:100%"
            :loading="groupsLoading"
            @change="handleGroupChange"
          >
            <el-option v-for="g in groupOptions" :key="g.room_id" :label="`${g.nickname} (${g.total}人) [${g.room_id}]`" :value="g.room_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="群成员" prop="wx_user_id">
          <el-select
            v-model="userForm.wx_user_id"
            placeholder="选择要艾特的群成员"
            clearable
            filterable
            style="width:100%"
            :disabled="!userForm.wx_room_id"
            :loading="membersLoading"
            @change="handleMemberChange"
          >
            <el-option
              v-for="m in memberOptions"
              :key="m.user_id"
              :label="`${m.nickname && m.nickname !== m.realname ? `${m.realname || m.nickname} (${m.nickname})` : (m.realname || m.nickname)} [${m.user_id}]`"
              :value="m.user_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="is_enabled">
          <el-switch v-model="userForm.is_enabled" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- Reset Password Dialog -->
    <el-dialog v-model="resetPwdVisible" title="重置密码" width="400px">
      <el-form :model="resetPwdForm" label-width="80px">
        <el-form-item label="新密码">
          <el-input v-model="resetPwdForm.new_password" type="password" show-password placeholder="请输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPwdVisible = false">取消</el-button>
        <el-button type="primary" @click="submitResetPassword">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { listUsers, createUser, updateUser, deleteUser, resetPassword } from '@/api/user'
import { listRoles } from '@/api/role'
import { getWxGroups, getWxGroupMembers } from '@/api/wxbot'
import { useUserStore } from '@/store/user'

const userStore = useUserStore()

const loading = ref(false)
const submitting = ref(false)
const userList = ref([])
const roleOptions = ref([])
const dialogVisible = ref(false)
const resetPwdVisible = ref(false)
const editingUser = ref(null)
const resetPwdTarget = ref(null)

const searchForm = reactive({ keyword: '' })
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const userFormRef = ref(null)
const userForm = reactive({
  username: '',
  real_name: '',
  password: '',
  role_ids: [],
  wx_room_id: '',
  wx_room_name: '',
  wx_user_id: '',
  wx_user_name: '',
  display_tags: [],
  is_enabled: true
})

const groupOptions = ref([])
const memberOptions = ref([])
const groupsLoading = ref(false)
const membersLoading = ref(false)

async function loadGroups() {
  if (groupOptions.value.length) return
  groupsLoading.value = true
  try {
    groupOptions.value = await getWxGroups() || []
  } catch (e) {
    groupOptions.value = []
  } finally {
    groupsLoading.value = false
  }
}

async function loadMembers(roomId) {
  memberOptions.value = []
  if (!roomId) return
  membersLoading.value = true
  try {
    memberOptions.value = await getWxGroupMembers(roomId) || []
  } catch (e) {
    memberOptions.value = []
  } finally {
    membersLoading.value = false
  }
}

function handleGroupChange(roomId) {
  const g = groupOptions.value.find(x => x.room_id === roomId)
  userForm.wx_room_name = g ? g.nickname : ''
  userForm.wx_user_id = ''
  userForm.wx_user_name = ''
  loadMembers(roomId)
}

function handleMemberChange(userId) {
  const m = memberOptions.value.find(x => x.user_id === userId)
  userForm.wx_user_name = m ? (m.realname || m.nickname || '') : ''
}

const resetPwdForm = reactive({ new_password: '' })

const userRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  real_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur', min: 6, message: '密码至少6位' }],
  role_ids: [{ required: true, type: 'array', min: 1, message: '请选择角色', trigger: 'change' }],
  wx_room_id: [{ required: true, message: '请选择微信群', trigger: 'change' }],
  wx_user_id: [{ required: true, message: '请选择群成员', trigger: 'change' }]
}

async function loadUsers() {
  loading.value = true
  try {
    const res = await listUsers({
      keyword: searchForm.keyword,
      page: pagination.page,
      page_size: pagination.pageSize
    })
    userList.value = res.items || res || []
    pagination.total = res.total || userList.value.length
  } catch (e) {
    userList.value = []
  } finally {
    loading.value = false
  }
}

async function loadRoles() {
  try {
    const res = await listRoles({ page: 1, page_size: 100 })
    roleOptions.value = res.items || res || []
  } catch (e) {
    roleOptions.value = []
  }
}

function resetSearch() {
  searchForm.keyword = ''
  pagination.page = 1
  loadUsers()
}

function openDialog(user = null) {
  editingUser.value = user
  if (user) {
    Object.assign(userForm, {
      username: user.username,
      real_name: user.real_name || '',
      role_ids: (user.roles || []).map(r => r.id),
      wx_room_id: user.wx_room_id || '',
      wx_room_name: user.wx_room_name || '',
      wx_user_id: user.wx_user_id || '',
      wx_user_name: user.wx_user_name || '',
      display_tags: Array.isArray(user.display_tags) ? [...user.display_tags] : [],
      is_enabled: user.is_enabled !== false
    })
    if (user.wx_room_id) loadMembers(user.wx_room_id)
  } else {
    Object.assign(userForm, {
      username: '', real_name: '', password: '',
      role_ids: [],
      wx_room_id: '', wx_room_name: '', wx_user_id: '', wx_user_name: '',
      display_tags: [],
      is_enabled: true
    })
    memberOptions.value = []
  }
  loadGroups()
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await userFormRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (editingUser.value) {
      await updateUser(editingUser.value.id, userForm)
      ElMessage.success('更新成功')
    } else {
      await createUser(userForm)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadUsers()
  } catch (e) {
    // handled by interceptor
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除用户 "${row.username}" 吗？`, '警告', {
    type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消'
  })
  try {
    await deleteUser(row.id)
    ElMessage.success('删除成功')
    loadUsers()
  } catch (e) {}
}

function handleResetPassword(row) {
  resetPwdTarget.value = row
  resetPwdForm.new_password = ''
  resetPwdVisible.value = true
}

async function submitResetPassword() {
  if (!resetPwdForm.new_password) {
    ElMessage.warning('请输入新密码')
    return
  }
  try {
    await resetPassword(resetPwdTarget.value.id, { new_password: resetPwdForm.new_password })
    ElMessage.success('密码重置成功')
    resetPwdVisible.value = false
  } catch (e) {}
}

onMounted(() => {
  loadUsers()
  loadRoles()
})
</script>

<style scoped>
.page-container { min-height: 100%; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-size: 16px; font-weight: 600; }
.search-bar { display: flex; gap: 8px; margin-bottom: 16px; }
.action-btns { display: flex; flex-wrap: nowrap; align-items: center; gap: 0; }
</style>
