import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../data/app_state.dart';
import '../screens/outbox.dart';

class NetworkChip extends StatelessWidget {
  const NetworkChip({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final scheme = Theme.of(context).colorScheme;
    final (icon, label, bg, fg) = s.syncing
        ? (Icons.sync, 'Syncing', scheme.tertiaryContainer, scheme.onTertiaryContainer)
        : s.online
            ? (Icons.cloud_done, 'Online', scheme.primaryContainer, scheme.onPrimaryContainer)
            : (Icons.cloud_off, 'Offline', scheme.errorContainer, scheme.onErrorContainer);
    final text = s.pending > 0 ? '$label · ${s.pending} pending' : label;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Tooltip(
        message: 'Network status: $text. Tap to open Outbox.',
        child: Material(
          color: bg,
          borderRadius: BorderRadius.circular(20),
          child: InkWell(
            borderRadius: BorderRadius.circular(20),
            onTap: () => Navigator.of(context)
                .push(MaterialPageRoute<void>(builder: (_) => const OutboxScreen())),
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 40),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 10),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  Icon(icon, size: 18, color: fg, semanticLabel: label),
                  const SizedBox(width: 6),
                  Text(text, style: TextStyle(color: fg, fontWeight: FontWeight.w500)),
                ]),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
