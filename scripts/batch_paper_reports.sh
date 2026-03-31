#!/usr/bin/env bash
# batch_paper_reports.sh - Generate paper reports for all PDFs in conference directories
#
# Usage:
#   ./scripts/batch_paper_reports.sh [--dry-run] [conf-dir ...]
#   CONCURRENCY=8 ./scripts/batch_paper_reports.sh osdi-2025
#
# Defaults to osdi-2025 and sosp-2025 if no conference dirs are given.
# Skips PDFs that already have a corresponding report in reports/{conf}/.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONCURRENCY="${CONCURRENCY:-4}"
LOG_FILE="${REPO_ROOT}/reports/batch_report.log"
DRY_RUN=false

# Parse flags
args=()
for arg in "$@"; do
    if [[ "$arg" == "--dry-run" ]]; then
        DRY_RUN=true
    else
        args+=("$arg")
    fi
done

if [[ ${#args[@]} -gt 0 ]]; then
    CONFS=("${args[@]}")
else
    CONFS=("osdi-2025" "sosp-2025")
fi

mkdir -p "${REPO_ROOT}/reports"

log() {
    local level="$1" msg="$2"
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$ts] [$level] $msg" | tee -a "$LOG_FILE" >&2
}

process_pdf() {
    local pdf_rel="$1"   # relative path from repo root, e.g. papers/sosp-2025/foo.pdf
    local conf="$2"
    local REPO_ROOT="$3"
    local LOG_FILE="$4"
    local DRY_RUN="$5"

    local basename="${pdf_rel##*/}"
    local report_name="${basename%.pdf}.md"
    local report_dir="${REPO_ROOT}/reports/${conf}"
    local report_path="${report_dir}/${report_name}"

    log() {
        local level="$1" msg="$2"
        local ts
        ts="$(date '+%Y-%m-%d %H:%M:%S')"
        echo "[$ts] [$level] $msg" | tee -a "$LOG_FILE" >&2
    }

    if [[ -f "$report_path" ]]; then
        log "SKIP" "${pdf_rel}"
        return 0
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log "WOULD_RUN" "${pdf_rel} -> reports/${conf}/${report_name}"
        return 0
    fi

    mkdir -p "$report_dir"
    log "START" "${pdf_rel}"

    cd "$REPO_ROOT"
    if claude -p "/paper-report ${pdf_rel}" --dangerously-skip-permissions 2>>"$LOG_FILE"; then
        # Verify the report was actually written
        if [[ -f "$report_path" && -s "$report_path" ]]; then
            log "DONE" "${pdf_rel} -> reports/${conf}/${report_name}"
        else
            log "FAIL" "${pdf_rel} (report file missing or empty after claude run)"
            return 1
        fi
    else
        log "FAIL" "${pdf_rel} (claude exited with error)"
        rm -f "$report_path"
        return 1
    fi
}

export -f process_pdf

# Main
log "INFO" "Starting batch report generation (concurrency=${CONCURRENCY}, dry_run=${DRY_RUN})"
log "INFO" "Conferences: ${CONFS[*]}"

total_pdfs=0
total_existing=0

for conf in "${CONFS[@]}"; do
    pdf_dir="${REPO_ROOT}/papers/${conf}"
    if [[ ! -d "$pdf_dir" ]]; then
        log "WARN" "Directory not found, skipping: ${pdf_dir}"
        continue
    fi

    pdf_count=$(find "$pdf_dir" -maxdepth 1 -name '*.pdf' | wc -l | tr -d ' ')
    existing_count=0
    if [[ -d "${REPO_ROOT}/reports/${conf}" ]]; then
        existing_count=$(find "${REPO_ROOT}/reports/${conf}" -maxdepth 1 -name '*.md' | wc -l | tr -d ' ')
    fi
    remaining=$((pdf_count - existing_count))
    total_pdfs=$((total_pdfs + pdf_count))
    total_existing=$((total_existing + existing_count))

    log "INFO" "${conf}: ${pdf_count} PDFs, ${existing_count} reports exist, ${remaining} to generate"

    find "$pdf_dir" -maxdepth 1 -name '*.pdf' -print0 | \
        sort -z | \
        xargs -0 -P "$CONCURRENCY" -I{} \
        bash -c 'process_pdf "papers/'"$conf"'/$(basename "$1")" "'"$conf"'" "'"$REPO_ROOT"'" "'"$LOG_FILE"'" "'"$DRY_RUN"'"' _ {}
done

# Summary
log "INFO" "=== Summary ==="
for conf in "${CONFS[@]}"; do
    pdf_dir="${REPO_ROOT}/papers/${conf}"
    [[ -d "$pdf_dir" ]] || continue
    pdf_count=$(find "$pdf_dir" -maxdepth 1 -name '*.pdf' | wc -l | tr -d ' ')
    done_count=0
    if [[ -d "${REPO_ROOT}/reports/${conf}" ]]; then
        done_count=$(find "${REPO_ROOT}/reports/${conf}" -maxdepth 1 -name '*.md' | wc -l | tr -d ' ')
    fi
    log "SUMMARY" "${conf}: ${done_count}/${pdf_count} reports generated"
done

log "INFO" "Log file: ${LOG_FILE}"
