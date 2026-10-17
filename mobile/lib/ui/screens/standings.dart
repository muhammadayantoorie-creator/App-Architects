import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/formatters.dart';
import '../../core/theme.dart';
import '../../data/app_state.dart';
import '../../data/repository.dart';
import '../widgets/common.dart';
import '../widgets/league_picker.dart';
import '../widgets/loader.dart';
import 'club.dart';

class StandingsTab extends StatefulWidget {
  const StandingsTab({super.key});

  @override
  State<StandingsTab> createState() => _StandingsTabState();
}

class _StandingsTabState extends State<StandingsTab> with Loader {
  late String _league = context.read<AppState>().leagueId;

  @override
  Future<Loaded> fetch() => app.repo.standings(_league);

  @override
  Widget build(BuildContext context) {
    final league = context.select<AppState, String>((s) => s.leagueId);
    if (league != _league) {
      _league = league;
      loaded = null;
      WidgetsBinding.instance.addPostFrameCallback((_) => reload());
    }
    return Column(children: [
      const LeaguePicker(),
      Expanded(child: loadedBody(context, (d) => _table(context, asMap(d)))),
    ]);
  }

  Widget _table(BuildContext context, Map<String, dynamic> data) {
    final t = Theme.of(context);
    final rows = asList(data['table']);
    final names = asMap(data['team_names']);
    final spots = (data['qualification_spots'] as num?)?.toInt() ?? 0;
    if (rows.isEmpty) {
      return RefreshIndicator(
        onRefresh: reload,
        child: const ScrollableEmpty(
          child: EmptyState(
              icon: Icons.leaderboard_outlined,
              message: 'No results yet. The table fills in once matches are played.'),
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: reload,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
        children: [
          if (spots > 0)
            Text('Top $spots qualify', style: t.textTheme.titleSmall),
          const SizedBox(height: 4),
          Text('Tap a team to see its squad and matches.',
              style: t.textTheme.bodySmall?.copyWith(color: t.colorScheme.onSurfaceVariant)),
          const SizedBox(height: 8),
          Card(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: DataTable(
                showCheckboxColumn: false,
                columnSpacing: 14,
                horizontalMargin: 8,
                headingRowHeight: 44,
                dataRowMinHeight: 48,
                dataRowMaxHeight: 56,
                columns: const [
                  DataColumn(label: Text('#'), numeric: true),
                  DataColumn(label: Text('Team')),
                  DataColumn(label: Tooltip(message: 'Played', child: Text('P')), numeric: true),
                  DataColumn(label: Tooltip(message: 'Won', child: Text('W')), numeric: true),
                  DataColumn(label: Tooltip(message: 'Drawn', child: Text('D')), numeric: true),
                  DataColumn(label: Tooltip(message: 'Lost', child: Text('L')), numeric: true),
                  DataColumn(
                      label: Tooltip(message: 'Goal difference', child: Text('GD')),
                      numeric: true),
                  DataColumn(label: Tooltip(message: 'Points', child: Text('Pts')), numeric: true),
                  DataColumn(label: Text('Status')),
                ],
                rows: [
                  for (final r in rows) _row(context, r, names, spots),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          _Legend(spots: spots),
        ],
      ),
    );
  }

  DataRow _row(BuildContext context, Map<String, dynamic> r, Map<String, dynamic> names, int spots) {
    final t = Theme.of(context);
    final (label, color) = statusOf(context, r, spots);
    final teamId = r['team_id'] as String?;
    final name = '${names[teamId] ?? teamId ?? ''}';
    return DataRow(
      onSelectChanged: teamId == null
          ? null
          : (_) => Navigator.push(
                context,
                MaterialPageRoute<void>(builder: (_) => ClubScreen(clubId: teamId)),
              ),
      cells: [
        DataCell(Row(mainAxisSize: MainAxisSize.min, children: [
          Container(width: 4, height: 32, color: color ?? Colors.transparent),
          const SizedBox(width: 8),
          Text('${r['rank'] ?? ''}'),
        ])),
        DataCell(ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 140),
          child: Text(name,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w500)),
        )),
        DataCell(Text('${r['played'] ?? 0}')),
        DataCell(Text('${r['won'] ?? 0}')),
        DataCell(Text('${r['drawn'] ?? 0}')),
        DataCell(Text('${r['lost'] ?? 0}')),
        DataCell(Text(formatDiff(r['diff']))),
        DataCell(Text('${r['points'] ?? 0}', style: const TextStyle(fontWeight: FontWeight.bold))),
        DataCell(Text(label,
            style: t.textTheme.labelLarge?.copyWith(
                color: label == 'Out' ? t.colorScheme.error : null,
                fontWeight: FontWeight.w600))),
      ],
    );
  }
}

(String, Color?) statusOf(BuildContext context, Map<String, dynamic> r, int spots) {
  final s = Theme.of(context).colorScheme;
  final rank = (r['rank'] as num?)?.toInt() ?? 999;
  return switch (r['status']) {
    'clinched' => ('Clinched', clinchedColor),
    'eliminated' => ('Out', s.error),
    _ when rank <= spots => ('Q', s.primary),
    _ => ('—', null),
  };
}

class _Legend extends StatelessWidget {
  const _Legend({required this.spots});
  final int spots;

  @override
  Widget build(BuildContext context) {
    final s = Theme.of(context).colorScheme;
    final style = Theme.of(context).textTheme.bodySmall;
    Widget item(Color c, String text) => Row(mainAxisSize: MainAxisSize.min, children: [
          Container(width: 4, height: 16, color: c),
          const SizedBox(width: 6),
          Flexible(child: Text(text, style: style)),
        ]);
    return Wrap(spacing: 16, runSpacing: 8, children: [
      item(clinchedColor, 'Clinched — qualified for sure'),
      if (spots > 0) item(s.primary, 'Q — in a qualifying place'),
      item(s.error, "Out — can't qualify"),
    ]);
  }
}
