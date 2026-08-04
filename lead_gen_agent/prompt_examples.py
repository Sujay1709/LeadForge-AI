"""Few-shot examples for converting requests into focused search phrases.

Keeping examples in a separate module makes the agent's behavior easy to
review and expand without burying product knowledge inside ``agents.py``.
"""

QUERY_TRANSFORMATION_EXAMPLES = (
    (
        "Looking for users who need AI video editing software",
        "AI video editing software",
    ),
    (
        "Find SaaS founders who struggle with customer onboarding",
        "SaaS customer onboarding",
    ),
    (
        "Find engineering teams looking for CI/CD pipeline improvements",
        "CI CD pipeline improvements",
    ),
    (
        "AI research papers",
        "recent AI research papers",
    ),
    (
        "List of DS Professors in ASU, USC",
        "data science professors ASU USC",
    ),
    (
        "Find PhD students researching large language models",
        "large language model PhD research",
    ),
    (
        "Find startups building tools for data scientists",
        "data science tools startups",
    ),
    (
        "Find people discussing electric vehicle battery technology",
        "electric vehicle battery technology",
    ),
    (
        "Find professors publishing work on computer vision",
        "computer vision professor research",
    ),
)


def format_query_examples() -> str:
    """Render examples in the format expected by the Gemini prompt."""
    return "\n\n".join(
        f'Input: "{user_input}"\nOutput: {search_phrase}'
        for user_input, search_phrase in QUERY_TRANSFORMATION_EXAMPLES
    )
