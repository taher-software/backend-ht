import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from src.settings import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def send_email(to_email, name, verification_link):
    """
    Send email verification to a new user.

    Args:
        to_email: Recipient email address
        name: User's name for personalization
        verification_link: Unique verification URL

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    # Email content with modern, professional template
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #8000ff 0%, #9B59B6 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 600;
        }}
        .header p {{
            margin: 10px 0 0 0;
            font-size: 14px;
            opacity: 0.9;
        }}
        .content {{
            padding: 40px 30px;
        }}
        .greeting {{
            font-size: 18px;
            color: #333;
            margin-bottom: 20px;
        }}
        .message {{
            font-size: 15px;
            color: #555;
            line-height: 1.6;
            margin-bottom: 30px;
        }}
        .button-container {{
            text-align: center;
            margin: 30px 0;
        }}
        .verify-button {{
            background: linear-gradient(135deg, #8000ff 0%, #9B59B6 100%);
            color: white;
            padding: 15px 40px;
            text-decoration: none;
            border-radius: 6px;
            display: inline-block;
            font-size: 16px;
            font-weight: 600;
            transition: transform 0.2s;
        }}
        .verify-button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(128, 0, 255, 0.3);
        }}
        .info-box {{
            background-color: #f8f9fa;
            border-left: 4px solid #8000ff;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .info-box p {{
            margin: 0;
            color: #666;
            font-size: 14px;
        }}
        .features {{
            margin: 30px 0;
        }}
        .feature-item {{
            display: flex;
            align-items: start;
            margin-bottom: 15px;
        }}
        .feature-icon {{
            color: #8000ff;
            font-size: 20px;
            margin-right: 10px;
            min-width: 24px;
        }}
        .feature-text {{
            color: #555;
            font-size: 14px;
            line-height: 1.5;
        }}
        .footer {{
            background-color: #f8f9fa;
            padding: 30px;
            text-align: center;
        }}
        .footer p {{
            margin: 5px 0;
            font-size: 13px;
            color: #666;
        }}
        .social-links {{
            margin-top: 20px;
        }}
        .social-links a {{
            display: inline-block;
            margin: 0 10px;
            text-decoration: none;
        }}
        .social-links img {{
            width: 32px;
            height: 32px;
            border-radius: 50%;
            transition: transform 0.2s;
        }}
        .social-links img:hover {{
            transform: scale(1.1);
        }}
        .divider {{
            border: 0;
            height: 1px;
            background: linear-gradient(to right, transparent, #ddd, transparent);
            margin: 30px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏨 Welcome to Bodor</h1>
            <p>Hotel Service Quality Management Platform</p>
        </div>

        <div class="content">
            <p class="greeting">Hi {name},</p>

            <p class="message">
                Welcome to Bodor! We're excited to have you on board. To get started and access all the powerful
                features of our platform, please verify your email address.
            </p>

            <div class="button-container">
                <a href="{verification_link}" class="verify-button">✓ Verify Your Email</a>
            </div>

            <div class="info-box">
                <p><strong>⏱️ This link expires in 60 minutes</strong></p>
                <p>If you didn't create an account with Bodor, you can safely ignore this email.</p>
            </div>

            <hr class="divider">

            <div class="features">
                <h3 style="color: #333; margin-bottom: 20px;">What you can do with Bodor:</h3>

                <div class="feature-item">
                    <span class="feature-icon">📊</span>
                    <span class="feature-text">Monitor and improve your hotel's service quality in real-time</span>
                </div>

                <div class="feature-item">
                    <span class="feature-icon">📱</span>
                    <span class="feature-text">Send automated guest satisfaction surveys and notifications</span>
                </div>

                <div class="feature-item">
                    <span class="feature-icon">🍽️</span>
                    <span class="feature-text">Manage meal menus and dining service notifications</span>
                </div>

                <div class="feature-item">
                    <span class="feature-icon">👥</span>
                    <span class="feature-icon">Collaborate with your team and track performance metrics</span>
                </div>
            </div>

            <p class="message">
                If you have any questions or need assistance, please don't hesitate to reach out to our support team.
            </p>

            <p style="color: #333; margin-top: 30px;">
                Best regards,<br>
                <strong>The Bodor Team</strong>
            </p>
        </div>

        <div class="footer">
            <p><strong>Bodor - Hotel Service Quality Management</strong></p>
            <p>Elevate your hotel's service quality with intelligent automation</p>

            <div class="social-links">
                <a href="https://www.facebook.com" target="_blank" title="Follow us on Facebook">
                    <img src="https://i.pinimg.com/originals/1f/fa/fe/1ffafe24a94a7dbaa4133f1b6604f3d4.jpg" alt="Facebook">
                </a>
                <a href="https://www.instagram.com" target="_blank" title="Follow us on Instagram">
                    <img src="https://i.pinimg.com/564x/45/4d/f2/454df2bcf8e66c01c3885c03373a7cf4.jpg" alt="Instagram">
                </a>
            </div>

            <p style="margin-top: 20px; font-size: 11px; color: #999;">
                © {datetime.now().year} Bodor. All rights reserved.
            </p>
        </div>
    </div>
</body>
</html>
"""

    try:
        # Create message container
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Verify Your Email - Bodor"
        msg["From"] = f"Bodor <{settings.mail_username}>"
        msg["To"] = to_email

        # Attach HTML content
        msg.attach(MIMEText(html_content, "html"))

        # Send the email via SMTP server
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(settings.mail_username, settings.mail_pwd)
            smtp.sendmail(settings.mail_username, to_email, msg.as_string())

        logger.info(f"Verification email sent successfully to {to_email}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {str(e)}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error occurred while sending email to {to_email}: {str(e)}")
        return False
    except Exception as e:
        logger.error(
            f"Failed to send verification email to {to_email}: {str(e)}", exc_info=True
        )
        return False


