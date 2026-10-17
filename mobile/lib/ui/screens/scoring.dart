import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/error_messages.dart';
import '../../core/formatters.dart';
import '../../core/nav.dart';
import '../../data/app_state.dart';
import '../../data/repository.dart';
import '../widgets/common.dart';
import '../widgets/network_chip.dart';
import '../widgets/status_label.dart';
import 'match.dart';

List<String> scoringKeys(dynamic sport) {
  final m = asMap(sport);
  final se = m['scoring_events'] ?? asMap(m['config'])['scoring_events'];
  if (se is Map) return se.keys.map((k) => '$k').toList();
  if (se is List) {
    return se
        .map((e) => e is Map ? '${e['key'] ?? e['type'] ?? e['name'] ?? ''}' : '$e')
        .where((k) => k.isNotEmpty)
        .toList();
  }
  return [];
}

class ScoringScreen extends StatefulWidget {
  const ScoringScreen({super.key, required this.leagueId, this.matchId});
  final String leagueId;
  final String? matchId;

  @override
  State<ScoringScreen> createState() => _ScoringScreenState();
}

class _ScoringScreenState extends State<ScoringScreen> {
  late final AppState _s = context.read<AppState>();
  List<Map<String, dynamic>> _fixtures = [];
  String? _matchId;
  Map<String, dynamic>? _match;
  bool _fromCache = false;
  DateTime? _fetchedAt;
  List<String> _keys = [];
  bool _drawAllowed = true;
  String _side = 'home';
  bool _loading = true;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _matchId = widget.matchId;
    _init();
  }

  Future<void> _init() async {
    try {
      final l = await _s.repo.fixtures(widget.leagueId);
      _fixtures = asList(asMap(l.data)['fixtures'])
        ..sort((a, b) => '${a['scheduled_at']}'.compareTo('${b['scheduled_at']}'));
    } catch (_) {}
    _matchId ??= (_fixtures.where((f) => f['status'] == 'in_progress').firstOrNull ??
            _fixtures.where((f) => f['status'] == 'upcoming').firstOrNull ??
            _fixtures.firstOrNull)?['match_id'] as String?;
    if (_matchId != null) {
      await _loadMatch();
    } else if (mounted) {
      setState(() {
        _loading = false;
        _error = 'No matches available to score.';
      });
    }
  }

  Future<void> _loadMatch() async {
    final id = _matchId!;
    setState(() => _loading = true);
    Map<String, dynamic>? m;
    try {
      final l = await _s.repo.match(id);
      m = asMap(l.data);
      _fromCache = l.fromCache;
      _fetchedAt = l.fetchedAt;
    } catch (_) {
      final f = _fixtures.where((f) => f['match_id'] == id).firstOrNull;
      if (f != null) {
        m = {
          'match_id': id,
          'status': f['status'],
          'version': f['version'],
          'scheduled_at': f['scheduled_at'],
          'home': {'team_id': f['home_team_id'], 'name': f['home_name'], 'score': f['home_score']},
          'away': {'team_id': f['away_team_id'], 'name': f['away_name'], 'score': f['away_score']},
          'events': <dynamic>[],
        };
        _fromCache = true;
        _fetchedAt = null;
      }
    }
    final sportId = m?['sport_id'] as String? ?? _s.sportIdFor(widget.leagueId);
    var keys = <String>[];
    var drawAllowed = true;
    if (sportId != null) {
      try {
        final sport = asMap((await _s.repo.sport(sportId)).data);
        keys = scoringKeys(sport);
        drawAllowed = sport['draw_allowed'] != false && sport['allows_draw'] != false;
      } catch (_) {}
    }
    if (!mounted) return;
    setState(() {
      _match = m;
      _keys = keys;
      _drawAllowed = drawAllowed;
      _loading = false;
      _error = m == null ? offlineReadMessage : null;
    });
  }

  Map<String, dynamic> get _home => asMap(_match?['home']);
  Map<String, dynamic> get _away => asMap(_match?['away']);
  String get _vs => '${_home['name']} vs ${_away['name']}';
  int? get _version => (_match?['version'] as num?)?.toInt();

  Future<void> _send({
    required String type,
    required Map<String, dynamic> payload,
    required String confirmTitle,
    required String label,
    required String successText,
  }) async {
    final ok = await confirmDialog(context,
        title: confirmTitle, message: '$_vs\n$label', confirmLabel: 'Confirm');
    if (!ok || !mounted) return;
    setState(() => _busy = true);
    try {
      final r = await _s.submitOrQueue(
        path: '/api/v1/events',
        body: {'event_id': newId(), 'match_id': _matchId, 'type': type, 'payload': payload},
        outboxType: 'score_event',
        baseVersion: _version,
        label: '$label · $_vs',
      );
      if (r.queued) {
        showSnack(friendlyMessage('NETWORK'));
      } else {
        showSnack(successText);
        final v = asMap(r.response)['match_version'];
        if (v != null) _match?['version'] = v;
        await _loadMatch();
      }
    } on ApiException catch (e) {
      showSnack(e.message, error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _score(String key) {
    final team = _side == 'home' ? _home : _away;
    _send(
      type: 'score',
      payload: {'team_id': team['team_id'], 'event_type': key},
      confirmTitle: 'Add ${humanize(key)}?',
      label: '${humanize(key)} for ${team['name']}',
      successText: '${humanize(key)} added for ${team['name']}.',
    );
  }

  Future<void> _correct() async {
    final names = {_home['team_id']: _home['name'], _away['team_id']: _away['name']};
    final events = asList(_match?['events'])
        .where((e) =>
            const ['score', 'discipline', 'tiebreak_winner'].contains(e['type']) &&
            e['compensated'] != true)
        .toList()
      ..sort((a, b) => ((b['sequence'] ?? 0) as num).compareTo((a['sequence'] ?? 0) as num));
    if (events.isEmpty) {
      showSnack('There are no events that can be corrected yet.', error: true);
      return;
    }
    final picked = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (c) => ConstrainedBox(
        constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(c).height * 0.7),
        child: ListView(shrinkWrap: true, padding: const EdgeInsets.fromLTRB(16, 0, 16, 16), children: [
          Text('Which event is wrong?', style: Theme.of(c).textTheme.titleLarge),
          const SizedBox(height: 8),
          for (final e in events)
            ListTile(
              leading: Text('#${e['sequence']}'),
              title: Text(eventTitle(e, names)),
              onTap: () => Navigator.pop(c, e),
            ),
        ]),
      ),
    );
    if (picked == null || !mounted) return;
    final reasonCtrl = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Reason for correction'),
        content: TextField(
          controller: reasonCtrl,
          autofocus: true,
          textCapitalization: TextCapitalization.sentences,
          decoration: const InputDecoration(hintText: 'e.g. Wrong team recorded'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c), child: const Text('Cancel')),
          FilledButton(
            onPressed: () => Navigator.pop(c, reasonCtrl.text.trim()),
            child: const Text('Continue'),
          ),
        ],
      ),
    );
    reasonCtrl.dispose();
    if (reason == null || !mounted) return;
    if (reason.isEmpty) {
      showSnack('Please add a reason for the correction.', error: true);
      return;
    }
    await _send(
      type: 'compensation',
      payload: {'compensates': picked['event_id'], 'reason': reason},
      confirmTitle: 'Correct this event?',
      label: 'Correction of "${eventTitle(picked, names)}"',
      successText: 'Event corrected.',
    );
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final status = _match?['status'] as String?;
    return Scaffold(
      appBar: AppBar(title: const Text('Scoring'), actions: const [NetworkChip()]),
      body: SafeArea(
        child: Column(children: [
          if (_fromCache && _match != null) OfflineBanner(at: _fetchedAt),
          Expanded(
            child: ListView(padding: const EdgeInsets.all(16), children: [
              if (_fixtures.isNotEmpty)
                DropdownButtonFormField<String>(
                  key: ValueKey(_matchId),
                  initialValue: _fixtures.any((f) => f['match_id'] == _matchId) ? _matchId : null,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Match'),
                  items: [
                    for (final f in _fixtures)
                      DropdownMenuItem(
                        value: f['match_id'] as String,
                        child: Text(
                            '${f['home_name']} vs ${f['away_name']} · ${StatusLabel.text(f['status'] as String?)}',
                            overflow: TextOverflow.ellipsis),
                      ),
                  ],
                  onChanged: _busy
                      ? null
                      : (v) {
                          if (v == null || v == _matchId) return;
                          _matchId = v;
                          _side = 'home';
                          _loadMatch();
                        },
                ),
              const SizedBox(height: 16),
              if (_loading)
                const Padding(
                  padding: EdgeInsets.all(32),
                  child: Center(child: CircularProgressIndicator(semanticsLabel: 'Loading match')),
                )
              else if (_match == null)
                EmptyState(icon: Icons.error_outline, message: _error ?? serverErrorMessage)
              else ...[
                ScoreHeader(match: _match!),
                const SizedBox(height: 16),
                if (status == 'upcoming')
                  FilledButton.icon(
                    onPressed: _busy
                        ? null
                        : () => _send(
                              type: 'match_start',
                              payload: {},
                              confirmTitle: 'Start this match?',
                              label: 'Start match',
                              successText: 'Match started.',
                            ),
                    icon: const Icon(Icons.play_arrow, semanticLabel: 'Start match'),
                    label: const Text('Start match'),
                  ),
                if (status == 'in_progress') ...[
                  Text('Team', style: t.textTheme.titleMedium),
                  const SizedBox(height: 8),
                  SegmentedButton<String>(
                    segments: [
                      ButtonSegment(
                          value: 'home',
                          label: Text('${_home['name'] ?? 'Home'}', overflow: TextOverflow.ellipsis)),
                      ButtonSegment(
                          value: 'away',
                          label: Text('${_away['name'] ?? 'Away'}', overflow: TextOverflow.ellipsis)),
                    ],
                    selected: {_side},
                    onSelectionChanged: (v) => setState(() => _side = v.first),
                  ),
                  const SizedBox(height: 16),
                  Text('Add a score', style: t.textTheme.titleMedium),
                  const SizedBox(height: 8),
                  if (_keys.isEmpty)
                    const Text(
                        "Scoring options aren't available for this sport yet. Open this screen once while online.")
                  else
                    LayoutBuilder(builder: (context, c) {
                      final w = c.maxWidth >= 480 ? (c.maxWidth - 16) / 3 : (c.maxWidth - 8) / 2;
                      return Wrap(spacing: 8, runSpacing: 8, children: [
                        for (final k in _keys)
                          SizedBox(
                            width: w,
                            child: FilledButton.tonal(
                              onPressed: _busy ? null : () => _score(k),
                              child: Text(humanize(k), textAlign: TextAlign.center),
                            ),
                          ),
                      ]);
                    }),
                  if (!_drawAllowed) ...[
                    const SizedBox(height: 16),
                    Text(
                        "This sport can't end in a draw. If scores are level, record who won the tie-break before ending the match.",
                        style: t.textTheme.bodySmall),
                    const SizedBox(height: 8),
                    OutlinedButton.icon(
                      onPressed: _busy
                          ? null
                          : () {
                              final team = _side == 'home' ? _home : _away;
                              _send(
                                type: 'tiebreak_winner',
                                payload: {'team_id': team['team_id']},
                                confirmTitle: 'Record tie-break winner?',
                                label: 'Tie-break won by ${team['name']}',
                                successText: 'Tie-break winner recorded.',
                              );
                            },
                      icon: const Icon(Icons.emoji_events_outlined, semanticLabel: 'Tie-break winner'),
                      label: Text('Tie-break won by ${(_side == 'home' ? _home : _away)['name']}'),
                    ),
                  ],
                  const SizedBox(height: 16),
                  OutlinedButton.icon(
                    onPressed: _busy ? null : _correct,
                    icon: const Icon(Icons.undo, semanticLabel: 'Correct an event'),
                    label: const Text('Correct an event'),
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    onPressed: _busy
                        ? null
                        : () => _send(
                              type: 'match_end',
                              payload: {},
                              confirmTitle: 'End this match?',
                              label: 'End match',
                              successText: 'Match ended.',
                            ),
                    icon: const Icon(Icons.flag, semanticLabel: 'End match'),
                    label: const Text('End match'),
                  ),
                ],
                if (status != 'upcoming' && status != 'in_progress')
                  Text('This match is ${StatusLabel.text(status).toLowerCase()}. Scores can only be added while it is live.'),
              ],
            ]),
          ),
        ]),
      ),
    );
  }
}
