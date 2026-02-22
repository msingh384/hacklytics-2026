from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.schemas import LeaderboardItem
from app.utils.text import extract_omdb_scores, normalize_title, stable_id

try:
    from supabase import Client, create_client
except ImportError:  # pragma: no cover
    Client = Any  # type: ignore
    create_client = None


class DataStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client: Client | None = None
        if settings.has_supabase and create_client is not None:
            self.client = create_client(settings.supabase_url, settings.supabase_service_role_key)

        # In-memory fallback mirrors the same logical model as Supabase.
        self.movies: dict[str, dict[str, Any]] = {}
        self.plot_summaries: dict[str, dict[str, Any]] = {}
        self.plot_beats: dict[str, list[dict[str, Any]]] = {}
        self.clusters: dict[str, list[dict[str, Any]]] = {}
        self.cluster_examples: dict[str, list[dict[str, Any]]] = {}
        self.what_ifs: dict[str, list[dict[str, Any]]] = {}
        self.user_reviews: dict[str, list[dict[str, Any]]] = {}
        self.critic_reviews: dict[str, list[dict[str, Any]]] = {}
        self.generations: dict[str, dict[str, Any]] = {}
        self.votes: dict[str, dict[str, int]] = {}

    @property
    def mode(self) -> str:
        return "supabase" if self.client is not None else "memory"

    @staticmethod
    def _iso_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _safe_upsert(self, table: str, rows: list[dict[str, Any]], on_conflict: str | None = None) -> None:
        if not self.client or not rows:
            return
        query = self.client.table(table).upsert(rows, on_conflict=on_conflict) if on_conflict else self.client.table(table).insert(rows)
        query.execute()

    def _safe_insert(self, table: str, rows: list[dict[str, Any]]) -> None:
        if not self.client or not rows:
            return
        self.client.table(table).insert(rows).execute()

    def get_movie(self, movie_id: str) -> dict[str, Any] | None:
        if self.client:
            data = self.client.table("movies").select("*").eq("movie_id", movie_id).limit(1).execute().data or []
            return data[0] if data else None
        return self.movies.get(movie_id)

    def upsert_movie(self, omdb_payload: dict[str, Any]) -> dict[str, Any]:
        movie_id = omdb_payload.get("imdbID") or omdb_payload.get("movie_id")
        if not movie_id:
            raise ValueError("Missing imdbID in OMDB payload")

        imdb_rating, rotten_tomatoes, audience_score = extract_omdb_scores(omdb_payload)
        row = {
            "movie_id": movie_id,
            "title": omdb_payload.get("Title") or omdb_payload.get("title"),
            "year": omdb_payload.get("Year") or omdb_payload.get("year"),
            "genre": omdb_payload.get("Genre") or omdb_payload.get("genre"),
            "poster": None if omdb_payload.get("Poster") == "N/A" else omdb_payload.get("Poster"),
            "imdb_rating": imdb_rating,
            "rotten_tomatoes": rotten_tomatoes,
            "audience_score": audience_score,
            "plot": omdb_payload.get("Plot") or omdb_payload.get("plot"),
            "omdb_payload": omdb_payload,
            "updated_at": self._iso_now(),
        }

        if self.client:
            self._safe_upsert("movies", [row], on_conflict="movie_id")
        self.movies[movie_id] = row
        return row

    def search_movies(self, query: str, limit: int = 25) -> list[dict[str, Any]]:
        """Match movies whose title starts with the query (first-word / prefix match)."""
        if self.client:
            data = (
                self.client.table("movies")
                .select("movie_id,title,year,poster,imdb_rating,rotten_tomatoes,audience_score,genre")
                .ilike("title", f"{query.strip()}%")
                .limit(limit)
                .execute()
                .data
                or []
            )
            return data

        q = normalize_title(query.strip())
        rows = [
            row
            for row in self.movies.values()
            if normalize_title(row.get("title", "")).startswith(q)
        ]
        rows.sort(key=lambda item: (item.get("genre") or "", item.get("title") or ""))
        return rows[:limit]

    def get_featured_movies(self, limit: int = 25) -> list[dict[str, Any]]:
        if self.client:
            rows = (
                self.client.table("movies")
                .select("movie_id,title,year,poster,imdb_rating,rotten_tomatoes,audience_score,genre")
                .order("genre")
                .order("title")
                .limit(limit)
                .execute()
                .data
                or []
            )
            if rows:
                return rows

        rows = list(self.movies.values())
        rows.sort(key=lambda item: ((item.get("genre") or ""), item.get("title") or ""))
        return rows[:limit]

    def get_user_reviews(self, movie_id: str, limit: int = 200) -> list[dict[str, Any]]:
        if self.client:
            rows = (
                self.client.table("user_reviews")
                .select("movie_id,movie_title,movie_review,rating")
                .eq("movie_id", movie_id)
                .limit(limit)
                .execute()
                .data
                or []
            )
            return rows
        return self.user_reviews.get(movie_id, [])[:limit]

    def count_user_reviews(self, movie_id: str) -> int:
        if self.client:
            data = (
                self.client.table("user_reviews")
                .select("movie_id", count="exact")
                .eq("movie_id", movie_id)
                .limit(1)
                .execute()
            )
            return data.count or 0
        return len(self.user_reviews.get(movie_id, []))

    def insert_user_reviews(self, movie_id: str, movie_title: str, reviews: list[dict[str, Any]]) -> int:
        deduped: dict[str, dict[str, Any]] = {}
        for review in reviews:
            text = review.get("movie_review") or review.get("text")
            if not text:
                continue
            dedupe_key = stable_id(movie_id, text[:160])
            deduped[dedupe_key] = {
                "movie_id": movie_id,
                "movie_title": movie_title,
                "movie_review": text,
                "rating": review.get("rating"),
                "review_id": review.get("review_id") or dedupe_key,
            }
        rows = list(deduped.values())
        if not rows:
            return 0

        if self.client:
            try:
                self._safe_upsert("user_reviews", rows, on_conflict="movie_id,review_id")
            except Exception:
                fallback_rows = [
                    {
                        "movie_id": row["movie_id"],
                        "movie_title": row["movie_title"],
                        "movie_review": row["movie_review"],
                        "rating": row["rating"],
                    }
                    for row in rows
                ]
                self._safe_insert("user_reviews", fallback_rows)

        existing = {stable_id(movie_id, item.get("movie_review", "")[:160]): item for item in self.user_reviews.get(movie_id, [])}
        existing.update(deduped)
        self.user_reviews[movie_id] = list(existing.values())
        return len(rows)

    def get_critic_reviews(self, movie_id: str, movie_title: str | None, limit: int = 300) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        if self.client:
            try:
                by_id = (
                    self.client.table("critic_reviews")
                    .select("imdb_id,title,review_content,rating,critic_name")
                    .eq("imdb_id", movie_id)
                    .limit(limit)
                    .execute()
                    .data
                    or []
                )
                collected.extend(by_id)
            except Exception:
                pass

            if movie_title:
                try:
                    by_title = (
                        self.client.table("critic_reviews")
                        .select("imdb_id,title,review_content,rating,critic_name")
                        .ilike("title", f"%{movie_title}%")
                        .limit(limit)
                        .execute()
                        .data
                        or []
                    )
                    collected.extend(by_title)
                except Exception:
                    pass

        deduped: dict[str, dict[str, Any]] = {}
        for row in collected:
            text = row.get("review_content") or row.get("movie_review")
            if not text:
                continue
            key = stable_id(movie_id, text[:180])
            deduped[key] = {
                "movie_id": movie_id,
                "movie_title": row.get("title") or movie_title,
                "movie_review": text,
                "rating": row.get("rating"),
                "critic_name": row.get("critic_name"),
            }

        if movie_id in self.critic_reviews:
            for row in self.critic_reviews[movie_id]:
                text = row.get("movie_review", "")
                deduped[stable_id(movie_id, text[:180])] = row

        rows = list(deduped.values())
        self.critic_reviews[movie_id] = rows
        return rows[:limit]

    def save_plot_summary(self, movie_id: str, plot_text: str, source_page: str | None = None) -> None:
        row = {
            "movie_id": movie_id,
            "plot_text": plot_text,
            "source_page": source_page,
            "updated_at": self._iso_now(),
        }
        if self.client:
            self._safe_upsert("plot_summary", [row], on_conflict="movie_id")
        self.plot_summaries[movie_id] = row

    def get_plot_summary(self, movie_id: str) -> dict[str, Any] | None:
        if self.client:
            rows = self.client.table("plot_summary").select("*").eq("movie_id", movie_id).limit(1).execute().data or []
            if rows:
                return rows[0]
        return self.plot_summaries.get(movie_id)

    def replace_plot_beats(self, movie_id: str, beats: list[dict[str, Any]], expanded_plot: str | None) -> None:
        rows = [
            {
                "movie_id": movie_id,
                "beat_order": beat.get("order"),
                "label": beat.get("label"),
                "beat_text": beat.get("text"),
            }
            for beat in beats
        ]

        if self.client:
            self.client.table("plot_beats").delete().eq("movie_id", movie_id).execute()
            if rows:
                self._safe_insert("plot_beats", rows)
            if expanded_plot:
                self.client.table("movies").update({"expanded_plot": expanded_plot, "updated_at": self._iso_now()}).eq("movie_id", movie_id).execute()

        self.plot_beats[movie_id] = rows
        if movie_id in self.movies and expanded_plot:
            self.movies[movie_id]["expanded_plot"] = expanded_plot

    def get_plot_beats(self, movie_id: str) -> list[dict[str, Any]]:
        if self.client:
            rows = (
                self.client.table("plot_beats")
                .select("movie_id,beat_order,label,beat_text")
                .eq("movie_id", movie_id)
                .order("beat_order")
                .execute()
                .data
                or []
            )
            return rows
        return self.plot_beats.get(movie_id, [])

    def replace_clusters(
        self,
        movie_id: str,
        clusters: list[dict[str, Any]],
        examples: list[dict[str, Any]],
    ) -> None:
        if self.client:
            self.client.table("cluster_examples").delete().eq("movie_id", movie_id).execute()
            self.client.table("complaint_clusters").delete().eq("movie_id", movie_id).execute()
            if clusters:
                self._safe_insert("complaint_clusters", clusters)
            if examples:
                self._safe_insert("cluster_examples", examples)

        self.clusters[movie_id] = clusters
        self.cluster_examples[movie_id] = examples

    def get_clusters(self, movie_id: str) -> list[dict[str, Any]]:
        if self.client:
            rows = (
                self.client.table("complaint_clusters")
                .select("movie_id,cluster_id,label,summary,review_count,tagline")
                .eq("movie_id", movie_id)
                .order("review_count", desc=True)
                .execute()
                .data
                or []
            )
            return rows
        return self.clusters.get(movie_id, [])

    def get_cluster_examples(self, movie_id: str) -> list[dict[str, Any]]:
        if self.client:
            rows = (
                self.client.table("cluster_examples")
                .select("movie_id,cluster_id,example_id,review_text,source,review_reference")
                .eq("movie_id", movie_id)
                .execute()
                .data
                or []
            )
            return rows
        return self.cluster_examples.get(movie_id, [])

    def replace_what_ifs(self, movie_id: str, suggestions: list[dict[str, Any]]) -> None:
        if self.client:
            self.client.table("what_if_suggestions").delete().eq("movie_id", movie_id).execute()
            if suggestions:
                self._safe_insert("what_if_suggestions", suggestions)
        self.what_ifs[movie_id] = suggestions

    def get_what_ifs(self, movie_id: str) -> list[dict[str, Any]]:
        if self.client:
            rows = (
                self.client.table("what_if_suggestions")
                .select("movie_id,suggestion_id,text,linked_cluster_ids")
                .eq("movie_id", movie_id)
                .execute()
                .data
                or []
            )
            return rows
        return self.what_ifs.get(movie_id, [])

    def movie_has_analysis(self, movie_id: str) -> bool:
        """True if this movie has clusters, plot beats, and what-if suggestions (ready to view)."""
        clusters = self.get_clusters(movie_id)
        beats = self.get_plot_beats(movie_id)
        what_ifs = self.get_what_ifs(movie_id)
        return bool(clusters and beats and what_ifs)

    def movies_have_analysis(self, movie_ids: list[str]) -> dict[str, bool]:
        """Batch check: returns dict of movie_id -> has_analysis. Uses 3 queries instead of 3*N."""
        if not movie_ids:
            return {}
        result: dict[str, bool] = {mid: False for mid in movie_ids}
        if not self.client:
            for mid in movie_ids:
                result[mid] = self.movie_has_analysis(mid)
            return result

        ids = [m for m in movie_ids if m]
        if not ids:
            return result

        clusters_by_movie: dict[str, list] = {mid: [] for mid in ids}
        beats_by_movie: dict[str, list] = {mid: [] for mid in ids}
        what_ifs_by_movie: dict[str, list] = {mid: [] for mid in ids}

        try:
            clusters_data = (
                self.client.table("complaint_clusters")
                .select("movie_id")
                .in_("movie_id", ids)
                .execute()
                .data
                or []
            )
            for row in clusters_data:
                mid = row.get("movie_id")
                if mid and mid in clusters_by_movie:
                    clusters_by_movie[mid].append(row)

            beats_data = (
                self.client.table("plot_beats")
                .select("movie_id")
                .in_("movie_id", ids)
                .execute()
                .data
                or []
            )
            for row in beats_data:
                mid = row.get("movie_id")
                if mid and mid in beats_by_movie:
                    beats_by_movie[mid].append(row)

            what_ifs_data = (
                self.client.table("what_if_suggestions")
                .select("movie_id")
                .in_("movie_id", ids)
                .execute()
                .data
                or []
            )
            for row in what_ifs_data:
                mid = row.get("movie_id")
                if mid and mid in what_ifs_by_movie:
                    what_ifs_by_movie[mid].append(row)

            for mid in ids:
                result[mid] = bool(
                    clusters_by_movie[mid] and beats_by_movie[mid] and what_ifs_by_movie[mid]
                )
        except Exception:
            for mid in ids:
                result[mid] = self.movie_has_analysis(mid)
        return result

    def save_generation(
        self,
        *,
        movie_id: str,
        movie_title: str,
        session_id: str,
        story_session_id: str,
        ending_text: str,
        story_payload: dict[str, Any],
        score_payload: dict[str, Any],
    ) -> dict[str, Any]:
        generation_id = stable_id(movie_id, session_id, story_session_id, ending_text[:80], self._iso_now())
        row = {
            "generation_id": generation_id,
            "movie_id": movie_id,
            "movie_title": movie_title,
            "session_id": session_id,
            "story_session_id": story_session_id,
            "ending_text": ending_text,
            "story_payload": story_payload,
            "score_payload": score_payload,
            "score_total": score_payload.get("score_total", 0),
            "votes": 0,
            "created_at": self._iso_now(),
        }
        if self.client:
            self._safe_insert("generations", [row])

        self.generations[generation_id] = row
        return row

    def get_generation(self, generation_id: str) -> dict[str, Any] | None:
        if self.client:
            rows = (
                self.client.table("generations")
                .select("*")
                .eq("generation_id", generation_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                return rows[0]
        return self.generations.get(generation_id)

    def vote_generation(self, generation_id: str, session_id: str, value: int) -> int:
        if generation_id not in self.generations:
            generation = self.get_generation(generation_id)
            if generation:
                self.generations[generation_id] = generation

        if self.client:
            vote_row = {
                "vote_id": stable_id(generation_id, session_id),
                "generation_id": generation_id,
                "session_id": session_id,
                "value": value,
            }
            self._safe_upsert("votes", [vote_row], on_conflict="vote_id")
            all_votes = self.client.table("votes").select("value").eq("generation_id", generation_id).execute().data or []
            total_votes = sum(int(item.get("value", 0)) for item in all_votes)
            self.client.table("generations").update({"votes": total_votes}).eq("generation_id", generation_id).execute()
        else:
            self.votes.setdefault(generation_id, {})[session_id] = value
            total_votes = sum(self.votes[generation_id].values())

        if generation_id in self.generations:
            self.generations[generation_id]["votes"] = total_votes

        return total_votes

    def leaderboard(self, limit: int = 50) -> list[LeaderboardItem]:
        rows: list[dict[str, Any]]
        if self.client:
            rows = (
                self.client.table("generations")
                .select("generation_id,movie_id,movie_title,ending_text,votes,score_total,created_at")
                .order("votes", desc=True)
                .order("created_at", desc=False)
                .limit(limit)
                .execute()
                .data
                or []
            )
        else:
            rows = list(self.generations.values())
            rows.sort(key=lambda item: (item.get("votes", 0), item.get("score_total", 0)), reverse=True)
            rows = rows[:limit]

        out: list[LeaderboardItem] = []
        for row in rows:
            created = row.get("created_at")
            if isinstance(created, str):
                created_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
            else:
                created_at = datetime.now(timezone.utc)
            out.append(
                LeaderboardItem(
                    generation_id=row.get("generation_id"),
                    movie_id=row.get("movie_id"),
                    movie_title=row.get("movie_title") or "Unknown",
                    ending_text=row.get("ending_text") or "",
                    votes=int(row.get("votes", 0)),
                    score_total=int(row.get("score_total", 0)),
                    created_at=created_at,
                )
            )
        return out
