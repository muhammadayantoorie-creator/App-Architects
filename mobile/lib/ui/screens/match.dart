import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/formatters.dart';
import '../../data/app_state.dart';
import '../../data/live/sse_client.dart';
import '../../data/repository.dart';
import '../widgets/common.dart';
import '../widgets/loader.dart';
import '../widgets/network_chip.dart';
import '../../core/theme.dart';
import '../widgets/sports.dart';
import 'product.dart';
import 'scoring.dart';

class MatchScreen extends StatefulWidget {
  const MatchScreen({super.key, required this.matchId, required this.leagueId});
  final String matchId;
  final String leagueId;

  @override
  State<MatchScreen> createState() => _MatchScreenState();
}

class _MatchScreenState extends State<MatchScreen> with Loader {
  late final AppState _s = context.read<AppState>();
  StreamSubscription<LiveEvent>? _sub;
  Timer? _debounce;

  @override
  Future<Loaded> fetch() => app.repo.match(widget.matchId);

  @override
  void initState() {
    super.initState();
    _s.live.acquire(widget.leagueId);
    _sub = _s.live.events.listen((e) {
      if (e.data['match_id'] != widget.matchId) return;
      _debounce?.cancel();
      _debounce = Timer(const Duration(milliseconds: 600), reload);
    });
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _sub?.cancel();
    _s.live.release();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final canScore = context.select<AppState, bool>((s) => s.canScore);
    return Scaffold(
      appBar: AppBar(title: const Text('Match'), actions: const [NetworkChip()]),
      floatingActionButton: canScore
          ? FloatingActionButton.extended(
              onPressed: () async {
                await Navigator.push(
                  context,
                  MaterialPageRoute<void>(
                    builder: (_) =>
                        ScoringScreen(leagueId: widget.leagueId, matchId: widget.matchId),
                  ),
                );
                reload();
              },
              icon: const Icon(Icons.add, semanticLabel: 'Add score'),
              label: const Text('Add score'),
            )
          : null,
      body: SafeArea(child: loadedBody(context, (d) => _body(context, asMap(d)))),
    );
  }

  Widget _body(BuildContext context, Map<String, dynamic> m) {
    final home = asMap(m['home']);
    final away = asMap(m['away']);
    final names = {home['team_id']: home['name'], away['team_id']: away['name']};
    final events = asList(m['events'])
      ..sort((a, b) => ((b['sequence'] ?? 0) as num).compareTo((a['sequence'] ?? 0) as num));
    final pinned = m['pinned_product'] is Map ? asMap(m['pinned_product']) : null;
    final canBuy = context.select<AppState, bool>((s) => s.canBuy);
    return RefreshIndicator(
      onRefresh: reload,
      child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
        ScoreHeader(match: m),
        if (pinned != null) ...[
          const SizedBox(height: 16),
          Card(
            child: ListTile(
              leading: const Icon(Icons.shopping_bag_outlined, semanticLabel: 'Featured product'),
              title: Text('${pinned['name'] ?? 'Featured product'}'),
              subtitle: Text('Featured · ${money(pinned['price_minor'] as num?, pinned['currency'] as String?)}'),
              trailing: canBuy
                  ? FilledButton(
                      onPressed: () => Navigator.push(
                        context,
                        MaterialPageRoute<void>(
                          builder: (_) =>
                              ProductScreen(productId: pinned['product_id'] as String),
                        ),
                      ),
                      child: const Text('Buy'),
                    )
                  : null,
            ),
          ),
        ],
        const SectionTitle('Timeline'),
        if (events.isEmpty)
          const Text('No events yet. Updates appear here live.')
        else
          for (final e in events) _EventTile(event: e, names: names),
      ]),
    );
  }
}

class ScoreHeader extends StatelessWidget {
  const ScoreHeader({super.key, required this.match});
  final Map<String, dynamic> match;

  static String scoreText(Map<String, dynamic> side) {
    final score = '${side['score'] ?? 0}';
    return side['wickets'] != null ? '$score/${side['wickets']}' : score;
  }

