"""
Tests for extract.py — covers prompt building and output validation.
API calls are not made here; those require a real key and are tested manually.
"""
import json
import pytest
from extract import build_prompt, parse_and_validate


SAMPLE_1 = (
    "Acme Ltd is a B2B SaaS company that builds workflow automation tools for "
    "logistics teams. Their platform helps mid-sized enterprises reduce manual "
    "admin work by 40%. They primarily serve companies in the UK and Europe. "
    "Key features include analytics dashboards, AI-powered document parsing, "
    "and automated email routing. The company was founded in 2018."
)

SAMPLE_2 = (
    "Beta Inc provides cloud-based compliance software. It works primarily with "
    "financial institutions across North America. The product includes risk scoring, "
    "regulatory monitoring, and automated reporting tools. Customers report up to "
    "30% faster audit preparation times."
)

VALID_OUTPUT = {
    "company_name": "Acme Ltd",
    "industry": "B2B SaaS",
    "target_customer": "Mid-sized logistics enterprises",
    "geography": ["UK", "Europe"],
    "key_features": ["Analytics dashboards", "AI-powered document parsing", "Automated email routing"],
    "value_proposition": "Reduces manual admin work by 40%.",
}


def test_build_prompt_injects_text():
    prompt = build_prompt(SAMPLE_1)
    assert SAMPLE_1.strip() in prompt
    assert "{input_text}" not in prompt


def test_build_prompt_strips_whitespace():
    prompt = build_prompt("  some text  ")
    assert "some text" in prompt
    assert "  some text  " not in prompt


def test_parse_valid_json():
    raw = json.dumps(VALID_OUTPUT)
    result = parse_and_validate(raw)
    assert result["company_name"] == "Acme Ltd"
    assert isinstance(result["geography"], list)
    assert isinstance(result["key_features"], list)


def test_parse_strips_markdown_fences():
    raw = "```json\n" + json.dumps(VALID_OUTPUT) + "\n```"
    result = parse_and_validate(raw)
    assert result["company_name"] == "Acme Ltd"


def test_parse_missing_field_raises():
    bad = {k: v for k, v in VALID_OUTPUT.items() if k != "industry"}
    with pytest.raises(ValueError, match="industry"):
        parse_and_validate(json.dumps(bad))


def test_parse_array_field_wrong_type_raises():
    bad = {**VALID_OUTPUT, "geography": "UK and Europe"}
    with pytest.raises(ValueError, match="geography"):
        parse_and_validate(json.dumps(bad))


def test_parse_invalid_json_raises():
    with pytest.raises(ValueError, match="Invalid JSON"):
        parse_and_validate("not json at all")


if __name__ == "__main__":
    test_build_prompt_injects_text()
    test_build_prompt_strips_whitespace()
    test_parse_valid_json()
    test_parse_strips_markdown_fences()
    test_parse_missing_field_raises()
    test_parse_array_field_wrong_type_raises()
    test_parse_invalid_json_raises()
    print("All tests passed.")