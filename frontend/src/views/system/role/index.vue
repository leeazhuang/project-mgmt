<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">角色管理</span>
          <el-button v-if="userStore.hasPermission('role:create')" type="primary" :icon="Plus" @click="openDialog()">新增角色</el-button>
        </div>
      </template>

      <el-table :data="roleList" v-loading="loading" border stripe>
        <el-table-column prop="name" label="角色名称" min-width="150" />
        <el-table-column prop="code" label="角色代码" min-width="150" />
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button v-if="userStore.hasPermission('role:update')" type="primary" size="small" text @click="openDialog(row)">编辑</el-button>
            <el-button v-if="userStore.hasPermission('role:delete')" type="danger" size="small" text @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, prev, pager, next"
        style="margin-top:16px;justify-content:flex-end"
        @change="loadRoles"
      />
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingRole ? '编辑角色' : '新增角色'"
      width="700px"
      :close-on-click-modal="false"
    >
      <el-form ref="roleFormRef" :model="roleForm" :rules="roleRules" label-width="100px">
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="roleForm.name" placeholder="请输入角色名称" />
        </el-form-item>
        <el-form-item label="角色代码" prop="code">
          <el-input v-model="roleForm.code" placeholder="请输入角色代码（英文）" :disabled="!!editingRole" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="roleForm.description" type="textarea" rows="2" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="菜单权限">
          <el-tree
            ref="menuTreeRef"
            :data="menuTreeData"
            show-checkbox
            check-strictly
            node-key="id"
            :props="{ label: 'name', children: 'children' }"
            style="width:100%;max-height:300px;overflow-y:auto;border:1px solid #ddd;border-radius:4px;padding:8px"
          />
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
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { listRoles, createRole, updateRole, deleteRole } from '@/api/role'
import { listMenus } from '@/api/menu'
import { useUserStore } from '@/store/user'

const userStore = useUserStore()

const loading = ref(false)
const submitting = ref(false)
const roleList = ref([])
const menuTreeData = ref([])
const dialogVisible = ref(false)
const editingRole = ref(null)

const pagination = reactive({ page: 1, pageSize: 10, total: 0 })
const roleFormRef = ref(null)
const menuTreeRef = ref(null)

const roleForm = reactive({
  name: '',
  code: '',
  description: '',
  menu_ids: []
})

const roleRules = {
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入角色代码', trigger: 'blur' }]
}

async function loadRoles() {
  loading.value = true
  try {
    const res = await listRoles({ page: pagination.page, page_size: pagination.pageSize })
    roleList.value = res.items || res || []
    pagination.total = res.total || roleList.value.length
  } catch (e) {
    roleList.value = []
  } finally {
    loading.value = false
  }
}

async function loadMenuTree() {
  try {
    const res = await listMenus()
    menuTreeData.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) {
    menuTreeData.value = []
  }
}

function openDialog(role = null) {
  editingRole.value = role
  if (role) {
    Object.assign(roleForm, {
      name: role.name,
      code: role.code,
      description: role.description || '',
      menu_ids: role.menu_ids || (role.menus || []).map(m => m.id)
    })
  } else {
    Object.assign(roleForm, { name: '', code: '', description: '', menu_ids: [] })
  }
  dialogVisible.value = true
  // default-checked-keys 只在树首次挂载生效一次，el-dialog 不销毁导致复用旧状态；
  // 每次打开主动用 setCheckedKeys 回填当前角色菜单，保证勾选与保存正确
  nextTick(() => {
    menuTreeRef.value?.setCheckedKeys(roleForm.menu_ids || [])
  })
}

async function handleSubmit() {
  const valid = await roleFormRef.value?.validate().catch(() => false)
  if (!valid) return

  // check-strictly 下父子独立，无半选，直接取勾选项即可
  const menu_ids = menuTreeRef.value?.getCheckedKeys() || []

  submitting.value = true
  try {
    const payload = { ...roleForm, menu_ids }
    if (editingRole.value) {
      await updateRole(editingRole.value.id, payload)
      ElMessage.success('更新成功')
    } else {
      await createRole(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadRoles()
  } catch (e) {
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除角色 "${row.name}" 吗？`, '警告', {
    type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消'
  })
  try {
    await deleteRole(row.id)
    ElMessage.success('删除成功')
    loadRoles()
  } catch (e) {}
}

onMounted(() => {
  loadRoles()
  loadMenuTree()
})
</script>

<style scoped>
.page-container { min-height: 100%; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-size: 16px; font-weight: 600; }
</style>
