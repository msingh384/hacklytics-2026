from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.integrations.gemini import GeminiClient
from app.schemas import StoryOption
from app.utils.text import stable_id


@dataclass
class StorySession:
    story_session_id: str
    user_session_id: str
    movie_id: str
    movie_title: str
    what_if: str
    plot_context: str
    beats: list[dict[str, Any]]
    clusters: list[dict[str, Any]]
    current_step: int = 1
    choice_history: list[str] = field(default_factory=list)
    active_options: list[StoryOption] = field(default_factory=list)
    is_complete: bool = False
    ending: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class StoryService:
    def __init__(self, gemini: GeminiClient):
        self.gemini = gemini
        self.sessions: dict[str, StorySession] = {}

    def _wrap_options(self, story_session_id: str, step_number: int, options: list[str]) -> list[StoryOption]:
        wrapped: list[StoryOption] = []
        for idx, text in enumerate(options[:3], start=1):
            wrapped.append(
                StoryOption(
                    option_id=stable_id(story_session_id, str(step_number), str(idx), text[:50]),
                    label=f"Option {idx}",
                    text=text,
                )
            )
        return wrapped

    def start_story(
        self,
        *,
        movie_id: str,
        movie_title: str,
        what_if: str,
        plot_context: str,
        beats: list[dict[str, Any]],
        clusters: list[dict[str, Any]],
        user_session_id: str,
    ) -> tuple[str, str, list[StoryOption], int]:
        story_session_id = stable_id(movie_id, user_session_id, what_if, datetime.now(timezone.utc).isoformat())
        payload = self.gemini.generate_story_step(
            movie_title=movie_title,
            what_if=what_if,
            plot_context=plot_context,
            beats=beats,
            step_number=1,
            choice_history=[],
            total_steps=3,
        )
        narrative = payload.get("narrative", "")
        options = self._wrap_options(story_session_id, 1, payload.get("options", []))

        self.sessions[story_session_id] = StorySession(
            story_session_id=story_session_id,
            user_session_id=user_session_id,
            movie_id=movie_id,
            movie_title=movie_title,
            what_if=what_if,
            plot_context=plot_context,
            beats=beats,
            clusters=clusters,
            current_step=1,
            active_options=options,
        )
        return story_session_id, narrative, options, 1

    def continue_story(
        self,
        *,
        story_session_id: str,
        option_id: str,
        user_session_id: str,
    ) -> dict[str, Any]:
        session = self.sessions.get(story_session_id)
        if not session:
            raise KeyError("Story session not found")
        if session.user_session_id != user_session_id:
            raise PermissionError("Session mismatch")
        if session.is_complete:
            return {
                "step_number": session.current_step,
                "narrative": "Story already completed.",
                "options": [],
                "ending": session.ending,
                "is_complete": True,
            }

        chosen = next((item for item in session.active_options if item.option_id == option_id), None)
        if not chosen:
            raise ValueError("Invalid option_id")
        session.choice_history.append(chosen.text)
        session.updated_at = datetime.now(timezone.utc)

        next_step = session.current_step + 1
        if next_step <= 3:
            payload = self.gemini.generate_story_step(
                movie_title=session.movie_title,
                what_if=session.what_if,
                plot_context=session.plot_context,
                beats=session.beats,
                step_number=next_step,
                choice_history=session.choice_history,
                total_steps=3,
            )
            narrative = payload.get("narrative", "")
            options = self._wrap_options(story_session_id, next_step, payload.get("options", []))
            session.current_step = next_step
            session.active_options = options
            return {
                "step_number": next_step,
                "narrative": narrative,
                "options": options,
                "ending": None,
                "is_complete": False,
            }

        # After the third choice, request ending/wrap-up.
        payload = self.gemini.generate_story_step(
            movie_title=session.movie_title,
            what_if=session.what_if,
            plot_context=session.plot_context,
            beats=session.beats,
            step_number=4,
            choice_history=session.choice_history,
            total_steps=3,
        )
        ending = payload.get("ending", "")
        session.current_step = 4
        session.is_complete = True
        session.active_options = []
        session.ending = ending
        return {
            "step_number": 4,
            "narrative": "Final wrap-up",
            "options": [],
            "ending": ending,
            "is_complete": True,
        }

    def get_story_coverage(self, story_session_id: str, ending_text: str) -> dict[str, Any]:
        session = self.sessions.get(story_session_id)
        if not session:
            raise KeyError("Story session not found")
        return self.gemini.score_theme_coverage(
            movie_title=session.movie_title,
            ending_text=ending_text,
            clusters=session.clusters,
        )
