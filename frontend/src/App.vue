<script setup>
import { computed, onMounted, ref } from 'vue'

const now = new Date()
const month = ref(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)
const data = ref({ runs: [], orders: [] })
const error = ref('')
const loading = ref(false)
const dryRun = computed(() => data.value.orders.some(order => order.message?.startsWith('DRY_RUN')))

async function request(path, options) {
  const response = await fetch(path, options)
  if (!response.ok) throw new Error((await response.json()).detail || '요청에 실패했습니다.')
  return response.json()
}
async function refresh() {
  try { data.value = await request('/api/dashboard') } catch (e) { error.value = e.message }
}
async function plan() {
  loading.value = true; error.value = ''
  try { await request(`/api/runs/${month.value}/plan`, { method: 'POST' }); await refresh() } catch (e) { error.value = e.message } finally { loading.value = false }
}
async function execute(market) {
  loading.value = true; error.value = ''
  try { await request(`/api/runs/${month.value}/execute?market=${market}`, { method: 'POST' }); await refresh() } catch (e) { error.value = e.message } finally { loading.value = false }
}
onMounted(refresh)
</script>

<template>
  <main>
    <header><div><p class="eyebrow">TOSS AUTO INVEST</p><h1>월간 투자 실행판</h1></div><button @click="refresh">새로고침</button></header>
    <p class="notice">{{ dryRun ? '현재는 DRY RUN입니다. 실제 주문은 보내지지 않습니다.' : '주문 상태를 확인하세요.' }}</p>
    <p v-if="error" class="error">{{ error }}</p>
    <section class="toolbar"><label>투자 월 <input v-model="month" type="month"></label><button :disabled="loading" @click="plan">잔고로 계획 만들기</button><button :disabled="loading" @click="execute('KR')">국내 주문 실행</button><button :disabled="loading" @click="execute('US')">미국 주문 실행</button></section>
    <section class="cards"><article v-for="run in data.runs" :key="run.id"><b>{{ run.month }}</b><span>KRW {{ Number(run.krw_budget).toLocaleString() }}</span><span>USD {{ Number(run.usd_budget).toLocaleString() }}</span></article></section>
    <section><h2>주문 기록</h2><table><thead><tr><th>종목</th><th>시장</th><th>배정 금액</th><th>수량</th><th>상태</th><th>메시지</th></tr></thead><tbody><tr v-for="order in data.orders" :key="order.id"><td>{{ order.symbol }}</td><td>{{ order.market }}</td><td>{{ Number(order.target_amount).toLocaleString() }}</td><td>{{ order.quantity || '-' }}</td><td><mark :class="order.status.toLowerCase()">{{ order.status }}</mark></td><td>{{ order.message || order.toss_order_id || '-' }}</td></tr></tbody></table></section>
  </main>
</template>
