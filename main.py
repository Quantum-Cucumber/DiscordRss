import yaml
import json
import feedparser
from discord import Webhook, RequestsWebhookAdapter, Embed
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


def build_webhook():
    with open("config.yaml", "r") as fd:
        url = yaml.full_load(fd)["webhook"]

    webhook = Webhook.from_url(url, adapter=RequestsWebhookAdapter())
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


def send_entry(webhook: Webhook,
               feed: feedparser.FeedParserDict, entry: feedparser.FeedParserDict,
               name: str, fields: dict):
    def parse_field(field):
        if isinstance(field, str) and field.startswith("$"):
            path = field.lstrip("$").split(".")

            source = path.pop(0)
            if source == "entry":
                return crawl_dict(entry, path)
            elif source == "feed":
                return crawl_dict(feed, path)
        else:
            return field

    embed = Embed()
    embed.colour = fields.get("colour") or fields.get("color") or Embed.Empty
    embed.title = parse_field(fields.get("title"))
    embed.url = parse_field(fields.get("url"))
    embed.description = parse_field(fields.get("body"))
    embed = embed.set_thumbnail(url=(parse_field(fields.get("thumbnail")) or Embed.Empty))

    webhook.send(username=f"{name} RSS Feed", content=f"New post in {name}!", embed=embed)


def main():
    sources = load_sources()
    cache = load_cache()
    webhook = build_webhook()

    # Process all sources
    new_cache = {}
    for name, data in sources.items():
        print("Loading", name)

        # Read the rss feed
        feed = feedparser.parse(data["feed"])

        latest_id = feed.entries[0].id
        new_cache.update({name: latest_id})

        last_sent_id = cache.get(name)  # Will be None if no cache entry exists
        for entry in feed.entries:
            if entry.id != last_sent_id:
                send_entry(webhook, feed["feed"], entry, name, data["embed"])

                if last_sent_id is None:  # Only send 1 entry
                    break
            else:
                break

    # Save new cache if needed
    if new_cache != cache:
        with open(".cache.json", "w+") as fd:
            json.dump(new_cache, fd)


if __name__ == "__main__":
    main()
