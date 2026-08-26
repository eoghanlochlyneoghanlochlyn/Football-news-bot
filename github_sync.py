import os
import subprocess


# ============================================================
# تنظیمات
# ============================================================

SEEN_FILE = os.getenv(
    "SEEN_FILE",
    "seen_news.json"
).strip()

# اگر false باشد، فقط وضعیت را بررسی می‌کند
# و چیزی به GitHub ارسال نمی‌کند.
ENABLE_GITHUB_SYNC = os.getenv(
    "ENABLE_GITHUB_SYNC",
    "true"
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on"
}


# ============================================================
# اجرای دستور Git
# ============================================================

def run_git_command(
    command,
    check=True
):

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=check
        )

        return {
            "success": True,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
            "error": ""
        }

    except subprocess.CalledProcessError as error:

        return {
            "success": False,
            "stdout": (
                error.stdout or ""
            ).strip(),
            "stderr": (
                error.stderr or ""
            ).strip(),
            "returncode": error.returncode,
            "error": str(error)
        }

    except Exception as error:

        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "returncode": -1,
            "error": str(error)
        }


# ============================================================
# بررسی وجود Git
# ============================================================

def check_git():

    result = run_git_command(
        [
            "git",
            "--version"
        ],
        check=False
    )

    if result["success"]:

        print(
            f"✓ Git در دسترس است: "
            f"{result['stdout']}"
        )

        return True

    print(
        "❌ Git در محیط اجرا در دسترس نیست."
    )

    return False


# ============================================================
# بررسی وضعیت فایل
# ============================================================

def get_file_status():

    result = run_git_command(
        [
            "git",
            "status",
            "--porcelain",
            "--",
            SEEN_FILE
        ],
        check=False
    )

    if not result["success"]:

        print(
            "❌ دریافت وضعیت Git ناموفق بود."
        )

        if result["stderr"]:

            print(
                result["stderr"]
            )

        return None

    return result["stdout"]


# ============================================================
# بررسی اینکه فایل تغییر کرده یا نه
# ============================================================

def has_changes():

    status = get_file_status()

    if status is None:

        return False

    if not status.strip():

        print(
            f"تغییری در {SEEN_FILE} وجود ندارد."
        )

        return False

    print(
        f"✓ تغییر در {SEEN_FILE} شناسایی شد."
    )

    return True


# ============================================================
# تنظیم هویت Git
# ============================================================

def configure_git_identity():

    username_result = run_git_command(
        [
            "git",
            "config",
            "user.name",
            "github-actions[bot]"
        ]
    )

    if not username_result["success"]:

        print(
            "❌ تنظیم نام Git ناموفق بود."
        )

        return False

    email_result = run_git_command(
        [
            "git",
            "config",
            "user.email",
            "41898282+github-actions[bot]"
            "@users.noreply.github.com"
        ]
    )

    if not email_result["success"]:

        print(
            "❌ تنظیم ایمیل Git ناموفق بود."
        )

        return False

    print(
        "✓ هویت Git تنظیم شد."
    )

    return True


# ============================================================
# افزودن فایل
# ============================================================

def stage_seen_file():

    result = run_git_command(
        [
            "git",
            "add",
            "--",
            SEEN_FILE
        ]
    )

    if not result["success"]:

        print(
            f"❌ افزودن {SEEN_FILE} به Git ناموفق بود."
        )

        if result["stderr"]:

            print(
                result["stderr"]
            )

        return False

    print(
        f"✓ {SEEN_FILE} برای ثبت آماده شد."
    )

    return True


# ============================================================
# بررسی وجود تغییر staged
# ============================================================

def has_staged_changes():

    result = run_git_command(
        [
            "git",
            "diff",
            "--cached",
            "--quiet",
            "--",
            SEEN_FILE
        ],
        check=False
    )

    # کد 0 یعنی تغییری وجود ندارد
    if result["returncode"] == 0:

        return False

    # کد 1 یعنی تغییر وجود دارد
    if result["returncode"] == 1:

        return True

    print(
        "❌ بررسی تغییرات staged ناموفق بود."
    )

    if result["stderr"]:

        print(
            result["stderr"]
        )

    return False


# ============================================================
# ثبت Commit
# ============================================================

