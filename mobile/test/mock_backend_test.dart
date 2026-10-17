import 'package:flutter_test/flutter_test.dart';
import 'package:nascon_app/core/mock_backend.dart';

void main() {
  test('demo backend serves every app route without runtime type errors', () {
    final b = MockBackend();
    final login = b.handle('POST', '/api/v1/auth/login',
        {'email': 'organizer@nascon.test', 'password': 'Nascon@26'}, null);
    expect(login.$1, 200);
    final auth = 'Bearer ${(login.$2 as Map)['access_token']}';
    final mgrLogin = b.handle('POST', '/api/v1/auth/login',
        {'email': 'manager@nascon.test', 'password': 'Nascon@26'}, null);
    final mgr = 'Bearer ${(mgrLogin.$2 as Map)['access_token']}';

    for (final path in [
      '/health',
      '/api/v1/me',
      '/api/v1/leagues',
      '/api/v1/leagues/demo-league-ui/fixtures',
      '/api/v1/leagues/demo-league-ui/standings',
      '/api/v1/matches/demo-match-4',
      '/api/v1/sports/kabaddi',
      '/api/v1/clubs/club-alpha-1',
      '/api/v1/store/products',
    ]) {
      expect(b.handle('GET', path, null, auth).$1, 200, reason: path);
    }

    final score = b.handle('POST', '/api/v1/events', {
      'event_id': 't-e1',
      'match_id': 'demo-match-4',
      'type': 'score',
      'payload': {'team_id': 'club-alpha-1', 'event_type': 'all_out'},
    }, auth);
    expect(score.$1, 201);
    final comp = b.handle('POST', '/api/v1/events', {
      'event_id': 't-e2',
      'match_id': 'demo-match-4',
      'type': 'compensation',
      'payload': {'compensates': 't-e1', 'reason': 'test'},
    }, auth);
    expect(comp.$1, 201);
    expect(b.handle('POST', '/api/v1/events', {
      'event_id': 't-e3', 'match_id': 'demo-match-4', 'type': 'tiebreak_winner',
      'payload': {'team_id': 'club-alpha-2'},
    }, auth).$1, 201);

    final club = b.handle('GET', '/api/v1/clubs/club-alpha-1', null, mgr).$2 as Map;
    final player = (club['roster'] as List).last as Map;
    final transfer = b.handle('POST', '/api/v1/roster/actions', {
      'request_id': 't-r1',
      'league_id': 'demo-roster-league',
      'player_id': player['player_id'],
      'type': 'transfer',
      'from_squad_id': club['squad_id'],
      'to_squad_id': ((club['destination_squads'] as List).first as Map)['squad_id'],
      'effective_date': '2026-10-20',
      'loan_end_date': null,
      'reason': 'test',
      'requested_by': 'u-mgr',
    }, mgr);
    expect(transfer.$1, 201);
    expect(b.handle('GET', '/api/v1/players/${player['player_id']}/history', null, mgr).$1, 200);
    expect(b.handle('POST', '/api/v1/clubs/club-alpha-1/players',
        {'name': 'New Player', 'position': 'df', 'role': 'substitute'}, mgr).$1, 201);

    final order = b.handle('POST', '/api/v1/checkout', {
      'order_id': 't-o1',
      'customer_id': 'u-mgr',
      'items': [
        {'variant_id': 'demo-var-scarf-std', 'quantity': 2},
      ],
      'discount_code': 'WELCOME10',
      'payment': {'token': 'tok_success'},
    }, mgr);
    expect(order.$1, 201);
    expect(((order.$2 as Map)['receipt'] as Map)['pdf_base64'], isNotEmpty);
    expect(b.handle('POST', '/api/v1/checkout', {
      'order_id': 't-o2', 'customer_id': 'u', 'items': [
        {'variant_id': 'demo-var-scarf-std', 'quantity': 1},
      ],
      'discount_code': null, 'payment': {'token': 'tok_capture_fail'},
    }, mgr).$1, 402);

    final sync = b.handle('POST', '/api/v1/offline-sync', {
      'device_id': 'dev-t',
      'actions': [
        {
          'action_id': 'a-1',
          'type': 'score_event',
          'queued_at': '2026-10-17T11:00:00Z',
          'base_version': 1,
          'payload': {
            'event_id': 't-e9',
            'match_id': 'demo-match-4',
            'type': 'score',
            'payload': {'team_id': 'club-alpha-1', 'event_type': 'raid_point'},
          },
        },
      ],
    }, auth);
    expect(sync.$1, 200);
    expect((((sync.$2 as Map)['results'] as List).first as Map)['status'], 'applied');
    expect(b.handle('POST', '/api/v1/events',
        {'event_id': 't-e10', 'match_id': 'demo-match-4', 'type': 'match_end', 'payload': {}}, auth).$1,
        201);
    expect(b.handle('GET', '/api/v1/leagues/demo-league-ui/standings', null, auth).$1, 200);
  });
}
