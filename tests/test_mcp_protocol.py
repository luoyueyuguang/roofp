import unittest

import anyio
from mcp import ClientSession

from roofp.mcp_server import mcp


def _lowlevel_server():
    """The low-level server moves across mcp majors: mcp 1.x FastMCP stores it as
    `_mcp_server`, mcp >= 2.0 MCPServer as `_lowlevel_server`."""
    server = getattr(mcp, "_lowlevel_server", None)
    if server is None:
        server = getattr(mcp, "_mcp_server", None)
    return server


def _field(obj, camel: str, snake: str):
    """mcp 1.x protocol models are camelCase; mcp >= 2.0 exposes the same values
    under snake_case field names. Resolve whichever this mcp version provides."""
    value = getattr(obj, snake, None)
    if value is None:
        value = getattr(obj, camel, None)
    return value


async def protocol_round_trip():
    server_to_client_send, server_to_client_receive = anyio.create_memory_object_stream(0)
    client_to_server_send, client_to_server_receive = anyio.create_memory_object_stream(0)
    lowlevel = _lowlevel_server()
    initialization_options = lowlevel.create_initialization_options()

    async with (
        server_to_client_send,
        server_to_client_receive,
        client_to_server_send,
        client_to_server_receive,
        anyio.create_task_group() as task_group,
    ):
        task_group.start_soon(
            lowlevel.run,
            client_to_server_receive,
            server_to_client_send,
            initialization_options,
        )
        async with ClientSession(
            server_to_client_receive,
            client_to_server_send,
        ) as session:
            await session.initialize()
            tools = await session.list_tools()
            result = await session.call_tool(
                "analyze_performance",
                arguments={
                    "roof": {"label": "Ideal", "compute": 100, "bandwidth": 10},
                    "operators": [{"name": "Op", "compute": 50, "arithmetic_intensity": 10}],
                },
            )
            invalid = await session.call_tool(
                "generate_roofline",
                arguments={
                    "ideal": {
                        "label": "A",
                        "compute": "sensitive-" * 20_000,
                        "bandwidth": 1,
                    }
                },
            )
        task_group.cancel_scope.cancel()
    return tools, result, invalid


class McpProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools, cls.result, cls.invalid = anyio.run(protocol_round_trip)

    def test_protocol_advertises_required_structured_schema(self) -> None:
        tools = {tool.name: tool for tool in self.tools.tools}
        self.assertEqual(
            set(tools),
            {"generate_roofline", "analyze_performance", "compare_rooflines"},
        )
        generate = tools["generate_roofline"]
        self.assertEqual(_field(generate, "inputSchema", "input_schema")["required"], ["ideal"])
        self.assertIsNotNone(_field(generate, "outputSchema", "output_schema"))
        self.assertNotIn(
            "operators_json",
            _field(generate, "inputSchema", "input_schema")["properties"],
        )

    def test_protocol_returns_structured_content(self) -> None:
        self.assertFalse(_field(self.result, "isError", "is_error"))
        structured = _field(self.result, "structuredContent", "structured_content")
        self.assertEqual(structured["schema_version"], "2.0")
        evaluation = structured["operators"][0]["evaluations"]["ideal"]
        self.assertEqual(evaluation["utilization_ratio"], 0.5)

    def test_protocol_error_is_bounded(self) -> None:
        self.assertTrue(_field(self.invalid, "isError", "is_error"))
        message = "".join(getattr(block, "text", "") for block in self.invalid.content)
        self.assertLess(len(message), 5_000)
        self.assertNotIn("sensitive-" * 1_000, message)


if __name__ == "__main__":
    unittest.main()
