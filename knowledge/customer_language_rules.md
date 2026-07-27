# Customer Language Rules / 客户语言规则

## Purpose / 用途

This document defines how the future AI assistant for **Jason在洛杉矶** identifies, records, and follows a customer's language preference.

The objective is to make communication natural and respectful. The assistant should follow the customer's current language instead of forcing Chinese, English, or a bilingual response.

## Supported language values / 支持的语言值

Use the following canonical values:

| Stored value | Meaning | Reply style |
|---|---|---|
| `English` | English | Natural English |
| `zh-CN` | Simplified Chinese / 简体中文 | Natural Simplified Chinese |
| `zh-TW` | Traditional Chinese / 繁體中文 | Natural Traditional Chinese |

Do not use a generic `Chinese` value when the assistant can reliably distinguish Simplified and Traditional Chinese.

## 1. Customer language detection / 客户语言识别

### Primary rule: follow the current message

The customer's current message is the strongest signal for the current reply:

- English message → reply in English
- Simplified Chinese message → reply in Simplified Chinese (`zh-CN`)
- Traditional Chinese message → reply in Traditional Chinese (`zh-TW`)

Do not force Chinese because the brand contains Chinese. Do not force English because the business operates in California. Do not automatically send the same message in two languages when one language is clear.

### Detection evidence

Use the writing in the current customer message:

- Predominantly English wording and grammar indicates `English`.
- Predominantly Simplified Chinese characters and wording indicates `zh-CN`.
- Predominantly Traditional Chinese characters and wording indicates `zh-TW`.

The assistant should evaluate the message as a whole. Some characters and expressions are shared across Chinese variants, so a very short message may not provide enough evidence.

### Mixed or ambiguous messages

If the customer mixes languages:

1. Follow the main language of the current message when it is clear.
2. Preserve necessary proper names, airport codes, flight numbers, and addresses in their original form.
3. If no main language is clear, use the saved `preferred_language` when available.
4. If there is no reliable saved preference, ask briefly:

**English:** Would you prefer English, 简体中文, or 繁體中文?

**简体中文：** 请问您希望使用 English、简体中文还是繁體中文沟通？

**繁體中文：** 請問您希望使用 English、简体中文還是繁體中文溝通？

Do not guess the customer's nationality, place of origin, or preferred language from their name, phone number, profile photo, airport, destination, or referral source.

## 2. Communication rules / 沟通规则

### English customer

- Reply in clear, natural English.
- Keep the brand name **Jason在洛杉矶** unchanged.
- Use the English brand name **Jason LA Airport Transportation** when helpful.
- Do not add a Chinese translation unless requested or operationally necessary.

### Simplified Chinese customer (`zh-CN`)

- Reply in natural Simplified Chinese.
- Use Simplified Chinese vocabulary and punctuation consistently.
- Keep airport codes, airline names, flight numbers, addresses, and official proper names accurate.
- Do not switch to Traditional Chinese merely because the customer is using ONT.

### Traditional Chinese customer (`zh-TW`)

- Reply in natural Traditional Chinese.
- Use Traditional Chinese characters and customer-service wording consistently.
- Avoid mechanically converting only a few characters while leaving the rest of the message in Simplified Chinese.
- Keep airport codes, airline names, flight numbers, addresses, and official proper names accurate.

### Current language versus saved preference

Apply this order:

1. An explicit language request in the current message
2. The clear language/script used in the current message
3. The saved `preferred_language`
4. A short clarification question when still uncertain

If the current message clearly changes language, reply in the current language. Do not permanently change the saved preference from one isolated mixed-language message unless the customer explicitly requests the change or a consistent new preference is established.

## 3. Taiwan customer consideration / 台湾客户服务考虑

ONT airport serves many customers connected with Taiwan in Jason's operating experience. The assistant should therefore be prepared to recognize and support Traditional Chinese customers well.

Operational rules:

- When a customer writes in Traditional Chinese, use `zh-TW` and respond in Traditional Chinese.
- Make Traditional Chinese an equal first-class service option in inquiry forms, templates, and future channel integrations.
- Do not assume every ONT customer is Taiwanese or prefers Traditional Chinese.
- Do not infer Taiwan identity from an airport, airline, flight, name, or route.
- Follow the customer's actual language or explicit preference.

## 4. Store language preference / 保存语言偏好

The future customer record should include:

