"""
Ai PhotoFlow - Admin, Affiliate Marketing & Active Users Management Service
Created for Anil Sharma to manage marketing referral agents, sales commissions,
and live active user licenses.
"""
import os
import sqlite3
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from backend.db.database import get_connection
from backend.services.license_service import LicenseService

class AdminService:
    def __init__(self):
        self.license_service = LicenseService()
        self._init_admin_tables()

    def _init_admin_tables(self):
        conn = get_connection()
        cursor = conn.cursor()

        # 1. Marketing / Referral Agents Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS affiliate_agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            referral_code TEXT UNIQUE NOT NULL,
            discount_percent REAL DEFAULT 15.0,
            commission_percent REAL DEFAULT 20.0,
            payout_upi TEXT DEFAULT '',
            payout_bank_details TEXT DEFAULT '',
            status TEXT DEFAULT 'ACTIVE',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 2. Referral Sales & Commissions Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS referral_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER NOT NULL REFERENCES affiliate_agents(id) ON DELETE CASCADE,
            order_id TEXT,
            payment_id TEXT,
            customer_name TEXT NOT NULL,
            customer_email TEXT,
            customer_phone TEXT,
            plan_name TEXT NOT NULL,
            billing_cycle TEXT NOT NULL DEFAULT 'yearly',
            sale_amount REAL NOT NULL,
            commission_rate REAL NOT NULL,
            commission_amount REAL NOT NULL,
            status TEXT DEFAULT 'PENDING', -- PENDING, PAID
            payout_date TIMESTAMP,
            payout_ref TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 3. Customer Licenses & Active Users Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            user_email TEXT NOT NULL,
            user_phone TEXT DEFAULT '',
            license_key TEXT UNIQUE NOT NULL,
            plan_name TEXT NOT NULL,
            status TEXT DEFAULT 'ACTIVE', -- ACTIVE, EXPIRED, REVOKED
            machine_id TEXT DEFAULT '',
            referral_code TEXT DEFAULT '',
            agent_id INTEGER REFERENCES affiliate_agents(id) ON DELETE SET NULL,
            activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT DEFAULT ''
        )
        """)

        # Ensure active_users contains current active license if exists
        cursor.execute("SELECT plan_name, license_key, status, user_name, user_email, expires_at, activated_at FROM license_state WHERE id = 1")
        curr_lic = cursor.fetchone()
        if curr_lic and curr_lic["license_key"]:
            cursor.execute("SELECT id FROM user_licenses WHERE license_key = ?", (curr_lic["license_key"],))
            if not cursor.fetchone():
                cursor.execute("""
                INSERT INTO user_licenses (user_name, user_email, license_key, plan_name, status, expires_at, activated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    curr_lic["user_name"] or "Primary User (Anil Sharma)",
                    curr_lic["user_email"] or "anil@aiphotoflow.com",
                    curr_lic["license_key"],
                    curr_lic["plan_name"],
                    curr_lic["status"],
                    curr_lic["expires_at"],
                    curr_lic["activated_at"] or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))

        # Check if initial sample agents exist, if not create starter agents for Anil Sharma
        cursor.execute("SELECT COUNT(*) as cnt FROM affiliate_agents")
        if cursor.fetchone()["cnt"] == 0:
            sample_agents = [
                ("Rajesh Studios", "+91 98210 44552", "rajesh@delhistudio.in", "RAJESH20", 15.0, 20.0, "rajesh@paytm", "HDFC Bank A/c 50100234123 IFSC: HDFC0000128", "Wedding photographer association coordinator"),
                ("Amit Photo Lab", "+91 94140 88219", "amit@jaipurphotos.com", "AMITPHOTO", 15.0, 25.0, "amitphoto@oksbi", "SBI A/c 301294812 IFSC: SBIN0001234", "Rajasthan lab channel partner"),
                ("Sunil Color Lab", "+91 97110 33910", "sunil@mumbaialbums.com", "SUNIL15", 10.0, 15.0, "sunil@upi", "ICICI Bank A/c 001201948 IFSC: ICIC0000012", "Mumbai album maker partner"),
            ]
            for a_name, a_phone, a_email, a_code, a_disc, a_comm, a_upi, a_bank, a_notes in sample_agents:
                cursor.execute("""
                INSERT INTO affiliate_agents (name, phone, email, referral_code, discount_percent, commission_percent, payout_upi, payout_bank_details, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (a_name, a_phone, a_email, a_code, a_disc, a_comm, a_upi, a_bank, a_notes))
                
                # Also ensure coupon exists in coupons table for seamless checkout discount
                cursor.execute("INSERT OR IGNORE INTO coupons (code, discount_percent, notes) VALUES (?, ?, ?)",
                               (a_code, a_disc, f"Referral discount for partner {a_name}"))

            # Add sample referral sales to show tracking right away
            cursor.execute("SELECT id, referral_code, commission_percent FROM affiliate_agents WHERE referral_code = 'RAJESH20'")
            ag1 = cursor.fetchone()
            if ag1:
                cursor.execute("""
                INSERT INTO referral_sales (agent_id, order_id, payment_id, customer_name, customer_email, customer_phone, plan_name, sale_amount, commission_rate, commission_amount, status, created_at)
                VALUES (?, 'order_LKn92xK8812', 'pay_LKn992A001', 'Vikram Rathore', 'vikram@rathorefilms.com', '+91 98290 11223', 'PRO', 10199, 20.0, 2039.8, 'PENDING', datetime('now', '-2 days'))
                """, (ag1["id"],))

                cursor.execute("""
                INSERT INTO user_licenses (user_name, user_email, user_phone, license_key, plan_name, status, referral_code, agent_id, expires_at)
                VALUES ('Vikram Rathore', 'vikram@rathorefilms.com', '+91 98290 11223', 'APF-PRO-VIKRAM-982182', 'PRO', 'ACTIVE', 'RAJESH20', ?, datetime('now', '+363 days'))
                """, (ag1["id"],))

            cursor.execute("SELECT id, referral_code, commission_percent FROM affiliate_agents WHERE referral_code = 'AMITPHOTO'")
            ag2 = cursor.fetchone()
            if ag2:
                cursor.execute("""
                INSERT INTO referral_sales (agent_id, order_id, payment_id, customer_name, customer_email, customer_phone, plan_name, sale_amount, commission_rate, commission_amount, status, payout_date, payout_ref, created_at)
                VALUES (?, 'order_AM9294821', 'pay_AM9294821B', 'Deepak Verma', 'deepak@vermaphotography.in', '+91 94141 55667', 'STUDIO', 20399, 25.0, 5099.75, 'PAID', datetime('now', '-5 days'), 'UPI-REF-93821094', datetime('now', '-7 days'))
                """, (ag2["id"],))

                cursor.execute("""
                INSERT INTO user_licenses (user_name, user_email, user_phone, license_key, plan_name, status, referral_code, agent_id, expires_at)
                VALUES ('Deepak Verma', 'deepak@vermaphotography.in', '+91 94141 55667', 'APF-STUDIO-DEEPAK-774128', 'STUDIO', 'ACTIVE', 'AMITPHOTO', ?, datetime('now', '+358 days'))
                """, (ag2["id"],))

        conn.commit()
        conn.close()

    # ------------------ Overview Metrics ------------------
    def get_overview_stats(self) -> Dict[str, Any]:
        conn = get_connection()
        cursor = conn.cursor()

        # Active users count
        cursor.execute("SELECT COUNT(*) as cnt FROM user_licenses WHERE status = 'ACTIVE'")
        active_users_cnt = cursor.fetchone()["cnt"]

        # Total agents count
        cursor.execute("SELECT COUNT(*) as cnt FROM affiliate_agents WHERE status = 'ACTIVE'")
        total_agents = cursor.fetchone()["cnt"]

        # Total referral sales & revenue
        cursor.execute("""
        SELECT 
            COUNT(*) as total_sales,
            COALESCE(SUM(sale_amount), 0) as total_revenue,
            COALESCE(SUM(CASE WHEN status = 'PENDING' THEN commission_amount ELSE 0 END), 0) as pending_commission,
            COALESCE(SUM(CASE WHEN status = 'PAID' THEN commission_amount ELSE 0 END), 0) as paid_commission
        FROM referral_sales
        """)
        sales_data = dict(cursor.fetchone())

        conn.close()

        return {
            "active_users_count": active_users_cnt,
            "total_agents": total_agents,
            "total_referral_sales": sales_data["total_sales"],
            "total_referral_revenue": round(sales_data["total_revenue"], 2),
            "pending_commission": round(sales_data["pending_commission"], 2),
            "paid_commission": round(sales_data["paid_commission"], 2),
        }

    # ------------------ Affiliate Agents CRUD ------------------
    def list_agents(self) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        SELECT 
            a.*,
            COUNT(s.id) as total_referrals,
            COALESCE(SUM(s.sale_amount), 0) as total_sales_volume,
            COALESCE(SUM(s.commission_amount), 0) as total_commission_earned,
            COALESCE(SUM(CASE WHEN s.status = 'PAID' THEN s.commission_amount ELSE 0 END), 0) as total_commission_paid,
            COALESCE(SUM(CASE WHEN s.status = 'PENDING' THEN s.commission_amount ELSE 0 END), 0) as pending_commission_balance
        FROM affiliate_agents a
        LEFT JOIN referral_sales s ON a.id = s.agent_id
        GROUP BY a.id
        ORDER BY a.created_at DESC
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def create_agent(self, data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()

        name = (data.get("name") or "").strip()
        phone = (data.get("phone") or "").strip()
        email = (data.get("email") or "").strip()
        code = (data.get("referral_code") or "").strip().upper()
        discount = float(data.get("discount_percent") or 15.0)
        commission = float(data.get("commission_percent") or 20.0)
        upi = (data.get("payout_upi") or "").strip()
        bank = (data.get("payout_bank_details") or "").strip()
        notes = (data.get("notes") or "").strip()

        if not name or not phone:
            conn.close()
            return False, "Agent name and phone number are required.", {}

        # Auto generate clean code if blank
        if not code:
            clean_name = "".join(filter(str.isalnum, name.upper()))[:6]
            rand_suffix = "".join(random.choices(string.digits, k=2))
            code = f"{clean_name}{rand_suffix}"

        # Check uniqueness of referral code
        cursor.execute("SELECT id FROM affiliate_agents WHERE referral_code = ?", (code,))
        if cursor.fetchone():
            conn.close()
            return False, f"Referral code '{code}' is already assigned to another agent. Please choose a different code.", {}

        try:
            cursor.execute("""
            INSERT INTO affiliate_agents (name, phone, email, referral_code, discount_percent, commission_percent, payout_upi, payout_bank_details, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, phone, email, code, discount, commission, upi, bank, notes))
            agent_id = cursor.lastrowid

            # Add to coupons so client gets immediate discount in checkout
            cursor.execute("""
            INSERT OR REPLACE INTO coupons (code, discount_percent, notes, is_active)
            VALUES (?, ?, ?, 1)
            """, (code, discount, f"Affiliate discount for {name}"))

            conn.commit()

            cursor.execute("SELECT * FROM affiliate_agents WHERE id = ?", (agent_id,))
            new_agent = dict(cursor.fetchone())
            conn.close()
            return True, f"Agent '{name}' created successfully with Referral Code: {code}", new_agent
        except Exception as e:
            conn.close()
            return False, f"Database error creating agent: {str(e)}", {}

    def update_agent(self, agent_id: int, data: Dict[str, Any]) -> Tuple[bool, str]:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, referral_code FROM affiliate_agents WHERE id = ?", (agent_id,))
        agent = cursor.fetchone()
        if not agent:
            conn.close()
            return False, "Agent not found"

        name = data.get("name")
        phone = data.get("phone")
        email = data.get("email")
        discount = data.get("discount_percent")
        commission = data.get("commission_percent")
        upi = data.get("payout_upi")
        bank = data.get("payout_bank_details")
        status = data.get("status")
        notes = data.get("notes")

        cursor.execute("""
        UPDATE affiliate_agents SET
            name = COALESCE(?, name),
            phone = COALESCE(?, phone),
            email = COALESCE(?, email),
            discount_percent = COALESCE(?, discount_percent),
            commission_percent = COALESCE(?, commission_percent),
            payout_upi = COALESCE(?, payout_upi),
            payout_bank_details = COALESCE(?, payout_bank_details),
            status = COALESCE(?, status),
            notes = COALESCE(?, notes)
        WHERE id = ?
        """, (name, phone, email, discount, commission, upi, bank, status, notes, agent_id))

        if discount is not None:
            cursor.execute("UPDATE coupons SET discount_percent = ? WHERE code = ?", (discount, agent["referral_code"]))

        conn.commit()
        conn.close()
        return True, "Agent updated successfully"

    def delete_agent(self, agent_id: int) -> Tuple[bool, str]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT referral_code FROM affiliate_agents WHERE id = ?", (agent_id,))
        row = cursor.fetchone()
        if row:
            cursor.execute("DELETE FROM coupons WHERE code = ?", (row["referral_code"],))
        cursor.execute("DELETE FROM affiliate_agents WHERE id = ?", (agent_id,))
        conn.commit()
        conn.close()
        return True, "Agent deleted"

    # ------------------ Referral Sales & Commissions ------------------
    def list_referral_sales(self) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT 
            s.*,
            a.name as agent_name,
            a.referral_code,
            a.payout_upi as agent_upi,
            a.payout_bank_details as agent_bank
        FROM referral_sales s
        JOIN affiliate_agents a ON s.agent_id = a.id
        ORDER BY s.created_at DESC
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def record_referral_sale(
        self,
        referral_code: str,
        customer_name: str,
        customer_email: str,
        customer_phone: str,
        plan_name: str,
        sale_amount: float,
        order_id: str = "",
        payment_id: str = "",
        billing_cycle: str = "yearly"
    ) -> Optional[int]:
        """
        Records a sale attributed to an agent and calculates the exact commission.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, commission_percent FROM affiliate_agents WHERE UPPER(referral_code) = ? AND status = 'ACTIVE'", (referral_code.strip().upper(),))
        agent = cursor.fetchone()
        if not agent:
            conn.close()
            return None

        agent_id = agent["id"]
        comm_rate = float(agent["commission_percent"])
        comm_amount = round((sale_amount * comm_rate) / 100.0, 2)

        cursor.execute("""
        INSERT INTO referral_sales (
            agent_id, order_id, payment_id, customer_name, customer_email, customer_phone,
            plan_name, billing_cycle, sale_amount, commission_rate, commission_amount, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
        """, (agent_id, order_id, payment_id, customer_name, customer_email, customer_phone, plan_name, billing_cycle, sale_amount, comm_rate, comm_amount))
        sale_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return sale_id

    def mark_commission_paid(self, sale_id: int, payout_ref: str, notes: str = "") -> Tuple[bool, str]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, status, commission_amount FROM referral_sales WHERE id = ?", (sale_id,))
        sale = cursor.fetchone()
        if not sale:
            conn.close()
            return False, "Referral sale not found"

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        UPDATE referral_sales SET
            status = 'PAID',
            payout_date = ?,
            payout_ref = ?,
            notes = COALESCE(?, notes)
        WHERE id = ?
        """, (now_str, payout_ref, notes, sale_id))
        conn.commit()
        conn.close()
        return True, f"Commission of ₹{sale['commission_amount']} marked as PAID! Reference: {payout_ref}"

    # ------------------ Active Users & Customer Licenses ------------------
    def list_users(self) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT 
            u.*,
            a.name as agent_name,
            a.referral_code as agent_code
        FROM user_licenses u
        LEFT JOIN affiliate_agents a ON u.agent_id = a.id
        ORDER BY u.activated_at DESC
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        # Compute remaining days
        now = datetime.now()
        for r in rows:
            if r["expires_at"]:
                try:
                    exp = datetime.strptime(r["expires_at"][:19], "%Y-%m-%d %H:%M:%S")
                    r["days_remaining"] = max(0, (exp - now).days)
                    if exp < now and r["status"] == "ACTIVE":
                        r["status"] = "EXPIRED"
                except Exception:
                    r["days_remaining"] = 365
            else:
                r["days_remaining"] = 9999 # Lifetime

        return rows

    def issue_manual_license(
        self,
        user_name: str,
        user_email: str,
        user_phone: str,
        plan_name: str,
        days: int = 365,
        referral_code: str = "",
        notes: str = ""
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Admin can directly create and issue an official signed license key to a client.
        """
        token = "".join(filter(str.isalnum, user_name.upper()))[:6] or "CLIENT"
        signed_key = self.license_service.generate_cryptographic_key(plan_name, days, token)

        conn = get_connection()
        cursor = conn.cursor()

        agent_id = None
        if referral_code:
            cursor.execute("SELECT id FROM affiliate_agents WHERE UPPER(referral_code) = ?", (referral_code.strip().upper(),))
            ag = cursor.fetchone()
            if ag:
                agent_id = ag["id"]

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        exp_str = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
        INSERT INTO user_licenses (user_name, user_email, user_phone, license_key, plan_name, status, referral_code, agent_id, activated_at, expires_at, notes)
        VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?)
        """, (user_name, user_email, user_phone, signed_key, plan_name, referral_code, agent_id, now_str, exp_str, notes))
        
        lic_id = cursor.lastrowid
        conn.commit()

        cursor.execute("SELECT * FROM user_licenses WHERE id = ?", (lic_id,))
        created = dict(cursor.fetchone())
        conn.close()

        return True, f"License generated successfully for {user_name}!", created
