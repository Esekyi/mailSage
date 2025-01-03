class MockMailService:
    def send_email(self, recipient, subject, html_body):
        return True  # Always succeed in tests
