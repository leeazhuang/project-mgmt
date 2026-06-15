<template>
  <el-container class="layout-container">
    <el-aside width="220px" class="layout-aside">
      <Sidebar />
    </el-aside>
    <el-container class="layout-right">
      <el-header class="layout-header">
        <Navbar />
      </el-header>
      <el-main class="layout-main">
        <AppMain />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import Sidebar from './Sidebar.vue'
import Navbar from './Navbar.vue'
import AppMain from './AppMain.vue'
</script>

<style scoped>
.layout-container {
  height: 100vh;
  width: 100%;
}
.layout-aside {
  background-color: #001529;
  overflow: hidden;
}
.layout-right {
  flex: 1;
  overflow: hidden;
}
.layout-header {
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  padding: 0;
  height: 60px;
  display: flex;
  align-items: center;
}
.layout-main {
  background-color: #f0f2f5;
  overflow-y: auto;
  padding: 20px;
}
</style>
