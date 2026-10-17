import 'package:flutter/material.dart';

import '../../core/formatters.dart';

/// Match status as icon + text (never colour alone).
class StatusLabel extends StatelessWidget {
  const StatusLabel(this.status, {super.key});
  final String? status;

  static String text(String? status) => switch (status) {
        'in_progress' => 'Live',
        'completed' => 'Full time',
        'upcoming' => 'Upcoming',
        _ => humanize(status),
      };

  @override
  Widget build(BuildContext context) {
    final s = Theme.of(context).colorScheme;
    final (icon, color) = switch (status) {
      'in_progress' => (Icons.radio_button_checked, s.error),
      'completed' => (Icons.check_circle_outline, s.onSurfaceVariant),
      'upcoming' => (Icons.schedule, s.primary),
      'postponed' => (Icons.update, s.onSurfaceVariant),
      'abandoned' => (Icons.block, s.onSurfaceVariant),
      'cancelled' => (Icons.cancel_outlined, s.onSurfaceVariant),
      _ => (Icons.info_outline, s.onSurfaceVariant),
    };
    final label = text(status);
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Icon(icon, size: 16, color: color, semanticLabel: label),
      const SizedBox(width: 4),
      Text(label,
          style: Theme.of(context)
              .textTheme
              .labelMedium
              ?.copyWith(color: color, fontWeight: FontWeight.w600)),
    ]);
  }
}
