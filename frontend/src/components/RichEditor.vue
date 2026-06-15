<template>
  <div class="rich-editor">
    <Toolbar :editor="editorRef" :defaultConfig="toolbarConfig" style="border-bottom: 1px solid #ccc" />
    <Editor
      :defaultConfig="editorConfig"
      :modelValue="modelValue"
      @onCreated="handleCreated"
      @onChange="handleChange"
      style="height: 350px; overflow-y: hidden"
    />
  </div>
</template>

<script setup>
import '@wangeditor/editor/dist/css/style.css'
import { onBeforeUnmount, ref, shallowRef } from 'vue'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'

const props = defineProps({
  modelValue: { type: String, default: '' }
})
const emit = defineEmits(['update:modelValue'])

const editorRef = shallowRef()

const toolbarConfig = {
  excludeKeys: ['group-video']
}

const editorConfig = {
  placeholder: '请输入内容...',
  MENU_CONF: {
    uploadImage: {
      server: '/api/attachments/upload-editor',
      fieldName: 'file',
      maxFileSize: 10 * 1024 * 1024,
      allowedFileTypes: ['image/*'],
      headers: {
        Authorization: `Bearer ${localStorage.getItem('token')}`
      },
      customInsert(res, insertFn) {
        const url = res.data?.url || res.url || ''
        if (url) insertFn(url, '', '')
      }
    },
    uploadVideo: {
      server: '/api/attachments/upload-editor',
      fieldName: 'file',
      maxFileSize: 100 * 1024 * 1024,
      headers: {
        Authorization: `Bearer ${localStorage.getItem('token')}`
      },
      customInsert(res, insertFn) {
        const url = res.data?.url || res.url || ''
        if (url) insertFn(url, '')
      }
    }
  }
}

function handleCreated(editor) {
  editorRef.value = editor
}

function handleChange(editor) {
  emit('update:modelValue', editor.getHtml())
}

onBeforeUnmount(() => {
  const editor = editorRef.value
  if (editor) editor.destroy()
})
</script>

<style scoped>
.rich-editor {
  border: 1px solid #ccc;
  border-radius: 4px;
  overflow: hidden;
  line-height: normal;
}
</style>
