const _messages = {
  'VALIDATION_ERROR': 'Some details are missing or invalid. Please check and try again.',
  'UNAUTHENTICATED': 'Your session expired. Please sign in again.',
  'FORBIDDEN': "Your account doesn't have permission to do this.",
  'OUT_OF_STOCK': 'Sorry, this item just sold out.',
  'PAYMENT_DECLINED': 'Your payment was declined. No money was taken.',
  'PAYMENT_CAPTURE_FAILED': "The payment couldn't be completed. No money was taken.",
  'INVALID_DISCOUNT_CODE': "That discount code isn't valid.",
  'MATCH_NOT_IN_PROGRESS': 'Scores can only be added while the match is live.',
  'ILLEGAL_TRANSITION': "The match can't change to that status right now.",
  'TIE_NOT_ALLOWED': "This sport doesn't allow draws. Record a tie-break winner first.",
  'INNINGS_COMPLETE': "This team's innings is already over.",
  'SERIES_ALREADY_DECIDED': 'The series is already decided.',
  'INVALID_COMPENSATION': "That event was already corrected or can't be corrected.",
  'DUPLICATE_EVENT_ID': 'This was already submitted.',
  'DUPLICATE_ORDER_ID': 'This was already submitted.',
  'CROSS_TENANT_TRANSFER': 'Players can only move between clubs in the same organisation.',
  'NOT_IN_SQUAD': 'This player is no longer in that squad.',
  'TRANSFER_WINDOW_CLOSED': 'The transfer window is closed for that date.',
  'PLAYER_ON_LOAN': "This player is on loan and can't be moved until they return.",
  'SQUAD_FULL': 'The destination squad is full.',
  'MIN_POSITION_VIOLATION': 'The club would have too few players in this position.',
  'INVALID_BASE_VERSION': 'This action was based on data that changed. Please refresh and try again.',
  'RATE_LIMITED': 'Too many requests. Retrying in a moment.',
  'NETWORK': "You're offline. Your action is saved and will sync automatically.",
};

const notFoundMessage = "We couldn't find that item. It may have been removed.";
const serverErrorMessage = 'Something went wrong on the server. Please try again.';
const offlineReadMessage =
    "You're offline and this page isn't saved on this phone yet. Connect to load it.";
const offlineNoQueueMessage =
    "You're offline. This needs a connection — please try again when you're back online.";

String friendlyMessage(String code, {int? status}) {
  final m = _messages[code];
  if (m != null) return m;
  if (code.endsWith('_NOT_FOUND') || status == 404) return notFoundMessage;
  if (status == 401) return _messages['UNAUTHENTICATED']!;
  if (status == 403) return _messages['FORBIDDEN']!;
  if (status == 429) return _messages['RATE_LIMITED']!;
  if (status == 400 || status == 422) return _messages['VALIDATION_ERROR']!;
  return serverErrorMessage;
}
