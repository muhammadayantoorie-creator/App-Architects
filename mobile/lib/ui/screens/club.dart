import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/formatters.dart';
import '../../data/app_state.dart';
import '../../data/repository.dart';
import '../widgets/common.dart';
import '../widgets/loader.dart';
import '../widgets/network_chip.dart';
import 'fixtures.dart';
import 'roster_sheet.dart';

/// Club tab: the user's own club, or a list of league clubs when the user has none.
class ClubTab extends StatelessWidget {
  const ClubTab({super.key});

  @override
  Widget build(BuildContext context) {
    final clubId = context.select<AppState, String?>((s) => s.clubId);
    return clubId != null ? ClubView(clubId: clubId) : const _ClubList();
  }
}

class ClubScreen extends StatelessWidget {
  const ClubScreen({super.key, required this.clubId});
  final String clubId;

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Club'), actions: const [NetworkChip()]),
        body: SafeArea(child: ClubView(clubId: clubId)),
      );
}

class _ClubList extends StatefulWidget {
  const _ClubList();

  @override
  State<_ClubList> createState() => _ClubListState();
}

class _ClubListState extends State<_ClubList> with Loader {
  @override
  Future<Loaded> fetch() => app.repo.standings(app.leagueId);

  @override
  Widget build(BuildContext context) {
    return loadedBody(context, (d) {
      final data = asMap(d);
      final names = asMap(data['team_names']);
      final ids = asList(data['table']).map((r) => r['team_id']).whereType<String>().toList();
      for (final id in names.keys) {
        if (!ids.contains(id)) ids.add(id);
      }
      if (ids.isEmpty) {
        return RefreshIndicator(
          onRefresh: reload,
          child: const ScrollableEmpty(
            child: EmptyState(icon: Icons.groups_outlined, message: 'No clubs in this league yet.'),
          ),
        );
      }
      return RefreshIndicator(
        onRefresh: reload,
        child: ListView(padding: const EdgeInsets.all(16), children: [
          Text('Clubs', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          for (final id in ids)
            Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                leading: const Icon(Icons.shield_outlined, semanticLabel: 'Club'),
                title: Text('${names[id] ?? id}'),
                trailing: const Icon(Icons.chevron_right, semanticLabel: 'Open club'),
                onTap: () => Navigator.push(
                    context, MaterialPageRoute<void>(builder: (_) => ClubScreen(clubId: id))),
              ),
            ),
        ]),
      );
    });
  }
}

class ClubView extends StatefulWidget {
  const ClubView({super.key, required this.clubId});
  final String clubId;

  @override
  State<ClubView> createState() => _ClubViewState();
}

class _ClubViewState extends State<ClubView> with Loader {
  @override
  Future<Loaded> fetch() => app.repo.club(widget.clubId);

  @override
  Widget build(BuildContext context) =>
      loadedBody(context, (d) => _content(context, asMap(d)));

