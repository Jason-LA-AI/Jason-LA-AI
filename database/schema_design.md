# Database Schema Design / 数据库结构设计

## Purpose / 用途

This document defines the Phase 0 and Phase 1 relational database design for the future **Jason在洛杉矶 / Jason-LA-AI** business assistant.

The database is the authoritative operational record for customers, inquiries, messages, orders, quotes, payments, trips, Jason approvals, notifications, and reports. AI output is advisory until validated and stored through the business workflow.

This is design documentation only. It is not application code or an executable migration.

## Database conventions / 数据库约定

- Recommended database: PostgreSQL.
- Primary keys use `uuid` so records can be created safely across integrations.
- Timestamps use `timestamptz` and are stored in UTC. Display them in `America/Los_Angeles` unless the user selects another timezone.
- Money uses `numeric(10,2)` plus a three-letter `currency_code`; do not use floating-point types.
- Flexible channel metadata and AI evidence may use `jsonb`, but core business fields remain relational and queryable.
- Every table includes `created_at`; mutable records also include `updated_at`.
- Customer-facing and internal text must be stored separately where disclosure would be unsafe.
- A round trip or separately operated trip leg should use a separate `orders` record. Related legs may share a `booking_group_id`.
- Status values are constrained to the documented values. They are written below as `varchar` plus allowed-value checks so they can evolve through controlled migrations.
- `NOT NULL` means required by the database. Some business-required trip information may initially be null while a lead is at `WAITING_FOR_INFORMATION`, but must be complete before confirmation.

## Relationship overview / 关系总览

```text
customers 1 ─── * leads
customers 1 ─── * conversations
customers 1 ─── * orders

leads 1 ─── * conversations
leads 1 ─── 0..* orders

orders 1 ─── * conversations
orders 1 ─── * quotes
orders 1 ─── * payments
orders 1 ─── 0..1 trips
orders 1 ─── * approvals
orders 1 ─── * notifications

quotes 1 ─── * approvals
trips 1 ─── * approvals

reports summarize leads, orders, quotes, payments, and trips
```

## 1. `customers`

### Purpose

Stores a reusable customer profile and contact preferences. Trip-specific facts must be reconfirmed on every order rather than copied as guaranteed current information.

### Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `id` | `uuid` | Yes | Primary key |
| `display_name` | `varchar(150)` | No | Customer name or preferred display name; may be unknown at first contact |
| `primary_contact` | `varchar(255)` | Yes | Phone number, messaging handle, email, or other reachable identifier |
| `primary_contact_type` | `varchar(30)` | Yes | `phone`, `xiaohongshu`, `facebook`, `email`, `wechat`, `other` |
| `secondary_contact` | `varchar(255)` | No | Optional alternate contact |
| `preferred_contact_method` | `varchar(30)` | No | Customer-stated preference |
| `source` | `varchar(30)` | Yes | `XIAOHONGSHU`, `FACEBOOK`, `GOOGLE_WEBSITE`, `REFERRAL`, `OTHER`, `UNKNOWN` |
| `source_detail` | `varchar(255)` | No | Campaign, page, referrer, or other factual source detail |
| `referrer_name` | `varchar(150)` | No | Only when supplied and operationally useful |
| `preferred_language` | `varchar(10)` | No | Customer communication preference: `English`, `zh-CN`, or `zh-TW` |
| `preferred_form_of_address` | `varchar(100)` | No | Customer-stated preferred name/title |
| `follow_up_preference` | `text` | No | Factual communication preference |
| `communication_notes` | `text` | No | Internal factual notes; no speculation |
| `common_pickup_area` | `varchar(255)` | No | Historical preference, not a new-order assumption |
| `common_destination` | `varchar(255)` | No | Historical preference, not a new-order assumption |
| `typical_passenger_count` | `smallint` | No | Historical information only; must be nonnegative |
| `typical_luggage_details` | `text` | No | Historical information only |
| `profile_status` | `varchar(20)` | Yes | `ACTIVE` or `INACTIVE` |
| `last_contact_at` | `timestamptz` | No | Most recent known interaction |
| `created_at` | `timestamptz` | Yes | Record creation time |
| `updated_at` | `timestamptz` | Yes | Last change time |

