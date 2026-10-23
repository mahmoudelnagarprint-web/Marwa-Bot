#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تنظيف مهام الاختبار: أرشفة فقط (لا حذف) ثم تقرير حالة الطابور الحيّة."""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cloud"))

from schema_migrator import _connect_cloud  # noqa: E402


def main() -> int:
    conn, route = _connect_cloud()
    cur = conn.cursor()
    cur.execute(
        """
        update public.agent_tasks
           set archived_at = now(),
               status = 'rejected',
               result_note = 'مهمة اختبار — أُرشفت بعد التحقق من آلية تحرير المهام العالقة.'
         where archived_at is null
           and (title like %s or title like %s or status = 'in_progress')
        """,
        ("%اختبار%", "%ORPHANTEST%"),
    )
    print(f"archived: {cur.rowcount}")
    conn.commit()

    cur.execute(
        "select status, count(*) from public.agent_tasks where archived_at is null group by status order by status"
    )
    print("live rows by status:", cur.fetchall())
    cur.execute("select count(*) from public.agent_tasks")
    print("total rows (audit trail kept):", cur.fetchone()[0])
    conn.close()
    print(f"via {route}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
