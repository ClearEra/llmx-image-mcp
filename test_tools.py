"""Offline tests: no API key and no paid requests required."""
import asyncio
import base64
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from mcp import types
import server

PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + struct.pack(">II", 1, 1) + b"\x08\x02\x00\x00\x00")
PAYLOAD = {"data": [{"b64_json": base64.b64encode(PNG).decode()}]}


class ToolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.a = self.root / "a.png"
        self.b = self.root / "b.png"
        self.a.write_bytes(PNG)
        self.b.write_bytes(PNG)
        self.patcher = patch.multiple(server, SAVE_DIR=self.root, SAVE_ROOT=self.root, API_KEY="test")
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    async def call(self, name, **arguments):
        response = await server.handle_call_tool(None, types.CallToolRequestParams(name=name, arguments=arguments))
        return json.loads(response.content[0].text)

    async def test_tools_and_info(self):
        tools = await server.handle_list_tools(None, None)
        self.assertEqual({tool.name for tool in tools.tools}, {"image_generate", "image_edit", "image_batch_edit", "image_multi_reference", "server_info"})
        info = await self.call("server_info")
        self.assertTrue(info["api_key_configured"])
        self.assertNotIn("test", json.dumps(info))

    async def test_generation_and_edit_routes(self):
        mock = AsyncMock(return_value=PAYLOAD)
        with patch.object(server, "_request", mock):
            result = await self.call("image_generate", prompt="a cat", quality="max", model="gpt-image-2.5-flare")
            self.assertTrue(result["ok"])
            self.assertEqual(result["saved"][0]["actual_size"], "1x1")
            self.assertEqual(mock.call_args.args[0], "/v1/images/generations")
            result = await self.call("image_edit", prompt="recolor", image_path=str(self.a))
            self.assertTrue(result["ok"])
            self.assertEqual(mock.call_args.args[0], "/v1/images/edits")
            self.assertEqual(mock.call_args.kwargs["files"][0][0], "image")
            result = await self.call("image_multi_reference", prompt="combine", image_paths=[str(self.a), str(self.b)])
            self.assertTrue(result["ok"])
            self.assertEqual([f[0] for f in mock.call_args.kwargs["files"]], ["image[]", "image[]"])

    async def test_batch_is_serial_and_partial_failure(self):
        mock = AsyncMock(side_effect=[PAYLOAD, ValueError("upstream failure")])
        with patch.object(server, "_request", mock):
            result = await self.call("image_batch_edit", prompt="recolor", image_paths=[str(self.a), str(self.b)])
        self.assertEqual((result["succeeded"], result["failed"], result["concurrency"]), (1, 1, 1))
        self.assertEqual(mock.await_count, 2)

    async def test_validation_before_billing(self):
        mock = AsyncMock(return_value=PAYLOAD)
        with patch.object(server, "_request", mock):
            for name, args in [
                ("image_edit", {"prompt": "x", "image_path": "missing"}),
                ("image_multi_reference", {"prompt": "x", "image_paths": [str(self.a)]}),
                ("image_generate", {"prompt": "x", "n": True}),
                ("image_generate", {"prompt": "x", "size": "999x999"}),
                ("image_generate", {"prompt": "x", "save_dir": "/tmp"}),
                ("image_batch_edit", {"prompt": "x", "image_paths": [str(self.a), "missing"]}),
            ]:
                self.assertFalse((await self.call(name, **args))["ok"])
            mock.assert_not_awaited()

    async def test_response_url_not_fetched(self):
        with patch.object(server, "_request", AsyncMock(return_value={"data": [{"url": "https://example.com/a.png"}]})):
            result = await self.call("image_generate", prompt="x")
        self.assertFalse(result["ok"])
        self.assertIn("b64_json", result["errors"][0])


if __name__ == "__main__":
    unittest.main()
