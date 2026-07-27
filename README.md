# Jason-LA-AI

Business knowledge base and Phase 1 backend foundation for the assistant supporting **Jason在洛杉矶 / Jason LA Airport Transportation**.

## Purpose / 用途

This repository helps Jason manage inquiries, qualify leads, prepare quotes, confirm trip details, and write professional customer replies for a private airport transportation service in Southern California.

本知识库用于协助 Jason 管理南加州私人机场接送业务，包括客户咨询、行程资料收集、报价准备、订单确认及中英文回复。

The repository now contains the initial backend skeleton as well as business knowledge and reusable operating documents. It is not yet a customer-facing website or a working booking system. The documentation and future software do not replace Jason's judgment, legal requirements, insurance conditions, airport rules, or vehicle safety limits.

## Official business identity

- Brand / 品牌：**Jason在洛杉矶**
- English brand：**Jason LA Airport Transportation**
- Owner / 负责人：**Jason**
- Base / 营运基地：**Rowland Heights, California**
- Vehicle / 车辆：**2026 Toyota RAV4 Hybrid LE**
- Service / 服务：Private airport transportation in Southern California / 南加州私人机场接送

## Knowledge map

- `knowledge/brand_profile.md` — official identity, positioning, and communication standards
- `knowledge/service_area.md` — airports, geographic coverage, and trip qualification
- `knowledge/pricing_rules.md` — internal quoting rules and confirmed reference pricing
- `knowledge/vehicle_capacity.md` — passenger and luggage guidance
- `knowledge/customer_reply_templates.md` — adaptable bilingual customer messages
- `orders/order_template.md` — one record per trip or booking
- `customers/lead_tracking.md` — lead pipeline and follow-up format

## Backend structure

```text
app/
├── main.py          # FastAPI application entry point
├── config/          # Environment-backed settings
├── models/          # Future SQLAlchemy models
├── schemas/         # Future Pydantic request/response schemas
├── api/             # API router boundary
├── services/        # Future business workflow services
└── knowledge/       # Future knowledge-access boundary

tests/               # Automated tests
database/            # Database design documentation
knowledge/           # Authoritative business knowledge documents
orders/              # Order workflow documentation
customers/           # Customer and lead documentation
```

## Local development

Requirements:

- Python 3.12 or newer
- PostgreSQL for later database implementation

Create a virtual environment, install dependencies, and copy `.env.example` to `.env`. No database connection is opened by the current skeleton.

Run the development server:

```powershell
python -m uvicorn app.main:app --reload
```

Run tests:

```powershell
python -m pytest
```

Initialize the local PostgreSQL schema and insert three repeatable development
inquiries:

```powershell
python -m scripts.seed_development
```

The seed command uses `DATABASE_URL`, creates missing tables, and inserts only
missing seed records. It never deletes existing data. The examples cover a
Traditional Chinese ONT inquiry, an English Ontario Airport inquiry, and a
high-risk LAX capacity inquiry. Their analyzer outcomes are validated before
the transaction is committed.

FastAPI documentation will be available at `/docs` while the local server is running. The `/api/v1` router is intentionally empty until Phase 1 features are implemented.

## AI assistant operating rules

1. Use only confirmed facts in this knowledge base; do not invent prices, availability, policies, permits, amenities, or capacity.
2. Collect enough trip information before suggesting a quote: date, pickup time, pickup and destination, airport, flight details, passenger count, luggage, and special requirements.
3. Treat all prices as internal guidance until Jason approves the customer-facing quote.
4. Never reveal an internal minimum price or negotiation floor to a customer.
5. Escalate unusual routes, late-night timing, four-passenger trips, heavy luggage, child seats, oversized items, or ambiguous requests to Jason.
6. Never confirm a booking, exact pickup arrangement, price, or availability without Jason's approval.
7. Protect customer personal information. Record only information needed to manage the inquiry or trip.
8. Reply in the customer's language when clear. Use concise, polite, natural Chinese or English; provide both only when useful.

## Current scope

The current software scope is an importable FastAPI project skeleton with environment settings, an empty versioned API router, a SQLAlchemy declarative base, and a smoke test.

The following are intentionally not implemented yet:

- Business entities or database sessions
- Database migrations
- Customer, lead, order, quote, payment, or trip endpoints
- Pricing, capacity, scoring, or booking workflows
- AI or knowledge retrieval
- External messaging, notification, payment, or flight APIs
- Authentication or deployment configuration
