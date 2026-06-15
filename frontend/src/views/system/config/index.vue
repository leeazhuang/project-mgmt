<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">系统设置</span>
        </div>
      </template>

      <el-form ref="formRef" :model="form" label-width="180px" style="max-width:700px" v-loading="loading">
        <el-divider content-position="left">企微机器人通知</el-divider>

        <el-form-item label="机器人API地址">
          <el-input v-model="form.wx_bot_url" placeholder="http://机器人服务地址:端口/api" clearable />
          <div class="form-tip">企微HOOK机器人完整接口地址（带 /api 后缀），通知将通过它发送群艾特消息</div>
        </el-form-item>

        <el-divider content-position="left">兜底告警（机器人通知失败时触发）</el-divider>

        <el-form-item label="兜底Webhook地址">
          <el-input v-model="form.wechat_work_webhook_url" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx" clearable />
          <div class="form-tip">企业微信群 → 群机器人 → 添加机器人 → 复制Webhook地址。机器人通知失败时把失败信息推到这里</div>
        </el-form-item>

        <el-form-item label="兜底接收人UserId">
          <el-input v-model="form.notify_fallback_userid" placeholder="hns" clearable />
          <div class="form-tip">机器人通知失败时在兜底消息中艾特的企微UserId</div>
        </el-form-item>

        <el-divider content-position="left">阿里云OSS存储</el-divider>

        <el-form-item label="启用OSS存储">
          <el-switch
            v-model="form.oss_enabled"
            active-value="true"
            inactive-value="false"
            active-text="启用"
            inactive-text="关闭"
          />
          <div class="form-tip">启用后新上传的图片/附件存阿里云OSS，关闭则存服务器本地磁盘（历史文件不受影响）</div>
        </el-form-item>

        <el-form-item label="AccessKey ID">
          <el-input v-model="form.oss_access_key_id" placeholder="LTAI****************" clearable />
        </el-form-item>

        <el-form-item label="AccessKey Secret">
          <el-input v-model="form.oss_access_key_secret" type="password" show-password placeholder="阿里云AccessKey Secret" clearable />
        </el-form-item>

        <el-form-item label="Bucket名称">
          <el-input v-model="form.oss_bucket" placeholder="my-bucket" clearable />
        </el-form-item>

        <el-form-item label="Endpoint">
          <el-input v-model="form.oss_endpoint" placeholder="oss-cn-beijing.aliyuncs.com" clearable />
          <div class="form-tip">在OSS控制台 Bucket 概览页查看，填外网Endpoint，不带 bucket 前缀</div>
        </el-form-item>

        <el-form-item label="存储路径">
          <el-input v-model="form.oss_base_path" placeholder="project-mgmt" clearable />
          <div class="form-tip">所有文件存到 Bucket 下该路径，完整路径为：存储路径/年/月/日/文件名，如 project-mgmt/2026/06/12/xxx.png</div>
        </el-form-item>

        <el-divider content-position="left">站点配置</el-divider>

        <el-form-item label="站点访问地址">
          <el-input v-model="form.site_url" placeholder="https://your-domain.com" clearable />
          <div class="form-tip">用于推送卡片的跳转链接，如 https://pm.company.com</div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSave">保存设置</el-button>
          <el-button @click="handleTest" :loading="testing">测试机器人连接</el-button>
          <el-button @click="handleTestFallback" :loading="testingFallback">测试兜底告警</el-button>
          <el-button @click="handleTestOss" :loading="testingOss">测试OSS连接</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 机器人测试弹框 -->
    <el-dialog v-model="testDialogVisible" title="测试机器人通知" width="480px" :close-on-click-modal="false">
      <el-form label-width="80px">
        <el-form-item label="微信群" required>
          <el-select
            v-model="testForm.room_id"
            placeholder="选择测试群"
            filterable
            style="width:100%"
            :loading="groupsLoading"
            @change="handleTestGroupChange"
          >
            <el-option v-for="g in groupOptions" :key="g.room_id" :label="`${g.nickname} (${g.total}人) [${g.room_id}]`" :value="g.room_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="接收人">
          <el-select
            v-model="testForm.at_user_id"
            placeholder="选择要艾特的成员（不选则只发群消息）"
            clearable
            filterable
            style="width:100%"
            :disabled="!testForm.room_id"
            :loading="membersLoading"
          >
            <el-option
              v-for="m in memberOptions"
              :key="m.user_id"
              :label="`${m.realname || m.nickname} [${m.user_id}]`"
              :value="m.user_id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="testDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="testing" @click="submitBotTest">发送测试消息</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getAllConfig, updateConfig, testWebhook, testOss } from '@/api/sysConfig'
