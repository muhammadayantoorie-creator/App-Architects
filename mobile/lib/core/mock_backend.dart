import 'dart:convert';

import 'package:dio/dio.dart';

/// Built-in demo backend (Settings → "Use demo data"). Mirrors the real API shapes so the
/// app can be exercised without a server. Respects device connectivity so offline flows
/// (cache, outbox, sync) behave exactly as with the real backend.
class MockInterceptor extends Interceptor {
  bool enabled = false;
  bool Function() hasNetwork = () => true;
  // Built on first demo-mode request only, so normal startup never touches demo data.
  late final _b = MockBackend();

  @override
  Future<void> onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    final o = options, h = handler;
    if (!enabled) return h.next(o);
    await Future<void>.delayed(const Duration(milliseconds: 250));
    if (!hasNetwork()) {
      return h.reject(DioException(
          requestOptions: o, type: DioExceptionType.connectionError, error: 'offline (demo)'));
    }
    final body = o.data is String ? jsonDecode(o.data as String) : o.data;
    final (status, data) =
        _b.handle(o.method, o.uri.path, body, o.headers['Authorization'] as String?);
    final res = Response<dynamic>(requestOptions: o, statusCode: status, data: data);
    if (status >= 400) {
      return h.reject(
          DioException(requestOptions: o, response: res, type: DioExceptionType.badResponse));
    }
    h.resolve(res);
  }
}

typedef MockResult = (int, dynamic);

MockResult _err(int status, String code, [String message = '']) => (
      status,
      {
        'error': {'code': code, 'message': message, 'details': {}}
      }
    );

class MockBackend {
  MockBackend() {
    _seed();
  }

  static const _tenant = {
    'tenant_id': 'tenant-alpha',
    'name': 'Alpha Sports',
    'logo_url': null,
    'primary_color': '#1565C0',
    'secondary_color': '#FFB300',
  };

  static const _users = {
    'admin@nascon.test': ('u-admin', 'super_admin', null),
    'organizer@nascon.test': ('u-org', 'league_organizer', null),
    'manager@nascon.test': ('u-mgr', 'club_manager', 'club-alpha-1'),
    'player@nascon.test': ('u-player', 'player', 'club-alpha-1'),
    'viewer@nascon.test': ('u-viewer', 'viewer', null),
  };

  final _teams = {
    'club-alpha-1': 'Alpha FC',
    'club-alpha-2': 'Alpha Rovers',
    'club-alpha-3': 'Alpha United',
    'club-alpha-4': 'Alpha City',
  };
  final _matches = <String, Map<String, dynamic>>{};
  final _roster = <String, List<Map<String, dynamic>>>{};
  final _history = <String, List<Map<String, dynamic>>>{};
  final _seenIds = <String>{};
  final _orders = <String, Map<String, dynamic>>{};
  late final List<Map<String, dynamic>> _products;

