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

## Prompt design

### System prompt (used in `main.py`)

```
You are a precise business analyst. Extract structured company profile
information from the provided text.

Field instructions:
- company_name: The company's formal name as stated.
- industry: A concise category (e.g. "B2B SaaS", "Cloud Software", "FinTech").
- target_customer: Primary customer type and segment in one sentence.
- geography: Each region or market as a separate list item. Never merge multiple
  regions into one string (e.g. return ["UK", "Europe"] not ["UK and Europe"]).
- key_features: Each distinct product feature as a separate list item.
- value_proposition: One sentence covering the core benefit, including any
  quantified outcome stated in the text.

Extract only what's in the text. Don't add outside knowledge.
```

Why each part is there:

- **Role framing** ("precise business analyst") — steers Claude away from conversational responses and toward terse, analytical ones.
- **Per-field instructions** — fields like `industry` and `value_proposition` are interpretive. Without a definition, the model gives inconsistently granular answers across different inputs.
- **Explicit array split rule for `geography`** — without this, Claude often returns `["UK and Europe"]` as one string instead of two separate items. The instruction directly prevents that.
- **"Don't add outside knowledge"** — stops Claude from filling in fields it can't find in the text with plausible-sounding guesses.
- **No JSON format instructions in the prompt** — structure is handled entirely by the tool schema. Duplicating it in the prompt risks conflicting signals.

The user message is just the raw input text — no extra wrapping needed since the system prompt sets all the context.

### Few-shot prompt (used in `extract.py`)

`extract.py` uses a different strategy: instead of a tool schema, the prompt shows Claude two complete input/output examples. Claude infers the expected format from the pattern. Simpler to set up, slightly less strict — the response is raw text so it gets run through markdown fence stripping and field checks before use.

```
System prompt  →  tells Claude HOW to interpret each field
Tool schema    →  tells the API WHAT shape the output must be
```

---

## Validation

Both scripts validate the output before printing it:

- **`main.py`**: two layers — the API schema enforces types, then a Python `validate()` function checks for non-empty strings and non-empty arrays (things JSON Schema `type: string` won't catch on its own)
- **`extract.py`**: `parse_and_validate()` checks all required keys are present and that array fields are actually lists

---

## How it would work in production

In production this becomes a small extraction service sitting between raw data ingestion and a structured database. The flow looks roughly like this:

```
Raw text input (CRM webhook, file upload, API call)
        ↓
Input validation + length check (reject anything malformed or too long)
        ↓
Claude API call with tool use schema
        ↓
Output validation (field presence, types)
        ↓
Store to database / pass to downstream service
```

A few things that would change vs the current script:

**Async + queuing** — the script processes texts one at a time. In production you'd push jobs onto a queue (SQS, RabbitMQ, etc.) and use the async Claude client (`AsyncAnthropic`) to run multiple extractions concurrently within rate limits.

**Prompt caching** — already enabled here. At volume it cuts input token costs by 80–90% for the static parts (system prompt + tool definition) since they're identical across every request.

**Retries with backoff** — the API has per-minute rate limits. A production client wraps calls in exponential backoff, not a hard exit like `sys.exit(1)`.

**Observability** — structured logging per request (input hash, model used, token counts, latency, cache hit/miss). Alerts on error rate spikes or unexpected field values.

**Schema versioning** — the tool schema is a contract. Any field change is a breaking change for downstream consumers. Version it (`extract_company_profile_v2`) and migrate consumers explicitly rather than changing in place.

**Secrets management** — `.env` is fine locally, but in production the API key lives in a secrets manager (AWS Secrets Manager, GCP Secret Manager, Vault) and is injected at runtime, never in files or environment variables on the host.

**Hallucination handling** — if a field isn't mentioned in the input, Claude may invent a plausible value. Production pipelines should make fields optional (nullable), log confidence signals, or run a post-extraction check that cross-references values against the original text.

**Prompt injection** — untrusted text inputs could attempt to override the system prompt. Sanitise inputs, enforce a max character limit, and monitor for outputs that don't match expected patterns.