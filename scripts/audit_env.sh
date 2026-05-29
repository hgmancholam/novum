#!/usr/bin/env bash
set -u
cd /home/novum/novum-backend/backend

ENV=.env
BAK=.env.bak.20260528-232407
EX=.env.example

echo "=== KEY DIFF: .env vs $BAK ==="
diff <(grep -oE '^[A-Z_][A-Z0-9_]*' "$ENV" | sort -u) \
     <(grep -oE '^[A-Z_][A-Z0-9_]*' "$BAK" | sort -u) \
     && echo "(keys identical)"

echo
echo "=== KEY DIFF: .env vs $EX ==="
diff <(grep -oE '^[A-Z_][A-Z0-9_]*' "$ENV" | sort -u) \
     <(grep -oE '^[A-Z_][A-Z0-9_]*' "$EX"  | sort -u) \
     && echo "(keys identical)"

echo
echo "=== DUPLICATE keys in .env ==="
dup=$(grep -oE '^[A-Z_][A-Z0-9_]*' "$ENV" | sort | uniq -d)
[ -z "$dup" ] && echo "(none)" || echo "$dup"

echo
echo "=== CHANGED values vs $BAK ==="
changed=0
while IFS= read -r k; do
  a=$(grep "^${k}=" "$ENV" | head -1)
  b=$(grep "^${k}=" "$BAK" | head -1)
  if [ "$a" != "$b" ]; then
    echo "CHANGED: $k"
    changed=1
  fi
done < <(grep -oE '^[A-Z_][A-Z0-9_]*' "$ENV" | sort -u)
[ $changed -eq 0 ] && echo "(none)"

echo
echo "=== EMPTY / suspect short values ==="
awk -F= '/^[A-Z_]/{
  v=substr($0, length($1)+2);
  if (length(v)==0) printf "EMPTY  %s\n", $1;
  else if (length(v)<8 && $1 !~ /ENV|LOG|PORT|WORKERS|DEBUG|MODE/) printf "SHORT  %s (len=%d)\n", $1, length(v);
}' "$ENV"

echo
echo "=== ALL keys with value length ==="
awk -F= '/^[A-Z_]/{
  v=substr($0, length($1)+2);
  printf "  %-32s len=%d\n", $1, length(v);
}' "$ENV"
