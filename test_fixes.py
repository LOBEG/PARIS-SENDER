"""
Tests for GUI features including: Placeholder Engine, DNS Domain Checker, Live Sent Email Log,
CollapsibleSection widget, GUI performance improvements, Health Monitor dashboard,
Log Viewer tab, and surfaced configuration fields.
These tests validate the backend logic and source structure without requiring a GUI (tkinter) window.
"""

import unittest
import re
import csv
import io
import queue
from datetime import datetime
from unittest.mock import MagicMock, patch

# Test Jinja2 template validation logic
try:
    from jinja2 import Environment, exceptions as jinja_exceptions
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

# Test DNS resolution logic
try:
    import dns.resolver
    DNSPYTHON_AVAILABLE = True
except ImportError:
    DNSPYTHON_AVAILABLE = False


class TestTemplateValidation(unittest.TestCase):
    """Tests for Jinja2 template validation and syntax error detection."""

    def setUp(self):
        self.known_placeholders = {
            "[EMAIL]", "[FIRSTNAME]", "[LASTNAME]", "[COMPANY]",
            "[DATE]", "[TIME]", "[GREETINGS]", "[SENDER_NAME]",
            "[DOMAIN]", "[UNAME]", "[EMAIL64]", "[COMPANYFULL]",
            "[DATE-1DAY]", "[DATE-2]", "[FUTURE-1DAY]", "[CURRENTDATE]",
        }

    def test_valid_bracket_placeholders(self):
        content = "Hello [FIRSTNAME], your email is [EMAIL]."
        found = re.findall(r'\[([A-Z0-9_\-]+)\]', content)
        for ph in found:
            self.assertIn(f"[{ph}]", self.known_placeholders)

    def test_unknown_bracket_placeholder_detected(self):
        content = "Hello [UNKNOWNFIELD], welcome."
        found = re.findall(r'\[([A-Z0-9_\-]+)\]', content)
        unknown = [f"[{ph}]" for ph in found if f"[{ph}]" not in self.known_placeholders]
        self.assertEqual(len(unknown), 1)
        self.assertEqual(unknown[0], "[UNKNOWNFIELD]")

    @unittest.skipUnless(JINJA2_AVAILABLE, "Jinja2 not available")
    def test_valid_jinja2_template(self):
        content = "Hello {{ firstname }}, welcome to {{ company }}."
        env = Environment()
        parsed = env.parse(content)
        self.assertIsNotNone(parsed)

    @unittest.skipUnless(JINJA2_AVAILABLE, "Jinja2 not available")
    def test_invalid_jinja2_syntax_detected(self):
        content = "Hello {% if user %} welcome {% endif"
        env = Environment()
        with self.assertRaises(jinja_exceptions.TemplateSyntaxError):
            env.parse(content)

    @unittest.skipUnless(JINJA2_AVAILABLE, "Jinja2 not available")
    def test_unclosed_jinja2_block_detection(self):
        content = "{% if user %}Hello{% if admin %}Admin{% endif %}"
        open_blocks = len(re.findall(r'\{%\s*(?:if|for|block|macro)\b', content))
        close_blocks = len(re.findall(r'\{%\s*(?:endif|endfor|endblock|endmacro)\b', content))
        self.assertGreater(open_blocks, close_blocks)

    def test_unclosed_jinja2_expression(self):
        content = "Hello {{ firstname"
        has_open = '{{' in content
        has_close = '}}' in content
        self.assertTrue(has_open)
        self.assertFalse(has_close)

    @unittest.skipUnless(JINJA2_AVAILABLE, "Jinja2 not available")
    def test_jinja2_variable_extraction(self):
        content = "Hello {{ firstname }}, {{ company }} welcomes {{ email }}."
        jinja_vars = re.findall(r'\{\{\s*(\w+(?:\.\w+)*)\s*\}\}', content)
        self.assertEqual(set(jinja_vars), {'firstname', 'company', 'email'})


class TestContextPreview(unittest.TestCase):
    """Tests for context variable preview rendering."""

    def test_context_from_email(self):
        email = "john.doe@example.com"
        local_part = email.split('@')[0]
        domain = email.split('@')[1]
        parts = re.split(r'[._\-+]+', local_part)
        valid_parts = [p for p in parts if len(p) > 1 and p.isalpha()]
        firstname = valid_parts[0].capitalize() if valid_parts else 'User'
        company = domain.split('.')[0].capitalize()

        self.assertEqual(firstname, 'John')
        self.assertEqual(company, 'Example')
        self.assertEqual(domain, 'example.com')

    def test_context_from_single_part_email(self):
        email = "admin@company.org"
        local_part = email.split('@')[0]
        parts = re.split(r'[._\-+]+', local_part)
        valid_parts = [p for p in parts if len(p) > 1 and p.isalpha()]
        firstname = valid_parts[0].capitalize() if valid_parts else 'User'
        self.assertEqual(firstname, 'Admin')

    def test_context_from_numeric_email(self):
        email = "12345@numbers.com"
        local_part = email.split('@')[0]
        parts = re.split(r'[._\-+]+', local_part)
        valid_parts = [p for p in parts if len(p) > 1 and p.isalpha()]
        firstname = valid_parts[0].capitalize() if valid_parts else 'User'
        self.assertEqual(firstname, 'User')


class TestDNSDomainChecker(unittest.TestCase):
    """Tests for DNS domain checker logic."""

    def test_domain_extraction_from_emails(self):
        emails = ["user@example.com", "admin@test.org", "info@example.com"]
        domains = sorted(set(e.split('@')[1] for e in emails if '@' in e))
        self.assertEqual(domains, ['example.com', 'test.org'])

    def test_domain_extraction_from_file_lines(self):
        lines = ["example.com\n", "test.org\n", " invalid \n", "another.net\n"]
        domains = [d.strip() for d in lines if d.strip() and '.' in d.strip() and ' ' not in d.strip()]
        self.assertEqual(len(domains), 3)

    def test_domain_from_email_in_file(self):
        line = "user@example.com"
        if '@' in line:
            line = line.split('@')[1]
        self.assertEqual(line, 'example.com')

    def test_dns_result_structure(self):
        result = {
            'domain': 'example.com',
            'mx': 'mx1.example.com',
            'spf': '✅',
            'dkim': '✅',
            'dmarc': '✅',
            'status': '✅ All Pass',
            'tag': 'pass'
        }
        self.assertIn('domain', result)
        self.assertIn('mx', result)
        self.assertIn('spf', result)
        self.assertIn('dkim', result)
        self.assertIn('dmarc', result)
        self.assertIn('status', result)
        self.assertIn('tag', result)

    def test_dns_status_classification(self):
        checks = ['✅', '✅', '❌']
        pass_count = sum(1 for c in checks if c == '✅')
        self.assertEqual(pass_count, 2)

        if pass_count == 3:
            status = '✅ All Pass'
        elif pass_count == 0:
            status = '❌ Critical Issues'
        else:
            status = f'⚠️ {pass_count}/3 Pass'
        self.assertEqual(status, '⚠️ 2/3 Pass')


class TestSentEmailLog(unittest.TestCase):
    """Tests for the sent email log system."""

    def test_log_entry_structure(self):
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        entry = {'timestamp': timestamp, 'severity': 'INFO', 'message': 'Test message'}
        self.assertIn('timestamp', entry)
        self.assertIn('severity', entry)
        self.assertIn('message', entry)

    def test_severity_auto_classification(self):
        test_cases = [
            ("❌ Failed to send", "ERROR"),
            ("Error connecting to SMTP", "ERROR"),
            ("⚠️ Rate limit approaching", "WARNING"),
            ("✅ Email sent successfully", "SUCCESS"),
            ("Starting campaign...", "INFO"),
        ]
        for msg, expected in test_cases:
            if '❌' in msg or 'Error' in msg or 'error' in msg or 'FAIL' in msg:
                severity = "ERROR"
            elif '⚠️' in msg or 'Warning' in msg or 'warning' in msg:
                severity = "WARNING"
            elif '✅' in msg or 'Success' in msg or 'Sent' in msg:
                severity = "SUCCESS"
            else:
                severity = "INFO"
            self.assertEqual(severity, expected, f"Failed for: {msg}")

    def test_log_entry_cap(self):
        entries = [{'timestamp': f'[{i:02d}:00:00]', 'severity': 'INFO', 'message': f'msg {i}'} for i in range(15000)]
        # The _append_sent_log method caps at 10000 entries, trimming to the last 5000
        if len(entries) > 10000:
            entries = entries[-5000:]
        self.assertEqual(len(entries), 5000)

    def test_filter_by_severity(self):
        entries = [
            {'timestamp': '[10:00:00]', 'severity': 'INFO', 'message': 'Starting'},
            {'timestamp': '[10:00:01]', 'severity': 'ERROR', 'message': 'Failed'},
            {'timestamp': '[10:00:02]', 'severity': 'SUCCESS', 'message': 'Sent email'},
        ]
        filtered = [e for e in entries if e['severity'] == 'ERROR']
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['message'], 'Failed')

    def test_filter_by_text(self):
        entries = [
            {'timestamp': '[10:00:00]', 'severity': 'INFO', 'message': 'Starting campaign'},
            {'timestamp': '[10:00:01]', 'severity': 'SUCCESS', 'message': 'Sent to user@test.com'},
            {'timestamp': '[10:00:02]', 'severity': 'SUCCESS', 'message': 'Sent to admin@example.com'},
        ]
        filter_text = 'test.com'
        filtered = [e for e in entries if filter_text.lower() in e['message'].lower()]
        self.assertEqual(len(filtered), 1)

    def test_export_csv_format(self):
        entries = [
            {'timestamp': '[10:00:00]', 'severity': 'INFO', 'message': 'Test message'},
            {'timestamp': '[10:00:01]', 'severity': 'ERROR', 'message': 'Error occurred'},
        ]
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Timestamp', 'Severity', 'Message'])
        for entry in entries:
            writer.writerow([entry['timestamp'], entry['severity'], entry['message']])
        csv_content = output.getvalue()
        self.assertIn('Timestamp,Severity,Message', csv_content)
        self.assertIn('ERROR', csv_content)


