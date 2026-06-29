// 附件在线预览相关判断
const ARCHIVE_EXT = ['zip', 'rar', '7z', 'tar', 'gz', 'tgz', 'bz2', 'xz']
const IMAGE_EXT = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico']

function fileExt(name = '') {
  const i = name.lastIndexOf('.')
  return i < 0 ? '' : name.slice(i + 1).toLowerCase()
}

// 是否图片（按 MIME 或扩展名）
export function isImageFile(row) {
  if ((row.file_type || '').startsWith('image/')) return true
  return IMAGE_EXT.includes(fileExt(row.file_name))
}

// 是否可在线预览：除压缩包外都给预览入口（图片/视频/PDF/文本由浏览器内联打开）
export function canPreview(row) {
  return !ARCHIVE_EXT.includes(fileExt(row.file_name))
}
