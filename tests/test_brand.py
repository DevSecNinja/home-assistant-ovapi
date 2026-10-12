"""Packaged artwork served by the actual authenticated Home Assistant brands API."""

import io
import json
import zipfile
from functools import partial
from importlib.metadata import version
from pathlib import Path
from types import ModuleType

from homeassistant.loader import DATA_CUSTOM_COMPONENTS, Integration
from homeassistant.setup import async_setup_component
from PIL import Image

from scripts.check_package import main as build_package


async def test_packaged_brand_api(hass, api, hass_client, hass_ws_client, tmp_path):
    minimum = json.loads(
        await hass.async_add_executor_job(Path("hacs.json").read_text)
    )["homeassistant"]
    archive_path = tmp_path / "ovapi.zip"
    await hass.async_add_executor_job(
        partial(
            build_package,
            profile="minimum" if version("homeassistant") == minimum else "dev",
            destination=archive_path,
        )
    )

    def unpack():
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(tmp_path)
        root = ModuleType("custom_components")
        root.__path__ = [str(tmp_path / "custom_components")]
        return Integration.resolve_from_root(hass, root, "ovapi")

    integration = await hass.async_add_executor_job(unpack)
    assert integration is not None and integration.has_branding
    path = integration.file_path
    hass.data[DATA_CUSTOM_COMPONENTS] = {"ovapi": integration}
    assert await async_setup_component(hass, "brands", {})
    client = await hass_client()
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "brands/access_token"})
    token = (await ws.receive_json())["result"]["token"]
    for dark in ("", "dark_"):
        for kind in ("icon", "logo"):
            for suffix, size in (("", 256), ("@2x", 512)):
                name = f"{dark}{kind}{suffix}.png"
                response = await client.get(
                    f"/api/brands/integration/ovapi/{name}?token={token}"
                )
                assert response.status == 200
                assert response.content_type == "image/png"
                content = await response.read()
                expected = await hass.async_add_executor_job(
                    (path / "brand" / name).read_bytes
                )
                assert content == expected
                with Image.open(io.BytesIO(content)) as image:
                    assert image.size == (
                        size if kind == "icon" else size * 7 // 2,
                        size,
                    )
                    image.verify()
    assert api.call_count == 0
    await ws.close()
