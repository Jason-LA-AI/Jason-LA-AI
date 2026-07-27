# Order Priority Scoring / 订单优先评分

## Purpose / 用途

This internal scoring system helps the future AI assistant for **Jason在洛杉矶** decide which inquiries deserve faster review. It supports queue ordering; it does not replace safety checks or Jason's business judgment.

- Base / 营运基地：**Rowland Heights, California**
- Vehicle / 车辆：**2026 Toyota RAV4 Hybrid LE**

A high score means **review sooner**, not “automatically accept.” A low score does not authorize an automatic rejection. Jason must approve availability, vehicle fit when relevant, final price, special arrangements, and booking confirmation.

## Core safeguards / 核心规则

1. Apply safety and feasibility overrides before calculating priority.
2. Score only supported facts. Unknown factors receive **0**, not a guessed positive or negative value.
3. Do not treat a documented price range as proof that a route is profitable.
4. Do not infer schedule convenience without comparing the trip with Jason's actual schedule.
5. Do not infer repeat-customer potential from age, language, source, location, or other personal characteristics.
6. Customer source—Xiaohongshu, Facebook, Google website, or referral—does not receive points by itself.
7. Do not expose the score, profitability judgment, internal minimum, or negative notes to customers.

## Safety and feasibility overrides / 安全及可行性优先规则

These conditions override the numerical score:

### `AVOID_RECOMMENDED`

Use when documented facts show a likely unsafe or unsuitable trip, including:

- Five adults with many large suitcases in the RAV4
- Likely unsafe seating, restraint, visibility, luggage, or vehicle loading
- A request requiring violation of airport or safety instructions
- A special requirement that cannot be safely supported

Do not continue ranking it as an ordinary opportunity. Give Jason the objective reason and recommend declining the current vehicle/trip arrangement.

### `INFORMATION_REQUIRED`

Use when missing or conflicting information prevents a responsible route, capacity, schedule, or price review.

- Ask only for missing details.
- Keep the order at `WAITING_FOR_INFORMATION`.
- Recalculate after the customer replies.

### `JASON_REVIEW_REQUIRED`

Use when the trip may be feasible but depends on Jason's judgment, including schedule conflicts, uncertain capacity, unknown pricing, long distance, late-night timing, waiting, extra stops, child seats, or special arrangements.

The numeric score may still help order Jason's review queue, but it does not resolve the issue.

## 1. Scoring framework / 评分框架

Start each inquiry at **50 points**. Add positive factors and subtract negative factors. Clamp the final numerical score to **0–100**.

```text
Priority score = 50 + positive points − negative points
Final score = minimum 100, maximum 0
```

Record the evidence for every nonzero item.

### Positive factors / 加分因素

| Factor | Points | Evidence required |
|---|---:|---|
| Route matches primary service context | +8 | Route is within Los Angeles County, Orange County, Inland Empire, or involves a main airport: LAX, ONT, SNA, BUR, LGB |
| Exact-direction documented route example | +5 | Exact origin → destination appears in current pricing knowledge |
| Good vehicle fit | +12 | 1–3 passengers with normal, clearly described luggage and no known special-fit concern |
| Reasonable passenger/luggage details | +8 | Counts and sizes are complete and do not create a capacity warning |
| Profitable route confirmed by Jason | +10 | Jason explicitly identifies this specific trip or route as profitable |
| Convenient schedule confirmed by Jason | +10 | Jason confirms that timing fits his current schedule without problematic conflict |
| Repeat-customer potential supported | +5 | Existing customer history, an actual repeat inquiry, or Jason's specific assessment supports it |
| Clear and complete customer communication | +7 | Required trip information is complete, consistent, and customer is reachable |

Maximum positive adjustment: **+60**, but the final score is capped at 100.

#### Positive-factor limits

- A route with a documented price earns the exact-route points, but not profitability points unless Jason confirms profitability.
- “Repeat-customer potential” is not the same as a guaranteed repeat booking.
- A referral source alone does not prove customer quality or repeat potential.
- Good vehicle fit remains guidance, not a capacity guarantee.

### Negative factors / 扣分因素

