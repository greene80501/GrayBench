"""Standard text-token price estimates, USD per million tokens.

Google 2.5 and OpenAI mini pilot rates verified 2026-09-13; other legacy
rates require revalidation before interpreting costs as current. No fallback
price is assigned to an unknown model. These estimates are not invoices.
"""

PRICING = {
    "openai": {
        "gpt-5.2": {"input": 1.75, "output": 14.0, "cached": 0.17500000000000002},
        "gpt-5.2-pro": {"input": 21.0, "output": 168.0, "cached": 2.1},
        "gpt-5.1": {"input": 1.25, "output": 10.0, "cached": 0.125},
        "gpt-5-mini": {"input": 0.25, "output": 2.0, "cached": 0.025},
        "gpt-5-nano": {"input": 0.05, "output": 0.4, "cached": 0.005000000000000001},
        "gpt-4.1": {"input": 2.0, "output": 8.0, "cached": 0.5},
        "gpt-4.1-mini": {"input": 0.4, "output": 1.6, "cached": 0.1},
        "gpt-4.1-nano": {"input": 0.1, "output": 0.4, "cached": 0.025},
        "gpt-4o": {"input": 2.5, "output": 10.0, "cached": 1.25},
        "gpt-4o-mini": {"input": 0.15, "output": 0.6, "cached": 0.075},
        "o3": {"input": 2.0, "output": 8.0, "cached": 0.5},
        "o3-pro": {"input": 20.0, "output": 80.0, "cached": 10.0},
        "o4-mini": {"input": 1.1, "output": 4.4, "cached": 0.55},
        "o1": {"input": 15.0, "output": 60.0, "cached": 7.5},
        "o1-mini": {"input": 1.1, "output": 4.4, "cached": 0.55},
        "o1-pro": {"input": 150.0, "output": 600.0, "cached": 75.0},
    },
    "anthropic": {
        "claude-opus-4-5-20251101": {"input": 5.0, "output": 25.0},
        "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0},
        "claude-opus-4-1-20250805": {"input": 15.0, "output": 75.0},
        "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
        "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    },
    "google": {
        "gemini-3.6-flash": {"input": 0.75, "cached": 0.075, "output": 3.75},
        "gemini-2.5-pro": {
            "input": 1.25,
            "cached": 0.125,
            "output": 10.0,
            "input_high": 2.5,
            "cached_high": 0.25,
            "output_high": 15.0,
        },
        "gemini-2.5-flash": {"input": 0.3, "cached": 0.03, "output": 2.5},
        "gemini-2.5-flash-lite": {"input": 0.1, "cached": 0.01, "output": 0.4},
    },
    "deepseek": {
        "deepseek-chat": {"input": 0.28, "output": 0.42},
        "deepseek-reasoner": {"input": 0.28, "output": 0.42},
    },
    "moonshot": {
        "kimi-k2.5": {"input": 0.6, "output": 3.0},
        "kimi-k2-thinking": {"input": 0.6, "output": 2.5},
        "kimi-k2-turbo-preview": {"input": 1.15, "output": 8.0},
    },
    "graygate": {},
}