class TestURLSubstringSanitization(unittest.TestCase):
    """Tests for URL hostname validation to prevent substring attacks."""

    def test_gmail_url_exact_hostname_match(self):
        """Verify urlparse-based hostname check matches exact Gmail domain."""
        from urllib.parse import urlparse
        url = "https://mail.google.com/mail/u/0/#inbox"
        hostname = urlparse(url).hostname
        self.assertEqual(hostname, "mail.google.com")

    def test_gmail_url_rejects_malicious_substring(self):
        """Verify urlparse rejects URLs where mail.google.com is a path, not host."""
        from urllib.parse import urlparse
        malicious_url = "https://evil.com/mail.google.com"
        hostname = urlparse(malicious_url).hostname
        self.assertNotEqual(hostname, "mail.google.com")
        self.assertEqual(hostname, "evil.com")

    def test_outlook_url_exact_hostname_match(self):
        """Verify urlparse-based hostname check matches exact Outlook domains."""
        from urllib.parse import urlparse
        for url, expected in [
            ("https://outlook.office.com/mail/", "outlook.office.com"),
            ("https://outlook.live.com/mail/", "outlook.live.com"),
        ]:
            hostname = urlparse(url).hostname
            self.assertEqual(hostname, expected)

    def test_outlook_url_rejects_malicious_substring(self):
        """Verify urlparse rejects URLs where outlook domain is in path only."""
        from urllib.parse import urlparse
        malicious_url = "https://evil.com/outlook.office.com"
        hostname = urlparse(malicious_url).hostname
        self.assertNotIn(hostname, ("outlook.office.com", "outlook.live.com"))


class TestParamikoHostKeyPolicy(unittest.TestCase):
    """Tests for paramiko host key policy (WarningPolicy instead of AutoAddPolicy)."""

    def test_warning_policy_exists(self):
        """Verify paramiko.WarningPolicy is available."""
        try:
            import paramiko
            policy = paramiko.WarningPolicy()
            self.assertIsNotNone(policy)
        except ImportError:
            self.skipTest("paramiko not available")

    def test_source_uses_warning_policy(self):
        """Verify the source code uses load_system_host_keys, not AutoAddPolicy."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertNotIn('AutoAddPolicy', content)
        self.assertNotIn('WarningPolicy', content)
        self.assertIn('load_system_host_keys', content)

    def test_source_uses_urlparse_for_url_checks(self):
        """Verify the source code uses urlparse for URL hostname checks."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        # Should NOT contain vulnerable substring checks for these domains
        import re
        # Check there's no pattern like: "mail.google.com" in some_url_var
        vulnerable_patterns = re.findall(r'"mail\.google\.com"\s+in\s+\w+', content)
        self.assertEqual(len(vulnerable_patterns), 0, f"Found vulnerable URL substring checks: {vulnerable_patterns}")


class TestCollapsibleSection(unittest.TestCase):
    """Tests for the CollapsibleSection widget class."""

    def test_collapsible_section_class_exists(self):
        """Verify CollapsibleSection class is defined in source."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('class CollapsibleSection', content)

    def test_collapsible_section_has_toggle(self):
        """Verify CollapsibleSection has _toggle method."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('def _toggle(self', content)

    def test_collapsible_sections_used_in_settings(self):
        """Verify collapsible sections are used in the Settings tab."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        # VPS, IMAP, Warmup sections should use CollapsibleSection
        self.assertIn("CollapsibleSection(right_frame, title=\"🖥️ Proxy VPS Mailer\"", content)
        self.assertIn("CollapsibleSection(right_frame, title=\"📬 IMAP (Reply Tracking)\"", content)
        self.assertIn("CollapsibleSection(right_frame, title=\"🌱 Warmup & Seed List\"", content)


class TestGUIPerformance(unittest.TestCase):
    """Tests for GUI performance improvements."""

    def test_log_batching_in_process_gui_updates(self):
        """Verify log messages are batched for insertion."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('log_batch = []', content)
        self.assertIn("log_batch.append(args[0])", content)
        self.assertIn("combined = ''.join(log_batch)", content)

    def test_scrollable_frame_throttling(self):
        """Verify ScrollableFrame has throttled configure updates."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('_scroll_update_pending', content)
        self.assertIn('_do_configure_update', content)

    def test_settings_tab_scrollable(self):
        """Verify Settings tab uses ScrollableFrame for overflow prevention."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('left_scroll = ScrollableFrame(left_outer)', content)
        self.assertIn('right_scroll = ScrollableFrame(right_outer)', content)


class TestNewGUITabs(unittest.TestCase):
    """Tests for new dashboard tabs."""

    def test_health_monitor_tab_exists(self):
        """Verify Health Monitor tab is built."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('_build_health_monitor_tab', content)
        self.assertIn("text='💓 Health Monitor'", content)

    def test_log_viewer_tab_exists(self):
        """Verify Log Viewer tab is built."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('_build_log_viewer_tab', content)
        self.assertIn("text='📋 Log Viewer'", content)

    def test_health_monitor_has_vps_grid(self):
        """Verify Health Monitor has VPS health grid."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('health_vps_tree', content)
        self.assertIn('_refresh_health_monitor_vps', content)

    def test_health_monitor_has_proxy_grid(self):
        """Verify Health Monitor has proxy health grid."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('health_proxy_tree', content)

    def test_health_monitor_has_retry_queue_viewer(self):
        """Verify Health Monitor has retry queue viewer."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('health_retry_tree', content)
        self.assertIn('_refresh_health_retry_queue', content)

    def test_health_monitor_has_encryption_status(self):
        """Verify Health Monitor has encryption key status."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('health_enc_status', content)
        self.assertIn('_refresh_health_enc_status', content)

    def test_log_viewer_has_filter(self):
        """Verify Log Viewer has filtering capability."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('log_viewer_filter_var', content)
        self.assertIn('_apply_log_viewer_filter', content)
        self.assertIn('log_viewer_level_var', content)


class TestMissingSurfacedFields(unittest.TestCase):
    """Tests for previously hidden backend fields now surfaced in GUI."""

    def test_unsubscribe_url_field(self):
        """Verify unsubscribe URL field is surfaced."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('unsubscribe_url_var', content)
        self.assertIn('Unsubscribe URL', content)

    def test_reply_to_override_field(self):
        """Verify Reply-To override field is surfaced."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('reply_to_override_var', content)
        self.assertIn('Reply-To Override', content)

    def test_message_id_domain_override_field(self):
        """Verify Message-ID domain override is surfaced."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('message_id_domain_override_var', content)
        self.assertIn('Message-ID Domain', content)

    def test_random_sender_pool_field(self):
        """Verify random sender pool editor is surfaced."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('random_sender_pool_var', content)
        self.assertIn('Random Sender Pool', content)

    def test_rate_limit_fields(self):
        """Verify rate limit configuration fields are surfaced."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('rate_limit_per_hour_var', content)
        self.assertIn('Rate Limit/Hour', content)

    def test_dkim_key_upload_field(self):
        """Verify DKIM key upload field exists."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('dkim_key_file_var', content)
        self.assertIn('_browse_dkim_key_file', content)

    def test_advanced_sending_section_collapsible(self):
        """Verify Advanced Sending Options uses CollapsibleSection."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn("CollapsibleSection(config_frame, title=\"🔧 Advanced Sending Options\"", content)


class TestExistingFeaturesPreserved(unittest.TestCase):
    """Tests to verify existing features are not removed or altered."""

    def test_sending_mode_selector_preserved(self):
        """Verify sending mode selector was removed as it was not wired to any logic.
        The actual sending is driven by provider_var in _start_sending."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        # sending_mode_var was removed because it was not connected to any sending logic
        self.assertNotIn('sending_mode_var', content)

    def test_all_original_tabs_preserved(self):
        """Verify all original tabs still exist."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        expected_tabs = [
            "✉️ Campaign", "🖥️ VPS Bulk Sender", "🚀 Direct MX Sender",
            "⚙️ Settings", "🛡️ Deliverability", "💧 Sequences",
            "📈 Visual Analytics", "🏷️ Placeholders", "🌐 DNS Checker", "📜 Sent Log"
        ]
        for tab in expected_tabs:
            self.assertIn(tab, content, f"Missing tab: {tab}")

    def test_smtp_handler_preserved(self):
        """Verify SMTP handler initialization is intact."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('self.smtp_handler = SMTPHandler(self)', content)

    def test_direct_mx_handler_preserved(self):
        """Verify Direct MX handler is intact."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('self.direct_mx_handler = DirectMXHandler(self)', content)

    def test_proxy_vps_handler_preserved(self):
        """Verify Proxy VPS handler is intact."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('self.proxy_vps_handler = ProxyVPSHandler(self)', content)

    def test_no_logic_modification(self):
        """Verify core sending logic methods are not modified (spot check)."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        # These core methods should still exist
        self.assertIn('def _start_sending(self', content)
        self.assertIn('def _stop_sending(self)', content)
        self.assertIn('def _toggle_pause(self)', content)
        self.assertIn('def _start_direct_mx_sending(self)', content)


class TestDirectMXSourceIPBinding(unittest.TestCase):
    """Tests for Direct MX source IP binding and EHLO hostname configuration."""

    def test_source_ip_field_exists_in_handler(self):
        """Verify DirectMXHandler has source_ip field."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('self.source_ip = ""', content)

    def test_ehlo_hostname_field_exists_in_handler(self):
        """Verify DirectMXHandler has ehlo_hostname field."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('self.ehlo_hostname = ""', content)

    def test_source_ip_loaded_from_settings(self):
        """Verify source_ip is loaded from settings file."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('settings.get("mx_source_ip"', content)

    def test_ehlo_hostname_loaded_from_settings(self):
        """Verify ehlo_hostname is loaded from settings file."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('settings.get("mx_ehlo_hostname"', content)

    def test_source_ip_saved_to_settings(self):
        """Verify source_ip is saved to settings file."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('"mx_source_ip":', content)

    def test_ehlo_hostname_saved_to_settings(self):
        """Verify ehlo_hostname is saved to settings file."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('"mx_ehlo_hostname":', content)

    def test_ehlo_uses_sender_domain_not_localhost(self):
        """Verify EHLO no longer uses hardcoded 'localhost'."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        # The _send_via_mx method should not contain 'EHLO localhost'
        # Instead it should use ehlo_cmd variable with sender domain
        self.assertIn("ehlo_hostname = self.ehlo_hostname if self.ehlo_hostname else sender_domain", content)
        self.assertIn("ehlo_cmd = f'EHLO {ehlo_hostname}", content)
        # Should NOT have hardcoded 'EHLO localhost' in the _send_via_mx method
        # Check that there's no "b'EHLO localhost" after _send_via_mx definition
        send_via_mx_idx = content.index("async def _send_via_mx")
        # Find the next method definition after _send_via_mx
        next_method = content.index("\n    async def _read_smtp_response", send_via_mx_idx)
        mx_method_body = content[send_via_mx_idx:next_method]
        self.assertNotIn("b'EHLO localhost", mx_method_body)

    def test_source_ip_used_in_connection(self):
        """Verify asyncio.open_connection uses local_addr when source_ip is set."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        # Helper method should build connect kwargs with local_addr
        self.assertIn("def _get_mx_connect_kwargs(self)", content)
        self.assertIn("kwargs['local_addr'] = (self.source_ip, 0)", content)
        # Connection calls should use the helper or connect_kwargs
        self.assertIn("self._get_mx_connect_kwargs()", content)

    def test_gui_source_ip_var_exists(self):
        """Verify GUI variable for source IP exists."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('self.mx_source_ip_var = tk.StringVar', content)

    def test_gui_ehlo_hostname_var_exists(self):
        """Verify GUI variable for EHLO hostname exists."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('self.mx_ehlo_hostname_var = tk.StringVar', content)

    def test_gui_network_config_section(self):
        """Verify Network Configuration section exists in Direct MX GUI."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn("Network Configuration (SPF Alignment)", content)
        self.assertIn("Source IP (VPS IP)", content)
        self.assertIn("EHLO Hostname", content)

    def test_source_ip_passed_to_handler_on_send(self):
        """Verify source_ip is transferred from GUI var to handler before sending."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('self.direct_mx_handler.source_ip = self.mx_source_ip_var.get()', content)
        self.assertIn('self.direct_mx_handler.ehlo_hostname = self.mx_ehlo_hostname_var.get()', content)