| Factor | Points | Evidence required |
|---|---:|---|
| Vehicle capacity needs confirmation | −15 | Four passengers with multiple large suitcases, uncertain dimensions, child-seat fit, or similar concern |
| Vehicle combination not recommended | −35 plus override | Five adults with many large suitcases or another likely unsafe/unsuitable combination |
| Extremely late hours | −10 | Jason classifies the exact trip time as extremely late |
| Long waiting risk | −10 | Planned/likely waiting is identified and materially affects the trip |
| Low price request | −10 | Customer requests an amount Jason identifies as commercially unacceptable for that exact trip |
| Poor information quality | −15 | Multiple required details are missing, materially unclear, or conflicting |
| Moderate operational difficulty | −8 | One caution factor such as long distance, international-arrival uncertainty, extra stop, parking, toll, or special item |
| High operational difficulty | −15 | Multiple complexity factors or a material feasibility concern |

Use either moderate or high operational-difficulty points for the same group of issues, not both.

#### Negative-factor limits

- “Late night,” “early morning,” and especially “extremely late” do not yet have documented exact hours. Jason must classify the time before those points apply.
- Do not label a request “low price” merely because it is below the top of a documented range. Jason must determine whether it is unacceptable.
- Waiting risk requires a factual reason; do not assume all airport pickups involve chargeable long waiting.
- Poor information quality describes the inquiry record, not the customer's character.

## Information-completeness check / 资料完整性检查

Before awarding clear-communication points, verify:

- Customer name and working contact
- Exact service date, including year
- Pickup time and whether it is landing time or passenger-ready time
- Airport, airline, flight number, and domestic/international status when applicable
- Exact pickup location and destination
- Passenger count, including adults and children
- Large luggage, carry-ons, dimensions, and oversized items
- Child-seat requirements
- One-way/round trip, stops, waiting, and special requests

If material items are missing, apply `INFORMATION_REQUIRED`. Apply poor-information points when the omissions are substantial or the facts conflict.

## 2. Priority levels / 优先等级

| Score | Priority | Meaning | AI action |
|---:|---|---|---|
| 85–100 | `P1 — IMMEDIATE REVIEW` | Exceptionally strong, complete, operationally simple inquiry | Put near the top of Jason's review queue; do not accept automatically |
| 70–84 | `P2 — HIGH PRIORITY` | Good potential with limited unresolved issues | Prepare a concise Jason approval summary promptly |
| 50–69 | `P3 — STANDARD` | Normal inquiry requiring ordinary review or follow-up | Process in normal order and resolve missing facts |
| 30–49 | `P4 — LOW PRIORITY / CAUTION` | Weak readiness or meaningful operational concerns | Resolve facts, explain risks, and request Jason review if still feasible |
| 0–29 | `P5 — AVOID / EXCEPTION REVIEW` | Severe fit, feasibility, or commercial concern | Apply overrides; recommend decline or explicit exception review |

### Queue-order tie breakers / 同分排序规则

When two inquiries have the same priority score, review them in this order:

1. Safety- or schedule-sensitive inquiry needing a prompt decision
2. Complete inquiry over incomplete inquiry
3. Confirmed schedule fit over unknown schedule fit
4. Comfortable vehicle fit over uncertain fit
5. Exact-direction documented price over unknown price
6. Earlier received inquiry

The AI must not use protected personal characteristics, language, customer source, or assumed wealth as a tie breaker.

## Response urgency is separate / 回复紧急度与商业优先级分开

Some low-scoring inquiries still need a fast response:

- An unsafe vehicle combination should receive a prompt, respectful decline or clarification.
- A flight change affecting a confirmed trip requires immediate operational attention.
- An incomplete inquiry should receive a timely request for missing information.

Do not confuse “respond quickly” with “accept first.”

## 3. Examples / 示例

These examples show the mechanics. They are not real acceptance or profitability decisions.

### Example A — Complete ONT → Garden Grove inquiry

Assumptions for illustration: exact trip details are complete, 2 passengers have normal documented luggage, no special requests, and no schedule judgment has yet been provided.

| Item | Points |
|---|---:|
| Base | 50 |
| Main airport/service context | +8 |
| Exact-direction documented example | +5 |
| Good vehicle fit | +12 |
| Reasonable passenger/luggage details | +8 |
| Clear and complete communication | +7 |
| Profitability | 0 — not documented |
| Schedule convenience | 0 — Jason has not reviewed it |
| **Total** | **90 — P1** |

Recommendation: **Immediate Jason review**, not automatic acceptance. Jason must approve availability and the final price; “around $100” remains an approximate internal example.

### Example B — LAX → San Diego, 3 passengers, incomplete luggage details

| Item | Points |
|---|---:|
| Base | 50 |
| Service context/documented long-distance route | +8 |
| Exact-direction documented example | +5 |
| Vehicle fit | 0 — luggage unknown |
| Reasonable luggage details | 0 |
| Poor information quality | −15 |
| Moderate operational difficulty: long distance | −8 |
| **Total** | **40 — P4** |

