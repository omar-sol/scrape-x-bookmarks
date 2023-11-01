import asyncio
import random
import json
import os

from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()


async def scrape_twitter_bookmarks(cookie_string):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.context.add_cookies(
            [
                {
                    "name": "auth_token",
                    "value": cookie_string,
                    "domain": ".twitter.com",
                    "path": "/",
                }
            ]
        )
        # Random delay before navigating to mimic human behavior
        await asyncio.sleep(random.uniform(2, 5))

        try:
            # Going to bookmarks page
            response = await page.goto("https://twitter.com/i/bookmarks")
            print(response.status, page.url)
            assert response.status == 200
            assert page.url == "https://twitter.com/i/bookmarks"
            await asyncio.sleep(5)  # Give some time for page to load

            # Wait for first article to load
            await page.wait_for_selector("article", timeout=5000)
            await asyncio.sleep(5)  # Wait for a longer duration before scrolling up

            # Scroll to the top
            await page.evaluate("window.scrollTo(0, 0)")  # This scrolls to the top
            scroll_position = await page.evaluate("window.pageYOffset")
            assert scroll_position == 0  # To ensure you're at the top
            await asyncio.sleep(random.uniform(2, 5))  # Wait for a longer duration

            if os.path.exists("scraped_links.json"):
                with open("scraped_links.json", "r") as f:
                    main_tweet_links = json.load(f)
            else:
                main_tweet_links = []

            last_scroll_position = -1
            current_scroll_position = 0

            # while len(main_tweet_links) < 20:  # While desired count not reached
            while True:  # While desired count not reached
                # Capture all the links
                tweet_links = await page.eval_on_selector_all(
                    "article",
                    """(articles) => {
                        return articles.map(article => {
                            const link = article.querySelector('a[href*="/status/"]');
                            return link ? link.href : null;
                        }).filter(Boolean);
                    }""",
                )
                # print("Tweet links:", len(tweet_links), tweet_links)
                # Filter out only the main tweet URLs
                new_links = [
                    link for link in tweet_links if link not in main_tweet_links
                ]

                # Scroll down to get more tweets
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(random.uniform(2, 5))

                if not new_links:
                    print("No new links, already scraped")
                    print("Total links:", len(main_tweet_links))
                    continue

                # Extend the main_tweet_links list with new unique links
                print("New links:", len(new_links))
                main_tweet_links.extend(new_links)
                print("Total links:", len(main_tweet_links))

                with open("scraped_links.json", "w", encoding="utf-8") as f:
                    json.dump(main_tweet_links, f, ensure_ascii=False, indent=4)

                # Check if scroll position has changed
                (
                    last_scroll_position,
                    current_scroll_position,
                ) = current_scroll_position, await page.evaluate("window.pageYOffset")
                if last_scroll_position == current_scroll_position:
                    break

        except Exception as e:
            print(f"An error occurred: {e}")

        await browser.close()
        return main_tweet_links


def main():
    cookie_string = os.getenv("COOKIE_STRING")
    data = asyncio.get_event_loop().run_until_complete(
        scrape_twitter_bookmarks(cookie_string)
    )
    print(data)


if __name__ == "__main__":
    main()
