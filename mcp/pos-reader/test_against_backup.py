"""
Read-only integration test for pos-reader against a BACKUP copy of pos_data.db.

Runs the server as a real MCP stdio client (mcp.client.stdio) and calls every tool,
printing numeric results. It never writes anything: the server only opens mode=ro.
"""

import asyncio
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = Path(__file__).resolve().parent / "server.py"
VENV_PY = Path(__file__).resolve().parent / ".venv" / "Scripts" / "python.exe"

BACKUP = Path(r"G:\ai\Naggar Print POS Agent\backup\pos_data_2026-10-10_1128.db")


def rows(res):
    """Decode a call_tool result ListContent into list[dict]."""
    out = []
    for c in res.content:
        if c.type == "text":
            import json

            out.append(json.loads(c.text))
    return out


async def main():
    if not BACKUP.exists():
        print("MISSING BACKUP:", BACKUP)
        sys.exit(2)
    print("Test DB (backup, read-only):", BACKUP)
    print("Server:", SERVER)
    print()

    env = dict(os.environ)
    env["POS_DB_PATH"] = str(BACKUP)

    params = StdioServerParameters(
        command=str(VENV_PY), args=[str(SERVER)], env=env, cwd=str(SERVER.parent)
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print("=== MCP handshake ===")
            print("server:", init.serverInfo)
            print()

            tools = await session.list_tools()
            print("=== tools/list ===")
            print("tool count:", len(tools.tools))
            for t in tools.tools:
                print(f"  - {t.name}: {t.description.splitlines()[0] if t.description else ''}")
            print()

            # 1) clients
            r = await session.call_tool("pos_search_clients", {"query": ""})
            clients = rows(r)
            print("=== 1) pos_search_clients(query='') ===")
            print("total clients returned (LIMIT 100):", len(clients))
            for c in clients[:5]:
                print("   ", c)
            print()

            # search by name
            r = await session.call_tool("pos_search_clients", {"query": "محمد"})
            print("=== pos_search_clients('محمد') ===")
            print("matches:", len(rows(r)))
            for c in rows(r)[:5]:
                print("   ", c)
            print()

            # 2) orders — all
            r = await session.call_tool("pos_search_orders", {})
            orders = rows(r)
            print("=== 2) pos_search_orders() ===")
            print("total orders:", len(orders))
            statuses = {}
            for o in orders:
                statuses[o["status"]] = statuses.get(o["status"], 0) + 1
            print("by status:", statuses)
            print()

            # overdue
            r = await session.call_tool("pos_search_orders", {"overdue": True})
            od = rows(r)
            print("=== pos_search_orders(overdue=True) ===")
            print("overdue count (Under Prep/Ready, delivery < today):", len(od))
            for o in od[:5]:
                print("   ", {k: o[k] for k in ("id", "client_id", "status", "date", "delivery_date", "total_amount")})
            print()

            # date filter sample
            r = await session.call_tool(
                "pos_search_orders", {"date_from": "2026-01-01", "date_to": "2026-10-10"}
            )
            print("=== pos_search_orders(date_from/date_to 2026) ===")
            print("orders in 2026:", len(rows(r)))
            print()

            # 3) products
            r = await session.call_tool("pos_list_products", {})
            prods = rows(r)
            print("=== 3) pos_list_products() ===")
            print("products:", len(prods))
            cats = {}
            for p in prods:
                cats[p["category"]] = cats.get(p["category"], 0) + 1
            print("categories:", cats)
            for p in prods[:4]:
                print("   ", p)
            print()

            # 4) statement for a real client
            if clients:
                cid = clients[0]["id"]
                r = await session.call_tool("pos_get_client_statement", {"client_id": cid})
                res = rows(r)
                st = res[0] if res else {}
                print(f"=== 4) pos_get_client_statement(client_id={cid}) ===")
                print("success:", st.get("success"))
                print("name:", st.get("name"), "| balance:", st.get("balance"))
                print("orders:", len(st.get("orders", [])))
                print("transactions:", len(st.get("transactions", [])))
                print("total_lifetime_paid:", st.get("total_lifetime_paid"))
                print("sum_orders:", st.get("sum_orders"), "| manual_debt:", st.get("manual_debt"))
            print()
            print("ALL TOOLS OK — server read-only, results above.")


if __name__ == "__main__":
    asyncio.run(main())
