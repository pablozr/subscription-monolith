from datetime import date, datetime
from html import escape


MONTH_NAMES_EN = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

BILLING_CYCLE_LABELS = {
    "DAILY": "Daily",
    "WEEKLY": "Weekly",
    "BIWEEKLY": "Biweekly",
    "MONTHLY": "Monthly",
    "YEARLY": "Yearly",
}


def _format_amount(amount: float | int | str | None) -> str:
    if amount is None:
        normalized_amount = 0.0
    else:
        try:
            normalized_amount = float(amount)
        except (TypeError, ValueError):
            normalized_amount = 0.0

    return f"BRL {normalized_amount:,.2f}"


def _format_billing_cycle(cycle: str | None) -> str:
    normalized_cycle = (cycle or "").upper()
    if normalized_cycle in BILLING_CYCLE_LABELS:
        return BILLING_CYCLE_LABELS[normalized_cycle]

    fallback_cycle = (cycle or "Recurring").replace("_", " ").strip()
    return fallback_cycle.title()


def _format_renewal_date(renewal_date: date | datetime | str | None) -> str:
    parsed_date = renewal_date
    if isinstance(parsed_date, datetime):
        parsed_date = parsed_date.date()

    if isinstance(parsed_date, date):
        month_name = MONTH_NAMES_EN[parsed_date.month - 1]
        return f"{month_name} {parsed_date.day:02d}, {parsed_date.year}"

    if parsed_date is None:
        return "-"

    return str(parsed_date)


def build_renewal_reminder_email_content(
    *,
    full_name: str | None,
    subscription_name: str | None,
    amount: float | int | str | None,
    billing_cycle: str | None,
    renewal_date: date | datetime | str | None,
) -> tuple[str, str]:
    normalized_full_name = str(full_name or "").strip() or "there"
    normalized_subscription_name = str(subscription_name or "").strip() or "your subscription"
    subject_subscription_name = " ".join(normalized_subscription_name.splitlines())

    safe_full_name = escape(normalized_full_name)
    safe_subscription_name = escape(normalized_subscription_name)
    formatted_amount = escape(_format_amount(amount))
    formatted_cycle = escape(_format_billing_cycle(billing_cycle))
    formatted_renewal_date = escape(_format_renewal_date(renewal_date))

    email_subject = f"Upcoming renewal: {subject_subscription_name}"

    email_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Renewal Reminder</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            background: #f4f7fb;
            font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
            color: #1f2937;
        }}
        .wrapper {{
            width: 100%;
            padding: 28px 12px;
        }}
        .card {{
            max-width: 620px;
            margin: 0 auto;
            border: 1px solid #dde5ef;
            border-radius: 14px;
            overflow: hidden;
            background: #ffffff;
            box-shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
        }}
        .header {{
            padding: 26px 32px;
            background: linear-gradient(135deg, #1f4f7a 0%, #0d2f4f 100%);
            color: #ffffff;
        }}
        .header small {{
            display: block;
            font-size: 12px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.85;
            margin-bottom: 8px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
        }}
        .content {{
            padding: 28px 32px 24px;
        }}
        .content p {{
            margin: 0 0 16px;
            font-size: 15px;
            line-height: 1.6;
            color: #334155;
        }}
        .details {{
            width: 100%;
            border: 1px solid #e4ebf3;
            border-radius: 10px;
            border-collapse: separate;
            border-spacing: 0;
            margin: 12px 0 22px;
            overflow: hidden;
        }}
        .details td {{
            padding: 12px 14px;
            font-size: 14px;
            border-bottom: 1px solid #edf2f7;
        }}
        .details tr:last-child td {{
            border-bottom: none;
        }}
        .label {{
            width: 38%;
            color: #64748b;
            background: #f8fbff;
            font-weight: 600;
        }}
        .value {{
            color: #0f172a;
            font-weight: 600;
        }}
        .footer {{
            padding: 0 32px 28px;
            font-size: 12px;
            color: #7a8699;
            line-height: 1.5;
        }}
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="card">
            <div class="header">
                <small>Subscription Reminder</small>
                <h1>Your renewal is coming up</h1>
            </div>
            <div class="content">
                <p>Hello {safe_full_name},</p>
                <p>This is a quick reminder that one of your subscriptions is about to renew.</p>

                <table class="details" role="presentation" cellpadding="0" cellspacing="0">
                    <tr>
                        <td class="label">Subscription</td>
                        <td class="value">{safe_subscription_name}</td>
                    </tr>
                    <tr>
                        <td class="label">Amount</td>
                        <td class="value">{formatted_amount}</td>
                    </tr>
                    <tr>
                        <td class="label">Billing cycle</td>
                        <td class="value">{formatted_cycle}</td>
                    </tr>
                    <tr>
                        <td class="label">Renewal date</td>
                        <td class="value">{formatted_renewal_date}</td>
                    </tr>
                </table>

                <p>If you no longer plan to keep this subscription, please cancel it before the renewal date to avoid the next charge.</p>
            </div>
            <div class="footer">
                This is an automated message from Subscription Monolith. Please do not reply to this email.
            </div>
        </div>
    </div>
</body>
</html>
""".strip()

    return email_subject, email_html
