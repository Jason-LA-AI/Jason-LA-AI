# Route Pricing Expansion / 路线价格扩展

## Purpose / 用途

This internal route registry organizes actual pricing examples and unknown routes for the future AI assistant of **Jason在洛杉矶**.

- Base / 营运基地：**Rowland Heights, California**
- Vehicle / 车辆：**2026 Toyota RAV4 Hybrid LE**
- Main airports / 主要机场：LAX, ONT, SNA, BUR, LGB

The direction shown is part of the route. Prices must not be reversed, interpolated, averaged, or transferred to another origin or destination.

## Documented operating examples / 已记录实际路线

These are internal historical reference ranges, not fixed or guaranteed customer fares.

| Origin | Destination | Time/category | Internal reference | Status |
|---|---|---|---:|---|
| Rowland Heights | LAX | Daytime | **$130–$150** | Documented example |
| Rowland Heights | LAX | Late night/early morning | **$140–$160** | Documented example; exact hours undefined |
| Rowland Heights | ONT | Time category not documented | **$60–$80** | Documented example |
| ONT | Garden Grove | Time category not documented | **around $100 / 约 $100** | Approximate documented example |
| LAX | Irvine | Time category not documented | **$160–$180** | Documented example |
| LAX | San Diego | Time category not documented | **$260–$320** | Documented long-distance example |

For Rowland Heights → LAX, the internal minimum acceptable amount remains documented in `pricing_rules.md`. It is confidential and must not be shown or suggested to customers.

## Common airport-route gaps / 常用机场路线缺口

The following routes are within the known service context, but no price has been documented. They are not approved price examples.

| Origin | Destination | Price status |
|---|---|---|
| LAX | Rowland Heights | **Unknown — Jason approval required** |
| ONT | Rowland Heights | **Unknown — Jason approval required** |
| Rowland Heights | SNA | **Unknown — Jason approval required** |
| SNA | Rowland Heights | **Unknown — Jason approval required** |
| Rowland Heights | BUR | **Unknown — Jason approval required** |
| BUR | Rowland Heights | **Unknown — Jason approval required** |
| Rowland Heights | LGB | **Unknown — Jason approval required** |
| LGB | Rowland Heights | **Unknown — Jason approval required** |
| ONT | San Diego | **Unknown — Jason approval required** |
| San Diego | Rowland Heights | **Unknown — Jason approval required** |

Other routes involving Los Angeles County, Orange County, the Inland Empire, San Diego, or an airport also require Jason approval unless the exact direction appears in the documented table.

## Exact-match rules / 路线匹配规则

Before using a documented range internally, verify:

1. Origin and destination match the documented direction.
2. Exact pickup and destination addresses are known or clearly identified as pending.
3. Date and exact pickup time are known.
4. Airport, airline, flight number, and arrival/departure direction are known when applicable.
5. Passenger and luggage details have been reviewed.
6. Extra stops, waiting, parking, tolls, child seats, and special requests have been identified.
7. Jason has reviewed availability and the final customer-facing price.

A city-level match is only an internal starting point. Exact addresses and trip conditions may change Jason's decision.

## Unknown-price procedure / 未知价格处理流程

When the exact route and direction have no documented price:

1. Do not calculate from distance, driving time, mileage, nearby routes, or a reverse route.
2. Do not quote a broad range merely to keep the conversation moving.
3. Collect all required trip and capacity information.
4. Write in the internal summary: **“No documented price — Jason to decide / 无现有价格参考，需 Jason 决定.”**
5. List possible price factors without assigning amounts.
6. Wait for Jason to approve a specific customer-facing fare.

## Route review template / 路线审核模板

```text
ROUTE PRICE REVIEW / 路线价格审核

Direction: [exact origin → exact destination]
Date and pickup time:
Airport/flight details:
Passengers and luggage:
Extra stops/special requests:
Late night/early morning consideration:
Waiting/parking/tolls:

Exact documented route match: [yes | no]
Documented internal reference: [range | none]
Limitations: [time category, approximate example, exact addresses, other]
Vehicle suitability: [likely comfortable | needs confirmation | not recommended]

Jason decisions required:
- Availability:
- Approved customer price:
- Additional-fee treatment:
- Booking acceptance:
```

## Adding future route experience / 新增路线经验

When Jason provides a real route price, record:

- Exact direction
- General origin and destination
- Date or operating context when useful
- Daytime, late-night/early-morning, or unspecified category
- Actual range or approximate amount exactly as Jason states it
- Whether parking, tolls, waiting, or stops were included, if known
- Any passenger/luggage condition that materially affected the trip

Do not convert a single experience into a universal fixed rate unless Jason explicitly defines it as one.

## Prohibited actions / 禁止事项

The AI must never invent prices, reverse a route price, interpolate between routes, apply a per-mile formula that Jason has not supplied, expose internal minimums, guarantee a range, or confirm a booking without Jason's approval.
