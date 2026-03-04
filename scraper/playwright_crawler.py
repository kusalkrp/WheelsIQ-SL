"""
Prime Wheels SL — Async Playwright crawler for riyasewana.com search pages.
Extracts listing cards and navigates pagination.
"""

import asyncio
import random

from playwright.async_api import Browser, Page, async_playwright

from scraper.config import (
    BASE_URL,
    CATEGORIES,
    LISTINGS_PER_PAGE,
    SEARCH_BOXINTXT_SELECTOR,
    SEARCH_LINK_SELECTOR,
    SEARCH_LISTING_SELECTOR,
    SEARCH_PRICE_SELECTOR,
    SEARCH_PROMOTED_CLASS,
    SEARCH_THUMBNAIL_SELECTOR,
    SEARCH_TITLE_SELECTOR,
    SEARCH_URL_TEMPLATE,
    USER_AGENTS,
    VIEWPORT_HEIGHT,
    VIEWPORT_WIDTH,
)
from scraper.parsers import parse_search_listing
from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def create_browser(playwright) -> Browser:
    """Create a stealth-configured Chromium browser."""
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ],
    )
    return browser


async def create_page(browser: Browser) -> Page:
    """Create a new page with stealth settings."""
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
        locale="en-US",
        timezone_id="Asia/Colombo",
    )
    page = await context.new_page()

    # Block unnecessary resources for speed
    await page.route(
        "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot}",
        lambda route: route.abort(),
    )
    # Block ad scripts
    await page.route(
        "**/googleads**",
        lambda route: route.abort(),
    )
    await page.route(
        "**/googlesyndication**",
        lambda route: route.abort(),
    )

    return page


async def scrape_search_page(
    page: Page,
    category: str = "cars",
    page_num: int = 1,
) -> list[dict]:
    """
    Scrape a single search results page.

    Args:
        page: Playwright Page instance
        category: Vehicle category slug
        page_num: Page number (1-indexed)

    Returns:
        List of parsed listing dicts from search cards.
    """
    url = SEARCH_URL_TEMPLATE.format(category=category, page=page_num)
    logger.info("scraping_search_page", category=category, page=page_num, url=url)

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # Wait for listings to render
        await page.wait_for_selector(SEARCH_LISTING_SELECTOR, timeout=10000)
    except Exception as e:
        logger.error("page_load_failed", url=url, error=str(e))
        return []

    # Extract all listing cards
    listings = page.locator(SEARCH_LISTING_SELECTOR)
    count = await listings.count()
    logger.info("listings_found", count=count, page=page_num)

    results = []
    for i in range(count):
        try:
            listing = listings.nth(i)

            # Title & URL
            link_el = listing.locator(SEARCH_LINK_SELECTOR).first
            title = await link_el.text_content()
            href = await link_el.get_attribute("href")
            detail_url = href if href and href.startswith("http") else f"{BASE_URL}{href}"

            # Price
            price_text = ""
            try:
                price_el = listing.locator(SEARCH_PRICE_SELECTOR).first
                price_text = await price_el.text_content()
            except Exception:
                pass

            # Location & other boxintxt fields
            location_text = ""
            try:
                boxintxt_els = listing.locator(SEARCH_BOXINTXT_SELECTOR)
                boxintxt_count = await boxintxt_els.count()
                if boxintxt_count > 0:
                    location_text = await boxintxt_els.nth(0).text_content()
            except Exception:
                pass

            # Thumbnail
            thumbnail_url = None
            try:
                thumb_el = listing.locator(SEARCH_THUMBNAIL_SELECTOR).first
                thumbnail_url = (
                    await thumb_el.get_attribute("src")
                    or await thumb_el.get_attribute("data-src")
                )
                if thumbnail_url and thumbnail_url.startswith("//"):
                    thumbnail_url = f"https:{thumbnail_url}"
            except Exception:
                pass

            # Is promoted?
            classes = await listing.get_attribute("class") or ""
            is_promoted = SEARCH_PROMOTED_CLASS in classes

            raw = {
                "url": detail_url,
                "title": title,
                "price_text": price_text,
                "location_text": location_text,
                "thumbnail_url": thumbnail_url,
                "is_promoted": is_promoted,
            }

            parsed = parse_search_listing(raw)
            if parsed:
                results.append(parsed)

        except Exception as e:
            logger.warning("listing_parse_error", index=i, error=str(e))
            continue

    return results


async def scrape_category_search(
    browser: Browser,
    category: str = "cars",
    max_pages: int | None = None,
) -> list[dict]:
    """
    Scrape all search pages for a category.

    Args:
        browser: Playwright Browser
        category: Category slug
        max_pages: Override max pages (None = use config default)

    Returns:
        List of all parsed listings across pages.
    """
    max_pg = max_pages or settings.scrape_max_pages
    page = await create_page(browser)
    all_listings = []

    try:
        for page_num in range(1, max_pg + 1):
            listings = await scrape_search_page(page, category, page_num)

            if not listings:
                logger.info("no_more_listings", category=category, stopped_at_page=page_num)
                break

            all_listings.extend(listings)
            logger.info(
                "search_progress",
                category=category,
                page=page_num,
                page_listings=len(listings),
                total=len(all_listings),
            )

            # If fewer than expected listings, probably last page
            if len(listings) < LISTINGS_PER_PAGE * 0.5:
                logger.info("likely_last_page", category=category, page=page_num)
                break

            # Random delay between pages
            delay = random.uniform(settings.scrape_delay_min, settings.scrape_delay_max)
            await asyncio.sleep(delay)

    finally:
        await page.context.close()

    logger.info(
        "category_search_complete",
        category=category,
        total_listings=len(all_listings),
    )
    return all_listings


async def get_total_pages(page: Page, category: str = "cars") -> int:
    """Estimate total pages for a category by checking pagination."""
    url = SEARCH_URL_TEMPLATE.format(category=category, page=1)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # Look for last page number in pagination
        pagination_links = page.locator("a[href*='page=']")
        count = await pagination_links.count()
        max_page = 1
        for i in range(count):
            href = await pagination_links.nth(i).get_attribute("href") or ""
            import re
            match = re.search(r"page=(\d+)", href)
            if match:
                max_page = max(max_page, int(match.group(1)))
        return max_page
    except Exception:
        return 1