class TestDKIMErrorMessages(unittest.TestCase):
    """Tests for improved DKIM error messaging."""

    def test_dkim_missing_fields_reported_individually(self):
        """Verify DKIM signing reports which specific fields are missing."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('Private key not configured', content)
        self.assertIn('Selector not set', content)
        self.assertIn('Domain not set', content)

    def test_dkim_library_missing_reported(self):
        """Verify clear message when dkimpy library is not installed."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('dkimpy library not installed', content)

    def test_dkim_missing_fields_point_to_settings(self):
        """Verify DKIM error message tells user where to configure."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('Configure via Settings > DKIM Configuration', content)


class TestDirectMXGUIControl(unittest.TestCase):
    """Tests for Direct MX GUI control panel and lifecycle management."""

    def test_direct_mx_state_machine_vars(self):
        """Verify Direct MX state machine variables exist."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('self.direct_mx_running = False', content)
        self.assertIn('self.direct_mx_paused = False', content)
        self.assertIn('self.direct_mx_task = None', content)
        self.assertIn('self.direct_mx_loop = None', content)

    def test_direct_mx_live_status_panel(self):
        """Verify live status panel labels exist."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('mx_status_indicator', content)
        self.assertIn('mx_queue_depth_label', content)
        self.assertIn('mx_success_count_label', content)
        self.assertIn('mx_failure_count_label', content)

    def test_direct_mx_live_status_update_method(self):
        """Verify live status update method exists."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('def _update_direct_mx_live_status(self)', content)
        self.assertIn('Status: Running', content)
        self.assertIn('Status: Paused', content)
        self.assertIn('Status: Stopped', content)

    def test_direct_mx_start_sets_state(self):
        """Verify start sets running state and calls live status."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('self.direct_mx_running = True', content)
        self.assertIn('self.direct_mx_paused = False', content)
        self.assertIn('self._update_direct_mx_live_status()', content)

    def test_direct_mx_stop_cancels_task(self):
        """Verify stop cancels async task."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('self.direct_mx_task.cancel()', content)
        self.assertIn('self.direct_mx_running = False', content)

    def test_direct_mx_pause_uses_dedicated_flag(self):
        """Verify pause uses direct_mx_paused flag."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('self.direct_mx_paused = True', content)

    def test_test_mx_connection_button(self):
        """Verify Test MX Connection method exists."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('def _test_mx_connection(self)', content)
        self.assertIn('Test MX Connection', content)

    def test_validate_network_button(self):
        """Verify Validate Network method exists."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('def _validate_mx_network(self)', content)
        self.assertIn('Validate Network', content)

    def test_dkim_test_button(self):
        """Verify Test DKIM Sign method exists."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('def _test_dkim_signing(self)', content)
        self.assertIn('Test DKIM Sign', content)

    def test_direct_mx_counters(self):
        """Verify Direct MX counters exist."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('self.direct_mx_sent_count = 0', content)
        self.assertIn('self.direct_mx_failed_count = 0', content)
        self.assertIn('self.direct_mx_retry_count = 0', content)


class TestDirectMXButtonFixes(unittest.TestCase):
    """Tests for Direct MX Start/Pause/Stop button wiring fixes."""

    def test_mx_send_loop_checks_direct_mx_running(self):
        """Verify the MX send loop checks direct_mx_running for stop support."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('not self.main_app.direct_mx_running', content)

    def test_mx_send_loop_has_pause_support(self):
        """Verify the MX send loop has pause wait logic with direct_mx_paused."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('while self.main_app.direct_mx_paused:', content)
        self.assertIn('await asyncio.sleep(0.5)', content)

    def test_mx_send_loop_increments_direct_mx_counters(self):
        """Verify send loop increments direct_mx_sent_count and direct_mx_failed_count."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('self.main_app.direct_mx_sent_count += 1', content)
        self.assertIn('self.main_app.direct_mx_failed_count += 1', content)

    def test_finalize_sending_resets_direct_mx_state(self):
        """Verify _finalize_sending resets Direct MX running state."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        # Find _finalize_sending method and verify it resets direct_mx_running
        finalize_idx = content.index('def _finalize_sending(self)')
        finalize_body = content[finalize_idx:finalize_idx + 1500]
        self.assertIn('self.direct_mx_running = False', finalize_body)
        self.assertIn('self.direct_mx_paused = False', finalize_body)

    def test_finalize_sending_resets_mx_buttons(self):
        """Verify _finalize_sending re-enables the MX start button."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        finalize_idx = content.index('def _finalize_sending(self)')
        finalize_body = content[finalize_idx:finalize_idx + 1500]
        self.assertIn('mx_start_btn', finalize_body)
        self.assertIn('mx_pause_btn', finalize_body)
        self.assertIn('mx_stop_btn', finalize_body)

    def test_batch_loop_checks_stop_flag(self):
        """Verify the batch processing loop checks running/direct_mx_running before each batch."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        # Find the batch processing section of run_direct_mx_sending_job
        job_idx = content.index('def run_direct_mx_sending_job')
        job_body = content[job_idx:job_idx + 2000]
        # Batch loop should break if not running
        self.assertIn('if not self.main_app.running or not self.main_app.direct_mx_running:', job_body)


class TestFStringBackslashFix(unittest.TestCase):
    """Tests that f-string expressions do not contain backslashes (Python 3.10 compatibility)."""

    def test_no_backslash_in_fstring_expressions(self):
        """Verify no f-string expression parts contain backslashes (SyntaxError on Python <3.12)."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        # Find all f-string expressions with backslashes inside curly braces
        # Pattern: inside an f-string, {expression_with_backslash}
        # We look for the specific problematic pattern that was fixed
        self.assertNotIn(
            r"socks.PROXY_TYPE_SOCKS5, \\'",
            content,
            "Found backslash inside f-string expression (Python 3.10 incompatible)"
        )

    def test_proxy_setup_line_variable_used(self):
        """Verify proxy setup is extracted into a variable instead of inline f-string expression."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('proxy_setup_line = ""', content)
        self.assertIn("{proxy_setup_line}", content)

    def test_file_parses_as_valid_python(self):
        """Verify the source file parses without SyntaxError."""
        import ast
        with open('paris_sender_complete1.py', 'r') as f:
            source = f.read()
        # This will raise SyntaxError if the file has any syntax issues
        ast.parse(source)


class TestWarmupEnforcement(unittest.TestCase):
    """Tests that warmup mode limits are enforced during sending."""

    def test_warmup_check_in_sending_loop(self):
        """Verify warmup limit check exists in _sending_process_threaded."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _sending_process_threaded')
        method_body = content[idx:idx + 1500]
        self.assertIn('warmup_mode.get()', method_body,
                      "Warmup mode should be checked in the sending loop")
        self.assertIn('_get_warmup_sends_for_today', method_body,
                      "Warmup sends limit should be checked in the sending loop")
        self.assertIn('Warmup limit reached', method_body,
                      "Warmup limit reached message should be logged")

    def test_warmup_daily_count_incremented_on_success(self):
        """Verify warmup daily count is incremented after a successful send."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _process_single_email')
        method_body = content[idx:idx + 3000]
        self.assertIn('warmup_mode.get()', method_body,
                      "Warmup daily count should be updated in _process_single_email")
        self.assertIn('daily_counts', method_body,
                      "daily_counts should be updated on successful send")

    def test_get_warmup_sends_for_today_logic(self):
        """Test the warmup schedule calculation logic."""
        from datetime import date
        schedule = [10, 20, 40, 80, 150, 300, 500]

        # Day 0 (first day): limit is 10
        self.assertEqual(schedule[0], 10)
        # Day 6 (last scheduled day): limit is 500
        self.assertEqual(schedule[6], 500)
        # After schedule completes, limit should be infinite
        days_since_start = 7
        limit = float('inf') if days_since_start >= len(schedule) else schedule[days_since_start]
        self.assertEqual(limit, float('inf'))

        # Remaining sends calculation
        limit = schedule[0]  # Day 0: max 10
        sent_today = 7
        remaining = max(0, limit - sent_today)
        self.assertEqual(remaining, 3)

        # When sent_today >= limit, remaining should be 0
        sent_today = 10
        remaining = max(0, limit - sent_today)
        self.assertEqual(remaining, 0)


class TestInboxPlacementVerification(unittest.TestCase):
    """Tests that inbox placement verification uses real IMAP checks instead of random simulation."""

    def test_no_random_simulation_in_seed_check(self):
        """Verify the seed check no longer uses random.random() for spam detection."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        # Find the seed list verification section
        idx = content.index('# Seed list inbox verification')
        section = content[idx:idx + 3000]
        self.assertNotIn('random.random()', section,
                         "Seed inbox check should not use random simulation")

    def test_imap_based_seed_check(self):
        """Verify the seed check uses IMAP to check spam folders."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('# Seed list inbox verification')
        section = content[idx:idx + 3000]
        self.assertIn('IMAP4_SSL', section,
                      "Seed check should use IMAP4_SSL for inbox verification")
        self.assertIn('spam_folders', section,
                      "Seed check should check spam/junk folders")
        self.assertIn('spam_seeds_found', section,
                      "Seed check should track which seeds landed in spam")


class TestDeliverabilityLinkHealthCheck(unittest.TestCase):
    """Tests that _run_link_health_check displays results in deliv_results_text."""

    def test_link_health_writes_to_deliv_results(self):
        """Verify _run_link_health_check writes results to deliv_results_text widget."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _run_link_health_check')
        method_body = content[idx:idx + 2000]
        self.assertIn('deliv_results_text', method_body,
                      "_run_link_health_check should display results in deliv_results_text")
        self.assertIn('Link Health Check Results', method_body,
                      "_run_link_health_check should show a header in results")

    def test_link_health_shows_all_link_statuses(self):
        """Verify _run_link_health_check displays status for all links, not just bad ones."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _run_link_health_check')
        method_body = content[idx:idx + 2000]
        self.assertIn('for link, status in results.items()', method_body,
                      "_run_link_health_check should iterate over all link results")
        self.assertIn('All', method_body,
                      "_run_link_health_check should show a summary for healthy links")


class TestDirectMXScheduleButton(unittest.TestCase):
    """Tests that Direct MX tab has a Schedule button and scheduling method."""

    def test_mx_schedule_button_exists(self):
        """Verify mx_schedule_btn is created in Direct MX config frame."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('mx_schedule_btn', content,
                      "Direct MX should have a schedule button")
        self.assertIn('_open_mx_schedule_window', content,
                      "Direct MX schedule button should be wired to _open_mx_schedule_window")

    def test_mx_schedule_method_exists(self):
        """Verify _open_mx_schedule_window method exists with proper implementation."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _open_mx_schedule_window')
        method_body = content[idx:idx + 2500]
        self.assertIn('Schedule Direct MX Campaign', method_body,
                      "_open_mx_schedule_window should show MX-specific title")
        self.assertIn('_start_direct_mx_sending', method_body,
                      "_open_mx_schedule_window should schedule _start_direct_mx_sending")
        self.assertIn('schedule_timer', method_body,
                      "_open_mx_schedule_window should use schedule_timer")

    def test_campaign_schedule_btn_safely_initialized(self):
        """Verify schedule_btn is safely initialized to None before conditional creation."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('self.schedule_btn = None', content,
                      "schedule_btn should be initialized to None before TKCALENDAR check")
        self.assertIn('self.mx_schedule_btn = None', content,
                      "mx_schedule_btn should be initialized to None before TKCALENDAR check")