### Relationships

- One customer may have many `leads`, `conversations`, `orders`, and `notifications`.
- `primary_contact` should not be globally unique because channels may reuse handles or data may be incomplete. Use channel-aware matching and manual verification before merging profiles.

### Language preference rules

- `preferred_language` stores the customer's reusable communication language preference.
- Allowed values are exactly `English`, `zh-CN`, and `zh-TW`; null means the preference is not yet reliably established.
- The language of the customer's current message takes priority for the current reply.
- Reuse the stored preference only when the current message does not clearly indicate another language and reuse is appropriate.
- Do not permanently change the stored preference because of one isolated mixed-language message unless the customer requests the change or a consistent new preference is established.
- Language preference must never affect pricing, risk assessment, order acceptance, or priority scoring.

### Privacy constraints

- Do not store payment-card data, identity-document numbers, immigration records, or unrelated private information.
- Sensitive contact fields should be masked in routine logs and encrypted where supported.

## 2. `leads`

### Purpose

Represents a customer inquiry before or during qualification. Tracks source, intent, missing information, priority, risk, and the next action.

### Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `id` | `uuid` | Yes | Primary key |
| `customer_id` | `uuid` | Yes | Foreign key to `customers.id` |
| `source` | `varchar(30)` | Yes | Same source vocabulary as `customers.source` |
| `external_conversation_id` | `varchar(255)` | No | Channel conversation/thread identifier |
| `intent` | `varchar(40)` | No | `AIRPORT_PICKUP`, `AIRPORT_DROPOFF`, `PRIVATE_TRANSPORTATION`, `LONG_DISTANCE` |
| `status` | `varchar(30)` | Yes | `NEW`, `AWAITING_DETAILS`, `PENDING_JASON`, `QUOTED`, `FOLLOW_UP`, `CONVERTED`, `LOST`, `UNAVAILABLE` |
| `received_at` | `timestamptz` | Yes | First inquiry time |
| `last_contact_at` | `timestamptz` | No | Most recent customer interaction |
| `next_action` | `text` | No | Concrete next step |
| `next_action_owner` | `varchar(20)` | No | `AI`, `JASON`, or `CUSTOMER` |
| `follow_up_at` | `timestamptz` | No | Follow-up due time |
| `missing_information` | `jsonb` | No | List of missing fields; expected to be a JSON array |
| `analysis_result` | `jsonb` | No | Full structured placeholder/AI analysis result used for this lead |
| `customer_message_summary` | `text` | No | Factual inquiry summary |
| `route_summary` | `text` | No | Factual route summary |
| `vehicle_assessment` | `varchar(30)` | No | `LIKELY_COMFORTABLE`, `NEEDS_CONFIRMATION`, `NOT_RECOMMENDED`, `INSUFFICIENT_INFORMATION` |
| `risk_level` | `varchar(10)` | No | `LOW`, `MEDIUM`, or `HIGH` |
| `risk_reason` | `text` | No | Internal factual explanation |
| `priority_score` | `smallint` | No | 0–100 after applying documented scoring rules |
| `priority_level` | `varchar(10)` | No | `P1`, `P2`, `P3`, `P4`, or `P5` |
| `priority_override` | `varchar(30)` | No | `AVOID_RECOMMENDED`, `INFORMATION_REQUIRED`, `JASON_REVIEW_REQUIRED`, or null |
| `jason_decision_needed` | `text` | No | Exact decisions requested from Jason |
| `lost_reason` | `text` | No | Customer-stated or known reason; no speculation |
| `knowledge_version` | `varchar(100)` | No | Knowledge-base revision used for AI assessment |
| `created_at` | `timestamptz` | Yes | Record creation time |
| `updated_at` | `timestamptz` | Yes | Last change time |

### Relationships

- Many leads belong to one customer.
- One lead may have many conversations.
- One lead may create one or more orders; multiple orders support separate round-trip legs.

### Constraints