  void _seed() {
    final now = DateTime.now().toUtc();
    final day = DateTime.utc(now.year, now.month, now.day);
    void match(String id, String h, String a, DateTime at, String status, int hs, int as) {
      _matches[id] = {
        'match_id': id,
        'league_id': 'demo-league-ui',
        'sport_id': _sportId,
        'scheduled_at': at.toIso8601String(),
        'status': status,
        'outcome': status == 'completed' ? (hs > as ? 'home_win' : hs < as ? 'away_win' : 'draw') : 'pending',
        'version': 1,
        'venue': {'name': h == 'club-alpha-1' ? 'Alpha Arena' : '${_teams[h]} Ground'},
        'home': {'team_id': h, 'name': _teams[h], 'score': hs, 'wickets': null, 'overs': null, 'fair_play': 0},
        'away': {'team_id': a, 'name': _teams[a], 'score': as, 'wickets': null, 'overs': null, 'fair_play': 0},
        'events': <dynamic>[
          {'sequence': 1, 'event_id': 'e-$id-1', 'type': 'match_init', 'payload': {}, 'compensated': false, 'compensated_by': null},
        ],
        'pinned_product': null,
      };
    }

    match('demo-match-1', 'club-alpha-1', 'club-alpha-3', day.subtract(const Duration(days: 6, hours: -15)), 'completed', 3, 1);
    match('demo-match-2', 'club-alpha-2', 'club-alpha-4', day.subtract(const Duration(days: 6, hours: -17)), 'completed', 1, 1);
    match('demo-match-3', 'club-alpha-3', 'club-alpha-2', day.subtract(const Duration(days: 2, hours: -16)), 'completed', 0, 2);
    match('demo-match-4', 'club-alpha-1', 'club-alpha-2', now.subtract(const Duration(minutes: 35)), 'in_progress', 1, 0);
    match('demo-match-5', 'club-alpha-4', 'club-alpha-3', day.add(const Duration(hours: 19)), 'upcoming', 0, 0);
    match('demo-match-6', 'club-alpha-2', 'club-alpha-1', day.add(const Duration(days: 3, hours: 16)), 'upcoming', 0, 0);
    final live = _matches['demo-match-4']!;
    (live['events'] as List).addAll([
      {'sequence': 2, 'event_id': 'e-4-2', 'type': 'match_start', 'payload': {}, 'compensated': false, 'compensated_by': null},
      {'sequence': 3, 'event_id': 'e-4-3', 'type': 'score', 'payload': {'team_id': 'club-alpha-1', 'event_type': 'raid_point'}, 'compensated': false, 'compensated_by': null},
    ]);
    live['version'] = 3;
    live['pinned_product'] = {'product_id': 'demo-prod-scarf', 'name': 'Alpha Scarf', 'price_minor': 150000, 'currency': 'PKR'};

    final names = {
      'club-alpha-1': ['Ali Raza', 'Hamza Khan', 'Bilal Ahmed', 'Usman Tariq', 'Saad Malik', 'Zain Abbas'],
      'club-alpha-2': ['Omar Farooq', 'Fahad Iqbal', 'Daniyal Shah', 'Imran Qureshi', 'Talha Butt'],
      'club-alpha-3': ['Kamran Akmal', 'Asad Ali', 'Haris Sohail', 'Junaid Khan'],
      'club-alpha-4': ['Waqar Younis', 'Shoaib Akhtar', 'Yasir Shah', 'Babar Hayat'],
    };
    const positions = ['gk', 'df', 'df', 'mf', 'mf', 'fw'];
    names.forEach((club, list) {
      _roster[club] = [
        for (var i = 0; i < list.length; i++)
          {
            'player_id': 'p-$club-$i',
            'name': list[i],
            'position': positions[i % positions.length],
            'role': i == 0 ? 'captain' : 'player',
            'squad_id': _squad(club),
            'league_id': 'demo-roster-league',
            'audit_count': 0,
            'on_loan': false,
          }
      ];
    });

    _products = [
      {
        'product_id': 'prod-jersey-001',
        'name': 'Alpha Home Jersey',
        'category': 'apparel',
        'description': 'Official 2026 home jersey. Breathable fabric.',
        'variants': [
          {'variant_id': 'var-jersey-001-M', 'label': 'M', 'price_minor': 450000, 'currency': 'PKR', 'stock': 1},
          {'variant_id': 'var-jersey-001-L', 'label': 'L', 'price_minor': 450000, 'currency': 'PKR', 'stock': 5},
        ],
      },
      {
        'product_id': 'demo-prod-scarf',
        'name': 'Alpha Scarf',
        'category': 'accessories',
        'description': 'Knitted supporters scarf in club colours.',
        'variants': [
          {'variant_id': 'demo-var-scarf-std', 'label': 'Standard', 'price_minor': 150000, 'currency': 'PKR', 'stock': 100},
        ],
      },
      {
        'product_id': 'demo-prod-cap',
        'name': 'Alpha Cap',
        'category': 'accessories',
        'description': 'Adjustable cap with embroidered crest.',
        'variants': [
          {'variant_id': 'demo-var-cap', 'label': 'One size', 'price_minor': 120000, 'currency': 'PKR', 'stock': 0},
        ],
      },
    ];
  }

  String _squad(String club) => 'demo-sq-${club.replaceFirst('club-', '')}';
  String? _clubOfSquad(String? squad) {
    for (final c in _teams.keys) {
      if (_squad(c) == squad) return c;
    }
    return null;
  }

