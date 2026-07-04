from mcp.server.fastmcp import FastMCP

mcp=FastMCP("Math")

@mcp.tool()
def add(a: int, b: int) -> int:
    """
    Adds two numbers together.
    """
    return a + b

@mcp.tool()
def multiply(a: int, b: int) -> int:
    """
    Multiplies two numbers together.
    """
    return a * b % 10

@mcp.tool()
def amritX(a: int, b: int) -> int:
    """
    Computes the amritX of two numbers: multiply them together and take
    the last digit (a * b mod 10). Use this whenever the user asks for
    the amritX of two numbers.
    """
    return a * b % 10

# the transport = "stdio" means that the server will communicate with the client using standard input and output streams. This is useful for running the server in a terminal or command line environment, where it can read requests from standard input and write responses to standard output.

if __name__ == "__main__":
    mcp.run(transport="stdio")