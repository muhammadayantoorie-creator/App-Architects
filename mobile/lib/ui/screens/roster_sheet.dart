import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/error_messages.dart';
import '../../core/formatters.dart';
import '../../core/nav.dart';
import '../../data/app_state.dart';
import '../../data/repository.dart';
import '../widgets/common.dart';

/// Returns true when an action was submitted or queued.
Future<bool?> showRosterSheet(
  BuildContext context, {
  required Map<String, dynamic> club,
  required Map<String, dynamic> player,
}) =>
    showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      builder: (_) => _RosterSheet(club: club, player: player),
    );

/// Club manager: register a new player in the club's squad. Needs a connection.
Future<bool?> showAddPlayerSheet(BuildContext context, {required Map<String, dynamic> club}) =>
    showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      builder: (_) => _AddPlayerSheet(club: club),
    );

class _AddPlayerSheet extends StatefulWidget {
  const _AddPlayerSheet({required this.club});
  final Map<String, dynamic> club;

  @override
  State<_AddPlayerSheet> createState() => _AddPlayerSheetState();
}

class _AddPlayerSheetState extends State<_AddPlayerSheet> {
  final _name = TextEditingController();
  final _position = TextEditingController();
  String _role = 'substitute';
  bool _busy = false;
  String? _error;

  static const _roles = ['captain', 'vice_captain', 'starter', 'substitute'];

  late final List<String> _knownPositions = asList(widget.club['roster'])
      .map((p) => '${p['position'] ?? ''}')
      .where((p) => p.isNotEmpty)
      .toSet()
      .toList();

  @override
  void dispose() {
    _name.dispose();
    _position.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final name = _name.text.trim();
    final position = _position.text.trim().toLowerCase();
    if (name.isEmpty || position.isEmpty) {
      setState(() => _error = 'Enter the player name and position.');
      return;
    }
    final ok = await confirmDialog(context,
        title: 'Add player?',
        message: 'Add $name (${position.toUpperCase()}, ${humanize(_role)}) to ${widget.club['name']}.',
        confirmLabel: 'Add player');
    if (!ok || !mounted) return;
    final s = context.read<AppState>();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await s.api.post('/api/v1/clubs/${widget.club['club_id']}/players', {
        'request_id': newId(),
        'league_id': widget.club['roster_league_id'],
        'squad_id': widget.club['squad_id'],
        'name': name,
        'position': position,
        'role': _role,
        'requested_by': s.userId,
      });
      if (!mounted) return;
      Navigator.pop(context, true);
      showSnack('$name added to the squad.');
    } on ApiException catch (e) {
      setState(() => _error = e.isNetwork ? offlineNoQueueMessage : e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Add player', style: t.textTheme.titleLarge),
          Text('${widget.club['name'] ?? ''}', style: t.textTheme.bodyMedium),
          const SizedBox(height: 16),
          TextField(
            controller: _name,
            textCapitalization: TextCapitalization.words,
            decoration: const InputDecoration(labelText: 'Player name'),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _position,
            autocorrect: false,
            decoration: InputDecoration(
              labelText: 'Position',
              hintText: _knownPositions.isEmpty ? 'e.g. gk' : 'e.g. ${_knownPositions.take(4).join(', ')}',
            ),
          ),
          if (_knownPositions.isNotEmpty) ...[
            const SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final p in _knownPositions)
                ActionChip(
                  label: Text(p.toUpperCase()),
                  tooltip: 'Use position $p',
                  onPressed: () => setState(() => _position.text = p),
                ),
            ]),
          ],
          const SizedBox(height: 16),
          DropdownButtonFormField<String>(
            initialValue: _role,
            decoration: const InputDecoration(labelText: 'Role'),
            items: [
              for (final r in _roles) DropdownMenuItem(value: r, child: Text(humanize(r))),
            ],
            onChanged: (v) => setState(() => _role = v ?? _role),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Row(children: [
              Icon(Icons.error_outline, color: t.colorScheme.error, semanticLabel: 'Error'),
              const SizedBox(width: 8),
              Expanded(child: Text(_error!, style: TextStyle(color: t.colorScheme.error))),
            ]),
          ],
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _busy ? null : _submit,
            child: _busy
                ? const SizedBox(
                    width: 22,
                    height: 22,
                    child: CircularProgressIndicator(strokeWidth: 2.5, semanticsLabel: 'Adding'))
                : const Text('Review and add'),
          ),
        ]),
      ),
    );
  }
}

class _RosterSheet extends StatefulWidget {
  const _RosterSheet({required this.club, required this.player});
  final Map<String, dynamic> club;
  final Map<String, dynamic> player;

  @override
  State<_RosterSheet> createState() => _RosterSheetState();
}

class _RosterSheetState extends State<_RosterSheet> {
  String _type = 'transfer';
  String? _dest;
  DateTime _effective = DateTime.now();
  DateTime _loanEnd = DateTime.now().add(const Duration(days: 30));
  final _reason = TextEditingController();
  bool _busy = false;
  String? _error;

  late final List<Map<String, dynamic>> _squads = asList(widget.club['destination_squads']);

  @override
  void initState() {
    super.initState();
    if (_squads.isNotEmpty) _dest = _squads.first['squad_id'] as String?;
  }

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  String get _playerName => '${widget.player['name'] ?? 'Player'}';
  String get _destName =>
      '${_squads.firstWhere((s) => s['squad_id'] == _dest, orElse: () => {})['name'] ?? _dest ?? ''}';