class TestFinalizeSendingGUIUpdates(unittest.TestCase):
    """Tests that _finalize_sending properly updates GUI for all engines."""

    def test_finalize_updates_mx_status(self):
        """Verify _finalize_sending updates MX status indicator to Completed."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _finalize_sending')
        method_body = content[idx:idx + 3000]
        self.assertIn('Status: Completed', method_body,
                      "_finalize_sending should update mx_status_indicator to Completed")
        self.assertIn('mx_success_count_label', method_body,
                      "_finalize_sending should update mx_success_count_label")
        self.assertIn('mx_failure_count_label', method_body,
                      "_finalize_sending should update mx_failure_count_label")

    def test_finalize_resets_vps_buttons(self):
        """Verify _finalize_sending resets VPS buttons on completion."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _finalize_sending')
        method_body = content[idx:idx + 3000]
        self.assertIn('vps_start_btn', method_body,
                      "_finalize_sending should reset vps_start_btn")
        self.assertIn('vps_pause_btn', method_body,
                      "_finalize_sending should reset vps_pause_btn")

    def test_stop_mx_updates_status_labels(self):
        """Verify _stop_direct_mx_sending updates status labels."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _stop_direct_mx_sending')
        method_body = content[idx:idx + 1500]
        self.assertIn('mx_status_indicator', method_body,
                      "_stop_direct_mx_sending should update mx_status_indicator")
        self.assertIn('Status: Stopped', method_body,
                      "_stop_direct_mx_sending should set status to Stopped")


class TestMIMEMultipartAlternative(unittest.TestCase):
    """Tests for RFC 1341 compliant MIME message construction (SpamAssassin HTML_IMAGE_ONLY_12 fix)."""

    def test_beautifulsoup_import_exists(self):
        """Verify BeautifulSoup import with availability flag exists."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('from bs4 import BeautifulSoup', content,
                      "BeautifulSoup should be imported from bs4")
        self.assertIn('BEAUTIFULSOUP_AVAILABLE', content,
                      "BEAUTIFULSOUP_AVAILABLE flag should exist")

    def test_html_to_text_uses_beautifulsoup_when_available(self):
        """Verify _html_to_text uses BeautifulSoup if available."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _html_to_text')
        method_body = content[idx:idx + 2500]
        self.assertIn('BEAUTIFULSOUP_AVAILABLE', method_body,
                      "_html_to_text should check for BeautifulSoup availability")
        self.assertIn('BeautifulSoup(html', method_body,
                      "_html_to_text should use BeautifulSoup for parsing")

    def test_html_to_text_has_regex_fallback(self):
        """Verify _html_to_text has regex fallback when BeautifulSoup unavailable."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _html_to_text')
        method_body = content[idx:idx + 2500]
        self.assertIn('else:', method_body,
                      "_html_to_text should have else branch for regex fallback")
        self.assertIn('re.sub', method_body,
                      "_html_to_text should use regex for stripping HTML tags")

    def test_mime_uses_alternative_root_without_attachments(self):
        """Verify MIME construction uses 'alternative' as root when no attachments."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        # Find all _create_mime_message methods
        self.assertIn("msg_root = MIMEMultipart('alternative')", content,
                      "MIME message should use 'alternative' as root when no attachments")
        # Verify conditional logic exists
        self.assertIn("has_attachments = bool(", content,
                      "MIME construction should check for attachments")

    def test_mime_uses_related_root_with_attachments(self):
        """Verify MIME construction uses 'related' as root when attachments exist."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn("if has_attachments:", content,
                      "MIME construction should have conditional for attachments")
        self.assertIn("msg_root = MIMEMultipart('related')", content,
                      "MIME message should use 'related' as root when attachments exist")

    def test_plain_text_attached_before_html(self):
        """Verify plain text is attached FIRST, HTML SECOND (RFC 1341 order)."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        # Find a _create_mime_message method and check order
        # Some methods use self._html_to_text, others use self.main_app.smtp_handler._html_to_text
        idx = content.index("def _create_mime_message")
        method_body = content[idx:idx + 3000]
        # Look for plain text attachment - it uses _html_to_text
        plain_idx = method_body.index("_html_to_text")
        html_idx = method_body.index("MIMEText(content, 'html'")
        self.assertLess(plain_idx, html_idx,
                        "Plain text MIMEText should be attached before HTML MIMEText")

    def test_html_to_text_strips_script_and_style(self):
        """Verify _html_to_text removes script and style elements."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _html_to_text')
        method_body = content[idx:idx + 2500]
        self.assertIn('script', method_body,
                      "_html_to_text should handle script tags")
        self.assertIn('style', method_body,
                      "_html_to_text should handle style tags")

    def test_html_to_text_handles_empty_input(self):
        """Verify _html_to_text handles empty or None input."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _html_to_text')
        method_body = content[idx:idx + 500]
        self.assertIn('if not html:', method_body,
                      "_html_to_text should check for empty/None input")

    def test_rfc_1341_compliance_docstrings(self):
        """Verify _create_mime_message methods document RFC 1341 compliance."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn("RFC 1341 compliance", content,
                      "MIME methods should document RFC 1341 compliance in docstrings")


