# Agent Notes

## Host MCP Build/Test Bridge

This repo is edited from inside the Codex container at `/app/space-game`, but
Godot and the Mac-local .NET/Godot toolchain live on the host at
`/Users/kdub/codes/space-game`.

When a build, Godot import, or host validation needs the Mac toolchain, use the
host MCP server instead of trying to run the Mac binaries directly from the
container.

### MCP Connection

The Codex config is in `/app/.codex/config.toml` and should include:

```toml
[mcp_servers.host-build]
url = "http://host.docker.internal:9090"
bearer_token_env_var = "DOCKER_MCP_TOKEN"
```

Inside Docker, `127.0.0.1` is the container. Use
`http://host.docker.internal:9090` to reach the Mac host MCP server.

Expected environment variables:

```sh
DOCKER_MCP_URL=http://host.docker.internal:9090
DOCKER_MCP_TOKEN=<bearer token>
```

### Available Profiles

List profiles with:

```sh
python3 - <<'PY'
import anyio, os
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

async def main():
    headers = {"Authorization": f"Bearer {os.environ['DOCKER_MCP_TOKEN']}"}
    async with streamablehttp_client(os.environ["DOCKER_MCP_URL"], headers=headers, timeout=5, sse_read_timeout=5) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("list_profiles", {})
            for content in result.content:
                print(getattr(content, "text", content))

anyio.run(main)
PY
```

Expected space-game profiles:

- `dotnet build`
- `import godot project`
- `review 0.2.1b host`
- `bootstrap ShuttleA Blender scene` (needed for 0.2.1c once available)
- `validate ShuttleA modeling workflow` (needed for 0.2.1c once available)
- `review 0.2.1c host` (needed for full Blender/Godot review once available)

0.2.1c Blender workflow scripts expect `BLENDER_BIN` to point to the host
Blender executable, for example:

```sh
export BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender
```

The 0.2.1c host profiles should run:

```sh
scripts/bootstrap-shuttle-a-blender.sh
scripts/validate-shuttle-a-modeling-workflow.sh
```

### Starting A Host Job

Use `start_job` with a profile name. Prefer `wait=true` for short jobs and
poll/tail for long jobs.

```sh
python3 - <<'PY'
import anyio, os, json
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

PROFILE = "dotnet build"

async def main():
    headers = {"Authorization": f"Bearer {os.environ['DOCKER_MCP_TOKEN']}"}
    async with streamablehttp_client(os.environ["DOCKER_MCP_URL"], headers=headers, timeout=5, sse_read_timeout=5) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("start_job", {"profile": PROFILE, "wait": True})
            for content in result.content:
                print(getattr(content, "text", content))

anyio.run(main)
PY
```

For long-running jobs, call `start_job` with `wait=false`, then use
`get_job_status` and `tail_job_log`.

### Recommended Validation Order

For changes that affect C# scripts, Godot scenes, imports, or generated
alignment assets:

1. Run local static checks when available, for example
   `scripts/preflight-0.2.1b-static.sh`.
2. Run the host `dotnet build` MCP profile.
3. Run the host `import godot project` MCP profile if imports or scenes changed.
4. Run the host `review 0.2.1b host` MCP profile for the full 0.2.1b evidence
   pass.

Do not assume `/Users/kdub/...` paths or `$GODOT_BIN` are executable from inside
the container. Use the MCP profiles for host execution.
