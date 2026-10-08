"""Raw LLM call for answer generation (same pattern as projects 1-2)."""
from . import config
from . import costs


def ask(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> dict:
    resp = config.get_client().chat.completions.create(
        model=config.MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
    usage = resp.usage
    return {
        "answer": resp.choices[0].message.content,
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "cost_usd": costs.estimate_cost(usage.prompt_tokens, usage.completion_tokens),
    }
