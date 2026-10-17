import 'dart:convert';

import '../../core/error_messages.dart';

class OutboxItem {
  OutboxItem({
    required this.actionId,
    required this.type,
    required this.queuedAt,
    required this.baseVersion,
    required this.payload,
    required this.label,
    this.status = 'pending',
    this.resultCode,
    this.resultMessage,
    this.syncedAt,
  });

  final String actionId;
  final String type; // score_event | roster_transfer
  final String queuedAt;
  final int? baseVersion;
  final Map<String, dynamic> payload;
  final String label;
  final String status; // pending | applied | duplicate | rejected
  final String? resultCode;
  final String? resultMessage;
  final String? syncedAt;

  factory OutboxItem.fromRow(Map<String, Object?> r) => OutboxItem(
        actionId: r['action_id'] as String,
        type: r['type'] as String,
        queuedAt: r['queued_at'] as String,
        baseVersion: r['base_version'] as int?,
        payload: Map<String, dynamic>.from(jsonDecode(r['payload'] as String) as Map),
        label: r['label'] as String? ?? '',
        status: r['status'] as String? ?? 'pending',
        resultCode: r['result_code'] as String?,
        resultMessage: r['result_message'] as String?,
        syncedAt: r['synced_at'] as String?,
      );

  Map<String, Object?> toRow() => {
        'action_id': actionId,
        'type': type,
        'queued_at': queuedAt,
        'base_version': baseVersion,
        'payload': jsonEncode(payload),
        'label': label,
        'status': status,
        'result_code': resultCode,
        'result_message': resultMessage,
        'synced_at': syncedAt,
      };

  /// Exact Section 5.14 action shape.
  Map<String, dynamic> toSyncJson() => {
        'action_id': actionId,
        'type': type,
        'queued_at': queuedAt,
        'base_version': baseVersion,
        'payload': payload,
      };
}

String syncResultMessage(Map r) {
  switch (r['status']) {
    case 'applied':
      return r['resolution'] == 'rebased_append'
          ? 'Synced — others had updated this match; your action was added on top'
          : 'Synced';
    case 'duplicate':
      return 'Already synced';
    default:
      return friendlyMessage('${r['error_code'] ?? 'SERVER_ERROR'}');
  }
}
