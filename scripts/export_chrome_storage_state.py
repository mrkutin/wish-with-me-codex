import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    chrome_root = Path("~/Library/Application Support/Google/Chrome").expanduser()
    profile_dir = os.environ.get("CHROME_PROFILE", "Default")
    target_url = os.environ.get("TARGET_URL", "https://www.ozon.ru/")
    out_path = Path("services/item-resolver/storage_state/ozon.ru.json").resolve()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(chrome_root),
            channel="chrome",
            headless=False,
            args=[
                f"--profile-directory={profile_dir}",
                "--disable-crashpad",
                "--disable-crash-reporter",
            ],
        )
        page = ctx.new_page()
        page.goto(target_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        ctx.storage_state(path=str(out_path))
        ctx.close()

    print(out_path)


if __name__ == "__main__":
    main()
