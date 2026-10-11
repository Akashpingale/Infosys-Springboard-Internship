import argparse
import json
import os
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

API_URL = "https://api.tavily.com/search"
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_IDEA = "AI crop disease detection app for farmers in India"

QUERIES = {
    "Market size and trends": "{idea} market size growth trends",
    "Competitors": "{idea} competitors alternatives startups",
    "Customer demand": "{idea} customer problems demand",
}


def search(api_key, query, max_results, depth):
    response = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "query": query,
            "search_depth": depth,
            "max_results": max_results,
            "include_answer": True,
        },
        timeout=30,
    )
    if response.status_code == 401:
        sys.exit("Invalid API key. Check TAVILY_API_KEY in your .env file.")
    if response.status_code == 429:
        sys.exit("Rate limit or credit limit reached. Try again later.")
    response.raise_for_status()
    return response.json()


def shorten(text, width=220):
    return textwrap.shorten(" ".join(text.split()), width=width, placeholder="...")


def render(idea, sections):
    lines = [
        f"# Web Search Results: {idea}",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M}",
        "",
    ]
    for title, data in sections:
        lines += [f"## {title}", f"Query: {data['query']}", ""]
        if data.get("answer"):
            lines += [f"Summary: {shorten(data['answer'], 400)}", ""]
        for i, item in enumerate(data["results"], 1):
            lines += [
                f"{i}. {item['title']} (relevance {item['score']:.2f})",
                f"   {item['url']}",
                f"   {shorten(item['content'])}",
                "",
            ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Tavily web search test")
    parser.add_argument("--idea", default=DEFAULT_IDEA)
    parser.add_argument("--max-results", type=int, default=3)
    parser.add_argument("--depth", choices=["basic", "advanced"], default="basic")
    args = parser.parse_args()

    load_dotenv(BASE_DIR / ".env")
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        sys.exit("TAVILY_API_KEY not found. Copy .env.example to .env and add your key.")

    sections, raw = [], {}
    for title, template in QUERIES.items():
        data = search(api_key, template.format(idea=args.idea), args.max_results, args.depth)
        sections.append((title, data))
        raw[title] = data

    report = render(args.idea, sections)
    print(report)

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "search_results.md").write_text(report, encoding="utf-8")
    (OUTPUT_DIR / "search_results.json").write_text(
        json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
