import json
import os
import sys

import anthropic
from dotenv import load_dotenv


# Add your input texts here. Each entry is (label, text).
# The label only shows up in console output, not in the JSON.
INPUT_TEXTS = [
    (
        "Acme Ltd",
        "Acme Ltd is a B2B SaaS company that builds workflow automation tools "
        "for logistics teams. Their platform helps mid-sized enterprises reduce "
        "manual admin work by 40%. They primarily serve companies in the UK and "
        "Europe. Key features include analytics dashboards, AI-powered document "
        "parsing, and automated email routing. The company was founded in 2018.",
    ),
    (
        "Beta Inc",
        "Beta Inc provides cloud-based compliance software. It works primarily "
        "with financial institutions across North America. The product includes "
        "risk scoring, regulatory monitoring, and automated reporting tools. "
        "Customers report up to 30% faster audit preparation times.",
    ),
]


# Tool schema — forces Claude to return specific fields with the right types.
# tool_choice="tool" means Claude must fill this in, it can't reply in plain text.
EXTRACTION_TOOL = {
    "name": "extract_company_profile",
    "description": "Extract structured company profile information from unstructured text.",
    "cache_control": {"type": "ephemeral"},  # cache between calls to save tokens
    "input_schema": {
        "type": "object",
        "properties": {
            "company_name": {
                "type": "string",
                "description": "The company's formal name as stated in the text.",
            },
            "industry": {
                "type": "string",
                "description": "A concise industry category (e.g. 'B2B SaaS', 'Cloud Software').",
            },
            "target_customer": {
                "type": "string",
                "description": "Primary customer type and segment in one sentence.",
            },
            "geography": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Geographic markets served. Each region as a separate item.",
            },
            "key_features": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Distinct product features. Each as a separate list item.",
            },
            "value_proposition": {
                "type": "string",
                "description": (
                    "One sentence covering the core benefit to customers, "
                    "including any quantified outcome if mentioned."
                ),
            },
        },
        "required": [
            "company_name",
            "industry",
            "target_customer",
            "geography",
            "key_features",
            "value_proposition",
        ],
    },
}


# System prompt handles interpretation (what each field means).
# The tool schema handles structure (types, required fields).
SYSTEM_PROMPT = """You are a precise business analyst. Extract structured company \
profile information from the provided text.

Field instructions:
- company_name: The company's formal name as stated.
- industry: A concise category (e.g. "B2B SaaS", "Cloud Software", "FinTech").
- target_customer: Primary customer type and segment in one sentence.
- geography: Each region or market as a separate list item. Never merge multiple \
regions into one string (e.g. return ["UK", "Europe"] not ["UK and Europe"]).
- key_features: Each distinct product feature as a separate list item.
- value_proposition: One sentence covering the core benefit, including any \
quantified outcome stated in the text.

Extract only what's in the text. Don't add outside knowledge."""


def extract_company_profile(client: anthropic.Anthropic, text: str) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        temperature=0,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "extract_company_profile"},
        messages=[{"role": "user", "content": text}],
    )

    if response.stop_reason == "max_tokens":
        print("  WARNING: response truncated — increase max_tokens if needed.")

    usage = response.usage
    cache_hit = getattr(usage, "cache_read_input_tokens", 0) or 0
    if cache_hit:
        print(f"  Cache hit: {cache_hit} tokens served from cache.")
    else:
        written = getattr(usage, "cache_creation_input_tokens", 0) or 0
        print(f"  Cache miss: {written} tokens written to cache.")

    tool_block = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_block is None:
        raise RuntimeError("No tool_use block in response.")

    return tool_block.input


def validate(data: dict, label: str) -> None:
    string_fields = ["company_name", "industry", "target_customer", "value_proposition"]
    array_fields = ["geography", "key_features"]

    for field in string_fields:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"[{label}] '{field}' must be a non-empty string, got: {value!r}")

    for field in array_fields:
        value = data.get(field)
        if not isinstance(value, list) or len(value) == 0:
            raise ValueError(f"[{label}] '{field}' must be a non-empty list, got: {value!r}")
        for i, item in enumerate(value):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"[{label}] '{field}[{i}]' must be a non-empty string, got: {item!r}")


def main() -> None:
    load_dotenv()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "ANTHROPIC_API_KEY not set.\n"
            "Add it to a .env file or export it in your shell:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-..."
        )
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    for label, text in INPUT_TEXTS:
        print(f"\n{'=' * 60}")
        print(f"Processing: {label}")
        print("=" * 60)

        try:
            profile = extract_company_profile(client, text)
            validate(profile, label)
            print(json.dumps(profile, indent=2))

        except anthropic.APIConnectionError as exc:
            print(f"Connection error: {exc}")
            sys.exit(1)

        except anthropic.RateLimitError:
            print("Rate limit hit — wait a moment and retry.")
            sys.exit(1)

        except anthropic.APIStatusError as exc:
            print(f"API error {exc.status_code}: {exc.message}")
            sys.exit(1)

        except (RuntimeError, ValueError) as exc:
            print(f"Error: {exc}")
            sys.exit(1)

    print(f"\n{'=' * 60}")
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()