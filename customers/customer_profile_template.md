# Customer Profile Template / 客户档案模板

Create one profile per customer when ongoing recordkeeping is useful. A customer profile stores contact preferences and relevant history; each trip must still have its own order record.

Only record information needed for customer service and trip operations. Do not store payment-card details, identity-document numbers, immigration information, or unrelated private information.

## 1. Profile control / 档案管理

- Customer ID / 客户编号：
- Profile created date/time / 档案建立日期时间：
- Last updated date/time / 最后更新日期时间：
- Profile status / 档案状态：`active | inactive`

## 2. Customer information / 客户资料

- Name / 姓名：
- Phone or primary contact / 电话或主要联系方式：
- Secondary contact / 备用联系方式：
- Preferred contact method / 首选联系方式：
- Source / 来源：`Xiaohongshu | Facebook | Google website | Referral | Unknown`
- Referrer, if provided by customer / 转介绍人（如客户提供）：
- Language preference / 语言偏好：
- Preferred form of address / 偏好称呼：

## 3. Communication preferences / 沟通偏好

- Preferred language for replies / 回复语言：
- Best known contact time / 合适联系时间：
- Permission or preference for follow-up / 跟进偏好：
- Communication notes / 沟通备注：

Do not infer preferences from demographic assumptions. Record only what the customer communicates or what is operationally observed and appropriate to retain.

## 4. Reusable trip preferences / 可重复使用的行程偏好

- Common pickup city or area / 常用上车城市或区域：
- Common destination or airport / 常用目的地或机场：
- Typical passenger count / 常见乘客人数：
- Typical luggage details / 常见行李情况：
- Child-seat requirement previously stated / 曾说明的儿童座椅需求：
- Accessibility or special requests stated by customer / 客户说明的无障碍或特殊需求：

These are historical preferences, not facts for a new trip. The AI must reconfirm date, route, passengers, luggage, child-seat needs, and special requests for every order.

## 5. Order history / 订单历史

| Order ID | Service date | Route | Final status | Final quoted price | Payment status | Notes |
|---|---|---|---|---:|---|---|
| | | | | | | |

Allowed final or current booking statuses:

`NEW | WAITING_FOR_INFORMATION | QUOTED | WAITING_FOR_JASON_APPROVAL | CONFIRMED | COMPLETED | CANCELLED`

## 6. Service notes / 服务备注

- Confirmed communication preferences / 已确认沟通偏好：
- Prior operational issues relevant to future trips / 与未来行程有关的历史运营情况：
- Customer feedback / 客户反馈：
- Internal notes / 内部备注：

Use factual and respectful language. Do not speculate about the customer or place internal price floors in this profile.

## 7. Current follow-up / 当前跟进

- Open lead ID / 当前线索编号：
- Open order ID / 当前订单编号：
- Last contact date/time / 上次联系日期时间：
- Next action / 下一步：
- Next action owner / 负责人：`AI | Jason | Customer`
- Follow-up date/time / 跟进日期时间：

## AI rules / AI 使用规则

- Verify the customer identity before linking a new inquiry to an existing profile.
- Do not assume that a previous phone number, address, route, passenger count, or luggage arrangement is still current.
- Ask for missing trip information before suggesting a price.
- Do not promise availability, vehicle capacity, price, or confirmation based on customer history.
- Keep suggested prices, approvals, payments, and booking status in the related order record.
- Do not mark an order `CONFIRMED` without Jason's explicit approval.
