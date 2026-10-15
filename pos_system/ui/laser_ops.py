import datetime
from typing import Any

import flet as ft
import requests

from src.production_engine import (
    ASSEMBLY_WORKSTATION,
    LASER_WORKSTATION,
    PHOTO_WORKSTATION,
    SUBLIMATION_WORKSTATION,
    UNCATEGORIZED_WORKSTATION,
)


API_BASE_URL = "http://127.0.0.1:7777/api"
ICON_SET = getattr(ft, "icons", None) or getattr(ft, "Icons", None)


def _icon(name: str):
    return getattr(ICON_SET, name, None)


WORKSTATION_OPTIONS = [
    LASER_WORKSTATION,
    SUBLIMATION_WORKSTATION,
    PHOTO_WORKSTATION,
    ASSEMBLY_WORKSTATION,
    UNCATEGORIZED_WORKSTATION,
]
MATERIAL_OPTIONS = [
    "أكريليك",
    "أكريليك - شفاف",
    "أكريليك - مراية",
    "خشب",
    "خشب - هافان",
    "خشب - بني",
    "خشب - دهبي",
    "خشب - فضي",
    "جلد",
    "غير محدد",
]


def _parse_date(value: str | None) -> datetime.date | None:
    if not value:
        return None
    raw = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.datetime.fromisoformat(raw.replace("Z", "")).date()
    except ValueError:
        return None


