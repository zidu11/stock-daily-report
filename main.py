import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header

import yfinance as yf


# ============================================================
# 配置
# ============================================================

WATCHLIST = {
    "NVDA": "NVIDIA",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "GOOGL": "Alphabet",
    "AMZN": "Amazon",
    "META": "Meta",
    "TSLA": "Tesla",
}

MARKET_INDICES = {
    "^GSPC": "S&P 500",
    "^IXIC": "NASDAQ",
    "^DJI": "Dow Jones",
}

OTHER_MARKETS = {
    "GC=F": "Gold",
    "CL=F": "Crude Oil",
    "BTC-USD": "Bitcoin",
    "CAD=X": "USD/CAD",
}


# ============================================================
# 获取数据
# ============================================================

def get_market_data(symbol):
    """
    获取股票/指数最近约一个月的数据。
    """

    try:
        ticker = yf.Ticker(symbol)

        data = ticker.history(
            period="1mo",
            interval="1d",
            auto_adjust=False
        )

        if data.empty:
            return None

        # 删除没有收盘价的行
        data = data.dropna(subset=["Close"])

        if data.empty:
            return None

        latest_close = float(data["Close"].iloc[-1])

        result = {
            "price": latest_close,
            "change_1d": None,
            "change_5d": None,
            "change_20d": None,
            "date": data.index[-1],
        }

        # 1日涨跌
        if len(data) >= 2:
            previous = float(data["Close"].iloc[-2])
            result["change_1d"] = percent_change(
                previous,
                latest_close
            )

        # 5日涨跌
        if len(data) >= 6:
            previous = float(data["Close"].iloc[-6])
            result["change_5d"] = percent_change(
                previous,
                latest_close
            )

        # 20日涨跌
        if len(data) >= 21:
            previous = float(data["Close"].iloc[-21])
            result["change_20d"] = percent_change(
                previous,
                latest_close
            )

        return result

    except Exception as e:
        print(f"获取 {symbol} 数据失败: {e}")
        return None


def percent_change(old, new):
    if old == 0:
        return None

    return (new - old) / old * 100


# ============================================================
# 格式化
# ============================================================

def format_price(price):
    if price is None:
        return "-"

    if price >= 1000:
        return f"{price:,.0f}"

    if price >= 100:
        return f"{price:,.2f}"

    return f"{price:,.2f}"


def format_percent(value):
    if value is None:
        return "-"

    if value > 0:
        return f"+{value:.2f}%"

    return f"{value:.2f}%"


def percent_class(value):
    if value is None:
        return ""

    if value > 0:
        return "positive"

    if value < 0:
        return "negative"

    return "neutral"


# ============================================================
# HTML 表格
# ============================================================

def build_table(items):
    html = """
    <table>
        <thead>
            <tr>
                <th>名称</th>
                <th>价格</th>
                <th>1日</th>
                <th>5日</th>
                <th>20日</th>
            </tr>
        </thead>
        <tbody>
    """

    for symbol, name, data in items:
        if data is None:
            html += f"""
            <tr>
                <td><strong>{symbol}</strong><br>
                    <span class="name">{name}</span>
                </td>
                <td colspan="4">数据暂时不可用</td>
            </tr>
            """
            continue

        html += f"""
        <tr>
            <td>
                <strong>{symbol}</strong><br>
                <span class="name">{name}</span>
            </td>

            <td>
                {format_price(data["price"])}
            </td>

            <td class="{percent_class(data["change_1d"])}">
                {format_percent(data["change_1d"])}
            </td>

            <td class="{percent_class(data["change_5d"])}">
                {format_percent(data["change_5d"])}
            </td>

            <td class="{percent_class(data["change_20d"])}">
                {format_percent(data["change_20d"])}
            </td>
        </tr>
        """

    html += """
        </tbody>
    </table>
    """

    return html


# ============================================================
# 找出涨跌幅最大的股票
# ============================================================

def get_summary(stock_data):
    valid = []

    for symbol, name, data in stock_data:
        if data and data["change_1d"] is not None:
            valid.append(
                (
                    symbol,
                    name,
                    data["change_1d"]
                )
            )

    if not valid:
        return "今天暂时没有足够的数据生成涨跌摘要。"

    best = max(valid, key=lambda x: x[2])
    worst = min(valid, key=lambda x: x[2])

    best_text = (
        f"今日关注列表中涨幅最大的是 "
        f"<strong>{best[0]} ({best[1]})</strong>，"
        f"上涨 <strong>{best[2]:.2f}%</strong>。"
    )

    worst_text = (
        f"跌幅最大的是 "
        f"<strong>{worst[0]} ({worst[1]})</strong>，"
        f"下跌 <strong>{abs(worst[2]):.2f}%</strong>。"
    )

    return best_text + "<br>" + worst_text


