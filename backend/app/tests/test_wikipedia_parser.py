from unittest.mock import patch

from app.config import Settings
from app.integrations.wikipedia import WikipediaPlotClient


def test_fetch_plot_returns_result_when_scraper_succeeds() -> None:
    client = WikipediaPlotClient(Settings())
    with patch("app.integrations.wikipedia.get_wikipedia_plot") as mock:
        mock.return_value = ("First plot paragraph. Second paragraph.", "Inception (film)")
        result = client.fetch_plot("Inception", "2010")
    assert result is not None
    plot_text, page_title = result
    assert plot_text == "First plot paragraph. Second paragraph."
    assert page_title == "Inception (film)"
    mock.assert_called_once_with("Inception")


def test_fetch_plot_tries_film_suffix_on_direct_failure() -> None:
    client = WikipediaPlotClient(Settings())
    with patch("app.integrations.wikipedia.get_wikipedia_plot") as mock:
        mock.side_effect = [None, ("Plot from film page.", "Inception (film)")]
        result = client.fetch_plot("Inception", "2010")
    assert result is not None
    assert result[0] == "Plot from film page."
    assert mock.call_count == 2
    assert mock.call_args_list[0][0][0] == "Inception"
    assert mock.call_args_list[1][0][0] == "Inception (2010 film)"
