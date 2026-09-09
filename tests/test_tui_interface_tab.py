import unittest
import asyncio
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from textual.widgets import OptionList, Static, TabbedContent
from netwatch.tui import NetMonitorTUI

class TestTUIInterfaceTab(unittest.IsolatedAsyncioTestCase):
    @patch("netwatch.tui.DesktopNotifier")
    @patch("netwatch.tui.NetworkMonitorThread")
    async def test_tui_interface_lifecycle(self, mock_thread, mock_notifier):
        app = NetMonitorTUI()
        
        async with app.run_test() as pilot:
            # 1. Check DOM structure for the new tab
            tabbed_content = app.query_one(TabbedContent)
            self.assertIsNotNone(tabbed_content)
            
            # Switch to interfaces tab
            tabbed_content.active = "interfaces_tab"
            await pilot.pause()
            
            opt_list = app.query_one("#iface_option_list", OptionList)
            name_card = app.query_one("#iface-name-card", Static)
            dl_card = app.query_one("#iface-dl-card", Static)
            ul_card = app.query_one("#iface-ul-card", Static)
            graph_area = app.query_one("#iface_graph_area", Static)

            self.assertIsNotNone(opt_list)
            self.assertIsNotNone(name_card)
            self.assertIsNotNone(dl_card)
            self.assertIsNotNone(ul_card)
            self.assertIsNotNone(graph_area)

            # 2. Simulate incoming data packet with active interfaces
            packet = {
                "upload_speed": 1024,
                "download_speed": 4096,
                "total_upload": 1024,
                "total_download": 4096,
                "total_usage": 5120,
                "timestamp": "2026-09-04 12:00:00",
                "interfaces": {
                    "Wi-Fi": {
                        "upload_speed": 800,
                        "download_speed": 3500,
                        "session_upload": 800,
                        "session_download": 3500,
                        "bytes_sent": 50000000,
                        "bytes_recv": 100000000,
                    },
                    "Ethernet": {
                        "upload_speed": 224,
                        "download_speed": 596,
                        "session_upload": 224,
                        "session_download": 596,
                        "bytes_sent": 10000000,
                        "bytes_recv": 20000000,
                    }
                }
            }
            app._process_data_packet(packet)
            await pilot.pause()

            # Options should now be populated in OptionList
            self.assertEqual(opt_list.option_count, 2)
            self.assertIn(app.selected_interface, ["Ethernet", "Wi-Fi"])

            # Detail view should reflect the selected interface
            self.assertIn(app.selected_interface, str(name_card.render()))

            # 3. Test changing selection
            other_iface = "Wi-Fi" if app.selected_interface == "Ethernet" else "Ethernet"
            app.selected_interface = other_iface
            app._update_interface_detail_view()
            await pilot.pause()

            self.assertIn(other_iface, str(name_card.render()))

            # 4. Test toggle bits/bytes
            self.assertFalse(app.show_bits)
            await pilot.press("ctrl+b")
            self.assertTrue(app.show_bits)

            # 5. Test toggle dark mode
            self.assertFalse(app.dark)
            await pilot.press("ctrl+d")
            self.assertTrue(app.dark)

            # 6. Test reset counters
            await pilot.press("ctrl+r")
            self.assertEqual(app.total_upload, 0)
            self.assertEqual(app.total_download, 0)
            self.assertEqual(app.interface_history, {})

if __name__ == "__main__":
    unittest.main()
