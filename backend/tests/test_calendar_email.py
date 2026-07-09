"""Calendar link extraction, auto-join dedup logic, and email recap rendering."""

from app.services.calendar import extract_meeting_link


def test_extract_google_meet_hangout_link():
    assert extract_meeting_link({"hangoutLink": "https://meet.google.com/abc-defg-hij"}) == (
        "https://meet.google.com/abc-defg-hij"
    )


def test_extract_from_conference_data():
    event = {
        "conferenceData": {
            "entryPoints": [
                {"entryPointType": "more", "uri": "https://x"},
                {"entryPointType": "video", "uri": "https://meet.google.com/xyz-abcd-efg"},
            ]
        }
    }
    assert extract_meeting_link(event) == "https://meet.google.com/xyz-abcd-efg"


def test_extract_zoom_from_location():
    event = {"location": "Join Zoom: https://us02web.zoom.us/j/8412345678?pwd=aBcD"}
    assert extract_meeting_link(event).startswith("https://us02web.zoom.us/j/8412345678")


def test_extract_teams_from_description():
    event = {"description": "Agenda...\nhttps://teams.microsoft.com/l/meetup-join/19%3ameeting_abc"}
    link = extract_meeting_link(event)
    assert link and link.startswith("https://teams.microsoft.com/l/meetup-join/")


def test_no_link_returns_none():
    assert extract_meeting_link({"summary": "Lunch", "location": "Cafe"}) is None


def test_calendar_status_dev_mode(client):
    # In dev mode (no Google auth) calendar reports "connected" so the UI shows it
    body = client.get("/api/calendar/status").json()
    assert body["auto_join"] == "none"
    assert body["connected"] is True

    updated = client.put("/api/calendar/auto-join", json={"auto_join": "video"}).json()
    assert updated["auto_join"] == "video"

    bad = client.put("/api/calendar/auto-join", json={"auto_join": "always"})
    assert bad.status_code == 400


def test_email_recap_renders_without_smtp(caplog):
    """With no SMTP configured, send_recap logs the recap instead of raising."""
    import logging

    from app.database import Base, SessionLocal, engine, run_sqlite_auto_migrations
    from app.models import Meeting, Summary, User
    from app.services.email_recap import send_recap

    Base.metadata.create_all(bind=engine)
    run_sqlite_auto_migrations()

    db = SessionLocal()
    try:
        user = User(email="organizer@example.com", name="Org")
        db.add(user)
        db.flush()
        meeting = Meeting(title="Recap test", status="completed", created_by=user.id)
        db.add(meeting)
        db.flush()
        db.add(
            Summary(
                meeting_id=meeting.id,
                overview_en="We discussed the roadmap.",
                overview_ta="நாங்கள் திட்டவரைபடத்தை பற்றி பேசினோம்.",
                action_items=[{"task": "Ship v1", "owner": "Priya", "due": "Friday"}],
                decisions=["Use Redis"],
            )
        )
        db.commit()
        mid = meeting.id
    finally:
        db.close()

    with caplog.at_level(logging.INFO, logger="neu.email"):
        send_recap(mid)
    assert any("Email recap" in r.message or "Recap" in r.message for r in caplog.records)
