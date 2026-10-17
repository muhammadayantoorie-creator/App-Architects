import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/formatters.dart';
import '../../core/nav.dart';
import '../../data/app_state.dart';
import '../../data/sync/outbox.dart';
import '../widgets/common.dart';
import '../widgets/network_chip.dart';

class OutboxScreen extends StatefulWidget {
  const OutboxScreen({super.key});

  @override
  State<OutboxScreen> createState() => _OutboxScreenState();
}

class _OutboxScreenState extends State<OutboxScreen> {
  List<OutboxItem> _pending = [];
  List<OutboxItem> _history = [];
  int _seenEpoch = -1;
  int _seenPending = -1;

  Future<void> _load() async {
    final s = context.read<AppState>();
    final p = await s.db.pendingOutbox();
    final h = await s.db.outboxHistory();
    if (mounted) {
      setState(() {
        _pending = p;
        _history = h;
      });
    }
  }

  Future<void> _sync() async {
    final s = context.read<AppState>();
    if (!s.online && !await s.checkOnline()) {
      showSnack("Still offline. Your actions are saved and will sync when you're back online.",
          error: true);
      return;
    }
    try {
      final done = await s.syncNow();
      await _load();
      if (!mounted) return;
      if (done.isEmpty) {
        showSnack('Nothing to sync.');
      } else {
        _showResults(done);
      }
    } on ApiException catch (e) {
      showSnack(
          e.isNetwork
              ? "Couldn't reach the server. Your actions are still saved."
              : e.message,
          error: true);
    }
  }

  void _showResults(List<OutboxItem> done) {
    showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (c) => ConstrainedBox(
        constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(c).height * 0.7),
        child: ListView(shrinkWrap: true, padding: const EdgeInsets.fromLTRB(16, 0, 16, 16), children: [
          Text('Sync results', style: Theme.of(c).textTheme.titleLarge),
          const SizedBox(height: 8),
          for (final i in done) _ResultTile(item: i),
          const SizedBox(height: 8),
          FilledButton(onPressed: () => Navigator.pop(c), child: const Text('Done')),
        ]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    if (s.epoch != _seenEpoch || s.pending != _seenPending) {
      _seenEpoch = s.epoch;
      _seenPending = s.pending;
      WidgetsBinding.instance.addPostFrameCallback((_) => _load());
    }
    final t = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Outbox'), actions: const [NetworkChip()]),
      body: SafeArea(
        child: ListView(padding: const EdgeInsets.all(16), children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Row(children: [
                  Icon(s.online ? Icons.cloud_done : Icons.cloud_off,
                      semanticLabel: s.online ? 'Online' : 'Offline'),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      s.pending == 0
                          ? 'Everything is synced.'
                          : '${s.pending} ${s.pending == 1 ? 'action is' : 'actions are'} waiting to sync.',
                      style: t.textTheme.titleMedium,
                    ),
                  ),
                ]),
                const SizedBox(height: 4),
                Text(
                  s.online
                      ? 'Saved actions sync automatically when you are online.'
                      : "You're offline. Actions are saved on this phone and sync automatically when you reconnect.",
                  style: t.textTheme.bodyMedium,
                ),
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: s.syncing || _pending.isEmpty ? null : _sync,
                  icon: s.syncing
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, semanticsLabel: 'Syncing'))
                      : const Icon(Icons.sync, semanticLabel: 'Sync now'),
                  label: Text(s.syncing ? 'Syncing…' : 'Sync now'),
                ),
              ]),
            ),
          ),
          const SectionTitle('Pending'),
          if (_pending.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Text('No pending actions. Anything you do while offline will appear here.'),
            )
          else
            for (final i in _pending)
              Card(
                margin: const EdgeInsets.only(bottom: 8),
                child: ListTile(
                  leading: const Icon(Icons.schedule, semanticLabel: 'Pending'),
                  title: Text(i.label),
                  subtitle: Text(
                      '${i.type == 'score_event' ? 'Score' : 'Roster'} · queued ${_when(i.queuedAt)}'),
                  trailing: Chip(
                    label: const Text('Pending'),
                    visualDensity: VisualDensity.compact,
                    backgroundColor: t.colorScheme.secondaryContainer,
                  ),
                ),
              ),
          SectionTitle(
            'Last sync results',
            trailing: _history.isEmpty
                ? null
                : TextButton(
                    onPressed: () async {
                      await context.read<AppState>().db.clearHistory();
                      await _load();
                    },
                    child: const Text('Clear'),
                  ),
          ),
          if (_history.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Text('No synced actions yet.'),
            )
          else
            for (final i in _history) _ResultTile(item: i),
        ]),
      ),
    );
  }

  static String _when(String stamp) {
    final d = parseDate(stamp);
    return d == null ? stamp : dateTimeLabel(d);
  }
}

class _ResultTile extends StatelessWidget {
  const _ResultTile({required this.item});
  final OutboxItem item;

  @override
  Widget build(BuildContext context) {
    final s = Theme.of(context).colorScheme;
    final (icon, label, color) = switch (item.status) {
      'applied' => (Icons.check_circle, 'Applied', s.primary),
      'duplicate' => (Icons.done_all, 'Already synced', s.primary),
      _ => (Icons.error, 'Rejected', s.error),
    };
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Icon(icon, color: color, semanticLabel: label),
        title: Text(item.label),
        subtitle: Text('$label · ${item.resultMessage ?? ''}'),
      ),
    );
  }
}
