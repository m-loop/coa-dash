#!/bin/bash
# Check for pending dashboard messages
DIR="/tmp"
PATTERN="claude-pending-*.jsonl"
MSG=""
NOW=$(date +%s)

for f in $DIR/$PATTERN; do
    [ -f "$f" ] || continue
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        SENT=$(echo "$line" | python3 -c "import sys,json; print(int(json.loads(sys.stdin.read())['sent_at']))" 2>/dev/null)
        [ -z "$SENT" ] && continue
        AGE=$(( NOW - SENT ))
        # Only show messages less than 4 hours old
        if [ $AGE -lt 14400 ]; then
            CONTENT=$(echo "$line" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['content'])" 2>/dev/null)
            if [ -n "$CONTENT" ]; then
                MSG="${MSG}[Dashboard message ${AGE}s ago]: ${CONTENT}\n"
            fi
        fi
    done < "$f"
done

if [ -n "$MSG" ]; then
    echo "NOTICE: You have pending messages from the dashboard:"
    echo -e "$MSG"
    echo "After reading and responding, clear with: rm /tmp/claude-pending-*.jsonl"
fi
