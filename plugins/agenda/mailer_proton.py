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
import logging
logger = logging.getLogger(__name__)

class MailerProton:
    """Mailer Proton Service Plugin
    
    Role: Handles email sending via Proton Bridge on Windows Host from WSL.
    
    Methods:
        send_mail(self, config, subject, body, to_email=None, attachment_path=None, debug=False) : Sends an email message with optional attachment via Proton Bridge SMTP server.
        _check_network(self, target_ip, smtp_port) : Checks network connectivity to the SMTP server.
        _build_message(self, config, subject, body, to_email, attachment_path, debug) : Builds the email message with headers and attachments.
        _send_email(self, msg, target_ip, smtp_port, config) : Sends the email via SMTP server.
    """

    def send_mail(self, config, subject, body, to_email=None, attachment_path=None, debug=False):
        start_time = time.time()
        target_ip = config.IP_MAIL
        smtp_port = int(config.PORT_SMTP_MAIL)

        if not self._check_network(target_ip, smtp_port):
            return cfg.RETURN_CODE.ERR

        msg = self._build_message(config, subject, body, to_email, attachment_path, debug)
        if msg is None:
            return cfg.RETURN_CODE.ERR

        success = self._send_email(msg, target_ip, smtp_port, config)
        if debug:
            duration = time.time() - start_time
            logger.info(f"Mail delivered via {target_ip} in {duration:.2f}s")

        return success

    def _check_network(self, target_ip, smtp_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3)
            if s.connect_ex((target_ip, smtp_port)) != 0:
                logger.error(f"[!] Network Error: Windows Host {target_ip}:{smtp_port} is unreachable.")
                logger.error("[!] Fix: Enable 'Allow LAN' in Proton Bridge and open Windows Firewall port 1025.")
                return False
        return True

    def _build_message(self, config, subject, body, to_email, attachment_path, debug):
        msg = MIMEMultipart()
        msg['From'] = f"{config.USERNAME} <{config.USER_MAIL}>"
        msg['To'] = to_email or getattr(config, 'ALTERNATE_MAIL', None) or config.USER_MAIL
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
                if debug:
                    logger.warning(f"Attachment Error: {e}")
                return None
        return msg

    def _send_email(self, msg, target_ip, smtp_port, config):
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            with smtplib.SMTP(target_ip, smtp_port, timeout=10) as server:
                server.starttls(context=context)
                server.login(config.USER_MAIL, config.PWD_MAIL)
                server.send_message(msg)
            return cfg.RETURN_CODE.SUCCESS
        except (smtplib.SMTPAuthenticationError, 
                smtplib.SMTPConnectError, 
                smtplib.SMTPException, 
                Exception) as e:
            logger.error(f"SMTP Error ({type(e).__name__}): {e}")
            return cfg.RETURN_CODE.ERR


if __name__ == "__main__":
    mailer = MailerProton()
    success = mailer.send_mail(
        subject="WSL to Windows Bridge Test",
        body="If you see this, the networking and firewall rules are correct.",
        debug=True
    )
    logger.info(f"Status: {'SUCCESS' if success else 'FAILED'}")