class TestContentValidation(unittest.TestCase):
    """Tests for content validation to avoid HTML_IMAGE_ONLY_12 SpamAssassin penalty."""

    def test_validate_content_structure_exists(self):
        """Verify _validate_content_structure method exists."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('def _validate_content_structure', content,
                      "_validate_content_structure method should exist")

    def test_validate_checks_word_count(self):
        """Verify validation checks word count."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _validate_content_structure')
        method_body = content[idx:idx + 2000]
        self.assertIn('word_count', method_body,
                      "_validate_content_structure should count words")

    def test_validate_checks_image_count(self):
        """Verify validation checks image count."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _validate_content_structure')
        method_body = content[idx:idx + 2000]
        self.assertIn('image_count', method_body,
                      "_validate_content_structure should count images")

    def test_validate_uses_beautifulsoup_when_available(self):
        """Verify validation uses BeautifulSoup if available."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _validate_content_structure')
        method_body = content[idx:idx + 2000]
        self.assertIn('BEAUTIFULSOUP_AVAILABLE', method_body,
                      "_validate_content_structure should check BeautifulSoup availability")

    def test_validate_has_regex_fallback(self):
        """Verify validation has regex fallback."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _validate_content_structure')
        method_body = content[idx:idx + 2000]
        self.assertIn('else:', method_body,
                      "_validate_content_structure should have regex fallback")

    def test_validate_returns_tuple(self):
        """Verify validation returns (is_valid, warning_message) tuple."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _validate_content_structure')
        method_body = content[idx:idx + 2000]
        self.assertIn('return True, None', method_body,
                      "_validate_content_structure should return tuple with True and None for valid content")
        self.assertIn('return False,', method_body,
                      "_validate_content_structure should return tuple with False for invalid content")

    def test_validate_warns_low_text_ratio(self):
        """Verify validation warns about low text-to-image ratio."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _validate_content_structure')
        method_body = content[idx:idx + 2000]
        self.assertIn('Low text-to-image ratio', method_body,
                      "_validate_content_structure should warn about low text-to-image ratio")


class TestSMTPSSLContextFallback(unittest.TestCase):
    """Tests for SSL context fallback when system certificates are unavailable."""

    def test_ssl_context_has_fallback(self):
        """Verify _create_secure_ssl_context catches FileNotFoundError/OSError."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('except (FileNotFoundError, OSError):', content,
                      "_create_secure_ssl_context should catch FileNotFoundError and OSError")

    def test_ssl_context_fallback_uses_tls_client(self):
        """Verify fallback creates a TLS client context."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)', content,
                      "Fallback should use ssl.PROTOCOL_TLS_CLIENT")

    def test_ssl_context_sets_minimum_tls_version(self):
        """Verify TLS 1.2 minimum is enforced in both normal and fallback paths."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _create_secure_ssl_context')
        method_body = content[idx:idx + 500]
        self.assertIn('context.minimum_version = ssl.TLSVersion.TLSv1_2', method_body)

    def test_ssl_context_fallback_disables_verification(self):
        """Verify fallback disables cert verification when certs are unavailable."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _create_secure_ssl_context')
        method_body = content[idx:idx + 500]
        self.assertIn('context.check_hostname = False', method_body,
                      "Fallback should disable hostname checking when certs unavailable")
        self.assertIn('context.verify_mode = ssl.CERT_NONE', method_body,
                      "Fallback should disable cert verification when certs unavailable")

    def test_vps_starttls_untouched(self):
        """Verify VPS mailer does not unconditionally force STARTTLS."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertNotIn('server.starttls()', content,
                         "VPS SMTP should not call starttls() unconditionally")
        self.assertIn("has_extn('STARTTLS')", content,
                      "VPS SMTP should check has_extn('STARTTLS') before starttls()")

    def test_direct_mx_ssl_context_untouched(self):
        """Verify Direct MX handler's SSL context creation is not modified."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('async def _send_via_mx')
        method_body = content[idx:idx + 3000]
        self.assertIn('context = ssl.create_default_context()', method_body,
                      "Direct MX handler should still use ssl.create_default_context()")
        self.assertIn('context.check_hostname = False', method_body)
        self.assertIn('context.verify_mode = ssl.CERT_NONE', method_body)


class TestSMTPTestConnectionFix(unittest.TestCase):
    """Tests for the SMTP test connection function fix for Errno 2."""

    def test_test_connection_catches_file_not_found(self):
        """Verify test_connection handles FileNotFoundError with fallback."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def test_connection(self):')
        method_body = content[idx:idx + 2500]
        self.assertIn('except FileNotFoundError:', method_body,
                      "test_connection should catch FileNotFoundError explicitly")

    def test_test_connection_catches_ssl_context_oserror(self):
        """Verify ssl.create_default_context() OSError triggers no-verify fallback."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def test_connection(self):')
        method_body = content[idx:idx + 1800]
        self.assertIn('except (FileNotFoundError, OSError)', method_body,
                      "ssl.create_default_context() should catch OSError for cert file issues")

    def test_test_connection_has_fallback_method(self):
        """Verify _test_connection_no_verify fallback exists."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('def _test_connection_no_verify(self, password):', content,
                      "Should have a fallback method for connection without verification")

    def test_test_connection_no_verify_disables_ssl_checks(self):
        """Verify fallback method disables SSL verification."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _test_connection_no_verify')
        method_body = content[idx:idx + 1000]
        self.assertIn('context.check_hostname = False', method_body)
        self.assertIn('context.verify_mode = ssl.CERT_NONE', method_body)

    def test_test_connection_uses_clean_ssl_context(self):
        """Verify test_connection uses ssl.create_default_context() without file paths."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def test_connection(self):')
        method_body = content[idx:idx + 1500]
        self.assertIn('ssl.create_default_context()', method_body,
                      "test_connection should use ssl.create_default_context() without file args")
        self.assertNotIn('cafile=', method_body,
                         "test_connection should not pass cafile to SSL context")
        self.assertNotIn('certfile=', method_body,
                         "test_connection should not pass certfile to SSL context")

    def test_test_connection_has_debug_logging(self):
        """Verify test_connection logs connection details before attempting."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def test_connection(self):')
        method_body = content[idx:idx + 1500]
        self.assertIn('Testing SMTP:', method_body,
                      "test_connection should log server, port, and TLS status")
        self.assertIn('TLS=', method_body,
                      "test_connection should include TLS status in debug log")

    def test_no_hardcoded_ssl_file_paths(self):
        """Verify no hardcoded SSL file paths in SMTP test functions."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        # Get test_connection and _test_connection_no_verify methods
        idx1 = content.index('def test_connection(self):')
        idx2 = content.index('def _test_connection_no_verify')
        # Use a generous slice from test_connection through _test_connection_no_verify
        test_methods = content[idx1:idx2 + 1500]
        self.assertNotIn('.pem', test_methods,
                         "SMTP test methods should not reference .pem files")
        self.assertNotIn('cafile=', test_methods,
                         "SMTP test methods should not use cafile parameter")
        self.assertNotIn('keyfile=', test_methods,
                         "SMTP test methods should not use keyfile parameter")

    def test_fallback_no_verify_uses_bare_ssl_context(self):
        """Verify fallback does not use ssl.create_default_context (which may also fail)."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _test_connection_no_verify')
        method_body = content[idx:idx + 1000]
        self.assertIn('ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)', method_body,
                      "Fallback should use bare SSLContext to avoid cert file issues")


class TestDetectTlsMode(unittest.TestCase):
    """Tests for the detect_tls_mode function logic."""

    def test_port_465_returns_ssl(self):
        """Port 465 should use SSL (implicit TLS)."""
        # Replicate detect_tls_mode logic
        port = 465
        if port == 465:
            use_ssl, use_starttls = True, False
        elif port in (587, 2525):
            use_ssl, use_starttls = False, True
        else:
            use_ssl, use_starttls = False, False
        self.assertTrue(use_ssl)
        self.assertFalse(use_starttls)

    def test_port_587_returns_starttls(self):
        """Port 587 should use STARTTLS."""
        port = 587
        if port == 465:
            use_ssl, use_starttls = True, False
        elif port in (587, 2525):
            use_ssl, use_starttls = False, True
        else:
            use_ssl, use_starttls = False, False
        self.assertFalse(use_ssl)
        self.assertTrue(use_starttls)

    def test_port_2525_returns_starttls(self):
        """Port 2525 should use STARTTLS."""
        port = 2525
        if port == 465:
            use_ssl, use_starttls = True, False
        elif port in (587, 2525):
            use_ssl, use_starttls = False, True
        else:
            use_ssl, use_starttls = False, False
        self.assertFalse(use_ssl)
        self.assertTrue(use_starttls)

    def test_port_25_returns_plain(self):
        """Port 25 should use plain SMTP (no SSL, no STARTTLS)."""
        port = 25
        if port == 465:
            use_ssl, use_starttls = True, False
        elif port in (587, 2525):
            use_ssl, use_starttls = False, True
        else:
            use_ssl, use_starttls = False, False
        self.assertFalse(use_ssl)
        self.assertFalse(use_starttls)


class TestUniversalSmtpSendStructure(unittest.TestCase):
    """Tests to verify universal_smtp_send and detect_tls_mode exist and are correct in the source."""

    def test_detect_tls_mode_function_exists(self):
        """Verify detect_tls_mode function exists in source code."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('def detect_tls_mode(', content,
                      "detect_tls_mode function should exist in the source")

    def test_universal_smtp_send_function_exists(self):
        """Verify universal_smtp_send function exists in source code."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('def universal_smtp_send(', content,
                      "universal_smtp_send function should exist in the source")

    def test_no_aiosmtplib_import(self):
        """Verify aiosmtplib is no longer imported."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertNotIn('import aiosmtplib', content,
                         "aiosmtplib should not be imported")

    def test_no_aiosmtplib_send_calls(self):
        """Verify no await aiosmtplib.send calls remain."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertNotIn('await aiosmtplib', content,
                         "No await aiosmtplib calls should remain")
        self.assertNotIn('aiosmtplib.SMTP(', content,
                         "No aiosmtplib.SMTP() constructor calls should remain")
        self.assertNotIn('aiosmtplib.errors', content,
                         "No aiosmtplib.errors references should remain")

    def test_universal_smtp_send_supports_ssl(self):
        """Verify universal_smtp_send uses smtplib.SMTP (not SMTP_SSL) for all modes including SSL."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def universal_smtp_send(')
        func_body = content[idx:idx + 2500]
        self.assertNotIn('smtplib.SMTP_SSL(', func_body,
                      "universal_smtp_send should NOT use SMTP_SSL - use SMTP with STARTTLS instead")
        self.assertIn('smtplib.SMTP(', func_body,
                      "universal_smtp_send should always use smtplib.SMTP()")

    def test_universal_smtp_send_supports_starttls(self):
        """Verify universal_smtp_send handles STARTTLS mode."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def universal_smtp_send(')
        func_body = content[idx:idx + 2000]
        self.assertIn('starttls', func_body,
                      "universal_smtp_send should use starttls for STARTTLS mode")

    def test_universal_smtp_send_returns_tuple(self):
        """Verify universal_smtp_send returns (success, message) tuples."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def universal_smtp_send(')
        func_body = content[idx:idx + 4000]
        self.assertIn('return True, "Sent successfully"', func_body,
                      "universal_smtp_send should return success tuple")
        self.assertIn('return False,', func_body,
                      "universal_smtp_send should return failure tuples")

    def test_universal_smtp_send_handles_auth_error(self):
        """Verify universal_smtp_send catches SMTPAuthenticationError."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def universal_smtp_send(')
        func_body = content[idx:idx + 4000]
        self.assertIn('SMTPAuthenticationError', func_body,
                      "universal_smtp_send should catch SMTPAuthenticationError")

    def test_universal_smtp_send_handles_ssl_error(self):
        """Verify universal_smtp_send catches SSLError."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def universal_smtp_send(')
        func_body = content[idx:idx + 8000]
        self.assertIn('ssl.SSLError', func_body,
                      "universal_smtp_send should catch ssl.SSLError (EOF errors)")

    def test_detect_tls_mode_used_in_threaded_send(self):
        """Verify detect_tls_mode is used in the threaded send path."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _send_single_email_threaded(')
        func_body = content[idx:idx + 3000]
        self.assertIn('detect_tls_mode(', func_body,
                      "_send_single_email_threaded should call detect_tls_mode")

    def test_universal_smtp_send_used_in_threaded_send(self):
        """Verify universal_smtp_send is used in the threaded send path."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _send_single_email_threaded(')
        func_body = content[idx:idx + 3000]
        self.assertIn('universal_smtp_send(', func_body,
                      "_send_single_email_threaded should call universal_smtp_send")

    def test_uses_ssl_create_default_context(self):
        """Verify universal_smtp_send uses ssl.create_default_context() instead of custom cert files."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def universal_smtp_send(')
        func_body = content[idx:idx + 2000]
        self.assertIn('ssl.create_default_context()', func_body,
                      "universal_smtp_send should use ssl.create_default_context()")
        self.assertNotIn('cafile', func_body,
                         "universal_smtp_send should not reference cafile")

    def test_universal_smtp_send_normalizes_login_credentials(self):
        """Verify universal_smtp_send normalizes username and password before login (SMTP auth fix)."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def universal_smtp_send(')
        func_body = content[idx:idx + 4000]
        self.assertIn('parseaddr', func_body,
                      "universal_smtp_send should use parseaddr() to extract full email username")
        self.assertIn("rstrip('\\r\\n')", func_body,
                      "universal_smtp_send should trim CRLF from password to avoid auth failures")


