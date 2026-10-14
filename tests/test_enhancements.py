import unittest
from datetime import datetime, timedelta
import os
import sqlite3
from backend.services.proofing_service import proofing_service
from backend.db.database import get_connection
from backend.core.editing_model import IndianWeddingEditingModel
import numpy as np

class TestEnhancements(unittest.TestCase):
    def test_editing_model_whites_calculation(self):
        model = IndianWeddingEditingModel()
        # Synthetic neutral image with bride face/dress
        img = np.full((100, 100, 3), 128, dtype=np.uint8)
        params = model.calculate_corrections(img, preset_name="Pure Light (No Color Tone)")
        self.assertGreater(params.whites, 0.0)

    def test_purge_expired_galleries(self):
        conn = get_connection()
        cursor = conn.cursor()
        
        # Insert a dummy expired gallery (expired 3 days ago)
        expired_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        test_uuid = "test_expired_uuid_12345"
        
        cursor.execute("DELETE FROM client_galleries WHERE gallery_uuid = ?", (test_uuid,))
        cursor.execute("""
            INSERT INTO client_galleries (project_id, gallery_uuid, title, client_name, client_pin, auto_delete_days, expires_at, status)
            VALUES (1, ?, 'Test Title', 'Test Client', '1234', 60, ?, 'ACTIVE')
        """, (test_uuid, expired_date))
        conn.commit()
        conn.close()

        # Run purge
        purged = proofing_service.purge_expired_galleries()
        self.assertGreaterEqual(purged, 1)

        # Verify it was removed
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM client_galleries WHERE gallery_uuid = ?", (test_uuid,))
        row = cursor.fetchone()
        conn.close()
        self.assertIsNone(row)

    def test_windows_path_handling(self):
        win_path = r"D:\Photos\Wedding 2026\Haldi\IMG_1234.JPG"
        parts = win_path.replace("\\", "/").split("/")
        subfolder = parts[-2]
        self.assertEqual(subfolder, "Haldi")

if __name__ == "__main__":
    unittest.main()
