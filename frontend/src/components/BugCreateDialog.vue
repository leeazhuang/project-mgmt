<template>
  <el-dialog v-model="visible" title="新增Bug" width="850px" top="5vh" :close-on-click-modal="false" @closed="onClosed" class="bug-create-dialog">
    <el-form ref="bugFormRef" :model="bugForm" :rules="bugRules" label-width="100px">
      <el-form-item label="所属项目" prop="project_id">
        <el-select v-model="bugForm.project_id" filterable placeholder="请选择项目" style="width:100%">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="Bug标题" prop="title">
        <el-input v-model="bugForm.title" placeholder="请输入Bug标题" />
      </el-form-item>
      <el-form-item label="严重程度" prop="severity">
        <el-radio-group v-model="bugForm.severity">
          <el-radio value="critical">严重</el-radio>
          <el-radio value="major">主要</el-radio>
          <el-radio value="minor">次要</el-radio>
          <el-radio value="trivial">轻微</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="优先级" prop="priority">
        <el-radio-group v-model="bugForm.priority">
          <el-radio value="urgent">紧急</el-radio>
          <el-radio value="high">高</el-radio>
          <el-radio value="medium">中</el-radio>
          <el-radio value="low">低</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="Bug描述">
        <RichEditor v-model="bugForm.description" />
      </el-form-item>
      <el-form-item label="环境信息">
        <el-input v-model="bugForm.environment" placeholder="操作系统、浏览器版本等" />
      </el-form-item>
      <el-form-item label="附件">
        <el-upload
          :action="uploadUrl"
          :headers="uploadHeaders"
          :data="uploadData"
          v-model:file-list="fileList"
          :on-success="handleUploadSuccess"
          :on-remove="handleUploadRemove"
          :before-upload="beforeUpload"
          multiple
        >
          <el-button type="primary" plain>上传附件</el-button>
          <template #tip>
            <div class="el-upload__tip">支持任意格式文件，单个文件不超过 50MB</div>
          </template>
        </el-upload>
      </el-form-item>
    </el-form>

    <div class="bug-guide">
      <div class="guide-title">提Bug规范</div>
      <ol>
        <li><b>标题简明扼要</b>：用一句话概括问题，如"登录页点击提交后白屏"，避免"有个Bug"这类模糊描述</li>
        <li><b>附带关键信息</b>：若商户问题请附带商户号，交易问题请附带交易单号</li>
        <li><b>描述复现步骤</b>：按 1、2、3 步骤写清楚操作路径，方便开发快速定位</li>
        <li><b>说明预期与实际</b>：描述"期望的结果"和"实际的结果"分别是什么</li>
        <li><b>附上截图或录屏</b>：能截图就截图，能录屏更好，一图胜千言</li>
        <li><b>正确选择严重程度</b>：严重=系统崩溃/数据丢失，主要=核心功能不可用，次要=非核心功能异常，轻微=UI/文案问题</li>
      </ol>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import RichEditor from '@/components/RichEditor.vue'
import { createBug } from '@/api/bug'
import { deleteAttachment, bindAttachments } from '@/api/attachment'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  projects: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'created'])

const visible = ref(false)
watch(() => props.modelValue, v => {
  visible.value = v
  // 打开时默认选第一个项目（最早创建的）
  if (v && !bugForm.project_id && props.projects.length) {
    bugForm.project_id = props.projects[0].id
  }
})
watch(visible, v => { emit('update:modelValue', v) })

const submitting = ref(false)
const bugFormRef = ref(null)
const fileList = ref([])
const uploadUrl = '/api/attachments'
const uploadHeaders = { Authorization: `Bearer ${localStorage.getItem('token')}` }
const uploadData = reactive({ target_id: 0, target_type: 'bug' })

const bugForm = reactive({
  project_id: null, title: '', severity: 'major', priority: 'medium',
  description: '', environment: ''
})
const bugRules = {
  project_id: [{ required: true, message: '请选择项目', trigger: 'change' }],
  title: [{ required: true, message: '请输入Bug标题', trigger: 'blur' }],
  severity: [{ required: true, message: '请选择严重程度', trigger: 'change' }]
}

function beforeUpload(file) {
  if (file.size > 50 * 1024 * 1024) { ElMessage.error('文件大小不能超过 50MB'); return false }
  return true
}
function handleUploadSuccess(response, file) { file.attachmentId = (response?.data || response)?.id }
function handleUploadRemove(file) { if (file.attachmentId) deleteAttachment(file.attachmentId).catch(() => {}) }

function onClosed() {
  Object.assign(bugForm, { project_id: null, title: '', severity: 'major', priority: 'medium', description: '', environment: '' })
  fileList.value = []
}

async function handleSubmit() {
  const valid = await bugFormRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const res = await createBug(bugForm)
    const newId = res?.id || res
    const attachmentIds = fileList.value.map(f => f.attachmentId || f.response?.data?.id).filter(Boolean)
    if (attachmentIds.length && newId) {
      await bindAttachments({ attachment_ids: attachmentIds, target_id: newId, target_type: 'bug' }).catch(() => {})
    }
    ElMessage.success('创建成功')
    visible.value = false
    emit('created')
  } catch (e) {} finally { submitting.value = false }
}
</script>

<style scoped>
:deep(.bug-create-dialog .el-dialog__body) {
  max-height: 70vh;
  overflow-y: auto;
}
.bug-guide {
  margin-top: 16px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 6px;
  border: 1px solid #ebeef5;
}
.guide-title {
  font-weight: 600;
  font-size: 14px;
  color: #333;
  margin-bottom: 10px;
}
.bug-guide ol {
  margin: 0;
  padding-left: 20px;
  color: #606266;
  font-size: 13px;
  line-height: 2;
}
.bug-guide b { color: #333; }
</style>