class TestSMTPSendingWiring(unittest.TestCase):
    """Tests to verify SMTP sending is properly wired in the main GUI campaign flow."""

    def setUp(self):
        with open('paris_sender_complete1.py', 'r') as f:
            self.content = f.read()

    def test_start_sending_routes_smtp_to_handler(self):
        """Verify _start_sending routes SMTP provider to smtp_handler.run_sending_job."""
        idx = self.content.index('def _start_sending(')
        func_body = self.content[idx:idx + 2000]
        self.assertIn('elif provider == "SMTP":', func_body,
                      "_start_sending should have an explicit SMTP provider branch")
        self.assertIn('self.smtp_handler.run_sending_job(', func_body,
                      "_start_sending should route SMTP to smtp_handler.run_sending_job")

    def test_send_single_email_handles_smtp(self):
        """Verify _send_single_email has an SMTP provider path."""
        idx = self.content.index('def _send_single_email(')
        func_body = self.content[idx:idx + 2000]
        self.assertIn('provider == "SMTP"', func_body,
                      "_send_single_email should handle SMTP provider")

    def test_smtp_handler_run_sending_job_uses_prepare_email_data(self):
        """Verify SMTPHandler.send_bulk_emails_threaded uses _prepare_email_data for autograb."""
        idx = self.content.index('def send_bulk_emails_threaded(')
        func_body = self.content[idx:idx + 2000]
        self.assertIn('_prepare_email_data(', func_body,
                      "send_bulk_emails_threaded should use _prepare_email_data for personalization/autograb")

    def test_smtp_handler_run_sending_job_uses_rotation_profiles(self):
        """Verify SMTPHandler.send_bulk_emails_threaded uses rotation profiles."""
        idx = self.content.index('def send_bulk_emails_threaded(')
        func_body = self.content[idx:idx + 2000]
        self.assertIn('get_rotation_profiles()', func_body,
                      "send_bulk_emails_threaded should use rotation profiles")

    def test_no_dead_sending_mode_ui(self):
        """Verify the unused sending_mode_var UI elements were removed."""
        self.assertNotIn('sending_mode_var', self.content,
                         "sending_mode_var should be removed as it was not wired to any logic")

    def test_gui_has_envelope_and_reply_chain_override_vars(self):
        """Verify GUI exposes optional envelope/reply-thread fields (wiring for new SMTP features)."""
        self.assertIn('envelope_from_override_var', self.content,
                      "GUI should define envelope_from_override_var")
        self.assertIn('from_header_override_var', self.content,
                      "GUI should define from_header_override_var for spoofing From header")
        self.assertIn('in_reply_to_override_var', self.content,
                      "GUI should define in_reply_to_override_var")
        self.assertIn('references_override_var', self.content,
                      "GUI should define references_override_var")
        self.assertIn('custom_headers_enabled_var', self.content,
                      "GUI should define custom_headers_enabled_var for spoofing toggle")
        self.assertIn('vps_from_header_var', self.content,
                      "GUI should define vps_from_header_var for VPS From header spoofing")

    def test_prepare_email_data_includes_envelope_and_reply_chain_fields(self):
        """Verify _prepare_email_data includes envelope_from / in_reply_to / references keys."""
        idx = self.content.index('def _prepare_email_data(')
        func_body = self.content[idx:idx + 4000]
        self.assertIn('custom_headers_enabled_var', func_body,
                      "_prepare_email_data should gate custom headers by custom_headers_enabled_var")
        self.assertIn('random_sender_pool_var', func_body,
                      "_prepare_email_data should reference Random Sender Pool for display-name spoofing")
        self.assertIn('parseaddr(', func_body,
                      "_prepare_email_data should parse pool entries safely (parseaddr)")
        self.assertIn('"from_header":', func_body,
                      "_prepare_email_data should include from_header field")
        self.assertIn('"envelope_from":', func_body,
                      "_prepare_email_data should include envelope_from field")
        self.assertIn('"in_reply_to":', func_body,
                      "_prepare_email_data should include in_reply_to field")
        self.assertIn('"references":', func_body,
                      "_prepare_email_data should include references field")

    def test_create_mime_message_accepts_smtp_and_reply_args(self):
        """Verify SMTPHandler._create_mime_message accepts envelope/reply-chain args for **email_data calls."""
        idx_class = self.content.index('class SMTPHandler:')
        idx = self.content.index('def _create_mime_message(', idx_class)
        sig = self.content[idx:self.content.index('):', idx) + 2]
        self.assertIn('envelope_from=None', sig,
                      "SMTPHandler._create_mime_message should accept envelope_from")
        self.assertIn('from_header=None', sig,
                      "SMTPHandler._create_mime_message should accept from_header")
        self.assertIn('in_reply_to=None', sig,
                      "SMTPHandler._create_mime_message should accept in_reply_to")
        self.assertIn('references=None', sig,
                      "SMTPHandler._create_mime_message should accept references")


class TestSTARTTLSAndInsecureSSL(unittest.TestCase):
    """Tests for STARTTLS connection logic, insecure SSL support, and SMTPServerDisconnected handling."""

    def setUp(self):
        with open('paris_sender_complete1.py', 'r') as f:
            self.content = f.read()

    def test_universal_smtp_send_has_allow_insecure_ssl_param(self):
        """Verify universal_smtp_send accepts allow_insecure_ssl parameter."""
        idx = self.content.index('def universal_smtp_send(')
        func_sig = self.content[idx:idx + 500]
        self.assertIn('allow_insecure_ssl', func_sig,
                      "universal_smtp_send should accept allow_insecure_ssl parameter")

    def test_universal_smtp_send_has_envelope_and_reply_chain_params(self):
        """Verify universal_smtp_send accepts envelope_from / in_reply_to / references parameters."""
        idx = self.content.index('def universal_smtp_send(')
        func_sig = self.content[idx:idx + 800]
        self.assertIn('envelope_from', func_sig,
                      "universal_smtp_send should accept envelope_from parameter")
        self.assertIn('in_reply_to', func_sig,
                      "universal_smtp_send should accept in_reply_to parameter")
        self.assertIn('references', func_sig,
                      "universal_smtp_send should accept references parameter")

    def test_universal_smtp_send_envelope_mode_uses_sendmail(self):
        """Verify universal_smtp_send uses server.sendmail when envelope_from is provided."""
        idx = self.content.index('def universal_smtp_send(')
        func_body = self.content[idx:idx + 4000]
        self.assertIn('if envelope_from', func_body,
                      "universal_smtp_send should branch on envelope_from")
        self.assertIn('server.sendmail(envelope_from', func_body,
                      "Envelope mode should use server.sendmail(envelope_from, ...)")
        self.assertIn('message.as_string()', func_body,
                      "Envelope mode should send message.as_string() to preserve headers")

    def test_universal_smtp_send_injects_reply_chain_headers(self):
        """Verify universal_smtp_send injects In-Reply-To and References headers when provided."""
        idx = self.content.index('def universal_smtp_send(')
        func_body = self.content[idx:idx + 2000]
        self.assertIn('In-Reply-To', func_body,
                      "universal_smtp_send should reference 'In-Reply-To' for reply threading")
        self.assertIn('References', func_body,
                      "universal_smtp_send should reference 'References' for reply threading")