# ============================================================
# 生成邮件
# ============================================================

def build_email():
    now = datetime.now()

    date_string = now.strftime("%Y-%m-%d")

    # ------------------------------
    # 指数
    # ------------------------------

    indices = []

    for symbol, name in MARKET_INDICES.items():
        data = get_market_data(symbol)
        indices.append((symbol, name, data))

    # ------------------------------
    # 其他市场
    # ------------------------------

    other_markets = []

    for symbol, name in OTHER_MARKETS.items():
        data = get_market_data(symbol)
        other_markets.append((symbol, name, data))

    # ------------------------------
    # 股票
    # ------------------------------

    stocks = []

    for symbol, name in WATCHLIST.items():
        data = get_market_data(symbol)
        stocks.append((symbol, name, data))

    summary = get_summary(stocks)

    # ------------------------------
    # HTML
    # ------------------------------

    html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">

    <head>

        <meta charset="UTF-8">

        <style>

            body {{
                margin: 0;
                padding: 0;
                background: #f5f7fa;
                font-family:
                    -apple-system,
                    BlinkMacSystemFont,
                    "Segoe UI",
                    Arial,
                    sans-serif;
                color: #222;
            }}

            .container {{
                max-width: 720px;
                margin: 30px auto;
                background: white;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            }}

            .header {{
                padding: 28px;
                background: #1f2937;
                color: white;
            }}

            .header h1 {{
                margin: 0 0 8px 0;
                font-size: 25px;
            }}

            .header p {{
                margin: 0;
                opacity: 0.75;
                font-size: 14px;
            }}

            .section {{
                padding: 24px 28px;
            }}

            .section h2 {{
                margin-top: 0;
                font-size: 19px;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 14px;
            }}

            th {{
                text-align: right;
                padding: 10px 6px;
                color: #666;
                border-bottom: 2px solid #eee;
            }}

            th:first-child {{
                text-align: left;
            }}

            td {{
                padding: 12px 6px;
                text-align: right;
                border-bottom: 1px solid #eee;
            }}

            td:first-child {{
                text-align: left;
            }}

            .name {{
                color: #888;
                font-size: 12px;
            }}

            .positive {{
                color: #16803c;
                font-weight: bold;
            }}

            .negative {{
                color: #d12c2c;
                font-weight: bold;
            }}

            .neutral {{
                color: #666;
            }}

            .summary {{
                background: #f8fafc;
                padding: 16px;
                border-radius: 8px;
                line-height: 1.8;
            }}

            .footer {{
                padding: 20px 28px;
                background: #f8f8f8;
                color: #888;
                font-size: 12px;
                line-height: 1.6;
            }}

        </style>

    </head>

    <body>

        <div class="container">

            <div class="header">

                <h1>📈 每日股市简报</h1>

                <p>{date_string}</p>

            </div>


            <div class="section">

                <h2>🌎 主要指数</h2>

                {build_table(indices)}

            </div>


            <div class="section">

                <h2>💰 其他市场</h2>

                {build_table(other_markets)}

            </div>


            <div class="section">

                <h2>📊 我的关注股票</h2>

                {build_table(stocks)}

            </div>


            <div class="section">

                <h2>🔎 今日摘要</h2>

                <div class="summary">

                    {summary}

                </div>

            </div>


            <div class="footer">

                数据来源：Yahoo Finance / yfinance<br>

                本邮件仅用于信息参考，不构成投资建议。

            </div>

        </div>

    </body>

    </html>
    """

    return html


# ============================================================
# 发送邮件
# ============================================================

def send_email(html):
    sender = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]
    receiver = os.environ["EMAIL_TO"]

    today = datetime.now().strftime("%Y-%m-%d")

    subject = f"📈 每日股市简报 - {today}"

    message = MIMEMultipart("alternative")

    message["From"] = sender
    message["To"] = receiver
    message["Subject"] = Header(
        subject,
        "utf-8"
    )

    text = (
        f"每日股市简报 - {today}\n\n"
        "请使用支持 HTML 的邮件客户端查看完整内容。"
    )

    message.attach(
        MIMEText(
            text,
            "plain",
            "utf-8"
        )
    )

    message.attach(
        MIMEText(
            html,
            "html",
            "utf-8"
        )
    )

    print("正在连接 163 SMTP...")

    with smtplib.SMTP_SSL(
        "smtp.163.com",
        465,
        timeout=30
    ) as server:

        server.login(
            sender,
            password
        )

        server.sendmail(
            sender,
            receiver,
            message.as_string()
        )

    print("邮件发送成功！")


# ============================================================
# 主程序
# ============================================================

def main():

    print("=" * 60)
    print("每日股市简报开始生成")
    print("=" * 60)

    html = build_email()

    send_email(html)

    print("=" * 60)
    print("任务完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
