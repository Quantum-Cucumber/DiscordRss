import asyncio
import aiohttp
import yaml
import json
import feedparser
from discord import Webhook, Embed
from typing import List


def load_sources():
    with open("config.yaml", "r") as fd:
        return yaml.full_load(fd)["sources"]


def load_cache():
    try:
        with open(".cache.json", "r") as fd:
            return json.load(fd)
    except FileNotFoundError:
        return {}


def build_webhook(session: aiohttp.ClientSession):
    with open("config.yaml", "r") as fd:
        url = yaml.full_load(fd)["webhook"]

    webhook = Webhook.from_url(url, session=session)
    return webhook


def crawl_dict(data: dict, path: List[str]):
    def crawl(branch, steps):
        step = steps.pop(0)
        if steps:
            # return None if key doesn't exist in dict, otherwise continue traversing
            return crawl(branch[step], steps) if step in branch else None
        else:
            return branch.get(step)

    return crawl(data, path)


def parse_field(feed: feedparser.FeedParserDict, entry: feedparser.FeedParserDict, field):
    if isinstance(field, str) and field.startswith("$"):
        path = field.lstrip("$").split(".")

        source = path.pop(0)
        if source == "entry":
            return crawl_dict(entry, path)
        elif source == "feed":
            return crawl_dict(feed, path)
    else:
        return field


async def send_entry(webhook: Webhook,
                     feed: feedparser.FeedParserDict, entry: feedparser.FeedParserDict,
                     name: str, fields: dict):
    embed = Embed()
    embed.colour = fields.get("colour") or fields.get("color") or Embed.Empty
    embed.title = parse_field(feed, entry, fields.get("title"))
    embed.url = parse_field(feed, entry, fields.get("url"))
    embed.description = parse_field(feed, entry, fields.get("body"))
    if embed.description and len(embed.description) > 2000:
        embed.description = embed.description[:2000] + "..."
    embed = embed.set_thumbnail(url=(parse_field(feed, entry, fields.get("thumbnail")) or Embed.Empty))

    await webhook.send(username=f"{name} RSS Feed", content=f"New post in {name}!", embed=embed)


async def main():
    async with aiohttp.ClientSession() as session:
        sources = load_sources()
        cache = load_cache()
        webhook = build_webhook(session)

        # Process all sources
        new_cache = {}
        for name, data in sources.items():
            print("Loading", name)

            # Which field to save for the ID. If not specified, use "id"
            id_field = data.get("id", "id")

            # Read the rss feed
            feed = feedparser.parse(data["feed"])

            latest_id = parse_field(feed, feed.entries[0], id_field)
            new_cache.update({name: latest_id})

            if name not in cache:
                print("Send one")
                # If feed has no cached ID, just send 1 entry
                await send_entry(webhook, feed["feed"], feed.entries[-1], name, data["embed"])
            else:
                print("Send unsent")
                # Send all unsent entries
                last_sent_id = cache[name]

                for entry in feed.entries:
                    if parse_field(feed, entry, id_field) != last_sent_id:
                        await send_entry(webhook, feed["feed"], entry, name, data["embed"])
                    else:
                        break

    # Save new cache if needed
    if new_cache != cache:
        with open(".cache.json", "w+") as fd:
            json.dump(new_cache, fd)


if __name__ == "__main__":
    asyncio.run(main())
