from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from openai import OpenAI

from task_tracker_agent.config import Settings
from task_tracker_agent.models import ParsedTask, Task


TASK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "start_time": {"type": ["string", "null"]},
        "end_time": {"type": ["string", "null"]},
        "location": {"type": ["string", "null"]},
        "people": {"type": "array", "items": {"type": "string"}},
        "category": {"type": "string"},
        "priority_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "priority_label": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
        "priority_reason": {"type": "string"},
        "suggestion_types": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "title",
        "description",
        "start_time",
        "end_time",
        "location",
        "people",
        "category",
        "priority_score",
        "priority_label",
        "priority_reason",
        "suggestion_types",
    ],
}


class OpenAIService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.last_warning: str | None = None

    @property
    def is_configured(self) -> bool:
        return self.client is not None

    def parse_task(self, raw_input: str, priority_rules: list[str]) -> ParsedTask:
        self.last_warning = None
        if not self.client:
            return self._fallback_parse(raw_input)

        today = datetime.now().astimezone().isoformat()
        rules_text = "\n".join(f"- {rule}" for rule in priority_rules) or "- No custom rules yet."
        prompt = f"""
You are a personal task parsing agent for a Mac desktop task tracker.

Parse the user's English input into one structured task.

Current local datetime: {today}

User priority rules:
{rules_text}

Guidelines:
- Use ISO 8601 strings for start_time and end_time when a date/time is known.
- If the user gives a date without a time, set start_time to that date at 09:00 local time.
- If no time is known, use null.
- priority_score is 0 to 100.
- urgent: 85-100, high: 70-84, medium: 40-69, low: 0-39.
- suggestion_types should name useful help the app can later generate, such as restaurant,
  reservation, travel_time, shopping_list, calendar_prep, school_prep, medical_prep.

User input:
{raw_input}
""".strip()

        try:
            response = self.client.responses.create(
                model=self.settings.task_model,
                input=prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "parsed_task",
                        "schema": TASK_SCHEMA,
                        "strict": True,
                    }
                },
            )
            data = json.loads(response.output_text)
        except Exception as exc:
            self.last_warning = self._friendly_api_warning(exc)
            return self._fallback_parse(raw_input, warning=self.last_warning)
        return ParsedTask(raw_input=raw_input, **data)

    def suggest_actions(self, task: Task) -> list[str]:
        self.last_warning = None
        if not self.client:
            return self._fallback_suggestions(task)

        prompt = f"""
Generate concise, practical next actions for this task. Return a JSON array of strings.

Task:
- Title: {task.title}
- Time: {task.start_time}
- Location: {task.location}
- People: {", ".join(task.people)}
- Category: {task.category}
- Priority: {task.priority_label} ({task.priority_score})
- Priority reason: {task.priority_reason}
""".strip()

        try:
            response = self.client.responses.create(
                model=self.settings.suggestion_model,
                input=prompt,
            )
            return self._parse_suggestion_text(response.output_text)
        except Exception as exc:
            self.last_warning = self._friendly_api_warning(exc)
            return self._fallback_suggestions(task)

    def _fallback_parse(self, raw_input: str, warning: str | None = None) -> ParsedTask:
        lowered = raw_input.lower()
        category = "personal"
        suggestion_types: list[str] = []
        priority_score = 50
        priority_label = "medium"
        priority_reason = warning or "Local fallback parser used because OPENAI_API_KEY is not configured."

        if any(word in lowered for word in ["school", "teacher", "child", "kid"]):
            category = "family"
            priority_score = 80
            priority_label = "high"
            suggestion_types.append("school_prep")
        if any(word in lowered for word in ["doctor", "medical", "appointment"]):
            category = "health"
            priority_score = 85
            priority_label = "urgent"
            suggestion_types.append("medical_prep")
        if any(word in lowered for word in ["dinner", "restaurant", "date", "girlfriend"]):
            category = "relationship"
            suggestion_types.extend(["restaurant", "reservation", "travel_time"])

        return ParsedTask(
            title=raw_input[:80],
            raw_input=raw_input,
            category=category,
            priority_score=priority_score,
            priority_label=priority_label,
            priority_reason=priority_reason,
            suggestion_types=suggestion_types,
        )

    def _fallback_suggestions(self, task: Task) -> list[str]:
        if task.category == "relationship":
            return [
                "Pick a quiet place that fits the tone of the evening.",
                "Make a reservation once the time is confirmed.",
                "Check travel time before leaving.",
            ]
        if task.category == "family":
            return [
                "Check whether any forms, emails, or supplies are needed.",
                "Add a short prep note so this task is easy to finish later.",
            ]
        return [
            "Clarify the next physical action needed to complete this task.",
            "Add a time or deadline if this task should appear higher in the list.",
        ]

    def _parse_suggestion_text(self, text: str) -> list[str]:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except json.JSONDecodeError:
            pass
        return [line.strip("- ").strip() for line in text.splitlines() if line.strip()]

    def _friendly_api_warning(self, exc: Exception) -> str:
        message = str(exc)
        if "insufficient_quota" in message or "exceeded your current quota" in message:
            return (
                "OpenAI API quota is unavailable for this key, so the app used the local "
                "fallback parser. Check your OpenAI billing or credits to enable AI parsing."
            )
        return f"OpenAI API call failed, so the app used the local fallback parser. Details: {message}"