- `priority_score` must be between 0 and 100.
- A lead must not become `QUOTED` unless an associated quote was approved by Jason and sent.
- A lead must not become `CONVERTED` unless an associated order becomes `CONFIRMED`.

## 3. `conversations`

### Purpose

Stores individual incoming, outgoing, internal, and system messages across customer channels. Preserves message history while separating customer-visible content from internal notes.

### Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `id` | `uuid` | Yes | Primary key |
| `customer_id` | `uuid` | Yes | Foreign key to `customers.id` |
| `lead_id` | `uuid` | No | Foreign key to `leads.id` |
| `order_id` | `uuid` | No | Foreign key to `orders.id` |
| `channel` | `varchar(30)` | Yes | `XIAOHONGSHU`, `FACEBOOK`, `GOOGLE_WEBSITE`, `TELEGRAM`, `PHONE`, `EMAIL`, `MANUAL`, `OTHER` |
| `external_conversation_id` | `varchar(255)` | No | Channel thread/conversation ID |
| `external_message_id` | `varchar(255)` | No | Channel message ID for deduplication |
| `direction` | `varchar(20)` | Yes | `INBOUND`, `OUTBOUND`, `INTERNAL`, `SYSTEM` |
| `sender_type` | `varchar(20)` | Yes | `CUSTOMER`, `JASON`, `AI`, `SYSTEM` |
| `sender_identifier` | `varchar(255)` | No | External sender handle or internal identifier |
| `language_code` | `varchar(20)` | No | Detected or selected language |
| `message_text` | `text` | Yes | Original or sent message text |
| `attachment_metadata` | `jsonb` | No | File names/types/storage references; no raw binary content |
| `customer_visible` | `boolean` | Yes | Prevents internal notes from being exposed |
| `ai_generated` | `boolean` | Yes | Whether AI drafted/generated the stored message |
| `approval_required` | `boolean` | Yes | Whether human approval is required before sending |
| `approved_at` | `timestamptz` | No | Time Jason approved this exact outbound content |
| `sent_at` | `timestamptz` | No | Actual delivery attempt time |
| `delivery_status` | `varchar(20)` | No | `DRAFT`, `PENDING`, `SENT`, `DELIVERED`, `FAILED`, `NOT_APPLICABLE` |
| `raw_event_reference` | `jsonb` | No | Minimal webhook metadata for audit/debugging; apply retention limits |
| `created_at` | `timestamptz` | Yes | Record creation/receipt time |

### Relationships

- Every message belongs to one customer.
- A message may belong to a lead, an order, or both during conversion.
- Outbound messages may correspond to an `approval` and a `notification`.

### Constraints

- Unique partial key on (`channel`, `external_message_id`) when an external ID exists.
- `INTERNAL` messages must have `customer_visible = false`.
- Unsanitized webhook payloads should not be retained indefinitely.

## 4. `orders`

### Purpose

Stores one operational trip leg from inquiry through completion or cancellation. Contains the authoritative trip requirements and booking status.

### Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `id` | `uuid` | Yes | Primary key |
| `booking_group_id` | `uuid` | No | Groups separately operated round-trip or multi-leg orders |
| `customer_id` | `uuid` | Yes | Foreign key to `customers.id` |
| `lead_id` | `uuid` | No | Originating lead |
| `status` | `varchar(40)` | Yes | Exact documented booking status; defaults to `NEW` |
| `intent` | `varchar(40)` | Yes | `AIRPORT_PICKUP`, `AIRPORT_DROPOFF`, `PRIVATE_TRANSPORTATION`, `LONG_DISTANCE` |
| `service_date` | `date` | No | Required before confirmation |
| `pickup_at` | `timestamptz` | No | Requested/approved pickup time; required before confirmation |
| `service_timezone` | `varchar(50)` | Yes | Defaults to `America/Los_Angeles` |
| `trip_direction` | `varchar(20)` | No | `ONE_WAY`; separate orders are recommended for return legs |
| `airport_code` | `varchar(3)` | No | LAX, ONT, SNA, BUR, LGB, or another Jason-approved airport |
| `flight_scope` | `varchar(20)` | No | `DOMESTIC`, `INTERNATIONAL`, `NOT_APPLICABLE`, `UNKNOWN` |
| `airline` | `varchar(100)` | No | Airline name/code |
| `flight_number` | `varchar(30)` | No | Airline plus flight number |
| `scheduled_flight_at` | `timestamptz` | No | Arrival or departure time |
| `terminal` | `varchar(50)` | No | Terminal when known |
| `pickup_location` | `text` | No | Required before confirmation |
| `pickup_city` | `varchar(100)` | No | Supports route reporting |
| `destination` | `text` | No | Required before confirmation |
| `destination_city` | `varchar(100)` | No | Supports exact-direction matching and reporting |
| `extra_stops` | `jsonb` | No | Ordered stops with address and waiting notes |
| `passenger_count` | `smallint` | No | Required before confirmation; nonnegative |
| `adult_count` | `smallint` | No | Nonnegative |
| `child_count` | `smallint` | No | Nonnegative |
| `large_suitcase_count` | `smallint` | No | Nonnegative |
| `large_suitcase_details` | `text` | No | Sizes or photos reference |
| `carry_on_count` | `smallint` | No | Nonnegative |
| `oversized_item_details` | `text` | No | Strollers, wheelchairs, golf clubs, boxes, etc. |
| `child_seat_required` | `varchar(10)` | Yes | `YES`, `NO`, or `UNKNOWN` |
| `child_seat_details` | `text` | No | Count/type/provider; Jason policy remains approval-gated |
| `special_requests` | `text` | No | Customer-stated requests |
| `pickup_coordination_notes` | `text` | No | Internal operating notes |
| `vehicle_name` | `varchar(100)` | Yes | Defaults to `2026 Toyota RAV4 Hybrid LE` |
| `vehicle_assessment` | `varchar(30)` | Yes | `LIKELY_COMFORTABLE`, `NEEDS_CONFIRMATION`, `NOT_RECOMMENDED`, `INSUFFICIENT_INFORMATION` |
| `vehicle_assessment_reason` | `text` | No | Factual reasoning |
| `risk_level` | `varchar(10)` | No | `LOW`, `MEDIUM`, `HIGH` |
| `risk_reason` | `text` | No | Internal reasoning |
| `priority_score` | `smallint` | No | 0–100 |
| `priority_level` | `varchar(10)` | No | `P1`–`P5` |
| `missing_information` | `jsonb` | No | Outstanding required facts |
| `next_action` | `text` | No | Current next step |
| `next_action_owner` | `varchar(20)` | No | `AI`, `JASON`, `CUSTOMER` |
| `follow_up_at` | `timestamptz` | No | Due time |
| `customer_details_reconfirmed` | `boolean` | Yes | Defaults false |
| `confirmation_sent_at` | `timestamptz` | No | Written confirmation time |
| `cancelled_by` | `varchar(20)` | No | `CUSTOMER`, `JASON`, `UNKNOWN` |
| `cancelled_at` | `timestamptz` | No | Cancellation time |
| `cancellation_reason` | `text` | No | Factual stated reason |
| `internal_notes` | `text` | No | Never customer-visible |
| `knowledge_version` | `varchar(100)` | No | Knowledge revision used for decision support |
| `created_at` | `timestamptz` | Yes | Record creation time |
| `updated_at` | `timestamptz` | Yes | Last change time |

### Allowed order statuses

```text
NEW
WAITING_FOR_INFORMATION
QUOTED
WAITING_FOR_JASON_APPROVAL
CONFIRMED
COMPLETED
CANCELLED
```

### Relationships

- Many orders belong to one customer and optionally one originating lead.
- One order may have many conversations, quotes, payments, approvals, and notifications.
- One order has zero or one trip execution record.

### Confirmation constraints

An order may enter `CONFIRMED` only when:

- Required trip information is complete.
- Jason approved availability.
- Vehicle fit was approved when needed.
- A final price was approved by Jason.
- Customer accepted the agreed details.
- Jason explicitly approved booking confirmation.

These checks should be enforced transactionally by the service layer and supported by database constraints where practical.

## 5. `quotes`

### Purpose