def create_commit():

    result = run_git_command(
        [
            "git",
            "commit",
            "-m",
            "Update seen news"
        ]
    )

    if not result["success"]:

        print(
            "❌ ساخت Commit ناموفق بود."
        )

        if result["stdout"]:

            print(
                result["stdout"]
            )

        if result["stderr"]:

            print(
                result["stderr"]
            )

        return False

    print(
        "✓ Commit با موفقیت ساخته شد."
    )

    if result["stdout"]:

        print(
            result["stdout"]
        )

    return True


# ============================================================
# Push
# ============================================================

def push_to_github():

    print(
        "در حال ارسال تغییرات به GitHub..."
    )

    result = run_git_command(
        [
            "git",
            "push"
        ]
    )

    if not result["success"]:

        print(
            "❌ Push به GitHub ناموفق بود."
        )

        if result["stdout"]:

            print(
                result["stdout"]
            )

        if result["stderr"]:

            print(
                result["stderr"]
            )

        return False

    print(
        "✓ تغییرات با موفقیت به GitHub ارسال شد."
    )

    if result["stdout"]:

        print(
            result["stdout"]
        )

    return True


# ============================================================
# همگام‌سازی seen_news با GitHub
# ============================================================

def sync_seen_file():

    print(
        "\n"
        + "=" * 60
    )

    print(
        "شروع همگام‌سازی با GitHub"
    )

    print(
        "=" * 60
    )

    # --------------------------------------------------------
    # بررسی فعال بودن
    # --------------------------------------------------------

    if not ENABLE_GITHUB_SYNC:

        print(
            "⚠️ همگام‌سازی GitHub غیرفعال است."
        )

        return {
            "success": True,
            "changed": False,
            "skipped": True,
            "error": ""
        }

    # --------------------------------------------------------
    # بررسی Git
    # --------------------------------------------------------

    if not check_git():

        return {
            "success": False,
            "changed": False,
            "skipped": False,
            "error": "Git در دسترس نیست."
        }

    # --------------------------------------------------------
    # بررسی تغییر
    # --------------------------------------------------------

    if not has_changes():

        return {
            "success": True,
            "changed": False,
            "skipped": False,
            "error": ""
        }

    # --------------------------------------------------------
    # تنظیم هویت
    # --------------------------------------------------------

    if not configure_git_identity():

        return {
            "success": False,
            "changed": True,
            "skipped": False,
            "error": "تنظیم هویت Git ناموفق بود."
        }

    # --------------------------------------------------------
    # Stage
    # --------------------------------------------------------

    if not stage_seen_file():

        return {
            "success": False,
            "changed": True,
            "skipped": False,
            "error": (
                f"افزودن {SEEN_FILE} ناموفق بود."
            )
        }

    # --------------------------------------------------------
    # بررسی staged
    # --------------------------------------------------------

    if not has_staged_changes():

        print(
            "⚠️ پس از stage کردن، "
            "تغییر قابل ثبت پیدا نشد."
        )

        return {
            "success": True,
            "changed": False,
            "skipped": False,
            "error": ""
        }

    # --------------------------------------------------------
    # Commit
    # --------------------------------------------------------

    if not create_commit():

        return {
            "success": False,
            "changed": True,
            "skipped": False,
            "error": "ساخت Commit ناموفق بود."
        }

    # --------------------------------------------------------
    # Push
    # --------------------------------------------------------

    if not push_to_github():

        return {
            "success": False,
            "changed": True,
            "skipped": False,
            "error": "Push به GitHub ناموفق بود."
        }

    print(
        "=" * 60
    )

    print(
        "✓ همگام‌سازی GitHub با موفقیت انجام شد."
    )

    print(
        "=" * 60
    )

    return {
        "success": True,
        "changed": True,
        "skipped": False,
        "error": ""
    }


# ============================================================
# تابع جایگزین برای استفاده در main.py
# ============================================================

def commit_seen_file():

    result = sync_seen_file()

    return result["success"]


# ============================================================
# تست مستقیم
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("تست github_sync.py")
    print("=" * 60)

    result = sync_seen_file()

    print(
        "\nنتیجه:"
    )

    print(
        f"موفق: {result['success']}"
    )

    print(
        f"تغییر داشت: {result['changed']}"
    )

    print(
        f"رد شد: {result['skipped']}"
    )

    if result["error"]:

        print(
            f"خطا: {result['error']}"
        )

    print("=" * 60)