def main(page: ft.Page):
    page.title = "Laser Ops Center MES"
    page.rtl = True
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#08111f"
    page.padding = 20
    page.window_width = 1500
    page.window_height = 920
    page.scroll = ft.ScrollMode.AUTO

    board_ref = ft.Ref[ft.Column]()
    status_ref = ft.Ref[ft.Text]()

    def notify(message: str, ok: bool = True):
        page.snack_bar = ft.SnackBar(
            ft.Text(message, color="white"),
            bgcolor="#15803D" if ok else "#B91C1C",
        )
        page.snack_bar.open = True
        page.update()

    def render_badges(item: dict[str, Any]) -> list[ft.Control]:
        badges: list[ft.Control] = []
        if item.get("is_urgent"):
            label = "🚨 عاجل"
            if item.get("is_overdue"):
                label = "🚨 متأخر"
            badges.append(_badge(label, "#7F1D1D", "#FCA5A5"))
        if item.get("is_scrap_friendly"):
            badges.append(_badge("♻️ استخدم قصاقيص", "#14532D", "#86EFAC"))
        if item.get("source") == "memory":
            badges.append(_badge("🧠 متعلم", "#1E3A8A", "#93C5FD"))
        return badges

    def _badge(text: str, bgcolor: str, color: str) -> ft.Control:
        return ft.Container(
            content=ft.Text(text, size=11, weight=ft.FontWeight.W_700, color=color),
            bgcolor=bgcolor,
            padding=ft.padding.symmetric(horizontal=10, vertical=5),
            border_radius=999,
        )

    def save_rule(product_name: str, workstation_dd: ft.Dropdown, material_dd: ft.Dropdown, scrap_cb: ft.Checkbox):
        workstation = workstation_dd.value or UNCATEGORIZED_WORKSTATION
        material = material_dd.value or "غير محدد"
        try:
            response = requests.post(
                f"{API_BASE_URL}/product_routing_rules",
                json={
                    "product_name": product_name,
                    "workstation": workstation,
                    "material": material,
                    "is_scrap_friendly": bool(scrap_cb.value),
                },
                timeout=20,
            )
            payload = response.json()
            if response.status_code != 200 or not payload.get("success"):
                raise RuntimeError(payload.get("message", f"HTTP {response.status_code}"))
            notify(f"تم حفظ قاعدة التصنيف لـ {product_name}")
            load_board()
        except Exception as exc:
            notify(f"فشل حفظ القاعدة: {exc}", ok=False)

    def make_uncategorized_resolver(item: dict[str, Any]) -> ft.Control:
        workstation_dd = ft.Dropdown(
            value=LASER_WORKSTATION,
            options=[ft.dropdown.Option(value=name, text=name) for name in WORKSTATION_OPTIONS],
            dense=True,
            filled=True,
            bgcolor="#0F172A",
        )
        material_dd = ft.Dropdown(
            value=item.get("material") or "غير محدد",
            options=[ft.dropdown.Option(value=name, text=name) for name in MATERIAL_OPTIONS],
            dense=True,
            filled=True,
            bgcolor="#0F172A",
        )
        scrap_cb = ft.Checkbox(
            label="♻️ قصاقيص",
            value=bool(item.get("is_scrap_friendly")),
            check_color="#000000",
            fill_color="#4ADE80",
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("حلّ التصنيف", size=13, weight=ft.FontWeight.W_700, color="#FCD34D"),
                    workstation_dd,
                    material_dd,
                    scrap_cb,
                    ft.ElevatedButton(
                        text="Save Rule",
                        icon=_icon("SAVE"),
                        on_click=lambda _: save_rule(item["product_name"], workstation_dd, material_dd, scrap_cb),
                        style=ft.ButtonStyle(
                            bgcolor="#2563EB",
                            color="white",
                            shape=ft.RoundedRectangleBorder(radius=12),
                        ),
                    ),
                ],
                spacing=8,
            ),
            bgcolor="#111827",
            padding=12,
            border_radius=14,
        )

    def make_item_card(item: dict[str, Any], workstation: str) -> ft.Control:
        notes = item.get("custom_notes") or []
        border_color = "#EF4444" if item.get("is_urgent") else "#1E293B"
        glow = ft.BoxShadow(
            spread_radius=0,
            blur_radius=18,
            color="#7F1D1D" if item.get("is_urgent") else "#00000000",
            offset=ft.Offset(0, 0),
        )

        controls: list[ft.Control] = [
            ft.Row(
                [
                    ft.Text(item.get("display_name") or item["product_name"], size=16, weight=ft.FontWeight.BOLD, expand=True),
                    ft.Container(
                        content=ft.Text(str(item.get("total_qty", 0)), size=16, weight=ft.FontWeight.BOLD, color="white"),
                        bgcolor="#DC2626" if item.get("is_urgent") else "#2563EB",
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        border_radius=14,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Row(render_badges(item), wrap=True, spacing=8),
            ft.Text(f"الخامة: {item.get('material', 'غير محدد')}", color="#CBD5E1", size=12),
            ft.Text(f"عدد الطلبات: {item.get('order_count', 0)}", color="#94A3B8", size=12),
            ft.Text(f"تاريخ التسليم: {item.get('delivery_date') or 'غير محدد'}", color="#FCA5A5" if item.get("is_urgent") else "#94A3B8", size=12),
        ]

        if notes:
            controls.append(ft.Text("📝 " + " | ".join(notes), size=13, weight=ft.FontWeight.BOLD, color="#F8FAFC"))

        if workstation == UNCATEGORIZED_WORKSTATION:
            controls.append(make_uncategorized_resolver(item))

        return ft.Container(
            content=ft.Column(controls, spacing=10),
            bgcolor="#0F172A",
            padding=16,
            border_radius=18,
            border=ft.border.all(2, border_color),
            shadow=glow,
        )

    def make_material_section(material_group: dict[str, Any], workstation: str) -> ft.Control:
        item_cards = [make_item_card(item, workstation) for item in material_group.get("items", [])]
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(material_group["material"], size=17, weight=ft.FontWeight.BOLD, expand=True),
                            ft.Text(f"إجمالي: {material_group.get('total_qty', 0)}", size=13, color="#94A3B8"),
                        ]
                    ),
                    ft.Column(item_cards, spacing=12),
                ],
                spacing=12,
            ),
            bgcolor="#111827",
            padding=16,
            border_radius=18,
        )

    def make_workstation_tab(column: dict[str, Any]) -> ft.Tab:
        materials = column.get("materials", [])
        if not materials:
            content = ft.Container(
                content=ft.Text("لا توجد عناصر في هذه المحطة", color="#94A3B8"),
                padding=20,
            )
        else:
            content = ft.Container(
                content=ft.Column(
                    [make_material_section(material, column["workstation"]) for material in materials],
                    scroll=ft.ScrollMode.AUTO,
                    spacing=14,
                ),
                expand=True,
            )

        label = f"{column['workstation']} ({column.get('total_qty', 0)})"
        return ft.Tab(text=label, content=content)

    def render_board(payload: dict[str, Any]):
        board = payload.get("board", [])
        stats = payload.get("stats", {})
        tabs = [make_workstation_tab(column) for column in board]
        if not tabs:
            board_ref.current.controls = [ft.Text("لا توجد طلبات تحت التجهيز حالياً", color="#86EFAC", size=16)]
        else:
            board_ref.current.controls = [
                ft.Row(
                    [
                        _stat_card("الطلبات النشطة", stats.get("under_preparation_items", 0), "#1D4ED8"),
                        _stat_card("المحطات", stats.get("workstation_count", 0), "#7C3AED"),
                        _stat_card("غير مصنف", stats.get("uncategorized_count", 0), "#B45309"),
                    ],
                    wrap=True,
                    spacing=12,
                ),
                ft.Container(
                    content=ft.Tabs(
                        tabs=tabs,
                        selected_index=0,
                        expand=True,
                        divider_color="#1E293B",
                        indicator_color="#38BDF8",
                        label_color="#F8FAFC",
                        unselected_label_color="#94A3B8",
                        animation_duration=200,
                    ),
                    expand=True,
                ),
            ]

        status_ref.current.value = f"آخر تحديث: {datetime.datetime.now().strftime('%H:%M:%S')}"
        page.update()

    def _stat_card(label: str, value: Any, accent: str) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(label, color="#94A3B8", size=12),
                    ft.Text(str(value), size=26, weight=ft.FontWeight.BOLD, color="white"),
                ],
                spacing=4,
            ),
            bgcolor="#0F172A",
            border=ft.border.all(1, accent),
            border_radius=18,
            padding=16,
            width=190,
        )

    def load_board():
        status_ref.current.value = "جاري تحميل لوحة التشغيل..."
        page.update()
        try:
            response = requests.get(f"{API_BASE_URL}/laser_ops_board", timeout=20)
            payload = response.json()
            if response.status_code != 200 or not payload.get("success"):
                raise RuntimeError(payload.get("message", f"HTTP {response.status_code}"))
            render_board(payload)
        except Exception as exc:
            board_ref.current.controls = [ft.Text(f"تعذر تحميل اللوحة: {exc}", color="#FCA5A5")]
            status_ref.current.value = "فشل التحميل"
            page.update()

    header = ft.Row(
        [
            ft.Column(
                [
                    ft.Text("Laser Ops Center", size=28, weight=ft.FontWeight.BOLD),
                    ft.Text("Self-learning Kanban Routing Board", color="#94A3B8"),
                ],
                spacing=2,
            ),
            ft.Row(
                [
                    ft.ElevatedButton(
                        text="تحديث",
                        icon=_icon("REFRESH"),
                        on_click=lambda _: load_board(),
                        style=ft.ButtonStyle(bgcolor="#0EA5E9", color="white"),
                    ),
                    ft.Text(ref=status_ref, value="...", color="#94A3B8"),
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    page.add(
        header,
        ft.Container(
            content=ft.Column(ref=board_ref, expand=True, spacing=16),
            expand=True,
            padding=ft.padding.only(top=16),
        ),
    )
    load_board()


if __name__ == "__main__":
    ft.app(target=main)