  MockResult handle(String method, String path, dynamic body, String? auth) {
    final b = body is Map ? Map<String, dynamic>.from(body) : <String, dynamic>{};
    if (path == '/health') return (200, {'status': 'ok', 'mode': 'demo'});
    if (method == 'POST' && path == '/api/v1/auth/login') return _login(b);
    final user = _userFor(auth);
    if (user == null) return _err(401, 'UNAUTHENTICATED');
    final seg = path.split('/').where((s) => s.isNotEmpty).toList(); // api v1 ...
    final p = seg.length > 2 ? seg.sublist(2) : <String>[];
    if (method == 'GET') {
      switch (p) {
        case ['me']:
          return (200, {..._meJson(user), 'tenant': _tenant});
        case ['leagues']:
          return (200, {
            'items': [
              {'league_id': 'demo-league-ui', 'name': 'Alpha Premier League', 'sport_id': _sportId, 'tenant_id': 'tenant-alpha'},
            ]
          });
        case ['leagues', _, 'fixtures']:
          return (200, {'league_id': p[1], 'fixtures': [for (final m in _matches.values) _fixture(m)]});
        case ['leagues', _, 'standings']:
          return (200, _standings(p[1]));
        case ['matches', final id]:
          final m = _matches[id];
          return m == null ? _err(404, 'MATCH_NOT_FOUND') : (200, m);
        case ['sports', final id]:
          return (200, {
            'sport_id': id,
            'name': 'Kabaddi',
            'scoring_model': 'event',
            'draw_allowed': _drawAllowed,
            'scoring_events': {
              for (final e in _sportEvents.entries) e.key: {'points': e.value},
            },
          });
        case ['clubs', final id]:
          return _teams.containsKey(id) ? (200, _club(id)) : _err(404, 'CLUB_NOT_FOUND');
        case ['players', final id, 'history']:
          String? squad;
          _roster.forEach((club, list) {
            final p = list.where((x) => x['player_id'] == id).firstOrNull;
            if (p != null) squad = '${p['squad_id']}';
          });
          return (200, {
            'player_id': id,
            'league_id': 'demo-roster-league',
            'current_squad_id': squad,
            'parent_squad_id': null,
            'history': _history[id] ?? [],
          });
        case ['store', 'products']:
          return (200, {'items': _products});
      }
    }
    if (method == 'POST') {
      switch (p) {
        case ['events']:
          return _event(b);
        case ['roster', 'actions']:
          return _rosterAction(b, user.$1);
        case ['clubs', final id, 'players']:
          final list = _roster[id];
          if (list == null) return _err(404, 'CLUB_NOT_FOUND');
          if ('${b['name'] ?? ''}'.trim().isEmpty || '${b['position'] ?? ''}'.trim().isEmpty) {
            return _err(400, 'VALIDATION_ERROR');
          }
          if (list.length >= 25) return _err(409, 'SQUAD_FULL');
          final player = <String, dynamic>{
            'player_id': 'p-$id-${DateTime.now().millisecondsSinceEpoch % 1000000}',
            'name': '${b['name']}'.trim(),
            'position': '${b['position']}'.trim(),
            'role': b['role'] ?? 'substitute',
            'squad_id': _squad(id),
            'league_id': 'demo-roster-league',
            'audit_count': 1,
            'on_loan': false,
          };
          list.add(player);
          _history['${player['player_id']}'] = [
            _audit('add', '${player['player_id']}', null, _squad(id), _today(), 'New registration', user.$1),
          ];
          return (201, player);
        case ['checkout']:
          return _checkout(b);
        case ['offline-sync']:
          return _sync(b, user.$1);
        case ['matches', final id, 'pinned-product']:
          final m = _matches[id];
          if (m == null) return _err(404, 'MATCH_NOT_FOUND');
          final prod = _products.where((x) => x['product_id'] == b['product_id']).firstOrNull;
          if (prod == null) return _err(404, 'PRODUCT_NOT_FOUND');
          final v = (prod['variants'] as List).first as Map;
          m['pinned_product'] = {'product_id': prod['product_id'], 'name': prod['name'], 'price_minor': v['price_minor'], 'currency': v['currency']};
          return (200, {'match_id': id, 'product_id': prod['product_id']});
      }
    }
    return _err(404, 'NOT_FOUND');
  }

  // ------------------------------------------------------------------ auth

  /// Mock tokens encode the email, so a stored token still works after an app restart.
  (String, String, String?, String)? _userFor(String? auth) {
    final t = auth?.replaceFirst('Bearer ', '');
    if (t == null || !t.startsWith('mock.')) return null;
    final email = utf8.decode(base64Url.decode(t.substring(5)));
    final u = _users[email];
    return u == null ? null : (u.$1, u.$2, u.$3, email);
  }