Stores every internal price suggestion and customer-facing quote revision without overwriting history.

### Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `id` | `uuid` | Yes | Primary key |
| `order_id` | `uuid` | Yes | Foreign key to `orders.id` |
| `version_number` | `integer` | Yes | Starts at 1; unique per order |
| `status` | `varchar(30)` | Yes | `DRAFT`, `WAITING_FOR_JASON_APPROVAL`, `APPROVED`, `SENT`, `ACCEPTED`, `DECLINED`, `SUPERSEDED` |
| `currency_code` | `char(3)` | Yes | Defaults to `USD` |
| `suggested_min_amount` | `numeric(10,2)` | No | Internal documented range minimum; never automatically customer-visible |
| `suggested_max_amount` | `numeric(10,2)` | No | Internal documented range maximum |
| `suggested_amount` | `numeric(10,2)` | No | AI/rules recommendation, not final approval |
| `final_quoted_amount` | `numeric(10,2)` | No | Must remain null until Jason price approval |
| `quote_type` | `varchar(20)` | Yes | `ONE_WAY`, `ROUND_TRIP`, `OTHER`; separate order legs remain preferred |
| `exact_route_match` | `boolean` | Yes | Whether direction exactly matches documented pricing |
| `pricing_source` | `text` | No | Knowledge file/section or `NO_DOCUMENTED_PRICE` |
| `pricing_limitations` | `text` | No | Approximate example, time category, address uncertainty, etc. |
| `additional_fee_factors` | `jsonb` | No | Late time, waiting, parking, tolls, stops, child seat; no invented values |
| `approved_inclusions` | `text` | No | Jason-approved customer wording |
| `approved_exclusions` | `text` | No | Jason-approved customer wording |
| `internal_notes` | `text` | No | Internal only; may not be sent to customer |
| `knowledge_version` | `varchar(100)` | No | Knowledge revision used |
| `approved_at` | `timestamptz` | No | Price approval time |
| `sent_at` | `timestamptz` | No | Quote sent time |
| `customer_responded_at` | `timestamptz` | No | Acceptance/decline time |
| `created_at` | `timestamptz` | Yes | Record creation time |
| `updated_at` | `timestamptz` | Yes | Last change time |

### Relationships

- Many quote versions belong to one order.
- A quote may have multiple approval events, but one current approved final-price decision.

### Constraints

- Unique (`order_id`, `version_number`).
- Monetary values must be nonnegative.
- `final_quoted_amount` requires a corresponding approved `FINAL_PRICE` approval before `status` becomes `APPROVED` or `SENT`.
- Internal minimums must not be copied into customer-visible fields automatically.

## 6. `payments`

### Purpose

Tracks payment state and external references. It does not store card data or define undocumented deposit, cancellation, or refund policies.

### Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `id` | `uuid` | Yes | Primary key |
| `order_id` | `uuid` | Yes | Foreign key to `orders.id` |
| `quote_id` | `uuid` | No | Quote associated with the requested amount |
| `status` | `varchar(30)` | Yes | `NOT_REQUESTED`, `PENDING`, `PARTIALLY_PAID`, `PAID`, `REFUND_PENDING`, `REFUNDED`, `UNKNOWN` |
| `currency_code` | `char(3)` | Yes | Defaults to `USD` |
| `amount_due` | `numeric(10,2)` | No | Jason-approved amount due |
| `amount_received` | `numeric(10,2)` | Yes | Defaults to 0 |
| `amount_refunded` | `numeric(10,2)` | Yes | Defaults to 0 |
| `payment_method` | `varchar(50)` | No | Only an approved method label; policy not yet defined |
| `provider_name` | `varchar(50)` | No | External payment provider, when added |
| `external_transaction_reference` | `varchar(255)` | No | Non-sensitive provider reference |
| `requested_at` | `timestamptz` | No | Payment request time |
| `paid_at` | `timestamptz` | No | Payment completion time |
| `refund_requested_at` | `timestamptz` | No | Refund follow-up time |
| `refunded_at` | `timestamptz` | No | Refund completion time |
| `follow_up_notes` | `text` | No | Internal payment/refund follow-up |
| `created_at` | `timestamptz` | Yes | Record creation time |
| `updated_at` | `timestamptz` | Yes | Last change time |

