import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

final _money = NumberFormat('#,##0.00', 'en_US');

String money(num? minor, [String? currency]) =>
    '${currency ?? 'PKR'} ${_money.format((minor ?? 0) / 100)}';

String humanize(String? key) {
  final s = (key ?? '').replaceAll('_', ' ').replaceAll('-', ' ').trim();
  if (s.isEmpty) return '';
  return s[0].toUpperCase() + s.substring(1);
}

DateTime? parseDate(dynamic s) => s is String ? DateTime.tryParse(s)?.toLocal() : null;

String hm(DateTime d) => DateFormat('HH:mm').format(d.toLocal());

String dayLabel(DateTime d) {
  final now = DateTime.now();
  final a = DateTime(d.year, d.month, d.day);
  final b = DateTime(now.year, now.month, now.day);
  final diff = a.difference(b).inDays;
  if (diff == 0) return 'Today';
  if (diff == 1) return 'Tomorrow';
  if (diff == -1) return 'Yesterday';
  return DateFormat('EEE d MMM').format(d);
}

String dateTimeLabel(DateTime d) => '${dayLabel(d)}, ${hm(d)}';

String prettyDate(DateTime d) => DateFormat('d MMM yyyy').format(d);

String ymd(DateTime d) => DateFormat('yyyy-MM-dd').format(d);

/// UTC timestamp without milliseconds: YYYY-MM-DDTHH:MM:SSZ
String utcStamp(DateTime d) => "${DateFormat("yyyy-MM-dd'T'HH:mm:ss").format(d.toUtc())}Z";

Color? parseHex(dynamic s) {
  if (s is! String) return null;
  var h = s.replaceAll('#', '').trim();
  if (h.length == 6) h = 'FF$h';
  final v = int.tryParse(h, radix: 16);
  return v == null || h.length != 8 ? null : Color(v);
}

String formatDiff(dynamic v) {
  if (v is int) return v > 0 ? '+$v' : '$v';
  if (v is num) {
    final s = v.toStringAsFixed(3);
    return v > 0 ? '+$s' : s;
  }
  return '${v ?? '-'}';
}
