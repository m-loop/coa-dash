#!/bin/bash
# E2E Tests for COA-dash v0.7.0 Claude Code Feature

set -e

BASE_URL="http://localhost:8890"
PASS=0
FAIL=0

test_api() {
  local name="$1"
  local url="$2"
  local expected="$3"

  response=$(curl -s "$url")
  if echo "$response" | jq -e "$expected" > /dev/null 2>&1; then
    echo "✅ PASS: $name"
    PASS=$((PASS + 1))
  else
    echo "❌ FAIL: $name"
    echo "   Response: $response"
    FAIL=$((FAIL + 1))
  fi
}

test_api_post() {
  local name="$1"
  local url="$2"
  local data="$3"
  local expected="$4"

  response=$(curl -s -X POST "$url" \
    -H "Content-Type: application/json" \
    -d "$data")
  if echo "$response" | jq -e "$expected" > /dev/null 2>&1; then
    echo "✅ PASS: $name"
    PASS=$((PASS + 1))
  else
    echo "❌ FAIL: $name"
    echo "   Response: $response"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== COA-dash v0.7.0 E2E Tests ==="
echo ""

# Test 1: List sessions (should be empty or have sessions)
echo "1. Claude Code API Tests"
test_api "GET /api/claudecode/sessions" "$BASE_URL/api/claudecode/sessions" ".sessions"

# Test 2: List available Claude sessions
test_api "GET /api/claudecode/available" "$BASE_URL/api/claudecode/available?cwd=/home/aegis/vault/projects/coa-dash" ".sessions"

# Test 3: Create a new session
test_api_post "POST /api/claudecode/sessions (create)" "$BASE_URL/api/claudecode/sessions" \
  '{"name": "e2e-test", "cwd": "/home/aegis/vault/projects/coa-dash"}' \
  ".success"

# Get session ID from the create response
SESSION_ID=$(curl -s -X POST "$BASE_URL/api/claudecode/sessions" \
  -H "Content-Type: application/json" \
  -d '{"name": "e2e-test-2", "cwd": "/home/aegis/vault/projects/coa-dash"}' | jq -r '.session.id')

echo "   Created session: $SESSION_ID"

# Test 4: Get single session
test_api "GET /api/claudecode/sessions/:id" "$BASE_URL/api/claudecode/sessions/$SESSION_ID" ".id"

# Test 5: Send message to session
echo ""
echo "2. Conversation Tests"
test_api_post "POST /api/claudecode/sessions/:id/message" "$BASE_URL/api/claudecode/sessions/$SESSION_ID/message" \
  '{"content": "Say hello in one word"}' \
  ".success"

# Wait for response
echo "   Waiting for Claude response..."
sleep 8

# Test 6: Check session status after message
test_api "GET /api/claudecode/sessions/:id (after message)" "$BASE_URL/api/claudecode/sessions/$SESSION_ID" ".messageCount > 0"

# Test 7: Get history
test_api "GET /api/claudecode/sessions/:id/history" "$BASE_URL/api/claudecode/sessions/$SESSION_ID/history" ".messages"

# Test 8: Import existing session
echo ""
echo "3. Import Tests"
AVAILABLE_ID=$(curl -s "$BASE_URL/api/claudecode/available?cwd=/home/aegis/vault/projects/coa-dash" | jq -r '.sessions[0].id // empty')
if [ -n "$AVAILABLE_ID" ]; then
  test_api_post "POST /api/claudecode/import" "$BASE_URL/api/claudecode/import" \
    "{\"claudeSessionId\": \"$AVAILABLE_ID\", \"name\": \"imported-e2e\", \"cwd\": \"/home/aegis/vault/projects/coa-dash\"}" \
    ".success"
else
  echo "⚠️  SKIP: No available sessions to import"
fi

# Test 9: Delete session
echo ""
echo "4. Cleanup Tests"
response=$(curl -s -X DELETE "$BASE_URL/api/claudecode/sessions/$SESSION_ID")
if echo "$response" | jq -e ".success" > /dev/null 2>&1; then
  echo "✅ PASS: DELETE /api/claudecode/sessions/:id"
  PASS=$((PASS + 1))
else
  echo "❌ FAIL: DELETE /api/claudecode/sessions/:id"
  echo "   Response: $response"
  FAIL=$((FAIL + 1))
fi

# Test 10: UI loads
echo ""
echo "5. UI Tests"
HTML=$(curl -s "$BASE_URL/")
if echo "$HTML" | grep -q 'data-tab="claudecode"'; then
  echo "✅ PASS: Claude tab exists in UI"
  PASS=$((PASS + 1))
else
  echo "❌ FAIL: Claude tab missing from UI"
  FAIL=$((FAIL + 1))
fi

if echo "$HTML" | grep -q 'v0.7.0'; then
  echo "✅ PASS: Version 0.7.0 in title"
  PASS=$((PASS + 1))
else
  echo "❌ FAIL: Version mismatch"
  FAIL=$((FAIL + 1))
fi

echo ""
echo "=== Test Results ==="
echo "Passed: $PASS"
echo "Failed: $FAIL"

if [ $FAIL -eq 0 ]; then
  echo "✅ All tests passed!"
  exit 0
else
  echo "❌ Some tests failed"
  exit 1
fi