import os
import json
import math
import time
import uuid
import difflib
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq, RateLimitError, APIStatusError

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
DATA_PATH = os.getenv("DATA_PATH", "data/players.json")
MAX_SESSION_MESSAGES = int(os.getenv("MAX_SESSION_MESSAGES", "24"))

if not GROQ_API_KEY:
    print("[تحذير] GROQ_API_KEY غير موجود في متغيرات البيئة. أضفه في ملف .env")

SYSTEM_PROMPT = (
    "أنت SpotMe Assistant، مساعد افتراضي ودود وذكي شغال جوه منصة SpotMe لاكتشاف المواهب الرياضية، "
    "بتتكلم مع كشافة (Scouts) ولاعبين بيدوروا على معلومات عن مواهب رياضية.\n"
    "قاعدة البيانات عندك فيها لاعبين في 4 رياضات: كرة القدم (football)، السلة (basketball)، اليد (handball)، الطائرة (volleyball).\n"
    "\n"
    "أسلوبك في الكلام:\n"
    "- اتكلم زي إنسان عادي بيدردش مع حد قدامه، مش زي بوت بيرد ردود جامدة أو رسمية جداً.\n"
    "- لو حد سلم عليك أو سألك عامل ايه أو ازيك أو صباح الخير أو أي كلام عادي أو تحية أو شكر، رد عليه بشكل طبيعي وودود "
    "زي أي حد بيرد على صاحبه، من غير ما تستخدم أي أداة (function) خالص، ومن غير ما تقول حاجة زي مفيش لاعب بهذا الاسم.\n"
    "- ابقى مرح وخفيف الظل في كلامك العادي، لكن لما الكلام يبقى عن بيانات فعلية (لاعب، رقم، مقارنة، ترشيح) ابقى دقيق "
    "ومتزم بالأرقام الحقيقية بس.\n"
    "- لو مش فاهم قصد المستخدم، اسأله سؤال قصير يوضح بيه قصده بدل ما تخمن أو تستخدم أداة على الفاضي.\n"
    "\n"
    "قواعد التعامل مع البيانات:\n"
    "1) تحدث عن SpotMe وبيانات اللاعبين اللي في قاعدة البيانات. أي سؤال بعيد تماماً عن الرياضة والمنصة (زي أسئلة "
    "عامة عن العالم مالها علاقة بالرياضة) ارفضه بلطف واقترح إنك تساعده في حاجة تخص اللاعبين أو المنصة.\n"
    "2) استخدم الأدوات (functions) فقط لما يكون السؤال فعلاً بيطلب بيانات من القاعدة: اسم لاعب، إحصائية، مقارنة، "
    "ترشيح، تشابه، أو نظرة عامة على القاعدة. الكلام العادي والتحيات والدردشة مالهاش علاقة بالأدوات خالص.\n"
    "3) لا تخترع لاعبين أو أرقاماً أبداً. كل رقم أو اسم لازم يكون جاي من نتيجة أداة فعلاً.\n"
    "4) أجب بنفس لغة المستخدم (عربي أو إنجليزي)، بأسلوب مختصر وواضح ومريح في القراءة.\n"
    "5) ممنوع استخدام أي تنسيق Markdown إطلاقاً. لا نجوم، لا خطوط مائلة، لا عناوين بالهاشتاج، ولا جداول Markdown. "
    "اكتب دائماً نص عادي فقط. لعرض عدة لاعبين استخدم أسطر مرقمة بسيطة مفصولة بسطر جديد، بدون أي رموز تنسيق.\n"
    "6) عند ترشيح لاعبين للكشافة، اشرح سبب الترشيح بناءً على المؤشرات (ai_score، عدد الإصابات، نسبة التعافي، "
    "التحسن الشهري، ومؤشرات الأداء الخاصة بكل رياضة).\n"
    "7) لأسئلة الترشيح أو مين الأفضل استخدم recommend_players بدلاً من ترتيب query_players بـ ai_score بس، "
    "لأن recommend_players بيحسب درجة موهبة مركّبة تجمع الأداء والإصابات والتعافي والتطور الشهري معاً، وأدق للترشيح.\n"
    "8) إذا طلب المستخدم مقارنة بين لاعبين استخدم compare_players. إذا طلب لاعبين مشابهين للاعب معين استخدم "
    "find_similar_players. إذا سأل كيف يقارن لاعب بأقرانه في نفس المركز استخدم get_player_percentile.\n"
    "9) إذا رجعت أداة get_player نتيجة فيها ambiguous بقيمة true، فده معناه وجود أكتر من لاعب مطابق. "
    "لا تختر لاعباً عشوائياً؛ اعرض للمستخدم أسماء المرشحين في candidates واطلب منه يحدد باسم كامل أو رقم اللاعب.\n"
    "10) لو أداة get_player رجعت error يعني مفيش لاعب بهذا الاسم فعلاً في القاعدة، قولها للمستخدم بلطف واقترح "
    "يتأكد من الاسم أو يجرب اسم تاني، بس متستخدمش الرد ده أبداً على كلام عادي أو تحية."
)


