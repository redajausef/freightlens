import pytest
from test_rules import document

from freightlens.rules import calendar_date, check_documents


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("9/24/2023", "2023-09-24"),
        ("9/25/2023", "2023-09-25"),
        ("24/9/2023", "2023-09-24"),
        ("02/02/2024", "2024-02-02"),
        ("2024-02-29", "2024-02-29"),
    ],
)
def test_unambiguous_dates_preserve_source_values_but_validate(raw, expected):
    assert calendar_date(raw).isoformat() == expected


@pytest.mark.parametrize(
    "raw",
    [
        "02/23/24",
        "02/24/24",
        "03/04/2024",
        "13/14/2024",
        "2/30/2024",
        "2023-02-29",
        "20240223",
        "2/0/2024",
        "02/23/0024 trailing",
    ],
)
def test_dates_never_guess_century_order_or_invalid_calendar_values(raw):
    with pytest.raises(ValueError):
        calendar_date(raw)


def test_slash_date_order_still_blocks_delivery_before_pickup():
    rate = document("rate_confirmation", pickup_date="9/25/2023", delivery_date="9/24/2023")
    codes = {issue.code for issue in check_documents([rate])}
    assert "date_order" in codes
    assert "invalid_date" not in codes
    assert rate.fields["pickup_date"].value == "9/25/2023"
