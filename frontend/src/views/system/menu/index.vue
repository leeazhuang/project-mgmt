<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">菜单管理</span>
          <el-button v-if="userStore.hasPermission('menu:create')" type="primary" :icon="Plus" @click="openDialog()">新增菜单</el-button>
        </div>
      </template>

      <el-table
        :data="menuList"
        v-loading="loading"
        border
        row-key="id"
        :tree-props="{ children: 'children' }"
        default-expand-all
      >
        <el-table-column prop="name" label="菜单名称" min-width="180" />
        <el-table-column prop="icon" label="图标" width="100" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="typeTagMap[row.type]" size="small">{{ typeLabel[row.type] || row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="path" label="路径" min-width="150" />
        <el-table-column prop="permission_code" label="权限代码" min-width="160" />
        <el-table-column prop="sort_order" label="排序" width="80" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button v-if="userStore.hasPermission('menu:update')" type="primary" size="small" text @click="openDialog(row)">编辑</el-button>
            <el-button v-if="userStore.hasPermission('menu:create')" type="primary" size="small" text @click="openDialog(null, row)">添加子项</el-button>
            <el-button v-if="userStore.hasPermission('menu:delete')" type="danger" size="small" text @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingMenu ? '编辑菜单' : '新增菜单'"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form ref="menuFormRef" :model="menuForm" :rules="menuRules" label-width="100px">
        <el-form-item label="上级菜单">
          <el-select v-model="menuForm.parent_id" placeholder="无（顶级菜单）" clearable style="width:100%">
            <el-option
              v-for="item in flatMenus"
              :key="item.id"
              :label="item.fullName"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="菜单名称" prop="name">
          <el-input v-model="menuForm.name" placeholder="请输入菜单名称" />
        </el-form-item>
        <el-form-item label="类型" prop="type">
          <el-radio-group v-model="menuForm.type">
            <el-radio value="directory">目录</el-radio>
            <el-radio value="menu">菜单</el-radio>
            <el-radio value="button">按钮</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="图标" v-if="menuForm.type !== 'button'">
          <el-input v-model="menuForm.icon" placeholder="图标名称（如 House, User）" />
        </el-form-item>
        <el-form-item label="路径" v-if="menuForm.type !== 'button'">
          <el-input v-model="menuForm.path" placeholder="路由路径（如 /dashboard）" />
        </el-form-item>
        <el-form-item label="权限代码">
          <el-input v-model="menuForm.permission_code" placeholder="权限代码（如 user:list）" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="menuForm.sort_order" :min="0" :max="999" />
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
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { listMenus, createMenu, updateMenu, deleteMenu } from '@/api/menu'
import { useUserStore } from '@/store/user'

const userStore = useUserStore()

const loading = ref(false)
const submitting = ref(false)
const menuList = ref([])
const dialogVisible = ref(false)
const editingMenu = ref(null)

const typeTagMap = { directory: '', menu: 'success', button: 'warning' }
const typeLabel = { directory: '目录', menu: '菜单', button: '按钮' }

const menuFormRef = ref(null)
const menuForm = reactive({
  parent_id: null,
  name: '',
  type: 'menu',
  icon: '',
  path: '',
  permission_code: '',
  sort_order: 0
})

const menuRules = {
  name: [{ required: true, message: '请输入菜单名称', trigger: 'blur' }],
  type: [{ required: true, message: '请选择类型', trigger: 'change' }]
}

const flatMenus = computed(() => {
  const result = []
  function flatten(list, prefix = '') {
    list.forEach(item => {
      result.push({ ...item, fullName: prefix + item.name })
      if (item.children?.length) flatten(item.children, prefix + item.name + ' / ')
    })
  }
  flatten(menuList.value)
  return result
})

async function loadMenus() {
  loading.value = true
  try {
    const res = await listMenus()
    menuList.value = Array.isArray(res) ? res : (res.items || [])
  } catch (e) {
    menuList.value = []
  } finally {
    loading.value = false
  }
}

function openDialog(menu = null, parent = null) {
  editingMenu.value = menu
  if (menu) {
    Object.assign(menuForm, {
      parent_id: menu.parent_id || null,
      name: menu.name,
      type: menu.type || 'menu',
      icon: menu.icon || '',
      path: menu.path || '',
      permission_code: menu.permission_code || '',
      sort_order: menu.sort_order || 0
    })
  } else {
    Object.assign(menuForm, {
      parent_id: parent?.id || null,
      name: '', type: 'menu', icon: '', path: '', permission_code: '', sort_order: 0
    })
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await menuFormRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (editingMenu.value) {
      await updateMenu(editingMenu.value.id, menuForm)
      ElMessage.success('更新成功')
    } else {
      await createMenu(menuForm)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadMenus()
  } catch (e) {
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除菜单 "${row.name}" 吗？`, '警告', {
    type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消'
  })
  try {
    await deleteMenu(row.id)
    ElMessage.success('删除成功')
    loadMenus()
  } catch (e) {}
}

onMounted(loadMenus)
</script>

<style scoped>
.page-container { min-height: 100%; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-size: 16px; font-weight: 600; }
</style>