class PlayerService:
    SPORTS = ["football", "basketball", "handball", "volleyball"]

    BASELINE_NUMERIC_FIELDS = [
        "age", "height_cm", "weight_kg", "ai_score",
        "injuries_last_2y", "recovery_percentage",
        "monthly_improvement_pct", "profile_views_last_week",
    ]

    TALENT_WEIGHTS = {
        "ai_score": 0.40,
        "recovery_percentage": 0.20,
        "injuries_last_2y": -0.15,
        "monthly_improvement_pct": 0.15,
        "profile_views_last_week": 0.10,
    }

    SIMILARITY_FIELDS = [
        "age", "height_cm", "weight_kg", "ai_score",
        "recovery_percentage", "injuries_last_2y", "monthly_improvement_pct",
    ]

    def __init__(self, data_path: str = DATA_PATH):
        with open(data_path, "r", encoding="utf-8") as f:
            self._data: Dict[str, List[Dict[str, Any]]] = json.load(f)

    def get_all_players(self, sport: Optional[str] = None) -> List[Dict[str, Any]]:
        if sport and sport.lower() in self.SPORTS:
            return self._data.get(sport.lower(), [])
        return [player for s in self.SPORTS for player in self._data.get(s, [])]

    @staticmethod
    def _normalize(values: List[float]) -> List[float]:
        lo, hi = min(values), max(values)
        if hi == lo:
            return [0.5 for _ in values]
        return [(v - lo) / (hi - lo) for v in values]

    def query_players(
        self,
        sport: Optional[str] = None,
        name_contains: Optional[str] = None,
        club_contains: Optional[str] = None,
        position: Optional[str] = None,
        min_age: Optional[int] = None,
        max_age: Optional[int] = None,
        min_ai_score: Optional[float] = None,
        max_ai_score: Optional[float] = None,
        min_height_cm: Optional[float] = None,
        max_height_cm: Optional[float] = None,
        max_injuries: Optional[int] = None,
        min_recovery: Optional[float] = None,
        sort_by: Optional[str] = "ai_score",
        order: Optional[str] = "desc",
        limit: Optional[int] = 10,
    ) -> Dict[str, Any]:
        rows = self.get_all_players(sport)

        def includes(val: Any, needle: str) -> bool:
            return needle.lower() in str(val or "").lower()

        if name_contains:
            rows = [p for p in rows if includes(p.get("name"), name_contains)]
        if club_contains:
            rows = [p for p in rows if includes(p.get("current_club"), club_contains)]
        if position:
            rows = [p for p in rows if includes(p.get("position"), position)]
        if min_age is not None:
            rows = [p for p in rows if p.get("age", 0) >= min_age]
        if max_age is not None:
            rows = [p for p in rows if p.get("age", 0) <= max_age]
        if min_ai_score is not None:
            rows = [p for p in rows if p.get("ai_score", 0) >= min_ai_score]
        if max_ai_score is not None:
            rows = [p for p in rows if p.get("ai_score", 0) <= max_ai_score]
        if min_height_cm is not None:
            rows = [p for p in rows if p.get("height_cm", 0) >= min_height_cm]
        if max_height_cm is not None:
            rows = [p for p in rows if p.get("height_cm", 0) <= max_height_cm]
        if max_injuries is not None:
            rows = [p for p in rows if p.get("injuries_last_2y", 0) <= max_injuries]
        if min_recovery is not None:
            rows = [p for p in rows if p.get("recovery_percentage", 0) >= min_recovery]

        total = len(rows)
        sort_by_field = sort_by or "ai_score"
        reverse = (order or "desc").lower() != "asc"

        def sort_key(player: Dict[str, Any]):
            val = player.get(sort_by_field)
            if isinstance(val, (int, float)):
                return (0, val)
            return (1, str(val or ""))

        rows.sort(key=sort_key, reverse=reverse)
        lim = min(max(limit or 10, 1), 50)

        return {
            "total_matches": total,
            "returned": min(lim, total),
            "players": rows[:lim],
        }

    def get_player(self, id_or_name: str) -> Dict[str, Any]:
        rows = self.get_all_players()
        target = id_or_name.strip().lower()

        for p in rows:
            if str(p.get("player_id", "")).lower() == target:
                return p

        exact_name_matches = [p for p in rows if str(p.get("name", "")).lower() == target]
        if len(exact_name_matches) == 1:
            return exact_name_matches[0]

        substr_matches = [p for p in rows if target in str(p.get("name", "")).lower()]
        if len(substr_matches) == 1:
            return substr_matches[0]
        if len(substr_matches) > 1:
            return {
                "ambiguous": True,
                "message": f"فيه أكتر من لاعب بيطابق '{id_or_name}'، حدد بالاسم الكامل أو برقم اللاعب (player_id)",
                "candidates": [
                    {
                        "player_id": p.get("player_id"),
                        "name": p.get("name"),
                        "sport": p.get("sport"),
                        "current_club": p.get("current_club"),
                    }
                    for p in substr_matches[:10]
                ],
            }

        names_map = {p.get("name", ""): p for p in rows}
        close = difflib.get_close_matches(id_or_name, list(names_map.keys()), n=5, cutoff=0.6)
        if close:
            return {
                "ambiguous": True,
                "message": f"لا يوجد تطابق تام لـ '{id_or_name}'، هل تقصد أحد هؤلاء؟",
                "candidates": [
                    {
                        "player_id": names_map[n].get("player_id"),
                        "name": n,
                        "sport": names_map[n].get("sport"),
                        "current_club": names_map[n].get("current_club"),
                    }
                    for n in close
                ],
            }

        return {"error": "لم يتم العثور على لاعب بهذا الاسم أو الرقم في قاعدة بيانات SpotMe"}

    def stats_for(self, metric: str, sport: Optional[str] = None) -> Dict[str, Any]:
        rows = [p for p in self.get_all_players(sport) if isinstance(p.get(metric), (int, float))]
        if not rows:
            return {"error": f"لا توجد بيانات رقمية للمؤشر {metric}"}

        values = [float(p[metric]) for p in rows]
        values_sorted = sorted(values)
        total_sum = sum(values)
        best_player = max(rows, key=lambda x: x[metric])

        return {
            "sport": sport or "all",
            "metric": metric,
            "count": len(rows),
            "average": round(total_sum / len(values), 2),
            "median": values_sorted[len(values_sorted) // 2],
            "min": values_sorted[0],
            "max": values_sorted[-1],
            "top_player": {
                "name": best_player.get("name"),
                "player_id": best_player.get("player_id"),
                "value": best_player.get(metric),
            },
        }

    def database_overview(self) -> Dict[str, Any]:
        sports_summary = []
        for s in self.SPORTS:
            players = self._data.get(s, [])
            if players:
                fields = list(players[0].keys())
                clubs = list(set(p.get("current_club") for p in players if p.get("current_club")))
                positions = list(set(p.get("position") for p in players if p.get("position")))
            else:
                fields, clubs, positions = [], [], []

            sports_summary.append({
                "sport": s,
                "players": len(players),
                "fields": fields,
                "clubs": clubs,
                "positions": positions,
            })

        return {
            "sports": sports_summary,
            "total_players": len(self.get_all_players()),
        }

    def compare_players(self, ids_or_names: List[str]) -> Dict[str, Any]:
        if not ids_or_names or len(ids_or_names) < 2:
            return {"error": "يجب إدخال لاعبين على الأقل للمقارنة"}
        ids_or_names = ids_or_names[:4]

        resolved = []
        for q in ids_or_names:
            res = self.get_player(q)
            if "error" in res or res.get("ambiguous"):
                return {"error": f"تعذر تحديد اللاعب لـ '{q}' بدقة", "detail": res}
            resolved.append(res)

        common_fields = set(resolved[0].keys())
        for p in resolved[1:]:
            common_fields &= set(p.keys())

        excluded = {"player_id", "name", "sport", "position", "current_club", "preferred_foot"}
        numeric_fields = sorted([
            f for f in common_fields
            if f not in excluded and all(isinstance(p.get(f), (int, float)) for p in resolved)
        ])

        neutral_fields = {"age", "height_cm", "weight_kg"}
        lower_is_better_fields = {"injuries_last_2y"}

        comparison = []
        for field in numeric_fields:
            values = {p["name"]: p.get(field) for p in resolved}
            if field in neutral_fields:
                comparison.append({"metric": field, "values": values, "best": None})
                continue
            higher_is_better = field not in lower_is_better_fields
            best_name = max(values, key=lambda n: values[n]) if higher_is_better else min(values, key=lambda n: values[n])
            comparison.append({"metric": field, "values": values, "best": best_name})

        return {
            "players": [
                {
                    "player_id": p.get("player_id"),
                    "name": p.get("name"),
                    "sport": p.get("sport"),
                    "position": p.get("position"),
                    "current_club": p.get("current_club"),
                }
                for p in resolved
            ],
            "comparison": comparison,
        }

    def recommend_players(
        self,
        sport: Optional[str] = None,
        position: Optional[str] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        rows = self.get_all_players(sport)
        if position:
            rows = [p for p in rows if str(p.get("position", "")).lower() == position.lower()]
        if not rows:
            return {"error": "لا يوجد لاعبون مطابقون لهذه الرياضة أو المركز"}

        fields = list(self.TALENT_WEIGHTS.keys())
        normalized_cols = {}
        for f in fields:
            vals = [float(p.get(f, 0) or 0) for p in rows]
            normalized_cols[f] = self._normalize(vals)

        scored = []
        for i, p in enumerate(rows):
            score = 0.0
            breakdown = {}
            for f, w in self.TALENT_WEIGHTS.items():
                norm_val = normalized_cols[f][i]
                score += norm_val * w
                breakdown[f] = {"raw": p.get(f), "normalized": round(norm_val, 3), "weight": w}

            scored.append({
                "player_id": p.get("player_id"),
                "name": p.get("name"),
                "sport": p.get("sport"),
                "position": p.get("position"),
                "current_club": p.get("current_club"),
                "talent_score": round(score * 100, 1),
                "score_breakdown": breakdown,
            })

        scored.sort(key=lambda x: x["talent_score"], reverse=True)
        lim = min(max(limit or 5, 1), 20)

        return {
            "sport": sport or "all",
            "position": position,
            "considered": len(rows),
            "top_players": scored[:lim],
        }

    def find_similar_players(self, id_or_name: str, limit: int = 5) -> Dict[str, Any]:
        target = self.get_player(id_or_name)
        if "error" in target or target.get("ambiguous"):
            return {"error": "تعذر تحديد اللاعب المرجعي بدقة", "detail": target}

        sport = target.get("sport", "").lower()
        pool = [p for p in self.get_all_players(sport) if p.get("player_id") != target.get("player_id")]
        if not pool:
            return {"error": "لا يوجد لاعبون آخرون لمقارنتهم في نفس الرياضة"}

        all_rows = pool + [target]
        stats = {}
        for f in self.SIMILARITY_FIELDS:
            vals = [float(p.get(f, 0) or 0) for p in all_rows]
            mean = sum(vals) / len(vals)
            variance = sum((v - mean) ** 2 for v in vals) / len(vals)
            std = math.sqrt(variance) or 1.0
            stats[f] = (mean, std)

        def vector(p):
            return [(float(p.get(f, 0) or 0) - stats[f][0]) / stats[f][1] for f in self.SIMILARITY_FIELDS]

        target_vec = vector(target)
        results = []
        for p in pool:
            v = vector(p)
            dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(target_vec, v)))
            results.append((dist, p))

        results.sort(key=lambda x: x[0])
        lim = min(max(limit or 5, 1), 15)

        return {
            "reference_player": {
                "player_id": target.get("player_id"),
                "name": target.get("name"),
                "sport": target.get("sport"),
            },
            "similar_players": [
                {
                    "player_id": p.get("player_id"),
                    "name": p.get("name"),
                    "position": p.get("position"),
                    "current_club": p.get("current_club"),
                    "ai_score": p.get("ai_score"),
                    "similarity_distance": round(dist, 3),
                }
                for dist, p in results[:lim]
            ],
        }

    def get_player_percentile(self, id_or_name: str, metric: str) -> Dict[str, Any]:
        target = self.get_player(id_or_name)
        if "error" in target or target.get("ambiguous"):
            return {"error": "تعذر تحديد اللاعب بدقة", "detail": target}

        if not isinstance(target.get(metric), (int, float)):
            return {"error": f"المؤشر {metric} غير رقمي أو غير موجود لهذا اللاعب"}

        sport = target.get("sport", "").lower()
        position = target.get("position")

        pool = [
            p for p in self.get_all_players(sport)
            if isinstance(p.get(metric), (int, float)) and p.get("position") == position
        ]
        scope = "position"
        if len(pool) < 3:
            pool = [p for p in self.get_all_players(sport) if isinstance(p.get(metric), (int, float))]
            scope = "sport"

        values = sorted(float(p[metric]) for p in pool)
        target_val = float(target[metric])
        rank = sum(1 for v in values if v <= target_val)
        percentile = round((rank / len(values)) * 100, 1)

        return {
            "player": {"name": target.get("name"), "player_id": target.get("player_id")},
            "metric": metric,
            "value": target_val,
            "percentile": percentile,
            "compared_to": scope,
            "pool_size": len(values),
        }


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_players",
            "description": (
                "البحث والفلترة والترتيب في قائمة لاعبي SpotMe حسب الرياضة، النادي، المركز، "
                "العمر، AI Score، الطول، عدد الإصابات، ونسبة التعافي. استخدمها فقط لما المستخدم "
                "فعلاً بيدور على بيانات لاعبين، مش لكلام عادي."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sport": {"type": "string", "description": "football, basketball, handball, volleyball"},
                    "name_contains": {"type": "string"},
                    "club_contains": {"type": "string"},
                    "position": {"type": "string"},
                    "min_age": {"type": "integer"},
                    "max_age": {"type": "integer"},
                    "min_ai_score": {"type": "number"},
                    "max_ai_score": {"type": "number"},
                    "min_height_cm": {"type": "number"},
                    "max_height_cm": {"type": "number"},
                    "max_injuries": {"type": "integer"},
                    "min_recovery": {"type": "number"},
                    "sort_by": {"type": "string", "description": "اسم الحقل المستخدم في الترتيب، مثل ai_score"},
                    "order": {"type": "string", "enum": ["asc", "desc"]},
                    "limit": {"type": "integer", "description": "عدد النتائج المطلوبة (حد أقصى 50)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_player",
            "description": (
                "جلب تفاصيل لاعب واحد بالاسم أو برقم اللاعب. استخدمها فقط لما المستخدم يذكر اسم لاعب "
                "أو رقم لاعب صريح وواضح، وليس لأي تحية أو جملة عادية زي عامل ايه أو ازيك. "
                "قد ترجع النتيجة ambiguous=true مع قائمة مرشحين إذا كان الاسم غير كافٍ للتحديد أو فيه خطأ إملائي بسيط."
            ),
            "parameters": {
                "type": "object",
                "properties": {"id_or_name": {"type": "string"}},
                "required": ["id_or_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stats_for",
            "description": (
                "حساب المتوسط والحد الأقصى والحد الأدنى والوسيط لمؤشر رقمي معين (مثل ai_score) "
                "لرياضة معينة أو لكل الرياضات، مع تحديد صاحب أعلى قيمة."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "description": "اسم الحقل الرقمي، مثل ai_score"},
                    "sport": {"type": "string"},
                },
                "required": ["metric"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "database_overview",
            "description": "نظرة عامة على قاعدة بيانات SpotMe: عدد اللاعبين لكل رياضة، الأندية، والمراكز المتاحة.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_players",
            "description": "مقارنة 2 إلى 4 لاعبين جنباً إلى جنب على كل المؤشرات الرقمية المشتركة بينهم، مع تحديد الأفضل في كل مؤشر.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ids_or_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "قائمة أسماء أو أرقام اللاعبين المراد مقارنتهم (من 2 إلى 4)",
                    }
                },
                "required": ["ids_or_names"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_players",
            "description": (
                "ترشيح ذكي للاعبين باستخدام درجة موهبة مركّبة (talent_score) تجمع بين ai_score ونسبة التعافي "
                "وعدد الإصابات (بالسلب) والتحسن الشهري وشعبية الملف الشخصي، وليس فقط ترتيب ai_score الخام. "
                "استخدمها دائماً عند سؤال المستخدم عن أفضل لاعب أو مين ترشحه للكشافة."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sport": {"type": "string"},
                    "position": {"type": "string"},
                    "limit": {"type": "integer", "description": "عدد اللاعبين المرشحين (حد أقصى 20)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_similar_players",
            "description": "إيجاد لاعبين في نفس الرياضة يشبهون لاعباً معيناً في العمر والطول والوزن والأداء والإصابات والتعافي.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id_or_name": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["id_or_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_player_percentile",
            "description": (
                "معرفة الترتيب المئوي (percentile) للاعب مقارنة بأقرانه في نفس الرياضة والمركز على مؤشر معين، "
                "مفيدة لسؤال مثل: كيف يقارن هذا اللاعب بزملائه في نفس المركز؟"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id_or_name": {"type": "string"},
                    "metric": {"type": "string", "description": "اسم الحقل الرقمي، مثل ai_score"},
                },
                "required": ["id_or_name", "metric"],
            },
        },
    },
]

MAX_TOOL_ITERATIONS = 8
GROQ_MAX_RETRIES = 3


class GroqService:
    def __init__(self, player_service: PlayerService):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.player_service = player_service
        self._dispatch = {
            "query_players": self.player_service.query_players,
            "get_player": self.player_service.get_player,
            "stats_for": self.player_service.stats_for,
            "database_overview": self.player_service.database_overview,
            "compare_players": self.player_service.compare_players,
            "recommend_players": self.player_service.recommend_players,
            "find_similar_players": self.player_service.find_similar_players,
            "get_player_percentile": self.player_service.get_player_percentile,
        }

    def _run_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        func = self._dispatch.get(name)
        if func is None:
            return {"error": f"أداة غير معروفة: {name}"}
        try:
            return func(**arguments)
        except Exception as e:
            return {"error": str(e)}

    def _call_groq(self, messages: List[Dict[str, Any]]):
        last_err: Optional[Exception] = None
        for attempt in range(GROQ_MAX_RETRIES):
            try:
                return self.client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0.4,
                )
            except RateLimitError:
                raise
            except Exception as e:
                last_err = e
                time.sleep(1.5 * (attempt + 1))
        raise last_err

    def chat(self, history: List[Dict[str, str]]) -> str:
        messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in history:
            role = "user" if str(m.get("role", "user")).lower() in ["user", "human"] else "assistant"
            messages.append({"role": role, "content": m.get("content", "")})

        for _ in range(MAX_TOOL_ITERATIONS):
            completion = self._call_groq(messages)
            msg = completion.choices[0].message

            if msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })

                for tc in msg.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    result = self._run_tool(tc.function.name, args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                continue

            return msg.content or "لم يتم إرجاع أي نص من النموذج."

        return "تعذر إكمال الطلب بعد عدة محاولات لاستخدام الأدوات، برجاء إعادة صياغة السؤال."


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: Optional[List[ChatMessage]] = None
    message: Optional[str] = None
    session_id: Optional[str] = None


class QueryPlayersInput(BaseModel):
    sport: Optional[str] = None
    name_contains: Optional[str] = None
    club_contains: Optional[str] = None
    position: Optional[str] = None
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    min_ai_score: Optional[float] = None
    max_ai_score: Optional[float] = None
    min_height_cm: Optional[float] = None
    max_height_cm: Optional[float] = None
    max_injuries: Optional[int] = None
    min_recovery: Optional[float] = None
    sort_by: Optional[str] = "ai_score"
    order: Optional[str] = "desc"
    limit: Optional[int] = 10


class MetricStatsInput(BaseModel):
    sport: Optional[str] = None
    metric: str


class ComparePlayersInput(BaseModel):
    ids_or_names: List[str]


class RecommendPlayersInput(BaseModel):
    sport: Optional[str] = None
    position: Optional[str] = None
    limit: Optional[int] = 5


class SimilarPlayersInput(BaseModel):
    id_or_name: str
    limit: Optional[int] = 5


class PercentileInput(BaseModel):
    id_or_name: str
    metric: str


app = FastAPI(
    title="SpotMe Scouting API",
    version="3.1.0",
    description="Backend-only service for SpotMe talent discovery, powered by FastAPI and Groq.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

player_service = PlayerService()
groq_service = GroqService(player_service=player_service)

SESSIONS: Dict[str, List[Dict[str, str]]] = {}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    if request.session_id:
        history = SESSIONS.get(request.session_id, [])
        session_id = request.session_id
    else:
        history = []
        session_id = str(uuid.uuid4())

    if request.message:
        history.append({"role": "user", "content": request.message})
    elif request.messages:
        history = [{"role": m.role, "content": m.content} for m in request.messages]
    else:
        raise HTTPException(status_code=400, detail="أرسل message مع session_id، أو أرسل messages كاملة")

    try:
        reply = groq_service.chat(history)
    except RateLimitError:
        raise HTTPException(
            status_code=429,
            detail="تم الوصول للحد الأقصى المسموح من استخدام الموديل حالياً، حاول تاني بعد شوية أو راجع حساب Groq بتاعك",
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"حدث خطأ أثناء معالجة الطلب: {e}")

    history.append({"role": "assistant", "content": reply})
    SESSIONS[session_id] = history[-MAX_SESSION_MESSAGES:]

    return {"reply": reply, "session_id": session_id}


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    return {"session_id": session_id, "history": SESSIONS.get(session_id, [])}


@app.delete("/api/session/{session_id}")
async def clear_session(session_id: str):
    SESSIONS.pop(session_id, None)
    return {"cleared": True, "session_id": session_id}


@app.post("/api/search")
async def search_players(input_data: QueryPlayersInput):
    return player_service.query_players(**input_data.model_dump(exclude_none=True))


@app.get("/api/players/{id_or_name}")
async def get_player_details(id_or_name: str):
    res = player_service.get_player(id_or_name)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@app.get("/api/overview")
async def get_overview():
    return player_service.database_overview()


@app.post("/api/stats")
async def get_metric_stats(input_data: MetricStatsInput):
    return player_service.stats_for(metric=input_data.metric, sport=input_data.sport)


@app.post("/api/compare")
async def compare_players(input_data: ComparePlayersInput):
    res = player_service.compare_players(input_data.ids_or_names)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@app.post("/api/recommend")
async def recommend_players(input_data: RecommendPlayersInput):
    res = player_service.recommend_players(
        sport=input_data.sport, position=input_data.position, limit=input_data.limit
    )
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@app.post("/api/similar")
async def similar_players(input_data: SimilarPlayersInput):
    res = player_service.find_similar_players(input_data.id_or_name, limit=input_data.limit)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@app.post("/api/percentile")
async def player_percentile(input_data: PercentileInput):
    res = player_service.get_player_percentile(input_data.id_or_name, input_data.metric)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)