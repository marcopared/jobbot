import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

JOBBOT_ROOT = Path(__file__).resolve().parents[1]
if str(JOBBOT_ROOT) not in sys.path:
    sys.path.insert(0, str(JOBBOT_ROOT))

from apps.api.settings import Settings


def _required_path(raw_value: str, env_name: str) -> Path:
    value = (raw_value or "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {env_name}")
    return Path(value).resolve()

def main():
    settings = Settings()
    ext_path = _required_path(settings.simplify_extension_path, "SIMPLIFY_EXTENSION_PATH")
    profile_dir = _required_path(settings.simplify_profile_dir, "SIMPLIFY_PROFILE_DIR")
    if not ext_path.exists():
        raise RuntimeError(
            f"SIMPLIFY_EXTENSION_PATH does not exist: {ext_path}. "
            "Set it to the unpacked extension directory."
        )
    if not ext_path.is_dir():
        raise RuntimeError(
            f"SIMPLIFY_EXTENSION_PATH is not a directory: {ext_path}. "
            "Set it to the unpacked extension directory."
        )
    manifest_path = ext_path / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(
            f"SIMPLIFY_EXTENSION_PATH does not look like an unpacked extension (missing manifest.json): {ext_path}"
        )

    print("Using Simplify extension path:", ext_path)
    print("Using Simplify profile dir:", profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chromium",
            headless=False,
            args=[
                f"--disable-extensions-except={ext_path}",
                f"--load-extension={ext_path}",
            ],
        )

        page = context.new_page()
        page.goto("https://simplify.jobs/dashboard")

        sw = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
        extension_id = sw.url.split("/")[2]

        print("Extension loaded.")
        print("Extension ID:", extension_id)
        print(f"Popup URL: chrome-extension://{extension_id}/popup.html")
        input("Log into Simplify in the browser, then press Enter here to save the session... ")

        context.close()

if __name__ == "__main__":
    main()
