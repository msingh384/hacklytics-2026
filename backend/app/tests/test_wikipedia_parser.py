from app.config import Settings
from app.integrations.wikipedia import WikipediaPlotClient


def test_extract_plot_section_only() -> None:
    client = WikipediaPlotClient(Settings())
    html = '''
    <h2><span id="Plot">Plot</span></h2>
    <p>First plot paragraph.[1]</p>
    <p>Second paragraph.</p>
    <h2><span id="Cast">Cast</span></h2>
    <p>Not part of plot.</p>
    '''

    extracted = client._extract_plot_from_html(html)
    assert extracted == 'First plot paragraph. Second paragraph.'