### Relationships

- Many payment events/records may belong to one order.
- A payment may reference the quote that established the amount.

### Constraints

- Amounts must be nonnegative.
- Payment status does not change an order to `CONFIRMED` without Jason booking approval.
- Never store full card number, CVV, bank credentials, or raw payment tokens.

## 7. `trips`

### Purpose

Stores operational execution for a confirmed order: assigned vehicle, pickup coordination, actual timing, flight changes, and completion outcome.

### Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `id` | `uuid` | Yes | Primary key |
| `order_id` | `uuid` | Yes | Foreign key to `orders.id`; unique |
| `status` | `varchar(20)` | Yes | `SCHEDULED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED` |
| `driver_name` | `varchar(100)` | Yes | Defaults to `Jason` for V1 |
| `vehicle_name` | `varchar(100)` | Yes | Defaults to `2026 Toyota RAV4 Hybrid LE` |
| `scheduled_pickup_at` | `timestamptz` | Yes | Approved operational pickup time |
| `actual_pickup_at` | `timestamptz` | No | Actual pickup time |
| `actual_dropoff_at` | `timestamptz` | No | Actual completion time |
| `flight_status_note` | `text` | No | Known delay/change facts; no guessed status |
| `passenger_ready_at` | `timestamptz` | No | Customer-reported readiness time |
| `pickup_meeting_instructions` | `text` | No | Jason-approved operational instructions |
| `waiting_details` | `text` | No | Factual waiting record; no automatic fee calculation |
| `parking_details` | `text` | No | Parking reason/known actual amount if applicable |
| `toll_details` | `text` | No | Known toll facts if applicable |
| `extra_stop_outcome` | `text` | No | Actual stop notes |
| `completion_notes` | `text` | No | Operational completion notes |
| `incident_or_exception_notes` | `text` | No | Factual safety/operational exception notes |
| `created_at` | `timestamptz` | Yes | Record creation time |
| `updated_at` | `timestamptz` | Yes | Last change time |

### Relationships

- Each trip belongs to exactly one order; `order_id` is unique.
- A trip may have approvals and notifications linked through its order and optional direct reference.

### Constraints

- A trip may be created as `SCHEDULED` only for a `CONFIRMED` order.
- A trip becomes `COMPLETED` only after service was performed; the related order may then become `COMPLETED`.

## 8. `approvals`

### Purpose

Creates an immutable decision trail for Jason's price, availability, capacity, special-arrangement, schedule-change, cancellation, refund, and booking decisions.

### Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `id` | `uuid` | Yes | Primary key |
| `order_id` | `uuid` | Yes | Foreign key to `orders.id` |
| `quote_id` | `uuid` | No | Relevant quote for price approval |
| `trip_id` | `uuid` | No | Relevant trip for operational approval |
| `approval_type` | `varchar(40)` | Yes | See allowed types below |
| `status` | `varchar(20)` | Yes | `PENDING`, `APPROVED`, `DECLINED`, `SUPERSEDED` |
| `requested_by` | `varchar(20)` | Yes | `AI`, `SYSTEM`, or `JASON` |
| `requested_at` | `timestamptz` | Yes | Request time |
| `request_summary` | `text` | Yes | Facts and exact decision needed |
| `proposed_value` | `jsonb` | No | Structured amount/status/arrangement proposed |
| `decision_by` | `varchar(100)` | No | Authenticated Jason user identifier |
| `decided_at` | `timestamptz` | No | Decision time |
| `decision_value` | `jsonb` | No | Approved/declined structured value |
| `decision_note` | `text` | No | Jason's optional reasoning |
| `created_at` | `timestamptz` | Yes | Immutable creation time |

Allowed approval types:

```text
AVAILABILITY
VEHICLE_CAPACITY
FINAL_PRICE
SPECIAL_ARRANGEMENT
LATE_NIGHT_EARLY_MORNING
WAITING_PARKING_TOLLS_STOPS
CHILD_SEAT
SCHEDULE_CHANGE
BOOKING_CONFIRMATION
CANCELLATION
PAYMENT_REFUND
```