  MockResult _login(Map<String, dynamic> b) {
    final email = '${b['email'] ?? ''}'.toLowerCase();
    final u = _users[email];
    if (u == null || b['password'] != 'Nascon@26') {
      return _err(401, 'UNAUTHENTICATED', 'Invalid credentials');
    }
    return (200, {
      'access_token': 'mock.${base64Url.encode(utf8.encode(email))}',
      'token_type': 'bearer',
      'expires_in': 3600,
      'user': _meJson((u.$1, u.$2, u.$3, email)),
    });
  }

  Map<String, dynamic> _meJson((String, String, String?, String) u) => {
        'user_id': u.$1,
        'email': u.$4,
        'role': u.$2,
        'tenant_id': 'tenant-alpha',
        'club_id': u.$3,
        'player_id': u.$2 == 'player' ? 'p-club-alpha-1-1' : null,
        'league_ids': ['demo-league-ui'],
      };

  // --------------------------------------------------------------- matches

  Map<String, dynamic> _fixture(Map<String, dynamic> m) => {
        'match_id': m['match_id'],
        'home_team_id': m['home']['team_id'],
        'home_name': m['home']['name'],
        'away_team_id': m['away']['team_id'],
        'away_name': m['away']['name'],
        'scheduled_at': m['scheduled_at'],
        'status': m['status'],
        'home_score': m['home']['score'],
        'away_score': m['away']['score'],
        'version': m['version'],
      };

  Map<String, dynamic> _standings(String leagueId) {
    final rows = {
      for (final t in _teams.keys)
        t: <String, dynamic>{'team_id': t, 'played': 0, 'won': 0, 'drawn': 0, 'lost': 0, 'scored': 0, 'conceded': 0, 'points': 0, 'fair_play': 0}
    };
    for (final m in _matches.values.where((m) => m['status'] == 'completed')) {
      final h = rows[m['home']['team_id']]!;
      final a = rows[m['away']['team_id']]!;
      final hs = m['home']['score'] as int, as = m['away']['score'] as int;
      void rec(Map<String, dynamic> r, int f, int ag) {
        r['played'] = (r['played'] as int) + 1;
        r['scored'] = (r['scored'] as int) + f;
        r['conceded'] = (r['conceded'] as int) + ag;
        final k = f > ag ? 'won' : f < ag ? 'lost' : 'drawn';
        r[k] = (r[k] as int) + 1;
        r['points'] = (r['points'] as int) + (f > ag ? 3 : f == ag ? 1 : 0);
      }

      rec(h, hs, as);
      rec(a, as, hs);
    }
    final table = rows.values.toList()
      ..forEach((r) => r['diff'] = (r['scored'] as int) - (r['conceded'] as int))
      ..sort((x, y) {
        final c = (y['points'] as int).compareTo(x['points'] as int);
        return c != 0 ? c : (y['diff'] as int).compareTo(x['diff'] as int);
      });
    for (var i = 0; i < table.length; i++) {
      table[i]['rank'] = i + 1;
      table[i]['status'] = i == 0 ? 'clinched' : i == table.length - 1 ? 'eliminated' : 'still_possible';
      table[i]['resolved_by'] = null;
    }
    return {
      'league_id': leagueId,
      'sport_id': _sportId,
      'qualification_spots': 2,
      'team_names': _teams,
      'table': table,
      'h2h': {},
    };
  }

  // Demo sport = the spec's "mystery sport" example, so nothing here assumes a real sport.
  static const _sportId = 'kabaddi';
  static const _sportEvents = {'raid_point': 1, 'tackle_point': 1, 'all_out': 2};
  static const _drawAllowed = false;

  static String? _side(Map<String, dynamic> m, dynamic teamId) => m['home']['team_id'] == teamId
      ? 'home'
      : m['away']['team_id'] == teamId
          ? 'away'
          : null;

