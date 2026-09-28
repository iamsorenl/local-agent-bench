from tools.server import PAGE_CHARS, calculator, clip, read_page


def test_calculator():
    assert calculator("0.175 * 2340") == "409.5"
    assert calculator("-(2 + 3) ** 2") == "-25"
    assert calculator("1 / 0").startswith("error")
    assert calculator("9 ** 9 ** 9").startswith("error")  # would hang without the exponent cap
    assert calculator("__import__('os').system('ls')").startswith("error")
    assert calculator("2 +").startswith("error")


def test_clip_pages_through_long_text():
    text = "x" * (PAGE_CHARS * 2 + 10)
    first = clip(text, 0)
    assert f"offset={PAGE_CHARS}" in first
    last = clip(text, PAGE_CHARS * 2)
    assert last == "x" * 10
    assert clip("short", -5) == "short"
    assert clip("short", 500) == "[end of page]"


def test_read_page_rejects_non_http():
    assert read_page("file:///etc/passwd") == "only http(s) urls are allowed"
