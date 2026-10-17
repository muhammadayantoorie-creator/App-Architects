import '../core/api_client.dart';
import 'app_state.dart';

class Loaded {
  Loaded(this.data, {this.fromCache = false, this.fetchedAt});
  final dynamic data;
  final bool fromCache;
  final DateTime? fetchedAt;
}

/// Read-through cache: network when online, SQLite when offline or unreachable.
class Repository {
  Repository(this.s);
  final AppState s;

  Future<Loaded> load(String path, {Map<String, String>? query}) async {
    final key = query == null ? path : '$path?${Uri(queryParameters: query).query}';
    if (!s.online) {
      final c = await s.db.getCache(key);
      if (c != null) return Loaded(c.data, fromCache: true, fetchedAt: c.fetchedAt);
    }
    try {
      final d = await s.api.get(path, query: query);
      await s.db.putCache(key, d);
      return Loaded(d, fetchedAt: DateTime.now());
    } on ApiException catch (e) {
      if (e.isNetwork) {
        final c = await s.db.getCache(key);
        if (c != null) return Loaded(c.data, fromCache: true, fetchedAt: c.fetchedAt);
      }
      rethrow;
    }
  }

  Future<dynamic> cachedOnly(String path) async => (await s.db.getCache(path))?.data;

  Future<Loaded> leagues() => load('/api/v1/leagues');
  Future<Loaded> fixtures(String leagueId) => load('/api/v1/leagues/$leagueId/fixtures');
  Future<Loaded> standings(String leagueId) => load('/api/v1/leagues/$leagueId/standings');
  Future<Loaded> match(String matchId) => load('/api/v1/matches/$matchId');
  Future<Loaded> sport(String sportId) => load('/api/v1/sports/$sportId');
  Future<Loaded> club(String clubId) => load('/api/v1/clubs/$clubId');
  Future<Loaded> playerHistory(String playerId) => load('/api/v1/players/$playerId/history');
  Future<Loaded> products() => load('/api/v1/store/products');

  /// Warm the sport config so scoring buttons work offline.
  Future<void> prefetchSport(String? sportId) async {
    if (sportId == null || !s.online) return;
    if (await s.db.getCache('/api/v1/sports/$sportId') != null) return;
    try {
      await sport(sportId);
    } catch (_) {}
  }
}

List<Map<String, dynamic>> asList(dynamic v) =>
    v is List ? v.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList() : [];

Map<String, dynamic> asMap(dynamic v) => v is Map ? Map<String, dynamic>.from(v) : {};
