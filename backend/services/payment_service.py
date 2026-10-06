"""
Ai PhotoFlow - Razorpay Payment Gateway Service
Handles:
1. Razorpay order creation via REST API (or test simulation if keys not provided)
2. Razorpay payment HMAC-SHA256 signature verification
3. Automatic license activation on successful payment
"""
import os
import hmac
import hashlib
import time
import json
import urllib.request
import urllib.error
import base64
from typing import Dict, Any, Tuple, Optional
from backend.db.database import get_connection
from backend.services.license_service import LicenseService

RAZORPAY_API_URL = "https://api.razorpay.com/v1/orders"

class PaymentService:
    def __init__(self):
        self.license_service = LicenseService()
        self._init_payment_tables()

    def _init_payment_tables(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            payment_id TEXT,
            plan_name TEXT NOT NULL,
            billing_cycle TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'INR',
            status TEXT DEFAULT 'CREATED',
            customer_name TEXT,
            customer_email TEXT,
            coupon_used TEXT,
            raw_response TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()
        conn.close()

    def get_razorpay_config(self) -> Dict[str, Any]:
        """
        Retrieves Razorpay credentials configured by Anil Sharma in settings.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM app_settings WHERE key IN ('razorpay_key_id', 'razorpay_key_secret', 'razorpay_enabled')")
        rows = {r["key"]: r["value"] for r in cursor.fetchall()}
        conn.close()

        key_id = rows.get("razorpay_key_id", os.environ.get("RAZORPAY_KEY_ID", ""))
        key_secret = rows.get("razorpay_key_secret", os.environ.get("RAZORPAY_KEY_SECRET", ""))
        enabled = rows.get("razorpay_enabled", "1") == "1"

        return {
            "key_id": key_id.strip(),
            "key_secret": key_secret.strip(),
            "is_configured": bool(key_id.strip() and key_secret.strip()),
            "enabled": enabled
        }

    def create_order(
        self,
        plan_id: str,
        billing_cycle: str = "yearly",
        customer_name: str = "",
        customer_email: str = "",
        coupon_code: Optional[str] = None,
        currency: str = "INR"
    ) -> Dict[str, Any]:
        """
        Creates an order on Razorpay for the specified plan and discount.
        """
        plan_id_clean = plan_id.upper()
        billing_cycle_clean = billing_cycle.lower()

        # Calculate price taking any referral coupon into account
        coupon_res = self.license_service.verify_coupon(coupon_code, plan_id_clean, billing_cycle_clean, currency)
        if coupon_res.get("valid"):
            final_price = coupon_res["final_price"]
        else:
            # Fallback to standard catalog price
            if plan_id_clean == "STUDIO":
                final_price = 6999 if billing_cycle_clean == "yearly" else 999
            else:
                final_price = 3499 if billing_cycle_clean == "yearly" else 499

        amount_in_paise = int(final_price * 100) # Razorpay expects amount in paise
        config = self.get_razorpay_config()

        order_id = f"order_{int(time.time())}_{int(time.time() * 1000) % 10000}"

        if config["is_configured"] and config["enabled"]:
            # Real call to Razorpay API
            try:
                auth_str = f"{config['key_id']}:{config['key_secret']}"
                b64_auth = base64.b64encode(auth_str.encode()).decode()

                payload = json.dumps({
                    "amount": amount_in_paise,
                    "currency": currency,
                    "receipt": f"rcpt_{int(time.time())}",
                    "notes": {
                        "plan": plan_id_clean,
                        "cycle": billing_cycle_clean,
                        "customer": customer_name,
                        "coupon": coupon_code or ""
                    }
                }).encode("utf-8")

                req = urllib.request.Request(
                    RAZORPAY_API_URL,
                    data=payload,
                    headers={
                        "Authorization": f"Basic {b64_auth}",
                        "Content-Type": "application/json"
                    },
                    method="POST"
                )

                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    order_id = data.get("id", order_id)
            except Exception as e:
                print(f"Warning: Razorpay live order creation fallback to local order ID: {e}")
                # Fallback to generated order ID if network issue

        # Record transaction in database
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO payment_transactions (order_id, plan_name, billing_cycle, amount, currency, status, customer_name, customer_email, coupon_used)
        VALUES (?, ?, ?, ?, ?, 'CREATED', ?, ?, ?)
        """, (order_id, plan_id_clean, billing_cycle_clean, final_price, currency, customer_name, customer_email, coupon_code or ""))
        conn.commit()
        conn.close()

        return {
            "order_id": order_id,
            "amount": amount_in_paise,
            "amount_display": final_price,
            "currency": currency,
            "key_id": config["key_id"] if config["key_id"] else "rzp_test_AiPhotoFlow",
            "is_test_mode": not config["is_configured"],
            "plan_id": plan_id_clean,
            "billing_cycle": billing_cycle_clean
        }

    def verify_payment(
        self,
        order_id: str,
        payment_id: str,
        signature: Optional[str] = None,
        client_name: str = "",
        client_email: str = ""
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Verifies Razorpay HMAC signature and automatically activates user's software license!
        """
        config = self.get_razorpay_config()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT plan_name, billing_cycle, amount, coupon_used FROM payment_transactions WHERE order_id = ?", (order_id,))
        tx = cursor.fetchone()

        plan_name = tx["plan_name"] if tx else "PRO"
        cycle = tx["billing_cycle"] if tx else "yearly"

        # Strict Payment Verification Guard
        if not config["is_configured"] or not config["key_secret"]:
            conn.close()
            return False, "Razorpay gateway is not configured yet. Please configure your Razorpay Key ID and Secret in Settings to accept live payments.", {}

        if not signature:
            conn.close()
            return False, "Payment signature missing. Payment was not completed or verified.", {}

        # Check signature against Razorpay Key Secret
        msg = f"{order_id}|{payment_id}"
        expected_sig = hmac.new(
            config["key_secret"].encode(),
            msg.encode(),
            hashlib.sha256
        ).hexdigest()

        if expected_sig != signature:
            conn.close()
            return False, "Security Error: Payment signature verification failed (Tampered payment).", {}

        # Signature mathematically verified by Razorpay Secret!
        # Update transaction status
        cursor.execute("""
        UPDATE payment_transactions SET
            payment_id = ?,
            status = 'PAID',
            updated_at = CURRENT_TIMESTAMP
        WHERE order_id = ?
        """, (payment_id, order_id))
        conn.commit()
        conn.close()

        # AUTOMATIC ACCESS ACTIVATION:
        days = 365 if cycle == "yearly" else 30
        max_devices = 3 if plan_name == "STUDIO" else 1
        new_key = f"APF-RZP-{order_id.replace('order_', '')}-{payment_id[-6:]}"

        success, msg, license_data = self.license_service._set_license(
            plan_name=plan_name,
            license_key=new_key,
            is_vip=0,
            days=days,
            user_name=client_name or "Subscriber",
            user_email=client_email or "",
            max_devices=max_devices
        )

        # Record referral commission and register into user_licenses
        try:
            from backend.services.admin_service import AdminService
            admin_svc = AdminService()
            coupon_code = tx["coupon_used"] if tx and tx["coupon_used"] else ""
            if coupon_code:
                admin_svc.record_referral_sale(
                    referral_code=coupon_code,
                    customer_name=client_name or "Subscriber",
                    customer_email=client_email or "",
                    customer_phone="",
                    plan_name=plan_name,
                    sale_amount=float(tx["amount"]) if tx else 0.0,
                    order_id=order_id,
                    payment_id=payment_id,
                    billing_cycle=cycle
                )
            
            # Register in user_licenses directory
            conn_u = get_connection()
            cursor_u = conn_u.cursor()
            cursor_u.execute("""
            INSERT OR REPLACE INTO user_licenses (user_name, user_email, license_key, plan_name, status, referral_code, expires_at)
            VALUES (?, ?, ?, ?, 'ACTIVE', ?, datetime('now', ?))
            """, (
                client_name or "Subscriber",
                client_email or "",
                new_key,
                plan_name,
                coupon_code,
                f"+{days} days"
            ))
            conn_u.commit()
            conn_u.close()
        except Exception as e:
            print(f"Non-fatal error recording referral/user license: {e}")

        return True, f"🎉 Payment Verified! Your {plan_name} plan has been automatically activated for {days} days!", license_data
