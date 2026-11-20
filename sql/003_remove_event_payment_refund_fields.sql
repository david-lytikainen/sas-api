alter table event_payments
    drop column if exists stripe_refund_id,
    drop column if exists refunded_amount_cents,
    drop column if exists refund_status;
