# Order Status Manual / 订单状态手册

## Purpose / 用途

This operational manual defines the booking statuses used by the future AI assistant for **Jason在洛杉矶**. Statuses organize work; they do not authorize the AI to set prices, accept trips, or confirm bookings without Jason.

Use exactly one current booking status per order:

```text
NEW
WAITING_FOR_INFORMATION
QUOTED
WAITING_FOR_JASON_APPROVAL
CONFIRMED
COMPLETED
CANCELLED
```

## Status definitions / 状态定义

### `NEW`

A new inquiry or order record has been created but has not yet been fully reviewed.

- Review the customer's message.
- Identify intent and required trip details.
- Do not quote or confirm.
- Next status is normally `WAITING_FOR_INFORMATION` or `WAITING_FOR_JASON_APPROVAL`.

### `WAITING_FOR_INFORMATION`

The AI cannot prepare a reliable internal review because required customer or trip information is missing, unclear, or conflicting.

- Record exactly what is missing.
- Ask the customer only for information not already supplied.
- Do not invent details or provide a price.
- Move to `WAITING_FOR_JASON_APPROVAL` after the necessary information is collected.

### `WAITING_FOR_JASON_APPROVAL`

The trip information is ready for Jason, or a material decision must be made by Jason.

Jason may need to decide:

- Availability
- Vehicle and luggage suitability
- Suggested or final price
- Late-night, waiting, parking, toll, extra-stop, or child-seat handling
- Schedule or route changes
- Whether the booking can be accepted

This status does not mean the trip is held or confirmed.

### `QUOTED`

Jason approved a customer-facing price and that price was sent to the customer.

- Record the exact final quoted price and time sent.
- Record what the quote includes or excludes when Jason specifies it.
- Wait for the customer's response.
- A quote is not a confirmed booking.
- If trip details change, return the order to `WAITING_FOR_INFORMATION` or `WAITING_FOR_JASON_APPROVAL` as appropriate.

### `CONFIRMED`

Jason explicitly accepted the booking, and the agreed trip details and price were communicated to the customer.

Before using this status, verify:

- Required trip details are complete
- Jason approved availability
- Jason reviewed vehicle suitability when needed
- Jason approved the final quoted price
- Customer accepted the agreed details
- Any special arrangements were approved

Payment does not automatically confirm a booking unless Jason has also approved it. Payment status must be tracked separately.

### `COMPLETED`

The confirmed transportation service has been performed.

- Record completion date and relevant operational notes.
- Record the final payment status separately.
- Do not mark an unperformed or cancelled trip as completed.

### `CANCELLED`

The inquiry or booking will not proceed.

Record, when known:

- Who cancelled: customer, Jason, or unknown
- Cancellation date and time
- Reason stated, without speculation
- Status at time of cancellation
- Payment or refund follow-up required

The knowledge base does not currently define cancellation charges or refund rules. Refer all financial decisions to Jason.

## Recommended status flow / 推荐状态流程

```text
NEW
  ├─ missing details → WAITING_FOR_INFORMATION
  ├─ complete; Jason decision needed → WAITING_FOR_JASON_APPROVAL
  └─ will not proceed → CANCELLED

WAITING_FOR_INFORMATION
  ├─ details complete → WAITING_FOR_JASON_APPROVAL
  └─ will not proceed → CANCELLED

WAITING_FOR_JASON_APPROVAL
  ├─ approved quote sent → QUOTED
  ├─ more details needed → WAITING_FOR_INFORMATION
  └─ declined/not proceeding → CANCELLED

QUOTED
  ├─ Jason and customer finalize booking → CONFIRMED
  ├─ material change → WAITING_FOR_JASON_APPROVAL
  ├─ missing revised details → WAITING_FOR_INFORMATION
  └─ declined/not proceeding → CANCELLED

CONFIRMED
  ├─ service performed → COMPLETED
  ├─ material change requiring review → WAITING_FOR_JASON_APPROVAL
  └─ cancelled → CANCELLED
```

## Status update requirements / 状态更新要求

Every status change should record:

- Previous status
- New status
- Date and time
- Reason
- Person or source responsible for the decision
- Next action and owner

## AI safeguards / AI 安全规则

The AI must never:

- Move an order to `QUOTED` before Jason approves the customer-facing price
- Move an order to `CONFIRMED` without Jason's explicit approval
- Treat a payment, customer request, suggested price, or internal range as confirmation
- Hide missing information or capacity concerns to advance an order
- Guarantee availability, price, pickup timing, luggage fit, or airport access
- Reopen a cancelled order as confirmed without a new Jason review