  MockResult _event(Map<String, dynamic> b) {
    final m = _matches[b['match_id']];
    if (m == null) return _err(404, 'MATCH_NOT_FOUND');
    if (_seenIds.contains(b['event_id'])) return _err(409, 'DUPLICATE_EVENT_ID');
    final type = b['type'];
    final payload = b['payload'] is Map ? Map<String, dynamic>.from(b['payload'] as Map) : <String, dynamic>{};
    switch (type) {
      case 'match_start':
        if (m['status'] != 'upcoming') return _err(409, 'ILLEGAL_TRANSITION');
        m['status'] = 'in_progress';
      case 'match_end':
        if (m['status'] != 'in_progress') return _err(409, 'ILLEGAL_TRANSITION');
        if (!_drawAllowed && m['home']['score'] == m['away']['score'] && m['tiebreak'] == null) {
          return _err(409, 'TIE_NOT_ALLOWED');
        }
        m['status'] = 'completed';
      case 'score':
        if (m['status'] != 'in_progress') return _err(409, 'MATCH_NOT_IN_PROGRESS');
        final side = _side(m, payload['team_id']);
        if (side == null) return _err(400, 'VALIDATION_ERROR');
        final points = _sportEvents[payload['event_type']];
        if (points == null) return _err(400, 'UNKNOWN_EVENT_TYPE');
        m[side]['score'] = (m[side]['score'] as int) + points;
      case 'tiebreak_winner':
        if (m['status'] != 'in_progress') return _err(409, 'MATCH_NOT_IN_PROGRESS');
        if (_side(m, payload['team_id']) == null) return _err(400, 'VALIDATION_ERROR');
        m['tiebreak'] = payload['team_id'];
      case 'compensation':
        final target = (m['events'] as List).cast<Map<String, dynamic>>().where((e) => e['event_id'] == payload['compensates']).firstOrNull;
        if (target == null) return _err(404, 'EVENT_NOT_FOUND');
        if (target['compensated'] == true || !const ['score', 'tiebreak_winner'].contains(target['type'])) {
          return _err(409, 'INVALID_COMPENSATION');
        }
        target['compensated'] = true;
        target['compensated_by'] = b['event_id'];
        final tp = target['payload'] as Map;
        if (target['type'] == 'tiebreak_winner') {
          m['tiebreak'] = null;
        } else {
          final side = _side(m, tp['team_id'])!;
          m[side]['score'] = (m[side]['score'] as int) - (_sportEvents[tp['event_type']] ?? 0);
        }
      default:
        return _err(400, 'VALIDATION_ERROR');
    }
    _seenIds.add('${b['event_id']}');
    final events = m['events'] as List;
    final seq = events.length + 1;
    events.add({'sequence': seq, 'event_id': b['event_id'], 'type': type, 'payload': payload, 'compensated': false, 'compensated_by': null});
    m['version'] = (m['version'] as int) + 1;
    return (201, {
      'event_id': b['event_id'],
      'match_id': m['match_id'],
      'type': type,
      'sequence': seq,
      'match_version': m['version'],
      'signature': 'demo-signature',
    });
  }

  // ---------------------------------------------------------------- clubs

  Map<String, dynamic> _club(String id) => {
        'club_id': id,
        'tenant_id': 'tenant-alpha',
        'name': _teams[id],
        'logo_url': null,
        'home_venue': {'name': id == 'club-alpha-1' ? 'Alpha Arena' : '${_teams[id]} Ground', 'latitude': 33.68, 'longitude': 73.04},
        'social': {'x': '@${_teams[id]!.toLowerCase().replaceAll(' ', '')}'},
        'staff': [
          {'name': 'Coach Ali', 'role': 'coach'},
          {'name': 'Dr. Sana', 'role': 'physio'},
        ],
        'roster_league_id': 'demo-roster-league',
        'squad_id': _squad(id),
        'roster': _roster[id] ?? [],
        'destination_squads': [
          for (final t in _teams.keys)
            if (t != id) {'squad_id': _squad(t), 'club_id': t, 'name': _teams[t]},
        ],
      };

