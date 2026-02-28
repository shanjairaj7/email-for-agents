"""
Transactional SMS — Order Notifications
A pattern library for sending personalized order update SMS messages.

Usage:
    from notifications import send_order_confirmation, send_shipping_update
    send_order_confirmation(order=order_dict, customer_phone="+14155551234")
"""

import os

from commune import CommuneClient
from openai import OpenAI

commune = CommuneClient(api_key=os.environ["COMMUNE_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
PHONE_NUMBER_ID = os.environ["COMMUNE_PHONE_NUMBER_ID"]


def _generate_sms(system_prompt: str, user_content: str) -> str:
    """Call OpenAI to generate a personalized SMS under 160 characters."""
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        max_tokens=80,
    )
    return response.choices[0].message.content.strip()


def send_order_confirmation(order: dict, customer_phone: str) -> str:
    """Send SMS when order is placed. Returns the message SID."""
    items_str = ", ".join(order.get("items", []))
    total = order.get("total", "")
    order_id = order.get("order_id", "your order")

    message = _generate_sms(
        system_prompt=(
            "Write a friendly order confirmation SMS under 160 characters. "
            "Include the order ID, item names (abbreviated if needed), and total. "
            "Mention it ships in 1-3 business days. No hashtags. Plain text only."
        ),
        user_content=f"Order ID: {order_id}\nItems: {items_str}\nTotal: ${total}",
    )

    result = commune.sms.send(
        to=customer_phone,
        body=message,
        phone_number_id=PHONE_NUMBER_ID,
    )
    return result.id


def send_shipping_update(order: dict, tracking: dict, customer_phone: str) -> str:
    """Send SMS when order ships. Returns the message SID."""
    order_id = order.get("order_id", "your order")
    items_str = ", ".join(order.get("items", []))
    carrier = tracking.get("carrier", "the carrier")
    tracking_number = tracking.get("tracking_number", "")
    eta = tracking.get("eta", "soon")

    message = _generate_sms(
        system_prompt=(
            "Write a shipping confirmation SMS under 160 characters. "
            "Include the order ID, carrier name, tracking number, and estimated delivery date. "
            "Keep it informative and upbeat. Plain text only."
        ),
        user_content=(
            f"Order ID: {order_id}\nItems: {items_str}\n"
            f"Carrier: {carrier}\nTracking: {tracking_number}\nETA: {eta}"
        ),
    )

    result = commune.sms.send(
        to=customer_phone,
        body=message,
        phone_number_id=PHONE_NUMBER_ID,
    )
    return result.id


def send_delivery_confirmation(order: dict, customer_phone: str) -> str:
    """Send SMS when order is delivered. Returns the message SID."""
    order_id = order.get("order_id", "your order")
    items_str = ", ".join(order.get("items", []))

    message = _generate_sms(
        system_prompt=(
            "Write a delivery confirmation SMS under 160 characters. "
            "Tell the customer their order arrived. Mention the main item. "
            "Be warm and brief. Invite them to reply with any questions. Plain text only."
        ),
        user_content=f"Order ID: {order_id}\nItems: {items_str}",
    )

    result = commune.sms.send(
        to=customer_phone,
        body=message,
        phone_number_id=PHONE_NUMBER_ID,
    )
    return result.id


def send_delay_notification(order: dict, new_eta: str, customer_phone: str) -> str:
    """Send SMS when order is delayed — AI personalizes the apology. Returns message SID."""
    order_id = order.get("order_id", "your order")
    items_str = ", ".join(order.get("items", []))
    original_eta = order.get("original_eta", "the original date")

    message = _generate_sms(
        system_prompt=(
            "Write a delay notification SMS under 160 characters. "
            "Acknowledge the delay, give the new estimated delivery date, and apologize briefly. "
            "Sound human and genuine, not robotic. No excessive apologies. Plain text only."
        ),
        user_content=(
            f"Order ID: {order_id}\nItems: {items_str}\n"
            f"Original ETA: {original_eta}\nNew ETA: {new_eta}"
        ),
    )

    result = commune.sms.send(
        to=customer_phone,
        body=message,
        phone_number_id=PHONE_NUMBER_ID,
    )
    return result.id


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Dummy data — replace with your actual order objects
    order = {
        "order_id": "ORD-8821",
        "items": ["Blue hoodie (L)", "Beanie"],
        "total": 89.00,
        "original_eta": "Feb 25",
    }
    tracking = {
        "carrier": "UPS",
        "tracking_number": "1Z9999W99999999999",
        "eta": "Feb 28",
    }
    customer_phone = "+14155550000"  # replace with a real number

    print("Sending order confirmation...")
    sid = send_order_confirmation(order=order, customer_phone=customer_phone)
    print(f"  Sent. SID: {sid}")

    print("Sending shipping update...")
    sid = send_shipping_update(order=order, tracking=tracking, customer_phone=customer_phone)
    print(f"  Sent. SID: {sid}")

    print("Sending delivery confirmation...")
    sid = send_delivery_confirmation(order=order, customer_phone=customer_phone)
    print(f"  Sent. SID: {sid}")

    print("Sending delay notification...")
    sid = send_delay_notification(order=order, new_eta="Mar 2", customer_phone=customer_phone)
    print(f"  Sent. SID: {sid}")
