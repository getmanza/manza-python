"""Mirror of spec/manza/resources/transfer_drafts_spec.rb: the deprecated alias
of Payments."""

from __future__ import annotations

import warnings

import pytest

from manza import Payments, TransferDrafts
from tests.fixture_ids import FIXTURE_IDS


def test_is_the_payments_resource(make_client):
    manza = make_client([])
    with pytest.warns(DeprecationWarning):
        assert manza.transfer_drafts is manza.payments


def test_keeps_the_class_naming_the_same_class():
    assert TransferDrafts is Payments


def test_warns_with_a_deprecation_warning_pointing_at_payments(make_client):
    manza = make_client([])
    with pytest.warns(DeprecationWarning, match=r"transfer_drafts is deprecated.*payments"):
        _ = manza.transfer_drafts


def test_calls_api_payments(make_client):
    manza = make_client(["payments/get"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        response = manza.transfer_drafts.get(FIXTURE_IDS["MANZA_FIXTURE_TRANSFER_DRAFT_ID"])
    assert isinstance(response.body["id"], str)


def test_assigning_it_replaces_payments(make_client):
    manza = make_client([])
    replacement = Payments(manza)
    with pytest.warns(DeprecationWarning):
        manza.transfer_drafts = replacement
    assert manza.payments is replacement