  MockResult _rosterAction(Map<String, dynamic> b, String userId) {
    if (_seenIds.contains(b['request_id'])) return _err(409, 'DUPLICATE_EVENT_ID');
    final from = _clubOfSquad(b['from_squad_id'] as String?);
    final list = from == null ? null : _roster[from];
    final player = list?.where((p) => p['player_id'] == b['player_id']).firstOrNull;
    if (player == null) return _err(409, 'NOT_IN_SQUAD');
    if (player['on_loan'] == true) return _err(409, 'PLAYER_ON_LOAN');
    final type = b['type'];
    final to = _clubOfSquad(b['to_squad_id'] as String?);
    if (type != 'release' && to == null) return _err(400, 'VALIDATION_ERROR');
    if (type == 'loan' && '${b['loan_end_date']}'.compareTo('${b['effective_date']}') <= 0) {
      return _err(400, 'VALIDATION_ERROR');
    }
    _seenIds.add('${b['request_id']}');
    list!.remove(player);
    if (to != null) {
      _roster[to]!.add({
        ...player,
        'squad_id': _squad(to),
        'on_loan': type == 'loan',
        'audit_count': (player['audit_count'] as int) + 1,
      });
    }
    final live = _matches.values
        .where((m) =>
            m['status'] == 'in_progress' &&
            (m['home']['team_id'] == from || m['away']['team_id'] == from))
        .firstOrNull;
    final state = live != null ? 'deferred_until_match_end' : 'active';
    final entry = _audit('$type', '${player['player_id']}', b['from_squad_id'] as String?,
        b['to_squad_id'] as String?, '${b['effective_date']}', '${b['reason'] ?? ''}', userId,
        state: state);
    (_history['${player['player_id']}'] ??= []).add(entry);
    return (201, {
      'request_id': b['request_id'],
      'status': 'accepted',
      'state': state,
      'blocking_match_id': live?['match_id'],
      'registration': type == 'release'
          ? null
          : {
              'player_id': player['player_id'],
              'league_id': b['league_id'],
              'squad_id': b['to_squad_id'],
              'parent_squad_id': type == 'loan' ? b['from_squad_id'] : null,
              'registration_type': type,
              'start_date': b['effective_date'],
              'loan_end_date': b['loan_end_date'],
              'role': 'substitute',
            },
      'audit_entry': entry,
    });
  }

  int _auditSeq = 0;
  static String _today() => DateTime.now().toUtc().toIso8601String().substring(0, 10);

  Map<String, dynamic> _audit(String action, String playerId, String? from, String? to,
          String effective, String why, String who, {String state = 'active'}) =>
      {
        'audit_id': 'au-${(++_auditSeq).toString().padLeft(4, '0')}',
        'action': action,
        'player_id': playerId,
        'league_id': 'demo-roster-league',
        'from_squad_id': from,
        'to_squad_id': to,
        'effective_date': effective,
        'state': state,
        'who': who,
        'when': '${DateTime.now().toUtc().toIso8601String().substring(0, 19)}Z',
        'why': why,
      };

  // ---------------------------------------------------------------- store

  MockResult _checkout(Map<String, dynamic> b) {
    final orderId = '${b['order_id']}';
    if (_orders.containsKey(orderId)) return (201, _orders[orderId]);
    final token = (b['payment'] as Map?)?['token'];
    final code = b['discount_code'] as String?;
    final items = <Map<String, dynamic>>[];
    final pdfLines = <String>[];
    var subtotal = 0;
    for (final i in (b['items'] as List? ?? []).cast<Map>()) {
      Map<String, dynamic>? variant;
      Map<String, dynamic>? product;
      for (final p in _products) {
        for (final v in (p['variants'] as List).cast<Map<String, dynamic>>()) {
          if (v['variant_id'] == i['variant_id']) {
            variant = v;
            product = p;
          }
        }
      }
      if (variant == null) return _err(404, 'VARIANT_NOT_FOUND');
      final qty = (i['quantity'] as num).toInt();
      if ((variant['stock'] as int) < qty) return _err(409, 'OUT_OF_STOCK');
      final line = (variant['price_minor'] as int) * qty;
      subtotal += line;
      items.add({
        'variant_id': variant['variant_id'],
        'quantity': qty,
        'unit_price_minor': variant['price_minor'],
      });
      pdfLines.add('$qty x ${product!['name']} (${variant['label']})  PKR ${(line / 100).toStringAsFixed(2)}');
    }
    if (code != null && code != 'WELCOME10') return _err(400, 'INVALID_DISCOUNT_CODE');
    if (token == 'tok_declined') return _err(402, 'PAYMENT_DECLINED');
    if (token == 'tok_capture_fail') return _err(402, 'PAYMENT_CAPTURE_FAILED');
    for (final i in items) {
      for (final p in _products) {
        for (final v in (p['variants'] as List).cast<Map<String, dynamic>>()) {
          if (v['variant_id'] == i['variant_id']) v['stock'] = (v['stock'] as int) - (i['quantity'] as int);
        }
      }
    }
    final discount = code == null ? 0 : subtotal * 10 ~/ 100;
    final total = subtotal - discount;
    final order = {
      'order_id': orderId,
      'status': 'paid',
      'currency': 'PKR',
      'items': items,
      'subtotal_minor': subtotal,
      'discount_minor': discount,
      'total_minor': total,
      'payment': {'authorization_id': 'auth_${_orders.length + 1}', 'capture_id': 'cap_${_orders.length + 1}', 'state': 'captured'},
      'receipt': {
        'payload': {
          'order_id': orderId,
          'customer_id': b['customer_id'],
          'items': items,
          'subtotal_minor': subtotal,
          'discount_minor': discount,
          'total_minor': total,
          'currency': 'PKR',
          'paid_at': '${DateTime.now().toUtc().toIso8601String().substring(0, 19)}Z',
        },
        'signature': 'demo-signature',
        'pdf_base64': base64Encode(_pdf(orderId, pdfLines, subtotal, discount, total)),
      },
    };
    _orders[orderId] = order;
    return (201, order);
  }