### Relationships

- Many approvals belong to one order.
- An approval may target a quote or trip when applicable.

### Constraints

- Only an authenticated Jason identity may set an approval to `APPROVED` or `DECLINED` in V1.
- Approval rows should be append-only; corrections supersede prior decisions rather than overwriting history.
- `FINAL_PRICE` approval must identify the exact quote and approved amount.
- `BOOKING_CONFIRMATION` approval is distinct from `FINAL_PRICE` approval.

## 9. `notifications`

### Purpose

Tracks phone/dashboard notifications to Jason and operational/customer notification delivery. Supports retries without duplicating business actions.

### Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `id` | `uuid` | Yes | Primary key |
| `customer_id` | `uuid` | No | Related customer |
| `lead_id` | `uuid` | No | Related lead |
| `order_id` | `uuid` | No | Related order |
| `approval_id` | `uuid` | No | Approval request notification |
| `report_id` | `uuid` | No | Report delivery notification |
| `recipient_type` | `varchar(20)` | Yes | `JASON`, `CUSTOMER`, `SYSTEM` |
| `recipient_identifier` | `varchar(255)` | Yes | Internal user, chat ID, email, or masked destination |
| `channel` | `varchar(20)` | Yes | `TELEGRAM`, `DASHBOARD`, `EMAIL`, `SMS`, `CHANNEL_REPLY` |
| `notification_type` | `varchar(40)` | Yes | `NEW_LEAD`, `PRICE_APPROVAL`, `BOOKING_APPROVAL`, `CAPACITY_WARNING`, `FLIGHT_CHANGE`, `UPCOMING_TRIP`, `PAYMENT_UPDATE`, `REPORT_READY`, `OTHER` |
| `priority` | `varchar(10)` | Yes | `LOW`, `NORMAL`, `HIGH`, `URGENT` |
| `title` | `varchar(200)` | Yes | Short notification title |
| `message_body` | `text` | Yes | Avoid unnecessary PII and internal minimums |
| `action_url` | `text` | No | Authenticated dashboard deep link |
| `deduplication_key` | `varchar(255)` | No | Prevent duplicate notifications |
| `status` | `varchar(20)` | Yes | `PENDING`, `SENT`, `DELIVERED`, `FAILED`, `READ`, `CANCELLED` |
| `attempt_count` | `smallint` | Yes | Defaults to 0 |
| `last_error` | `text` | No | Sanitized delivery failure |
| `scheduled_at` | `timestamptz` | No | Future delivery time |
| `sent_at` | `timestamptz` | No | Send time |
| `delivered_at` | `timestamptz` | No | Delivery acknowledgement when supported |
| `read_at` | `timestamptz` | No | Dashboard read/acknowledgement time |
| `created_at` | `timestamptz` | Yes | Record creation time |
| `updated_at` | `timestamptz` | Yes | Last change time |

### Relationships

- Notifications may reference customers, leads, orders, approvals, or reports.
- Foreign keys are optional because system-level notifications may not relate to a customer/order.

### Constraints

- Unique `deduplication_key` when supplied.
- Lock-screen messages should not contain full addresses, phone numbers, internal risk notes, or confidential price floors.

## 10. `reports`

### Purpose

Stores generated daily, weekly, and monthly report metadata, calculation windows, authoritative metrics, and optional AI-written narrative.

### Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `id` | `uuid` | Yes | Primary key |
| `report_type` | `varchar(20)` | Yes | `DAILY`, `WEEKLY`, `MONTHLY`, `AD_HOC` |
| `period_start` | `timestamptz` | Yes | Inclusive reporting window start |
| `period_end` | `timestamptz` | Yes | Exclusive reporting window end |
| `timezone` | `varchar(50)` | Yes | Defaults to `America/Los_Angeles` |
| `status` | `varchar(20)` | Yes | `PENDING`, `GENERATING`, `COMPLETED`, `FAILED` |
| `metrics` | `jsonb` | No | SQL-calculated authoritative results |
| `narrative_summary` | `text` | No | Optional AI-generated explanation based on metrics |
| `knowledge_version` | `varchar(100)` | No | Knowledge revision used for narrative interpretation |
| `generated_at` | `timestamptz` | No | Completion time |
| `delivery_status` | `varchar(20)` | No | `NOT_SCHEDULED`, `PENDING`, `SENT`, `FAILED` |
| `error_message` | `text` | No | Sanitized generation failure |
| `created_at` | `timestamptz` | Yes | Record creation time |
| `updated_at` | `timestamptz` | Yes | Last change time |

