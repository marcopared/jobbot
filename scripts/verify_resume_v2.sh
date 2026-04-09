#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="${1:-storage/verification/resume_v2_demo}"

COMMANDS=$(cat <<EOF
bash scripts/verify_resume_v2.sh ${OUTPUT_DIR}
PYTHONPATH=. python3 -m core.resumes.verification_harness --output-dir ${OUTPUT_DIR}
EOF
)

JOBBOT_VERIFY_RESUME_V2_COMMANDS="${COMMANDS}" \
PYTHONPATH=. python3 -m core.resumes.verification_harness --output-dir "${OUTPUT_DIR}"
