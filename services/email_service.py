import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")


def send_email(to_email: str, subject: str, body: str):
    if not to_email:
        print("No email provided, skipping email send.")
        return

    msg = MIMEMultipart()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")


def send_tournament_winner_email(to_email: str, tournament_name: str, prize: int, currency_type: str):
    subject = f"Congratulations! You won {tournament_name}"
    body = (
        f"Hey champion!\n\n"
        f"You won the tournament \"{tournament_name}\"!\n"
        f"Your prize: {prize} {currency_type}\n\n"
        f"Thanks for playing Coin Toss!"
    )
    send_email(to_email, subject, body)