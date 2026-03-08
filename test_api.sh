#!/usr/bin/env bash
# =============================================================
# PDM Assistant API 测试脚本
# 使用前请确保已通过 python run_api.py 启动服务
# 使用方式: bash test_api.sh
# =============================================================

BASE_URL="http://localhost:8001"
BOLD="\033[1m"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[1;33m"
RESET="\033[0m"

separator() {
  echo -e "\n${CYAN}──────────────────────────────────────────────────────${RESET}"
  echo -e "${BOLD}$1${RESET}"
  echo -e "${CYAN}──────────────────────────────────────────────────────${RESET}"
}

# =============================================================
# 【0】健康检查
# =============================================================
separator "【0】根路由 / 健康检查"
echo -e "${YELLOW}GET /${RESET}"
curl -s "$BASE_URL/" | jq .

echo -e "\n${YELLOW}GET /health${RESET}"
curl -s "$BASE_URL/health" | jq .

# =============================================================
# 【1】PDM 查询模块
# =============================================================
separator "【1-1】列出所有表 GET /api/pdm/tables"
curl -s "$BASE_URL/api/pdm/tables" | jq .

# ---- 获取第一张表的 code 用于后续测试 ----
TABLE_CODE=$(curl -s "$BASE_URL/api/pdm/tables" | jq -r '.data[0].code // empty')

if [ -n "$TABLE_CODE" ]; then
  separator "【1-2】获取表结构详情 GET /api/pdm/tables/$TABLE_CODE"
  curl -s "$BASE_URL/api/pdm/tables/$TABLE_CODE" | jq .

  separator "【1-4】查询表关联关系 GET /api/pdm/relationships/$TABLE_CODE"
  curl -s "$BASE_URL/api/pdm/relationships/$TABLE_CODE" | jq .
else
  echo -e "${YELLOW}⚠ 没有找到已索引的表，跳过表详情和关系查询测试${RESET}"
fi

separator "【1-3】语义搜索表 POST /api/pdm/search"
curl -s -X POST "$BASE_URL/api/pdm/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "用户信息", "n_results": 3}' | jq .

separator "【1-5】执行 SQL 查询 POST /api/pdm/sql/execute"
curl -s -X POST "$BASE_URL/api/pdm/sql/execute" \
  -H "Content-Type: application/json" \
  -d '{"db_type": "mysql", "sql": "SELECT 1"}' | jq .

separator "【1-6】查询索引状态 GET /api/pdm/indexer/status"
curl -s "$BASE_URL/api/pdm/indexer/status" | jq .

# =============================================================
# 【2】会话管理模块
# =============================================================
separator "【2-1】列出所有会话 GET /api/conversations"
curl -s "$BASE_URL/api/conversations" | jq .

separator "【2-2】创建新会话 POST /api/conversations"
CREATE_RESP=$(curl -s -X POST "$BASE_URL/api/conversations" \
  -H "Content-Type: application/json" \
  -d '{"name": "测试会话"}')
echo "$CREATE_RESP" | jq .

SESSION_ID=$(echo "$CREATE_RESP" | jq -r '.data.session_id // empty')

if [ -n "$SESSION_ID" ]; then
  separator "【2-3】获取会话详情 GET /api/conversations/$SESSION_ID"
  curl -s "$BASE_URL/api/conversations/$SESSION_ID" | jq .

  separator "【2-4】获取会话历史 GET /api/conversations/$SESSION_ID/history"
  curl -s "$BASE_URL/api/conversations/$SESSION_ID/history" | jq .

  separator "【2-5】发送消息（AI 对话）POST /api/conversations/$SESSION_ID/messages"
  echo -e "${YELLOW}⚠ 此接口会调用 LLM，可能需要等待数秒...${RESET}"
  curl -s -X POST "$BASE_URL/api/conversations/$SESSION_ID/messages" \
    -H "Content-Type: application/json" \
    -d '{"message": "请列出所有已索引的表"}' | jq .

  separator "【2-6】清空会话历史 DELETE /api/conversations/$SESSION_ID/history"
  curl -s -X DELETE "$BASE_URL/api/conversations/$SESSION_ID/history" | jq .

  separator "【2-7】删除会话 DELETE /api/conversations/$SESSION_ID"
  curl -s -X DELETE "$BASE_URL/api/conversations/$SESSION_ID" | jq .
else
  echo -e "${YELLOW}⚠ 创建会话失败，跳过后续会话测试${RESET}"
fi

# =============================================================
# 完成
# =============================================================
separator "✅ 测试完成"
echo -e "Swagger UI 文档: ${BOLD}${BASE_URL}/docs${RESET}"
echo -e "ReDoc    文档:   ${BOLD}${BASE_URL}/redoc${RESET}"
