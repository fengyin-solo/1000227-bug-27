<template>
  <section class="page" data-module="location">
    <header class="page-head">
      <div>
        <h2>场地租用管理</h2>
        <p class="page-desc">维护拍摄场地，围绕场地编号、场地名称、场地类型、所属区域做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记拍摄场地</button>
        <button class="btn" type="button" @click="exportRows">导出场地租用清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="search">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <label class="filter-item">
        <span>租用状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">当前筛选条件下暂无场地租用数据</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条场地租用记录</span>
      <span class="pager">
        <button class="btn" type="button" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
        <span>第 {{ page }} / {{ totalPages }} 页</span>
        <button class="btn" type="button" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</button>
      </span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/location'
const columns = ["场地编号", "场地名称", "场地类型", "所属区域", "可租时段", "场地费用", "对接联系人", "租用状态"]
const actions = ["签约场地", "确认进场", "办理退场"]
const statuses = ["待洽谈", "已签约", "使用中", "已退场"]
const stats = [{"label": "已签约场地", "value": 0}, {"label": "使用中场地", "value": 0}, {"label": "待洽谈场地", "value": 0}]
const PAGE_SIZE = 20

const rows = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const errorMessage = ref('')
// key 与后端查询参数名完全一致，保证筛选口径统一
const filters = ref<Record<string, string>>({ 场地编号: '', 场地名称: '', 场地类型: '', 所属区域: '' })
const filterFields = ["场地编号", "场地名称", "场地类型", "所属区域"]
const statusFilter = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function buildQuery(withPage = true): string {
  const params = new URLSearchParams()
  for (const field of filterFields) {
    const value = filters.value[field]?.trim() ?? ''
    if (value) {
      params.set(field, value)
    }
  }
  if (statusFilter.value) {
    params.set('status', statusFilter.value)
  }
  if (withPage) {
    params.set('page', String(page.value))
    params.set('size', String(PAGE_SIZE))
  }
  const query = params.toString()
  return query ? `?${query}` : ''
}

function search() {
  page.value = 1
  void reload()
}

function changePage(target: number) {
  if (target < 1 || target > totalPages.value || target === page.value) {
    return
  }
  page.value = target
  void reload()
}

function resetFilters() {
  for (const field of filterFields) {
    filters.value[field] = ''
  }
  statusFilter.value = ''
  page.value = 1
  void reload()
}

function exportRows() {
  // 导出沿用当前筛选范围（不带分页），内容与列表命中记录一致
  window.open(`${ENDPOINT}/export${buildQuery(false)}`, '_blank')
}

function openCreate() {
  errorMessage.value = '拍摄场地登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('场地租用动作未生效，请稍后重试')
    }
    // 沿用当前筛选与页码再查一次，处理后页面恢复为上次结果
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '场地租用操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}${buildQuery()}`)
    if (!response.ok) {
      throw new Error('拍摄场地列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    // 筛选后若当前页超出范围（如末页记录被处理），退回最后一页
    if (page.value > totalPages.value) {
      page.value = totalPages.value
      await reload()
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '场地租用列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.pager { display: inline-flex; align-items: center; gap: 8px; }
.pager .btn:disabled { opacity: 0.5; cursor: not-allowed; }
.filter-item select { padding: 4px 6px; }
</style>
