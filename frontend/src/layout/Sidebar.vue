<template>
  <div class="sidebar-container">
    <div class="logo">
      <span class="logo-text">项目管理系统</span>
    </div>
    <el-menu
      :default-active="activeMenu"
      router
      background-color="#001529"
      text-color="#b7bec8"
      active-text-color="#ffffff"
      class="sidebar-menu"
      :collapse="false"
    >
      <template v-for="menu in displayMenus" :key="menu.id">
        <!-- 目录：有子菜单的用 sub-menu -->
        <el-sub-menu
          v-if="menu.type === 'directory' && visibleChildren(menu).length"
          :index="menu.path || String(menu.id)"
        >
          <template #title>
            <el-icon v-if="menu.icon"><component :is="menu.icon" /></el-icon>
            <span>{{ menu.name }}</span>
          </template>
          <el-menu-item
            v-for="child in visibleChildren(menu)"
            :key="child.id"
            :index="child.path || String(child.id)"
          >
            <el-icon v-if="child.icon"><component :is="child.icon" /></el-icon>
            <span>{{ child.name }}</span>
          </el-menu-item>
        </el-sub-menu>
        <!-- 普通菜单 -->
        <el-menu-item
          v-else-if="menu.type === 'menu'"
          :index="menu.path || String(menu.id)"
        >
          <el-icon v-if="menu.icon"><component :is="menu.icon" /></el-icon>
          <span>{{ menu.name }}</span>
        </el-menu-item>
        <!-- button 类型不渲染 -->
      </template>
    </el-menu>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/store/user'

const route = useRoute()
const userStore = useUserStore()

const activeMenu = computed(() => route.path)
const displayMenus = computed(() => userStore.menus || [])

// 过滤子菜单：只显示 type=menu 的，不显示 button
function visibleChildren(menu) {
  return (menu.children || []).filter(c => c.type === 'menu')
}
</script>

<style scoped>
.sidebar-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #002140;
  flex-shrink: 0;
}
.logo-text {
  color: #fff;
  font-size: 16px;
  font-weight: bold;
  white-space: nowrap;
}
.sidebar-menu {
  flex: 1;
  border-right: none;
  overflow-y: auto;
  overflow-x: hidden;
}
.sidebar-menu::-webkit-scrollbar {
  width: 4px;
}
.sidebar-menu::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.2);
  border-radius: 2px;
}
</style>
