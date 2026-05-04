#  python -m tests.runners.debug.check_playwright_url url_test

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright


async def check_url(
    url: str,
    *,
    timeout_ms: int,
    headless: bool,
    screenshot_path: Path | None,
) -> int:
    failed_requests: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        page.on(
            "requestfailed",
            lambda request: failed_requests.append(
                f"{request.url} -> {request.failure or 'unknown failure'}"
            ),
        )

        try:
            response = await page.goto(
                url,
                wait_until="load",
                timeout=timeout_ms,
            )

            title = await page.title()
            status = response.status if response is not None else None

            print(f"url: {url}")
            print(f"final_url: {page.url}")
            print(f"title: {title!r}")
            print(f"status: {status}")

            if failed_requests:
                print("failed_requests:")
                for failed in failed_requests:
                    print(f"- {failed}")

            if response is None:
                print("result: FAIL - page.goto returned no response")
                return 1

            if status >= 400:
                print(f"result: FAIL - HTTP status {status}")
                return 1

            if screenshot_path is not None:
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(screenshot_path), full_page=True)
                print(f"screenshot: {screenshot_path}")

            print("result: OK")
            return 0

        except PlaywrightTimeoutError as exc:
            print(f"result: FAIL - timeout after {timeout_ms}ms")
            print(exc)
            return 1

        except PlaywrightError as exc:
            print("result: FAIL - playwright error")
            print(exc)
            return 1

        finally:
            await context.close()
            await browser.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--screenshot-path", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(
        check_url(
            args.url,
            timeout_ms=args.timeout_ms,
            headless=not args.headed,
            screenshot_path=args.screenshot_path,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