class TestVpsEnvelopeAndReplyChainWiring(unittest.TestCase):
    """Source-structure tests for VPS envelope mode and reply-chain support."""

    def setUp(self):
        with open('paris_sender_complete1.py', 'r') as f:
            self.content = f.read()

    def test_send_via_vps_signature_accepts_new_params(self):
        self.assertIn('def send_via_vps(self, email_data, vps_config, envelope_from=None, in_reply_to=None, references=None):', self.content,
                      "ProxyVPSHandler.send_via_vps should accept new optional parameters")

    def test_send_via_vps_uses_actual_sender_in_remote_sendmail(self):
        self.assertIn("actual_sender = email_data.get('envelope_from') or sender_email", self.content,
                      "send_via_vps should compute actual_sender from envelope_from or sender_email")
        self.assertIn("server.sendmail('{actual_sender_escaped}'", self.content,
                      "send_via_vps remote script should sendmail using actual_sender")

    def test_vps_smtp_paths_do_not_force_starttls(self):
        """Verify VPS SMTP test/sender only uses STARTTLS when advertised (has_extn)."""
        self.assertIn("has_extn('STARTTLS')", self.content,
                      "VPS SMTP scripts should check has_extn('STARTTLS') before starttls()")
        self.assertNotIn("server.starttls()", self.content,
                         "VPS SMTP scripts should not unconditionally call starttls()")

    def test_universal_smtp_send_checks_has_extn_starttls(self):
        """Verify universal_smtp_send checks server.has_extn('STARTTLS') before upgrading."""
        idx = self.content.index('def universal_smtp_send(')
        func_body = self.content[idx:idx + 2500]
        self.assertIn("has_extn('STARTTLS')", func_body,
                      "universal_smtp_send should check has_extn('STARTTLS') before starttls()")

    def test_universal_smtp_send_catches_smtp_server_disconnected(self):
        """Verify universal_smtp_send catches SMTPServerDisconnected for retry logic."""
        idx = self.content.index('def universal_smtp_send(')
        func_body = self.content[idx:idx + 2500]
        self.assertIn('SMTPServerDisconnected', func_body,
                      "universal_smtp_send should catch SMTPServerDisconnected")

    def test_universal_smtp_send_starttls_fallback(self):
        """Verify universal_smtp_send retries without STARTTLS on disconnect."""
        idx = self.content.index('def universal_smtp_send(')
        func_body = self.content[idx:idx + 8000]
        self.assertIn('starttls_enabled=False', func_body,
                      "universal_smtp_send should retry with starttls_enabled=False on disconnect")

    def test_universal_smtp_send_insecure_ssl_disables_hostname_check(self):
        """Verify SSL context always disables check_hostname and sets CERT_NONE (Universal Fix)."""
        idx = self.content.index('def universal_smtp_send(')
        func_body = self.content[idx:idx + 2500]
        self.assertIn('check_hostname = False', func_body,
                      "SSL context should disable check_hostname")
        self.assertIn('ssl.CERT_NONE', func_body,
                      "SSL context should set verify_mode to CERT_NONE")

    def test_universal_smtp_send_uses_smtplib_smtp_not_ssl_for_starttls(self):
        """Verify universal_smtp_send always uses smtplib.SMTP (never SMTP_SSL) for all connections."""
        idx = self.content.index('def universal_smtp_send(')
        func_body = self.content[idx:idx + 2500]
        self.assertIn('smtplib.SMTP(host, port', func_body,
                      "Should always use smtplib.SMTP, not SMTP_SSL")
        self.assertNotIn('smtplib.SMTP_SSL(', func_body,
                      "Should never use smtplib.SMTP_SSL")

    def test_universal_smtp_send_does_not_shadow_parseaddr(self):
        """Verify universal_smtp_send does not create a local parseaddr that breaks auth normalization."""
        idx = self.content.index('def universal_smtp_send(')
        func_body = self.content[idx:idx + 4000]
        self.assertNotIn('from email.utils import getaddresses, parseaddr', func_body,
                         "universal_smtp_send should not import parseaddr locally (would shadow global parseaddr)")

    def test_smtp_handler_has_allow_insecure_ssl_attribute(self):
        """Verify SMTPHandler __init__ sets allow_insecure_ssl."""
        idx = self.content.index('class SMTPHandler:')
        init_body = self.content[idx:idx + 1000]
        self.assertIn('allow_insecure_ssl', init_body,
                      "SMTPHandler should have allow_insecure_ssl attribute")

    def test_configure_smtp_accepts_allow_insecure_ssl(self):
        """Verify configure_smtp method accepts allow_insecure_ssl parameter."""
        idx = self.content.index('def configure_smtp(')
        sig_body = self.content[idx:idx + 300]
        self.assertIn('allow_insecure_ssl', sig_body,
                      "configure_smtp should accept allow_insecure_ssl parameter")

    def test_configure_smtp_does_not_force_sender_email_to_username(self):
        """Verify sender_email is set independently from username when provided."""
        idx = self.content.index('def configure_smtp(')
        func_body = self.content[idx:idx + 800]
        self.assertIn('sender_email if sender_email', func_body,
                      "configure_smtp should preserve sender_email separately from username")

    def test_test_connection_catches_smtp_server_disconnected(self):
        """Verify test_connection handles SMTPServerDisconnected."""
        idx = self.content.index('def test_connection(self):')
        method_body = self.content[idx:idx + 2500]
        self.assertIn('SMTPServerDisconnected', method_body,
                      "test_connection should catch SMTPServerDisconnected")

    def test_test_connection_no_verify_catches_smtp_server_disconnected(self):
        """Verify _test_connection_no_verify handles SMTPServerDisconnected."""
        idx = self.content.index('def _test_connection_no_verify(')
        method_body = self.content[idx:idx + 2000]
        self.assertIn('SMTPServerDisconnected', method_body,
                      "_test_connection_no_verify should catch SMTPServerDisconnected")

    def test_test_connection_insecure_ssl_context(self):
        """Verify test_connection always sets insecure SSL context (Universal Fix)."""
        idx = self.content.index('def test_connection(self):')
        method_body = self.content[idx:idx + 2500]
        self.assertIn('check_hostname = False', method_body,
                      "test_connection should set check_hostname = False")
        self.assertIn('CERT_NONE', method_body,
                      "test_connection should set verify_mode = CERT_NONE")

    def test_allow_insecure_ssl_propagated_to_universal_send(self):
        """Verify allow_insecure_ssl is passed from profile config to universal_smtp_send."""
        idx = self.content.index('def _send_single_email_threaded(')
        func_body = self.content[idx:idx + 3000]
        self.assertIn('allow_insecure_ssl', func_body,
                      "_send_single_email_threaded should pass allow_insecure_ssl to universal_smtp_send")

    def test_default_profile_includes_allow_insecure_ssl(self):
        """Verify get_rotation_profiles default profile includes allow_insecure_ssl."""
        idx = self.content.index('def get_rotation_profiles(')
        func_body = self.content[idx:idx + 3000]
        self.assertIn('allow_insecure_ssl', func_body,
                      "get_rotation_profiles should include allow_insecure_ssl in profiles")

    def test_detect_tls_mode_port_2525_is_starttls(self):
        """Verify detect_tls_mode returns STARTTLS for port 2525 (Postal)."""
        idx = self.content.index('def detect_tls_mode(')
        func_body = self.content[idx:idx + 500]
        self.assertIn('2525', func_body,
                      "detect_tls_mode should handle port 2525 for STARTTLS")
        # Port 2525 should be in the STARTTLS branch (False, True), not the SSL branch (True, False)
        self.assertIn('587, 2525', func_body,
                      "Port 2525 should be grouped with 587 for STARTTLS mode")

    def test_smtp_config_ui_has_insecure_ssl_checkbox(self):
        """Verify the SMTP config UI has an 'Allow Insecure SSL' checkbox."""
        idx = self.content.index('def _open_smtp_config(')
        func_body = self.content[idx:idx + 5000]
        self.assertIn('Allow Insecure SSL', func_body,
                      "SMTP config UI should have 'Allow Insecure SSL' checkbox")
        self.assertIn('insecure_ssl_var', func_body,
                      "SMTP config UI should use insecure_ssl_var for the checkbox")

    def test_no_smtp_ssl_in_test_connection(self):
        """Verify test_connection never uses SMTP_SSL (Universal Fix)."""
        idx = self.content.index('def test_connection(self):')
        method_body = self.content[idx:idx + 2500]
        self.assertNotIn('SMTP_SSL', method_body,
                      "test_connection should not use SMTP_SSL")
        self.assertIn('smtplib.SMTP(', method_body,
                      "test_connection should use smtplib.SMTP()")

    def test_no_smtp_ssl_in_test_connection_no_verify(self):
        """Verify _test_connection_no_verify never uses SMTP_SSL (Universal Fix)."""
        idx = self.content.index('def _test_connection_no_verify(')
        method_body = self.content[idx:idx + 2000]
        self.assertNotIn('SMTP_SSL', method_body,
                      "_test_connection_no_verify should not use SMTP_SSL")
        self.assertIn('smtplib.SMTP(', method_body,
                      "_test_connection_no_verify should use smtplib.SMTP()")

    def test_universal_fix_pattern_ehlo_starttls_ehlo(self):
        """Verify universal_smtp_send follows the ehlo -> starttls -> ehlo pattern."""
        idx = self.content.index('def universal_smtp_send(')
        func_body = self.content[idx:idx + 2500]
        # Verify the pattern: SMTP() -> ehlo() -> starttls() -> ehlo()
        smtp_pos = func_body.index('smtplib.SMTP(')
        ehlo1_pos = func_body.index('server.ehlo()', smtp_pos)
        starttls_pos = func_body.index('server.starttls(', ehlo1_pos)
        ehlo2_pos = func_body.index('server.ehlo()', starttls_pos)
        self.assertGreater(ehlo1_pos, smtp_pos, "ehlo should come after SMTP()")
        self.assertGreater(starttls_pos, ehlo1_pos, "starttls should come after first ehlo")
        self.assertGreater(ehlo2_pos, starttls_pos, "second ehlo should come after starttls")


class TestSMTPAuthNormalization(unittest.TestCase):
    """Focused tests for SMTP auth normalization in connection testing."""

    def test_test_connection_normalizes_username_for_login(self):
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def test_connection(self):')
        method_body = content[idx:idx + 2500]
        self.assertIn('parseaddr', method_body,
                      "test_connection should normalize username (full email) before SMTP AUTH")


class TestHTMLRenderingAndSpamFilter(unittest.TestCase):
    """Tests for proper HTML rendering across all sending engines for spam filter compliance."""

    def test_get_message_content_plain_text_has_head_section(self):
        """Verify _get_message_content wraps plain text with proper <head> section including charset."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _get_message_content(self):')
        method_body = content[idx:idx + 1000]
        # The plain text wrapping path (else branch) should include <head> with charset
        self.assertIn("<head><meta charset='utf-8'>", method_body,
                      "_get_message_content plain text wrapping must include <head> with charset meta tag")
        self.assertIn("<meta name='viewport'", method_body,
                      "_get_message_content should include viewport meta tag for mobile rendering")

    def test_get_message_content_plain_text_wraps_in_paragraph(self):
        """Verify _get_message_content wraps plain text content in <p> tags."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _get_message_content(self):')
        method_body = content[idx:idx + 1000]
        self.assertIn("<body><p>", method_body,
                      "_get_message_content should wrap plain text in <p> tags for proper rendering")

    def test_get_vps_message_content_plain_text_has_head_section(self):
        """Verify _get_vps_message_content wraps plain text with proper <head> section."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _get_vps_message_content(self):')
        method_body = content[idx:idx + 1000]
        self.assertIn("<head><meta charset='utf-8'>", method_body,
                      "_get_vps_message_content plain text wrapping must include <head> with charset meta tag")
        self.assertIn("<meta name='viewport'", method_body,
                      "_get_vps_message_content should include viewport meta tag for mobile rendering")

    def test_get_mx_message_content_method_exists(self):
        """Verify _get_mx_message_content method exists for Direct MX sender HTML wrapping."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        self.assertIn('def _get_mx_message_content(self):', content,
                      "_get_mx_message_content method must exist for Direct MX HTML wrapping")

    def test_get_mx_message_content_has_html_structure(self):
        """Verify _get_mx_message_content wraps content with proper HTML structure."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _get_mx_message_content(self):')
        method_body = content[idx:idx + 1000]
        self.assertIn("<!DOCTYPE html>", method_body,
                      "_get_mx_message_content must include DOCTYPE declaration")
        self.assertIn("<head><meta charset='utf-8'>", method_body,
                      "_get_mx_message_content must include <head> with charset meta tag")
        self.assertIn("<body>", method_body,
                      "_get_mx_message_content must include <body> tag")

    def test_direct_mx_start_uses_get_mx_message_content(self):
        """Verify Direct MX start sending uses _get_mx_message_content() instead of raw text box read."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _start_direct_mx_sending(self):')
        method_body = content[idx:idx + 2000]
        self.assertIn('self._get_mx_message_content()', method_body,
                      "_start_direct_mx_sending must use _get_mx_message_content() for proper HTML wrapping")

    def test_html_to_text_preserves_link_urls(self):
        """Verify _html_to_text preserves link URLs for spam filter compatibility."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _html_to_text(self, html):')
        method_body = content[idx:idx + 3000]
        # Both BeautifulSoup and regex paths should preserve links
        self.assertIn("find_all('a'", method_body,
                      "_html_to_text (BeautifulSoup path) should find anchor tags to preserve URLs")
        self.assertIn('href', method_body,
                      "_html_to_text should process href attributes")

    def test_html_to_text_regex_fallback_preserves_links(self):
        """Verify _html_to_text regex fallback also preserves link URLs."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _html_to_text(self, html):')
        method_body = content[idx:idx + 3000]
        self.assertIn("<a\\s", method_body,
                      "_html_to_text regex fallback should process <a> tags to preserve link URLs")

    def test_html_to_text_skips_internal_links(self):
        """Verify _html_to_text skips javascript: and mailto: and anchor links."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _html_to_text(self, html):')
        method_body = content[idx:idx + 3000]
        self.assertIn("javascript:", method_body,
                      "_html_to_text should skip javascript: links when preserving URLs")
        self.assertIn("mailto:", method_body,
                      "_html_to_text should skip mailto: links when preserving URLs")

    def test_all_content_getters_have_consistent_structure(self):
        """Verify all three content getter methods produce consistent HTML structure."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        for method_name in ['_get_message_content', '_get_vps_message_content', '_get_mx_message_content']:
            idx = content.index(f'def {method_name}(self):')
            method_body = content[idx:idx + 1000]
            self.assertIn("<!DOCTYPE html>", method_body,
                          f"{method_name} must include DOCTYPE declaration")
            self.assertIn("<html>", method_body,
                          f"{method_name} must include <html> tag")
            self.assertIn("</html>", method_body,
                          f"{method_name} must include closing </html> tag")
            self.assertIn("</body>", method_body,
                          f"{method_name} must include closing </body> tag")

    def test_html_to_text_docstring_mentions_spam_filter(self):
        """Verify _html_to_text documents spam filter compatibility."""
        with open('paris_sender_complete1.py', 'r') as f:
            content = f.read()
        idx = content.index('def _html_to_text(self, html):')
        docstring_area = content[idx:idx + 400]
        self.assertIn('spam filter', docstring_area,
                      "_html_to_text docstring should mention spam filter compatibility")


