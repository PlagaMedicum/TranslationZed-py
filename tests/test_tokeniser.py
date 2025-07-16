from translationzed_py.core.parser import Kind, _tokenise


def test_tokenise_simple():
    src = b'UI_YES = "Yes"\n'
    kinds = [tok.kind for tok in _tokenise(src)]
    assert kinds == [
        Kind.KEY,
        Kind.TRIVIA,
        Kind.EQUAL,
        Kind.TRIVIA,
        Kind.STRING,
        Kind.NEWLINE,
    ]
