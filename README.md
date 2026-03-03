# company-profile-extractor

Converts unstructured company description text into structured JSON using the Claude API. Useful for enriching CRM data, building company databases, or any pipeline where you're ingesting raw company blurbs and need clean, consistent fields out the other end.

---

## What it does

Given a paragraph like this:

> Acme Ltd is a B2B SaaS company that builds workflow automation tools for logistics teams. Their platform helps mid-sized enterprises reduce manual admin work by 40%...

It returns:

```json
{
  "company_name": "Acme Ltd",
  "industry": "B2B SaaS",
  "target_customer": "Mid-sized logistics enterprises",
  "geography": ["UK", "Europe"],
  "key_features": ["Analytics dashboards", "AI-powered document parsing", "Automated email routing"],
  "value_proposition": "Reduces manual admin work by 40% for mid-sized logistics enterprises."
}
```

---

## Project structure

```
.
├── main.py          # Hardcoded inputs, tool use approach (schema-enforced output)
├── extract.py       # File-based inputs, few-shot prompt approach
├── requirements.txt
├── .env.example
└── .gitignore
```

### `main.py`

Processes two hardcoded company texts and prints structured JSON for each. Uses **tool use** (function calling) to guarantee the output matches the schema — Claude is forced to call `extract_company_profile` with the correct fields and types, so there's no risk of getting back markdown, prose, or wrong field names.

Also has **prompt caching** enabled: the system prompt and tool definition get cached on the first call. The second call reads from cache instead of re-processing those tokens, which reduces cost.

Run it with:
```bash
python main.py
```

### `extract.py`

More flexible — reads paragraphs from any text file (separated by blank lines) and extracts JSON from each. Uses a **few-shot prompt** approach: the prompt contains two worked examples, and Claude learns the expected format from them. Slightly less strict than tool use since output is raw text, but handles it with markdown fence stripping and field validation.

Run it with:
```bash
python extract.py --input-file inputs.txt
python extract.py --input-file inputs.txt --output-file results.json
```

Your `inputs.txt` should look like:

```
Acme Ltd is a B2B SaaS company...

Beta Inc provides cloud-based compliance software...
```

One blank line between each company.

---

## Setup

**Requirements:** Python 3.9+

```bash
# Install dependencies
pip install -r requirements.txt

# Copy the env template and add your Anthropic API key
cp .env.example .env
```

Open `.env` and replace the placeholder:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Get your key from [console.anthropic.com](https://console.anthropic.com) → API Keys.

---

## How the prompting works

### `main.py` — tool use

The tool definition acts as a strict JSON schema. When `tool_choice` is set to force a specific tool, Claude cannot reply in plain text — it has to return structured data that matches the schema exactly. Field types (`string` vs `array`) are enforced at the API level, not just checked after the fact.

The system prompt sits alongside the schema and handles the interpretive side: how to handle ambiguous geography strings, what counts as a feature vs a value proposition, etc.

```
System prompt  →  tells Claude HOW to interpret each field
Tool schema    →  tells the API WHAT shape the output must be
```

### `extract.py` — few-shot prompt

Two input/output examples are included directly in the prompt. Claude picks up the pattern and follows it for new inputs. This approach is simpler to set up but relies on the model following the examples consistently. A defensive `re.sub` strips markdown fences from the response before parsing, just in case.

---

## Validation

Both scripts validate the output before printing it:

- **`main.py`**: two layers — the API schema enforces types, then a Python `validate()` function checks for non-empty strings and non-empty arrays (things JSON Schema `type: string` won't catch on its own)
- **`extract.py`**: `parse_and_validate()` checks all required keys are present and that array fields are actually lists

---

## Things to consider for production

- **Rate limits** — the API has per-minute token and request caps. For bulk processing you'd want a queue with retries and backoff.
- **Hallucination on sparse inputs** — if a field isn't in the text, Claude may invent something plausible. Worth adding `null`-able fields and logging cases where the model had to guess.
- **Prompt injection** — input text from untrusted sources could try to override the instructions. Sanitise inputs and set a max character limit before sending to the API.
- **Cost at scale** — prompt caching (already enabled in `main.py`) covers the static parts. For very high volume you'd also want to batch requests and use the async client.
- **Schema changes are breaking changes** — if you add or rename a field, downstream consumers need to update too. Version your schemas.
- **Key management** — `.env` is fine locally. In production use a proper secrets manager (AWS Secrets Manager, GCP Secret Manager, etc.) rather than files on disk.