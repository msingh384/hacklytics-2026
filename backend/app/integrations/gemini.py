from __future__ import annotations

import json
import re
from typing import Any

from app.config import Settings

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover
    genai = None


_JSON_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)


class GeminiClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = bool(settings.gemini_api_key and genai is not None)
        self.model = None
        if self.enabled:
            genai.configure(api_key=settings.gemini_api_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash")

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = _JSON_RE.search(text)
            if match:
                return json.loads(match.group(1).strip())
        raise ValueError("Gemini response did not contain valid JSON")

    def _generate_json(self, system_prompt: str, user_prompt: str, fallback: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled or not self.model:
            return fallback

        prompt = (
            f"{system_prompt}\n\n"
            "Return only strict JSON. No markdown and no commentary.\n\n"
            f"{user_prompt}"
        )

        try:
            response = self.model.generate_content(prompt)
            raw = response.text if getattr(response, "text", None) else ""
            if not raw:
                return fallback
            return self._extract_json(raw)
        except Exception:
            return fallback

    def generate_plot_package(self, movie_title: str, plot_text: str) -> dict[str, Any]:
        fallback_beats = []
        sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", plot_text) if item.strip()]
        for index, sentence in enumerate(sentences[:6], start=1):
            fallback_beats.append({"order": index, "label": f"Beat {index}", "text": sentence})

        fallback = {
            "expanded_plot": plot_text,
            "beats": fallback_beats,
        }

        system_prompt = "You are a narrative analyst for movie storytelling."
        user_prompt = (
            f"Movie: {movie_title}\n"
            "Create a richer plot expansion and structured beats for downstream story generation.\n"
            "Schema: {\"expanded_plot\": string, \"beats\": [{\"order\": int, \"label\": string, \"text\": string}]}\n"
            "Rules: 5-8 beats, labels concise, text factual, no spoilers outside provided plot.\n"
            f"Plot source:\n{plot_text}"
        )
        payload = self._generate_json(system_prompt, user_prompt, fallback)

        beats = payload.get("beats", [])
        if not isinstance(beats, list) or not beats:
            payload["beats"] = fallback_beats
        return payload

    def label_clusters(self, movie_title: str, cluster_snippets: list[list[str]]) -> list[str]:
        fallback = {
            "labels": [f"Theme {idx + 1}" for idx, _ in enumerate(cluster_snippets)],
        }
        system_prompt = "You are an expert at turning review snippets into concise complaint labels."
        user_prompt = (
            f"Movie: {movie_title}\n"
            "For each cluster, return one short complaint label.\n"
            "Schema: {\"labels\": [string]}\n"
            f"Clusters: {json.dumps(cluster_snippets)}"
        )
        payload = self._generate_json(system_prompt, user_prompt, fallback)
        labels = payload.get("labels", [])
        if not isinstance(labels, list) or len(labels) != len(cluster_snippets):
            return fallback["labels"]
        return [str(label) for label in labels]

    def generate_cluster_taglines(self, clusters: list[dict[str, Any]]) -> list[str]:
        """Generate a 1-3 word tagline for each cluster from its keywords/summary."""
        descriptions = []
        for c in clusters:
            summary = c.get("summary", "")
            keywords = summary.replace("Recurring concerns:", "").strip() if "Recurring concerns:" in summary else summary
            descriptions.append(keywords)
        fallback = {"taglines": [f"Theme {i+1}" for i in range(len(clusters))]}

        system_prompt = "You are a movie critic. You interpret keyword groups and create concise, meaningful labels."
        user_prompt = (
            "Below are keyword groups extracted from movie review complaint clusters.\n"
            "For EACH group, infer what the audience complaint is about and give a 1-3 word label.\n"
            "Examples: \"Weak Villain\", \"Rushed Ending\", \"Plot Holes\", \"Bad CGI\", \"Slow Pacing\", \"Flat Characters\", \"Forced Romance\"\n"
            "Do NOT use generic labels like \"Recurring Concerns\" or \"General Issues\".\n"
            "Each label must be UNIQUE and SPECIFIC.\n"
            f"Return exactly {len(descriptions)} labels.\n"
            "Schema: {\"taglines\": [string, ...]}\n\n"
            + "\n".join(f"Cluster {i+1} keywords: {d}" for i, d in enumerate(descriptions))
        )
        payload = self._generate_json(system_prompt, user_prompt, fallback)
        taglines = payload.get("taglines", [])
        if not isinstance(taglines, list) or len(taglines) != len(clusters):
            return fallback["taglines"]
        return [str(t) for t in taglines]

    def generate_what_if(self, movie_title: str, cluster_labels: list[str], plot_context: str) -> list[str]:
        fallback = [
            f"What if the ending directly resolved '{cluster_labels[0]}'?" if cluster_labels else "What if the ending slowed down for emotional closure?",
            f"What if a key character made a different final choice tied to '{cluster_labels[1]}'?" if len(cluster_labels) > 1 else "What if the protagonist chose sacrifice over victory?",
            f"What if the final act paid off earlier setup tied to '{cluster_labels[2]}'?" if len(cluster_labels) > 2 else "What if the final twist reframed the central conflict?",
        ]
        fallback_payload = {"what_ifs": fallback[:3]}

        system_prompt = "You are a screenwriter generating alternate branching hooks grounded in audience complaints."
        user_prompt = (
            f"Movie: {movie_title}\n"
            f"Complaint labels: {json.dumps(cluster_labels)}\n"
            "Generate exactly 3 what-if suggestions.\n"
            "Schema: {\"what_ifs\": [string, string, string]}\n"
            f"Plot context:\n{plot_context}"
        )
        payload = self._generate_json(system_prompt, user_prompt, fallback_payload)
        what_ifs = payload.get("what_ifs", [])
        if not isinstance(what_ifs, list) or len(what_ifs) < 3:
            return fallback[:3]
        return [str(item) for item in what_ifs[:3]]

    def generate_story_step(
        self,
        movie_title: str,
        what_if: str,
        plot_context: str,
        beats: list[dict[str, Any]],
        step_number: int,
        choice_history: list[str],
        total_steps: int = 3,
    ) -> dict[str, Any]:
        fallback: dict[str, Any]
        if step_number <= total_steps:
            fallback = {
                "narrative": (
                    f"In {movie_title}, the story pivots on: {what_if}. "
                    f"Step {step_number} unfolds with consequences from prior choices: {'; '.join(choice_history) or 'none yet'}."
                ),
                "options": [
                    f"Escalate the conflict in a personal way for step {step_number}.",
                    f"Choose a strategic compromise that addresses audience complaints for step {step_number}.",
                    f"Reveal a hidden truth that re-frames the ending for step {step_number}.",
                ],
            }
        else:
            fallback = {
                "ending": (
                    f"The alternate ending of {movie_title} resolves {what_if.lower()} while reflecting the selected choices: "
                    f"{'; '.join(choice_history)}."
                )
            }

        system_prompt = "You are a movie rewrite engine. Keep narrative under 8 sentences, cinematic but coherent."
        user_prompt = (
            f"Movie: {movie_title}\n"
            f"What-if: {what_if}\n"
            f"Step: {step_number} of {total_steps}.\n"
            f"Choice history: {json.dumps(choice_history)}\n"
            f"Plot context: {plot_context}\n"
            f"Beats: {json.dumps(beats)}\n"
            "If step <= total_steps return schema {\"narrative\": string, \"options\": [string,string,string]}"
            " else return schema {\"ending\": string}."
        )
        payload = self._generate_json(system_prompt, user_prompt, fallback)

        if step_number <= total_steps:
            options = payload.get("options", [])
            narrative = payload.get("narrative")
            if not isinstance(narrative, str) or not isinstance(options, list) or len(options) < 3:
                return fallback
            return {
                "narrative": narrative,
                "options": [str(opt) for opt in options[:3]],
            }

        ending = payload.get("ending")
        if not isinstance(ending, str):
            return fallback
        return {"ending": ending}

    def score_theme_coverage(
        self,
        movie_title: str,
        ending_text: str,
        clusters: list[dict[str, Any]],
    ) -> dict[str, Any]:
        base = max(60, min(95, 65 + len(clusters) * 4))
        fallback = {
            "score_total": base,
            "breakdown": {
                "complaint_coverage": min(100, base + 3),
                "preference_satisfaction": max(50, base - 4),
                "coherence": min(100, base + 1),
            },
            "per_cluster": [
                {
                    "cluster_label": c.get("label", "Unknown"),
                    "addressed": True,
                    "evidence_excerpt": ending_text[:160],
                    "review_reference": c.get("cluster_id", "cluster"),
                }
                for c in clusters
            ],
        }

        system_prompt = "You score alternate endings against complaint clusters."
        user_prompt = (
            f"Movie: {movie_title}\n"
            f"Ending:\n{ending_text}\n"
            f"Clusters: {json.dumps(clusters)}\n"
            "Return schema: {\"score_total\": int, \"breakdown\": {\"complaint_coverage\": int, \"preference_satisfaction\": int, \"coherence\": int}, "
            "\"per_cluster\": [{\"cluster_label\": string, \"addressed\": bool, \"evidence_excerpt\": string, \"review_reference\": string}]}"
        )

        payload = self._generate_json(system_prompt, user_prompt, fallback)
        if not isinstance(payload, dict) or "breakdown" not in payload:
            return fallback
        return payload
