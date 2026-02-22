from __future__ import annotations

import json

from app.integrations.imdb_scraper import _extract_pagination_keys, _parse_reviews


def test_extract_pagination_keys_from_next_data_payload() -> None:
    payload = {
        "props": {
            "pageProps": {
                "contentData": {
                    "data": {
                        "title": {
                            "reviews": {
                                "pageInfo": {
                                    "endCursor": "cursor_abc123xyz",
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    html = f'<html><body><script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script></body></html>'

    keys = _extract_pagination_keys(html)

    assert "cursor_abc123xyz" in keys


def test_parse_reviews_from_legacy_dom_markup() -> None:
    html = """
    <article class="user-review-item">
      <a href="/review/rw1234567/">Outstanding</a>
      <div class="ipc-html-content">This film is deeply engaging with strong pacing and memorable performances.</div>
      <div class="rating-other-user-rating"><span>8</span><span>/10</span></div>
      <div class="display-name-link">cinephile</div>
      <div class="review-date">1 Jan 2025</div>
      <div class="actions">12 out of 15 found this helpful</div>
    </article>
    """

    reviews = _parse_reviews(html)

    assert len(reviews) == 1
    review = reviews[0]
    assert review.review_id == "rw1234567"
    assert review.rating == 8.0
    assert review.author == "cinephile"
    assert review.helpful_count == 12


def test_parse_reviews_from_embedded_json_payload() -> None:
    payload = {
        "props": {
            "pageProps": {
                "reviews": {
                    "edges": [
                        {
                            "node": {
                                "id": "rw7654321",
                                "summary": {"originalText": "Great worldbuilding"},
                                "text": {
                                    "originalText": {
                                        "plainText": "Excellent production design with a strong cast and clear emotional stakes."
                                    }
                                },
                                "authorRating": {"value": 9},
                                "author": {"nickName": "reviewer01"},
                                "submissionDate": "2025-01-15",
                                "reviewUrl": "/review/rw7654321/",
                                "helpfulness": {"upVotes": 42},
                            }
                        }
                    ]
                }
            }
        }
    }
    html = f'<html><body><script type="application/json">{json.dumps(payload)}</script></body></html>'

    reviews = _parse_reviews(html)

    assert len(reviews) == 1
    review = reviews[0]
    assert review.review_id == "rw7654321"
    assert review.rating == 9.0
    assert review.author == "reviewer01"
    assert review.helpful_count == 42