  List<int> _pdf(String orderId, List<String> itemLines, int sub, int disc, int total) {
    String money(int m) => 'PKR ${(m / 100).toStringAsFixed(2)}';
    final lines = [
      'Alpha Sports Store - Receipt',
      'Order: $orderId',
      '',
      ...itemLines,
      '',
      'Subtotal: ${money(sub)}',
      'Discount: ${money(disc)}',
      'Total paid: ${money(total)}',
      '',
      'Demo receipt generated by the app (no server).',
    ];
    final text = StringBuffer('BT /F1 14 Tf 50 780 Td 18 TL\n');
    for (final l in lines) {
      text.write('(${l.replaceAll('\\', '\\\\').replaceAll('(', '\\(').replaceAll(')', '\\)')}) Tj T*\n');
    }
    text.write('ET');
    final content = text.toString();
    final objs = [
      '<< /Type /Catalog /Pages 2 0 R >>',
      '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
      '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
      '<< /Length ${content.length} >>\nstream\n$content\nendstream',
      '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ];
    final out = StringBuffer('%PDF-1.4\n');
    final offsets = <int>[];
    for (var i = 0; i < objs.length; i++) {
      offsets.add(out.length);
      out.write('${i + 1} 0 obj\n${objs[i]}\nendobj\n');
    }
    final xref = out.length;
    out.write('xref\n0 ${objs.length + 1}\n0000000000 65535 f \n');
    for (final o in offsets) {
      out.write('${o.toString().padLeft(10, '0')} 00000 n \n');
    }
    out.write('trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n$xref\n%%EOF\n');
    return latin1.encode(out.toString());
  }

  // ---------------------------------------------------------------- sync

  MockResult _sync(Map<String, dynamic> b, String userId) {
    final results = <Map<String, dynamic>>[];
    var applied = 0, rejected = 0, duplicate = 0, order = 0;
    for (final a in (b['actions'] as List? ?? []).cast<Map>()) {
      order++;
      final payload = Map<String, dynamic>.from(a['payload'] as Map);
      final isScore = a['type'] == 'score_event';
      final id = '${isScore ? payload['event_id'] : payload['request_id']}';
      if (_seenIds.contains(id)) {
        duplicate++;
        results.add({'action_id': a['action_id'], 'status': 'duplicate', 'resolution': 'skipped_duplicate', 'error_code': null, 'processed_order': order, 'server_version': null, 'signature': null});
        continue;
      }
      final baseVersion = (a['base_version'] as num?)?.toInt();
      final before = isScore ? (_matches[payload['match_id']]?['version'] as int?) : null;
      final (status, res) = isScore ? _event(payload) : _rosterAction(payload, userId);
      if (status < 300) {
        applied++;
        results.add({
          'action_id': a['action_id'],
          'status': 'applied',
          'resolution': isScore && before != null && baseVersion != null && baseVersion < before ? 'rebased_append' : 'appended',
          'error_code': null,
          'processed_order': order,
          'server_version': isScore ? (res as Map)['match_version'] : null,
          'signature': 'demo-signature',
        });
      } else {
        rejected++;
        results.add({
          'action_id': a['action_id'],
          'status': 'rejected',
          'resolution': 'server_wins',
          'error_code': ((res as Map)['error'] as Map)['code'],
          'processed_order': order,
          'server_version': null,
          'signature': null,
        });
      }
    }
    return (200, {
      'device_id': b['device_id'],
      'results': results,
      'summary': {'applied': applied, 'rejected': rejected, 'duplicate': duplicate},
    });
  }
}
