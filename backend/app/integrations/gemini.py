from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover
    genai = None

# Google Search grounding: legacy SDK uses google_search_retrieval which API rejects.
# Use google-genai package for web search; for now we skip tools.


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
            logger.debug("Gemini disabled or no model; using fallback")
            return fallback

        prompt = (
            f"{system_prompt}\n\n"
            "Return only strict JSON. No markdown and no commentary.\n\n"
            f"{user_prompt}"
        )

        # Skip tools: legacy google-generativeai uses deprecated google_search_retrieval.
        # Migrate to google-genai for Google Search grounding.
        tools = None

        try:
            response = self.model.generate_content(prompt, tools=tools)
            raw = response.text if getattr(response, "text", None) else ""
            if not raw:
                logger.warning("Gemini returned empty response; using fallback")
                return fallback
            logger.debug("Gemini raw response (first 500 chars): %s", (raw[:500] + "...") if len(raw) > 500 else raw)
            payload = self._extract_json(raw)
            logger.debug("Gemini parsed payload keys: %s", list(payload.keys()))
            return payload
        except Exception as e:
            logger.exception("Gemini _generate_json failed: %s", e)
            return fallback

    def generate_plot_package(self, movie_title: str, plot_text: str) -> dict[str, Any]:
        fallback_beats = []
        sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", plot_text) if item.strip()]
        for index, sentence in enumerate(sentences[:6], start=1):
            fallback_beats.append({"order": index, "label": f"Beat {index}", "text": sentence})

        fallback = {
            "expanded_plot": plot_text,
            "beats": fallback_beats,
            "characters": [],
        }

        system_prompt = "You are a narrative analyst for movie storytelling."
        user_prompt = (
            f"Movie: {movie_title}\n\n"
            "Create a richer plot expansion, structured beats, and a character map.\n\n"
            "Schema:\n"
            '{"expanded_plot": string, '
            '"beats": [{"order": int, "label": string, "text": string}], '
            '"characters": [{"name": string, "role": string, "analysis": string}]}\n\n'
            "Rules:\n"
            "- 5-8 beats, labels concise, text factual, no spoilers outside provided plot.\n"
            "- characters: List all important characters. For each: name (as in film), role (e.g. protagonist, antagonist, supporting), "
            "and analysis: exactly 5 sentences describing their character, persona, motivations, and arc.\n"
            f"Plot source:\n{plot_text}"
        )
        payload = self._generate_json(system_prompt, user_prompt, fallback)

        beats = payload.get("beats", [])
        if not isinstance(beats, list) or not beats:
            payload["beats"] = fallback_beats
        if "characters" not in payload or not isinstance(payload["characters"], list):
            payload["characters"] = []
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

    def label_clusters_from_full_reviews(
        self,
        movie_title: str,
        cluster_payloads: list[dict[str, Any]],
    ) -> list[str]:
        """
        Generate one complaint label per cluster from the top 3 full review texts.
        cluster_payloads: [ { "cluster_id", "review_count", "top_reviews": [full, full, full] } ]
        Returns: [ label1, label2, ... ]
        """
        if not cluster_payloads:
            return []
        fallback = {"labels": [f"Theme {i+1}" for i in range(len(cluster_payloads))]}
        system_prompt = (
            "You are an expert at analyzing movie reviews and identifying audience complaints. "
            "Given full review texts for each cluster, infer the main complaint theme and return "
            "one short, specific label (e.g. 'Rushed Ending', 'Weak Villain', 'Plot Holes', 'Confusing Plot'). "
            "Do NOT use generic labels like 'Theme 1' or 'Recurring Concerns'. Each label must be UNIQUE."
        )
        user_prompt = (
            f"Movie: {movie_title}\n\n"
            "For each cluster below, read the top 3 full reviews and return one complaint label.\n"
            "Schema: {\"labels\": [string, ...]}\n\n"
            + "\n".join(
                f"Cluster {i+1} (cluster_id={p.get('cluster_id','')[:12]}..., {p.get('review_count',0)} reviews):\n"
                + "\n---\n".join((p.get("top_reviews") or [])[:3])
                for i, p in enumerate(cluster_payloads)
            )
        )
        payload = self._generate_json(system_prompt, user_prompt, fallback)
        labels = payload.get("labels") or payload.get("cluster_labels") or payload.get("clusterLabels") or []
        if not isinstance(labels, list) or len(labels) != len(cluster_payloads):
            logger.warning(
                "label_clusters_from_full_reviews: invalid labels (expected %d, got %s); using fallback",
                len(cluster_payloads),
                labels[:5] if isinstance(labels, list) else type(labels),
            )
            return fallback["labels"]
        logger.info("label_clusters_from_full_reviews: labels=%s", labels)
        return [str(l) for l in labels]

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

    def extract_entities_relations(
        self, movie_title: str, chunk_text: str, source: str = "script"
    ) -> dict[str, Any]:
        """Extract entities and relations from text for knowledge graph. source: 'script' | 'reviews'."""
        fallback = {"entities": [], "relations": []}
        if source == "reviews":
            system_prompt = (
                "You extract entities and relationships from movie reviews and ratings. "
                "Entity types: CHARACTER (people mentioned), LOCATION, OBJECT, EVENT, ORG, "
                "CONCEPT (aspects like pacing, acting, CGI, plot, ending, dialogue). "
                "Extract what reviewers praise, criticize, or connect. Return strict JSON only."
            )
            user_prompt = (
                f"Movie: {movie_title}\n\n"
                "Extract entities (characters, aspects, concepts, places) and relationships "
                "(praised_for, criticized_for, improves, hurts, related_to, etc.) from this "
                "review/rating excerpt.\n\n"
                'Schema: {"entities": [{"name": string, "type": "CHARACTER"|"LOCATION"|"OBJECT"|"EVENT"|"ORG"|"CONCEPT"}], '
                '"relations": [{"source": string, "target": string, "type": string, "confidence": float}]}\n\n'
                f"Excerpt:\n{chunk_text[:6000]}"
            )
        else:
            system_prompt = (
                "You extract named entities and relationships from movie script text. "
                "Entity types: CHARACTER, LOCATION, OBJECT, EVENT, ORG, CONCEPT. "
                "Return strict JSON only."
            )
            user_prompt = (
                f"Movie: {movie_title}\n\n"
                "Extract entities (people, places, things, events, organizations, concepts) and "
                "relationships between them from this script excerpt.\n\n"
                'Schema: {"entities": [{"name": string, "type": "CHARACTER"|"LOCATION"|"OBJECT"|"EVENT"|"ORG"|"CONCEPT"}], '
                '"relations": [{"source": string, "target": string, "type": string, "confidence": float}]}\n\n'
                f"Script excerpt:\n{chunk_text[:6000]}"
            )
        payload = self._generate_json(system_prompt, user_prompt, fallback)
        entities = payload.get("entities", [])
        relations = payload.get("relations", [])
        if not isinstance(entities, list):
            entities = []
        if not isinstance(relations, list):
            relations = []
        return {"entities": entities, "relations": relations}