  @override
  Widget build(BuildContext context) {
    final home = asMap(match['home']);
    final away = asMap(match['away']);
    final d = parseDate(match['scheduled_at']);
    final venue = asMap(match['venue'])['name'];
    final status = match['status'] as String?;
    final showScore = status == 'in_progress' || status == 'completed';
    const sub = TextStyle(color: Colors.white70, fontSize: 12);
    Widget side(Map<String, dynamic> s, String role) => Expanded(
          child: Column(children: [
            TeamBadge(
                teamId: '${s['team_id']}', name: '${s['name'] ?? 'TBC'}', size: 56, light: true, showName: false),
            const SizedBox(height: 8),
            Text('${s['name'] ?? 'TBC'}',
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w700)),
            Text(s['overs'] != null ? '$role · ${s['overs']} ov' : role, style: sub),
          ]),
        );
    return Container(
      decoration: BoxDecoration(color: AppColors.header, borderRadius: BorderRadius.circular(24)),
      padding: const EdgeInsets.all(20),
      child: Column(children: [
        StatusPill(status: status, time: d),
        const SizedBox(height: 6),
        Text(
          [if (venue != null) '$venue', if (d != null) dateTimeLabel(d)].join(' · '),
          style: sub,
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 16),
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          side(home, 'Home'),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
            child: FittedBox(
              child: Text(
                showScore ? '${scoreText(home)} - ${scoreText(away)}' : 'vs',
                style: const TextStyle(
                    color: Colors.white,
                    fontSize: 40,
                    fontWeight: FontWeight.w800,
                    fontFeatures: [FontFeature.tabularFigures()]),
                semanticsLabel: showScore
                    ? '${home['name']} ${scoreText(home)}, ${away['name']} ${scoreText(away)}'
                    : 'versus',
              ),
            ),
          ),
          side(away, 'Away'),
        ]),
      ]),
    );
  }
}

String eventTitle(Map<String, dynamic> e, Map<dynamic, dynamic> names) {
  final p = asMap(e['payload']);
  final team = names[p['team_id']];
  return switch (e['type']) {
    'score' => '${humanize(p['event_type'] as String?)}${team != null ? ' — $team' : ''}',
    'match_init' => 'Match created',
    'match_start' => 'Match started',
    'match_end' => 'Match ended',
    'compensation' => 'Correction${p['reason'] != null ? ': ${p['reason']}' : ''}',
    'discipline' => 'Fair-play ${p['points'] ?? ''}${team != null ? ' — $team' : ''}',
    'tiebreak_winner' => 'Tie-break won${team != null ? ' — $team' : ''}',
    _ => '${humanize(e['type'] as String?)}${team != null ? ' — $team' : ''}',
  };
}

class _EventTile extends StatelessWidget {
  const _EventTile({required this.event, required this.names});
  final Map<String, dynamic> event;
  final Map<dynamic, dynamic> names;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final corrected = event['compensated'] == true;
    final icon = switch (event['type']) {
      'score' => Icons.sports_score,
      'match_start' => Icons.play_arrow,
      'match_end' => Icons.flag,
      'compensation' => Icons.undo,
      'discipline' => Icons.style,
      'tiebreak_winner' => Icons.emoji_events_outlined,
      _ => Icons.circle_outlined,
    };
    return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Column(children: [
        CircleAvatar(
          radius: 16,
          backgroundColor: t.colorScheme.secondaryContainer,
          child: Icon(icon, size: 18, color: t.colorScheme.onSecondaryContainer,
              semanticLabel: humanize(event['type'] as String?)),
        ),
        Container(width: 2, height: 24, color: t.colorScheme.outlineVariant),
      ]),
      const SizedBox(width: 12),
      Expanded(
        child: Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Wrap(spacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
            Text(
              eventTitle(event, names),
              style: t.textTheme.bodyLarge?.copyWith(
                decoration: corrected ? TextDecoration.lineThrough : null,
                color: corrected ? t.colorScheme.onSurfaceVariant : null,
              ),
            ),
            if (corrected)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  border: Border.all(color: t.colorScheme.outline),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text('Corrected', style: t.textTheme.labelSmall),
              ),
          ]),
        ),
      ),
      Padding(
        padding: const EdgeInsets.only(top: 6),
        child: Text('#${event['sequence'] ?? ''}', style: t.textTheme.labelSmall),
      ),
    ]);
  }
}
