import smtplib
import ssl
import time
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email import utils
from pathlib import Path
from config_loader import cfg

class MailerProton:
    """Class to handle email sending via Proton Bridge on the Windows Host from WSL.

    Methods:
        send_mail(subject, body, to_email=None, attachment_path=None, debug=False) : Sends an email message with optional attachment via Proton Bridge SMTP server.
    """

    def send_mail(self, subject, body, to_email=None, attachment_path=None, debug=False):
        start_time = time.time()

        target_ip = cfg.agenda.IP_MAIL
        smtp_port = int(cfg.agenda.PORT_SMTP_MAIL)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3)
            if s.connect_ex((target_ip, smtp_port)) != 0:
                print(f"[!] Network Error: Windows Host {target_ip}:{smtp_port} is unreachable.")
                print("[!] Fix: Enable 'Allow LAN' in Proton Bridge and open Windows Firewall port 1025.")
                return False

        msg = MIMEMultipart()
        msg['From'] = f"{cfg.agenda.USERNAME} <{cfg.agenda.USER_MAIL}>"
        msg['To'] = to_email or cfg.agenda.USER_MAIL
        msg['Subject'] = subject
        msg['Date'] = utils.formatdate(localtime=True)
        msg['Message-ID'] = utils.make_msgid()

        msg.attach(MIMEText(body, 'plain'))

        if attachment_path and Path(attachment_path).exists():
            try:
                with open(attachment_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=Path(attachment_path).name)
                part['Content-Disposition'] = f'attachment; filename="{Path(attachment_path).name}"'
                msg.attach(part)
            except Exception as e:
                if debug: print(f"Attachment Error: {e}")

        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            with smtplib.SMTP(target_ip, smtp_port, timeout=10) as server:
                server.starttls(context=context)
                server.login(cfg.agenda.USER_MAIL, cfg.agenda.PWD_MAIL)
                server.send_message(msg)

            if debug:
                duration = time.time() - start_time
                print(f"Mail delivered via {target_ip} in {duration:.2f}s")

            return True

        except Exception as e:
            print(f"SMTP Error: {e}")
            return False


if __name__ == "__main__":
    mailer = MailerProton()
    success = mailer.send_mail(
        subject="WSL to Windows Bridge Test",
        body="If you see this, the networking and firewall rules are correct.",
        debug=True
    )
    print(f"Status: {'SUCCESS' if success else 'FAILED'}")
