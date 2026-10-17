import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/formatters.dart';
import '../../data/app_state.dart';
import '../../data/live/sse_client.dart';
import '../../data/repository.dart';
import '../widgets/common.dart';
import '../widgets/league_picker.dart';
import '../widgets/loader.dart';
import '../../core/theme.dart';
import '../widgets/sports.dart';
import 'match.dart';

class FixturesTab extends StatefulWidget {
  const FixturesTab({super.key});

  @override
  State<FixturesTab> createState() => _FixturesTabState();
}

class _FixturesTabState extends State<FixturesTab> with Loader {
  late final AppState _s = context.read<AppState>();
  late String _league = _s.leagueId;
  StreamSubscription<LiveEvent>? _sub;

  @override
  Future<Loaded> fetch() => app.repo.fixtures(_league);

  @override
  void initState() {
    super.initState();
    _s.live.acquire(_league);
    _sub = _s.live.events.listen(_onLive);
  }

  @override
  void dispose() {
    _sub?.cancel();
    _s.live.release();
    super.dispose();
  }

  void _onLive(LiveEvent e) {
    if (e.type != 'match_updated' || loaded == null) return;
    final rows = asList(asMap(loaded!.data)['fixtures']);
    final i = rows.indexWhere((r) => r['match_id'] == e.data['match_id']);
    if (i < 0) return;
    for (final k in ['status', 'home_score', 'away_score', 'version']) {
      if (e.data.containsKey(k)) rows[i][k] = e.data[k];
    }
    setState(() => loaded = Loaded({...asMap(loaded!.data), 'fixtures': rows},
        fromCache: loaded!.fromCache, fetchedAt: loaded!.fetchedAt));
  }

  @override
  Widget build(BuildContext context) {
    final league = context.select<AppState, String>((s) => s.leagueId);
    if (league != _league) {
      _league = league;
      loaded = null;
      WidgetsBinding.instance.addPostFrameCallback((_) => reload());
    }
    return Column(children: [
      const ExploreHeading('Leagues'),
      const LeaguePicker(),
      Expanded(child: loadedBody(context, (data) => _list(context, data))),
    ]);
  }

  Widget _list(BuildContext context, dynamic data) {
    final rows = asList(asMap(data)['fixtures'])
      ..sort((a, b) => '${a['scheduled_at']}'.compareTo('${b['scheduled_at']}'));
    if (rows.isEmpty) {
      return RefreshIndicator(
        onRefresh: reload,
        child: const ScrollableEmpty(
          child: EmptyState(
              icon: Icons.event_busy,
              message: 'No matches scheduled yet. Pull down to refresh.'),
        ),
      );
    }
    final children = <Widget>[];
    String? lastDay;
    for (final r in rows) {
      final d = parseDate(r['scheduled_at']);
      final day = d == null ? 'Date to be confirmed' : dayLabel(d);
      if (day != lastDay) {
        lastDay = day;
        children.add(SectionHeader(day));
      }
      children.add(Padding(
        padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
        child: FixtureTile(row: r, leagueId: _league),
      ));
    }
    return RefreshIndicator(
      onRefresh: reload,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.only(bottom: 16),
        children: children,
      ),
    );
  }
}

class FixtureTile extends StatelessWidget {
  const FixtureTile({super.key, required this.row, required this.leagueId});
  final Map<String, dynamic> row;
  final String leagueId;

  @override
  Widget build(BuildContext context) {
    final status = row['status'] as String?;
    final showScore = status == 'in_progress' || status == 'completed';
    final d = parseDate(row['scheduled_at']);
    final hs = (row['home_score'] as num?) ?? 0;
    final as = (row['away_score'] as num?) ?? 0;
    final done = status == 'completed';
    final homeWins = done && hs > as;
    final awayWins = done && as > hs;
    Widget team(String id, String? name, bool win, bool lose) => TeamBadge(
        teamId: id, name: name ?? 'TBC', size: 28, bold: win, dim: lose);
    return Card(
      child: InkWell(
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute<void>(
            builder: (_) => MatchScreen(matchId: row['match_id'] as String, leagueId: leagueId),
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(children: [
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                team('${row['home_team_id']}', row['home_name'] as String?, homeWins, awayWins),
                const SizedBox(height: 8),
                team('${row['away_team_id']}', row['away_name'] as String?, awayWins, homeWins),
              ]),
            ),
            const SizedBox(width: 8),
            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              StatusPill(status: status, time: d),
              if (showScore) ...[
                const SizedBox(height: 4),
                ScoreText('$hs', dim: awayWins),
                ScoreText('$as', dim: homeWins),
              ] else if (d != null) ...[
                const SizedBox(height: 6),
                Text(dayLabel(d), style: const TextStyle(fontSize: 12, color: AppColors.textSub)),
              ],
            ]),
          ]),
        ),
      ),
    );
  }
}
