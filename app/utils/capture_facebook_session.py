from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    state_file = Path("playwright/.auth/facebook.json")
    state_file.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(
            "http://127.0.0.1:9222"
        )

        if not browser.contexts:
            raise RuntimeError(
                "No Chromium-based browser context was found on port 9222"
            )

        context = browser.contexts[0]

        print("Connected pages:")
        for page in context.pages:
            print(page.url)

        input(
            "Make sure Facebook Marketplace listings are visible in the "
            "connected browser, then press Enter here."
        )

        context.storage_state(path=str(state_file))

    print(f"Session saved to {state_file}")


if __name__ == "__main__":
    main()
