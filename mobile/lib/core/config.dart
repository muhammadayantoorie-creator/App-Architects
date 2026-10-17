const defaultServerUrl = 'http://10.0.2.2:8080';
const defaultLeagueId = 'demo-league-ui';
const demoProductId = 'demo-prod-scarf';
const appVersion = '1.0.0';

const demoPassword = 'Nascon@26';
const demoAccounts = [
  ('Admin', 'admin@nascon.test'),
  ('Organizer', 'organizer@nascon.test'),
  ('Manager', 'manager@nascon.test'),
  ('Player', 'player@nascon.test'),
  ('Viewer', 'viewer@nascon.test'),
];

/// Mock payment gateway tokens (token, label).
const paymentOptions = [
  ('tok_success', 'Card — success'),
  ('tok_declined', 'Card — declined'),
  ('tok_capture_failed', 'Card — capture fails'),
];
