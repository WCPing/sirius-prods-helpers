<template>
  <div class="knowledge-container">
    <!-- 顶部导航 -->
    <div class="knowledge-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" link @click="$router.push('/')">返回</el-button>
        <el-divider direction="vertical" />
        <el-icon class="logo-icon"><Collection /></el-icon>
        <span class="header-title">知识源管理</span>
      </div>
      <div class="header-right">
        <el-button type="primary" :icon="Plus" @click="showAddDialog = true">
          新增知识源
        </el-button>
      </div>
    </div>

    <!-- 知识源表格 -->
    <div class="knowledge-body">
      <el-table
        :data="sources"
        v-loading="loading"
        stripe
        style="width: 100%"
        empty-text="暂无知识源，点击右上角添加"
      >
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column prop="source_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="typeTagMap[row.source_type] || 'info'" size="small">
              <el-icon style="margin-right: 4px">
                <component :is="typeIconMap[row.source_type] || 'Folder'" />
              </el-icon>
              {{ typeTextMap[row.source_type] || row.source_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="location" label="路径 / URL" min-width="250" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagMap[row.status] || 'info'" size="small" effect="light">
              {{ statusTextMap[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="180">
          <template #default="{ row }">
            {{ row.updated_at ? row.updated_at.replace('T', ' ').slice(0, 19) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :icon="Refresh" link @click="handleIndex(row)">
              索引
            </el-button>
            <el-button size="small" :icon="Download" link @click="handleSync(row)">
              同步
            </el-button>
            <el-button size="small" :icon="DataLine" link @click="handleStats(row)">
              统计
            </el-button>
            <el-button size="small" :icon="Delete" link type="danger" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 新增知识源对话框 -->
    <el-dialog v-model="showAddDialog" title="新增知识源" width="520px" :close-on-click-modal="false">
      <el-form :model="addForm" label-width="100px" :rules="addRules" ref="addFormRef">
        <el-form-item label="类型" prop="source_type">
          <el-select v-model="addForm.source_type" placeholder="选择类型" style="width: 100%">
            <el-option label="Git 仓库" value="git">
              <el-icon style="margin-right: 6px"><Link /></el-icon>Git 仓库
            </el-option>
            <el-option label="本地目录" value="local">
              <el-icon style="margin-right: 6px"><FolderOpened /></el-icon>本地目录
            </el-option>
            <el-option label="PDM 文件" value="pdm">
              <el-icon style="margin-right: 6px"><Document /></el-icon>PDM 文件
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="addForm.name" placeholder="知识源名称" />
        </el-form-item>
        <el-form-item label="路径 / URL" prop="location">
          <el-input
            v-model="addForm.location"
            :placeholder="addForm.source_type === 'git' ? 'Git 仓库 URL' : '本地目录路径'"
          />
        </el-form-item>
        <el-form-item v-if="addForm.source_type === 'git'" label="分支">
          <el-input v-model="addForm.branch" placeholder="main" />
        </el-form-item>
        <el-form-item label="匹配模式">
          <el-input v-model="addForm.include_patterns" placeholder=".java,.xml,.yml（逗号分隔，可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleAdd">确认添加</el-button>
      </template>
    </el-dialog>

    <!-- 统计对话框 -->
    <el-dialog v-model="showStatsDialog" title="索引统计" width="420px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="代码片段">{{ stats.code_chunks }}</el-descriptions-item>
        <el-descriptions-item label="配置条目">{{ stats.config_entries }}</el-descriptions-item>
        <el-descriptions-item label="交叉引用">{{ stats.cross_references }}</el-descriptions-item>
        <el-descriptions-item label="已索引文件">{{ stats.indexed_files }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="showStatsDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import {
  Plus, Delete, Refresh, Download, DataLine,
  ArrowLeft, Collection, Link, FolderOpened, Document, Folder
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listSources,
  registerSource,
  deleteSource,
  triggerIndex,
  syncSource,
  getSourceStats
} from '@/api/knowledge'

const loading = ref(false)
const sources = ref([])
const showAddDialog = ref(false)
const showStatsDialog = ref(false)
const submitting = ref(false)
const addFormRef = ref(null)

const addForm = reactive({
  source_type: 'local',
  name: '',
  location: '',
  branch: 'main',
  include_patterns: ''
})

const addRules = {
  source_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  location: [{ required: true, message: '请输入路径或 URL', trigger: 'blur' }]
}

const stats = reactive({
  code_chunks: 0,
  config_entries: 0,
  cross_references: 0,
  indexed_files: 0
})

const typeTagMap = { git: '', local: 'success', pdm: 'warning' }
const typeTextMap = { git: 'Git', local: '本地', pdm: 'PDM' }
const typeIconMap = { git: 'Link', local: 'FolderOpened', pdm: 'Document' }

const statusTagMap = {
  registered: 'info',
  indexing: 'warning',
  indexed: 'success',
  error: 'danger'
}
const statusTextMap = {
  registered: '已注册',
  indexing: '索引中',
  indexed: '已索引',
  error: '异常'
}

async function fetchSources() {
  loading.value = true
  try {
    const res = await listSources()
    sources.value = res.data || []
  } catch (e) {
    console.error('fetchSources error:', e)
  } finally {
    loading.value = false
  }
}

async function handleAdd() {
  const valid = await addFormRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await registerSource({
      name: addForm.name,
      source_type: addForm.source_type,
      location: addForm.location,
      branch: addForm.branch,
      include_patterns: addForm.include_patterns
    })
    ElMessage.success('知识源已添加')
    showAddDialog.value = false
    // 重置表单
    addForm.name = ''
    addForm.location = ''
    addForm.branch = 'main'
    addForm.include_patterns = ''
    await fetchSources()
  } catch (e) {
    console.error('handleAdd error:', e)
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除知识源「${row.name}」？此操作不可恢复。`,
      '提示',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteSource(row.id)
    ElMessage.success('已删除')
    await fetchSources()
  } catch {}
}

async function handleIndex(row) {
  try {
    await triggerIndex(row.id)
    ElMessage.success('索引任务已提交，正在后台执行')
    await fetchSources()
  } catch (e) {
    console.error('handleIndex error:', e)
  }
}

async function handleSync(row) {
  try {
    await syncSource(row.id)
    ElMessage.success('同步成功')
    await fetchSources()
  } catch (e) {
    console.error('handleSync error:', e)
  }
}

async function handleStats(row) {
  try {
    const res = await getSourceStats(row.id)
    stats.code_chunks = res.code_chunks || 0
    stats.config_entries = res.config_entries || 0
    stats.cross_references = res.cross_references || 0
    stats.indexed_files = res.indexed_files || 0
    showStatsDialog.value = true
  } catch (e) {
    console.error('handleStats error:', e)
  }
}

onMounted(() => {
  fetchSources()
})
</script>

<style scoped>
.knowledge-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-color);
  overflow: hidden;
}

.knowledge-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--header-height);
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-icon {
  font-size: 22px;
  color: var(--primary-color);
}

.header-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.knowledge-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}
</style>
