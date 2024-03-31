import asyncio
import random
import json
import os
from tqdm import tqdm

from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

SCRAPED_CONTENTS_FILE = "scraped_contents.json"
BOOKMARKS_URL = "https://twitter.com/i/bookmarks"
EMPTY_SCROLL_LIMIT = 3  # Number of consecutive empty scrolls before ending the loop


async def load_or_initialize_json(filepath, default=None):
    if default is None:
        default = []
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return default


async def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


async def setup_page(browser, cookie_string):
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
    await asyncio.sleep(random.uniform(2, 5))
    return page


async def scrape_post_content(page, tweet_contents):
    await asyncio.sleep(random.uniform(2, 5))

    for tweet in tqdm(tweet_contents, desc="Scraping Posts"):
        link = tweet["link"]

        if tweet["content"] is not None and tweet["time"] is not None:
            print(f"Already scraped: {link}")
            continue

        print("Scraping:", link)

        try:
            response = await page.goto(link)
            assert response.status == 200
            assert page.url == link
            await asyncio.sleep(5)  # Give some time for page to load
            await page.wait_for_selector("article", timeout=5000)

            tweet_div = await page.query_selector(
                'article div[data-testid="tweetText"]'
            )
            if tweet_div:
                tweet_content = await tweet_div.eval_on_selector_all(
                    ":scope > *",
                    """(nodes) => {
                        return nodes.map(node => {
                            // For 'a' tags, return an object with text and href
                            if (node.tagName.toLowerCase() === 'a') {
                                return {
                                    text: node.innerText,  // The text of the 'a' tag
                                    href: node.href  // The absolute href of the 'a' tag
                                };
                            }
                            // For other tags, return their innerText
                            return {
                                text: node.innerText
                            };
                        }).filter(item => item.text.trim());  // Filter out any objects with empty text
                    }""",
                )

                tweet_content_parts = []

                for content_piece in tweet_content:
                    # Check if the href key exists in the object
                    if "href" in content_piece:
                        # Create a string with both text and href
                        content_str = (
                            f"{content_piece['text']} ({content_piece['href']})"
                        )
                    else:
                        # Otherwise, just take the text
                        content_str = content_piece["text"]

                    # Add the content string to the parts list
                    tweet_content_parts.append(content_str)

                # Combine the parts into one string separated by spaces
                tweet_content_combined = " ".join(tweet_content_parts)

            else:
                print("Couldn't find the tweet content.")
                tweet_content_combined = None

            time_element = await page.query_selector("article time")

            if time_element:
                # Extract the content and the datetime attribute
                time_content = await time_element.inner_text()
                datetime_value = await time_element.get_attribute("datetime")

            else:
                print("Couldn't find the <time> element.")
                time_content = None
                datetime_value = None

            tweet.update(
                {
                    "content": tweet_content_combined,
                    "time": datetime_value if time_element else None,
                }
            )
            await save_json(SCRAPED_CONTENTS_FILE, tweet_contents)

        except Exception as e:
            print(f"An error occurred while scraping {link}: {e}")
            tweet_contents[link] = {
                "content": None,
                "time": None,
            }
            await save_json(SCRAPED_CONTENTS_FILE, tweet_contents)


async def scrape_bookmarks_urls(page, main_tweet_links):
    await asyncio.sleep(random.uniform(2, 5))
    try:
        response = await page.goto(BOOKMARKS_URL)
        print("response status:", response.status)
        assert response.status == 200
        assert page.url == BOOKMARKS_URL
        await asyncio.sleep(5)

        await page.wait_for_selector("article", timeout=5000)
        await asyncio.sleep(5)

        await page.evaluate("window.scrollTo(0, 0)")  # This scrolls to the top
        scroll_position = await page.evaluate("window.pageYOffset")
        assert scroll_position == 0
        await asyncio.sleep(random.uniform(2, 5))

        # Add a counter for empty scrolls
        empty_scroll_counter = 0
        last_scroll_position = -1
        current_scroll_position = 0

        while True:  # Keep scrolling until 3 consecutive empty scrolls
            tweet_links = await page.eval_on_selector_all(
                "article",
                """(articles) => {
                    return articles.map(article => {
                        const link = article.querySelector('a[href*="/status/"]');
                        return link ? link.href : null;
                    }).filter(Boolean);
                }""",
            )
            # Filter out only the main tweet URLs
            new_links = [
                link
                for link in tweet_links
                if link not in [tweet["link"] for tweet in main_tweet_links]
            ]

            # Scroll down to get more tweets
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(random.uniform(2, 5))

            if not new_links:
                print("No new links, already scraped")
                print("Total links:", len(main_tweet_links))
                empty_scroll_counter += 1
                if empty_scroll_counter >= EMPTY_SCROLL_LIMIT:
                    print(
                        f"No new links found for {EMPTY_SCROLL_LIMIT} consecutive scrolls. Ending the loop."
                    )
                    break
                continue
            else:
                empty_scroll_counter = 0

            print("New links:", len(new_links))
            print("Total links:", len(main_tweet_links))

            for link in new_links:
                main_tweet_links.append(
                    {
                        "link": link,
                        "content": None,
                        "time": None,
                    }
                )
            await save_json(SCRAPED_CONTENTS_FILE, main_tweet_links)

            # Check if scroll position has changed
            (
                last_scroll_position,
                current_scroll_position,
            ) = current_scroll_position, await page.evaluate("window.pageYOffset")
            if last_scroll_position == current_scroll_position:
                break

    except Exception as e:
        print(f"An error occurred: {e}")


async def main_async() -> None:
    cookie_string: str | None = os.getenv("COOKIE_STRING")
    if not cookie_string:
        print("Cookie string not found")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await setup_page(browser, cookie_string)

        main_tweet_links = await load_or_initialize_json(SCRAPED_CONTENTS_FILE)
        await scrape_bookmarks_urls(page, main_tweet_links)
        await scrape_post_content(page, main_tweet_links)

        await browser.close()
        print("Done")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
