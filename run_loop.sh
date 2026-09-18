#!/data/data/com.termux/files/usr/bin/bash
# Termux용 무한 루프: 5분마다 baseline(자동으로 burst 전환 포함), 하루 1회는 full_scan.
# systemd/cron/launchd 없이 그냥 계속 sleep-loop로 돈다.

cd "$(dirname "$0")" || exit 1

mkdir -p logs

LOG_FILE="logs/run_loop.log"
LAST_FULL_SCAN_FILE="logs/.last_full_scan_date"
INTERVAL_SEC=300

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S %z')] $*" >> "$LOG_FILE"
}

termux-wake-lock 2>>"$LOG_FILE"
log "run_loop.sh 시작 (PID=$$)"

while true; do
    TODAY=$(date +%Y-%m-%d)
    LAST_FULL_SCAN=""
    [ -f "$LAST_FULL_SCAN_FILE" ] && LAST_FULL_SCAN=$(cat "$LAST_FULL_SCAN_FILE")

    if [ "$TODAY" != "$LAST_FULL_SCAN" ]; then
        log "cycle 시작 mode=full_scan"
        MODE=full_scan python3 -m src.main >> "$LOG_FILE" 2>&1
        RC=$?
        if [ "$RC" -eq 0 ]; then
            echo "$TODAY" > "$LAST_FULL_SCAN_FILE"
        fi
        log "cycle 종료 mode=full_scan rc=$RC"
    else
        log "cycle 시작 mode=auto(baseline/burst)"
        python3 -m src.main >> "$LOG_FILE" 2>&1
        RC=$?
        log "cycle 종료 mode=auto rc=$RC"
    fi

    # RC가 0이 아니어도(네트워크 오류, 일시적 실패 등) 루프는 절대 멈추지 않는다.
    sleep "$INTERVAL_SEC"
done
