import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';

import '../app_state.dart';

class LiveEvent {
  LiveEvent(this.type, this.data);
  final String type;
  final Map<String, dynamic> data;
}

/// SSE client for /api/v1/live. Connected only while a fixtures/match screen is visible
/// and the app is online. Reconnects with 1, 2, 4, 8 … 30 s backoff.
class LiveService {
  LiveService(this.s);
  final AppState s;

  final _dio = Dio(BaseOptions(connectTimeout: const Duration(seconds: 3)));
  final _ctrl = StreamController<LiveEvent>.broadcast();
  Stream<LiveEvent> get events => _ctrl.stream;

  int _refs = 0;
  String? _league;
  CancelToken? _cancel;
  Timer? _retry;
  bool _running = false;
  int _backoff = 1;

  void acquire(String leagueId) {
    _refs++;
    if (_league != leagueId) {
      _league = leagueId;
      _restart();
    } else if (!_running) {
      _connect();
    }
  }

  void release() {
    _refs = (_refs - 1).clamp(0, 1 << 20);
    if (_refs == 0) stop();
  }

  void switchLeague(String leagueId) {
    if (_league == leagueId) return;
    _league = leagueId;
    if (_refs > 0) _restart();
  }

  /// Called when the app goes back online.
  void kick() {
    if (_refs > 0 && !_running) {
      _backoff = 1;
      _restart();
    }
  }

  void stop() {
    _retry?.cancel();
    _cancel?.cancel();
    _cancel = null;
    _running = false;
  }

  void _restart() {
    stop();
    _connect();
  }

  void _scheduleRetry() {
    if (_refs == 0) return;
    _retry?.cancel();
    _retry = Timer(Duration(seconds: _backoff), _connect);
    _backoff = (_backoff * 2).clamp(1, 30);
  }

  Future<void> _connect() async {
    if (_refs == 0 || _running || s.api.mock.enabled) return;
    final token = s.api.token;
    if (!s.online || token == null || _league == null) {
      _scheduleRetry();
      return;
    }
    _running = true;
    final cancel = _cancel = CancelToken();
    try {
      final res = await _dio.get<ResponseBody>(
        s.api.url('/api/v1/live'),
        queryParameters: {'league_id': _league},
        cancelToken: cancel,
        options: Options(
          responseType: ResponseType.stream,
          headers: {'Accept': 'text/event-stream', 'Authorization': 'Bearer $token'},
        ),
      );
      _backoff = 1;
      String? event;
      final data = StringBuffer();
      final lines = res.data!.stream
          .cast<List<int>>()
          .transform(utf8.decoder)
          .transform(const LineSplitter());
      await for (final line in lines) {
        if (line.isEmpty) {
          if (data.isNotEmpty) _emit(event ?? 'message', data.toString());
          event = null;
          data.clear();
        } else if (line.startsWith(':')) {
          continue;
        } else if (line.startsWith('event:')) {
          event = line.substring(6).trim();
        } else if (line.startsWith('data:')) {
          if (data.isNotEmpty) data.write('\n');
          data.write(line.substring(5).trim());
        }
      }
    } catch (_) {
      // Fall through to reconnect.
    }
    if (identical(_cancel, cancel)) {
      _running = false;
      if (!cancel.isCancelled) _scheduleRetry();
    }
  }

  void _emit(String type, String raw) {
    try {
      final d = jsonDecode(raw);
      if (d is Map) _ctrl.add(LiveEvent(type, Map<String, dynamic>.from(d)));
    } catch (_) {}
  }
}
