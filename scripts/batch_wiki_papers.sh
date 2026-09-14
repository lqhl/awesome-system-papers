#!/usr/bin/env bash
# batch_wiki_papers.sh - Generate final Wiki paper pages for all PDFs in conference directories
#
# Usage:
#   ./scripts/batch_wiki_papers.sh [--dry-run] [conf-dir ...]
#   CONCURRENCY=8 ./scripts/batch_wiki_papers.sh osdi-2025
#
# Defaults to osdi-2025 and sosp-2025 if no conference dirs are given.
# Skips PDFs that already have a corresponding Wiki page in wiki/papers/.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONCURRENCY="${CONCURRENCY:-4}"
LOG_FILE="${REPO_ROOT}/wiki/batch_wiki_papers.log"
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

mkdir -p "${REPO_ROOT}/wiki"

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
    local page_name="paper-${basename%.pdf}.md"
    local page_dir="${REPO_ROOT}/wiki/papers"
    local page_path="${page_dir}/${page_name}"

    log() {
        local level="$1" msg="$2"
        local ts
        ts="$(date '+%Y-%m-%d %H:%M:%S')"
        echo "[$ts] [$level] $msg" | tee -a "$LOG_FILE" >&2
    }

    if [[ -f "$page_path" ]]; then
        log "SKIP" "${pdf_rel}"
        return 0
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log "WOULD_RUN" "${pdf_rel} -> wiki/papers/${page_name}"
        return 0
    fi

    mkdir -p "$page_dir"
    log "START" "${pdf_rel}"

    cd "$REPO_ROOT"
    # Use pi's non-interactive mode so this batch job shares the repository's
    # configured provider, model, tools, and skills.
    if pi -p "/wiki-paper ${pdf_rel} --no-update --output wiki/papers/${page_name}" \
        --no-session 2>>"$LOG_FILE"; then
        # Verify the Wiki page was actually written
        if [[ -f "$page_path" && -s "$page_path" ]]; then
            log "DONE" "${pdf_rel} -> wiki/papers/${page_name}"
        else
            log "FAIL" "${pdf_rel} (Wiki page missing or empty after claude run)"
            return 1
        fi
    else
        log "FAIL" "${pdf_rel} (claude exited with error)"
        rm -f "$page_path"
        return 1
    fi
}

export -f process_pdf

# Main
log "INFO" "Starting batch Wiki page generation (concurrency=${CONCURRENCY}, dry_run=${DRY_RUN})"
log "INFO" "Conferences: ${CONFS[*]}"

# Step 0: pre-generate mineru markdowns for every conference.
# Done sequentially per-conference (mineru-api is a singleton per run), once up-front
# so parallel /wiki-paper invocations below don't race to start their own mineru.
if [[ "$DRY_RUN" == "false" ]]; then
    for conf in "${CONFS[@]}"; do
        pdf_dir="${REPO_ROOT}/papers/${conf}"
        [[ -d "$pdf_dir" ]] || continue
        md_dir="${REPO_ROOT}/markdowns/${conf}"
        log "INFO" "Pre-generating mineru markdowns for ${conf} -> markdowns/${conf}/"
        (
            cd "$REPO_ROOT"
            uv run scripts/run_mineru.py "papers/${conf}" "markdowns/${conf}" -j 2 -m txt \
                2>&1 | tee -a "$LOG_FILE"
        ) || log "WARN" "mineru pre-generation for ${conf} exited non-zero; continuing (wiki-paper will fall back to PDF for any missing markdowns)"
    done
fi

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
    if [[ -d "${REPO_ROOT}/wiki/papers" ]]; then
        existing_count=$(find "${REPO_ROOT}/wiki/papers" -maxdepth 1 -name '*.md' | wc -l | tr -d ' ')
    fi
    remaining=$((pdf_count - existing_count))
    total_pdfs=$((total_pdfs + pdf_count))
    total_existing=$((total_existing + existing_count))

    log "INFO" "${conf}: ${pdf_count} PDFs, ${existing_count} Wiki pages exist, ${remaining} to generate"

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
    if [[ -d "${REPO_ROOT}/wiki/papers" ]]; then
        done_count=$(find "${REPO_ROOT}/wiki/papers" -maxdepth 1 -name '*.md' | wc -l | tr -d ' ')
    fi
    log "SUMMARY" "${conf}: ${done_count}/${pdf_count} Wiki pages generated"
done

if [[ "$DRY_RUN" == "false" ]]; then
    log "INFO" "Running Quartz build validation"
    (
        cd "${REPO_ROOT}/quartz"
        npm ci --ignore-scripts
        npx quartz build -d ../wiki
    ) || {
        log "FAIL" "Quartz build validation failed"
        exit 1
    }
    log "INFO" "Quartz build validation passed"
fi

log "INFO" "Log file: ${LOG_FILE}"
