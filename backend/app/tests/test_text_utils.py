from app.utils.text import normalize_title, split_into_review_chunks


def test_normalize_title_removes_special_chars() -> None:
    assert normalize_title('The Dark Knight (2008)!') == 'the dark knight 2008'


def test_split_into_review_chunks_groups_by_three_sentences() -> None:
    text = 'One. Two? Three! Four.'
    chunks = split_into_review_chunks(text, max_sentences=3)
    assert len(chunks) == 2
    assert chunks[0] == 'One. Two? Three!'
    assert chunks[1] == 'Four.'
