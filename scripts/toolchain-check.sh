#!/bin/bash
# Says whether Node 24 or later and a JDK of 21 or later are on the PATH that make uses.
# Exit 0 both present, 1 otherwise. Prints one line per tool.
missing=0
node_major=$(node -e 'console.log(process.versions.node.split(".")[0])' 2>/dev/null || echo 0)
if [ "${node_major:-0}" -ge 24 ]; then echo "ok:      Node $node_major"
else echo "WARNING: Node 24 or later is needed for the frontend (found: ${node_major:-none})"; missing=1; fi

java_major=$(java -version 2>&1 | sed -n 's/.* version "\([0-9]*\).*/\1/p' | head -1)
if [ "${java_major:-0}" -ge 21 ]; then echo "ok:      JDK $java_major"
else echo "WARNING: a JDK of 21 or later is needed for the Firestore emulator (found: ${java_major:-none})"; missing=1; fi
exit "$missing"
