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

    email_subject = f"Renewal reminder: {subject_subscription_name}"

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
            background-color: #f3f6fb;
            font-family: "Segoe UI", Roboto, Arial, sans-serif;
            color: #0f172a;
        }}

        .preheader {{
            display: none !important;
            visibility: hidden;
            opacity: 0;
            color: transparent;
            height: 0;
            width: 0;
            overflow: hidden;
            mso-hide: all;
        }}

        .wrapper {{
            width: 100%;
            padding: 32px 16px;
        }}

        .container {{
            max-width: 640px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 20px;
            overflow: hidden;
            border: 1px solid #e5eaf1;
            box-shadow: 0 20px 45px rgba(15, 23, 42, 0.08);
        }}

        .hero {{
            padding: 36px 36px 28px;
            background: #1d4ed8;
            background-image:
                radial-gradient(circle at top right, rgba(255,255,255,0.18), transparent 30%),
                linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%);
            color: #ffffff;
        }}

        .eyebrow {{
            display: inline-block;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            padding: 7px 10px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.14);
            margin-bottom: 16px;
            color: #ffffff;
        }}

        .hero h1 {{
            margin: 0 0 10px;
            font-size: 28px;
            line-height: 1.2;
            font-weight: 700;
            color: #ffffff;
        }}

        .hero p {{
            margin: 0;
            font-size: 15px;
            line-height: 1.65;
            color: rgba(255, 255, 255, 0.88);
            max-width: 500px;
        }}

        .content {{
            padding: 32px 36px 24px;
        }}

        .content p {{
            margin: 0 0 16px;
            font-size: 15px;
            line-height: 1.7;
            color: #334155;
        }}

        .summary-card {{
            margin: 24px 0;
            border: 1px solid #e7edf5;
            border-radius: 16px;
            background: #fbfdff;
            overflow: hidden;
        }}

        .summary-header {{
            padding: 16px 18px;
            border-bottom: 1px solid #e7edf5;
            background: #f8fbff;
        }}

        .summary-header span {{
            font-size: 13px;
            font-weight: 700;
            color: #1e3a8a;
            letter-spacing: 0.02em;
        }}

        .details {{
            width: 100%;
            border-collapse: collapse;
        }}

        .details td {{
            padding: 15px 18px;
            font-size: 14px;
            border-bottom: 1px solid #edf2f7;
            vertical-align: middle;
        }}

        .details tr:last-child td {{
            border-bottom: none;
        }}

        .label {{
            width: 38%;
            color: #64748b;
            font-weight: 600;
        }}

        .value {{
            color: #0f172a;
            font-weight: 700;
            text-align: right;
        }}

        .highlight-box {{
            margin: 24px 0 10px;
            padding: 18px 18px;
            border-radius: 14px;
            background: linear-gradient(180deg, #f8fbff 0%, #f1f7ff 100%);
            border: 1px solid #dbeafe;
        }}

        .highlight-box strong {{
            display: block;
            font-size: 14px;
            color: #1d4ed8;
            margin-bottom: 8px;
        }}

        .highlight-box p {{
            margin: 0;
            color: #334155;
            font-size: 14px;
            line-height: 1.65;
        }}

        .button-wrap {{
            padding-top: 8px;
            padding-bottom: 8px;
        }}

        .button {{
            display: inline-block;
            padding: 13px 20px;
            border-radius: 10px;
            background: #0f172a;
            color: #ffffff !important;
            text-decoration: none;
            font-size: 14px;
            font-weight: 700;
        }}

        .footer {{
            padding: 0 36px 32px;
        }}

        .footer p {{
            margin: 0;
            font-size: 12px;
            line-height: 1.6;
            color: #94a3b8;
        }}

        @media only screen and (max-width: 600px) {{
            .hero,
            .content,
            .footer {{
                padding-left: 22px !important;
                padding-right: 22px !important;
            }}

            .hero h1 {{
                font-size: 24px !important;
            }}

            .details td {{
                display: block;
                width: 100% !important;
                text-align: left !important;
                padding-top: 10px;
                padding-bottom: 10px;
            }}

            .value {{
                text-align: left !important;
                padding-top: 0 !important;
            }}
        }}
    </style>
</head>
<body>
    <div class="preheader">
        Your subscription to {safe_subscription_name} is renewing soon.
    </div>

    <div class="wrapper">
        <div class="container">
            <div class="hero">
                <div class="eyebrow">Subscription Reminder</div>
                <h1>Your renewal is coming up</h1>
                <p>
                    A quick heads-up so you can review your upcoming charge and stay in control of your recurring payments.
                </p>
            </div>

            <div class="content">
                <p>Hello {safe_full_name},</p>

                <p>
                    This is a reminder that <strong>{safe_subscription_name}</strong> is scheduled to renew soon.
                    Here is a summary of the upcoming billing:
                </p>

                <div class="summary-card">
                    <div class="summary-header">
                        <span>Renewal details</span>
                    </div>

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
                </div>

                <div class="highlight-box">
                    <strong>Friendly reminder</strong>
                    <p>
                        If you no longer plan to keep this subscription, make sure to cancel it before the renewal date
                        to avoid the next charge.
                    </p>
                </div>

                <div class="button-wrap">
                    <a href="#" class="button">Review subscription</a>
                </div>
            </div>

            <div class="footer">
                <p>
                    This is an automated message from Subscription Monolith. Please do not reply to this email.
                </p>
            </div>
        </div>
    </div>
</body>
</html>
""".strip()

    return email_subject, email_html