```text
preferred_language
```

Allowed values:

```text
English
zh-CN
zh-TW
```

The value should record a reliable preference, not a demographic assumption.

Recommended supporting metadata for future implementation:

- How the preference was established: `customer_selected`, `customer_requested`, or `language_observed`
- When it was last confirmed
- Whether the current message used a different language without changing the saved preference

These supporting items are recommendations for later schema review; this document does not modify the database design or implement software.

## 5. Customer profile reuse / 客户档案复用

Save the customer's reliable language preference in the customer profile and use it for future communication when the new message does not clearly indicate another language.

Reuse rules:

- Use the saved preference for proactive follow-ups, reminders, quote notices, and booking messages.
- Re-evaluate each incoming message; the current language may temporarily override the saved preference.
- Allow the customer to change their preference at any time.
- Apply profile updates only after verifying that the message belongs to the correct customer.
- Do not copy one customer's preference to another customer in the same group, family, or referral chain.

Language preference does not replace trip verification. Dates, times, routes, passenger counts, luggage, child seats, and special requests must still be reconfirmed for each order.

## 6. Message-generation rules / 消息生成规则

Before sending a customer-facing message, check:

- The output language matches the current message or saved preference.
- Simplified and Traditional Chinese are not mixed unintentionally.
- Dates and times remain unambiguous.
- Airport codes, flights, addresses, prices, and passenger/luggage details are unchanged.
- The translation does not add a guarantee, policy, fee, or service claim.
- Internal pricing floors, risk notes, priority scores, and Jason-only comments are excluded.
- All placeholders have been replaced.

Language adaptation must change expression, not business facts. The same approval and safety rules apply in every language.

## 7. Examples / 示例

### English

Customer:

> How much is an ONT pickup to Rowland Heights?

Assistant response language: `English`

> Thanks for contacting **Jason在洛杉矶 / Jason LA Airport Transportation**. Before Jason can review the trip and fare, could you please provide the travel date, arrival time, airline and flight number, passenger count, luggage details, and your destination address in Rowland Heights?

### Simplified Chinese

Customer:

> 请问ONT接机到罗兰岗多少钱？

Assistant response language: `zh-CN`

> 您好，感谢您联系 **Jason在洛杉矶**。为了让 Jason 核实行程和费用，请提供用车日期、航班到达时间、航空公司及航班号、乘客人数、行李数量和尺寸，以及罗兰岗的具体目的地地址。

### Traditional Chinese

Customer:

> 請問ONT接機到羅蘭崗多少錢？

Assistant response language: `zh-TW`

> 您好，感謝您聯絡 **Jason在洛杉矶**。為了讓 Jason 核實行程和費用，請提供用車日期、航班抵達時間、航空公司及航班號、乘客人數、行李數量和尺寸，以及羅蘭崗的具體目的地地址。

The official brand spelling **Jason在洛杉矶** remains unchanged even when the surrounding message uses Traditional Chinese.

## 8. Marketing considerations / 营销考虑

Future customer acquisition should support language-based targeting without stereotyping customers.

Recommended approach:

- Prepare separate English, Simplified Chinese, and Traditional Chinese campaign content.
- Direct each campaign to a landing page or inquiry form in the matching language.
- Offer an explicit language selector: `English | 简体中文 | 繁體中文`.
- Track campaign language separately from the customer's confirmed `preferred_language`.
- Evaluate inquiries, qualified leads, quotes, confirmed orders, and completed trips by campaign language.
- Include Traditional Chinese campaigns when testing ONT-related customer acquisition.
- Judge performance using actual conversion and completed-trip data, not assumptions about nationality or customer value.

Marketing language must not change pricing, capacity, availability, or approval rules. Customer source and language do not automatically raise or lower business priority.

## 9. AI safeguards / AI 安全规则

The AI must never:

- Force a customer into English or Chinese when their preference is clear
- Treat Simplified and Traditional Chinese as interchangeable in customer-facing replies
- Infer nationality, immigration status, or place of origin from language
- Assume all ONT passengers are from Taiwan
- Change factual trip information during translation
- Translate internal-only business notes into customer-facing content
- Make stronger promises in one language than another
- Use language preference as a reason to change price, acceptance, risk, or order priority

When language is uncertain, ask. When business information is uncertain, follow the normal knowledge-base rules and request the missing facts or Jason's approval.
