from src.services.payload_service import PayloadNotFoundError

VALID_BODY = {"list_1": ["a", "b"], "list_2": ["c", "d"]}


async def test_create_payload_returns_id(client, service):
    service.create_payload.return_value = "abc123"

    response = await client.post("/payload", json=VALID_BODY)

    assert response.status_code == 200
    assert response.json() == {"id": "abc123"}  # adjust to your CreatePayloadResponse fields
    service.create_payload.assert_awaited_once_with(["a", "b"], ["c", "d"])


async def test_create_payload_rejects_unequal_lists(client, service):
    body = {"list_1": ["a"], "list_2": ["b", "c"]}

    response = await client.post("/payload", json=body)

    assert response.status_code == 422
    service.create_payload.assert_not_awaited()


async def test_create_payload_rejects_missing_field(client):
    response = await client.post("/payload", json={"list_1": ["a"]})

    assert response.status_code == 422


async def test_get_payload_returns_output(client, service):
    service.get_payload.return_value = "A, B"

    response = await client.get("/payload/abc123")

    assert response.status_code == 200
    assert response.json() == {"output": "A, B"}


async def test_get_payload_returns_404_when_missing(client, service):
    service.get_payload.side_effect = PayloadNotFoundError("nope")

    response = await client.get("/payload/nope")

    assert response.status_code == 404