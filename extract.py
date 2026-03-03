#!/usr/bin/env python3
"""
Reads company description paragraphs from a text file and extracts
structured JSON from each one using Claude.

Usage:
  python extract.py --input-file inputs.txt
  python extract.py --input-file inputs.txt --output-file results.json

Paragraphs in the input file should be separated by a blank line.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from typing import Any, Dict

import anthropic
from dotenv import load_dotenv


# Few-shot prompt — shows Claude two examples of input/output so it knows
# exactly what format to follow. The {input_text} placeholder gets swapped
# out at runtime with the actual paragraph.
PROMPT_TEMPLATE = """\
You are a precise extractor. Input: a short paragraph about a company.
Output: a single valid JSON object and nothing else with keys exactly: company_name, industry, target_customer, geography, key_features, value_proposition.
- `geography` and `key_features` must be JSON arrays (possibly empty).
- If a field is not present in the text, use an empty string for strings and an empty array for lists.
- Do not include any extra keys or commentary.


# Example 1
Input: "Acme Ltd is a B2B SaaS company that builds workflow automation tools for logistics teams. Their platform helps mid-sized enterprises reduce manual admin work by 40%. They primarily serve companies in the UK and Europe. Key features include analytics dashboards, AI-powered document parsing, and automated email routing. The company was founded in 2018."
Output: {"company_name": "Acme Ltd", "industry": "B2B SaaS", "target_customer": "logistics teams / mid-sized enterprises", "geography": ["UK", "Europe"], "key_features": ["analytics dashboards", "AI-powered document parsing", "automated email routing"], "value_proposition": "Helps mid-sized enterprises reduce manual admin work by 40%"}

# Example 2
Input: "Beta Inc provides cloud-based compliance software. It works primarily with financial institutions across North America. The product includes risk scoring, regulatory monitoring, and automated reporting tools. Customers report up to 30% faster audit preparation times."
Output: {"company_name": "Beta Inc", "industry": "cloud-based compliance software", "target_customer": "financial institutions", "geography": ["North America"], "key_features": ["risk scoring", "regulatory monitoring", "automated reporting tools"], "value_proposition": "Customers report up to 30% faster audit preparation times"}

Now extract from the input below (ONLY output the JSON object):

{input_text}
"""

REQUIRED_FIELDS = [
    "company_name", "industry", "target_customer",
    "geography", "key_features", "value_proposition",
]
ARRAY_FIELDS = ["geography", "key_features"]


def build_prompt(input_text: str) -> str:
    return PROMPT_TEMPLATE.replace("{input_text}", input_text.strip())


def parse_and_validate(raw: str) -> Dict[str, Any]:
    # Strip markdown fences in case Claude wraps output in ```json ... ```
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.DOTALL)

    try:
        obj = json.loads(text)
    except Exception as e:
        raise ValueError(f"Invalid JSON from model: {e}\nRaw output:\n{raw}")

    for field in REQUIRED_FIELDS:
        if field not in obj:
            raise ValueError(f"Missing key in model output: '{field}'")
    for field in ARRAY_FIELDS:
        if not isinstance(obj[field], list):
            raise ValueError(f"'{field}' must be an array, got: {type(obj[field]).__name__}")

    return obj


def call_anthropic(client: anthropic.Anthropic, prompt: str) -> str:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def extract_from_text(client: anthropic.Anthropic, input_text: str) -> Dict[str, Any]:
    prompt = build_prompt(input_text)
    raw = call_anthropic(client, prompt)
    return parse_and_validate(raw)


def main(argv=None):
    load_dotenv()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set.\nAdd it to a .env file or export it in your shell.", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Extract structured company JSON from text using Claude.")
    parser.add_argument("--input-file", required=True, help="Text file with paragraphs separated by blank lines")
    parser.add_argument("--output-file", help="Write results here (one JSON object per line)")
    args = parser.parse_args(argv)

    with open(args.input_file, "r", encoding="utf-8") as f:
        content = f.read().strip()

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    client = anthropic.Anthropic(api_key=api_key)

    results = []
    for i, paragraph in enumerate(paragraphs, 1):
        print(f"\n{'=' * 60}")
        print(f"Paragraph {i}")
        print("=" * 60)
        try:
            obj = extract_from_text(client, paragraph)
            results.append(obj)
            print(json.dumps(obj, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)

    if args.output_file:
        with open(args.output_file, "w", encoding="utf-8") as out:
            for o in results:
                out.write(json.dumps(o, ensure_ascii=False) + "\n")
        print(f"\nResults written to {args.output_file}")


if __name__ == "__main__":
    main()