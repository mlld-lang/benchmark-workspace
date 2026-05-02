"""Entrypoint: `python -m agentdojo_mcp <config>`.

Exists so the module is invokable without naming the file. Equivalent to
running `server.py` directly.
"""

from server import main

if __name__ == "__main__":
    main()
