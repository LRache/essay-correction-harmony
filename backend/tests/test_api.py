from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_path=str(tmp_path / "test.db"),
        jwt_secret="test-secret",
        token_ttl_seconds=3600,
        ai_provider="local-nlp",
        ai_base_url="",
        ai_api_key="",
        ai_model="openai-test",
        local_bert_model="model-that-does-not-exist",
        local_model_files_only=True,
    )
    return TestClient(create_app(settings))


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["token"]


def test_student_submit_analyze_and_teacher_review(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    student_token = login(client, "student@example.com", "student123")
    teacher_token = login(client, "teacher@example.com", "teacher123")

    essay_response = client.post(
        "/essays",
        headers={"Authorization": f"Bearer {student_token}"},
        json={
            "prompt_id": "prompt-growth-choice",
            "title": "一次选择",
            "prompt": "请以成长中的一次选择为题写一篇作文。",
            "content": "那天我做出一个重要的的选择。首先我很犹豫，后来我明白成长需要承担责任。",
        },
    )
    assert essay_response.status_code == 200
    essay_id = essay_response.json()["id"]

    job_response = client.post(
        f"/essays/{essay_id}/analysis-jobs",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"provider": "local-nlp"},
    )
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "completed"
    assert job_response.json()["provider"] == "local-nlp"
    assert job_response.json()["model"] == "model-that-does-not-exist"

    report_response = client.get(
        f"/essays/{essay_id}/report",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["essay_id"] == essay_id
    assert report["provider"]["latency_ms"] < 2000
    assert report["grammar_issues"][0]["issue_type"] == "duplicate_particle"

    overview_response = client.get("/reports", headers={"Authorization": f"Bearer {student_token}"})
    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert len(overview) == 1
    assert overview[0]["essay_id"] == essay_id
    assert overview[0]["title"] == "一次选择"
    assert overview[0]["total_score"] == report["total_score"]

    list_response = client.get("/teacher/essays", headers={"Authorization": f"Bearer {teacher_token}"})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    review_response = client.post(
        f"/teacher/essays/{essay_id}/review",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={"score": 88, "comment": "主题明确，建议补充更多细节。", "annotations": ["第二段增加动作描写"]},
    )
    assert review_response.status_code == 200
    assert review_response.json()["score"] == 88


def test_self_assigned_essay_only_creates_student_report(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    student_token = login(client, "student@example.com", "student123")
    teacher_token = login(client, "teacher@example.com", "teacher123")
    student_headers = {"Authorization": f"Bearer {student_token}"}
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

    essay_response = client.post(
        "/essays",
        headers=student_headers,
        json={
            "title": "藏在细节里的温暖",
            "prompt": "请以藏在细节里的温暖为题写一篇记叙文。",
            "content": "清晨母亲把伞塞进我的手里，又蹲下来替我系好鞋带。后来我才明白温暖藏在这些细节里。",
        },
    )
    assert essay_response.status_code == 200
    essay_id = essay_response.json()["id"]
    assert essay_response.json()["prompt_id"] is None

    job_response = client.post(f"/essays/{essay_id}/analysis-jobs", headers=student_headers)
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "completed"

    report_response = client.get(f"/essays/{essay_id}/report", headers=student_headers)
    assert report_response.status_code == 200
    assert report_response.json()["essay_id"] == essay_id

    teacher_list = client.get("/teacher/essays", headers=teacher_headers)
    assert teacher_list.status_code == 200
    assert all(item["essay"]["id"] != essay_id for item in teacher_list.json())

    review_response = client.post(
        f"/teacher/essays/{essay_id}/review",
        headers=teacher_headers,
        json={"score": 88, "comment": "这篇自拟作文不应进入老师批改。", "annotations": []},
    )
    assert review_response.status_code == 404


def test_permissions_and_contract(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    student_token = login(client, "student@example.com", "student123")

    teacher_list = client.get("/teacher/essays", headers={"Authorization": f"Bearer {student_token}"})
    assert teacher_list.status_code == 403

    examples = client.get("/examples", headers={"Authorization": f"Bearer {student_token}"})
    assert examples.status_code == 200
    first = examples.json()[0]
    assert {"id", "title", "prompt", "content", "theme", "highlights"}.issubset(first.keys())


def test_teacher_creates_class_and_student_joins_with_invite_code(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    student_token = login(client, "student@example.com", "student123")
    teacher_token = login(client, "teacher@example.com", "teacher123")
    student_headers = {"Authorization": f"Bearer {student_token}"}
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

    create_response = client.post("/classes", headers=teacher_headers, json={"name": "九年级一班"})
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["name"] == "九年级一班"
    assert len(created["invite_code"]) >= 4
    assert created["student_count"] == 0

    join_response = client.post(
        "/classes/join",
        headers=student_headers,
        json={"invite_code": created["invite_code"].lower()},
    )
    assert join_response.status_code == 200
    joined = join_response.json()
    assert joined["id"] == created["id"]
    assert joined["student_count"] == 1

    student_classes = client.get("/classes", headers=student_headers)
    assert student_classes.status_code == 200
    assert any(item["id"] == created["id"] for item in student_classes.json())

    teacher_classes = client.get("/classes", headers=teacher_headers)
    assert teacher_classes.status_code == 200
    assert any(item["id"] == created["id"] and item["student_count"] == 1 for item in teacher_classes.json())

    students = client.get(f"/classes/{created['id']}/students", headers=teacher_headers)
    assert students.status_code == 200
    assert students.json()[0]["username"] == "student@example.com"


def test_student_report_overviews_can_list_multiple_reports(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    student_token = login(client, "student@example.com", "student123")
    headers = {"Authorization": f"Bearer {student_token}"}

    for title in ["一次选择", "旧伞下的新路"]:
        essay_response = client.post(
            "/essays",
            headers=headers,
            json={
                "title": title,
                "prompt": "请围绕成长写一篇中文作文。",
                "content": f"{title}让我明白了成长需要承担责任。首先我认真观察，后来我开始行动，最后我学会了坚持。",
            },
        )
        assert essay_response.status_code == 200
        essay_id = essay_response.json()["id"]
        job_response = client.post(f"/essays/{essay_id}/analysis-jobs", headers=headers)
        assert job_response.status_code == 200
        assert job_response.json()["status"] == "completed"

    overview_response = client.get("/reports", headers=headers)
    assert overview_response.status_code == 200
    overviews = overview_response.json()
    assert len(overviews) == 2
    titles = {item["title"] for item in overviews}
    assert titles == {"一次选择", "旧伞下的新路"}
    assert all("submitted_at" in item for item in overviews)


def test_teacher_can_create_prompt_and_student_reports_group_by_prompt(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    student_token = login(client, "student@example.com", "student123")
    teacher_token = login(client, "teacher@example.com", "teacher123")
    student_headers = {"Authorization": f"Bearer {student_token}"}
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

    prompt_response = client.post(
        "/teacher/prompts",
        headers=teacher_headers,
        json={"title": "校园里的温暖", "prompt": "请围绕校园生活中的温暖瞬间写一篇记叙文。"},
    )
    assert prompt_response.status_code == 200
    writing_prompt = prompt_response.json()

    prompts_response = client.get("/writing-prompts", headers=student_headers)
    assert prompts_response.status_code == 200
    assert any(item["id"] == writing_prompt["id"] for item in prompts_response.json())

    essay_response = client.post(
        "/essays",
        headers=student_headers,
        json={
            "prompt_id": writing_prompt["id"],
            "title": "会被题库覆盖",
            "prompt": "会被题库覆盖",
            "content": "那天老师把伞递给我，我看见校园里的温暖。首先我有些意外，后来我明白善意会被记住。",
        },
    )
    assert essay_response.status_code == 200
    essay = essay_response.json()
    assert essay["prompt_id"] == writing_prompt["id"]
    assert essay["title"] == "校园里的温暖"

    job_response = client.post(f"/essays/{essay['id']}/analysis-jobs", headers=student_headers)
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "completed"

    overview_response = client.get("/reports", headers=student_headers)
    assert overview_response.status_code == 200
    overview = overview_response.json()[0]
    assert overview["prompt_id"] == writing_prompt["id"]
    assert overview["prompt_title"] == "校园里的温暖"
