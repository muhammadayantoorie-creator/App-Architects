import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/formatters.dart';
import '../../core/theme.dart';
import '../widgets/sports.dart';
import '../../data/app_state.dart';
import '../../data/repository.dart';
import '../widgets/common.dart';
import '../widgets/loader.dart';
import '../widgets/network_chip.dart';
import 'fixtures.dart';
import 'roster_sheet.dart';

/// Light rounded list card (same look as the match and product cards).
Widget lightTile({
  required Widget leading,
  required String title,
  String? subtitle,
  IconData? trailing,
  String? trailingLabel,
  VoidCallback? onTap,
  bool threeLine = false,
}) =>
    Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: const Color(0xFFF2F2F2),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        clipBehavior: Clip.antiAlias,
        child: ListTile(
          contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
          leading: leading,
          title: Text(title.toUpperCase(),
              style: const TextStyle(
                  fontFamily: condensedFont,
                  color: Color(0xFF0B0B0B),
                  fontSize: 18,
                  fontWeight: FontWeight.w800)),
          subtitle: subtitle == null || subtitle.isEmpty
              ? null
              : Text(subtitle, style: const TextStyle(color: Color(0xFF555555))),
          isThreeLine: threeLine,
          trailing: trailing == null
              ? null
              : CircleAvatar(
                  radius: 18,
                  backgroundColor: const Color(0xFF0B0B0B),
                  child: Icon(trailing, size: 18, color: AppColors.primary, semanticLabel: trailingLabel),
                ),
          onTap: onTap,
        ),
      ),
    );

