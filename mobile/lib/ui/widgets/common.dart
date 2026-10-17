import 'package:flutter/material.dart';

import '../../core/formatters.dart';

Future<bool> confirmDialog(
  BuildContext context, {
  required String title,
  required String message,
  required String confirmLabel,
}) async {
  final r = await showDialog<bool>(
    context: context,
    builder: (c) => AlertDialog(
      title: Text(title),
      content: Text(message),
      actions: [
        TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(c, true), child: Text(confirmLabel)),
      ],
    ),
  );
  return r ?? false;
}

class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.icon,
    required this.message,
    this.actionLabel,
    this.onAction,
  });

  final IconData icon;
  final String message;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 48, color: t.colorScheme.onSurfaceVariant, semanticLabel: message),
          const SizedBox(height: 16),
          Text(message, textAlign: TextAlign.center, style: t.textTheme.bodyLarge),
          if (actionLabel != null) ...[
            const SizedBox(height: 16),
            OutlinedButton(onPressed: onAction, child: Text(actionLabel!)),
          ],
        ]),
      ),
    );
  }
}

/// Wraps an empty state so pull-to-refresh still works.
class ScrollableEmpty extends StatelessWidget {
  const ScrollableEmpty({super.key, required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
        builder: (context, c) => ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [SizedBox(height: c.maxHeight, child: child)],
        ),
      );
}

class OfflineBanner extends StatelessWidget {
  const OfflineBanner({super.key, this.at});
  final DateTime? at;

  @override
  Widget build(BuildContext context) {
    final s = Theme.of(context).colorScheme;
    final when = at == null
        ? ''
        : ' from ${dayLabel(at!) == 'Today' ? hm(at!) : dateTimeLabel(at!)}';
    return Semantics(
      liveRegion: true,
      child: Container(
        width: double.infinity,
        color: s.secondaryContainer,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(children: [
          Icon(Icons.cloud_off, size: 18, color: s.onSecondaryContainer, semanticLabel: 'Offline'),
          const SizedBox(width: 8),
          Expanded(
            child: Text('Offline · showing data$when',
                style: TextStyle(color: s.onSecondaryContainer)),
          ),
        ]),
      ),
    );
  }
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key, this.trailing});
  final String text;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(0, 16, 0, 8),
        child: Row(children: [
          Expanded(
            child: Text(text,
                style: Theme.of(context).textTheme.titleMedium, semanticsLabel: text),
          ),
          ?trailing,
        ]),
      );
}

class LabelValue extends StatelessWidget {
  const LabelValue(this.label, this.value, {super.key, this.bold = false});
  final String label;
  final String value;
  final bool bold;

  @override
  Widget build(BuildContext context) {
    final style = bold
        ? Theme.of(context).textTheme.titleMedium
        : Theme.of(context).textTheme.bodyLarge;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(children: [
        Expanded(child: Text(label, style: style)),
        Text(value, style: style),
      ]),
    );
  }
}
