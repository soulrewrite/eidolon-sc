#!/bin/sh
# 每天凌晨把 eidolon 的 SQLite 在线备份到家目录下的 eidolon-backup，保留 14 天。
# 用容器里的 sqlite3 backup API（不是 cp）：WAL 模式下直接拷文件会拿到不一致的快照。
# 由部署用户的 cron 调用：0 4 * * * $HOME/eidolon-db-backup.sh
set -u

DIR="$HOME/eidolon-backup"
KEEP_DAYS=14
CONTAINER=eidolon-sc-backend-1
LOG=$DIR/backup.log
stamp=$(date +%Y%m%d-%H%M)
tmp=/tmp/eidolon-backup-$stamp.db
out=$DIR/eidolon-$stamp.db.gz

mkdir -p "$DIR"
say() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
    say "$CONTAINER 没在跑，这次不备份"
    exit 5
fi

# 1) 容器内在线备份 + 完整性检查
if ! docker exec "$CONTAINER" python -c "
import sqlite3, sys
src = sqlite3.connect('/data/eidolon.db')
dst = sqlite3.connect('/data/backup-tmp.db')
src.backup(dst)
ok = dst.execute('PRAGMA integrity_check').fetchone()[0]
dst.close(); src.close()
sys.exit(0 if ok == 'ok' else 1)
" 2>>"$LOG"; then
    say "导出或完整性检查失败，这次不备份"
    docker exec "$CONTAINER" rm -f /data/backup-tmp.db 2>/dev/null
    rm -f "$tmp"
    exit 2
fi

# 2) 取回宿主机
if ! docker cp "$CONTAINER:/data/backup-tmp.db" "$tmp" 2>>"$LOG"; then
    say "docker cp 失败，这次不备份"
    docker exec "$CONTAINER" rm -f /data/backup-tmp.db 2>/dev/null
    rm -f "$tmp"
    exit 2
fi
docker exec "$CONTAINER" rm -f /data/backup-tmp.db 2>/dev/null

# 3) 压缩、落盘
gzip -9 -f "$tmp" || { say "gzip 失败"; exit 2; }
mv "$tmp.gz" "$out" || { say "落盘失败"; exit 2; }
size=$(du -h "$out" | cut -f1)
say "备份完成 $out（$size）"

# 4) 清掉过期的，最新的一份不删
find "$DIR" -name 'eidolon-*.db.gz' -type f -mtime +"$KEEP_DAYS" ! -name "eidolon-$stamp.db.gz" -delete
kept=$(find "$DIR" -name 'eidolon-*.db.gz' -type f | wc -l)
say "目录里现有 $kept 份备份，保留 ${KEEP_DAYS} 天"
exit 0
