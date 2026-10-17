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
    // Feature one match in lime: the live one, else the next upcoming one.
    var featured = rows.indexWhere((r) => r['status'] == 'in_progress');
    if (featured < 0) featured = rows.indexWhere((r) => r['status'] == 'upcoming');
    final children = <Widget>[];
    String? lastDay;
    for (var i = 0; i < rows.length; i++) {
      final r = rows[i];
      final d = parseDate(r['scheduled_at']);
      final day = d == null ? 'Date to be confirmed' : dayLabel(d);
      if (day != lastDay) {
        lastDay = day;
        children.add(SectionHeader(day));
      }
      children.add(Padding(
        padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
        child: FixtureTile(row: r, leagueId: _league, highlight: i == featured),
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

/// Ticket-style match card: teams + "VS"/score on top (lime when featured), time panel below.
class FixtureTile extends StatelessWidget {
  const FixtureTile({super.key, required this.row, required this.leagueId, this.highlight = false});
  final Map<String, dynamic> row;
  final String leagueId;
  final bool highlight;

  static const _months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];

  @override
  Widget build(BuildContext context) {
    final status = row['status'] as String?;
    final live = status == 'in_progress';
    final showScore = live || status == 'completed';
    final d = parseDate(row['scheduled_at']);
    final hs = (row['home_score'] as num?) ?? 0;
    final as = (row['away_score'] as num?) ?? 0;
    final homeName = (row['home_name'] as String?) ?? 'TBC';
    final awayName = (row['away_name'] as String?) ?? 'TBC';
    final statusLabel = switch (status) {
      'in_progress' => 'LIVE',
      'completed' => 'FULL TIME',
      'upcoming' => 'UPCOMING',
      _ => humanize(status).toUpperCase(),
    };
    const ink = Color(0xFF0B0B0B);
    const condensed = TextStyle(fontFamily: condensedFont, color: ink, fontWeight: FontWeight.w800);
    Widget side(String id, String name) => Expanded(
          child: Column(children: [
            TeamBadge(teamId: id, name: name, size: 52, showName: false),
            const SizedBox(height: 8),
            Text(name.toUpperCase(),
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: condensed.copyWith(fontSize: 18, height: 1.0)),
          ]),
        );
    Widget cell(Widget child) => Expanded(
          flex: 4,
          child: Container(
            height: 78,
            margin: const EdgeInsets.all(4),
            padding: const EdgeInsets.symmetric(horizontal: 6),
            alignment: Alignment.center,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: const Color(0xFFD0D0D0), width: 1.2),
            ),
            child: FittedBox(fit: BoxFit.scaleDown, child: child),
          ),
        );
    return Semantics(
      button: true,
      label: '$homeName versus $awayName, ${statusLabel.toLowerCase()}'
          '${showScore ? ', score $hs to $as' : ''}${d == null ? '' : ', ${dayLabel(d)} ${hm(d)}'}',
      child: ExcludeSemantics(
        child: Material(
          color: const Color(0xFFF2F2F2),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(32)),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute<void>(
                builder: (_) => MatchScreen(matchId: row['match_id'] as String, leagueId: leagueId),
              ),
            ),
            child: Column(children: [
              Container(
                decoration: BoxDecoration(
                  color: highlight || live ? AppColors.primary : const Color(0xFFCFCFCF),
                  borderRadius: BorderRadius.circular(32),
                ),
                padding: const EdgeInsets.fromLTRB(10, 18, 10, 16),
                child: Row(children: [
                  side('${row['home_team_id']}', homeName),
                  Container(
                    width: 64,
                    height: 64,
                    alignment: Alignment.center,
                    decoration: const BoxDecoration(color: ink, shape: BoxShape.circle),
                    child: FittedBox(
                      fit: BoxFit.scaleDown,
                      child: Padding(
                        padding: const EdgeInsets.all(8),
                        child: Text(showScore ? '$hs:$as' : 'VS',
                            style: condensed.copyWith(
                                color: Colors.white, fontSize: 24, fontWeight: FontWeight.w900)),
                      ),
                    ),
                  ),
                  side('${row['away_team_id']}', awayName),
                ]),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(6, 4, 6, 8),
                child: Row(children: [
                  cell(Row(mainAxisSize: MainAxisSize.min, children: [
                    if (live) ...[
                      Container(
                          width: 9,
                          height: 9,
                          decoration:
                              const BoxDecoration(color: AppColors.live, shape: BoxShape.circle)),
                      const SizedBox(width: 6),
                    ],
                    Text(statusLabel, style: condensed.copyWith(fontSize: 18)),
                  ])),
                  Expanded(
                    flex: 5,
                    child: Column(children: [
                      Text(d == null ? 'TBC' : hm(d),
                          style: condensed.copyWith(
                              fontSize: 44, fontWeight: FontWeight.w900, height: 1.0, letterSpacing: -1)),
                      const SizedBox(height: 2),
                      Text(d == null ? '' : '${d.day.toString().padLeft(2, '0')} ${_months[d.month - 1]}',
                          style: const TextStyle(color: Color(0xFF444444), fontSize: 13)),
                    ]),
                  ),
                  cell(Text.rich(TextSpan(children: [
                    TextSpan(text: 'MATCH ', style: condensed.copyWith(fontSize: 18)),
                    TextSpan(
                        text: 'INFO',
                        style: condensed.copyWith(fontSize: 18, color: const Color(0xFF9A9A9A))),
                  ]))),
                ]),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}
