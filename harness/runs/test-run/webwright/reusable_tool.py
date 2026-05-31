# -*- coding: utf-8 -*-
import argparse
import asyncio
from playwright.async_api import async_playwright

async def main():
    parser = argparse.ArgumentParser(description="Webwright Parameterized Reusable Workflow CLI")
    parser.add_argument("--url", required=True, help="Target URL")
    args = parser.parse_args()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print(f"Navigating to {args.url}...")
        await page.goto(args.url)
        print(f"Title: {await page.title()}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