import { getWxGroups, getWxGroupMembers, testWxBot } from '@/api/wxbot'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const testingFallback = ref(false)
const testingOss = ref(false)

const form = reactive({
  wx_bot_url: '',
  wechat_work_webhook_url: '',
  notify_fallback_userid: '',
  oss_enabled: 'false',
  oss_access_key_id: '',
  oss_access_key_secret: '',
  oss_bucket: '',
  oss_endpoint: '',
  oss_base_path: '',
  site_url: '',
})

const configKeys = [
  'wx_bot_url', 'wechat_work_webhook_url', 'notify_fallback_userid',
  'oss_enabled', 'oss_access_key_id', 'oss_access_key_secret', 'oss_bucket', 'oss_endpoint', 'oss_base_path',
  'site_url',
]

async function loadConfig() {
  loading.value = true
  try {
    const data = await getAllConfig()
    for (const key of configKeys) {
      if (data[key] !== undefined) {
        form[key] = data[key]
      }
    }
  } catch (e) {}
  finally { loading.value = false }
}

async function handleSave() {
  saving.value = true
  try {
    for (const key of configKeys) {
      await updateConfig({ config_key: key, config_value: form[key] || '' })
    }
    ElMessage.success('保存成功')
  } catch (e) {}
  finally { saving.value = false }
}

const testDialogVisible = ref(false)
const groupsLoading = ref(false)
const membersLoading = ref(false)
const groupOptions = ref([])
const memberOptions = ref([])
const testForm = reactive({ room_id: '', at_user_id: '' })

async function handleTest() {
  if (!form.wx_bot_url) {
    ElMessage.warning('请先填写并保存机器人API地址后再测试')
    return
  }
  testForm.room_id = ''
  testForm.at_user_id = ''
  memberOptions.value = []
  testDialogVisible.value = true
  if (!groupOptions.value.length) {
    groupsLoading.value = true
    try {
      groupOptions.value = await getWxGroups() || []
    } catch (e) {
      ElMessage.error('获取群列表失败，请检查机器人地址')
    } finally {
      groupsLoading.value = false
    }
  }
}

async function handleTestGroupChange(roomId) {
  testForm.at_user_id = ''
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

async function submitBotTest() {
  if (!testForm.room_id) {
    ElMessage.warning('请选择微信群')
    return
  }
  testing.value = true
  try {
    await testWxBot({ room_id: testForm.room_id, at_user_id: testForm.at_user_id || '' })
    ElMessage.success('测试消息已发送，请查看微信群')
    testDialogVisible.value = false
  } catch (e) {
    // handled by interceptor
  } finally {
    testing.value = false
  }
}

async function handleTestOss() {
  testingOss.value = true
  try {
    const res = await testOss()
    ElMessage.success('OSS连接成功，上传/删除测试通过')
  } catch (e) {
    // handled by interceptor
  } finally {
    testingOss.value = false
  }
}

async function handleTestFallback() {
  if (!form.wechat_work_webhook_url) {
    ElMessage.warning('请先填写并保存兜底Webhook地址后再测试')
    return
  }
  testingFallback.value = true
  try {
    await testWebhook()
    ElMessage.success('兜底测试消息已发送，请查看企业微信群')
  } catch (e) {
    ElMessage.error(e?.message || '发送失败')
  } finally {
    testingFallback.value = false
  }
}

onMounted(() => { loadConfig() })
</script>

<style scoped>
.page-container { min-height: 100%; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-size: 16px; font-weight: 600; }
.form-tip { font-size: 12px; color: #909399; margin-top: 4px; line-height: 1.4; }
</style>
