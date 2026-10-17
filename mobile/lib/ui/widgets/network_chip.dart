import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme.dart';
import '../../data/app_state.dart';
import '../screens/outbox.dart';

/// White status pill in the app bar: coloured dot + text. Tap opens the Outbox.
class NetworkChip extends StatelessWidget {
  const NetworkChip({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final (dot, label) = s.syncing
        ? (AppColors.accent, 'Syncing')
        : s.online
            ? (const Color(0xFF2E7D32), 'Online')
            : (AppColors.live, 'Offline');
    final text = s.pending > 0 ? '$label · ${s.pending} pending' : label;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Tooltip(
        message: 'Network status: $text. Tap to open Outbox.',
        child: Material(
          color: Colors.white,
          borderRadius: BorderRadius.circular(14),
          child: InkWell(
            borderRadius: BorderRadius.circular(14),
            onTap: () => Navigator.of(context)
                .push(MaterialPageRoute<void>(builder: (_) => const OutboxScreen())),
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 28, minWidth: 48),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(color: dot, shape: BoxShape.circle),
                  ),
                  const SizedBox(width: 6),
                  Text(text,
                      semanticsLabel: 'Network status $text',
                      style: const TextStyle(
                          color: AppColors.onPrimary, fontSize: 12, fontWeight: FontWeight.w700)),
                ]),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
