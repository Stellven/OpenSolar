#!/bin/bash
#
# Pre-commit hook for Cortex Files
# Validates YAML frontmatter in all .md files
#
# Reference: Letta Context Repositories pattern
#

set -e

CORTEX_ROOT="${HOME}/.solar/cortex"
FRONTMATTER_REGEX='^---$'
REQUIRED_FIELDS=("description" "limit")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

errors=0
warnings=0

log_error() {
    echo -e "${RED}ERROR: $1${NC}"
    ((errors++))
}

log_warning() {
    echo -e "${YELLOW}WARNING: $1${NC}"
    ((warnings++))
}

log_ok() {
    echo -e "${GREEN}OK: $1${NC}"
}

# Get list of staged .md files
staged_files=$(git diff --cached --name-only --diff-filter=ACMR | grep '\.md$' || true)

if [ -z "$staged_files" ]; then
    echo "No .md files to check."
    exit 0
fi

echo "Checking frontmatter in staged .md files..."
echo ""

for file in $staged_files; do
    if [ ! -f "$file" ]; then
        continue
    fi

    echo "Checking: $file"

    # Read file content
    content=$(cat "$file")

    # Check for frontmatter
    if ! echo "$content" | head -1 | grep -q "^---$"; then
        log_error "$file: Missing frontmatter opening '---'"
        continue
    fi

    # Extract frontmatter (between first two --- lines)
    frontmatter=$(echo "$content" | sed -n '2,/^---$/p')

    if [ -z "$frontmatter" ]; then
        log_error "$file: Empty or missing frontmatter"
        continue
    fi

    # Check required fields
    file_ok=true

    # Check description field
    description=$(echo "$frontmatter" | grep "^description:" | sed 's/^description: *//' | tr -d '"')
    if [ -z "$description" ] || [ "$description" = "null" ]; then
        log_error "$file: Missing or empty 'description' field"
        file_ok=false
    fi

    # Check limit field
    limit=$(echo "$frontmatter" | grep "^limit:" | sed 's/^limit: *//')
    if [ -z "$limit" ]; then
        log_warning "$file: Missing 'limit' field (using default 2000)"
    elif ! [[ "$limit" =~ ^[0-9]+$ ]]; then
        log_error "$file: 'limit' must be a positive integer, got: $limit"
        file_ok=false
    elif [ "$limit" -le 0 ]; then
        log_error "$file: 'limit' must be positive, got: $limit"
        file_ok=false
    fi

    # Check read_only protection
    read_only=$(echo "$frontmatter" | grep "^read_only:" | sed 's/^read_only: *//')
    if [ "$read_only" = "true" ]; then
        # Check if this is a modification (not new file)
        if git diff --cached --name-status | grep -q "^M.*$file"; then
            log_warning "$file: Modifying a read_only file"
        fi
    fi

    if [ "$file_ok" = true ]; then
        log_ok "$file"
    fi
done

echo ""
echo "==========================================="
echo "Summary: $errors errors, $warnings warnings"

if [ $errors -gt 0 ]; then
    echo ""
    echo "Commit blocked due to frontmatter validation errors."
    echo "Please fix the issues above and try again."
    exit 1
fi

exit 0