class TestHTMLToTextConversion(unittest.TestCase):
    """Functional tests for HTML-to-text conversion with link preservation."""

    def _replace_link(self, m):
        """Helper matching the regex replacement logic from _html_to_text."""
        href, link_text = m.group(1), m.group(2)
        if href.startswith(('#', 'mailto:', 'javascript:')):
            return link_text
        if link_text.strip().lower() != href.strip().lower():
            return f"{link_text} ({href})"
        return href

    def test_regex_link_preservation(self):
        """Test that regex fallback correctly converts links to text with URLs."""
        html = '<a href="https://example.com">Click Here</a>'
        result = re.sub(
            r'<a\s[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            self._replace_link, html, flags=re.DOTALL | re.IGNORECASE
        )
        self.assertIn('Click Here', result)
        self.assertIn('https://example.com', result)
        self.assertIn('(https://example.com)', result)

    def test_regex_link_same_text_as_url(self):
        """Test that when link text equals the URL, only the URL is kept."""
        html = '<a href="https://example.com">https://example.com</a>'
        result = re.sub(
            r'<a\s[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            self._replace_link, html, flags=re.DOTALL | re.IGNORECASE
        )
        self.assertEqual(result.strip(), 'https://example.com')

    def test_regex_skips_mailto_links(self):
        """Test that mailto: links are not expanded with URL in parentheses."""
        html = '<a href="mailto:test@example.com">Contact Us</a>'
        result = re.sub(
            r'<a\s[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            self._replace_link, html, flags=re.DOTALL | re.IGNORECASE
        )
        self.assertEqual(result.strip(), 'Contact Us')
        self.assertNotIn('mailto:', result)

    def test_regex_skips_javascript_links(self):
        """Test that javascript: links are not expanded."""
        html = '<a href="javascript:void(0)">Click</a>'
        result = re.sub(
            r'<a\s[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            self._replace_link, html, flags=re.DOTALL | re.IGNORECASE
        )
        self.assertEqual(result.strip(), 'Click')
        self.assertNotIn('javascript:', result)

    def test_plain_text_wrapping_has_proper_structure(self):
        """Test that plain text content is wrapped with proper HTML structure."""
        plain = "Hello World"
        formatted_text = plain.replace("\n", "<br>")
        result = f"<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'></head><body><p>{formatted_text}</p></body></html>"
        self.assertIn('<!DOCTYPE html>', result)
        self.assertIn("<meta charset='utf-8'>", result)
        self.assertIn("<meta name='viewport'", result)
        self.assertIn('<body><p>Hello World</p></body>', result)

    def test_html_fragment_wrapping(self):
        """Test that HTML fragments are wrapped with proper structure."""
        fragment = "<p>Hello <b>World</b></p>"
        result = f"<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'></head><body>{fragment}</body></html>"
        self.assertIn('<!DOCTYPE html>', result)
        self.assertIn("<meta charset='utf-8'>", result)
        self.assertIn('<body><p>Hello <b>World</b></p></body>', result)


class TestIndustryEnhancements(unittest.TestCase):
    """Tests for industry-grade enhancements: logging, version, exception handling, SSL."""

    def setUp(self):
        with open('paris_sender_complete1.py', 'r') as f:
            self.content = f.read()

    def test_version_constant_exists(self):
        """Verify __version__ constant is defined at module level."""
        self.assertIn("__version__", self.content,
                      "Module should define __version__ for proper version tracking")

    def test_version_is_string(self):
        """Verify __version__ is a proper string assignment."""
        self.assertIn('__version__ = "', self.content,
                      "__version__ should be assigned a string value")

    def test_logging_module_imported(self):
        """Verify Python standard logging module is imported."""
        self.assertIn('import logging', self.content,
                      "Standard logging module should be imported for persistent file logging")

    def test_logger_configured(self):
        """Verify a module-level logger is configured."""
        self.assertIn('logging.getLogger(', self.content,
                      "A named logger should be created with logging.getLogger()")

    def test_logger_has_file_handler(self):
        """Verify the logger has a file handler for persistent logs."""
        self.assertIn('logging.FileHandler(', self.content,
                      "Logger should have a FileHandler for persistent log files")

    def test_logger_has_formatter(self):
        """Verify the logger has a proper log formatter."""
        self.assertIn('logging.Formatter(', self.content,
                      "Logger should use a Formatter for structured log output")

    def test_log_method_mirrors_to_logger(self):
        """Verify the log() method mirrors messages to the Python logging framework."""
        idx = self.content.index('def log(self, msg):')
        method_body = self.content[idx:idx + 2000]
        self.assertIn('logger.log(', method_body,
                      "log() method should mirror messages to the Python logger")

    def test_log_method_maps_severity_levels(self):
        """Verify the log() method maps emoji severity to Python log levels."""
        idx = self.content.index('def log(self, msg):')
        method_body = self.content[idx:idx + 2000]
        self.assertIn('logging.ERROR', method_body,
                      "log() should map error messages to logging.ERROR")
        self.assertIn('logging.WARNING', method_body,
                      "log() should map warning messages to logging.WARNING")

    def test_no_bare_except_clauses(self):
        """Verify there are no bare except: clauses (must specify exception type)."""
        lines = self.content.splitlines()
        bare_excepts = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == 'except:' or stripped.startswith('except:'):
                bare_excepts.append(i)
        self.assertEqual(len(bare_excepts), 0,
                         f"Found bare except: clauses at lines {bare_excepts}. "
                         f"All except blocks should specify an exception type (e.g., except Exception:)")

    def test_ssl_context_respects_allow_insecure_flag(self):
        """Verify universal_smtp_send SSL context respects allow_insecure_ssl parameter."""
        idx = self.content.index('def universal_smtp_send(')
        func_body = self.content[idx:idx + 2500]
        self.assertIn('allow_insecure_ssl', func_body,
                      "universal_smtp_send should have allow_insecure_ssl parameter")
        # The _build_ssl_context function should check allow_insecure_ssl before setting CERT_NONE
        build_idx = func_body.index('def _build_ssl_context')
        build_body = func_body[build_idx:build_idx + 300]
        self.assertIn('if allow_insecure_ssl', build_body,
                      "_build_ssl_context should check allow_insecure_ssl before disabling cert verification")

    def test_test_connection_respects_allow_insecure_ssl(self):
        """Verify test_connection uses allow_insecure_ssl flag for SSL context."""
        idx = self.content.index('def test_connection(self):')
        method_body = self.content[idx:idx + 1500]
        self.assertIn('allow_insecure_ssl', method_body,
                      "test_connection should check allow_insecure_ssl before disabling cert verification")


class TestEmailValidationAcceptsAllProviders(unittest.TestCase):
    """Tests that _is_valid_email accepts emails from all major providers (Gmail, Yahoo, AOL, etc.)
    and only rejects actual disposable/throwaway email services."""

    def setUp(self):
        with open('paris_sender_complete1.py', 'r') as f:
            self.content = f.read()

    def test_is_valid_email_does_not_reject_common_isp_domains(self):
        """Verify _is_valid_email does NOT check against common_isp_domains (Gmail, Yahoo, AOL, etc.)."""
        idx = self.content.index('def _is_valid_email(self, email):')
        method_body = self.content[idx:idx + 500]
        self.assertNotIn('common_isp_domains', method_body,
                         "_is_valid_email must NOT reject emails from common ISP domains like Gmail, Yahoo, AOL")

    def test_is_valid_email_checks_disposable_domains(self):
        """Verify _is_valid_email checks against disposable_domains for throwaway email services."""
        idx = self.content.index('def _is_valid_email(self, email):')
        method_body = self.content[idx:idx + 500]
        self.assertIn('disposable_domains', method_body,
                      "_is_valid_email should check disposable_domains to reject throwaway email services")

    def test_common_isp_domains_contains_major_providers(self):
        """Verify common_isp_domains set includes Gmail, Yahoo, AOL, Outlook, Hotmail."""
        self.assertIn('"gmail.com"', self.content)
        self.assertIn('"yahoo.com"', self.content)
        self.assertIn('"aol.com"', self.content)
        self.assertIn('"outlook.com"', self.content)
        self.assertIn('"hotmail.com"', self.content)

    def test_disposable_domains_contains_throwaway_services(self):
        """Verify disposable_domains set includes actual throwaway email services."""
        self.assertIn('"mailinator.com"', self.content)
        self.assertIn('"guerrillamail.com"', self.content)
        self.assertIn('"10minutemail.com"', self.content)

    def test_common_isp_domains_still_used_for_autograb(self):
        """Verify common_isp_domains is still used in personalization (autograb company name fallback)."""
        idx = self.content.index('def _personalize_content(')
        method_body = self.content[idx:idx + 3000]
        self.assertIn('common_isp_domains', method_body,
                      "common_isp_domains should still be used in _personalize_content for company autograb fallback")


if __name__ == '__main__':
    unittest.main()