# SpotMe Scouting API

Backend خاص بمنصة SpotMe لاكتشاف المواهب الرياضية، مبني بـ FastAPI، وفيه شات ذكي مربوط بـ Groq (نموذج llama-3.3-70b-versatile) بيرد على أسئلة الكشافة من قاعدة بيانات اللاعبين مباشرة، وبيدردش بشكل طبيعي في الكلام العادي.

## المميزات

- بحث وفلترة وترتيب في قاعدة اللاعبين (رياضة، نادي، مركز، عمر، AI Score، طول، إصابات، نسبة تعافي).
- جلب لاعب واحد بالاسم أو الرقم، مع حل الغموض والتصحيح الإملائي التلقائي (fuzzy matching).
- إحصائيات لأي مؤشر رقمي (متوسط، وسيط، أعلى وأقل قيمة).
- مقارنة بين 2 إلى 4 لاعبين على كل المؤشرات المشتركة.
- ترشيح ذكي للاعبين بدرجة موهبة مركّبة (talent score) تجمع الأداء والإصابات والتعافي والتطور الشهري.
- إيجاد لاعبين مشابهين للاعب معين.
- الترتيب المئوي (percentile) للاعب بين أقرانه في نفس المركز.
- شات ذكي (`/api/chat`) بيستخدم الأدوات دي تلقائي عن طريق Groq function calling، ومحتفظ بجلسات محادثة (sessions) في الرام.

## هيكل المشروع

```
SpotMe/
├── app.py                 # كل الكود: API + منطق البيانات + تكامل Groq
├── data/
│   └── players.json       # قاعدة بيانات اللاعبين
├── .env                    # متغيرات البيئة (مش بيترفع على Git)
├── .env.example            # نموذج لمتغيرات البيئة
├── requirements.txt
├── .gitignore
└── README.md
```

## المتطلبات والتثبيت

يحتاج Python 3.10 أو أحدث.

```bash
python -m venv venv
venv\Scripts\activate        # على ويندوز
source venv/bin/activate     # على ماك/لينكس

pip install -r requirements.txt
```

## متغيرات البيئة

اعمل ملف `.env` في نفس مكان `app.py` بالشكل ده:

```
GROQ_API_KEY=ضع_مفتاحك_هنا
GROQ_MODEL=llama-3.3-70b-versatile
DATA_PATH=data/players.json
MAX_SESSION_MESSAGES=24
```

- `GROQ_API_KEY`: مفتاح API بتاعك من https://console.groq.com
- `GROQ_MODEL`: اسم الموديل المستخدم في الشات (ممكن تغيره لموديل أخف زي `llama-3.1-8b-instant` لو عايز استهلاك توكن أقل)
- `DATA_PATH`: مسار ملف بيانات اللاعبين
- `MAX_SESSION_MESSAGES`: أقصى عدد رسائل يتم الاحتفاظ بيها في كل جلسة شات

## شكل بيانات اللاعبين (players.json)

الملف عبارة عن object فيه مفتاح لكل رياضة (`football`, `basketball`, `handball`, `volleyball`)، وكل مفتاح قيمته array من اللاعبين:

```json
{
  "football": [
    {
      "player_id": "f001",
      "name": "اسم اللاعب",
      "sport": "football",
      "position": "Winger",
      "current_club": "اسم النادي",
      "age": 21,
      "height_cm": 178,
      "weight_kg": 72,
      "ai_score": 87.5,
      "injuries_last_2y": 1,
      "recovery_percentage": 92,
      "monthly_improvement_pct": 4.2,
      "profile_views_last_week": 340,
      "preferred_foot": "Right"
    }
  ],
  "basketball": [],
  "handball": [],
  "volleyball": []
}
```

## تشغيل السيرفر

```bash
python app.py
```

أو:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

السيرفر هيشتغل على `http://localhost:8000`.

## الـ API Endpoints

| Method | Endpoint | الوظيفة |
|---|---|---|
| POST | `/api/chat` | الشات الذكي، بيستقبل `message` + `session_id` أو `messages` كاملة |
| GET | `/api/session/{session_id}` | جلب تاريخ جلسة شات معينة |
| DELETE | `/api/session/{session_id}` | مسح جلسة شات |
| POST | `/api/search` | بحث وفلترة اللاعبين |
| GET | `/api/players/{id_or_name}` | جلب لاعب واحد |
| GET | `/api/overview` | نظرة عامة على قاعدة البيانات |
| POST | `/api/stats` | إحصائيات مؤشر معين |
| POST | `/api/compare` | مقارنة لاعبين |
| POST | `/api/recommend` | ترشيح لاعبين |
| POST | `/api/similar` | لاعبين مشابهين |
| POST | `/api/percentile` | الترتيب المئوي للاعب |

### مثال استخدام الشات

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "رشحلي أفضل 3 لاعبين كرة سلة للكشافة"}'
```

الرد بيرجع `reply` و `session_id`. ابعت نفس الـ `session_id` في الطلب اللي بعده عشان يفتكر المحادثة.

## ملاحظات مهمة

- الشات مبني على Groq، وكل حساب Groq مجاني ليه حد أقصى يومي من التوكنز (Tokens Per Day). لو ظهر خطأ `429` معناه إنك خلصت الحد اليومي، وهيرجع يشتغل تلقائي بعد فترة قصيرة، أو تقدر تعمل ترقية (upgrade) من https://console.groq.com/settings/billing
- بيانات الجلسات (`SESSIONS`) محفوظة في الرام بس، فلو السيرفر اتقفل أو اتعمله ريستارت هتضيع كل المحادثات المفتوحة.
- الشات مصمم يرد بشكل طبيعي على الكلام العادي (تحية، دردشة) من غير ما يلجأ لقاعدة البيانات، ويستخدم الأدوات بس لما السؤال يكون فعلاً عن لاعب أو إحصائية أو مقارنة.