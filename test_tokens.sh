#!/bin/bash
# Test each GH PAT against GitHub Models inference endpoint.
TOKENS=(
  ""
  ""
  ""
  ""
)
PAYLOAD='{"model":"meta/Llama-4-Scout-17B-16E-Instruct","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
for i in "${!TOKENS[@]}"; do
  tok="${TOKENS[$i]}"
  code=$(curl -s -o /tmp/resp_$i.json -w "%{http_code}" -X POST \
    https://models.github.ai/inference/chat/completions \
    -H "Authorization: Bearer $tok" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")
  echo "T$((i+1)) (${tok:0:15}...) => HTTP $code"
  if [ "$code" != "200" ]; then
    head -c 200 /tmp/resp_$i.json; echo
  fi
  sleep 2
done
