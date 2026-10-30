"""Mirror of spec/examples/routing_spec.rb in manza-ruby."""

from __future__ import annotations

import routing


def test_says_the_challenge_went_to_the_authorizer_when_it_is_pending():
    assert "challenge sent" in routing.describe({"status": "pending"})


def test_explains_every_create_time_refusal_reason_in_words():
    expected = {
        "untrusted_payee": "bank details are not trusted",
        "unrestricted_api_key": "key A has no IP allowlist",
        "over_new_payee_limit": "limit per transfer to a new payee",
        "over_transfer_limit": "over the limit per transfer",
        "over_daily_limit": "limit per 24 hours",
        "currency_mismatch": "not the enrolled currency",
        "suspended": "is suspended",
        "secret_expired": "secret has expired",
    }
    assert set(routing.REFUSAL_REASONS) == set(expected)

    for reason, words in expected.items():
        line = routing.describe({"status": "refused", "refusal_reason": reason})
        for part in ("approvers", "refused", reason, words):
            assert part in line


def test_points_at_the_docs_for_a_reason_it_does_not_know():
    line = routing.describe({"status": "refused", "refusal_reason": "something_new"})
    assert "something_new" in line
    assert "transfer authorization docs" in line


def test_says_no_authorizer_was_enrolled_when_there_is_no_authorization():
    assert "no transfer authorizer" in routing.describe(None)