def send_account_confirmation_email(
    to_email: str, hotel_name: str, username: str, password: str
):
    """
    Send account confirmation email with login credentials to hotel admin.

    Args:
        to_email: Recipient email address
        hotel_name: Name of the hotel/namespace
        username: Login username (phone number)
        password: Plain text password (temporary)

    Returns:
        bool: True if email sent successfully, False otherwise

    Raises:
        Exception: If email sending fails
    """
    # Get app store details from settings
    web_url = str(settings.application_url)
    app_store_name = settings.app_store_app_name or "Bodor Hotel Manager"
    play_store_name = settings.play_store_app_name or "Bodor Hotel Manager"
    app_store_url = str(settings.app_store_url) if settings.app_store_url else "#"
    play_store_url = str(settings.play_store_url) if settings.play_store_url else "#"

    # Email content with modern, professional template
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #8000ff 0%, #9B59B6 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 600;
        }}
        .header p {{
            margin: 10px 0 0 0;
            font-size: 14px;
            opacity: 0.9;
        }}
        .content {{
            padding: 40px 30px;
        }}
        .greeting {{
            font-size: 18px;
            color: #333;
            margin-bottom: 20px;
        }}
        .message {{
            font-size: 15px;
            color: #555;
            line-height: 1.6;
            margin-bottom: 30px;
        }}
        .credentials-box {{
            background-color: #f8f9fa;
            border-left: 4px solid #8000ff;
            padding: 20px;
            margin: 30px 0;
            border-radius: 4px;
        }}
        .credentials-box h3 {{
            margin: 0 0 15px 0;
            color: #333;
            font-size: 16px;
        }}
        .credential-item {{
            display: flex;
            margin-bottom: 12px;
            align-items: center;
        }}
        .credential-label {{
            font-weight: 600;
            color: #666;
            min-width: 100px;
        }}
        .credential-value {{
            color: #8000ff;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            background-color: #fff;
            padding: 8px 12px;
            border-radius: 4px;
            border: 1px solid #e0e0e0;
        }}
        .button-container {{
            text-align: center;
            margin: 30px 0;
        }}
        .login-button {{
            background: linear-gradient(135deg, #8000ff 0%, #9B59B6 100%);
            color: white;
            padding: 15px 40px;
            text-decoration: none;
            border-radius: 6px;
            display: inline-block;
            font-size: 16px;
            font-weight: 600;
            transition: transform 0.2s;
        }}
        .login-button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(128, 0, 255, 0.3);
        }}
        .info-box {{
            background-color: #e8f4fd;
            border-left: 4px solid #2196F3;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .info-box p {{
            margin: 0;
            color: #666;
            font-size: 14px;
        }}
        .app-downloads {{
            margin: 30px 0;
            text-align: center;
        }}
        .app-downloads h3 {{
            color: #333;
            margin-bottom: 20px;
            font-size: 18px;
        }}
        .app-buttons {{
            display: flex;
            justify-content: center;
            gap: 15px;
            flex-wrap: wrap;
        }}
        .app-button {{
            display: inline-block;
            background-color: #000;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            transition: transform 0.2s;
        }}
        .app-button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }}
        .app-button .store-icon {{
            font-size: 20px;
            margin-right: 8px;
        }}
        .features {{
            margin: 30px 0;
        }}
        .feature-item {{
            display: flex;
            align-items: start;
            margin-bottom: 15px;
        }}
        .feature-icon {{
            color: #8000ff;
            font-size: 20px;
            margin-right: 10px;
            min-width: 24px;
        }}
        .feature-text {{
            color: #555;
            font-size: 14px;
            line-height: 1.5;
        }}
        .footer {{
            background-color: #f8f9fa;
            padding: 30px;
            text-align: center;
        }}
        .footer p {{
            margin: 5px 0;
            font-size: 13px;
            color: #666;
        }}
        .divider {{
            border: 0;
            height: 1px;
            background: linear-gradient(to right, transparent, #ddd, transparent);
            margin: 30px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎉 Welcome to Bodor!</h1>
            <p>Your Account is Ready</p>
        </div>

        <div class="content">
            <p class="greeting">Dear {hotel_name} Team,</p>

            <p class="message">
                Congratulations! Your hotel management account has been successfully confirmed and activated.
                You can now log in to start feeding your data and engage your team to leverage our comprehensive
                hotel service quality management solution.
            </p>

            <div class="credentials-box">
                <h3>🔐 Your Login Credentials</h3>
                <div class="credential-item">
                    <span class="credential-label">Username:</span>
                    <span class="credential-value">{username}</span>
                </div>
                <div class="credential-item">
                    <span class="credential-label">Password:</span>
                    <span class="credential-value">{password}</span>
                </div>
            </div>

            <div class="info-box">
                <p><strong>🔒 Security Note:</strong> You can change your password anytime when you log in to the app for enhanced security.</p>
            </div>

            <div class="button-container">
                <a href="{web_url}" class="login-button">🌐 Access Web Dashboard</a>
            </div>

            <hr class="divider">

            <div class="app-downloads">
                <h3>📱 Download Our Mobile App</h3>
                <p style="color: #666; margin-bottom: 20px;">Manage your hotel on the go with our mobile applications</p>
                <div class="app-buttons">
                    <a href="{app_store_url}" class="app-button">
                        <span class="store-icon"></span>
                        Download on App Store
                        <br><small>{app_store_name}</small>
                    </a>
                    <a href="{play_store_url}" class="app-button">
                        <span class="store-icon">▶</span>
                        Get it on Google Play
                        <br><small>{play_store_name}</small>
                    </a>
                </div>
            </div>

            <hr class="divider">

            <div class="features">
                <h3 style="color: #333; margin-bottom: 20px;">🚀 Get Started with Bodor:</h3>

                <div class="feature-item">
                    <span class="feature-icon">📊</span>
                    <span class="feature-text"><strong>Set Up Your Dashboard:</strong> Configure your hotel profile and customize settings to match your operational needs</span>
                </div>

                <div class="feature-item">
                    <span class="feature-icon">👥</span>
                    <span class="feature-text"><strong>Invite Your Team:</strong> Add staff members and assign roles to collaborate effectively</span>
                </div>

                <div class="feature-item">
                    <span class="feature-icon">📱</span>
                    <span class="feature-text"><strong>Launch Guest Surveys:</strong> Start collecting real-time feedback to improve service quality</span>
                </div>

                <div class="feature-item">
                    <span class="feature-icon">🍽️</span>
                    <span class="feature-text"><strong>Manage Menus:</strong> Upload meal menus and automate dining notifications for guests</span>
                </div>

                <div class="feature-item">
                    <span class="feature-icon">📈</span>
                    <span class="feature-text"><strong>Track Performance:</strong> Monitor service metrics and team performance in real-time</span>
                </div>
            </div>

            <p class="message">
                If you have any questions or need assistance getting started, our support team is here to help you every step of the way.
            </p>

            <p style="color: #333; margin-top: 30px;">
                Best regards,<br>
                <strong>The Bodor Team</strong>
            </p>
        </div>

        <div class="footer">
            <p><strong>Bodor - Hotel Service Quality Management</strong></p>
            <p>Elevate your hotel's service quality with intelligent automation</p>
            <p style="margin-top: 20px; font-size: 11px; color: #999;">
                © {datetime.now().year} Bodor. All rights reserved.
            </p>
        </div>
    </div>
</body>
</html>
"""

    try:
        # Create message container
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Welcome to Bodor - {hotel_name} Account Activated"
        msg["From"] = f"Bodor <{settings.mail_username}>"
        msg["To"] = to_email

        # Attach HTML content
        msg.attach(MIMEText(html_content, "html"))

        # Send the email via SMTP server
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(settings.mail_username, settings.mail_pwd)
            smtp.sendmail(settings.mail_username, to_email, msg.as_string())

        logger.info(f"Account confirmation email sent successfully to {to_email}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {str(e)}")
        raise Exception(f"Failed to send confirmation email: SMTP authentication error")
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error occurred while sending email to {to_email}: {str(e)}")
        raise Exception(f"Failed to send confirmation email: {str(e)}")
    except Exception as e:
        logger.error(
            f"Failed to send confirmation email to {to_email}: {str(e)}", exc_info=True
        )
        raise Exception(f"Failed to send confirmation email: {str(e)}")


def send_account_under_review_email(to_email: str, hotel_name: str):
    """
    Send notification email to user that their account is under review.

    Args:
        to_email: User's email address
        hotel_name: Name of the hotel from registration

    Raises:
        Exception: If email sending fails
    """
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 600;
        }}
        .content {{
            padding: 40px 30px;
        }}
        .greeting {{
            font-size: 18px;
            color: #333;
            margin-bottom: 20px;
        }}
        .message {{
            font-size: 15px;
            color: #555;
            line-height: 1.6;
            margin-bottom: 20px;
        }}
        .info-box {{
            background-color: #e3f2fd;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .info-box h3 {{
            margin-top: 0;
            color: #333;
            font-size: 16px;
        }}
        .info-box p {{
            margin: 5px 0;
            color: #555;
        }}
        .timeline {{
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            margin: 20px 0;
        }}
        .timeline p {{
            color: #555;
            margin: 0;
        }}
        .footer {{
            background-color: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #999;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Account Under Review</h1>
        </div>

        <div class="content">
            <p class="greeting">Dear Hotel Owner,</p>

            <p class="message">
                Thank you for registering <strong>{hotel_name}</strong> with Bodor Hotel Management System.
            </p>

            <div class="info-box">
                <h3>📋 Your Registration is Being Reviewed</h3>
                <p>We have received your registration and it is currently under review by our team.</p>
            </div>

            <p class="message">
                We carefully verify all new registrations to ensure the security and quality of our platform.
                This is a standard procedure for all new accounts.
            </p>

            <div class="timeline">
                <p><strong>What happens next?</strong></p>
                <p style="margin-top: 10px;">Our team will review your registration details and contact you very soon with the next steps.</p>
            </div>

            <p class="message">
                We appreciate your patience and look forward to welcoming you to the Bodor platform.
            </p>

            <p class="message">
                If you have any questions in the meantime, please don't hesitate to reach out to our support team.
            </p>

            <p class="message">
                Best regards,<br>
                <strong>The Bodor Team</strong>
            </p>
        </div>

        <div class="footer">
            <p>© {datetime.now().year} Bodor. All rights reserved.</p>
            <p>This is an automated message, please do not reply directly to this email.</p>
        </div>
    </div>
</body>
</html>
"""

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = settings.mail_username
        msg["To"] = to_email
        msg["Subject"] = "Your Bodor Account is Under Review"

        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)

        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(settings.mail_username, settings.mail_pwd)
            smtp.sendmail(settings.mail_username, to_email, msg.as_string())

        logger.info(f"Account under review email sent to {to_email}")

    except Exception as e:
        logger.error(
            f"Failed to send account under review email to {to_email}: {str(e)}",
            exc_info=True,
        )
        raise Exception(f"Failed to send account under review email: {str(e)}")


def send_suspicious_account_alert_to_commercial(
    hotel_name: str, user_email: str, country: str, city: str
):
    """
    Send alert email to commercial team about suspicious account requiring review.

    Args:
        hotel_name: Name of the hotel from registration
        user_email: Email of the user who registered
        country: Country from registration
        city: City from registration

    Raises:
        Exception: If email sending fails
    """
    commercial_emails = settings.commercial_email_list

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #ff4757 0%, #e84118 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 600;
        }}
        .urgent-badge {{
            background-color: #fff;
            color: #ff4757;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            display: inline-block;
            margin-top: 10px;
        }}
        .content {{
            padding: 40px 30px;
        }}
        .alert-message {{
            font-size: 16px;
            color: #333;
            margin-bottom: 20px;
            font-weight: 600;
        }}
        .message {{
            font-size: 15px;
            color: #555;
            line-height: 1.6;
            margin-bottom: 20px;
        }}
        .details-box {{
            background-color: #fff3cd;
            border-left: 4px solid #ff4757;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .details-box h3 {{
            margin-top: 0;
            color: #333;
            font-size: 16px;
            margin-bottom: 15px;
        }}
        .detail-row {{
            display: flex;
            margin-bottom: 10px;
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .detail-row:last-child {{
            border-bottom: none;
        }}
        .detail-label {{
            font-weight: 600;
            color: #333;
            min-width: 140px;
        }}
        .detail-value {{
            color: #555;
        }}
        .action-box {{
            background-color: #e8f4f8;
            padding: 20px;
            border-radius: 6px;
            margin: 20px 0;
        }}
        .action-box h3 {{
            margin-top: 0;
            color: #333;
            font-size: 16px;
        }}
        .action-box ul {{
            margin: 10px 0;
            padding-left: 20px;
        }}
        .action-box li {{
            color: #555;
            margin-bottom: 8px;
        }}
        .footer {{
            background-color: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #999;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ Suspicious Account Alert</h1>
            <span class="urgent-badge">URGENT REVIEW REQUIRED</span>
        </div>

        <div class="content">
            <p class="alert-message">A new registration has been flagged for review.</p>

            <p class="message">
                A registration attempt has failed automated verification checks and requires immediate attention from the commercial team.
            </p>

            <div class="details-box">
                <h3>📋 Account Details:</h3>
                <div class="detail-row">
                    <div class="detail-label">Hotel Name:</div>
                    <div class="detail-value">{hotel_name}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">User Email:</div>
                    <div class="detail-value">{user_email}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Country:</div>
                    <div class="detail-value">{country}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">City:</div>
                    <div class="detail-value">{city}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Detection Time:</div>
                    <div class="detail-value">{datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}</div>
                </div>
            </div>

            <div class="action-box">
                <h3>Required Actions:</h3>
                <ul>
                    <li>Review the registration details for accuracy and authenticity</li>
                    <li>Verify the hotel information through available channels</li>
                    <li>Contact the applicant at {user_email} if additional information is needed</li>
                    <li>Approve or reject the registration based on your findings</li>
                </ul>
            </div>

            <p class="message">
                Please prioritize this review to ensure a timely response to the applicant.
            </p>

            <p class="message">
                <strong>The Bodor Security Team</strong>
            </p>
        </div>

        <div class="footer">
            <p>© {datetime.now().year} Bodor. All rights reserved.</p>
            <p>This is an automated security alert from the Bodor platform.</p>
        </div>
    </div>
</body>
</html>
"""

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = settings.mail_username
        msg["To"] = ", ".join(commercial_emails)
        msg["Subject"] = f"🚨 URGENT: Suspicious Account Review Required - {hotel_name}"

        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)

        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(settings.mail_username, settings.mail_pwd)
            smtp.sendmail(settings.mail_username, commercial_emails, msg.as_string())

        logger.info(
            f"Suspicious account alert sent to commercial team for {hotel_name} ({user_email})"
        )

    except Exception as e:
        logger.error(
            f"Failed to send suspicious account alert to commercial team: {str(e)}",
            exc_info=True,
        )
        raise Exception(f"Failed to send suspicious account alert: {str(e)}")


def send_account_rejection_email(to_email: str, hotel_name: str):
    """
    Send notification email when account registration is rejected.

    Args:
        to_email: User's email address
        hotel_name: Name of the hotel from registration

    Raises:
        Exception: If email sending fails
    """
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 600;
        }}
        .content {{
            padding: 40px 30px;
        }}
        .greeting {{
            font-size: 18px;
            color: #333;
            margin-bottom: 20px;
        }}
        .message {{
            font-size: 15px;
            color: #555;
            line-height: 1.6;
            margin-bottom: 20px;
        }}
        .info-box {{
            background-color: #f8f9fa;
            border-left: 4px solid #6c757d;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .info-box p {{
            margin: 5px 0;
            color: #555;
        }}
        .support-box {{
            background-color: #e3f2fd;
            padding: 20px;
            border-radius: 6px;
            margin: 20px 0;
            text-align: center;
        }}
        .support-box p {{
            margin: 5px 0;
            color: #555;
        }}
        .footer {{
            background-color: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #999;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Registration Update</h1>
        </div>

        <div class="content">
            <p class="greeting">Dear Hotel Owner,</p>

            <p class="message">
                Thank you for your interest in registering <strong>{hotel_name}</strong> with Bodor Hotel Management System.
            </p>

            <div class="info-box">
                <p>After careful review of your registration, we regret to inform you that we are unable to proceed with your account at this time.</p>
            </div>

            <p class="message">
                This decision was made based on our verification process, which ensures the accuracy and authenticity of all registrations on our platform.
            </p>

            <p class="message">
                We understand this may be disappointing, and we appreciate the time you took to complete the registration process.
            </p>

            <div class="support-box">
                <p><strong>Have questions or believe this is an error?</strong></p>
                <p>Please don't hesitate to contact our support team for further assistance.</p>
                <p>We're here to help clarify any concerns you may have.</p>
            </div>

            <p class="message">
                We appreciate your understanding and wish you the best in your business endeavors.
            </p>

            <p class="message">
                Best regards,<br>
                <strong>The Bodor Team</strong>
            </p>
        </div>

        <div class="footer">
            <p>© {datetime.now().year} Bodor. All rights reserved.</p>
            <p>This is an automated message, please do not reply directly to this email.</p>
        </div>
    </div>
</body>
</html>
"""

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = settings.mail_username
        msg["To"] = to_email
        msg["Subject"] = "Registration Update - Bodor Hotel Management"

        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)

        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(settings.mail_username, settings.mail_pwd)
            smtp.sendmail(settings.mail_username, to_email, msg.as_string())

        logger.info(f"Account rejection email sent to {to_email}")

    except Exception as e:
        logger.error(
            f"Failed to send account rejection email to {to_email}: {str(e)}",
            exc_info=True,
        )
        raise Exception(f"Failed to send account rejection email: {str(e)}")