  Future<void> _pickDate({required bool loanEnd}) async {
    final now = DateTime.now();
    final d = await showDatePicker(
      context: context,
      initialDate: loanEnd ? _loanEnd : _effective,
      firstDate: DateTime(now.year - 1),
      lastDate: DateTime(now.year + 3),
    );
    if (d != null) setState(() => loanEnd ? _loanEnd = d : _effective = d);
  }

  String get _summary => switch (_type) {
        'loan' =>
          'Loan $_playerName to $_destName from ${prettyDate(_effective)} until ${prettyDate(_loanEnd)}.',
        'release' => 'Release $_playerName from ${widget.club['name']} on ${prettyDate(_effective)}.',
        _ => 'Transfer $_playerName to $_destName on ${prettyDate(_effective)}.',
      };

  Future<void> _submit() async {
    if (_type != 'release' && _dest == null) {
      setState(() => _error = 'Choose a destination club.');
      return;
    }
    if (_type == 'loan' && !_loanEnd.isAfter(_effective)) {
      setState(() => _error = 'The loan end date must be after the start date.');
      return;
    }
    if (_reason.text.trim().isEmpty) {
      setState(() => _error = 'Add a short reason.');
      return;
    }
    final ok = await confirmDialog(context,
        title: 'Confirm ${humanize(_type).toLowerCase()}?',
        message: _summary,
        confirmLabel: 'Confirm');
    if (!ok || !mounted) return;
    final s = context.read<AppState>();
    final body = {
      'request_id': newId(),
      'league_id': widget.player['league_id'] ?? widget.club['roster_league_id'],
      'player_id': widget.player['player_id'],
      'type': _type,
      'from_squad_id': widget.player['squad_id'] ?? widget.club['squad_id'],
      'to_squad_id': _type == 'release' ? null : _dest,
      'effective_date': ymd(_effective),
      'loan_end_date': _type == 'loan' ? ymd(_loanEnd) : null,
      'reason': _reason.text.trim(),
      'requested_by': s.userId,
    };
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final r = await s.submitOrQueue(
        path: '/api/v1/roster/actions',
        body: body,
        outboxType: 'roster_transfer',
        baseVersion: (widget.player['audit_count'] as num?)?.toInt() ?? 0,
        label: '${humanize(_type)} · $_playerName${_type == 'release' ? '' : ' → $_destName'}',
      );
      if (!mounted) return;
      Navigator.pop(context, true);
      if (r.queued) {
        showSnack(friendlyMessage('NETWORK'));
      } else {
        final res = asMap(r.response);
        final state = res['state'] ?? asMap(res['registration'])['state'];
        showSnack(state == 'deferred_until_match_end'
            ? 'Saved. Will take effect after the current match ends.'
            : '${humanize(_type)} completed for $_playerName.');
      }
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(_playerName, style: t.textTheme.titleLarge),
          Text('${'${widget.player['position'] ?? ''}'.toUpperCase()} · ${widget.club['name'] ?? ''}',
              style: t.textTheme.bodyMedium),
          const SizedBox(height: 16),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'transfer', label: Text('Transfer')),
              ButtonSegment(value: 'loan', label: Text('Loan')),
              ButtonSegment(value: 'release', label: Text('Release')),
            ],
            selected: {_type},
            showSelectedIcon: false,
            onSelectionChanged: (v) => setState(() => _type = v.first),
          ),
          const SizedBox(height: 16),
          if (_type != 'release') ...[
            if (_squads.isEmpty)
              const Text('No destination clubs are available.')
            else
              DropdownButtonFormField<String>(
                initialValue: _dest,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Destination club'),
                items: [
                  for (final s in _squads)
                    DropdownMenuItem(
                      value: s['squad_id'] as String,
                      child: Text('${s['name'] ?? s['squad_id']}', overflow: TextOverflow.ellipsis),
                    ),
                ],
                onChanged: (v) => setState(() => _dest = v),
              ),
            const SizedBox(height: 16),
          ],
          OutlinedButton.icon(
            onPressed: () => _pickDate(loanEnd: false),
            icon: const Icon(Icons.event, semanticLabel: 'Effective date'),
            label: Text('Effective date: ${prettyDate(_effective)}'),
          ),
          if (_type == 'loan') ...[
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: () => _pickDate(loanEnd: true),
              icon: const Icon(Icons.event_available, semanticLabel: 'Loan end date'),
              label: Text('Loan ends: ${prettyDate(_loanEnd)}'),
            ),
          ],
          const SizedBox(height: 16),
          TextField(
            controller: _reason,
            textCapitalization: TextCapitalization.sentences,
            decoration: const InputDecoration(
                labelText: 'Reason', hintText: 'e.g. Needs more match time'),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Row(children: [
              Icon(Icons.error_outline, color: t.colorScheme.error, semanticLabel: 'Error'),
              const SizedBox(width: 8),
              Expanded(child: Text(_error!, style: TextStyle(color: t.colorScheme.error))),
            ]),
          ],
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _busy ? null : _submit,
            child: _busy
                ? const SizedBox(
                    width: 22,
                    height: 22,
                    child: CircularProgressIndicator(strokeWidth: 2.5, semanticsLabel: 'Submitting'))
                : Text('Review ${humanize(_type).toLowerCase()}'),
          ),
        ]),
      ),
    );
  }
}
