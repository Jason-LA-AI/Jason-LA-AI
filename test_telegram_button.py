from app.services.telegram_notifier import send_telegram_notification


send_telegram_notification(
    """
📩 测试审核

客户:
测试客户

路线:
Rowland Heights → LAX

AI回复:
您好，我是 Jason。
这是审核按钮测试。
""",
    approval_id="test123",
)