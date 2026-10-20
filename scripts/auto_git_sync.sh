#!/bin/bash
set -eu

REPO="/opt/crypto-bot"
BRANCH="main"

# جلوگیری از اجرای هم‌زمان
exec 9>/run/lock/crypto-bot-git-sync.lock
flock -n 9 || exit 0

cd "$REPO"

# فقط فایل‌های پروژه؛ فایل‌های حساس با gitignore حذف می‌شوند
git add -A -- .gitignore .env.example app scripts

# اگر تغییری وجود دارد، ثبت کن
if ! git diff --cached --quiet; then
    git diff --cached --check
    git commit -m "Auto-sync: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
fi

# ارسال به GitHub
git push origin "$BRANCH"
