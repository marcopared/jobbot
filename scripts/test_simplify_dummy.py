from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
JOBBOT_ROOT = REPO_ROOT / "jobbot"
if str(JOBBOT_ROOT) not in sys.path:
    sys.path.insert(0, str(JOBBOT_ROOT))

from apps.api.settings import Settings


def _required_path(raw_value: str, env_name: str) -> Path:
    value = (raw_value or "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {env_name}")
    return Path(value).expanduser().resolve()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch Playwright with Simplify extension against a dummy apply form."
    )
    parser.add_argument(
        "--url",
        default="",
        help="Optional URL to open instead of the local file:// dummy form.",
    )
    return parser.parse_args()


def _collect_fill_summary(page) -> dict:
    return page.evaluate(
        """
        () => {
          const fields = Array.from(
            document.querySelectorAll("input, select, textarea")
          );

          const normalizeValue = (field) => {
            const fieldType = (field.type || field.tagName || "").toLowerCase();
            if (fieldType === "checkbox" || fieldType === "radio") {
              return field.checked ? (field.value || "checked") : "";
            }
            if (fieldType === "file") {
              const fileNames = Array.from(field.files || []).map((f) => f.name);
              return fileNames.join(", ");
            }
            return (field.value || "").trim();
          };

          const filledFields = fields
            .map((field) => {
              const value = normalizeValue(field);
              return {
                name: field.name || "",
                id: field.id || "",
                type: (field.type || field.tagName || "").toLowerCase(),
                value_preview: value.slice(0, 80),
              };
            })
            .filter((entry) => entry.value_preview !== "");

          return {
            total_fields: fields.length,
            filled_fields_count: filledFields.length,
            filled_fields_sample: filledFields.slice(0, 12),
          };
        }
        """
    )


def _wait_for_extension_service_worker(context):
    if context.service_workers:
        return context.service_workers[0]
    try:
        return context.wait_for_event("serviceworker", timeout=15000)
    except PlaywrightTimeoutError as exc:
        raise RuntimeError(
            "Timed out waiting for Simplify extension service worker. "
            "Confirm SIMPLIFY_EXTENSION_PATH points to a valid unpacked extension."
        ) from exc


def main() -> None:
    args = _parse_args()
    settings = Settings()

    if not settings.simplify_enabled:
        raise RuntimeError("SIMPLIFY_ENABLED must be true to run this smoke test.")

    extension_path = _required_path(settings.simplify_extension_path, "SIMPLIFY_EXTENSION_PATH")
    profile_dir = _required_path(settings.simplify_profile_dir, "SIMPLIFY_PROFILE_DIR")

    if not extension_path.exists():
        raise RuntimeError(
            f"SIMPLIFY_EXTENSION_PATH does not exist: {extension_path}. "
            "Set it to the unpacked extension directory."
        )
    if not extension_path.is_dir():
        raise RuntimeError(
            f"SIMPLIFY_EXTENSION_PATH is not a directory: {extension_path}. "
            "Set it to the unpacked extension directory."
        )
    manifest_path = extension_path / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(
            "SIMPLIFY_EXTENSION_PATH does not look like an unpacked extension "
            f"(missing manifest.json): {extension_path}"
        )

    dummy_form_path = (REPO_ROOT / "tests" / "fixtures" / "dummy_apply_form.html").resolve()
    if not dummy_form_path.exists():
        raise RuntimeError(f"Dummy fixture not found: {dummy_form_path}")

    artifact_dir = (REPO_ROOT / "storage" / "artifacts" / "simplify_dummy_test").resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    target_url = args.url.strip() or dummy_form_path.as_uri()

    print("Using Simplify extension path:", extension_path)
    print("Using Simplify profile dir:", profile_dir)
    print("Dummy form:", dummy_form_path)
    print("Opening URL:", target_url)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chromium",
            headless=False,
            args=[
                f"--disable-extensions-except={extension_path}",
                f"--load-extension={extension_path}",
            ],
        )

        try:
            service_worker = _wait_for_extension_service_worker(context)
            extension_id = service_worker.url.split("/")[2]
            print("Extension loaded.")
            print("Extension ID:", extension_id)

            page = context.new_page()
            page.goto(target_url, wait_until="domcontentloaded")
            page.wait_for_load_state("load")

            print("Page URL:", page.url)
            print("Page title:", page.title())
            print(
                "MVP note: this smoke test checks Simplify profile/account autofill; "
                "local resume upload automation is a later feature."
            )
            input(
                "Inspect Simplify autofill behavior (including how it handles the resume field), "
                "then press Enter to capture artifacts and close the browser... "
            )

            summary = _collect_fill_summary(page)
            summary_path = artifact_dir / "field_fill_summary.json"
            summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

            screenshot_path = artifact_dir / "dummy_apply_page.png"
            html_path = artifact_dir / "dummy_apply_page.html"
            page.screenshot(path=str(screenshot_path), full_page=True)
            html_path.write_text(page.content(), encoding="utf-8")

            print("Field fill summary:")
            print(json.dumps(summary, indent=2))
            print("Saved field summary:", summary_path)
            print("Saved screenshot:", screenshot_path)
            print("Saved HTML:", html_path)
        finally:
            context.close()


if __name__ == "__main__":
    main()