Override: `INFORMATION_REQUIRED`, followed by `JASON_REVIEW_REQUIRED`. Recommendation: collect luggage and full trip details, then recalculate. The $260–$320 internal range is not a guaranteed fare.

### Example C — LAX pickup, 5 adults and 6 large suitcases, late night

| Item | Points |
|---|---:|
| Base | 50 |
| Main airport/service context | +8 |
| Vehicle combination not recommended | −35 |
| Extremely late hours | 0 unless Jason classifies the exact time |
| Operational difficulty | −15 |
| **Preliminary total** | **8 — P5** |

Override: `AVOID_RECOMMENDED`. Recommendation: advise Jason that the current RAV4 arrangement is unsuitable and recommend declining it. Do not add points for a potentially high fare.

### Example D — “机场接送多少钱？”

| Item | Points |
|---|---:|
| Base | 50 |
| Poor information quality | −15 |
| All other factors | 0 — unknown |
| **Total** | **35 — P4** |

Override: `INFORMATION_REQUIRED`. Recommendation: reply promptly with the required-information questions. The customer may later become high priority after supplying a suitable trip.

### Example E — Repeat customer on a suitable route

Assumptions for illustration: the customer has documented prior completed orders, current details are complete, the trip fits the RAV4, and Jason confirms that the schedule is convenient. Profitability remains unconfirmed.

| Item | Points |
|---|---:|
| Base | 50 |
| Service context | +8 |
| Good vehicle fit | +12 |
| Reasonable passenger/luggage details | +8 |
| Convenient schedule confirmed by Jason | +10 |
| Supported repeat potential | +5 |
| Clear communication | +7 |
| Profitability | 0 — not confirmed |
| **Total** | **100 — P1** |

Recommendation: review immediately, while still requiring Jason's final price and booking approval.

## 4. Rules for Jason approval / Jason 核准规则

### Always requires Jason approval

- Availability and schedule convenience
- Profitability classification
- Whether a customer-requested price is acceptable or too low
- Final customer-facing price
- Vehicle fit when capacity is uncertain
- Late-night, early-morning, waiting, parking, toll, extra-stop, or child-seat handling
- Long-distance and San Diego service
- Special arrangements, exceptions, acceptance, and booking confirmation

### Score-related approval rules

- No score can move an order directly to `QUOTED` or `CONFIRMED`.
- A P1 or P2 inquiry is a queue recommendation only.
- `AVOID_RECOMMENDED` remains a recommendation until Jason decides how to respond.
- Jason may override a score. Record his decision and reason rather than changing facts to make the score fit.
- Recalculate after material changes to route, date/time, passengers, luggage, stops, flight, price request, or special requirements.
- Do not reuse an old score for a new trip, even for a repeat customer.

## Internal scoring template / 内部评分模板

```text
ORDER PRIORITY SCORE / 订单优先评分

Order/lead ID:
Customer/source:
Route/date/time:
Passengers/luggage:

Override check:
- AVOID_RECOMMENDED: [yes/no — reason]
- INFORMATION_REQUIRED: [yes/no — missing items]
- JASON_REVIEW_REQUIRED: [yes/no — decisions]

Base score: 50

Positive factors:
- Service context: [0/+8 — evidence]
- Exact documented route: [0/+5 — evidence]
- Good vehicle fit: [0/+12 — evidence]
- Reasonable passenger/luggage: [0/+8 — evidence]
- Jason-confirmed profitability: [0/+10 — evidence]
- Jason-confirmed schedule convenience: [0/+10 — evidence]
- Supported repeat potential: [0/+5 — evidence]
- Clear communication: [0/+7 — evidence]

Negative factors:
- Capacity needs confirmation: [0/−15 — evidence]
- Vehicle not recommended: [0/−35 — evidence]
- Jason-classified extremely late time: [0/−10 — evidence]
- Long waiting risk: [0/−10 — evidence]
- Jason-classified low price request: [0/−10 — evidence]
- Poor information quality: [0/−15 — evidence]
- Operational difficulty: [0/−8/−15 — evidence]

Final score: [0–100]
Priority level: [P1/P2/P3/P4/P5]
Response urgency:
AI recommendation:
Decisions needed from Jason:
```

## Final boundary / 最终边界

The current knowledge base does not define preferred working hours, daily trip limits, schedule buffers, minimum notice, repeat-customer priority, route profitability, or a universal low-price threshold. Score these items as **0 / unknown** until Jason documents or confirms them for the specific inquiry.
