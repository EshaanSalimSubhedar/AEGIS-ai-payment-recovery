import os
from typing import Optional

from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

class MessagingError(Exception):
    pass

class TwilioSMSDispatcher:
    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
    ):
        self.account_sid = account_sid or TWILIO_ACCOUNT_SID
        self.auth_token = auth_token or TWILIO_AUTH_TOKEN
        self.from_number = from_number or TWILIO_PHONE_NUMBER
        self.client = None

        if (
            self.account_sid
            and self.auth_token
            and self.from_number
        ):
            self.client = Client(
                self.account_sid,
                self.auth_token,
            )

    def send(
        self,
        to_number: str,
        message: str,
    ) -> str:
        if not to_number:
            raise MessagingError(
                "Recipient phone number is missing."
            )

        if not message:
            raise MessagingError(
                "Cannot send an empty message."
            )

        if not self.client:
            raise MessagingError(
                "Twilio credentials are not configured."
            )

        try:
            response = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number,
            )
            return response.sid
        except Exception as exc:
            raise MessagingError(
                f"Twilio SMS failed: {exc}"
            ) from exc

class ChannelDispatcher:
    def __init__(
        self,
        sms_dispatcher: Optional[
            TwilioSMSDispatcher
        ] = None,
    ):
        self.sms_dispatcher = (
            sms_dispatcher
            or TwilioSMSDispatcher()
        )

    def send(
        self,
        channel: str,
        recipient: str,
        message: str,
    ) -> str:
        if channel == "twilio_sms":
            return self.sms_dispatcher.send(
                to_number=recipient,
                message=message,
            )

        raise MessagingError(
            f"Unsupported messaging channel: {channel}"
        )

_dispatcher: Optional[ChannelDispatcher] = None

def get_channel_dispatcher() -> ChannelDispatcher:
    global _dispatcher

    if _dispatcher is None:
        _dispatcher = ChannelDispatcher()

    return _dispatcher

def send_message(
    customer_contact: str,
    message: str,
    **kwargs,
) -> str:
    dispatcher = get_channel_dispatcher()

    return dispatcher.send(
        channel="twilio_sms",
        recipient=customer_contact,
        message=message,
    )