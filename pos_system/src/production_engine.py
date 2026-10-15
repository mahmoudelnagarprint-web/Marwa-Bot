import re
from dataclasses import dataclass
from typing import Any

import database as db


UNCATEGORIZED_WORKSTATION = "❓ غير مصنف (Uncategorized)"
LASER_WORKSTATION = "⚡ ليزر (قص/حفر)"
SUBLIMATION_WORKSTATION = "🖨️ طباعة سبليميشن"
PHOTO_WORKSTATION = "🖨️ طباعة فوتو"
ASSEMBLY_WORKSTATION = "🧵 تجميع وتشطيب"


@dataclass(frozen=True)
class MaterialRule:
    label: str
    keywords: tuple[str, ...]


class ProductionRouter:
    TWO_DIMENSION_PATTERN = re.compile(
        r"(\d+(?:[.,]\d+)?)\s*[x×*]\s*(\d+(?:[.,]\d+)?)\s*(سم|cm|ملي|mm)?",
        re.IGNORECASE,
    )
    SINGLE_DIMENSION_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*(سم|cm|ملي|mm)", re.IGNORECASE)

    WORKSTATION_KEYWORDS = {
        SUBLIMATION_WORKSTATION: ("سبليميشن", "مج", "تيشيرت", "ميدالية", "مخدة"),
        PHOTO_WORKSTATION: ("فوتو", "تابلوه", "برواز"),
        LASER_WORKSTATION: ("فانوس", "بوكس", "نتيجة", "استاند", "نوت بوك", "نوتبوك", "حفر", "بصمة"),
    }

    SCRAP_KEYWORDS = ("ميدالية", "دلاية", "سلسلة", "باتش")
    WOOD_BASE_KEYWORDS = ("خشب", "ام دي اف", "هافان")
    ACRYLIC_BASE_KEYWORDS = ("اكريليك", "شفاف", "مراية")
    LEATHER_KEYWORDS = ("جلد", "محفظة")

    def parse(self, product_name: str) -> dict[str, Any]:
        normalized_name = self._normalize_text(product_name)
        size = self._extract_size(normalized_name)
        materials = self._detect_materials(normalized_name)
        workstations = self._detect_workstations(normalized_name, materials)
        is_scrap_friendly = self._detect_scrap_friendly(normalized_name)

        learned_rule = db.get_product_routing_rule(product_name)
        if learned_rule:
            stored_w = learned_rule.get("workstation") or ""
            stored_m = learned_rule.get("material") or ""
            
            if stored_w:
                w_list = [w.strip() for w in stored_w.split(",") if w.strip()]
            else:
                w_list = workstations if workstations else [UNCATEGORIZED_WORKSTATION]
                
            if stored_m:
                m_list = [m.strip() for m in stored_m.split(",") if m.strip()]
            else:
                m_list = materials if materials else ["غير محدد"]
                
            return {
                "product_name": product_name,
                "workstation": w_list[0] if w_list else UNCATEGORIZED_WORKSTATION,
                "material": m_list[0] if m_list else "غير محدد",
                "workstations": w_list,
                "materials": m_list,
                "size": size,
                "is_scrap_friendly": bool(learned_rule.get("is_scrap_friendly")),
                "source": "memory",
            }

        w_list = workstations if workstations else [UNCATEGORIZED_WORKSTATION]
        m_list = materials if materials else ["غير محدد"]
        source_val = "auto" if workstations else "fallback"

        return {
            "product_name": product_name,
            "workstation": w_list[0] if w_list else UNCATEGORIZED_WORKSTATION,
            "material": m_list[0] if m_list else "غير محدد",
            "workstations": w_list,
            "materials": m_list,
            "size": size,
            "is_scrap_friendly": is_scrap_friendly,
            "source": source_val,
        }

    def _normalize_text(self, text: str) -> str:
        normalized = str(text or "").strip().lower()
        normalized = normalized.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        normalized = normalized.replace("ة", "ه").replace("ى", "ي")
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    def _extract_size(self, normalized_name: str) -> str | None:
        pair_match = self.TWO_DIMENSION_PATTERN.search(normalized_name)
        if pair_match:
            width = pair_match.group(1).replace(",", ".")
            height = pair_match.group(2).replace(",", ".")
            unit = self._normalize_unit(pair_match.group(3) or "سم")
            return f"{width}×{height} {unit}"

        single_match = self.SINGLE_DIMENSION_PATTERN.search(normalized_name)
        if single_match:
            value = single_match.group(1).replace(",", ".")
            unit = self._normalize_unit(single_match.group(2))
            return f"{value} {unit}"

        return None

    def _normalize_unit(self, unit: str) -> str:
        unit = unit.lower()
        if unit in ("cm", "سم"):
            return "سم"
        return "مم"

    def _detect_materials(self, normalized_name: str) -> list[str]:
        materials = []
        if any(keyword in normalized_name for keyword in self.LEATHER_KEYWORDS):
            materials.append("جلد")

        if "مرايه" in normalized_name:
            materials.append("أكريليك - مراية")
        elif "شفاف" in normalized_name:
            materials.append("أكريليك - شفاف")
        elif any(keyword in normalized_name for keyword in self.ACRYLIC_BASE_KEYWORDS):
            materials.append("أكريليك")

        has_wood_base = any(keyword in normalized_name for keyword in self.WOOD_BASE_KEYWORDS)
        if "هافان" in normalized_name:
            materials.append("خشب - هافان")
        elif has_wood_base and "بني" in normalized_name:
            materials.append("خشب - بني")
        elif has_wood_base and "دهبي" in normalized_name:
            materials.append("خشب - دهبي")
        elif has_wood_base and "فضي" in normalized_name:
            materials.append("خشب - فضي")
        elif has_wood_base:
            materials.append("خشب")

        return materials

    def _detect_workstations(self, normalized_name: str, detected_materials: list[str]) -> list[str]:
        workstations = []
        for workstation, keywords in self.WORKSTATION_KEYWORDS.items():
            if any(keyword in normalized_name for keyword in keywords):
                workstations.append(workstation)

        if detected_materials:
            for material in detected_materials:
                if material.startswith("خشب") or material.startswith("أكريليك"):
                    if LASER_WORKSTATION not in workstations:
                        workstations.append(LASER_WORKSTATION)
                if material.startswith("جلد"):
                    if ASSEMBLY_WORKSTATION not in workstations:
                        workstations.append(ASSEMBLY_WORKSTATION)

        # Multi-stage printing detection (e.g. printed on wood/acrylic)
        if any(keyword in normalized_name for keyword in ("مطبوع", "طباعه", "سبليميشن", "فوتو")):
            # If it's a tablow/photo frame, routes to PHOTO
            if any(k in normalized_name for k in ("تابلوه", "برواز", "فوتو")):
                if PHOTO_WORKSTATION not in workstations:
                    workstations.append(PHOTO_WORKSTATION)
            else:
                if SUBLIMATION_WORKSTATION not in workstations:
                    workstations.append(SUBLIMATION_WORKSTATION)

        return workstations

    def _detect_scrap_friendly(self, normalized_name: str) -> bool:
        normalized_keywords = tuple(self._normalize_text(keyword) for keyword in self.SCRAP_KEYWORDS)
        return any(keyword in normalized_name for keyword in normalized_keywords)


router = ProductionRouter()
