"""Test script for WebSearchTool with DuckDuckGo."""
import asyncio
from nanobot.agent.tools.web import WebSearchTool


async def test_basic_search():
    """Test basic search functionality."""
    print("Testing basic search...")
    tool = WebSearchTool(max_results=5)
    result = await tool.execute("Python programming", count=3)
    print("Result:")
    print(result)
    print("\n" + "="*80 + "\n")


async def test_count_parameter():
    """Test count parameter."""
    print("Testing count parameter with 5 results...")
    tool = WebSearchTool()
    result = await tool.execute("artificial intelligence", count=5)
    print("Result:")
    print(result)
    print("\n" + "="*80 + "\n")


async def test_rare_query():
    """Test rare query that might return fewer results."""
    print("Testing rare query...")
    tool = WebSearchTool()
    result = await tool.execute("xyz123abc456def789ghi")
    print("Result:")
    print(result)
    print("\n" + "="*80 + "\n")


async def main():
    """Run all tests."""
    print("Starting WebSearchTool tests with DuckDuckGo...\n")
    
    try:
        await test_basic_search()
        await test_count_parameter()
        await test_rare_query()
        print("All tests completed!")
    except Exception as e:
        print(f"Error during testing: {e}")


if __name__ == "__main__":
    asyncio.run(main())
