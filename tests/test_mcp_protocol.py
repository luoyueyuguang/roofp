import unittest

import anyio
from mcp import ClientSession

from roofp.mcp_server import mcp


async def protocol_round_trip():
    server_to_client_send, server_to_client_receive = anyio.create_memory_object_stream(0)
    client_to_server_send, client_to_server_receive = anyio.create_memory_object_stream(0)
    initialization_options = mcp._mcp_server.create_initialization_options()

    async with (
        server_to_client_send,
        server_to_client_receive,
        client_to_server_send,
        client_to_server_receive,
        anyio.create_task_group() as task_group,
    ):
        task_group.start_soon(
            mcp._mcp_server.run,
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
        self.assertEqual(tools["generate_roofline"].inputSchema["required"], ["ideal"])
        self.assertIsNotNone(tools["generate_roofline"].outputSchema)
        self.assertNotIn(
            "operators_json",
            tools["generate_roofline"].inputSchema["properties"],
        )

    def test_protocol_returns_structured_content(self) -> None:
        self.assertFalse(self.result.isError)
        self.assertEqual(self.result.structuredContent["schema_version"], "2.0")
        evaluation = self.result.structuredContent["operators"][0]["evaluations"]["ideal"]
        self.assertEqual(evaluation["utilization_ratio"], 0.5)

    def test_protocol_error_is_bounded(self) -> None:
        self.assertTrue(self.invalid.isError)
        message = "".join(getattr(block, "text", "") for block in self.invalid.content)
        self.assertLess(len(message), 5_000)
        self.assertNotIn("sensitive-" * 1_000, message)


if __name__ == "__main__":
    unittest.main()
