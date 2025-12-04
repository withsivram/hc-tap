def test_get_note_not_found(api_client):
    # Should return 404 for non-existent note
    resp = api_client.get("/notes/missing_note_999")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


def test_search_bad_limit(api_client):
    # Should return 400 for invalid limit
    resp = api_client.get("/search?limit=500")
    assert resp.status_code == 400
    assert resp.json()["error"] == "bad_request"


def test_stats_missing_run(api_client):
    # Should return 404 for non-existent run
    resp = api_client.get("/stats/run/INVALID_RUN")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"
