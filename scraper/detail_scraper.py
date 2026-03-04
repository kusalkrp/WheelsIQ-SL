"""
Prime Wheels SL — Detail page scraper.
Navigates to individual vehicle listing pages and extracts all specs.
"""

import asyncio
import random
import re

from playwright.async_api import Browser, Page

from scraper.config import (
    BASE_URL,
    DETAIL_DESCRIPTION,
    DETAIL_MAIN_IMAGE,
    DETAIL_SPECS_TABLE,
    DETAIL_THUMBNAILS,
    SPECS_LABEL_MAP,
    USER_AGENTS,
    VIEWPORT_HEIGHT,
    VIEWPORT_WIDTH,
)
from scraper.parsers import parse_detail_page
from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def scrape_detail_page(page: Page, url: str) -> dict | None:
    """
    Scrape a single vehicle detail page.

    Args:
        page: Playwright Page instance
        url: Full URL of the vehicle listing

    Returns:
        Parsed vehicle dict or None on failure.
    """
    logger.info("scraping_detail", url=url)

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        logger.error("detail_page_load_failed", url=url, error=str(e))
        return None

    detail_data = {"url": url}

    # ── Title ──
    try:
        title_el = page.locator("h1").first
        detail_data["title"] = await title_el.text_content()
    except Exception:
        try:
            title_el = page.locator("h2").first
            detail_data["title"] = await title_el.text_content()
        except Exception:
            detail_data["title"] = ""

    # ── Posted info (from text near title) ──
    try:
        # Pattern: "Posted by {name} on {date}, {location}"
        body_text = await page.locator("body").text_content()
        posted_match = re.search(
            r"Posted by\s+(.+?)\s+on\s+(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}\s*[ap]m)[,\s]*(\w[\w\s]*)?",
            body_text or "",
            re.IGNORECASE,
        )
        if posted_match:
            detail_data["seller_name"] = posted_match.group(1).strip()
            detail_data["posted_text"] = posted_match.group(2).strip()
            detail_data["location"] = (posted_match.group(3) or "").strip()
    except Exception:
        pass

    # ── Specs Table (table.moret) ──
    specs = {}
    try:
        table = page.locator(DETAIL_SPECS_TABLE).first
        rows = table.locator("tr")
        row_count = await rows.count()

        for i in range(row_count):
            row = rows.nth(i)
            cells = row.locator("td")
            cell_count = await cells.count()

            if cell_count >= 2:
                # Standard 2-column row (label | value)
                label = (await cells.nth(0).text_content() or "").strip()
                value = (await cells.nth(1).text_content() or "").strip()
                if label:
                    specs[label] = value

            if cell_count >= 4:
                # 4-column row (label | value | label | value)
                label2 = (await cells.nth(2).text_content() or "").strip()
                value2 = (await cells.nth(3).text_content() or "").strip()
                if label2:
                    specs[label2] = value2

        # Extract price and negotiable from the "Price" row
        price_row = specs.get("Price", "")
        if price_row:
            detail_data["price_text"] = price_row
        else:
            # Try the specific td.tfiv selector
            try:
                price_el = page.locator("td.tfiv").first
                detail_data["price_text"] = await price_el.text_content()
            except Exception:
                detail_data["price_text"] = ""

        # Contact
        contact = specs.get("Contact", "")
        if contact:
            detail_data["contact"] = contact

    except Exception as e:
        logger.warning("specs_table_error", url=url, error=str(e))

    detail_data["specs"] = specs

    # ── Description ──
    try:
        desc_el = page.locator(DETAIL_DESCRIPTION).first
        detail_data["description"] = await desc_el.text_content()
    except Exception:
        try:
            # Fallback: look for the Details row in specs
            detail_data["description"] = specs.get("Details", "")
        except Exception:
            detail_data["description"] = ""

    # ── Images ──
    images = []
    try:
        # Main image
        main_img = page.locator(DETAIL_MAIN_IMAGE).first
        main_src = await main_img.get_attribute("src")
        if main_src:
            if main_src.startswith("//"):
                main_src = f"https:{main_src}"
            images.append(main_src)
    except Exception:
        pass

    try:
        # Thumbnail gallery
        thumb_els = page.locator(DETAIL_THUMBNAILS)
        thumb_count = await thumb_els.count()
        for i in range(thumb_count):
            src = (
                await thumb_els.nth(i).get_attribute("src")
                or await thumb_els.nth(i).get_attribute("data-src")
            )
            if src:
                if src.startswith("//"):
                    src = f"https:{src}"
                if src not in images:
                    images.append(src)
    except Exception:
        pass

    detail_data["images"] = images

    # ── View count ──
    try:
        body_text = await page.locator("body").text_content()
        view_match = re.search(r"(\d[\d,]*)\s*Views?", body_text or "", re.IGNORECASE)
        if view_match:
            detail_data["view_count"] = view_match.group(1).replace(",", "")
    except Exception:
        pass

    # ── Raw HTML (for future re-parsing) ──
    try:
        detail_data["raw_html"] = await page.content()
    except Exception:
        pass

    # Parse into normalized dict
    return parse_detail_page(detail_data)


async def scrape_details_batch(
    browser: Browser,
    urls: list[str],
    batch_size: int = 1,
) -> list[dict]:
    """
    Scrape multiple detail pages sequentially with delays.

    Args:
        browser: Playwright Browser
        urls: List of detail page URLs
        batch_size: Number of concurrent pages (keep at 1 for politeness)

    Returns:
        List of parsed vehicle dicts.
    """
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
        locale="en-US",
        timezone_id="Asia/Colombo",
    )
    page = await context.new_page()

    # Block images and ads for speed
    await page.route(
        "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot}",
        lambda route: route.abort(),
    )
    await page.route("**/googleads**", lambda route: route.abort())
    await page.route("**/googlesyndication**", lambda route: route.abort())

    results = []
    for i, url in enumerate(urls):
        try:
            result = await scrape_detail_page(page, url)
            if result:
                results.append(result)
                logger.info(
                    "detail_scraped",
                    index=i + 1,
                    total=len(urls),
                    riyasewana_id=result.get("riyasewana_id"),
                    make=result.get("make"),
                    model=result.get("model"),
                )
        except Exception as e:
            logger.error("detail_scrape_error", url=url, error=str(e))

        # Random delay between detail pages
        if i < len(urls) - 1:
            delay = random.uniform(settings.scrape_delay_min, settings.scrape_delay_max)
            await asyncio.sleep(delay)

    await context.close()

    logger.info("detail_batch_complete", total_scraped=len(results), total_urls=len(urls))
    return results