### Expected metrics

Daily reports may include:

- New leads and missing-information follow-ups
- Pending Jason approvals
- Upcoming confirmed trips
- Payment follow-ups
- Capacity or schedule risks

Weekly/monthly reports may include:

- Leads by source
- Quote and confirmation conversion
- Completed and cancelled trips
- Approved/completed-trip value
- Common exact-direction routes
- Repeat-customer activity
- Payment status
- Known lost-order reasons

### Relationships

- Reports summarize operational tables through queries; they do not own those source records.
- A report may have multiple notification delivery records.

### Constraints

- `period_end` must be later than `period_start`.
- Metrics must come from database calculations. AI may summarize metrics but must not replace or alter authoritative totals.
- Unique (`report_type`, `period_start`, `period_end`) prevents duplicate scheduled reports.

## Recommended indexes / 推荐索引

| Table | Index |
|---|---|
| `customers` | (`primary_contact_type`, `primary_contact`) |
| `leads` | (`status`, `follow_up_at`), (`priority_level`, `received_at`), (`customer_id`, `received_at`) |
| `conversations` | (`customer_id`, `created_at`), (`lead_id`, `created_at`), (`order_id`, `created_at`), unique (`channel`, `external_message_id`) when present |
| `orders` | (`status`, `pickup_at`), (`customer_id`, `service_date`), (`airport_code`, `service_date`), (`pickup_city`, `destination_city`) |
| `quotes` | unique (`order_id`, `version_number`), (`order_id`, `status`) |
| `payments` | (`order_id`, `status`), (`status`, `updated_at`) |
| `trips` | unique (`order_id`), (`status`, `scheduled_pickup_at`) |
| `approvals` | (`status`, `requested_at`), (`order_id`, `approval_type`), (`quote_id`, `approval_type`) |
| `notifications` | (`status`, `scheduled_at`), unique (`deduplication_key`) when present |
| `reports` | unique (`report_type`, `period_start`, `period_end`) |

## Cross-table business rules / 跨表业务规则

1. AI-generated suggested prices belong in `quotes.suggested_*`; only Jason-approved values belong in `final_quoted_amount`.
2. `orders.status = QUOTED` requires a Jason-approved quote that was sent.
3. `orders.status = CONFIRMED` requires a separate approved `BOOKING_CONFIRMATION` record.
4. Payment alone never confirms a booking.
5. A confirmed order with execution scheduled may create one `trips` row.
6. Completing a trip may move the order to `COMPLETED`; it must not silently change payment status.
7. Unknown route prices remain null and require a `FINAL_PRICE` approval request. Never reverse or interpolate a price.
8. Capacity uncertainty creates a `VEHICLE_CAPACITY` approval request; it must not be hidden by a high priority score.
9. Internal price floors, risk reasoning, and private notes must never be copied to customer-visible conversations or notifications.
10. Every material price, status, schedule, capacity, cancellation, or refund decision should be traceable to a timestamped approval or message.
11. `customers.preferred_language` controls communication language only. Current-message language has priority, and the field must never influence pricing, risk, acceptance, or order priority.

## Phase 1 minimum implementation / Phase 1 最小范围

The Phase 1 application should implement all ten tables but may initially use only:

- Manual and Google website lead intake
- Customer and conversation records
- One order per trip leg
- Quote drafts and Jason final-price approval
- Payment-status tracking without payment processing
- Jason booking approval
- Telegram/dashboard notifications
- Basic daily report records

Facebook and other direct channel integrations, hosted payments, live flight data, and richer reports can use the same schema later without replacing the core model.
