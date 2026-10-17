import 'dart:convert';

import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

import '../data/sync/outbox.dart';

class CacheEntry {
  CacheEntry(this.data, this.fetchedAt);
  final dynamic data;
  final DateTime fetchedAt;
}

class AppDb {
  late Database _db;

  Future<void> open() async {
    _db = await openDatabase(
      p.join(await getDatabasesPath(), 'nascon.db'),
      version: 1,
      onCreate: (db, _) async {
        await db.execute('CREATE TABLE cache(key TEXT PRIMARY KEY, json TEXT, fetched_at TEXT)');
        await db.execute('CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT)');
        await db.execute('''CREATE TABLE outbox(
          action_id TEXT PRIMARY KEY, type TEXT, queued_at TEXT, base_version INTEGER,
          payload TEXT, label TEXT, status TEXT DEFAULT 'pending', result_code TEXT,
          result_message TEXT, synced_at TEXT)''');
      },
    );
  }

  Future<String?> getSetting(String key) async {
    final r = await _db.query('settings', where: 'key = ?', whereArgs: [key]);
    return r.isEmpty ? null : r.first['value'] as String?;
  }

  Future<void> setSetting(String key, String? value) async {
    if (value == null) {
      await _db.delete('settings', where: 'key = ?', whereArgs: [key]);
    } else {
      await _db.insert('settings', {'key': key, 'value': value},
          conflictAlgorithm: ConflictAlgorithm.replace);
    }
  }

  Future<CacheEntry?> getCache(String key) async {
    final r = await _db.query('cache', where: 'key = ?', whereArgs: [key]);
    if (r.isEmpty) return null;
    return CacheEntry(
      jsonDecode(r.first['json'] as String),
      DateTime.tryParse(r.first['fetched_at'] as String? ?? '')?.toLocal() ?? DateTime.now(),
    );
  }

  Future<void> putCache(String key, dynamic data) => _db.insert(
        'cache',
        {
          'key': key,
          'json': jsonEncode(data),
          'fetched_at': DateTime.now().toUtc().toIso8601String(),
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );

  Future<void> clearCache() => _db.delete('cache');

  Future<void> insertOutbox(OutboxItem item) =>
      _db.insert('outbox', item.toRow(), conflictAlgorithm: ConflictAlgorithm.replace);

  Future<List<OutboxItem>> pendingOutbox() async {
    final r = await _db.query('outbox', where: "status = 'pending'", orderBy: 'queued_at ASC');
    return r.map(OutboxItem.fromRow).toList();
  }

  Future<List<OutboxItem>> outboxHistory() async {
    final r = await _db.query('outbox',
        where: "status != 'pending'", orderBy: 'synced_at DESC, queued_at DESC', limit: 30);
    return r.map(OutboxItem.fromRow).toList();
  }

  Future<int> pendingCount() async =>
      Sqflite.firstIntValue(
          await _db.rawQuery("SELECT COUNT(*) FROM outbox WHERE status = 'pending'")) ??
      0;

  Future<void> markResult(String actionId,
          {required String status, String? code, required String message}) =>
      _db.update(
        'outbox',
        {
          'status': status,
          'result_code': code,
          'result_message': message,
          'synced_at': DateTime.now().toUtc().toIso8601String(),
        },
        where: 'action_id = ?',
        whereArgs: [actionId],
      );

  Future<void> clearHistory() => _db.delete('outbox', where: "status != 'pending'");
}