Widget inkCircle(Widget child) =>
    CircleAvatar(radius: 22, backgroundColor: const Color(0xFF0B0B0B), child: child);

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
        child: ListView(padding: const EdgeInsets.fromLTRB(12, 0, 12, 16), children: [
          const ExploreHeading('Clubs'),
          for (final id in ids)
            lightTile(
              leading: TeamBadge(teamId: id, name: '${names[id] ?? id}', size: 44, showName: false),
              title: '${names[id] ?? id}',
              trailing: Icons.chevron_right,
              trailingLabel: 'Open club',
              onTap: () => Navigator.push(
                  context, MaterialPageRoute<void>(builder: (_) => ClubScreen(clubId: id))),
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
    final venue = asMap(club['home_venue']);
    final social = asMap(club['social']);
    final name = '${club['name'] ?? ''}';
    return DefaultTabController(
      length: 4,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Container(
          margin: const EdgeInsets.fromLTRB(12, 4, 12, 8),
          clipBehavior: Clip.antiAlias,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(32),
            color: AppColors.header,
            image: const DecorationImage(image: AssetImage('assets/stadium.jpg'), fit: BoxFit.cover),
          ),
          child: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0xB3000000), Color(0x66000000), Color(0xCC3E6B0E)],
            ),
          ),
          padding: const EdgeInsets.fromLTRB(16, 20, 16, 20),
          child: Row(children: [
            TeamBadge(teamId: widget.clubId, name: name, size: 68, light: true, showName: false),
            const SizedBox(width: 14),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(name.toUpperCase(),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        fontFamily: condensedFont,
                        color: Colors.white,
                        fontSize: 32,
                        height: 1.0,
                        fontWeight: FontWeight.w900)),
                const SizedBox(height: 4),
                if (venue['name'] != null)
                  Row(children: [
                    const Icon(Icons.place, size: 14, color: Colors.white70, semanticLabel: 'Venue'),
                    const SizedBox(width: 4),
                    Flexible(
                      child: Text('${venue['name']}',
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(color: Colors.white70, fontSize: 13)),
                    ),
                  ]),
                if (social.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Wrap(spacing: 6, runSpacing: 4, children: [
                    for (final e in social.entries)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                            color: Colors.white24, borderRadius: BorderRadius.circular(10)),
                        child: Text('${humanize(e.key)} ${e.value}',
                            style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w600)),
                      ),
                  ]),
                ],
              ]),
            ),
          ]),
          ),
        ),
        Container(
          margin: const EdgeInsets.fromLTRB(12, 0, 12, 4),
          padding: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            color: const Color(0xFF151517),
            borderRadius: BorderRadius.circular(40),
            border: Border.all(color: AppColors.chip),
          ),
          child: TabBar(
            indicator: BoxDecoration(color: AppColors.primary, borderRadius: BorderRadius.circular(30)),
            indicatorSize: TabBarIndicatorSize.tab,
            dividerColor: Colors.transparent,
            labelColor: AppColors.onPrimary,
            unselectedLabelColor: Colors.white,
            labelStyle: const TextStyle(fontWeight: FontWeight.w800, fontSize: 14),
            labelPadding: EdgeInsets.zero,
            tabs: const [
              Tab(height: 44, text: 'Squad'),
              Tab(height: 44, text: 'Matches'),
              Tab(height: 44, text: 'Staff'),
              Tab(height: 44, text: 'History'),
            ],
          ),
        ),
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
    Future<void> addPlayer() async {
      final added = await showAddPlayerSheet(context, club: club);
      if (added == true) reload();
    }

    if (roster.isEmpty) {
      return RefreshIndicator(
        onRefresh: reload,
        child: ScrollableEmpty(
          child: EmptyState(
            icon: Icons.person_off_outlined,
            message: 'No players registered yet.',
            actionLabel: canManage ? 'Add player' : null,
            onAction: canManage ? addPlayer : null,
          ),
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: reload,
      child: ListView(padding: const EdgeInsets.all(16), children: [
        if (canManage) ...[
          OutlinedButton.icon(
            onPressed: addPlayer,
            icon: const Icon(Icons.person_add_alt, semanticLabel: 'Add player'),
            label: const Text('Add player'),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text('Tap a player to transfer, loan or release.',
                style: Theme.of(context).textTheme.bodySmall),
          ),
        ],
        for (final p in roster)
          lightTile(
            leading: inkCircle(Text('${p['position'] ?? '?'}'.toUpperCase(),
                style: const TextStyle(
                    color: AppColors.primary, fontSize: 12, fontWeight: FontWeight.w900))),
            title: '${p['name'] ?? ''}',
            subtitle: [
              humanize(p['role'] as String?),
              if (p['on_loan'] == true) 'On loan',
            ].where((x) => x.isNotEmpty).join(' · '),
            trailing: canManage ? Icons.swap_horiz : Icons.history,
            trailingLabel: canManage ? 'Roster actions' : 'Player history',
            onTap: () async {
              if (canManage) {
                final changed = await showRosterSheet(context, club: club, player: p);
                if (changed == true) reload();
              } else {
                _openHistory(p);
              }
            },
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
        lightTile(
          leading: inkCircle(const Icon(Icons.badge_outlined,
              color: AppColors.primary, semanticLabel: 'Staff member')),
          title: '${s['name'] ?? ''}',
          subtitle: humanize(s['role'] as String?),
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
        lightTile(
          leading: inkCircle(
              const Icon(Icons.history, color: AppColors.primary, semanticLabel: 'History')),
          title: '${p['name'] ?? ''}',
          subtitle: '${p['audit_count'] ?? 0} recorded changes',
          trailing: Icons.chevron_right,
          trailingLabel: 'Open history',
          onTap: () => _openHistory(p),
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
  Widget build(BuildContext context) {
    final league = context.select<AppState, String>((s) => s.leagueId);
    return loadedBody(context, (d) {
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
                  FixtureTile(row: r, leagueId: league),
                ]),
              ),
          ]),
        );
      });
  }
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
            final m = asMap(d);
            final items = d is List ? asList(d) : asList(m['history'] ?? m['items']);
            if (items.isEmpty) {
              return const EmptyState(
                  icon: Icons.history, message: 'No transfers, loans or releases recorded yet.');
            }
            final t = Theme.of(context);
            return ListView(padding: const EdgeInsets.all(16), children: [
              if (m.containsKey('current_squad_id'))
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(
                      m['current_squad_id'] == null
                          ? 'Currently not registered with a squad.'
                          : 'Current squad: ${m['current_squad_id']}'
                              '${m['parent_squad_id'] != null ? ' (on loan from ${m['parent_squad_id']})' : ''}',
                      style: t.textTheme.titleSmall),
                ),
              for (final h in items.reversed)
                lightTile(
                    leading: inkCircle(Icon(
                        switch (h['action'] ?? h['type']) {
                          'loan' => Icons.schedule_send,
                          'loan_return' => Icons.keyboard_return,
                          'release' => Icons.logout,
                          'add' => Icons.person_add_alt,
                          _ => Icons.swap_horiz,
                        },
                        color: AppColors.primary,
                        semanticLabel: 'Roster change')),
                    title: humanize('${h['action'] ?? h['type'] ?? 'Change'}'),
                    subtitle: [
                      if (h['from_squad_id'] != null || h['to_squad_id'] != null)
                        '${h['from_squad_id'] ?? '—'} → ${h['to_squad_id'] ?? 'released'}',
                      if (h['effective_date'] != null) 'Effective ${h['effective_date']}',
                      if (h['state'] == 'deferred_until_match_end') 'After current match',
                      if ((h['why'] ?? h['reason']) != null) 'Why: ${h['why'] ?? h['reason']}',
                      if ((h['who'] ?? h['requested_by']) != null) 'By ${h['who'] ?? h['requested_by']}',
                      if (parseDate(h['when']) != null) dateTimeLabel(parseDate(h['when'])!),
                    ].join('\n'),
                    threeLine: true,
                ),
            ]);
          }),
        ),
      );
}
