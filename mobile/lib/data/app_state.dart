import 'dart:async';
import 'dart:convert';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../core/api_client.dart';
import '../core/config.dart';
import '../core/db.dart';
import '../core/error_messages.dart';
import '../core/formatters.dart';
import '../core/nav.dart';
import '../core/secure_store.dart';
import '../ui/screens/outbox.dart';
import 'live/sse_client.dart';
import 'repository.dart';
import 'sync/outbox.dart';

const _uuid = Uuid();
String newId() => _uuid.v4();

class Submitted {
  const Submitted({required this.queued, this.response});
  final bool queued;
  final dynamic response;
}

class AppState extends ChangeNotifier {
  final db = AppDb();
  final api = ApiClient();
  final secure = SecureStore();
  late final repo = Repository(this);
  late final live = LiveService(this);

  Map<String, dynamic>? me;
  String deviceId = '';
  String leagueId = defaultLeagueId;
  List<Map<String, dynamic>> leagues = [];
  bool online = true;
  bool syncing = false;
  int pending = 0;
  int epoch = 0;
  String? sessionMessage;

  bool _hasNetwork = true;
  Timer? _probeTimer;

  bool get loggedIn => me != null;
  String get role => me?['role'] as String? ?? 'viewer';
  String get userId => me?['user_id'] as String? ?? '';
  String? get clubId => me?['club_id'] as String?;
  String? get playerId => me?['player_id'] as String?;
  bool get isAdmin => role == 'super_admin';
  bool get canScore => isAdmin || role == 'league_organizer';
  bool get canBuy => role != 'viewer';
  bool canManageClub(String clubId) => isAdmin || (role == 'club_manager' && this.clubId == clubId);

  Map<String, dynamic> get tenant => me?['tenant'] is Map ? Map<String, dynamic>.from(me!['tenant'] as Map) : {};
  String get tenantName => tenant['name'] as String? ?? 'NaSCon League';
  Color get seed => parseHex(tenant['primary_color']) ?? const Color(0xFF1565C0);

  String? sportIdFor(String leagueId) {
    for (final l in leagues) {
      if (l['league_id'] == leagueId) return l['sport_id'] as String?;
    }
    return null;
  }

  // ---------------------------------------------------------------- startup

  Future<void> init() async {
    await db.open();
    api.baseUrl = await db.getSetting('server_url') ?? defaultServerUrl;
    deviceId = await db.getSetting('device_id') ?? '';
    if (deviceId.isEmpty) {
      deviceId = 'dev-${newId()}';
      await db.setSetting('device_id', deviceId);
    }
    leagueId = await db.getSetting('league_id') ?? defaultLeagueId;
    api.onUnauthorized = () => logout(message: friendlyMessage('UNAUTHENTICATED'));
    api.onReachability = _onReachability;
    pending = await db.pendingCount();

    final token = await secure.readToken();
    if (token != null) {
      api.token = token;
      final cachedMe = await db.getSetting('me');
      if (cachedMe != null) {
        me = Map<String, dynamic>.from(jsonDecode(cachedMe) as Map);
        unawaited(refreshMe());
      } else {
        await refreshMe();
      }
    }

    final conn = Connectivity();
    conn.onConnectivityChanged.listen(_onConnectivity);
    _onConnectivity(await conn.checkConnectivity());
  }

  Future<void> setServerUrl(String url) async {
    api.baseUrl = url.trim();
    await db.setSetting('server_url', api.baseUrl);
    notifyListeners();
    unawaited(_probe());
  }

  Future<void> setLeague(String id) async {
    if (id == leagueId) return;
    leagueId = id;
    live.switchLeague(id);
    await db.setSetting('league_id', id);
    notifyListeners();
  }

  // ------------------------------------------------------------------- auth

  Future<void> login(String email, String password) async {
    final res = await api.post('/api/v1/auth/login', {'email': email.trim(), 'password': password},
        auth: false);
    final token = res['access_token'] as String;
    await secure.writeToken(token);
    api.token = token;
    sessionMessage = null;
    me = Map<String, dynamic>.from(res['user'] as Map);
    await db.setSetting('me', jsonEncode(me));
    await refreshMe();
    epoch++;
    notifyListeners();
  }

  Future<void> refreshMe() async {
    try {
      final res = await api.get('/api/v1/me');
      if (res is Map && api.token != null) {
        me = {...?me, ...Map<String, dynamic>.from(res)};
        await db.setSetting('me', jsonEncode(me));
        notifyListeners();
      }
    } on ApiException catch (_) {}
  }

