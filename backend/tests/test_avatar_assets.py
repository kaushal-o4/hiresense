# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/tests/test_avatar_assets.py
#
# FILE PURPOSE:
# The browser is only told about a high-detail avatar model when the file really exists (no wasted
# 404).
#
# WHAT THIS FILE DOES:
# 1. Automated test (pytest, mocked AI - no real model needed).
# 2. Contains 4 test(s), e.g.: missing hd model is not advertised; existing hd model is advertised;
#    asset exists rejects unsafe urls; public does not mutate the persona.
# 3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.
#
# IMPORTANT FUNCTIONS:
#    Other helper functions: test_missing_hd_model_is_not_advertised,
#    test_existing_hd_model_is_advertised, test_asset_exists_rejects_unsafe_urls,
#    test_public_does_not_mutate_the_persona
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/services/interview/interviewer_personalities.py
#
# IMPORTANT NOTE:
# Test/tool file: it checks or measures the application and is not used by the running app.
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""The browser is only told about a high-detail avatar model when the file really exists (no wasted 404)."""
from app.services.interview import interviewer_personalities as interviewers


def test_missing_hd_model_is_not_advertised(tmp_path, monkeypatch):
    monkeypatch.setattr(interviewers, "PUBLIC_DIR", tmp_path)
    ui = interviewers.get("aria").public()["ui"]
    assert ui["hd_model"] is None
    assert ui["model"] == "/avatars/interviewer.glb"  # the normal model is always sent


def test_existing_hd_model_is_advertised(tmp_path, monkeypatch):
    monkeypatch.setattr(interviewers, "PUBLIC_DIR", tmp_path)
    (tmp_path / "avatars" / "hd").mkdir(parents=True)
    (tmp_path / "avatars" / "hd" / "victor.glb").write_bytes(b"glTF")
    assert interviewers.get("victor").public()["ui"]["hd_model"] == "/avatars/hd/victor.glb"
    assert interviewers.get("aria").public()["ui"]["hd_model"] is None


def test_asset_exists_rejects_unsafe_urls(tmp_path, monkeypatch):
    monkeypatch.setattr(interviewers, "PUBLIC_DIR", tmp_path)
    assert not interviewers.asset_exists(None)
    assert not interviewers.asset_exists("avatars/x.glb")
    assert not interviewers.asset_exists("/../secret.glb")


def test_public_does_not_mutate_the_persona(tmp_path, monkeypatch):
    monkeypatch.setattr(interviewers, "PUBLIC_DIR", tmp_path)
    interviewers.get("elena").public()
    assert interviewers.get("elena").ui["hd_model"] == "/avatars/hd/elena.glb"
