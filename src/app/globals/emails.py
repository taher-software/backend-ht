import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from src.settings import settings


def send_email(to_email, name, verification_link):
    # Email content
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <style>
        .button {{
            background-color: #8000ff;
            border: none;
            color: white;
            padding: 15px 32px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin: 4px 2px;
            cursor: pointer;
            border-radius: 4px;
        }}
    </style>
</head>
<body style="background-color: rgb(113,110,251)">
    <p style="font-family: Arial, sans-serif;padding-top: 5% ;text-align: center;color: white;margin-bottom:0;padding-bottom:0;font-size:10px">Email not displaying correctly? View it in your browser.</p>
    <div style="margin-left: 20%;border-bottom: 2px solid yellow;font-family: Arial, sans-serif; width:60% ;padding: 20px;background-color: #fff">
        <img src="https://drive.google.com/uc?export=view&id=1XmhvIdB8lc-34sRtN8wDvcPqU6PXdkgd" alt="bodor_icon" style="text-align: center; width:60%;margin-left:20%">
        <p style="color: black">Hi {name},</p>
        <p style="color: black">To start using Bodor app, just click the verify email button below:</p>
        <a style="margin-left: 35%;background-color: rgb(152,114,251);text-align: center;text-transform: capitalize" href="{verification_link}" class="button">Verify Your Email</a>
        <p style="color: black">Questions about Bodor app? Check out our <a href="https://your-help-center-url">Help Center</a>.</p>
        <p style="color: black">Take control of your hotel's service quality with Bodor..</p>
        <p style="color: black">Thank you,<br>Bodor Company Team</p>
        
    </div>
    <div style="display: flex; margin-left:45%; margin-top: 2.5%">
        <a style="margin-right: 1.25%" href="https://www.facebook.com/?locale=fr_FR"><img  width="20px"  src="https://i.pinimg.com/originals/1f/fa/fe/1ffafe24a94a7dbaa4133f1b6604f3d4.jpg" alt="bodor_icon"></a>
        <a href="https://www.facebook.com/?locale=fr_FR" style="margin-bottom: 2.5%"> <img width="20px"  src="https://i.pinimg.com/564x/45/4d/f2/454df2bcf8e66c01c3885c03373a7cf4.jpg" alt="bodor_icon"> </a>
    </div>
</body>
</html>
""".format(
        name=name, verification_link=verification_link
    )

    # Create message container
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Verify Your Email"
    msg["From"] = settings.mail_username
    msg["To"] = to_email

    # Attach HTML content
    msg.attach(MIMEText(html_content, "html"))

    # Send the email via SMTP server
    # try:
    smtp = smtplib.SMTP("smtp.gmail.com", 587)  # Use your SMTP server
    smtp.starttls()
    smtp.login(
        settings.mail_username, settings.mail_pwd
    )  # Replace with your credentials
    smtp.sendmail(settings.mail_username, to_email, msg.as_string())
    smtp.quit()
    return True
    # except Exception as e:
    #     print(f"Failed to send email: {str(e)}")
    #     return False