  Future<void> logout({String? message}) async {
    if (me == null && api.token == null) return;
    live.stop();
    api.token = null;
    me = null;
    sessionMessage = message;
    await secure.clear();
    await db.setSetting('me', null);
    navKey.currentState?.popUntil((r) => r.isFirst);
    notifyListeners();
  }

  // ----------------------------------------------------------- connectivity

  void _onConnectivity(List<ConnectivityResult> results) {
    _hasNetwork = results.isNotEmpty && !results.every((r) => r == ConnectivityResult.none);
    if (!_hasNetwork) {
      _setOnline(false);
    } else {
      unawaited(_probe());
    }
  }

  Future<void> _probe() async {
    try {
      await api.request('GET', '/health', auth: false);
    } catch (_) {}
  }

  void _onReachability(bool ok) {
    if (ok && !_hasNetwork) _hasNetwork = true;
    if (ok != online) _setOnline(ok);
  }

  void _setOnline(bool value) {
    if (value == online) return;
    online = value;
    _probeTimer?.cancel();
    if (!value) {
      _probeTimer = Timer.periodic(const Duration(seconds: 8), (_) {
        if (_hasNetwork) _probe();
      });
    } else {
      live.kick();
      epoch++;
      if (pending > 0) scheduleMicrotask(() => syncNow(auto: true).catchError((_) => <OutboxItem>[]));
    }
    notifyListeners();
  }

  /// Re-checks the server, e.g. from a "Sync now" tap while offline.
  Future<bool> checkOnline() async {
    await _probe();
    return online;
  }

  // ----------------------------------------------------------------- outbox

  Future<void> enqueue({
    required String type,
    required Map<String, dynamic> payload,
    required int? baseVersion,
    required String label,
  }) async {
    await db.insertOutbox(OutboxItem(
      actionId: 'a-${newId()}',
      type: type,
      queuedAt: utcStamp(DateTime.now()),
      baseVersion: baseVersion,
      payload: payload,
      label: label,
    ));
    pending = await db.pendingCount();
    notifyListeners();
  }

  /// Online → send directly. Offline (or the request can't reach the server) → outbox.
  Future<Submitted> submitOrQueue({
    required String path,
    required Map<String, dynamic> body,
    required String outboxType,
    required int? baseVersion,
    required String label,
  }) async {
    if (online) {
      try {
        return Submitted(queued: false, response: await api.post(path, body));
      } on ApiException catch (e) {
        if (!e.isNetwork) rethrow;
      }
    }
    await enqueue(type: outboxType, payload: body, baseVersion: baseVersion, label: label);
    return const Submitted(queued: true);
  }

  /// Sends all pending actions in one Section 5.14 request.
  /// Returns the items that were processed (with their results).
  Future<List<OutboxItem>> syncNow({bool auto = false}) async {
    if (syncing) return [];
    final items = await db.pendingOutbox();
    if (items.isEmpty) return [];
    syncing = true;
    notifyListeners();
    try {
      final res = await api.post('/api/v1/offline-sync', {
        'device_id': deviceId,
        'actions': items.map((i) => i.toSyncJson()).toList(),
      });
      final results = asList(res is Map ? res['results'] : null);
      final processed = <String>{};
      for (final r in results) {
        final id = r['action_id'] as String?;
        if (id == null) continue;
        processed.add(id);
        await db.markResult(id,
            status: '${r['status'] ?? 'rejected'}',
            code: r['error_code'] as String?,
            message: syncResultMessage(r));
      }
      pending = await db.pendingCount();
      epoch++;
      final history = await db.outboxHistory();
      final done = history.where((h) => processed.contains(h.actionId)).toList();
      if (auto && done.isNotEmpty) {
        final rejected = done.where((d) => d.status == 'rejected').length;
        final ok = done.length - rejected;
        showSnack(
          rejected == 0
              ? 'Back online — $ok saved ${ok == 1 ? 'action' : 'actions'} synced.'
              : 'Back online — $ok synced, $rejected couldn\'t be applied.',
          error: rejected > 0,
          action: SnackBarAction(
            label: 'View',
            onPressed: () => navKey.currentState
                ?.push(MaterialPageRoute<void>(builder: (_) => const OutboxScreen())),
          ),
        );
      }
      return done;
    } finally {
      syncing = false;
      notifyListeners();
    }
  }
}