  Widget _content(BuildContext context, Map<String, dynamic> club) {
    final t = Theme.of(context);
    final venue = asMap(club['home_venue']);
    final social = asMap(club['social']);
    return DefaultTabController(
      length: 4,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: Row(children: [
            CircleAvatar(
              radius: 22,
              backgroundColor: t.colorScheme.primaryContainer,
              child: Icon(Icons.shield, color: t.colorScheme.onPrimaryContainer,
                  semanticLabel: 'Club crest'),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('${club['name'] ?? ''}',
                    style: t.textTheme.titleLarge, overflow: TextOverflow.ellipsis),
                Text(
                  [
                    if (venue['name'] != null) '${venue['name']}',
                    for (final e in social.entries) '${humanize(e.key)}: ${e.value}',
                  ].join(' · '),
                  style: t.textTheme.bodySmall?.copyWith(color: t.colorScheme.onSurfaceVariant),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ]),
            ),
          ]),
        ),
        const TabBar(isScrollable: true, tabAlignment: TabAlignment.start, tabs: [
          Tab(text: 'Squad'),
          Tab(text: 'Matches'),
          Tab(text: 'Staff'),
          Tab(text: 'History'),
        ]),
        Expanded(
          child: TabBarView(children: [
            _squad(context, club),
            _ClubMatches(clubId: widget.clubId),
            _staff(context, club),
            _history(context, club),
          ]),
        ),
      ]),
    );
  }

  Widget _squad(BuildContext context, Map<String, dynamic> club) {
    final roster = asList(club['roster']);
    final canManage = context.select<AppState, bool>((s) => s.canManageClub(widget.clubId));
    if (roster.isEmpty) {
      return RefreshIndicator(
        onRefresh: reload,
        child: const ScrollableEmpty(
            child: EmptyState(icon: Icons.person_off_outlined, message: 'No players registered yet.')),
      );
    }
    return RefreshIndicator(
      onRefresh: reload,
      child: ListView(padding: const EdgeInsets.all(16), children: [
        if (canManage)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text('Tap a player to transfer, loan or release.',
                style: Theme.of(context).textTheme.bodySmall),
          ),
        for (final p in roster)
          Card(
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              leading: CircleAvatar(
                child: Text('${p['position'] ?? '?'}'.toUpperCase(),
                    style: const TextStyle(fontSize: 12)),
              ),
              title: Text('${p['name'] ?? ''}'),
              subtitle: Text([
                humanize(p['role'] as String?),
                if (p['on_loan'] == true) 'On loan',
              ].where((x) => x.isNotEmpty).join(' · ')),
              trailing: Icon(canManage ? Icons.swap_horiz : Icons.history,
                  semanticLabel: canManage ? 'Roster actions' : 'Player history'),
              onTap: () async {
                if (canManage) {
                  final changed = await showRosterSheet(context, club: club, player: p);
                  if (changed == true) reload();
                } else {
                  _openHistory(p);
                }
              },
            ),
          ),
      ]),
    );
  }

  Widget _staff(BuildContext context, Map<String, dynamic> club) {
    final staff = asList(club['staff']);
    if (staff.isEmpty) {
      return const EmptyState(icon: Icons.badge_outlined, message: 'No staff listed for this club.');
    }
    return ListView(padding: const EdgeInsets.all(16), children: [
      for (final s in staff)
        Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            leading: const Icon(Icons.badge_outlined, semanticLabel: 'Staff member'),
            title: Text('${s['name'] ?? ''}'),
            subtitle: Text(humanize(s['role'] as String?)),
          ),
        ),
    ]);
  }

  Widget _history(BuildContext context, Map<String, dynamic> club) {
    final roster = asList(club['roster']);
    if (roster.isEmpty) {
      return const EmptyState(icon: Icons.history, message: 'No player history yet.');
    }
    return ListView(padding: const EdgeInsets.all(16), children: [
      Text('Registration history per player', style: Theme.of(context).textTheme.bodySmall),
      const SizedBox(height: 8),
      for (final p in roster)
        Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            leading: const Icon(Icons.history, semanticLabel: 'History'),
            title: Text('${p['name'] ?? ''}'),
            subtitle: Text('${p['audit_count'] ?? 0} recorded changes'),
            trailing: const Icon(Icons.chevron_right, semanticLabel: 'Open history'),
            onTap: () => _openHistory(p),
          ),
        ),
    ]);
  }

  void _openHistory(Map<String, dynamic> p) => Navigator.push(
        context,
        MaterialPageRoute<void>(
          builder: (_) => PlayerHistoryScreen(
              playerId: p['player_id'] as String, name: '${p['name'] ?? 'Player'}'),
        ),
      );
}

class _ClubMatches extends StatefulWidget {
  const _ClubMatches({required this.clubId});
  final String clubId;

  @override
  State<_ClubMatches> createState() => _ClubMatchesState();
}

class _ClubMatchesState extends State<_ClubMatches> with Loader {
  @override
  Future<Loaded> fetch() => app.repo.fixtures(app.leagueId);

  @override
  Widget build(BuildContext context) => loadedBody(context, (d) {
        final rows = asList(asMap(d)['fixtures'])
            .where((r) => r['home_team_id'] == widget.clubId || r['away_team_id'] == widget.clubId)
            .toList()
          ..sort((a, b) => '${a['scheduled_at']}'.compareTo('${b['scheduled_at']}'));
        if (rows.isEmpty) {
          return const EmptyState(
              icon: Icons.event_busy, message: 'No matches for this club in the selected league.');
        }
        return RefreshIndicator(
          onRefresh: reload,
          child: ListView(padding: const EdgeInsets.all(16), children: [
            for (final r in rows)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  if (parseDate(r['scheduled_at']) != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Text(dayLabel(parseDate(r['scheduled_at'])!),
                          style: Theme.of(context).textTheme.labelMedium),
                    ),
                  FixtureTile(row: r, leagueId: app.leagueId),
                ]),
              ),
          ]),
        );
      });
}

class PlayerHistoryScreen extends StatefulWidget {
  const PlayerHistoryScreen({super.key, required this.playerId, required this.name});
  final String playerId;
  final String name;

  @override
  State<PlayerHistoryScreen> createState() => _PlayerHistoryScreenState();
}

class _PlayerHistoryScreenState extends State<PlayerHistoryScreen> with Loader {
  @override
  Future<Loaded> fetch() => app.repo.playerHistory(widget.playerId);

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text(widget.name), actions: const [NetworkChip()]),
        body: SafeArea(
          child: loadedBody(context, (d) {
            final items = d is List ? asList(d) : asList(asMap(d)['items'] ?? asMap(d)['history']);
            if (items.isEmpty) {
              return const EmptyState(
                  icon: Icons.history, message: 'No transfers, loans or releases recorded yet.');
            }
            return ListView(padding: const EdgeInsets.all(16), children: [
              for (final h in items.reversed)
                Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    leading: const Icon(Icons.swap_horiz, semanticLabel: 'Roster change'),
                    title: Text(humanize('${h['type'] ?? h['action'] ?? 'Change'}')),
                    subtitle: Text([
                      if (h['effective_date'] != null) 'Effective ${h['effective_date']}',
                      if (h['to_squad_id'] != null) 'To ${h['to_squad_id']}',
                      if (h['reason'] != null) '${h['reason']}',
                    ].join(' · ')),
                  ),
                ),
            ]);
          }),
        ),
      );
}
