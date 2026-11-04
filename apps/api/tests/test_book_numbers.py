"""BOOK-NUMBER-01: a topic whose book misprints its heading number shows the number in sequence and the book's own."""

from portal_api.modules.curriculum.models import Topic

CS11 = "pk-punjab/xi/computer_science/c11-cs"


def book_number(key: str, number: str | None) -> str | None:
    return Topic(natural_key=f"{CS11}/{key}", number=number).book_number


def test_book_number_is_the_printed_number_only_when_it_differs() -> None:
    # Unit 1: the book prints 1.1.1.1 Requirement Gathering where the topic sits at 1.2.2.1, and prints 1.1.1.1 again
    # for Design (natural key "1.1.1.1~2").
    assert book_number("ch1/1.1.1.1", "1.2.2.1") == "1.1.1.1"
    assert book_number("ch1/1.1.1.1~2", "1.2.2.2") == "1.1.1.1"
    assert book_number("ch1/1.2", "1.2") is None
    # Unnumbered headings and exercises have no printed number to show.
    assert book_number("ch9/u-business-plan-tools", "9.2.3") is None
    assert book_number("ch1/u-exercise", None) is None


def test_a_heading_printed_in_another_chapters_numbers_shows_both() -> None:
    # Biology 11 chapter 6 prints Photosynthesis as 5.1 (owner, 2026-11-04: "book ma numbers hain but hamare application
    # ma nahe hain"): students see 6.1 and, beside it, the book's 5.1.
    bio = "pk-punjab/xi/biology/c11-bio"
    assert Topic(natural_key=f"{bio}/ch6/u-photosynthesis-printed-as-5-1", number="6.1").book_number == "5.1"
    assert Topic(natural_key=f"{bio}/ch8/u-vernalisation-printed-as-7-12", number="8.12").book_number == "7.12"
