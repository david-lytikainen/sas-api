from decimal import Decimal, ROUND_HALF_UP
import stripe
from flask import current_app
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse
from app.extensions import db
from app.models import Event, EventPayment, User


class StripeService:
    INTRO_EVENT_LIMIT = 2
    INTRO_FIXED_FEE = Decimal("1.00")
    INTRO_PERCENT_FEE = Decimal("5.0")
    STANDARD_FIXED_FEE = Decimal("1.50")
    STANDARD_PERCENT_FEE = Decimal("8.0")

    @staticmethod
    def is_configured() -> bool:
        return bool(current_app.config.get("STRIPE_SECRET_KEY"))

    @staticmethod
    def configure():
        stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")

    @staticmethod
    def require_configured():
        StripeService.configure()

    @staticmethod
    def amount_to_cents(amount) -> int:
        decimal_amount = Decimal(str(amount or "0"))
        return int(
            (decimal_amount * Decimal("100")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )

    @staticmethod
    def cents_to_decimal(total_cents: int) -> Decimal:
        return (Decimal(total_cents) / Decimal("100")).quantize(Decimal("0.01"))

    @staticmethod
    def get_fee_schedule(is_intro_event: bool) -> tuple[Decimal, Decimal]:
        if is_intro_event:
            return StripeService.INTRO_FIXED_FEE, StripeService.INTRO_PERCENT_FEE
        return StripeService.STANDARD_FIXED_FEE, StripeService.STANDARD_PERCENT_FEE

    @staticmethod
    def minimum_ticket_price(is_intro_event: bool) -> Decimal:
        fixed_fee, percent_fee = StripeService.get_fee_schedule(is_intro_event)
        minimum_price = fixed_fee / (Decimal("1") - (percent_fee / Decimal("100")))
        return minimum_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_platform_fee_amount(total_cents: int, is_intro_event: bool) -> int:
        fixed_fee, percent_fee = StripeService.get_fee_schedule(is_intro_event)
        total_amount = StripeService.cents_to_decimal(total_cents)
        fee_amount = fixed_fee + (total_amount * percent_fee / Decimal("100"))
        return int(
            (fee_amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )

    @staticmethod
    def user_can_manage_events(user: User) -> bool:
        if user.role_id == 3:
            return True
        return user.role_id == 2 and bool(user.stripe_connect_onboarding_complete)

    @staticmethod
    def is_intro_event(event: Event) -> bool:
        first_two_event_ids = [
            event_id
            for event_id, in Event.query.filter_by(creator_id=event.creator_id)
            .order_by(Event.created_at.asc(), Event.id.asc())
            .with_entities(Event.id)
            .limit(StripeService.INTRO_EVENT_LIMIT)
            .all()
        ]
        return event.id in first_two_event_ids

    @staticmethod
    def get_or_create_customer(user: User) -> str:
        StripeService.require_configured()
        if user.stripe_customer_id:
            return user.stripe_customer_id

        customer = stripe.Customer.create(
            email=user.email,
            name=f"{user.first_name} {user.last_name}",
            metadata={"user_id": str(user.id)},
        )
        user.stripe_customer_id = customer.id
        db.session.commit()
        return customer.id

    @staticmethod
    def ensure_connected_account(user: User) -> str:
        StripeService.require_configured()
        if user.stripe_connected_account_id:
            return user.stripe_connected_account_id

        account = stripe.Account.create(
            type="express",
            country=current_app.config.get("STRIPE_CONNECT_COUNTRY", "US"),
            email=user.email,
            business_type="individual",
            business_profile={
                "mcc": "7999",
                "product_description": "Hosting a speed dating event",
                **(
                    {"url": current_app.config.get("CLIENT_URL")}
                    if current_app.config.get("CLIENT_URL")
                    and "localhost" not in current_app.config.get("CLIENT_URL")
                    and "127.0.0.1" not in current_app.config.get("CLIENT_URL")
                    else {}
                ),
            },
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
            metadata={"user_id": str(user.id)},
        )
        user.stripe_connected_account_id = account.id
        user.stripe_connect_onboarding_complete = False
        db.session.commit()
        return account.id

    @staticmethod
    def create_connect_onboarding_link(user: User) -> str:
        StripeService.require_configured()
        account_id = StripeService.ensure_connected_account(user)
        account_link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=current_app.config.get("STRIPE_CONNECT_REFRESH_URL"),
            return_url=current_app.config.get("STRIPE_CONNECT_RETURN_URL"),
            type="account_onboarding",
            collection_options={
                "fields": "currently_due",
                "future_requirements": "omit",
            },
        )
        return account_link.url

    @staticmethod
    def sync_connect_status(user: User) -> User:
        StripeService.require_configured()
        if not user.stripe_connected_account_id:
            user.stripe_connect_onboarding_complete = False
            db.session.commit()
            return user

        account = stripe.Account.retrieve(user.stripe_connected_account_id)
        user.stripe_connect_onboarding_complete = bool(
            account.details_submitted
            and account.charges_enabled
            and account.payouts_enabled
        )
        if user.stripe_connect_onboarding_complete and user.role_id == 1:
            user.role_id = 2
        db.session.commit()
        return user

    @staticmethod
    def create_event_registration_checkout(
        event: Event, attendee: User, organizer: User
    ) -> str:
        StripeService.require_configured()
        if organizer.role_id != 3 and not organizer.stripe_connected_account_id:
            raise ValueError("Organizer Stripe account is not set up yet.")

        customer_id = StripeService.get_or_create_customer(attendee)
        unit_amount = StripeService.amount_to_cents(event.price_per_person)
        fee_amount = StripeService.calculate_platform_fee_amount(
            unit_amount, StripeService.is_intro_event(event)
        )

        payment_intent_data = None
        if organizer.role_id != 3:
            payment_intent_data = {
                "application_fee_amount": fee_amount,
                "transfer_data": {
                    "destination": organizer.stripe_connected_account_id,
                },
            }

        session = stripe.checkout.Session.create(
            mode="payment",
            customer=customer_id,
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",  # TODO: make configurable if multi-currency needed
                        "unit_amount": unit_amount,
                        "product_data": {
                            "name": event.name,
                            "description": "Event sign up. Non-refundable through app.",
                        },
                    },
                    "quantity": 1,
                }
            ],
            payment_intent_data=payment_intent_data,
            custom_text={
                "submit": {
                    "message": "Non-refundable through app. Contact event organizer for refund questions."
                }
            },
            success_url=StripeService.append_query_params(
                current_app.config.get("STRIPE_CHECKOUT_SUCCESS_URL").replace(
                    "view=create&", ""
                ),
                {
                    "checkout": "success",
                    "session_id": "{CHECKOUT_SESSION_ID}",
                },
            ),
            cancel_url=StripeService.append_query_params(
                current_app.config.get("STRIPE_CHECKOUT_CANCEL_URL").replace(
                    "view=create&", ""
                ),
                {
                    "checkout": "cancel",
                },
            ),
            metadata={
                "checkout_type": "event_registration",
                "event_id": str(event.id),
                "user_id": str(attendee.id),
                "organizer_user_id": str(organizer.id),
            },
        )
        return session.url

    @staticmethod
    def append_query_params(url: str, params: dict[str, str]) -> str:
        parsed_url = urlparse(url)
        query_items = dict(parse_qsl(parsed_url.query, keep_blank_values=True))
        query_items.update({key: value for key, value in params.items() if value is not None})
        return urlunparse(
            parsed_url._replace(query=urlencode(query_items, quote_via=quote, safe="{}"))
        )

    @staticmethod
    def upsert_checkout_session_payment(session_data: dict) -> EventPayment | None:
        metadata = session_data.get("metadata") or {}
        checkout_type = metadata.get("checkout_type")
        if checkout_type != "event_registration":
            return None

        session_id = session_data.get("id")
        event_id = metadata.get("event_id")
        user_id = metadata.get("user_id")
        organizer_user_id = metadata.get("organizer_user_id")
        if not all([session_id, event_id, user_id, organizer_user_id]):
            return None

        payment = EventPayment.query.filter_by(
            stripe_checkout_session_id=session_id
        ).first()
        if not payment:
            payment = EventPayment(stripe_checkout_session_id=session_id)

        payment.stripe_payment_intent_id = session_data.get("payment_intent")
        payment.event_id = int(event_id)
        payment.user_id = int(user_id)
        payment.organizer_user_id = int(organizer_user_id)
        payment.amount_cents = int(session_data.get("amount_total") or 0)
        payment.currency = (session_data.get("currency") or "usd").lower()
        payment.payment_status = session_data.get("payment_status") or "paid"
        payment.registration_status = payment.registration_status or "pending"

        db.session.add(payment)
        db.session.commit()
        return payment

    @staticmethod
    def retrieve_checkout_session(session_id: str) -> dict:
        StripeService.require_configured()
        return stripe.checkout.Session.retrieve(session_id)

    @staticmethod
    def finalize_event_registration_checkout(session_data: dict) -> dict:
        metadata = session_data.get("metadata") or {}
        if metadata.get("checkout_type") != "event_registration":
            return {"error": "Checkout session is not an event registration session."}

        session_id = session_data.get("id")
        event_id = metadata.get("event_id")
        user_id = metadata.get("user_id")
        if not all([session_id, event_id, user_id]):
            return {"error": "Checkout session is missing required registration metadata."}

        if (session_data.get("payment_status") or "").lower() != "paid":
            return {"error": "Checkout session has not been paid."}

        payment = StripeService.upsert_checkout_session_payment(session_data)
        if payment and payment.registration_status in {
            "registered",
            "registration_failed_refunded",
            "refund_failed",
        }:
            return {
                "message": "Checkout session already processed.",
                "status": payment.registration_status,
            }

        user = User.query.get(int(user_id))
        if user and session_data.get("customer"):
            user.stripe_customer_id = session_data.get("customer")
            db.session.commit()

        from app.services.event_service import EventService

        registration_response = EventService.register_for_event(
            int(event_id),
            int(user_id),
            join_waitlist=False,
            payment_confirmed=True,
        )

        if isinstance(registration_response, dict) and "error" in registration_response:
            failure_reason = registration_response["error"]
            if failure_reason == "You are already registered for this event" and payment:
                payment.registration_status = "registered"
                payment.failure_reason = None
                db.session.add(payment)
                db.session.commit()
                return {
                    "message": "Already registered for event.",
                    "status": "registered",
                }

            if payment:
                payment.registration_status = "registration_failed"
                payment.failure_reason = failure_reason
                db.session.add(payment)
                db.session.commit()
                try:
                    payment = StripeService.refund_payment(payment, failure_reason)
                    payment.registration_status = "registration_failed_refunded"
                    db.session.add(payment)
                    db.session.commit()
                except Exception as refund_error:
                    db.session.rollback()
                    current_app.logger.error(
                        "Automatic refund failed for checkout session %s: %s",
                        session_id,
                        str(refund_error),
                        exc_info=True,
                    )
                    payment = EventPayment.query.filter_by(
                        stripe_checkout_session_id=session_id
                    ).first()
                    if payment:
                        payment.refund_status = "failed"
                        payment.registration_status = "refund_failed"
                        payment.failure_reason = (
                            f"{failure_reason} | Refund error: {str(refund_error)}"
                        )
                        db.session.add(payment)
                        db.session.commit()
            current_app.logger.warning(
                "Paid checkout completed but registration failed for user %s event %s: %s",
                user_id,
                event_id,
                failure_reason,
            )
            return {"error": failure_reason}

        if payment:
            payment.registration_status = "registered"
            payment.failure_reason = None
            db.session.add(payment)
            db.session.commit()

        return {
            "message": registration_response.get(
                "message", "Successfully registered for event"
            ),
            "status": "registered",
        }

    @staticmethod
    def refund_payment(payment: EventPayment, reason: str) -> EventPayment:
        StripeService.require_configured()
        if not payment.stripe_payment_intent_id:
            raise ValueError("Missing Stripe payment intent for refund.")

        refund_kwargs = {
            "payment_intent": payment.stripe_payment_intent_id,
            "reason": "requested_by_customer",
            "metadata": {
                "event_payment_id": str(payment.id),
                "event_id": str(payment.event_id),
                "user_id": str(payment.user_id),
                "failure_reason": reason[:400],
            },
        }
        organizer = User.query.get(payment.organizer_user_id)
        if (
            organizer
            and organizer.role_id != 3
            and organizer.stripe_connected_account_id
        ):
            refund_kwargs["reverse_transfer"] = True
            refund_kwargs["refund_application_fee"] = True

        refund = stripe.Refund.create(**refund_kwargs)
        payment.stripe_refund_id = refund.id
        payment.refund_status = refund.status
        payment.refunded_amount_cents = int(refund.amount or 0)
        payment.registration_status = "registration_failed_refunded"
        payment.failure_reason = reason
        db.session.add(payment)
        db.session.commit()
        return payment

    @staticmethod
    def construct_webhook_event(payload: bytes, sig_header: str):
        StripeService.require_configured()
        webhook_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")
        if not webhook_secret:
            raise ValueError("Stripe webhook secret is missing.")
        return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
